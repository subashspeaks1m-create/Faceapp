# Testing AI Styles

Three kinds of test, kept separate on purpose:

| Kind | What talks to what | Costs money | Command |
|---|---|---|---|
| Unit and integration (mocked provider) | API code with a test double or a mocked HTTP transport; Upstash limiter against a real local `redis-server` | No | `make test-style-api` and `npm test --workspace=@portraitlab/mobile` |
| Browser end-to-end | Real web build → real style API → **fake OpenAI server** (`tests/e2e/fake_openai.py`, sepia-tones the photo) | No | see below |
| Live provider | Style API provider code → **real OpenAI** | Yes, one image | see below |

`make test` runs the first kind together with the rest of the repository's tests.

## What the mocked tests cover

- Catalog: exactly the 25 named styles in order and category; no prompt text in the public catalog; band boundaries 0/25/26/50/51/75/76/100; every prompt has identity, people-count and no-text clauses; high-strength extras only at 76+; schema rejects unknown fields, duplicate IDs and gaps; no studio or character names; the app's generated catalog matches the server's.
- Images: magic-byte sniffing; JPEG, PNG and WebP accepted; empty, corrupt, truncated, mismatched, too small, too many bytes, too many pixels, GIF/HEIC/PDF refused; EXIF rotation applied and metadata removed; transparency flattened; resize to 1536; output size choice; bad provider output refused.
- OpenAI provider (mocked transport): endpoint, auth header and form fields; `input_fidelity` sent only to models that accept it; usage parsing; mapping of 401, 429, moderation 400, other 400, 500, 504, non-JSON, empty data, URL instead of base64, invalid base64, timeouts and network errors; the key never appears in errors or `repr`.
- Rate limiter: the real Lua script on a real Redis via a fake Upstash REST endpoint; limits, rollback of refused requests, TTLs, global cap, 10 concurrent requests never exceed a limit of 3, fail closed when unreachable, unauthorised or unconfigured.
- HTTP: health, styles, quota; success returns a JPEG with quota and CORS headers; every validation error; Origin enforcement and CORS preflight; rate limit after N; each provider error code passes through with CORS headers; unexpected exceptions become `INTERNAL_ERROR` without leaking; not-configured and misconfigured states.
- App client (Node): search and category filtering, bands, base-URL rules, upload sizing, request fields, response and quota parsing, error mapping (server JSON, unknown codes, HTML error pages, non-JPEG bodies, network failure, cancel, no URL configured).

## Browser end-to-end

Needs Playwright with Chromium (`npm i -g playwright`, or the preinstalled one in Claude Code's cloud environment). From the repository root, in three terminals:

```sh
# 1. Fake OpenAI (test fixture only)
cd apps/style-api && ../../.venv/bin/python -m tests.e2e.fake_openai --port 8791

# 2. The real style API pointed at it
cd apps/style-api && APP_ENV=development OPENAI_BASE_URL=http://127.0.0.1:8791/v1 \
  OPENAI_API_KEY=sk-e2e-fake-key-not-real RATE_LIMIT_BACKEND=memory LIMIT_PER_IP_HOUR=2 \
  ALLOWED_ORIGINS=http://localhost:8765 TRUST_PROXY_HEADERS=false \
  ../../.venv/bin/python -m uvicorn api.index:app --port 8790

# 3. The web build
cd apps/mobile && EXPO_PUBLIC_STYLE_API_URL=http://localhost:8790 npm run build:web \
  && (cd dist && python3 -m http.server 8765)
```

Then `cd apps/mobile && npm run e2e`. It checks: 25 styles listed, search and category filter, choosing the synthetic demo portrait, that nothing is uploaded before consent, the consent sheet, a 200 `image/jpeg` response for the chosen style, the quota line, Result/Original/Compare views, a downloaded JPEG, the server's rate limit shown as "Limit reached", and no console errors. Restart server 2 before re-running (the memory limiter keeps its counts).

## Live provider test

Costs one image (about $0.04 to $0.05 at medium quality). Uses `assets/demo/portrait-original.png`, a synthetic fictional adult. Set the key only in your own shell:

```sh
cd apps/style-api
STYLE_API_LIVE=1 OPENAI_API_KEY=... STYLE_API_LIVE_STYLE=storybook-anime STYLE_API_LIVE_OUT=/tmp \
  ../../.venv/bin/python -m unittest tests.live.test_openai_live -v
```

It prints model, size, seconds and token counts, and writes the image for review. Look at identity, people count, absence of text, and whether the style reads correctly.

## Not yet tested

- Any real OpenAI call (no key, and this build environment cannot reach api.openai.com).
- The deployed Vercel function and real Upstash.
- The native phone upload path on an Android or iOS device.
- Screen-reader passes with TalkBack and VoiceOver.
