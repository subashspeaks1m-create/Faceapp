PYTHON ?= .venv/bin/python
SHARED := $(CURDIR)/packages/shared-types
.PHONY: build test dev lint docker-up dev-mobile dev-web contracts
build: contracts
	$(PYTHON) scripts/static_check.py
	npm run build --workspace=@portraitlab/shared-types
	npm run build --workspace=@portraitlab/mobile
	npm run build --workspace=@portraitlab/web-admin
test:
	PYTHONPATH=$(SHARED) $(PYTHON) -m unittest discover -s tests -v
dev:
	cd apps/api-server && PYTHONPATH=$(SHARED) ../../.venv/bin/python -m uvicorn main:app --reload --port 8000
dev-mobile:
	npm run dev --workspace=@portraitlab/mobile
dev-web:
	npm run dev --workspace=@portraitlab/web-admin
lint:
	$(PYTHON) -m ruff check apps/inference-engine apps/api-server packages/shared-types scripts tests
	npm run lint --workspaces
docker-up:
	docker compose --env-file .env up --build -d
contracts:
	PYTHONPATH=$(SHARED) $(PYTHON) scripts/generate_contracts.py
