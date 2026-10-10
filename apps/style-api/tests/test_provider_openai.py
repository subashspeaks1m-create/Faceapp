"""OpenAI provider against a mocked transport. No network; see tests/live for the opt-in live test."""

import asyncio
import base64
import json
import unittest

import httpx

from styleapi.errors import ApiError
from styleapi.providers import EditRequest, OpenAIImageEditProvider

from .helpers import image_bytes

KEY = "sk-test-secret-value-abcdef"


def _provider(handler, model: str = "gpt-image-2") -> OpenAIImageEditProvider:  # type: ignore[no-untyped-def]
    return OpenAIImageEditProvider(
        KEY, model=model, quality="medium", base_url="https://api.openai.test/v1", timeout_seconds=30, transport=httpx.MockTransport(handler)
    )


def _request() -> EditRequest:
    return EditRequest(image_png=image_bytes("PNG", (512, 512)), prompt="Style: test", size="1024x1024")


def _fields(request: httpx.Request) -> dict[str, str]:
    body = request.content
    boundary = request.headers["content-type"].split("boundary=")[1].encode()
    out: dict[str, str] = {}
    for part in body.split(b"--" + boundary):
        if b"name=\"" not in part:
            continue
        header, _, value = part.partition(b"\r\n\r\n")
        name = header.split(b'name="')[1].split(b'"')[0].decode()
        out[name] = value.rstrip(b"\r\n").decode("latin-1") if b"filename=" not in header else "<file>"
    return out


class OpenAIProviderTest(unittest.TestCase):
    def run_edit(self, handler, model: str = "gpt-image-2"):  # type: ignore[no-untyped-def]
        return asyncio.run(_provider(handler, model).edit(_request()))

    def test_request_shape_gpt_image_2(self) -> None:
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["auth"] = request.headers["authorization"]
            seen["fields"] = _fields(request)
            png = image_bytes("JPEG", (1024, 1024))
            return httpx.Response(200, json={"created": 1, "data": [{"b64_json": base64.b64encode(png).decode()}], "usage": {"input_tokens": 5, "output_tokens": 7}})

        result = self.run_edit(handler)
        self.assertEqual(seen["url"], "https://api.openai.test/v1/images/edits")
        self.assertEqual(seen["auth"], f"Bearer {KEY}")
        fields = seen["fields"]
        assert isinstance(fields, dict)
        self.assertEqual(fields["model"], "gpt-image-2")
        self.assertEqual(fields["size"], "1024x1024")
        self.assertEqual(fields["quality"], "medium")
        self.assertEqual(fields["output_format"], "jpeg")
        self.assertEqual(fields["image"], "<file>")
        self.assertNotIn("input_fidelity", fields)
        self.assertNotIn("response_format", fields)
        self.assertEqual((result.input_tokens, result.output_tokens), (5, 7))
        self.assertTrue(result.image.startswith(b"\xff\xd8\xff"))

    def test_input_fidelity_only_for_supporting_models(self) -> None:
        seen: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen.update(_fields(request))
            return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(image_bytes("PNG", (256, 256))).decode()}]})

        self.run_edit(handler, model="gpt-image-1.5")
        self.assertEqual(seen["input_fidelity"], "high")

    def assertMaps(self, response: httpx.Response, code: str) -> ApiError:
        with self.assertRaises(ApiError) as ctx:
            self.run_edit(lambda _r: response)
        self.assertEqual(ctx.exception.code, code)
        self.assertNotIn(KEY, json.dumps(ctx.exception.body("r")))
        return ctx.exception

    def test_error_mapping(self) -> None:
        self.assertMaps(httpx.Response(401, json={"error": {"message": f"Incorrect API key provided: {KEY}", "code": "invalid_api_key"}}), "PROVIDER_NOT_CONFIGURED")
        self.assertMaps(httpx.Response(429, json={"error": {"code": "rate_limit_exceeded"}}), "GENERATION_UNAVAILABLE")
        self.assertMaps(httpx.Response(400, json={"error": {"code": "moderation_blocked", "message": "x"}}), "PROVIDER_REJECTED")
        self.assertMaps(httpx.Response(400, json={"error": {"code": "invalid_value"}}), "PROVIDER_ERROR")
        self.assertMaps(httpx.Response(500, text="oops"), "PROVIDER_ERROR")
        self.assertMaps(httpx.Response(504, text="gateway"), "PROVIDER_TIMEOUT")
        self.assertMaps(httpx.Response(200, text="not json"), "INVALID_PROVIDER_RESPONSE")
        self.assertMaps(httpx.Response(200, json={"data": []}), "INVALID_PROVIDER_RESPONSE")
        self.assertMaps(httpx.Response(200, json={"data": [{"url": "https://x"}]}), "INVALID_PROVIDER_RESPONSE")
        self.assertMaps(httpx.Response(200, json={"data": [{"b64_json": "!!!notbase64"}]}), "INVALID_PROVIDER_RESPONSE")

    def test_timeout_and_network_errors(self) -> None:
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
