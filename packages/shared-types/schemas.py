"""Authoritative wire schemas; runtime ownership/billing checks remain mandatory."""

from __future__ import annotations
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, AwareDatetime, model_validator

FilterId = Literal[
    "age_young",
    "age_teen",
    "age_50s",
    "age_70s",
    "smile_subtle",
    "smile_tooth",
    "laugh",
    "gender_feminine",
    "gender_masculine",
    "hair_color",
    "beard_density",
    "beauty_retouch",
]
JobState = Literal["queued", "running", "succeeded", "failed", "cancel_requested", "canceled", "expired", "purged"]


class WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Options(WireModel):
    color_hex: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    skin_smoothing: StrictFloat | None = Field(default=None, ge=0, le=1)
    makeup: StrictFloat | None = Field(default=None, ge=0, le=1)


class UploadRequest(WireModel):
    mime_type: Literal["image/jpeg", "image/png", "image/heic"]
    byte_length: StrictInt = Field(ge=1, le=10_485_760)
    checksum_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    consent_receipt_id: UUID


class UploadGrant(WireModel):
    asset_id: UUID
    upload_url: str
    method: Literal["PUT"] = "PUT"
    required_headers: dict[str, str]
    expires_at: AwareDatetime
    absolute_purge_at: AwareDatetime


class UploadComplete(WireModel):
    checksum_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AssetReceipt(WireModel):
    asset_id: UUID
    normalized_width: StrictInt = Field(ge=1, le=24000)
    normalized_height: StrictInt = Field(ge=1, le=24000)
    faces: list[UUID] = Field(max_length=8)
    expires_at: AwareDatetime


class TransformRequest(WireModel):
    asset_id: UUID
    face_id: UUID
    filter_type: FilterId
    intensity: StrictFloat = Field(ge=0, le=1)
    preserve_background: StrictBool = True
    source_revision: StrictInt = Field(ge=0)
    candidate_revision: StrictInt = Field(ge=0)
    options: Options = Field(default_factory=Options)

    @model_validator(mode="after")
    def check_options(self):
        if self.options.color_hex is not None and self.filter_type != "hair_color":
            raise ValueError("color_hex only applies to hair_color")
        if (
            self.options.makeup is not None or self.options.skin_smoothing is not None
        ) and self.filter_type != "beauty_retouch":
            raise ValueError("beauty parameters only apply to beauty_retouch")
        return self


class SafeError(WireModel):
    code: str
    message: str
    retryable: StrictBool
    request_id: UUID


class JobPayload(WireModel):
    job_id: UUID
    asset_id: UUID
    face_id: UUID
    source_revision: StrictInt = Field(ge=0)
    candidate_revision: StrictInt = Field(ge=0)
    status: JobState
    stage: Literal[
        "queued", "decode", "detect", "align", "parse", "transform", "restore", "blend", "encode", "deliver", "done"
    ]
    event_revision: StrictInt = Field(ge=0)
    progress_percent: StrictFloat | None = Field(default=None, ge=0, le=100)
    progress_source: Literal["indeterminate", "measured_steps", "complete"] = "indeterminate"
    result_cdn_url: str | None = None
    result_expires_at: AwareDatetime | None = None
    error: SafeError | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @model_validator(mode="after")
    def check_result_and_progress(self):
        if self.result_cdn_url is not None and self.status != "succeeded":
            raise ValueError("Only succeeded jobs may have a result grant")
        if (self.result_cdn_url is None) != (self.result_expires_at is None):
            raise ValueError("Result URL and expiration must occur together")
        if self.progress_source == "indeterminate" and self.progress_percent is not None:
            raise ValueError("Unknown progress must be null")
        if self.progress_source == "complete" and self.progress_percent != 100.0:
            raise ValueError("Complete progress must be 100")
        return self


class DeletionReceipt(WireModel):
    job_id: UUID
    status: Literal["requested", "deleting", "complete", "partial_failure"]
    requested_at: AwareDatetime
