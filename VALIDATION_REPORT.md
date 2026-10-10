# Validation report — 2026-10-10

## Passed on this computer

- 28 Python unittest cases: 11 API/schema cases and 17 image geometry/locality/error cases.
- Five-point scale/rotation/translation fit,512 crop/validity, exact zero-delta and zero-strength original, finite feather locality, other-face protection, sensitive eye/lip protection, zero-validity rejection and Poisson outside-region preservation.
- Missing filter/face, cancelled job, expired stage/unlocked worker slot, bad mask, oversized/empty image and nonfinite intensity checks.
- Pydantic strict fields/ranges/options/extra keys, uploaded size/checksum, progress/result consistency, OpenAPI3.1 routes/auth/idempotency, no-store responses, unconfigured 503, missing auth 401, validation input redaction and 12 manifest/schema ID agreement.
- Ruff0.11.13 check passed on all Python apps/packages/scripts/tests after formatting.
- Python AST, JSON/SVG parsing, asset references andschema draft2020-12 checks passed. OpenAPI generated from actual app; YAML/JSON equivalence checked during packaging.
- ZIP byte integrity and file/hash manifest checked during final packaging.

Local test runtime: Python 3.12, NumPy 2.3.5, OpenCV 4.12.0, Pydantic 2.13.5, FastAPI 0.115.12/Starlette 0.46.2, AnyIO 4.9.0, HTTPX 0.28.1, jsonschema 4.23.0. Libraries for validation were isolated in temporary directories. OpenCV bootstrap requirements prefer NumPy<2.3 according to its wheel dependency range; current host NumPy 2.3.5 loaded successfully for these tests, but that does not validate every production matrix. Install/freeze a consistent dependency set for deployment.

## Not run / not supplied

No actual InsightFace/BiSeNet/generative/restoration weights were loaded. GPU/CUDA/Triton/Modal/RunPod quality, identity and latency are unmeasured. ONNX adapters are code/contracts with no real checkpoint execution.28 tests do not demonstrate realistic age/smile/gender generation or 2.5-second service latency.

No JS dependencies installed/locked; no Expo native/device/Skia/VisionCamera/Next production build, TypeScript workspace check or signed store package was run here. Native/mobile andwebUI remain initial shells. No PostgreSQL/Prisma CLI migration execution, SQL integration, Docker startup, actual storage presign/purge or Celery queue/billing integration run. Auth/storage/job/wallet/purge Runtime remains interface-only and API routes fail closed with 503 until implemented. Prisma+rawSQL are concrete reviewed design files, not applied migrations.

No legal compliance certification, payment credentials, cloud accounts, model commercial rights, real user consents or app store products are manufactured by this bundle. Missing resources are listed in docs/05_MODEL_REGISTRY_AND_LICENSES.md and docs/06_ASSETS_AND_UX.md. Complete Phase 1 and document actual evidence before enabling filters.
