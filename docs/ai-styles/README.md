# AI Styles

One-tap AI restyling of a single photo into one of 25 looks (70s Retro Film, Ghibli-Inspired Storybook, Cyberpunk and so on). The person uploads a photo, picks a style, sets a strength from 0 to 100 and gets a real image-to-image result from OpenAI's image edit API or Google's Gemini API (chosen by server setting), with Before/After compare and download or share.

This folder is the documentation for the feature:

| Document | What it covers |
|---|---|
| [README.md](README.md) (this file) | Product requirements, architecture, known limitations, third-party services |
| [API_REFERENCE.md](API_REFERENCE.md) | `GET /api/health`, `GET /api/styles`, `GET /api/quota`, `POST /api/generate`, error codes |
| [STYLE_PROMPT_GUIDE.md](STYLE_PROMPT_GUIDE.md) | How prompts are built, the 25 styles, how to add or change one |
| [SETUP_AND_DEPLOYMENT.md](SETUP_AND_DEPLOYMENT.md) | OpenAI key, Upstash, environment variables, deploying the API to Vercel, rebuilding GitHub Pages, costs and limits, troubleshooting |
| [SECURITY_AND_PRIVACY.md](SECURITY_AND_PRIVACY.md) | Key handling, CORS, rate limiting, validation, logging, data flow and retention |
| [TESTING.md](TESTING.md) | Unit, integration, browser end-to-end and the opt-in live test |

## Product requirements (as built)

- **Screens.** Home, style browser (category chips and search), style detail (strength slider with band label), upload (system picker or camera), consent sheet, progress (indeterminate spinner with a real elapsed-seconds counter and Cancel), result (Before/After slider, Result and Original toggles, Download, Share, Adjust and regenerate, Change style, Start over), failure and retry, Privacy, Settings (service status, quota, withdraw consent, clear session). A quota line ("3 of 5 generations left this hour") appears on the browser, detail and result screens.
- **Consent first.** Nothing is uploaded until the person ticks three boxes (send to the service and OpenAI; photo is of them or they have permission; they are 18+ and the photo shows no children) and taps Agree. The server also refuses a request without `consent=true`. Consent can be withdrawn in Settings.
- **No fake output.** If the app was built without a style API URL, it says AI styles are not connected. If the server has no OpenAI key it returns `PROVIDER_NOT_CONFIGURED`. There is no placeholder image, filter fallback or stock image anywhere in the flow.
- **No persistent gallery.** The server keeps nothing. The app keeps the result in memory (and a cache file on phones) until the person starts over or saves it.
- **Accessibility.** Every control has a label and role; the compare slider is an adjustable control (swipe up or down with a screen reader) and has button alternatives; status and errors are announced through live regions; touch targets are at least 44 pt; colour chips are hidden from screen readers because they are decoration.

## Architecture

```
Phone app / web app (Expo, apps/mobile)                 Style API (FastAPI, apps/style-api)              OpenAI
-------------------------------------------            ----------------------------------------        ------------------
pick photo -> normalize (orientation, <=24 MP)
style browser uses the bundled PUBLIC catalog
Generate -> consent? -> resize to <=1536 px JPEG ----->  CORS + Origin check
             multipart: image, style_id,                 validate: size, magic bytes, decode,
             intensity, consent                           pixels, min side, style id, intensity
                                                          rate limit (Upstash Lua, fail closed)
                                                          build prompt from SERVER catalog
                                                          re-encode PNG (drops EXIF/GPS) -------->  POST /v1/images/edits
                                                          validate output, re-encode JPEG <-------  data[0].b64_json
show result, compare, download/share  <-------------  image/jpeg + X-Quota-* headers
```

- **One catalog.** `apps/style-api/styleapi/catalog.json` is the only source of styles, categories, intensity bands and prompt text. The app bundles a generated public copy (`apps/mobile/src/styles/catalog.generated.ts`) that has no prompt text; a test fails if it drifts. The server only accepts style IDs from its own catalog.
- **Provider abstraction.** `styleapi/providers/base.py` defines `ImageEditProvider.edit(EditRequest) -> EditResult`. `OpenAIImageEditProvider` and `GeminiImageEditProvider` are the production implementations, selected by `IMAGE_PROVIDER`. A test double lives in `tests/helpers.py` and is never selectable at runtime.
- **Stateless and synchronous.** One HTTP request does the whole job. OpenAI image edits typically take tens of seconds; Vercel's function limit is 300 s on every plan with Fluid compute, and the provider timeout defaults to 240 s. An async job queue was not needed for this.
- **Separate from the Phase 1 portrait backend.** `apps/api-server` (PostgreSQL, S3, Celery, credits) is untouched. The style API is a small standalone service so it can be deployed on a serverless host without that infrastructure.

### Key files

| Path | Role |
|---|---|
| `apps/style-api/styleapi/catalog.json` | The 25 styles and prompt parts |
| `apps/style-api/styleapi/catalog.py` | Validated catalog model, public view, `build_prompt` |
| `apps/style-api/styleapi/app.py` | Routes, CORS, Origin check, request IDs, logging |
| `apps/style-api/styleapi/images.py` | Upload validation and output checks |
| `apps/style-api/styleapi/ratelimit.py` | Upstash limiter (and dev-only memory limiter) |
| `apps/style-api/styleapi/providers/openai_images.py`, `gemini_images.py` | OpenAI and Gemini image edit calls and error mapping |
| `apps/style-api/api/index.py`, `vercel.json` | Vercel entry point and function settings |
| `apps/mobile/app/styles.tsx`, `app/style/[id].tsx`, `app/result.tsx`, `app/privacy.tsx`, `app/settings.tsx` | Screens |
| `apps/mobile/src/styles/client.ts` | Request and response handling, error mapping |
| `apps/mobile/src/styles/upload.ts` / `upload.web.ts` | Platform-specific resize and upload |

## Known limitations

- **No live provider call has been made from this project yet.** The build environment cannot reach OpenAI or Google's APIs, and no key is configured on a server. Gemini's request format and model ID come from search results about Google's docs, which could not be opened directly. The request format follows OpenAI's published docs and is covered by mocked-transport tests; the first real check is the live test in [TESTING.md](TESTING.md) or the first generation after deployment.
- **The style API is not deployed yet.** It needs a Vercel project, an Upstash database and an OpenAI key, which only the owner can create. Until then the live web app shows "AI styles are not connected".
- **Phones are untested.** The native upload path (expo/fetch with an expo-file-system `File`) type-checks and follows Expo's documented FormData support but has not run on a device. The web build was tested end to end in Chromium.
- **Identity preservation is a prompt instruction, not a guarantee.** gpt-image-2 processes inputs at high fidelity, but strongly stylised looks (Pixel Art, Clay Figure, 3D Animated) will change faces. Results are labelled AI-generated.
- **Age and content checks rely on the person's declaration and OpenAI's moderation.** The service does not run its own face, age or nudity detection. Refusals by OpenAI surface as `PROVIDER_REJECTED`.
- **Output aspect is one of three sizes** (1024×1024, 1024×1536, 1536×1024), chosen from the photo's shape. Very wide or tall photos are reframed by the model.
- **Rate limits are per IP address.** People behind one shared IP share a quota; someone changing IPs gets a new one. The global daily cap is the hard cost ceiling.
- **Canceling stops waiting, not the provider call.** If the request already reached OpenAI it may finish and count toward the limit.
- **"Ghibli-Inspired" is a trademark reference in a style name** chosen by the product owner. Prompts never name the studio, its films or characters. Consider a neutral name such as "Storybook Anime" before a store release.

## Third-party services and licences

| Component | Use | Licence or terms |
|---|---|---|
| OpenAI Images API (`gpt-image-2` by default) | Image generation | OpenAI API terms and usage policies; per-image cost |
| Google Gemini API (`gemini-3.1-flash-image` by default) | Image generation (alternative) | Gemini API Additional Terms (paid tier required); per-image cost; outputs carry Google's SynthID watermark |
| Upstash Redis (REST) | Persistent rate-limit counters | Upstash terms; free tier available |
| Vercel (Python runtime) | Hosting the style API | Vercel terms |
| FastAPI, Starlette, Pydantic | API framework | MIT |
| httpx | HTTP client | BSD-3-Clause |
| Pillow | Image decode and re-encode | MIT-CMU (HPND) |
| python-multipart | Multipart parsing | Apache-2.0 |
| Expo, React Native, React Native Web | App | MIT |
| @react-native-community/slider | Strength slider | MIT |

Existing app and asset licences are listed in `assets/ASSET_LICENSES.md`.
