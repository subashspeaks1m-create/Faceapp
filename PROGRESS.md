# PROGRESS

Current phase: **Phase 1, slice 3 (AI Styles: 25 one-tap OpenAI image-edit styles)**; slice 2 was the Expo 57 on-device editor, slice 1 the backend runtime. Updated 2026-10-10.

## Slice 3: AI Styles (docs/ai-styles/)

Owner request (2026-10-10): integrate an AI image API so a user picks one of 25 named styles and gets a real image-to-image result, with a secure backend. Built as a standalone stateless FastAPI service `apps/style-api` (Vercel Python runtime) plus new app screens; `apps/api-server` is unchanged.

| Item | Status |
|---|---|
| 25-style catalog with server-only prompts, intensity bands, generated public copy for the app | IV (unit tests, drift test) |
| OpenAI provider (`POST /v1/images/edits`, default `gpt-image-2`, quality `medium`, JPEG output) | IU: request/response/error mapping tested on a mocked transport only. No real OpenAI call made: no key, and this environment cannot reach api.openai.com (proxy 403) |
| Validation (magic bytes, decode, pixels, EXIF strip), CORS allowlist, Origin check, error codes, logging without images/IPs/secrets | IV (HTTP tests) |
| Upstash rate limiter (atomic Lua, fail closed) | IV against local redis-server 7 through a fake Upstash REST endpoint; IU against real Upstash |
| App screens: home, style browser with search/categories, style detail with strength, consent sheet, progress/cancel, result with Before/After slider, download/share, failure/retry, privacy, settings, quota | IV on web (Playwright e2e, real API + fake OpenAI fixture); IU on phones (type-checked only) |
| Deployed backend | BLOCKED: needs owner's Vercel project, Upstash database and OpenAI key (Vercel connector here has no permission to create projects) |

Model and docs basis: OpenAI's image docs (via search; direct fetch blocked) say `gpt-image-1.5` shuts down 2026-12-01 and `gpt-image-2` must omit `input_fidelity`. Per-image prices in docs/ai-styles/SETUP_AND_DEPLOYMENT.md are secondary-source estimates.

Commands run for this slice:

| Command | Result |
|---|---|
| `make test-style-api` | 48 run, 47 pass, 1 skipped (live OpenAI test, opt-in) |
| `npm test --workspace=@portraitlab/mobile` | 33 pass (25 editor + 8 AI Styles client/catalog) |
| `make test` | pass (style API + 53 runtime tests, 25 integration skipped without services + mobile) |
| `make lint`, `make build` | pass |
| `npm run build:web` with `EXPO_PUBLIC_STYLE_API_URL` | builds; bundle secret scan clean; scanner verified to fail on a planted key |
| `npm run e2e` (Chromium 412×915, real style API → fake OpenAI) | pass: 25 styles, search/filter, consent gate (no upload before consent), 200 image/jpeg, quota header, compare views, JPEG download, server rate limit shown, no console errors |


## Environment actually available

| Capability | Status |
|---|---|
| Files, shell, package install (PyPI, npm) | Yes |
| Python | 3.12 via `uv` (host also has 3.13) |
| Node / npm | 22.22.0 / 10.9.4 |
| Docker | Yes (daemon started manually). `minio/minio` image unavailable, see ADR 0002 |
| PostgreSQL | 16 (local cluster) |
| Redis | 7.0.15 |
| S3-compatible store | SeaweedFS 3.97 in Docker, tmpfs |
| GPU / CUDA | None |
| iOS / Android simulators, Xcode, Android SDK | None |

## Requirement status

Legend: **IV** implemented and verified, **IU** implemented but unverified, **SPEC** specification/interface only, **BLOCKED** blocked by a named dependency.

### A. Reproducible repository
- IV: Clean Python 3.12 venv from `requirements-dev.lock`; NumPy/OpenCV mismatch resolved (NumPy 2.2.6 with opencv-python-headless 4.12.0.88, which declares `numpy<2.3`).
- IV: Hash-pinned `apps/api-server/requirements.lock` used by the Dockerfile (`--require-hashes`).
- IV: FastAPI 0.115.12/Starlette 0.46.2 had 14 published Starlette advisories (pip-audit). Upgraded to FastAPI 0.143.0 / Starlette 1.7.0; pip-audit now reports none; all tests pass.
- IV: npm workspaces installed, `package-lock.json` committed. `npm run build` (shared-types tsc, mobile tsc, `next build`) and `npm run lint` pass.
- IV: Upgraded to Expo 57 / React Native 0.86.3 / Reanimated 4.5.1 / Skia 2.6.2 (owner decision, ADR 0003). `expo install --check` reports aligned.
- IU: `docker compose` file rewritten (postgres, redis, s3, migrate, api, worker, daemons). The images and commands were exercised individually; the full compose stack was not started as one unit.
- Note: `MANIFEST.json` and `VALIDATION_REPORT.md` describe the supplied baseline bundle and were intentionally not regenerated; this file records new evidence.
- Open: `npm audit --omit=dev` still reports 44 advisories after the Expo 57 upgrade, in build tooling (Expo CLI, Metro, Jest, prebuild). node-forge, braces and sprintf-js have no patched release. In app runtime: decode-uri-component via expo-router (DoS on malformed links). Next.js is clean. See ADR 0003.

### C. Authenticated API and database
- IV: JWT verification of signature, issuer, audience, expiry, `sub`; `alg` allowlist; `none` and wrong-key tokens rejected. Dev HS256 auth only via `JWT_DEV_HS256_SECRET`, refused when `PORTRAITLAB_ENV=production`; production uses `JWT_PUBLIC_KEY_PEM` or `JWT_JWKS_URL`.
- IV: Users and wallets provisioned from verified subjects. Owner-mismatched consent/asset/job/face IDs return 404.
- IV: Consent create/withdraw routes (ADR 0001). Withdrawal revokes assets and tombstones jobs.
- IV: Upload grants: server-generated random prefix, 60 s presigned PUT with signed Content-Type and SHA256 header, 10 min absolute deadline, 5 grants/min/user.
- IV: Finalization: HEAD size check, streamed SHA256 verification (store does not verify the body, ADR 0002), magic-byte sniffing, 24 MP header check before decode, EXIF orientation applied, ICC converted to sRGB, all metadata stripped (PNG re-encode), raw upload deleted.
- IV: Migrations: Prisma 6.19.3-generated baseline + raw constraints + runtime constraints, applied to real PostgreSQL 16 by `python -m portraitlab.service migrate`; CHECK constraints verified active.
- IV: Safe error envelopes, `Cache-Control: no-store` on every response.
- BLOCKED (decoder licensing): HEIC is accepted by the contract but finalization returns `UNSUPPORTED_IMAGE_FORMAT` until a HEIC decoder (libheif/pillow-heif) is approved.
- BLOCKED (approved detector weights): with no approved detector in `model-registry.json`, finalization returns 503 `DETECTOR_UNAVAILABLE` and purges the upload. Verified against the running server.
- SPEC: TypeScript declarations are hand-synced with Pydantic; schema-driven TS generation not yet added.

### D. Jobs and credits
- IV: Transform creates wallet reservation, ImageJob, RESERVE ledger row, outbox event and audit row in one transaction, wallet row locked first.
- IV: Idempotency: same key + same canonical hash returns the original job (also under 5 concurrent identical requests); different body returns 409.
- IV: 402 `CREDIT_REQUIRED`, 429 `ADMISSION_LIMIT` (2 pending/user), 503 `FILTER_UNAVAILABLE` before any charge.
- IV: Worker claims by conditional update with incremented fence and lease, renews the lease by heartbeat, re-checks the fence before fetching input and before writing, and attaches the result conditionally. Settlement happens once; redelivery returns `not_claimable`; a stale fence after lease expiry cannot attach and its output is deleted.
- IV: Reconciler requeues dead leases once, then fails and releases; expires queued work; repairs unreleased reservations.
- IV: Outbox relay (`FOR UPDATE SKIP LOCKED`) publishes opaque job IDs only.
- IV: Long polling waits on PostgreSQL `LISTEN/NOTIFY` with no pooled connection checked out during the wait (asserted), wakes on change, returns the snapshot on timeout.
- IV: Progress is `indeterminate`/null until success (`complete`, 100). No timers.
- IU: Celery worker boots against Redis and registers `portraitlab.process_job`; a job was not pushed through Celery end to end because no filter is approved.

### E. Real transformation
- BLOCKED (approved weights/licences): `model-registry.json` has no approved detector, parser or generative route, so every filter returns `FILTER_UNAVAILABLE`. The registry-driven executor only enables a filter when detector, parser and its route all carry path, SHA256 and a commercial approval reference. Baseline geometry/blending tests still pass (17 cases).

### F. Privacy lifecycle
- IV: Purge daemon tombstones/revokes before I/O, deletes all objects, versions, delete markers and multipart uploads under the prefix, verifies absence, redacts object pointers/checksum, deletes face geometry, retries with capped backoff.
- IV: Orphan uploads (>2 min unfinalized), expired assets (10 min absolute), idle sources (30 s after last job), expired result windows (5 min), deleted jobs.
- IV: Delete concurrent with an output write: tombstone wins, late output deleted, job ends `purged`, credits released, source purged.
- IV: Media gateway: 15 s HMAC capability, database check on every access, tampered token 404, expired 410, revoked after delete 410.
- IV: Inventory sweep deletes prefixes no live row accounts for.
- SPEC: No claim of GDPR/BIPA compliance; working bytes exist briefly by design.

### B. Mobile editor
- IV: Render engine (`src/editor/render.ts`): crop → LUT → colour matrix, one path for preview and export. Run on CanvasKit in Node: identity export bit-exact at source size; colour within 1/255 and all four LUTs within 2/255 of a CPU reference; preview picture bit-identical to export.
- IV: Candidate/committed history (apply, discard, undo, redo, reset, 100-entry cap keeping the original), input validation, crop geometry, .cube parsing, generated LUT module drift check. 25 tests.
- IV: Metro bundles for iOS and Android (`expo export`, Hermes bytecode); `expo prebuild` generates both native projects with camera/photo permission strings.
- IU: Screens: privacy notice, choose photo (system picker), take photo (system camera, permission denied and Open Settings states), editor with Adjust/Looks/Crop/AI tabs, labelled sliders, Before/After toggle and press-and-hold compare, Undo/Redo/Reset, Apply/Discard, full-size JPEG export to the share sheet. Type-checked and bundled; never run on a device or simulator (none available here).
- IU: Normalization through expo-image-manipulator: orientation applied, >24 MP downscaled with a notice, PNG re-encode drops metadata. EXIF orientation and ICC handling not verified on devices.
- SPEC: Editor AI tab lists the 12 Phase 1 portrait filters as "Not available yet" (separate from AI Styles, which upload through the style API). No face picker. Crop is centered aspect presets only (no free crop/rotate).

### G. Admin
- SPEC: Not started. Still the supplied Next.js shell (type-checks and builds).

## Commands run (this slice)

| Command | Result |
|---|---|
| `uv venv --python 3.12 .venv && uv pip sync requirements-dev.lock` | ok |
| `make test` without service env | 53 run, 28 pass, 25 integration skipped |
| `make test` with PostgreSQL 16 + SeaweedFS | 53 run, all pass on 5 runs after the storage fix (one earlier run failed in setup while SeaweedFS was still starting; runs before the fix failed when SeaweedFS ran out of volumes) |
| `make lint` (ruff + tsc) | pass |
| `scripts/static_check.py` | pass |
| `npm install`, `npm run build --workspaces`, `npm run lint --workspaces` | pass |
| `uvx pip-audit -r requirements-dev.lock` | no known vulnerabilities |
| `npm audit --omit=dev` | 44 advisories in Expo 57 build toolchain (ADR 0003) |
| `npm test --workspace=@portraitlab/mobile` | 25 pass (render tests on CanvasKit 0.41) |
| `npx tsc --noEmit` (mobile) | pass |
| `expo install --check` | aligned with Expo 57 |
| `expo export --platform android --platform ios` | both bundles built (1966 / 1874 modules) |
| `expo prebuild --no-install --platform all` | native projects generated (then deleted; CNG) |
| Live server smoke (`uvicorn` + migrate + dev token + consent + presigned PUT + complete) | 503 `DETECTOR_UNAVAILABLE`, as designed |
| `celery -A portraitlab.tasks worker` | boots, task registered |

## Startup

```sh
make python-env                     # .venv from requirements-dev.lock
npm ci
cp .env.example .env                # fill local-only values
cp infra/seaweedfs/s3.json.example infra/seaweedfs/s3.json   # same keys as S3_ACCESS_KEY/S3_SECRET_KEY
docker compose --env-file .env up -d postgres redis s3
set -a; . ./.env; set +a
make migrate
PYTHONPATH=packages/shared-types:apps/api-server .venv/bin/python -m portraitlab.service ensure-bucket
make dev                            # API on :8000
make worker                         # Celery worker
make daemons                        # outbox relay, reconciler, purge
PYTHONPATH=packages/shared-types:apps/api-server .venv/bin/python -m portraitlab.service dev-token alice
PYTHONPATH=packages/shared-types:apps/api-server .venv/bin/python -m portraitlab.service grant-credits alice 10 dev-grant-1
```

Environment variable names: `PORTRAITLAB_ENV`, `DATABASE_URL`, `REDIS_URL`, `S3_BUCKET`, `S3_INTERNAL_ENDPOINT`, `S3_PUBLIC_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_REGION`, `JWT_ISSUER`, `JWT_AUDIENCE`, `JWT_PUBLIC_KEY_PEM` | `JWT_JWKS_URL` | `JWT_DEV_HS256_SECRET`, `JWT_ALGORITHMS`, `MEDIA_TOKEN_SECRET`, `CONSENT_POLICY_VERSION`, `CREDIT_UNITS_PER_JOB`, and for tests `PORTRAITLAB_TEST_DATABASE_URL`, `PORTRAITLAB_TEST_S3_ENDPOINT`, `PORTRAITLAB_TEST_S3_ACCESS_KEY`, `PORTRAITLAB_TEST_S3_SECRET_KEY`.

## Real versus fixture

- Real: PostgreSQL, S3 store, presigned URLs, JWT verification, image normalization, ledger, purge, long polling.
- Fixtures (tests only, `tests/test_runtime_integration.py`): `FixtureDetector` returns one fixed box; `FixtureExecutor` inverts pixels. They exist only to drive the job lifecycle and are never wired into the service.
- No inference measurement exists. No latency, quality or cost numbers are claimed.

## Decisions

- Mobile stack is React Native/Expo as specified (not Flutter). Expo 57 + Reanimated 4, system picker/camera instead of VisionCamera (ADR 0003).
- ADR 0001: consent routes, `AssetFace`, media gateway and schema additions.
- ADR 0002: SeaweedFS for local S3.
- One credit unit per job (`CREDIT_UNITS_PER_JOB`); no free grant. Billing is Phase 3.
- `DELETE /jobs/{id}/data` also purges the source asset when no other unrevoked job uses it.

## Blockers and next steps (dependency order)

0. AI Styles go-live (owner actions, docs/ai-styles/SETUP_AND_DEPLOYMENT.md): create the OpenAI key and Upstash database, deploy `apps/style-api` on Vercel, then rebuild the web app with `EXPO_PUBLIC_STYLE_API_URL` and run the live test.
1. Run the app on a device: follow docs/DEVICE_TESTING.md (development build; EAS profiles in apps/mobile/eas.json, not yet run because they need an Expo login).
2. App side of the cloud flow: consent, upload, face picker, job status, result binding (`src/editor-binding.ts`). Useful only once a model is approved.
3. Admin (Phase 1 G): OIDC-authenticated, role-checked metadata views.
4. Approved detector and parser artifacts (path, SHA256, licence approval) to enable face detection, then one approved transformation.
5. HEIC decoder licensing decision.
6. Production auth provider (issuer, audience, JWKS URL).
