# 3. Complete actual directory structure

```text
FaceApp-Production-Spec-v2/
|-- apps/
|   |-- api-server/
|   |   |-- Dockerfile
|   |   |-- celery_config.py
|   |   |-- main.py
|   |   +-- requirements.txt
|   |-- inference-engine/
|   |   |-- inference_pipeline.py
|   |   |-- model_adapters.py
|   |   +-- requirements-gpu.txt
|   |-- mobile/
|   |   |-- src/
|   |   |   +-- editor-binding.ts
|   |   |-- App.tsx
|   |   |-- app.json
|   |   |-- babel.config.cjs
|   |   |-- package.json
|   |   +-- tsconfig.json
|   +-- web-admin/
|       |-- app/
|       |   |-- layout.tsx
|       |   +-- page.tsx
|       |-- next-env.d.ts
|       |-- package.json
|       +-- tsconfig.json
|-- assets/
|   |-- backgrounds/
|   |   |-- cool-sky.svg
|   |   |-- cream.svg
|   |   |-- forest.svg
|   |   |-- midnight.svg
|   |   |-- rose-mist.svg
|   |   |-- studio-slate.svg
|   |   |-- studio-violet.svg
|   |   +-- warm-sand.svg
|   |-- brand/
|   |   |-- EXPORT_RECIPE.md
|   |   |-- app-icon-source.svg
|   |   |-- mark.svg
|   |   +-- wordmark.svg
|   |-- demo/
|   |   |-- PROVENANCE.md
|   |   +-- portrait-original.png
|   |-- fonts/
|   |   |-- Inter-variable.ttf
|   |   +-- OFL.txt
|   |-- icons/
|   |   |-- age.svg
|   |   |-- back.svg
|   |   |-- background.svg
|   |   |-- beard.svg
|   |   |-- blur.svg
|   |   |-- brightness.svg
|   |   |-- brush.svg
|   |   |-- camera.svg
|   |   |-- check-circle.svg
|   |   |-- check.svg
|   |   |-- chevron-right.svg
|   |   |-- close.svg
|   |   |-- cloud.svg
|   |   |-- compare.svg
|   |   |-- contrast.svg
|   |   |-- crop.svg
|   |   |-- crown.svg
|   |   |-- dots.svg
|   |   |-- download.svg
|   |   |-- eraser.svg
|   |   |-- eye.svg
|   |   |-- face.svg
|   |   |-- faces.svg
|   |   |-- flip.svg
|   |   |-- folder.svg
|   |   |-- glasses.svg
|   |   |-- hair-color.svg
|   |   |-- hair-volume.svg
|   |   |-- hair.svg
|   |   |-- heart.svg
|   |   |-- help.svg
|   |   |-- history.svg
|   |   |-- image.svg
|   |   |-- info.svg
|   |   |-- layers.svg
|   |   |-- lips.svg
|   |   |-- lock.svg
|   |   |-- magic-wand.svg
|   |   |-- makeup.svg
|   |   |-- menu.svg
|   |   |-- minus.svg
|   |   |-- offline.svg
|   |   |-- plus.svg
|   |   |-- preset.svg
|   |   |-- redo.svg
|   |   |-- refresh.svg
|   |   |-- rotate.svg
|   |   |-- saturation.svg
|   |   |-- save.svg
|   |   |-- settings.svg
|   |   |-- share.svg
|   |   |-- shield.svg
|   |   |-- skin.svg
|   |   |-- sliders.svg
|   |   |-- smile.svg
|   |   |-- sparkle.svg
|   |   |-- star.svg
|   |   |-- temperature.svg
|   |   |-- trash.svg
|   |   |-- undo.svg
|   |   |-- warning.svg
|   |   +-- zoom.svg
|   |-- luts/
|   |   |-- README.md
|   |   |-- balanced-mono.cube
|   |   |-- cool-clean.cube
|   |   |-- muted-film.cube
|   |   +-- soft-warm.cube
|   |-- ASSET_LICENSES.md
|   |-- design-tokens.json
|   +-- filters.json
|-- docs/
|   |-- 01_PRD.md
|   |-- 02_ARCHITECTURE_AND_MATH.md
|   |-- 03_API_AND_DATABASE.md
|   |-- 04_PRIVACY_PURGE.md
|   |-- 05_MODEL_REGISTRY_AND_LICENSES.md
|   |-- 06_ASSETS_AND_UX.md
|   |-- 07_RESEARCH_SOURCES.md
|   |-- DIRECTORY_TREE.md
|   |-- migration_constraints.sql
|   |-- openapi.json
|   |-- openapi.yaml
|   +-- schema.prisma
|-- infra/
|   +-- triton/
|       |-- models/
|       |   +-- face_parser/
|       |       |-- 1/
|       |       |   +-- README.md
|       |       +-- config.pbtxt
|       +-- README.md
|-- packages/
|   +-- shared-types/
|       |-- json-schema/
|       |   |-- AssetReceipt.json
|       |   |-- DeletionReceipt.json
|       |   |-- JobPayload.json
|       |   |-- SafeError.json
|       |   |-- TransformRequest.json
|       |   |-- UploadComplete.json
|       |   |-- UploadGrant.json
|       |   +-- UploadRequest.json
|       |-- index.ts
|       |-- package.json
|       |-- schemas.py
|       +-- tsconfig.json
|-- scripts/
|   |-- generate_contracts.py
|   |-- package_project.py
|   +-- static_check.py
|-- tests/
|   |-- test_contracts.py
|   +-- test_pipeline.py
|-- .env.example
|-- .gitignore
|-- CHATGPT_COLLECTION_PROMPT.md
|-- CLAUDE.md
|-- MANIFEST.json
|-- Makefile
|-- PROJECT_SPECIFICATION.md
|-- README.md
|-- VALIDATION_REPORT.md
|-- docker-compose.yml
|-- model-registry.json
|-- package.json
|-- pyproject.toml
|-- requirements-dev.txt
+-- tsconfig.base.json
```

No model weights are bundled. Native UI/backend integrations are implementation phases; this tree lists real supplied files. Transient dependencies/caches are excluded.
