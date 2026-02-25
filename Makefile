.PHONY: help install sync dev-all dev-backend dev-rag dev-frontend \
	docker-up docker-down docker-down-safe docker-logs docker-reset-dangerous db-backup \
       db-migrate db-upgrade db-seed \
       lint format test test-backend test-rag test-frontend clean

POSTGRES_USER ?= exam_prep
POSTGRES_DB ?= exam_prep
BACKUP_DIR ?= backups

# ── Meta ──────────────────────────────────────────────────────────────────────

help:
	@echo "E-exam-prepare Development Commands (uv)"
	@echo "=========================================="
	@echo ""
	@echo "Setup:"
	@echo "  make install          Install all deps (uv sync + npm install)"
	@echo "  make sync             uv sync only (Python)"
	@echo ""
	@echo "Development:"
	@echo "  make dev-all          Run frontend + backend + rag concurrently"
	@echo "  make dev-backend      Run backend only"
	@echo "  make dev-rag          Run RAG service only"
	@echo "  make dev-frontend     Run frontend only"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up        Start all services with Docker Compose"
	@echo "  make docker-down      Stop all services (safe, keeps volumes)"
	@echo "  make docker-down-safe Safe stop (no volume deletion)"
	@echo "  make db-backup        Backup PostgreSQL to backups/*.sql"
	@echo "  make docker-reset-dangerous  DANGER: backup + destroy volumes"
	@echo "  make docker-logs      Tail service logs"
	@echo ""
	@echo "Database:"
	@echo "  make db-migrate MSG=… Create a new Alembic migration"
	@echo "  make db-upgrade       Run all pending migrations"
	@echo "  make db-seed          Seed sample data"
	@echo ""
	@echo "Quality:"
	@echo "  make lint             Ruff check (backend + rag-service)"
	@echo "  make format           Ruff format"
	@echo "  make test             Run all tests"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean            Remove caches and build artefacts"

# ── Setup ─────────────────────────────────────────────────────────────────────

install: sync
	cd frontend && npm install

sync:
	uv sync --all-packages

# ── Dev servers ───────────────────────────────────────────────────────────────

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

# NOTE: Must use --app-dir (or cd into rag-service/) to avoid name collision
# with backend/app/ — both packages are named 'app' in the uv workspace.
dev-rag:
	uv run uvicorn app.main:app --app-dir rag-service --reload --port 8001

dev-frontend:
	cd frontend && npm run dev

dev-all:
	@echo "Starting all services in parallel…"
	$(MAKE) -j3 dev-backend dev-rag dev-frontend

# ── Docker ────────────────────────────────────────────────────────────────────

docker-up:
	docker compose down --remove-orphans
	docker compose up -d
	@echo "✅ Services started"
	@echo "  Frontend:  http://localhost:3000"
	@echo "  Backend:   http://localhost:8000/docs"
	@echo "  RAG:       http://localhost:8001/docs"

docker-down:
	$(MAKE) docker-down-safe

docker-down-safe:
	docker compose down

docker-logs:
	docker compose logs -f

db-backup:
	@mkdir -p $(BACKUP_DIR)
	@if ! docker compose ps postgres | grep -q "Up"; then \
		echo "Starting postgres for backup..."; \
		docker compose up -d postgres; \
		sleep 3; \
	fi
	@backup_file="$(BACKUP_DIR)/postgres_$(shell date +%Y%m%d_%H%M%S).sql"; \
	docker compose exec -T postgres pg_dump -U $(POSTGRES_USER) -d $(POSTGRES_DB) > $$backup_file; \
	echo "✅ PostgreSQL backup created: $$backup_file"

docker-reset-dangerous:
	@echo "⚠️  DANGER: This will permanently delete Docker volumes (including PostgreSQL data)."
	@echo "A PostgreSQL backup will be created first."
	@printf "Type RESET to continue: "; \
	read ans; \
	if [ "$$ans" != "RESET" ]; then \
		echo "Aborted."; \
		exit 1; \
	fi
	@$(MAKE) db-backup
	docker compose down -v --remove-orphans
	@echo "✅ Destructive reset completed. Volumes removed after backup."

# ── Database ──────────────────────────────────────────────────────────────────

MSG ?= auto

db-migrate:
	cd backend && uv run alembic revision --autogenerate -m "$(MSG)"

db-upgrade:
	cd backend && uv run alembic upgrade head

db-seed:
	cd backend && uv run python -m scripts.seed

# ── Quality ───────────────────────────────────────────────────────────────────

lint:
	uv run ruff check backend/ rag-service/

format:
	uv run ruff format backend/ rag-service/

test: test-backend test-rag test-frontend

test-backend:
	cd backend && uv run pytest -v

test-rag:
	cd rag-service && uv run pytest -v

test-frontend:
	cd frontend && npm test -- --passWithNoTests

# ── Cleanup ───────────────────────────────────────────────────────────────────

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name .DS_Store -delete 2>/dev/null || true
	@echo "✅ Clean"
