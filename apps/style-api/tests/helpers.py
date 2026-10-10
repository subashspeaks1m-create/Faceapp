"""Test helpers. FakeProvider is a test double only; the app never selects it at runtime."""

from __future__ import annotations

import io
from dataclasses import dataclass, field

from PIL import Image

from styleapi.config import Settings, load_settings
from styleapi.errors import ApiError
from styleapi.providers import EditRequest, EditResult

ORIGIN = "https://example.github.io"


def make_settings(**overrides: str) -> Settings:
    env = {
        "APP_ENV": "test",
        "ALLOWED_ORIGINS": ORIGIN,
        "OPENAI_API_KEY": "sk-test-not-a-real-key-123456",
        "RATE_LIMIT_BACKEND": "memory",
        "RATE_LIMIT_SALT": "test-salt",
    }
    env.update(overrides)
    return load_settings({k: v for k, v in env.items() if v is not None})


def image_bytes(fmt: str = "JPEG", size: tuple[int, int] = (800, 1000), color: tuple[int, ...] = (180, 120, 90), **save: object) -> bytes:
    mode = "RGBA" if len(color) == 4 else "RGB"
    img = Image.new(mode, size, color)
    out = io.BytesIO()
    img.save(out, format=fmt, **save)
    return out.getvalue()


@dataclass
class FakeProvider:
    """Records calls and returns a solid-colour image of the requested size, clearly not a real edit."""

    name: str = "fake"
    fail_with: ApiError | None = None
    output: bytes | None = None
    calls: list[EditRequest] = field(default_factory=list)

    async def edit(self, request: EditRequest) -> EditResult:
        self.calls.append(request)
        if self.fail_with is not None:
            raise self.fail_with
        if self.output is not None:
            return EditResult(image=self.output, model="fake", input_tokens=None, output_tokens=None)
        w, h = (int(x) for x in request.size.split("x"))
        return EditResult(image=image_bytes("PNG", (w, h), (20, 200, 120)), model="fake", input_tokens=10, output_tokens=20)
