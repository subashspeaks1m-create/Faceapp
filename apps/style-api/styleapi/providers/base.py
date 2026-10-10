"""Provider interface. Implementations raise ApiError with a stable code; they never return placeholders."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..images import ProviderSize


@dataclass(frozen=True)
class EditRequest:
    image_png: bytes
    prompt: str
    size: ProviderSize


@dataclass(frozen=True)
class EditResult:
    image: bytes
    model: str
    # Token usage as reported by the provider, for cost tracking. None when not reported.
    input_tokens: int | None
    output_tokens: int | None


class ImageEditProvider(Protocol):
    name: str

    async def edit(self, request: EditRequest) -> EditResult: ...
