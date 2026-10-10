# Style API reference

Base URL: wherever `apps/style-api` is deployed (for example `https://portraitlab-style-api.vercel.app`). All responses carry `X-Request-ID`. Browsers may call the API only from origins listed in `ALLOWED_ORIGINS`.

## GET /api/health

Readiness without secrets.

```json
{
  "status": "ok",
  "provider_configured": true,
  "provider": "openai",
  "model": "gpt-image-2",
  "rate_limit_backend": "upstash",
  "catalog_version": "2026-10-10.1",
  "style_count": 25
}
```

`provider` is `openai` or `gemini` (the app uses it to name the provider in the consent screen). `status` is `ok`, `provider_not_configured` (no key for the selected provider) or `misconfigured` (settings refused at startup; check the function logs for the setting name).

## GET /api/styles

The public catalog: `version`, `categories[]`, `intensity_bands[]` (`min`, `max`, `label`) and `styles[]` with `id`, `number`, `name`, `category`, `summary`, `tags`, `default_intensity`, `swatch`. Prompt text is never returned. Cached for 5 minutes.

## GET /api/quota

Remaining generations for the caller, without using one.

```json
{ "remaining": 4, "limit": 5, "window": "hour" }
```

`window` is the tightest limit: `hour`, `day` or `global` (the service-wide daily cap).

## POST /api/generate

`multipart/form-data`, at most 4,000,000 bytes of image plus form overhead (Vercel's request limit is 4.5 MB).

| Field | Type | Rules |
|---|---|---|
| `image` | file | JPEG, PNG or WebP by magic bytes; declared type must match; not animated; at least 256 px on the short side; at most 16 MP |
| `style_id` | string | An `id` from `/api/styles` |
| `intensity` | string | Whole number `0` to `100` |
| `consent` | string | Must be `true` |

Success: `200`, `Content-Type: image/jpeg`, the styled image (1024×1024, 1024×1536 or 1536×1024, matching the photo's shape), with headers:

| Header | Meaning |
|---|---|
| `X-Style-Id` | Style used |
| `X-Catalog-Version` | Catalog version used |
| `X-Quota-Remaining`, `X-Quota-Limit`, `X-Quota-Window` | Quota after this request |
| `Cache-Control: no-store` | Never cached |

Example (from a shell; a browser would also send `Origin`):

```sh
curl -sS -X POST "$STYLE_API/api/generate" \
  -F image=@photo.jpg -F style_id=seventies-film -F intensity=60 -F consent=true \
  -o result.jpg -D -
```

Order of checks: Origin, provider configured, size, multipart, consent, style, intensity, image decode, then rate limit, then the provider call. Requests rejected before the rate limit do not use quota.

## Errors

Every error is JSON:

```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "You have reached the generation limit for now. Try again later.",
    "retryable": true,
    "request_id": "6f1c…",
    "retry_after_seconds": 1840
  }
}
```

`retry_after_seconds` (and a `Retry-After` header) appear only when known. Messages are written for end users and never include provider text, configuration or secrets.

| Code | HTTP | Retryable | When |
|---|---|---|---|
| `INVALID_IMAGE` | 400 | no | Empty, corrupt, truncated, too small, or declared type differs from content |
| `UNSUPPORTED_IMAGE_FORMAT` | 415 | no | Not JPEG, PNG or WebP (for example HEIC, GIF, PDF), or animated |
| `IMAGE_TOO_LARGE` | 413 | no | Over the byte or pixel limit |
| `INVALID_STYLE` | 400 | no | Unknown or missing `style_id` |
| `INVALID_REQUEST` | 400 | no | Not multipart, missing size, bad `intensity` |
| `CONSENT_REQUIRED` | 400 | no | `consent` is not `true` |
| `ORIGIN_NOT_ALLOWED` | 403 | no | Browser `Origin` not in `ALLOWED_ORIGINS` |
| `PROVIDER_NOT_CONFIGURED` | 503 | no | No key for the selected provider, or the provider rejected it |
| `RATE_LIMITED` | 429 | yes | Hourly or daily per-client limit reached |
| `PROVIDER_TIMEOUT` | 504 | yes | The provider did not answer within `PROVIDER_TIMEOUT_SECONDS` |
| `PROVIDER_REJECTED` | 422 | no | The provider's safety system declined the image or request |
| `PROVIDER_ERROR` | 502 | yes | Other provider or network failure (including an unknown model ID) |
| `INVALID_PROVIDER_RESPONSE` | 502 | yes | The provider returned no image or an undecodable one |
| `GENERATION_UNAVAILABLE` | 503 | yes | Rate limiter unreachable (fail closed), service-wide daily cap reached, provider busy or out of credit (429), or settings refused at startup |
| `INTERNAL_ERROR` | 500 | yes | Unexpected server error |

The app adds three client-side codes that never come from the server: `NOT_CONNECTED` (no API URL in this build), `NETWORK_ERROR` and `CANCELED`.

`INVALID_REQUEST`, `CONSENT_REQUIRED`, `ORIGIN_NOT_ALLOWED` and `PROVIDER_REJECTED` were added to the original code list so that these cases are not reported as a broken image or a server fault.
