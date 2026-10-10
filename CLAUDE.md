# 7. Claude Code / Claude Projects implementation blueprint

## Project summary and goals

Build an independent FaceApp-like portrait modification product: iOS/Android React Native/Expo, Next.js admin/preview, FastAPI gateway/Celery/private storage, Python GPU pipeline. Twelve launch tiles include four age, three expression, two presentation, hair color, beard and combined beauty with makeup/skin controls. Preserve user source and selected-face continuity; do not misrepresent unimplemented/research-only routes. Read PROJECT_SPECIFICATION.md, schemas/OpenAPI, Prisma + migration constraints, privacy purge and model registry before implementing.

## Coding conventions

TypeScript strict, no implicit any, no unchecked indexed access; typed errors/unions; generated API types from source schemas; no provider secrets in client. Python3.12 type hints, Pydantic2 extra=forbid with strict numeric/bool fields, Ruff lint and focused unittest/pytest. No `except: pass`, swallowed model errors or success-shaped dummy response. Return stable safe code/message/retryable/request_id; log opaque job IDs/durations only. Validate bytes/pixels/EXIF/ICC, masks/tensor dimensions, finite values and asset ownership. UUID secrecy is not authorization.

Source images are immutable; candidate/committed/revision separate; crop geometry and masks use one documented transform chain. Unknown filter/model/version returns FILTER_UNAVAILABLE. Models require local approved path/checksum/licensing. No download during a request. InsightFace detection uses5 landmarks, dense68 is a separate optional adapter; do not load recognition embeddings by default. Pipeline output remains source resolution and untargeted pixels are protected.

## Commands

`npm run build`, `npm run test`, `npm run dev`, `npm run lint`, `npm run docker:up` delegate to Makefile. Prerequisite Python environment is `python3 -m venv .venv`, then `.venv/bin/python -m pip install -r requirements-dev.txt`; app packages use npm workspaces. `make dev` serves API; `make dev-mobile`/`make dev-web` run application packages. `make docker-up` starts private local infrastructure. Initial scaffold health/OpenAPI works after dependencies; production routes fail503 until Runtime repositories/auth/queue are implemented. Do not call that a full backend.

`make build` performs static Python/schema checks plus app TypeScript checks as configured; it does not create signed mobile binaries or build unimplemented screens. Create native builds with Expo prebuild/run/EAS and document actual platform tests. Freeze compatible JS/Python dependencies and container digests during Phase1; ranges/tags in this specification are bootstrap candidates, not a reviewed production lockfile. GPU optional dependencies need CUDA12/cuDNN major compatibility and deployment-hardware testing.

## Start building Phase 1 — exact order

1. Audit scaffold, identify actual versus interface-only code; record versions/decisions in PROGRESS.md. Resolve any contract changes in Pydantic, TS, OpenAPI and Prisma together.
2. Install and lock compatible dependencies. Keep requested Reanimated3 track only with compatible Expo/RN patches; no silent unsupported native package mix.
3. Implement Expo navigation, system picker/camera permission paths, original normalization, Skia local canvas, candidate/committed state, compare, undo and real edited export. No forced cloud call for local tools.
4. Implement safe authenticated Runtime interface: upload grants/finalize and owner/consent relations using PostgreSQL/private MinIO. Routes must not trust client object keys or remote URLs.
5. Apply migrations/constraints; implement atomic credit reservation, idempotency hash, job/outbox, task leases/fences and long-poll update notification.
6. Connect licensed detector/parser local artifacts, then a single real transformation. Missing generative weights stay unavailable, not simulated with color filters. Run geometry/zero-intensity/locality tests and permitted face benchmark.
7. Implement purge daemon and media gateway; test deletion concurrent with output writes/callbacks and orphan cleanup before expanding AI families.
8. Build minimal Next.js metadata admin/preview with role checks, feature/worker status and no public portrait listing.
9. Report runnable flow, actual tests/platforms, what remains scaffold-only, licensing/accounts missing, measured latency and next phase. Preserve prior build kit.

## Later phases

Phase2 approved age/expression/presentation/style modules and calibrated intensity; Phase3 live store billing, quota/restore/revocation, full editor polish; Phase4 real-device/GPU concurrency/privacy/accessibility/store deployment. Do not promise 2.5s cold-start diffusion; keep readiness/warm pool and measured fast/slow routes. No fake progress percentage: indeterminate or actual step callback. Private result delivery only, no public CDN portrait URLs.

## Production invariants

Credits reserved transactionally before paid work, settled once; request key reused with different body409; at-least-once Celery does not duplicate cost; deletion/tombstones override every task; no resurrection after purge; absolute expiry never sliding; no images/vectors/EXIF in Redis/logs/audit; restoration optional/benchmarked; teen effect illustrative and actual minor-use policy reviewed; policy claims match provider/storage reality. GDPR/BIPA review is a release gate, not a promise made by the scaffold.

## Completion evidence

PROGRESS.md lists commands, pass/fail, live vs mock, actual device/GPU/backend versions, model/checkpoint/prompt version, output dimensions/latency/cost, constraints and blockers. Continue reversible work without repetitive approvals. Secret names may be documented, secret values never pasted. Do not claim native/AI/billing tests passed when only package or geometry tests ran.

## AI Styles service (apps/style-api)

Standalone stateless FastAPI service for the 25 one-tap OpenAI image-edit styles; docs in docs/ai-styles/. `styleapi/catalog.json` is the only source of styles and prompts: after editing it run `make style-catalog` (regenerates `apps/mobile/src/styles/catalog.generated.ts`, which must never contain prompt text) and `make test-style-api`. Keep `OPENAI_API_KEY`, Upstash tokens and `RATE_LIMIT_SALT` server-only; the app may contain only `EXPO_PUBLIC_STYLE_API_URL`, and `npm run build:web` scans the bundle for secrets. Production must keep Upstash rate limiting (fail closed), explicit https CORS origins and the `consent=true` check. Provider test doubles stay in `tests/`; there is no fallback or simulated generation. Live OpenAI tests are opt-in (`STYLE_API_LIVE=1`).
