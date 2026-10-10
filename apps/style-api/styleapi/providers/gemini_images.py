"""Google Gemini API image editing (POST {base}/models/{model}:generateContent).

The photo goes in as inline image data next to the text instruction; the response carries the image
as inline data in the candidate's parts. Gemini picks output pixel dimensions from the requested
aspect ratio. Provider error text is never forwarded to clients; only its category is.
"""

from __future__ import annotations

import base64
import binascii
import logging

import httpx

from ..errors import ApiError
from ..images import ProviderSize
from .base import EditRequest, EditResult

log = logging.getLogger("styleapi.provider")

_ASPECT: dict[ProviderSize, str] = {"1024x1024": "1:1", "1024x1536": "2:3", "1536x1024": "3:2"}
# Finish or block reasons that mean Google's safety systems declined the request or the image.
_SAFETY_REASONS = frozenset({"SAFETY", "IMAGE_SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION", "IMAGE_PROHIBITED_CONTENT", "IMAGE_RECITATION"})


class GeminiImageEditProvider:
    name = "gemini"

    def __init__(
        self,
        api_key: str,
        *,
        model: str,
        base_url: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._timeout = timeout_seconds
        self._transport = transport

    def __repr__(self) -> str:  # never show the key
        return f"GeminiImageEditProvider(model={self._model!r})"

    def _body(self, request: EditRequest) -> dict[str, object]:
        return {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": request.prompt},
                        {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(request.image_png).decode("ascii")}},
                    ],
                }
            ],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {"aspectRatio": _ASPECT[request.size]},
            },
        }

    async def edit(self, request: EditRequest) -> EditResult:
        timeout = httpx.Timeout(self._timeout, connect=10.0)
        try:
            async with httpx.AsyncClient(timeout=timeout, transport=self._transport) as client:
                resp = await client.post(
                    f"{self._base_url}/models/{self._model}:generateContent",
                    json=self._body(request),
                    headers={"x-goog-api-key": self._api_key},
                )
        except httpx.TimeoutException as e:
            raise ApiError("PROVIDER_TIMEOUT") from e
        except httpx.HTTPError as e:
            raise ApiError("PROVIDER_ERROR") from e
        if resp.status_code != 200:
            raise _map_error(resp)
        return self._parse(resp)

    def _parse(self, resp: httpx.Response) -> EditResult:
        try:
            payload = resp.json()
        except ValueError as e:
            raise ApiError("INVALID_PROVIDER_RESPONSE") from e
        if not isinstance(payload, dict):
            raise ApiError("INVALID_PROVIDER_RESPONSE")
        feedback = payload.get("promptFeedback")
        if isinstance(feedback, dict) and feedback.get("blockReason"):
            log.warning("provider_blocked reason=%s", str(feedback.get("blockReason"))[:40])
            raise ApiError("PROVIDER_REJECTED")
        candidates = payload.get("candidates")
        first = candidates[0] if isinstance(candidates, list) and candidates else None
        if not isinstance(first, dict):
            raise ApiError("INVALID_PROVIDER_RESPONSE")
        image_b64: str | None = None
        content = first.get("content")
        parts = content.get("parts") if isinstance(content, dict) else None
        for part in parts if isinstance(parts, list) else []:
            inline = part.get("inlineData") or part.get("inline_data") if isinstance(part, dict) else None
            if isinstance(inline, dict) and str(inline.get("mimeType") or inline.get("mime_type") or "").startswith("image/"):
                data = inline.get("data")
                if isinstance(data, str) and data:
                    image_b64 = data
                    break
        if image_b64 is None:
            reason = str(first.get("finishReason") or "")
            log.warning("provider_no_image finish_reason=%s", reason[:40])
            # A text-only answer or a safety finish means the model declined to make the image.
            if reason in _SAFETY_REASONS or reason in ("NO_IMAGE", "IMAGE_OTHER") or (isinstance(parts, list) and parts):
                raise ApiError("PROVIDER_REJECTED")
            raise ApiError("INVALID_PROVIDER_RESPONSE")
        try:
            image = base64.b64decode(image_b64, validate=True)
        except (binascii.Error, ValueError) as e:
            raise ApiError("INVALID_PROVIDER_RESPONSE") from e
        usage = payload.get("usageMetadata")
        input_tokens = usage.get("promptTokenCount") if isinstance(usage, dict) else None
        output_tokens = usage.get("candidatesTokenCount") if isinstance(usage, dict) else None
        return EditResult(
            image=image,
            model=self._model,
            input_tokens=input_tokens if isinstance(input_tokens, int) else None,
            output_tokens=output_tokens if isinstance(output_tokens, int) else None,
        )


def _map_error(resp: httpx.Response) -> ApiError:
    status = resp.status_code
    google_status = ""
    reason = ""
    try:
        body = resp.json()
        err = body.get("error") if isinstance(body, dict) else None
        if isinstance(err, dict):
            google_status = str(err.get("status") or "")
            for detail in err.get("details") or []:
                if isinstance(detail, dict) and detail.get("reason"):
                    reason = str(detail["reason"])
                    break
    except ValueError:
        pass
    # Only the HTTP status and Google's short status/reason codes are logged; never the message.
    log.warning("provider_error status=%s google_status=%s reason=%s", status, google_status[:40], reason[:40])
    if status in (401, 403) or reason in ("API_KEY_INVALID", "API_KEY_SERVICE_BLOCKED", "SERVICE_DISABLED"):
        return ApiError("PROVIDER_NOT_CONFIGURED", "AI styles are not available right now because the server's AI account is not set up correctly.")
    if status == 429:
        return ApiError("GENERATION_UNAVAILABLE", "The AI service is busy or out of quota. Try again later.")
    if status in (408, 504) or google_status == "DEADLINE_EXCEEDED":
        return ApiError("PROVIDER_TIMEOUT")
    if status in (400, 404, 413, 422):
        return ApiError("PROVIDER_ERROR", "The AI service could not process this request. Try again, or try a different photo.")
    return ApiError("PROVIDER_ERROR")
