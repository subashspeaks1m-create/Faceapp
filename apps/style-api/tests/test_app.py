"""HTTP-level tests with a fake provider (test double) and in-memory limiter. No network."""

import io
import json
import unittest

from fastapi.testclient import TestClient
from PIL import Image

from styleapi.app import create_app
from styleapi.errors import ALL_CODES, ApiError

from .helpers import ORIGIN, FakeProvider, image_bytes, make_settings

SECRET = "sk-test-not-a-real-key-123456"


def _form(style: str = "seventies-film", intensity: str = "60", consent: str = "true") -> dict[str, str]:
    return {"style_id": style, "intensity": intensity, "consent": consent}


class AppTest(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = FakeProvider()
        self.app = create_app(make_settings(LIMIT_PER_IP_HOUR="3"), provider=self.provider)
        self.client = TestClient(self.app)

    def post(self, data: dict[str, str] | None = None, image: bytes | None = None, mime: str = "image/jpeg", origin: str | None = ORIGIN, ip: str = "198.51.100.7"):  # type: ignore[no-untyped-def]
        headers = {"x-forwarded-for": ip}
        if origin is not None:
            headers["origin"] = origin
        files = {"image": ("p.jpg", image if image is not None else image_bytes("JPEG"), mime)}
        return self.client.post("/api/generate", data=data or _form(), files=files, headers=headers)

    def assertError(self, resp, code: str, status: int) -> dict:  # type: ignore[no-untyped-def]
        self.assertEqual(resp.status_code, status, resp.text)
        body = resp.json()["error"]
        self.assertEqual(body["code"], code)
        self.assertEqual(set(body) - {"retry_after_seconds"}, {"code", "message", "retryable", "request_id"})
        self.assertEqual(body["request_id"], resp.headers["x-request-id"])
        self.assertNotIn(SECRET, resp.text)
        return body

    def test_health_and_styles(self) -> None:
        h = self.client.get("/api/health").json()
        self.assertEqual(h["status"], "ok")
        self.assertTrue(h["provider_configured"])
        self.assertEqual(h["style_count"], 25)
        styles = self.client.get("/api/styles")
        self.assertEqual(len(styles.json()["styles"]), 25)
        self.assertNotIn("prompt", styles.text)
        self.assertNotIn(SECRET, json.dumps(h) + styles.text)

    def test_generate_success(self) -> None:
        resp = self.post(_form("storybook-anime", "80"), image=image_bytes("JPEG", (800, 1200)))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.headers["content-type"], "image/jpeg")
        self.assertEqual(resp.headers["cache-control"], "no-store")
        self.assertEqual(resp.headers["x-style-id"], "storybook-anime")
        self.assertEqual(resp.headers["x-quota-remaining"], "2")
        self.assertEqual(resp.headers["access-control-allow-origin"], ORIGIN)
        self.assertIn("X-Quota-Remaining", resp.headers["access-control-expose-headers"])
        with Image.open(io.BytesIO(resp.content)) as out:
            self.assertEqual(out.format, "JPEG")
            self.assertEqual(out.size, (1024, 1536))
        call = self.provider.calls[0]
        self.assertEqual(call.size, "1024x1536")
        self.assertIn("Strength 80/100 (Full)", call.prompt)
        self.assertIn("storybook anime", call.prompt)

    def test_validation_errors(self) -> None:
        self.assertError(self.post(_form(style="nope")), "INVALID_STYLE", 400)
        self.assertError(self.post(_form(intensity="101")), "INVALID_REQUEST", 400)
        self.assertError(self.post(_form(intensity="5.5")), "INVALID_REQUEST", 400)
        self.assertError(self.post(_form(intensity="-1")), "INVALID_REQUEST", 400)
        self.assertError(self.post(_form(consent="false")), "CONSENT_REQUIRED", 400)
        self.assertError(self.post(image=b"GIF89a....", mime="image/gif"), "UNSUPPORTED_IMAGE_FORMAT", 415)
        self.assertError(self.post(image=b"\xff\xd8\xff garbage"), "INVALID_IMAGE", 400)
        big = b"\xff\xd8\xff" + b"0" * 4_100_000
        self.assertError(self.post(image=big), "IMAGE_TOO_LARGE", 413)
        self.assertEqual(self.provider.calls, [])
        # Validation failures do not use quota.
        self.assertEqual(self.client.get("/api/quota", headers={"x-forwarded-for": "198.51.100.7"}).json()["remaining"], 3)

    def test_missing_image_and_non_multipart(self) -> None:
        r = self.client.post("/api/generate", data=_form(), files={"other": ("p.jpg", image_bytes("JPEG"), "image/jpeg")}, headers={"origin": ORIGIN})
        self.assertError(r, "INVALID_IMAGE", 400)
        r = self.client.post("/api/generate", data=_form(), headers={"origin": ORIGIN})
        self.assertError(r, "INVALID_REQUEST", 400)
        r = self.client.post("/api/generate", json={"style_id": "x"}, headers={"origin": ORIGIN})
        self.assertError(r, "INVALID_REQUEST", 400)

    def test_origin_enforced(self) -> None:
        self.assertError(self.post(origin="https://evil.example"), "ORIGIN_NOT_ALLOWED", 403)
        pre = self.client.options("/api/generate", headers={"origin": "https://evil.example", "access-control-request-method": "POST"})
        self.assertNotIn("access-control-allow-origin", pre.headers)
        pre = self.client.options("/api/generate", headers={"origin": ORIGIN, "access-control-request-method": "POST"})
        self.assertEqual(pre.headers["access-control-allow-origin"], ORIGIN)
        # Native apps send no Origin header.
        self.assertEqual(self.post(origin=None).status_code, 200)

    def test_rate_limit(self) -> None:
        for _ in range(3):
            self.assertEqual(self.post().status_code, 200)
        body = self.assertError(self.post(), "RATE_LIMITED", 429)
        self.assertTrue(body["retryable"])
        self.assertEqual(len(self.provider.calls), 3)
        self.assertEqual(self.post(ip="198.51.100.8").status_code, 200)

    def test_provider_errors_are_passed_through_as_codes(self) -> None:
        for code in ("PROVIDER_TIMEOUT", "PROVIDER_ERROR", "PROVIDER_REJECTED", "INVALID_PROVIDER_RESPONSE", "GENERATION_UNAVAILABLE"):
            self.provider.fail_with = ApiError(code)  # type: ignore[arg-type]
            app = create_app(make_settings(), provider=self.provider)
            resp = TestClient(app).post("/api/generate", data=_form(), files={"image": ("p.jpg", image_bytes("JPEG"), "image/jpeg")}, headers={"origin": ORIGIN})
            self.assertError(resp, code, ApiError(code).status)  # type: ignore[arg-type]
            self.assertEqual(resp.headers["access-control-allow-origin"], ORIGIN)

    def test_garbage_provider_output_rejected(self) -> None:
        app = create_app(make_settings(), provider=FakeProvider(output=b"definitely not an image"))
        resp = TestClient(app).post("/api/generate", data=_form(), files={"image": ("p.jpg", image_bytes("JPEG"), "image/jpeg")})
        self.assertError(resp, "INVALID_PROVIDER_RESPONSE", 502)

    def test_unexpected_exception_becomes_internal_error(self) -> None:
        class Boom:
            name = "boom"

            async def edit(self, request):  # type: ignore[no-untyped-def]
                raise RuntimeError(f"leak {SECRET}")

        app = create_app(make_settings(), provider=Boom())
        resp = TestClient(app, raise_server_exceptions=False).post(
            "/api/generate", data=_form(), files={"image": ("p.jpg", image_bytes("JPEG"), "image/jpeg")}, headers={"origin": ORIGIN}
        )
        self.assertError(resp, "INTERNAL_ERROR", 500)
        self.assertEqual(resp.headers["access-control-allow-origin"], ORIGIN)

    def test_provider_not_configured(self) -> None:
        app = create_app(make_settings(OPENAI_API_KEY=""))
        client = TestClient(app)
        self.assertEqual(client.get("/api/health").json()["status"], "provider_not_configured")
        resp = client.post("/api/generate", data=_form(), files={"image": ("p.jpg", image_bytes("JPEG"), "image/jpeg")}, headers={"origin": ORIGIN})
        self.assertError(resp, "PROVIDER_NOT_CONFIGURED", 503)

    def test_production_fails_closed_without_limiter_backend(self) -> None:
        # Production with Upstash selected but not reachable/configured: no provider call happens.
        s = make_settings(RATE_LIMIT_BACKEND="upstash")
        object.__setattr__(s, "environment", "production")
        provider = FakeProvider()
        resp = TestClient(create_app(s, provider=provider)).post(
            "/api/generate", data=_form(), files={"image": ("p.jpg", image_bytes("JPEG"), "image/jpeg")}, headers={"origin": ORIGIN}
        )
        self.assertError(resp, "GENERATION_UNAVAILABLE", 503)
        self.assertEqual(provider.calls, [])

    def test_misconfigured_environment_reports_without_leaking(self) -> None:
        import os
        from unittest import mock

        with mock.patch.dict(os.environ, {"APP_ENV": "production", "ALLOWED_ORIGINS": "*", "OPENAI_API_KEY": SECRET}, clear=True):
            app = create_app()
        client = TestClient(app)
        self.assertEqual(client.get("/api/health").json()["status"], "misconfigured")
        resp = client.post("/api/generate", data=_form(), files={"image": ("p.jpg", image_bytes("JPEG"), "image/jpeg")})
        self.assertError(resp, "GENERATION_UNAVAILABLE", 503)

    def test_refused_settings_still_answer_the_browser_with_cors(self) -> None:
        import os
        from unittest import mock

        env = {"APP_ENV": "production", "ALLOWED_ORIGINS": f"{ORIGIN}/Faceapp", "IMAGE_PROVIDER": "gemini", "GEMINI_API_KEY": SECRET}
        with mock.patch.dict(os.environ, env, clear=True):
            app = create_app()
        client = TestClient(app)
        health = client.get("/api/health", headers={"origin": ORIGIN})
        self.assertEqual(health.headers["access-control-allow-origin"], ORIGIN)
        body = health.json()
        self.assertEqual(body["status"], "misconfigured")
        self.assertIn("GEMINI_PAID_TIER", body["problem"])
        self.assertNotIn(SECRET, json.dumps(body))
        resp = client.post("/api/generate", data=_form(), files={"image": ("p.jpg", image_bytes("JPEG"), "image/jpeg")}, headers={"origin": ORIGIN})
        self.assertError(resp, "GENERATION_UNAVAILABLE", 503)
        self.assertEqual(resp.headers["access-control-allow-origin"], ORIGIN)

    def test_health_names_missing_pieces(self) -> None:
        health = TestClient(create_app(make_settings())).get("/api/health").json()
        self.assertEqual((health["problem"], health["rate_limit_ready"], health["allowed_origins"]), (None, True, [ORIGIN]))
        prod = make_settings(APP_ENV="production", RATE_LIMIT_BACKEND="upstash", ALLOWED_ORIGINS="")
        health = TestClient(create_app(prod)).get("/api/health").json()
        self.assertFalse(health["rate_limit_ready"])
        self.assertIn("Upstash", health["problem"])

    def test_gemini_selected_from_settings(self) -> None:
        app = create_app(make_settings(OPENAI_API_KEY="", GEMINI_API_KEY="gem-test-key"))
        health = TestClient(app).get("/api/health").json()
        self.assertEqual((health["status"], health["provider"], health["model"]), ("ok", "gemini", "gemini-3.1-flash-image"))
        self.assertNotIn("gem-test-key", json.dumps(health))

    def test_all_error_codes_have_messages(self) -> None:
        for code in ALL_CODES:
            body = ApiError(code).body("rid")["error"]
            assert isinstance(body, dict)
            self.assertTrue(body["message"])


if __name__ == "__main__":
    unittest.main()
