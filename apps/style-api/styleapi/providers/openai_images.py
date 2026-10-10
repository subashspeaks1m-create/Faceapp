"""OpenAI Images API edit endpoint (POST {base}/images/edits, multipart).

GPT image models always return base64 (`data[0].b64_json`). `input_fidelity` is sent only to models that
accept it; OpenAI's guide says to omit it for gpt-image-2, which processes inputs at high fidelity.
Provider error text is never forwarded to clients; only its category is.
"""

from __future__ import annotations

import base64
import binascii
import logging

import httpx

from ..errors import ApiError
from .base import EditRequest, EditResult

log = logging.getLogger("styleapi.provider")

_INPUT_FIDELITY_MODELS = frozenset({"gpt-image-1", "gpt-image-1.5"})


class OpenAIImageEditProvider:
    name = "openai"

    def __init__(
        self,
        api_key: str,
        *,
        model: str,
        quality: str,
        base_url: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._quality = quality
        self._base_url = base_url
        self._timeout = timeout_seconds
        self._transport = transport

    def __repr__(self) -> str:  # never show the key
        return f"OpenAIImageEditProvider(model={self._model!r})"

    def _form(self, request: EditRequest) -> dict[str, str]:
        form = {
            "model": self._model,
            "prompt": request.prompt,
            "n": "1",
            "size": request.size,
            "quality": self._quality,
            "output_format": "jpeg",
            "output_compression": "92",
        }
        if self._model in _INPUT_FIDELITY_MODELS:
            form["input_fidelity"] = "high"
        return form

    async def edit(self, request: EditRequest) -> EditResult:
        files = {"image": ("photo.png", request.image_png, "image/png")}
        timeout = httpx.Timeout(self._timeout, connect=10.0)
        try:
            async with httpx.AsyncClient(timeout=timeout, transport=self._transport) as client:
                resp = await client.post(
                    f"{self._base_url}/images/edits",
                    data=self._form(request),
                    files=files,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
        except httpx.TimeoutException as e:
            raise ApiError("PROVIDER_TIMEOUT") from e
        except httpx.HTTPError as e:
            raise ApiError("PROVIDER_ERROR") from e

        if resp.status_code != 200:
            raise _map_error(resp)
        return self._parse(resp)

    def _parse(self, resp: httpx.Response) -> EditResult:
        try:
            payload = resp.json()
        except ValueError as e:
            raise ApiError("INVALID_PROVIDER_RESPONSE") from e
        data = payload.get("data") if isinstance(payload, dict) else None
        first = data[0] if isinstance(data, list) and data else None
        b64 = first.get("b64_json") if isinstance(first, dict) else None
        if not isinstance(b64, str) or not b64:
            raise ApiError("INVALID_PROVIDER_RESPONSE")
        try:
            image = base64.b64decode(b64, validate=True)
        except (binascii.Error, ValueError) as e:
            raise ApiError("INVALID_PROVIDER_RESPONSE") from e
        usage = payload.get("usage") if isinstance(payload, dict) else None
        input_tokens = usage.get("input_tokens") if isinstance(usage, dict) else None
        output_tokens = usage.get("output_tokens") if isinstance(usage, dict) else None
        return EditResult(
            image=image,
            model=self._model,
            input_tokens=input_tokens if isinstance(input_tokens, int) else None,
            output_tokens=output_tokens if isinstance(output_tokens, int) else None,
        )


def _map_error(resp: httpx.Response) -> ApiError:
    status = resp.status_code
    code = ""
    try:
        body = resp.json()
        err = body.get("error") if isinstance(body, dict) else None
        if isinstance(err, dict):
            code = str(err.get("code") or err.get("type") or "")
    except ValueError:
        pass
    # Only the status and OpenAI's short error code are logged; never the message, which can echo input.
    log.warning("provider_error status=%s code=%s", status, code[:60])
    if status in (401, 403):
        # A wrong or revoked key is a server configuration problem, not the user's.
        return ApiError("PROVIDER_NOT_CONFIGURED", "AI styles are not available right now because the server's AI account is not set up correctly.")
    if status == 429:
        return ApiError("GENERATION_UNAVAILABLE", "The AI service is busy or out of credit. Try again later.")
    if status == 400 and ("moderation" in code or "safety" in code or "content_policy" in code):
        return ApiError("PROVIDER_REJECTED")
    if status in (400, 404, 413, 415, 422):
        # Usually a request/config mismatch (model, size), so not blamed on the photo.
        return ApiError("PROVIDER_ERROR", "The AI service could not process this request. Try again, or try a different photo.")
    if status in (408, 504):
        return ApiError("PROVIDER_TIMEOUT")
    return ApiError("PROVIDER_ERROR")
