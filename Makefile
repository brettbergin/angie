.DEFAULT_GOAL := help
PYTHON       := .venv/bin/python
UV           := uv
PYTEST       := .venv/bin/pytest
RUFF         := .venv/bin/ruff

.PHONY: help install lint lint-fix format format-fix check fix test test-frontend test-backend test-single \
        lint-frontend lint-frontend-fix format-frontend format-frontend-fix \
        build docker-build docker-up docker-down docker-restart docker-logs migrate clean \
        docker-restart-api docker-restart-worker docker-restart-daemon docker-restart-frontend \
        docker-restart-mysql docker-restart-redis

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies (including dev)
	$(UV) sync --extra dev

lint: ## Run ruff linter on Python (check only)
	$(RUFF) check src/ tests/

lint-fix: ## Run ruff linter on Python and auto-fix
	$(RUFF) check --fix src/ tests/

format: ## Check Python formatting with ruff
	$(RUFF) format --check src/ tests/

format-fix: ## Auto-format Python with ruff
	$(RUFF) format src/ tests/

lint-frontend: ## Run ESLint on frontend
	cd frontend && npx next lint

lint-frontend-fix: ## Run ESLint on frontend with auto-fix
	cd frontend && npx next lint --fix

format-frontend: ## Check frontend formatting with Prettier
	cd frontend && npx prettier --check "src/**/*.{ts,tsx,js,jsx,css,json}"

format-frontend-fix: ## Auto-format frontend with Prettier
	cd frontend && npx prettier --write "src/**/*.{ts,tsx,js,jsx,css,json}"

check: lint format lint-frontend format-frontend ## Run all checks (lint + format)

fix: lint-fix format-fix lint-frontend-fix format-frontend-fix ## Auto-fix all lint and format issues

typecheck: ## Run mypy type checks
	$(UV) run mypy src/

test: ## Run all tests (backend + frontend)
	$(PYTEST) tests/ -v
	cd frontend && npx vitest run

test-frontend: ## Run frontend unit tests only
	cd frontend && npx vitest run

test-backend: ## Run backend tests only
	$(PYTEST) tests/ -v

test-single: ## Run a single test by keyword: make test-single K=test_name
	$(PYTEST) tests/ -v -k "$(K)"

test-cov: ## Run tests with coverage report
	$(PYTEST) tests/ --cov=src/angie --cov-report=term-missing -v

build: ## Build the angie CLI binary with PyInstaller
	$(UV) run pyinstaller angie.spec

migrate: ## Run Alembic database migrations
	$(UV) run alembic upgrade head

migrate-new: ## Create a new Alembic migration: make migrate-new MSG="description"
	$(UV) run alembic revision --autogenerate -m "$(MSG)"

docker-build: ## Build all Docker images
	docker compose build

docker-up: ## Start all services with Docker Compose
	docker compose up -d

docker-down: ## Stop all services
	docker compose down

docker-restart: ## Rebuild images and restart all services
	docker compose down && docker compose build && docker compose up -d

docker-restart-api: ## Rebuild and restart the API service
	docker compose up -d --build api

docker-restart-worker: ## Rebuild and restart the Worker service
	docker compose up -d --build worker

docker-restart-daemon: ## Rebuild and restart the Daemon service
	docker compose up -d --build daemon

docker-restart-frontend: ## Rebuild and restart the Frontend service
	docker compose up -d --build frontend

docker-restart-mysql: ## Restart the MySQL service
	docker compose up -d --build mysql

docker-restart-redis: ## Restart the Redis service
	docker compose up -d --build redis

docker-logs: ## Tail logs from all services
	docker compose logs -f

docker-reset: ## Stop services and remove volumes (destructive!)
	docker compose down -v

