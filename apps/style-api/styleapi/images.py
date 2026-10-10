"""Upload validation and output checks.

Input: sniff magic bytes, decode fully with Pillow under a pixel cap, apply EXIF orientation,
then re-encode a metadata-free PNG for the provider (drops EXIF, GPS and ICC text).
Output: decode the provider's bytes, check dimensions, re-encode a metadata-free JPEG.
"""

from __future__ import annotations

import io
import warnings
from dataclasses import dataclass
from typing import Literal

from PIL import Image, ImageOps, UnidentifiedImageError

from .errors import ApiError

InputFormat = Literal["jpeg", "png", "webp"]
ProviderSize = Literal["1024x1024", "1024x1536", "1536x1024"]

# Longest edge sent to the provider. Larger inputs only add input-token cost.
PROVIDER_MAX_EDGE = 1536


def sniff_format(data: bytes) -> InputFormat | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(data) >= 12 and data[0:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


_PIL_FORMATS: dict[InputFormat, str] = {"jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}
_DECLARED_MIME: dict[str, InputFormat] = {"image/jpeg": "jpeg", "image/jpg": "jpeg", "image/png": "png", "image/webp": "webp"}


@dataclass(frozen=True)
class PreparedImage:
    png: bytes
    width: int
    height: int
    size: ProviderSize


def choose_size(width: int, height: int) -> ProviderSize:
    ratio = width / height
    if ratio >= 1.2:
        return "1536x1024"
    if ratio <= 1 / 1.2:
        return "1024x1536"
    return "1024x1024"


def prepare_upload(data: bytes, declared_mime: str | None, *, max_bytes: int, max_pixels: int, min_side: int) -> PreparedImage:
    if len(data) == 0:
        raise ApiError("INVALID_IMAGE", "No photo was received.")
    if len(data) > max_bytes:
        raise ApiError("IMAGE_TOO_LARGE")
    fmt = sniff_format(data)
    if fmt is None:
        raise ApiError("UNSUPPORTED_IMAGE_FORMAT")
    if declared_mime is not None:
        declared = _DECLARED_MIME.get(declared_mime.split(";")[0].strip().lower())
        if declared is None:
            raise ApiError("UNSUPPORTED_IMAGE_FORMAT")
        if declared != fmt:
            raise ApiError("INVALID_IMAGE", "The file type does not match its contents.")

    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            with Image.open(io.BytesIO(data), formats=[_PIL_FORMATS[fmt]]) as probe:
                w, h = probe.size
                if w * h > max_pixels:
                    raise ApiError("IMAGE_TOO_LARGE", "This photo has too many pixels. Use a photo under 16 megapixels.")
                if getattr(probe, "n_frames", 1) > 1:
                    raise ApiError("UNSUPPORTED_IMAGE_FORMAT", "Animated images are not supported.")
                probe.load()
                img = ImageOps.exif_transpose(probe)
        except ApiError:
            raise
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as e:
            raise ApiError("INVALID_IMAGE") from e

    if min(img.size) < min_side:
        raise ApiError("INVALID_IMAGE", f"This photo is too small. Use one at least {min_side} pixels on each side.")

    img = img.convert("RGBA" if img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info else "RGB")
    if img.mode == "RGBA":
        # Providers handle transparency inconsistently; flatten onto white.
        flat = Image.new("RGB", img.size, (255, 255, 255))
        flat.paste(img, mask=img.getchannel("A"))
        img = flat
    if max(img.size) > PROVIDER_MAX_EDGE:
        img.thumbnail((PROVIDER_MAX_EDGE, PROVIDER_MAX_EDGE), Image.Resampling.LANCZOS)

    out = io.BytesIO()
    img.save(out, format="PNG", optimize=False)
    return PreparedImage(png=out.getvalue(), width=img.width, height=img.height, size=choose_size(img.width, img.height))


def finalize_output(data: bytes, *, max_side: int = 4096) -> tuple[bytes, int, int]:
    """Validate provider bytes and return a clean JPEG. Raises INVALID_PROVIDER_RESPONSE."""
    fmt = sniff_format(data)
    if fmt is None:
        raise ApiError("INVALID_PROVIDER_RESPONSE")
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            with Image.open(io.BytesIO(data), formats=[_PIL_FORMATS[fmt]]) as img:
                w, h = img.size
                if not (64 <= w <= max_side and 64 <= h <= max_side):
                    raise ApiError("INVALID_PROVIDER_RESPONSE")
                img.load()
                rgb = img.convert("RGB")
        except ApiError:
            raise
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as e:
            raise ApiError("INVALID_PROVIDER_RESPONSE") from e
    out = io.BytesIO()
    rgb.save(out, format="JPEG", quality=92, optimize=True)
    return out.getvalue(), rgb.width, rgb.height
