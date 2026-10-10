"""Executable API contract shell. Inject an implemented Runtime to enable routes.

Default fails closed with503. No fake queue/database/auth/paid success is supplied.
"""

from __future__ import annotations
from typing import Annotated, Protocol
from uuid import UUID, uuid4
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from schemas import (
    UploadRequest,
    UploadGrant,
    UploadComplete,
    AssetReceipt,
    TransformRequest,
    JobPayload,
    SafeError,
    DeletionReceipt,
)


class Runtime(Protocol):
    async def authenticate(self, token: str) -> UUID: ...
    async def upload(self, owner: UUID, body: UploadRequest) -> UploadGrant: ...
    async def complete(self, owner: UUID, asset_id: UUID, body: UploadComplete) -> AssetReceipt: ...
    async def transform(self, owner: UUID, body: TransformRequest, idempotency_key: str) -> JobPayload: ...
    async def status(self, owner: UUID, job_id: UUID, wait_seconds: int, after_revision: int) -> JobPayload: ...
    async def cancel(self, owner: UUID, job_id: UUID) -> JobPayload: ...
    async def delete(self, owner: UUID, job_id: UUID) -> DeletionReceipt: ...


app = FastAPI(
    title="PortraitLab Faces API",
    version="2.0.0",
    openapi_version="3.1.0",
    description="Production design contract; service Runtime repositories are not implemented in this scaffold.",
)
app.state.runtime = None
security = HTTPBearer(auto_error=False)
app.router.responses.update(
    {
        code: {"model": SafeError, "description": description}
        for code, description in {
            401: "Authentication required",
            402: "Credits required",
            403: "Permission denied",
            404: "Resource not found",
            409: "Conflict or idempotency mismatch",
            410: "Expired or purged",
            422: "Invalid request",
            429: "Admission limit",
            500: "Internal error",
            503: "Service or filter unavailable",
        }.items()
    }
)


@app.middleware("http")
async def prevent_portrait_caching(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.exception_handler(RequestValidationError)
async def safe_validation_error(request: Request, error: RequestValidationError):
    # Do not echo input values, request bodies or framework error contexts.
    body = SafeError(
        code="VALIDATION_ERROR", message="Request parameters are invalid.", retryable=False, request_id=uuid4()
    )
    return JSONResponse(status_code=422, content=body.model_dump(mode="json"))


@app.exception_handler(ResponseValidationError)
@app.exception_handler(Exception)
async def safe_internal_error(request: Request, error: Exception):
    body = SafeError(
        code="INTERNAL_ERROR", message="Request could not be completed.", retryable=False, request_id=uuid4()
    )
    return JSONResponse(status_code=500, content=body.model_dump(mode="json"), headers={"Cache-Control": "no-store"})


def runtime(request: Request) -> Runtime:
    service = request.app.state.runtime
    if service is None:
        raise HTTPException(status_code=503, detail="SERVICE_NOT_CONFIGURED")
    return service


async def owner(
    request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)]
) -> UUID:
    if credentials is None:
        raise HTTPException(status_code=401, detail="UNAUTHENTICATED")
    return await runtime(request).authenticate(credentials.credentials)


@app.exception_handler(HTTPException)
async def safe_http_error(request: Request, error: HTTPException):
    code = str(error.detail) if isinstance(error.detail, str) else "HTTP_ERROR"
    body = SafeError(
        code=code,
        message="Request could not be completed.",
        retryable=error.status_code in (429, 503, 504),
        request_id=uuid4(),
    )
    return JSONResponse(
        status_code=error.status_code, content=body.model_dump(mode="json"), headers={"Cache-Control": "no-store"}
    )


@app.get("/health", tags=["health"])
async def health():
    return {"status": "alive", "runtime_configured": app.state.runtime is not None}


@app.post("/api/v1/faces/upload-url", response_model=UploadGrant, status_code=201, tags=["faces"])
async def upload_url(body: UploadRequest, request: Request, who: Annotated[UUID, Depends(owner)]):
    return await runtime(request).upload(who, body)


@app.post("/api/v1/faces/uploads/{asset_id}/complete", response_model=AssetReceipt, tags=["faces"])
async def complete_upload(asset_id: UUID, body: UploadComplete, request: Request, who: Annotated[UUID, Depends(owner)]):
    return await runtime(request).complete(who, asset_id, body)


@app.post("/api/v1/faces/transform", response_model=JobPayload, status_code=202, tags=["faces"])
async def transform(
    body: TransformRequest,
    request: Request,
    who: Annotated[UUID, Depends(owner)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=128)],
):
    return await runtime(request).transform(who, body, idempotency_key)


@app.get("/api/v1/faces/jobs/{job_id}", response_model=JobPayload, tags=["faces"])
async def job_status(
    job_id: UUID,
    request: Request,
    who: Annotated[UUID, Depends(owner)],
    wait_seconds: Annotated[int, Query(ge=0, le=25)] = 0,
    after_revision: Annotated[int, Query(ge=0)] = 0,
):
    # Runtime must release DB connection while waiting and return on change/deadline.
    return await runtime(request).status(who, job_id, wait_seconds, after_revision)


@app.post("/api/v1/faces/jobs/{job_id}/cancel", response_model=JobPayload, status_code=202, tags=["faces"])
async def cancel_job(job_id: UUID, request: Request, who: Annotated[UUID, Depends(owner)]):
    return await runtime(request).cancel(who, job_id)


@app.delete("/api/v1/faces/jobs/{job_id}/data", response_model=DeletionReceipt, status_code=202, tags=["faces"])
async def delete_job_data(job_id: UUID, request: Request, who: Annotated[UUID, Depends(owner)]):
    return await runtime(request).delete(who, job_id)
