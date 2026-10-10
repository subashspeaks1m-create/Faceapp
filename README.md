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

Use Python3.12 and a Node version supported by the selected web/Expo packages. Create a virtual environment, install requirements-dev.txt, then install JavaScript workspaces and freeze lockfiles only after compatibility checks:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
npm install
make contracts
npm run test
npm run lint
npm run build
cp .env.example .env
npm run docker:up
npm run dev
```

`make dev-mobile` uses a custom Expo development build; VisionCamera is not available merely by opening Expo Go. `make dev-web` starts Next. Set local-only credentials in .env; never commit real secrets. Docker starts PostgreSQL/Redis/MinIO/API shell, not a running commercial inference service. Initialize a private ephemeral bucket and implement Runtime/repositories/worker/purge before a real user flow. /health and /openapi.json are available; unconfigured portrait routes return503. See VALIDATION_REPORT.md for actual checks, not inferred passes.

Expo53/Reanimated3 is the requested legacy compatibility track. Web uses Next16.4/React19.3 bootstrap candidates researched2026-10-10. Recheck official security and store requirements, freeze supported versions and image digests, then run device/GPU/DB/deletion tests. None of those integration builds is claimed as verified here.

## Handoff

CHATGPT_COLLECTION_PROMPT.md is the exhaustive research/assets prompt. CLAUDE.md is the implementation instruction file. docs/ holds individual specifications and real contracts; apps/ and packages/ hold code; assets/ contains actual files. MANIFEST.json lists SHA256/bytes for every deliverable except its own manifest. Sources synced from the ChatGPT project were read-only and untouched.
