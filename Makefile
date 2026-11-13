# Run `make help` for the list. CI runs `make check`.

LOCAL_ENV = DATABASE_URL=postgresql://bob:bob@postgres:5432/bob VALKEY_URL=redis://valkey:6379/0

.PHONY: help up up-local down logs check backend-check frontend-check size-check fmt dev-api dev-worker dev-web

help: ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

up: ## Run everything against Aiven (run `source scripts/aiven-env.sh` first)
	@test -n "$$DATABASE_URL" -a -n "$$VALKEY_URL" || { echo "Run: source scripts/aiven-env.sh"; exit 1; }
	docker compose up --build

up-local: ## Run everything offline with local Postgres + Valkey containers
	$(LOCAL_ENV) docker compose --profile local up --build

down: ## Stop all containers
	docker compose --profile local down

logs: ## Follow API and worker logs
	docker compose logs -f backend worker

check: backend-check frontend-check size-check ## Everything CI runs

backend-check: ## Format check, lint, type check, tests
	cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy app eval && uv run pytest -q

frontend-check: ## Format check, lint, type check, tests, build
	cd frontend && npm run format:check && npm run lint && npm run typecheck && npm test && npm run build

size-check: ## No source file over 600 lines
	scripts/check-file-size.sh

fmt: ## Auto-format everything
	cd backend && uv run ruff format . && uv run ruff check --fix .
	cd frontend && npm run format

dev-api: ## API with reload, outside Docker (needs DATABASE_URL, VALKEY_URL, DATA_DIR)
	cd backend && uv run uvicorn app.main:app --reload --port 8000

dev-worker: ## Ingest worker outside Docker (needs tesseract installed locally)
	cd backend && uv run python -m app.worker

dev-web: ## Vite dev server on :5173, proxying /api to :8000
	cd frontend && npm run dev
