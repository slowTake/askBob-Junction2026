# Run `make help` for the list. CI runs `make check`.

LOCAL_ENV = DATABASE_URL=postgresql://bob:bob@postgres:5432/bob VALKEY_URL=redis://valkey:6379/0
# Build and start in the background, then `make smoke` waits (up to SMOKE_TIMEOUT s) for
# the API, a worker, the proxy and the UI. No `--wait`: that would also block on vision,
# which the app works without. Follow the logs with `make logs`.
UP_FLAGS = --build --detach
SMOKE_TIMEOUT ?= 180

.PHONY: help up up-aiven up-local up-verda up-claude smoke down logs check backend-check vision-check frontend-check size-check scripts-check frontend-image-check runtime-image-check fmt dev-api dev-worker dev-web

help: ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

up: ## Run everything against Aiven (run `source scripts/aiven-env.sh` first)
	@test -n "$$DATABASE_URL" -a -n "$$VALKEY_URL" || { echo "Run: source scripts/aiven-env.sh"; exit 1; }
	docker compose up $(UP_FLAGS)
	@$(MAKE) --no-print-directory smoke

up-aiven: ## Run everything against Aiven: URLs from avn, passwords from your keyring
	bash -c 'source scripts/aiven-env.sh && exec docker compose up $(UP_FLAGS)'
	@$(MAKE) --no-print-directory smoke

up-local: ## Run everything offline with local Postgres + Valkey containers
	$(LOCAL_ENV) docker compose --profile local up $(UP_FLAGS)
	@$(MAKE) --no-print-directory smoke

up-verda: ## Like up-local, but CubiCasa (VISION_URL) and optionally OCR (OCR_URL) run on Verda
	@test -n "$$VISION_URL" || { echo "Run: VISION_URL=http://<verda-ip>:8001 make up-verda"; exit 1; }
	@curl -sf --max-time 10 "$$VISION_URL/health" >/dev/null \
		|| { echo "No vision service answers at $$VISION_URL/health (see docs/verda-setup.md)"; exit 1; }
	@test -z "$$OCR_URL" || curl -sf --max-time 10 "$$OCR_URL/health" >/dev/null \
		|| { echo "No OCR service answers at $$OCR_URL/health (see docs/verda-setup.md)"; exit 1; }
	$(LOCAL_ENV) docker compose --profile local up $(UP_FLAGS) --scale vision=0
	@$(MAKE) --no-print-directory smoke

up-claude: ## Run locally with Claude: key from environment, keyring, or a hidden prompt
	bash -c 'source scripts/claude-env.sh && $(MAKE) up-local'

smoke: ## Check the running stack: API healthy, worker listening, nginx proxies /api, UI served
	SMOKE_TIMEOUT=$(SMOKE_TIMEOUT) scripts/smoke.sh

down: ## Stop all containers
	docker compose --profile local down

logs: ## Follow API and worker logs
	docker compose logs -f backend worker

check: backend-check vision-check frontend-check size-check scripts-check ## Everything CI runs

backend-check: ## Format check, lint, type check, tests
	cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy app eval && uv run pytest -q

vision-check: ## Floor-plan model service: format check, lint, type check, tests
	cd vision && uv run ruff format --check . && uv run ruff check . && uv run mypy app && uv run pytest -q

frontend-check: ## Format check, lint, type check, tests, build
	cd frontend && npm run format:check && npm run lint && npm run typecheck && npm test && npm run build

size-check: ## No source file over 600 lines
	scripts/check-file-size.sh

scripts-check: ## Tests for the helper scripts
	scripts/bulk-issues-test.sh
	scripts/aiven-env-test.sh
	bash scripts/claude-env-test.sh
	scripts/smoke-test.sh

frontend-image-check: ## Frontend image starts without a backend and follows BACKEND_URL (needs Docker; CI runs it)
	scripts/frontend-image-test.sh

runtime-image-check: ## Single-container Runtime image passes smoke against throwaway DBs (needs Docker; CI runs it)
	scripts/runtime-image-test.sh

fmt: ## Auto-format everything
	cd backend && uv run ruff format . && uv run ruff check --fix .
	cd vision && uv run ruff format . && uv run ruff check --fix .
	cd frontend && npm run format

dev-api: ## API with reload, outside Docker (needs DATABASE_URL, VALKEY_URL, DATA_DIR)
	cd backend && uv run uvicorn app.main:app --reload --port 8000

dev-worker: ## Ingest worker outside Docker (needs tesseract installed locally)
	cd backend && uv run python -m app.worker

dev-web: ## Vite dev server on :5173, proxying /api to :8000
	cd frontend && npm run dev
