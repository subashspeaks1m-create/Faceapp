import io
import unittest

from PIL import Image

from styleapi.errors import ApiError
from styleapi.images import choose_size, finalize_output, prepare_upload, sniff_format

from .helpers import image_bytes

LIMITS = {"max_bytes": 4_000_000, "max_pixels": 16_000_000, "min_side": 256}


class ImagesTest(unittest.TestCase):
    def assertCode(self, code: str, fn, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        with self.assertRaises(ApiError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_sniff(self) -> None:
        self.assertEqual(sniff_format(image_bytes("JPEG")), "jpeg")
        self.assertEqual(sniff_format(image_bytes("PNG")), "png")
        self.assertEqual(sniff_format(image_bytes("WEBP")), "webp")
        self.assertIsNone(sniff_format(image_bytes("GIF")))
        self.assertIsNone(sniff_format(b"<svg></svg>"))

    def test_accepts_supported_formats(self) -> None:
        for fmt, mime in (("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")):
            p = prepare_upload(image_bytes(fmt), mime, **LIMITS)
            self.assertEqual((p.width, p.height), (800, 1000))
            self.assertTrue(p.png.startswith(b"\x89PNG"))

    def test_rejections(self) -> None:
        self.assertCode("INVALID_IMAGE", prepare_upload, b"", "image/jpeg", **LIMITS)
        self.assertCode("UNSUPPORTED_IMAGE_FORMAT", prepare_upload, image_bytes("GIF"), "image/gif", **LIMITS)
        self.assertCode("UNSUPPORTED_IMAGE_FORMAT", prepare_upload, b"%PDF-1.7 ....", None, **LIMITS)
        self.assertCode("UNSUPPORTED_IMAGE_FORMAT", prepare_upload, image_bytes("PNG"), "image/heic", **LIMITS)
        self.assertCode("INVALID_IMAGE", prepare_upload, image_bytes("PNG"), "image/jpeg", **LIMITS)
        self.assertCode("INVALID_IMAGE", prepare_upload, b"\xff\xd8\xff" + b"\x00" * 500, "image/jpeg", **LIMITS)
        self.assertCode("INVALID_IMAGE", prepare_upload, image_bytes("JPEG")[:400], "image/jpeg", **LIMITS)
        self.assertCode("INVALID_IMAGE", prepare_upload, image_bytes("JPEG", (200, 600)), "image/jpeg", **LIMITS)
        self.assertCode("IMAGE_TOO_LARGE", prepare_upload, image_bytes("JPEG"), "image/jpeg", max_bytes=1000, max_pixels=16_000_000, min_side=256)
        self.assertCode("IMAGE_TOO_LARGE", prepare_upload, image_bytes("PNG", (3000, 3000)), "image/png", max_bytes=4_000_000, max_pixels=4_000_000, min_side=256)

    def test_exif_orientation_applied_and_metadata_dropped(self) -> None:
        img = Image.new("RGB", (1000, 600), (10, 20, 30))
        exif = Image.Exif()
        exif[0x0112] = 6  # rotate 90 CW on display
        exif[0x010F] = "SecretCam"
        out = io.BytesIO()
        img.save(out, format="JPEG", exif=exif.tobytes())
        p = prepare_upload(out.getvalue(), "image/jpeg", **LIMITS)
        self.assertEqual((p.width, p.height), (600, 1000))
        self.assertNotIn(b"SecretCam", p.png)
        with Image.open(io.BytesIO(p.png)) as again:
            self.assertEqual(len(again.getexif()), 0)

    def test_transparency_flattened_and_large_resized(self) -> None:
        p = prepare_upload(image_bytes("PNG", (3000, 2000), (0, 0, 0, 0)), "image/png", **LIMITS)
        self.assertEqual((p.width, p.height), (1536, 1024))
        self.assertEqual(p.size, "1536x1024")
        with Image.open(io.BytesIO(p.png)) as again:
            self.assertEqual(again.mode, "RGB")
            self.assertEqual(again.getpixel((5, 5)), (255, 255, 255))

    def test_choose_size(self) -> None:
        self.assertEqual(choose_size(1000, 1000), "1024x1024")
        self.assertEqual(choose_size(1100, 1000), "1024x1024")
        self.assertEqual(choose_size(1200, 1000), "1536x1024")
        self.assertEqual(choose_size(800, 1000), "1024x1536")
        self.assertEqual(choose_size(900, 1000), "1024x1024")

    def test_finalize_output(self) -> None:
        jpeg, w, h = finalize_output(image_bytes("PNG", (1024, 1536)))
        self.assertTrue(jpeg.startswith(b"\xff\xd8\xff"))
        self.assertEqual((w, h), (1024, 1536))
        self.assertCode("INVALID_PROVIDER_RESPONSE", finalize_output, b"not an image")
        self.assertCode("INVALID_PROVIDER_RESPONSE", finalize_output, image_bytes("PNG", (32, 32)))
        self.assertCode("INVALID_PROVIDER_RESPONSE", finalize_output, image_bytes("PNG")[:200])


if __name__ == "__main__":
    unittest.main()
