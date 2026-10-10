# Setup and deployment

Three things need accounts only the owner can create: an **OpenAI API key**, an **Upstash Redis** database and a **Vercel** project for the style API. Put every secret into Vercel's environment-variable settings. Never paste a key into the repository, an issue, a chat, the app, or any `EXPO_PUBLIC_` variable.

## 1. OpenAI key

1. Sign in at platform.openai.com, add billing, and set a monthly budget limit under Settings > Limits.
2. Create a project API key (API keys > Create new secret key). Restrict it to the Images endpoint if your dashboard offers per-endpoint permissions.
3. If your organisation must verify before using GPT image models, complete Settings > Organization > Verification first; otherwise calls fail and the app shows "not set up correctly".
4. Copy the key straight into Vercel (step 3). Do not save it anywhere else.

## 2. Upstash Redis (rate limits)

1. At console.upstash.com create a Redis database (any region near your Vercel region; the free tier is enough).
2. From the database page copy **REST URL** and **REST token** (not the read-only token).
3. Alternatively, add Upstash from the Vercel Marketplace: it injects `KV_REST_API_URL` and `KV_REST_API_TOKEN`, which the API also accepts.

## 3. Deploy the style API to Vercel

1. vercel.com > Add New > Project > import `subashspeaks1m-create/Faceapp`.
2. **Root Directory:** `apps/style-api`. Framework preset: Other (or FastAPI if offered). Leave build and output settings empty; `apps/style-api/vercel.json` routes every path to `api/index.py` and allows 300 s per request.
3. **Environment Variables** (Production):

| Name | Value |
|---|---|
| `APP_ENV` | `production` |
| `ALLOWED_ORIGINS` | `https://subashspeaks1m-create.github.io` (add others comma-separated, scheme and host only) |
| `OPENAI_API_KEY` | your key (mark Sensitive) |
| `UPSTASH_REDIS_REST_URL` | REST URL from step 2 |
| `UPSTASH_REDIS_REST_TOKEN` | REST token (Sensitive) |
| `RATE_LIMIT_SALT` | a random string of 32+ characters, e.g. from `openssl rand -hex 32` (Sensitive) |

Optional: `OPENAI_IMAGE_MODEL` (`gpt-image-2`), `OPENAI_IMAGE_QUALITY` (`medium`), `LIMIT_PER_IP_HOUR` (5), `LIMIT_PER_IP_DAY` (15), `LIMIT_GLOBAL_DAY` (200), `PROVIDER_TIMEOUT_SECONDS` (240). The full list with defaults is in `apps/style-api/.env.example`.

4. Deploy, then open `https://<your-project>.vercel.app/api/health`. Expect `"status": "ok"` and `"provider_configured": true`. `misconfigured` means a setting was refused; the Vercel function log names it.

What production refuses on purpose: a wildcard or `http://` origin, any rate-limit backend other than Upstash, a non-https `OPENAI_BASE_URL`. If Upstash credentials or the salt are missing, or Upstash cannot be reached, `/api/generate` returns `GENERATION_UNAVAILABLE` and never calls OpenAI.

## 4. Rebuild the web app with the API URL

The live site is `https://subashspeaks1m-create.github.io/Faceapp/`, served from the `gh-pages` branch. The API URL is public and is compiled into the app.

```sh
npm ci
cd apps/mobile
EXPO_BASE_URL=/Faceapp EXPO_PUBLIC_STYLE_API_URL=https://<your-project>.vercel.app npm run build:web
```

`build:web` ends with a secret scan of `dist/` and fails if anything resembling a key is present. Then publish it from the repository root:

```sh
scripts/publish-gh-pages.sh
```

The script adds a new commit to `gh-pages` (copying `index.html` to `404.html` and keeping `.nojekyll`). It never force-pushes, so any earlier deploy can be restored with `git revert` on that branch.

For phones, set the same `EXPO_PUBLIC_STYLE_API_URL` in `apps/mobile/eas.json` under the build profile's `env`, or as an EAS environment variable, before `eas build`. Native apps send no `Origin`, so they do not need an `ALLOWED_ORIGINS` entry.

## Local development

```sh
cd apps/style-api
export APP_ENV=development RATE_LIMIT_BACKEND=memory ALLOWED_ORIGINS=http://localhost:8081
export OPENAI_API_KEY=...   # in your own shell only; omit to test the not-configured path
make -C ../.. dev-style-api # serves http://localhost:8790
```

Then run the app with `EXPO_PUBLIC_STYLE_API_URL=http://localhost:8790 npx expo start --web` from `apps/mobile`. On a phone on the same Wi-Fi use your computer's LAN address (`http://192.168.x.x:8790`); the app accepts plain http only for localhost and private addresses.

## Costs and limits

OpenAI bills GPT image models by tokens: input text, input image and output image. Check openai.com/api/pricing for current rates. Published per-image estimates for `gpt-image-2` output (taken from secondary sources citing OpenAI's calculator, not verified against OpenAI's own page from this environment):

| Quality | 1024×1024 | 1024×1536 or 1536×1024 |
|---|---|---|
| low | about $0.006 | about $0.005 |
| medium (default) | about $0.053 | about $0.041 |
| high | about $0.211 | about $0.165 |

Edits also pay for the input photo (sent at up to 1536 px) and the prompt. With the defaults (medium, 200 generations a day service-wide), the worst case is roughly 200 × $0.05 to $0.07, or about $10 to $14 a day, before input costs. Lower `LIMIT_GLOBAL_DAY` or the quality to reduce exposure, and keep an OpenAI budget limit as a second ceiling.

Default limits: 5 per client per hour, 15 per client per day, 200 per day in total. Upstash's free tier covers this traffic. Vercel bills function duration; a generation holds a function for roughly the provider's response time.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| App says "AI styles are not connected" | The web or phone build had no `EXPO_PUBLIC_STYLE_API_URL`. Rebuild with it (step 4). |
| "AI styles are not set up on this server yet" | `OPENAI_API_KEY` missing, or OpenAI returned 401/403 (wrong key, revoked key, unverified organisation). Fix in Vercel, then redeploy. |
| "Generation is temporarily unavailable" | Upstash unreachable or not configured, `RATE_LIMIT_SALT` missing, daily cap reached, or OpenAI returned 429 (rate limit or no credit). Check `/api/health` and the Vercel logs (they show `provider_error status=429` etc.). |
| "This site is not allowed to use the style service" | The page's origin is not in `ALLOWED_ORIGINS`. Use the scheme and host only: `https://subashspeaks1m-create.github.io`, no `/Faceapp`. |
| Browser console shows a CORS error | Same as above, or the API URL in the build is wrong. |
| "The AI service took too long" | OpenAI exceeded `PROVIDER_TIMEOUT_SECONDS`. Retry; consider `OPENAI_IMAGE_QUALITY=low`. |
| "The AI service declined this photo or style" | OpenAI's moderation refused it. Use a different photo. |
| "This photo is too large" | Over 4 MB or 16 MP after the app's resize; usually only when calling the API directly. |
| 404 at `subashspeaks1m-create.github.io` | The site is at `/Faceapp/`, and GitHub Pages must be enabled for the `gh-pages` branch in repository Settings > Pages. |

Every error the app shows includes a short reference. It is the start of the request ID, which appears in the Vercel log line for that request.
