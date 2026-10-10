"""Hardened upload normalization: sniff, bound pixels, apply EXIF orientation, convert to sRGB, strip metadata."""

from __future__ import annotations
from dataclasses import dataclass
import io
import warnings
from PIL import Image, ImageCms, ImageOps

# Formats this build can decode. HEIC is accepted by the wire contract but needs an
# approved decoder (libheif licensing review) before it can be finalized.
DECODERS = {"image/jpeg": "JPEG", "image/png": "PNG"}
MAGIC = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/heic": (b"ftypheic", b"ftypheix", b"ftypmif1", b"ftyphevc"),
}


class ImageRejected(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class NormalizedImage:
    png: bytes
    rgb: Image.Image
    width: int
    height: int


def sniff_matches(mime: str, data: bytes) -> bool:
    if mime == "image/heic":
        return data[4:12] in MAGIC[mime]
    return any(data.startswith(m) for m in MAGIC.get(mime, ()))


def normalize(data: bytes, mime: str, max_pixels: int) -> NormalizedImage:
    if not sniff_matches(mime, data):
        raise ImageRejected("UPLOAD_TYPE_MISMATCH")
    if mime not in DECODERS:
        raise ImageRejected("UNSUPPORTED_IMAGE_FORMAT")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            img = Image.open(io.BytesIO(data), formats=[DECODERS[mime]])
            # Header-only size check before any pixel decode.
            if img.width * img.height > max_pixels or img.width < 1 or img.height < 1:
                raise ImageRejected("IMAGE_TOO_LARGE")
            if getattr(img, "n_frames", 1) != 1:
                raise ImageRejected("UNSUPPORTED_IMAGE_FORMAT")
            img.load()
    except ImageRejected:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ImageRejected("IMAGE_TOO_LARGE") from None
    except Exception:
        raise ImageRejected("IMAGE_DECODE_FAILED") from None

    icc = img.info.get("icc_profile")
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "RGBA", "L", "LA", "P", "CMYK", "I;16"):
        raise ImageRejected("UNSUPPORTED_IMAGE_FORMAT")
    if icc:
        try:
            source = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            img = ImageCms.profileToProfile(
                img.convert("RGB") if img.mode not in ("RGB", "CMYK") else img,
                source,
                ImageCms.createProfile("sRGB"),
                outputMode="RGB",
            )
        except (ImageCms.PyCMSError, OSError):
            raise ImageRejected("IMAGE_COLOR_PROFILE_INVALID") from None
    if img.mode in ("RGBA", "LA", "P"):
        # Composite transparency over white rather than exposing undefined colour under alpha.
        rgba = img.convert("RGBA")
        base = Image.new("RGB", rgba.size, (255, 255, 255))
        base.paste(rgba, mask=rgba.split()[3])
        img = base
    rgb = img.convert("RGB")
    # Re-encode from pixels only: EXIF/GPS/XMP/ICC/text chunks are not carried over.
    clean = Image.new("RGB", rgb.size)
    clean.paste(rgb)
    out = io.BytesIO()
    clean.save(out, format="PNG", optimize=False)
    return NormalizedImage(out.getvalue(), clean, clean.width, clean.height)
