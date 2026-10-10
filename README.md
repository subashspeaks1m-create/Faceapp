# PortraitLab — FaceApp-like production specification v2

Read [PROJECT_SPECIFICATION.md](PROJECT_SPECIFICATION.md) for the full seven-section deliverable, with complete API/schema/Python/SVG/manifest/Claude source blocks. Read [CLAUDE.md](CLAUDE.md), then tell Claude Code: **Start building Phase 1.** For Claude Projects, upload the Markdown/specification/contracts; use Claude Code/Cowork with access to this extracted folder for actual repository edits. A ZIP is the portable project bundle, not a proprietary Claude project format.

This is a production-oriented specification and tested scaffold, not a finished FaceApp replica. It uses independent working branding. Licensed generative weights and real backend integrations must be added before deployment; do not promise FaceApp's proprietary model quality. Presets are launch requirements and stay disabled until license/benchmark approval.

## Included and verified

- Complete PRD, mathematical architecture, retention/purge/race contracts and primary-source research ledger.
- Executable FastAPI/OpenAPI3.1 contract shell, Pydantic2/TypeScript types, Prisma6 schema + raw SQL constraints.
- Real five-landmark alignment, ONNX detector/parser adapters, dispatcher, deterministic smoothing and source-resolution alpha/Poisson blending. A custom conditional ONNX adapter signature is supplied; model files are not.
- Four required SVGs plus supplementary icons, brand vector sources,8 background SVGs,4 local LUTs, dark UI tokens,12 filter presets, Inter font/license and synthetic portrait/provenance.
- Expo/Next starter workspaces, local Docker infrastructure/config, test/contract-generation commands, master collection prompt and phased CLAUDE.md.

## Bootstrap

Current implementation status, commands run and blockers live in [PROGRESS.md](PROGRESS.md). Architecture decisions are in [docs/adr](docs/adr).

```sh
make python-env          # Python 3.12 venv from requirements-dev.lock (needs uv)
npm ci                   # JS workspaces from package-lock.json
make test                # unit/contract tests; integration tests skip without services
make lint
npm run build --workspaces
```

Backend with local services (PostgreSQL, Redis, SeaweedFS S3): follow "Startup" in PROGRESS.md. `make test` runs the 25 integration tests when `PORTRAITLAB_TEST_DATABASE_URL` and `PORTRAITLAB_TEST_S3_*` are set. With no approved detector in `model-registry.json`, upload finalization returns 503 `DETECTOR_UNAVAILABLE` and every filter returns `FILTER_UNAVAILABLE`; nothing is simulated.

`make dev-mobile` uses a custom Expo development build; VisionCamera is not available merely by opening Expo Go. `make dev-web` starts Next. Expo 53/Reanimated 3 is the requested legacy compatibility track; see PROGRESS.md for its open npm advisories.

## Handoff

CHATGPT_COLLECTION_PROMPT.md is the exhaustive research/assets prompt. CLAUDE.md is the implementation instruction file. docs/ holds individual specifications and real contracts; apps/ and packages/ hold code; assets/ contains actual files. MANIFEST.json lists SHA256/bytes for every deliverable except its own manifest. Sources synced from the ChatGPT project were read-only and untouched.
