.DEFAULT_GOAL := help
PYTHON       := .venv/bin/python
UV           := uv
PYTEST       := .venv/bin/pytest
RUFF         := .venv/bin/ruff

.PHONY: help install lint lint-fix format format-fix check fix test test-single \
        build docker-build docker-up docker-down docker-logs migrate clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies (including dev)
	$(UV) sync --dev --all-extras

lint: ## Run ruff linter (check only)
	$(RUFF) check src/ tests/

lint-fix: ## Run ruff linter and auto-fix
	$(RUFF) check --fix src/ tests/

format: ## Check formatting with ruff
	$(RUFF) format --check src/ tests/

format-fix: ## Auto-format with ruff
	$(RUFF) format src/ tests/

check: lint format ## Run all checks (lint + format)

fix: lint-fix format-fix ## Auto-fix all lint and format issues

typecheck: ## Run mypy type checks
	$(UV) run mypy src/

test: ## Run all tests
	$(PYTEST) tests/ -v

test-single: ## Run a single test by keyword: make test-single K=test_name
	$(PYTEST) tests/ -v -k "$(K)"

test-cov: ## Run tests with coverage report
	$(PYTEST) tests/ --cov=src/angie --cov-report=term-missing -v

build: ## Build the angie CLI binary with PyInstaller
	$(UV) run pyinstaller --onefile --name angie \
		--add-data "prompts:prompts" \
		src/angie/cli/main.py

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

docker-logs: ## Tail logs from all services
	docker compose logs -f

docker-reset: ## Stop services and remove volumes (destructive!)
	docker compose down -v

build: ## Build angie CLI binary with PyInstaller
	$(UV) run pyinstaller --onefile --name angie \
		--add-data "prompts:prompts" \
		src/angie/cli/main.py
