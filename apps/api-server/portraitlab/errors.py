"""Typed API failures. The detail is a stable safe code; messages never carry input data."""

from fastapi import HTTPException


class ApiError(HTTPException):
    def __init__(self, status_code: int, code: str):
        super().__init__(status_code=status_code, detail=code)
        self.code = code


def unauthenticated() -> ApiError:
    return ApiError(401, "UNAUTHENTICATED")


def not_found(code: str = "NOT_FOUND") -> ApiError:
    # Owner-mismatched identifiers deliberately look identical to missing ones.
    return ApiError(404, code)
