PYTHON ?= .venv/bin/python
SHARED := $(CURDIR)/packages/shared-types
API := $(CURDIR)/apps/api-server
PYPATH := PYTHONPATH=$(SHARED):$(API)
.PHONY: build test test-integration dev lint docker-up dev-mobile dev-web contracts migrate python-env daemons worker test-style-api dev-style-api style-catalog
python-env:
	uv venv --python 3.12 .venv && uv pip sync --python $(PYTHON) requirements-dev.lock
build: contracts
	$(PYTHON) scripts/static_check.py
	npm run build --workspace=@portraitlab/shared-types
	npm run build --workspace=@portraitlab/mobile
	npm run build --workspace=@portraitlab/web-admin
# Unit/contract tests always run; integration tests skip unless PORTRAITLAB_TEST_* is set.
test: test-style-api
	$(PYPATH) $(PYTHON) -m unittest discover -s tests -v
	npm test --workspace=@portraitlab/mobile
# Style API unit/integration tests (mocked provider). The live OpenAI test skips unless STYLE_API_LIVE=1.
test-style-api:
	cd apps/style-api && ../../$(PYTHON) -m unittest discover -s tests -t . -v
	cd apps/style-api && ../../$(PYTHON) scripts/export_public_catalog.py --check
# Regenerate the app's public copy of the style catalog after editing apps/style-api/styleapi/catalog.json.
style-catalog:
	cd apps/style-api && ../../$(PYTHON) scripts/export_public_catalog.py
# Local style API. Export its variables first (see apps/style-api/.env.example and docs/DEPLOYMENT_BACKEND.md).
dev-style-api:
	cd apps/style-api && ../../.venv/bin/python -m uvicorn api.index:app --reload --port 8790
test-integration:
	@test -n "$$PORTRAITLAB_TEST_DATABASE_URL" || (echo "Set PORTRAITLAB_TEST_DATABASE_URL and PORTRAITLAB_TEST_S3_*" && exit 1)
	$(PYPATH) $(PYTHON) -m unittest tests.test_runtime_integration -v
dev:
	cd apps/api-server && $(PYPATH) ../../.venv/bin/python -m uvicorn main:app --reload --port 8000
migrate:
	$(PYPATH) $(PYTHON) -m portraitlab.service migrate
daemons:
	$(PYPATH) $(PYTHON) -m portraitlab.service daemons
worker:
	cd apps/api-server && $(PYPATH) ../../.venv/bin/celery -A portraitlab.tasks worker --loglevel=INFO
dev-mobile:
	npm run dev --workspace=@portraitlab/mobile
dev-web:
	npm run dev --workspace=@portraitlab/web-admin
lint:
	$(PYTHON) -m ruff check apps/inference-engine apps/api-server apps/style-api packages/shared-types scripts tests
	npm run lint --workspaces
docker-up:
	docker compose --env-file .env up --build -d
contracts:
	$(PYPATH) $(PYTHON) scripts/generate_contracts.py
