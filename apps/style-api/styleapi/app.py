"""PortraitLab style API: one-tap AI style transfer for a single uploaded photo.

Stateless: the photo and result exist only in memory for the duration of the request.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.datastructures import UploadFile

from .catalog import Catalog, build_prompt, load_catalog, public_catalog
from .config import ConfigError, Settings, load_settings
from .errors import ApiError
from .images import finalize_output, prepare_upload
from .providers import EditRequest, ImageEditProvider, OpenAIImageEditProvider
from .ratelimit import Quota, RateLimiter, client_id_from, make_limiter

log = logging.getLogger("styleapi")

_INTENSITY = re.compile(r"^(?:100|[1-9]?[0-9])$")
_DEV_SALT = "development-only-salt"
_EXPOSED_HEADERS = ["X-Request-ID", "X-Quota-Remaining", "X-Quota-Limit", "X-Quota-Window", "X-Style-Id", "X-Catalog-Version", "Retry-After"]
# Multipart overhead allowance on top of the image limit.
_FORM_OVERHEAD = 64 * 1024


@dataclass
class _State:
    settings: Settings | None
    config_error: str | None
    catalog: Catalog
    provider: ImageEditProvider | None
    limiter: RateLimiter | None


def _new_request_id() -> str:
    return uuid.uuid4().hex


def _error_response(err: ApiError, request_id: str) -> JSONResponse:
    headers = {"X-Request-ID": request_id, "Cache-Control": "no-store"}
    if err.retry_after_seconds is not None:
        headers["Retry-After"] = str(err.retry_after_seconds)
    return JSONResponse(err.body(request_id), status_code=err.status, headers=headers)


def _quota_headers(q: Quota) -> dict[str, str]:
    return {"X-Quota-Remaining": str(q.remaining), "X-Quota-Limit": str(q.limit), "X-Quota-Window": q.window}


def create_app(
    settings: Settings | None = None,
    *,
    provider: ImageEditProvider | None = None,
    limiter: RateLimiter | None = None,
) -> FastAPI:
    config_error: str | None = None
    if settings is None:
        try:
            settings = load_settings()
        except ConfigError as e:
            config_error = str(e)
            log.error("config_error %s", config_error)

    if settings is not None and provider is None and settings.openai_api_key is not None:
        provider = OpenAIImageEditProvider(
            settings.openai_api_key.get_secret_value(),
            model=settings.openai_model,
            quality=settings.openai_quality,
            base_url=settings.openai_base_url,
            timeout_seconds=settings.provider_timeout_seconds,
        )
    if settings is not None and limiter is None:
        limiter = make_limiter(settings)

    state = _State(settings=settings, config_error=config_error, catalog=load_catalog(), provider=provider, limiter=limiter)
    app = FastAPI(title="PortraitLab Style API", version=state.catalog.version, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.styleapi = state

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return _error_response(exc, getattr(request.state, "request_id", _new_request_id()))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _error_response(ApiError("INVALID_REQUEST"), getattr(request.state, "request_id", _new_request_id()))

    @app.middleware("http")
    async def _request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = _new_request_id()
        request.state.request_id = request_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as e:
            # Exception type only: messages and tracebacks could carry request data.
            log.error("unhandled request_id=%s path=%s type=%s", request_id, request.url.path, type(e).__name__)
            response = _error_response(ApiError("INTERNAL_ERROR"), request_id)
        response.headers["X-Request-ID"] = request_id
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        log.info(
            "request request_id=%s method=%s path=%s status=%s duration_ms=%d",
            request_id, request.method, request.url.path, response.status_code, (time.perf_counter() - start) * 1000,
        )
        return response

    def _origin_check(request: Request) -> None:
        s = state.settings
        origin = request.headers.get("origin")
        # Native apps send no Origin. Browsers always do on cross-origin POST; refuse unknown sites.
        if s is not None and origin is not None and origin.rstrip("/") not in s.allowed_origins:
            raise ApiError("ORIGIN_NOT_ALLOWED")

    def _client_ip(request: Request) -> str:
        s = state.settings
        if s is not None and s.trust_proxy_headers:
            for header in ("x-vercel-forwarded-for", "x-real-ip", "x-forwarded-for"):
                value = request.headers.get(header)
                if value:
                    return value.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _client_id(request: Request) -> str:
        s = state.settings
        assert s is not None
        if s.rate_limit_salt is not None:
            salt = s.rate_limit_salt.get_secret_value()
        elif s.is_production:
            raise ApiError("GENERATION_UNAVAILABLE")
        else:
            salt = _DEV_SALT
        return client_id_from(_client_ip(request), salt)

    @app.get("/api/health")
    async def health() -> JSONResponse:
        s = state.settings
        ready = s is not None and state.provider is not None
        body = {
            "status": "ok" if ready else ("misconfigured" if s is None else "provider_not_configured"),
            "provider_configured": state.provider is not None,
            "provider": getattr(state.provider, "name", None),
            "model": s.openai_model if s is not None and state.provider is not None else None,
            "rate_limit_backend": s.rate_limit_backend if s is not None else None,
            "catalog_version": state.catalog.version,
            "style_count": len(state.catalog.styles),
        }
        return JSONResponse(body, headers={"Cache-Control": "no-store"})

    @app.get("/api/styles")
    async def styles() -> JSONResponse:
        return JSONResponse(public_catalog(state.catalog), headers={"Cache-Control": "public, max-age=300"})

    @app.get("/api/quota")
    async def quota(request: Request) -> JSONResponse:
        if state.settings is None or state.limiter is None:
            raise ApiError("GENERATION_UNAVAILABLE")
        q = await state.limiter.peek(_client_id(request))
        return JSONResponse({"remaining": q.remaining, "limit": q.limit, "window": q.window}, headers={"Cache-Control": "no-store", **_quota_headers(q)})

    @app.post("/api/generate")
    async def generate(request: Request) -> Response:
        request_id: str = request.state.request_id
        s = state.settings
        if s is None or state.limiter is None:
            raise ApiError("GENERATION_UNAVAILABLE")
        _origin_check(request)
        if state.provider is None:
            raise ApiError("PROVIDER_NOT_CONFIGURED")

        length = request.headers.get("content-length")
        if length is None or not length.isdigit():
            raise ApiError("INVALID_REQUEST", "The upload size was not given.")
        if int(length) > s.max_upload_bytes + _FORM_OVERHEAD:
            raise ApiError("IMAGE_TOO_LARGE")
        if not request.headers.get("content-type", "").startswith("multipart/form-data"):
            raise ApiError("INVALID_REQUEST", "Send the photo as multipart form data.")

        try:
            form = await request.form(max_files=1, max_fields=4)
        except Exception as e:  # malformed multipart
            raise ApiError("INVALID_REQUEST") from e
        try:
            image = form.get("image")
            style_id = form.get("style_id")
            intensity_raw = form.get("intensity")
            consent = form.get("consent")
            if not isinstance(image, UploadFile):
                raise ApiError("INVALID_IMAGE", "No photo was received.")
            if consent != "true":
                raise ApiError("CONSENT_REQUIRED")
            if not isinstance(style_id, str):
                raise ApiError("INVALID_STYLE")
            style = state.catalog.style(style_id)
            if style is None:
                raise ApiError("INVALID_STYLE")
            if not isinstance(intensity_raw, str) or not _INTENSITY.fullmatch(intensity_raw):
                raise ApiError("INVALID_REQUEST", "Strength must be a whole number from 0 to 100.")
            intensity = int(intensity_raw)

            data = await image.read(s.max_upload_bytes + 1)
            prepared = prepare_upload(
                data, image.content_type, max_bytes=s.max_upload_bytes, max_pixels=s.max_input_pixels, min_side=s.min_input_side
            )
            del data
        finally:
            await form.close()

        quota = await state.limiter.reserve(_client_id(request))
        prompt = build_prompt(style, intensity, state.catalog)
        started = time.perf_counter()
        try:
            result = await state.provider.edit(EditRequest(image_png=prepared.png, prompt=prompt, size=prepared.size))
            jpeg, width, height = finalize_output(result.image)
        except ApiError as e:
            log.info("generate_failed request_id=%s style=%s code=%s provider_ms=%d", request_id, style.id, e.code, (time.perf_counter() - started) * 1000)
            raise
        log.info(
            "generate_ok request_id=%s style=%s intensity=%d size=%dx%d provider_ms=%d input_tokens=%s output_tokens=%s",
            request_id, style.id, intensity, width, height, (time.perf_counter() - started) * 1000, result.input_tokens, result.output_tokens,
        )
        headers = {
            "Cache-Control": "no-store",
            "Content-Disposition": f'inline; filename="portraitlab-{style.id}.jpg"',
            "X-Style-Id": style.id,
            "X-Catalog-Version": state.catalog.version,
            **_quota_headers(quota),
        }
        return Response(content=jpeg, media_type="image/jpeg", headers=headers)

    # Added last so it is the outermost middleware and error responses also carry CORS headers.
    if settings is not None and settings.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.allowed_origins),
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
            expose_headers=_EXPOSED_HEADERS,
            allow_credentials=False,
            max_age=600,
        )
    return app
