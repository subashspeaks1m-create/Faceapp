# Security and privacy

## Credentials

- `OPENAI_API_KEY`, `GEMINI_API_KEY`, `UPSTASH_REDIS_REST_TOKEN` and `RATE_LIMIT_SALT` are read only by the style API from server environment variables. They are held as `SecretStr`, excluded from `repr`, never logged and never returned (tests assert this for config, provider errors and every error response).
- The app contains only the API's public URL (`EXPO_PUBLIC_STYLE_API_URL`). `npm run build:web` scans the compiled output for key-like strings and variable names and fails if any are found.
- `.env`, `.env.*` are git-ignored; `.env.example` files contain names and placeholders only.
- A wrong or revoked key surfaces as `PROVIDER_NOT_CONFIGURED`. OpenAI's error text, which can echo part of the key, is never forwarded or logged; only the HTTP status and OpenAI's short error code are logged.

## Abuse and cost controls

- **Rate limits in Upstash.** One Lua script per request increments the per-client hourly and daily counters and the global daily counter together, and rolls all of them back if any is over. It is atomic, so concurrent requests on many serverless instances cannot overshoot (tested with 10 parallel requests against a real Redis). Production refuses any other backend.
- **Fail closed.** If Upstash is unreachable, unauthorised or not configured, or the salt is missing, `/api/generate` returns `GENERATION_UNAVAILABLE` before calling OpenAI.
- **Client identity.** The client IP (from Vercel's `x-vercel-forwarded-for` / `x-real-ip`) is HMAC-SHA256 hashed with `RATE_LIMIT_SALT`; Redis stores only the hash and counters, which expire after an hour or a day.
- **CORS.** Only origins in `ALLOWED_ORIGINS` (explicit https origins, no wildcard, no credentials) get CORS headers. A browser request with any other `Origin` is refused with `ORIGIN_NOT_ALLOWED` before any work. Native apps send no `Origin`; for them and for scripts the rate limits and global cap are the control. This is not authentication: anyone can call the API within the limits.
- **Bounded work.** Requests over the size limit are rejected from the `Content-Length` header before the body is parsed; multipart parsing is limited to one file and four fields; images are checked against the pixel cap from the header before decoding; Pillow's decompression-bomb guard is an error; the provider call has a timeout.

## Input and output validation

- Image type comes from magic bytes (JPEG, PNG, WebP). A declared type that disagrees is refused. HEIC, GIF, SVG, PDF and animated images are refused.
- The image is fully decoded, EXIF orientation applied, transparency flattened, resized to at most 1536 px and re-encoded as PNG. This drops EXIF (including GPS), XMP and other metadata before anything is sent to OpenAI.
- `style_id` must be in the server catalog; `intensity` must be a whole number 0 to 100; `consent` must be `true`.
- The provider's output is base64-decoded, sniffed, decoded and size-checked, then re-encoded as a metadata-free JPEG. Anything else is `INVALID_PROVIDER_RESPONSE`; nothing unverified reaches the client.
- Responses carry `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`.

## Logging

One line per request: request ID, method, path, status, duration. Generation adds style ID, strength, output size, provider duration and token counts, or the error code. Never logged: images, prompts, IP addresses, headers, provider error messages or secrets. Unhandled exceptions log only the exception type.

## Data flow and retention

| Data | Where | How long |
|---|---|---|
| Original photo | Phone or browser memory and cache | Until the person starts over, clears it in Settings, or the app is closed |
| Upload (resized JPEG) | Style API memory | Only during the request |
| Photo and prompt sent to OpenAI | OpenAI | Per OpenAI's API data policy: not used for training by default; abuse-monitoring logs kept up to 30 days unless Zero Data Retention is approved for the account |
| Photo and prompt sent to Gemini (if selected) | Google | Gemini API paid-tier terms: not used to improve Google products; logged for a limited period for abuse detection. Unpaid tier is refused in production (`GEMINI_PAID_TIER`) |
| Result image | Style API memory, then the device | Server: only during the request. Device: as for the original, or wherever the person saves it |
| Hashed IP + counters | Upstash | Up to 24 hours |
| Consent record | Device storage (version and time) | Until withdrawn in Settings |

There is no account, gallery, analytics or server-side image storage.

## Content policy

- The consent sheet requires the person to confirm the photo is of them or they have permission, and that they are 18+ and the photo shows no children.
- Prompts instruct the model to keep the person's identity, age, body and clothing coverage, and forbid sexualised or revealing changes, added people, text, logos and named characters or works.
- The provider's own moderation runs on every request; refusals (OpenAI moderation errors, Gemini block or safety finish reasons, or a text-only answer) return `PROVIDER_REJECTED`.
- The product does not identify people or infer sensitive attributes, and the privacy screen says results must not be used to identify anyone or passed off as real photos.
- Not built: the service does not run its own age, face or nudity detection. That would be a separate, reviewed model decision, as the Phase 1 spec requires for minor-use policy.

## Before a public launch

- Legal review of the privacy text, consent wording and the "Ghibli-Inspired" style name.
- GDPR or BIPA review if serving users in those jurisdictions (biometric data handling by the provider).
- Set an OpenAI budget limit and alerting; consider Vercel spend management.
- Consider an app-attestation or sign-in step if anonymous use is abused beyond what the per-IP limits handle.
