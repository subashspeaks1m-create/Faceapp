# PROGRESS

Current phase: **Phase 1, slice 1 (reproducible repo + authenticated backend runtime)**. Updated 2026-10-10.

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
- IV: Expo SDK 53 alignment via `expo install --check` (offline map): react-native 0.79.6, @shopify/react-native-skia 2.0.0-next.4.
- IU: `docker compose` file rewritten (postgres, redis, s3, migrate, api, worker, daemons). The images and commands were exercised individually; the full compose stack was not started as one unit.
- Note: `MANIFEST.json` and `VALIDATION_REPORT.md` describe the supplied baseline bundle and were intentionally not regenerated; this file records new evidence.
- Open: `npm audit --omit=dev` reports 39 advisories (21 high), all inside the Expo 53 / React Native 0.79 toolchain (metro, @expo/cli, node-forge, jest-*). Next.js is clean. Fixing them requires leaving the requested Expo 53 / Reanimated 3 track (current Expo is 57). Owner decision needed.

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

### B. Mobile editor, G. Admin
- SPEC: Not started in this slice. Mobile and admin are still the supplied shells (they type-check and build).

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
| `npm audit --omit=dev` | 39 advisories in Expo 53/RN 0.79 toolchain |
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

- Mobile stack is React Native/Expo as specified (not Flutter).
- ADR 0001: consent routes, `AssetFace`, media gateway and schema additions.
- ADR 0002: SeaweedFS for local S3.
- One credit unit per job (`CREDIT_UNITS_PER_JOB`); no free grant. Billing is Phase 3.
- `DELETE /jobs/{id}/data` also purges the source asset when no other unrevoked job uses it.

## Blockers and next steps (dependency order)

1. Owner decision: stay on Expo 53 / Reanimated 3 (39 npm advisories in its toolchain) or move to the current Expo SDK.
2. Mobile editor (Phase 1 B): picker/camera permissions, normalization, Skia canvas with LUTs and local adjustments, candidate/committed state, compare with accessible alternative, undo/reset, export/share. Can be written and type-checked here; native builds and device tests need a machine with Xcode/Android SDK.
3. Admin (Phase 1 G): OIDC-authenticated, role-checked metadata views.
4. Approved detector and parser artifacts (path, SHA256, licence approval) to enable face detection, then one approved transformation.
5. HEIC decoder licensing decision.
6. Production auth provider (issuer, audience, JWKS URL).
