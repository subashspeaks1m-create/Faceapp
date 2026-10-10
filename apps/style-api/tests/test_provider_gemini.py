"""Gemini provider against a mocked transport. No network."""

import asyncio
import base64
import json
import unittest

import httpx

from styleapi.errors import ApiError
from styleapi.providers import EditRequest, GeminiImageEditProvider

from .helpers import image_bytes

KEY = "gemini-test-secret-value-abcdef"
IMG = image_bytes("PNG", (832, 1248))


def _provider(handler) -> GeminiImageEditProvider:  # type: ignore[no-untyped-def]
    return GeminiImageEditProvider(
        KEY, model="gemini-3.1-flash-image", base_url="https://gemini.test/v1beta", timeout_seconds=30, transport=httpx.MockTransport(handler)
    )


def _request(size: str = "1024x1536") -> EditRequest:
    return EditRequest(image_png=image_bytes("PNG", (512, 768)), prompt="Style: test", size=size)  # type: ignore[arg-type]


def _ok(parts: list[dict], **extra: object) -> httpx.Response:
    return httpx.Response(200, json={"candidates": [{"content": {"role": "model", "parts": parts}, "finishReason": "STOP"}], **extra})


def _image_part(data: bytes = IMG) -> dict:
    return {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(data).decode()}}


class GeminiProviderTest(unittest.TestCase):
    def run_edit(self, handler, size: str = "1024x1536"):  # type: ignore[no-untyped-def]
        return asyncio.run(_provider(handler).edit(_request(size)))

    def test_request_shape(self) -> None:
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["key"] = request.headers.get("x-goog-api-key")
            seen["auth"] = request.headers.get("authorization")
            seen["body"] = json.loads(request.content)
            return _ok([{"text": "Here you go"}, _image_part()], usageMetadata={"promptTokenCount": 11, "candidatesTokenCount": 22})

        result = self.run_edit(handler)
        self.assertEqual(seen["url"], "https://gemini.test/v1beta/models/gemini-3.1-flash-image:generateContent")
        self.assertEqual(seen["key"], KEY)
        self.assertIsNone(seen["auth"])
        body = seen["body"]
        assert isinstance(body, dict)
        parts = body["contents"][0]["parts"]
        self.assertEqual(parts[0], {"text": "Style: test"})
        self.assertEqual(parts[1]["inlineData"]["mimeType"], "image/png")
        self.assertTrue(base64.b64decode(parts[1]["inlineData"]["data"]).startswith(b"\x89PNG"))
        self.assertEqual(body["generationConfig"]["responseModalities"], ["IMAGE"])
        self.assertEqual(body["generationConfig"]["imageConfig"], {"aspectRatio": "2:3"})
        self.assertEqual(result.image, IMG)
        self.assertEqual((result.input_tokens, result.output_tokens), (11, 22))
        self.assertNotIn(KEY, str(seen["url"]))

    def test_aspect_ratios(self) -> None:
        for size, aspect in (("1024x1024", "1:1"), ("1536x1024", "3:2")):
            seen: dict[str, str] = {}

            def handler(request: httpx.Request, seen: dict[str, str] = seen) -> httpx.Response:
                seen["aspect"] = json.loads(request.content)["generationConfig"]["imageConfig"]["aspectRatio"]
                return _ok([_image_part()])

            self.run_edit(handler, size)
            self.assertEqual(seen["aspect"], aspect)

    def test_snake_case_response_accepted(self) -> None:
        r = self.run_edit(lambda _r: _ok([{"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(IMG).decode()}}]))
        self.assertEqual(r.image, IMG)

    def assertMaps(self, response: httpx.Response, code: str) -> None:
        with self.assertRaises(ApiError) as ctx:
            self.run_edit(lambda _r: response)
        self.assertEqual(ctx.exception.code, code)
        self.assertNotIn(KEY, json.dumps(ctx.exception.body("r")))

    def test_error_mapping(self) -> None:
        bad_key = {"error": {"code": 400, "message": f"API key not valid {KEY}", "status": "INVALID_ARGUMENT", "details": [{"reason": "API_KEY_INVALID"}]}}
        self.assertMaps(httpx.Response(400, json=bad_key), "PROVIDER_NOT_CONFIGURED")
        self.assertMaps(httpx.Response(403, json={"error": {"status": "PERMISSION_DENIED"}}), "PROVIDER_NOT_CONFIGURED")
        self.assertMaps(httpx.Response(429, json={"error": {"status": "RESOURCE_EXHAUSTED"}}), "GENERATION_UNAVAILABLE")
        self.assertMaps(httpx.Response(404, json={"error": {"status": "NOT_FOUND"}}), "PROVIDER_ERROR")
        self.assertMaps(httpx.Response(400, json={"error": {"status": "INVALID_ARGUMENT"}}), "PROVIDER_ERROR")
        self.assertMaps(httpx.Response(500, text="oops"), "PROVIDER_ERROR")
        self.assertMaps(httpx.Response(504, json={"error": {"status": "DEADLINE_EXCEEDED"}}), "PROVIDER_TIMEOUT")

    def test_refusals_and_bad_payloads(self) -> None:
        self.assertMaps(httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}}), "PROVIDER_REJECTED")
        self.assertMaps(httpx.Response(200, json={"candidates": [{"finishReason": "IMAGE_SAFETY"}]}), "PROVIDER_REJECTED")
        self.assertMaps(httpx.Response(200, json={"candidates": [{"finishReason": "NO_IMAGE", "content": {"parts": []}}]}), "PROVIDER_REJECTED")
        self.assertMaps(_ok([{"text": "I can't edit photos of this kind."}]), "PROVIDER_REJECTED")
        self.assertMaps(httpx.Response(200, json={"candidates": []}), "INVALID_PROVIDER_RESPONSE")
        self.assertMaps(httpx.Response(200, text="not json"), "INVALID_PROVIDER_RESPONSE")
        self.assertMaps(_ok([{"inlineData": {"mimeType": "image/png", "data": "!!!"}}]), "INVALID_PROVIDER_RESPONSE")

    def test_timeout_and_network(self) -> None:
        def timeout(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("slow", request=request)

        def broken(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("down", request=request)

        for handler, code in ((timeout, "PROVIDER_TIMEOUT"), (broken, "PROVIDER_ERROR")):
            with self.assertRaises(ApiError) as ctx:
                self.run_edit(handler)
            self.assertEqual(ctx.exception.code, code)

    def test_repr_hides_key(self) -> None:
        self.assertNotIn(KEY, repr(_provider(lambda r: httpx.Response(200))))


if __name__ == "__main__":
    unittest.main()
