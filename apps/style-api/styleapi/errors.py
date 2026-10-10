"""Stable error codes. Messages are written for end users and never include provider text or config."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ErrorCode = Literal[
    "INVALID_IMAGE",
    "UNSUPPORTED_IMAGE_FORMAT",
    "IMAGE_TOO_LARGE",
    "INVALID_STYLE",
    "INVALID_REQUEST",
    "CONSENT_REQUIRED",
    "ORIGIN_NOT_ALLOWED",
    "PROVIDER_NOT_CONFIGURED",
    "RATE_LIMITED",
    "PROVIDER_TIMEOUT",
    "PROVIDER_REJECTED",
    "PROVIDER_ERROR",
    "INVALID_PROVIDER_RESPONSE",
    "GENERATION_UNAVAILABLE",
    "INTERNAL_ERROR",
]

_DEFAULTS: dict[ErrorCode, tuple[int, bool, str]] = {
    "INVALID_IMAGE": (400, False, "This file could not be read as a photo. Try a different JPEG, PNG or WebP image."),
    "UNSUPPORTED_IMAGE_FORMAT": (415, False, "Only JPEG, PNG and WebP photos are supported."),
    "IMAGE_TOO_LARGE": (413, False, "This photo is too large. Use a photo under 4 MB."),
    "INVALID_STYLE": (400, False, "That style is not available."),
    "INVALID_REQUEST": (400, False, "The request was incomplete or malformed."),
    "CONSENT_REQUIRED": (400, False, "Please agree to send your photo for processing first."),
    "ORIGIN_NOT_ALLOWED": (403, False, "This site is not allowed to use the style service."),
    "PROVIDER_NOT_CONFIGURED": (503, False, "AI styles are not set up on this server yet."),
    "RATE_LIMITED": (429, True, "You have reached the generation limit for now. Try again later."),
    "PROVIDER_TIMEOUT": (504, True, "The AI service took too long to respond. Try again."),
    "PROVIDER_REJECTED": (422, False, "The AI service declined this photo or style. Try a different photo."),
    "PROVIDER_ERROR": (502, True, "The AI service had a problem. Try again in a moment."),
    "INVALID_PROVIDER_RESPONSE": (502, True, "The AI service returned an unusable image. Try again."),
    "GENERATION_UNAVAILABLE": (503, True, "Generation is temporarily unavailable. Try again later."),
    "INTERNAL_ERROR": (500, True, "Something went wrong on our side. Try again."),
}


@dataclass(frozen=True)
class ApiError(Exception):
    code: ErrorCode
    message: str | None = None
    retry_after_seconds: int | None = None

    @property
    def status(self) -> int:
        return _DEFAULTS[self.code][0]

    @property
    def retryable(self) -> bool:
        return _DEFAULTS[self.code][1]

    @property
    def user_message(self) -> str:
        return self.message or _DEFAULTS[self.code][2]

    def body(self, request_id: str) -> dict[str, object]:
        err: dict[str, object] = {
            "code": self.code,
            "message": self.user_message,
            "retryable": self.retryable,
            "request_id": request_id,
        }
        if self.retry_after_seconds is not None:
            err["retry_after_seconds"] = self.retry_after_seconds
        return {"error": err}


ALL_CODES: tuple[ErrorCode, ...] = tuple(_DEFAULTS)
