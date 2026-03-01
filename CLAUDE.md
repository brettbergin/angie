# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Dev Commands

```bash
make install                    # uv sync --dev --all-extras
make check                      # lint + format check (no changes)
make fix                        # auto-fix lint + format
make test                       # all tests (.venv/bin/pytest tests/ -v)
make test-single K=test_name    # single test by keyword
make test-cov                   # tests with coverage
make md-check                   # check markdown formatting (mdformat)
make md-fix                     # auto-format markdown
make migrate                    # alembic upgrade head
make migrate-new MSG="desc"     # generate new migration
make docker-up / docker-down    # start/stop MySQL + Redis
make build                      # PyInstaller binary → dist/angie
make dist                       # sdist + wheel → dist/
```

Always use `.venv/bin/pytest` or `make test` — `uv run pytest` may pick up the wrong Python.

Run services locally (no Docker, but needs MySQL + Redis running):

```bash
uv run uvicorn angie.api.app:app --reload          # API on :8000
uv run celery -A angie.queue.celery_app worker -l info  # Worker
uv run python -m angie.main                         # Daemon
cd frontend && npm run dev                           # UI on :3000
```

## Architecture

Angie is an event-driven daemon that routes messages through a fleet of pydantic-ai agents.

### Event Flow

```
Channel (Slack/Discord/iMessage/Email/WebSocket)
  → AngieEvent (core/events.py)
  → EventRouter.dispatch()
  → AngieTask (core/tasks.py)
  → Celery queue (queue/workers.py)
  → AgentRegistry.resolve() → BaseAgent.execute()
  → FeedbackManager (core/feedback.py) → reply to originating channel
```

### Agent Routing

`AgentRegistry.resolve(task)` uses a two-phase approach:

1. **Confidence scoring** — each agent's `confidence(task)` returns 0.0–1.0 based on slug match and capability keywords
1. **LLM fallback** — if no agent scores ≥0.5, the registry asks the LLM to pick from the roster

### Prompt Hierarchy

Three-tier composition via `PromptManager` (core/prompts.py) with Jinja2 templates from `prompts/`:

- Agent tasks: `system.md → angie.md → agents/{slug}.md + agent.instructions`
- User chat: `system.md → angie.md → user prompts from DB`

### Current Agents (AGENT_MODULES in agents/registry.py)

| Slug               | Category     | Module                              |
| ------------------ | ------------ | ----------------------------------- |
| `cron`             | System       | `agents/system/cron.py`             |
| `task-manager`     | System       | `agents/system/task_manager.py`     |
| `workflow-manager` | System       | `agents/system/workflow_manager.py` |
| `event-manager`    | System       | `agents/system/event_manager.py`    |
| `github`           | Dev          | `agents/dev/github.py`              |
| `software-dev`     | Dev          | `agents/dev/software_dev.py`        |
| `web`              | Productivity | `agents/productivity/web.py`        |
| `weather`          | Lifestyle    | `agents/lifestyle/weather.py`       |

### Adding a New Agent

1. Create `src/angie/agents/<category>/<slug>.py`
1. Extend `BaseAgent`, declare ClassVars: `name`, `slug`, `description`, `capabilities`, `category`, `instructions`
1. Implement `build_pydantic_agent()` (register `@agent.tool` functions) and `async execute(self, task: dict) -> dict`
1. Add module path to `AGENT_MODULES` in `src/angie/agents/registry.py`

LLM model is injected at runtime via `get_llm_model()` — never stored on the agent. Credentials loaded via `self.get_credentials(user_id, service_type)` with env var fallback.

## Key Conventions

- **Config**: all via env vars / `.env` using pydantic-settings (`from angie.config import get_settings`)
- **Database**: SQLAlchemy 2.0 async, MySQL 8. Models in `src/angie/models/`. Use `TimestampMixin`, UUID string PKs via `new_uuid`. FastAPI dep: `Depends(get_session)`
- **API routes**: JWT auth via `Depends(get_current_user)`, prefix `/api/v1/<resource>`, Pydantic response models with `from_attributes=True`
- **LLM providers**: set `LLM_PROVIDER` env var to `github` (default), `openai`, or `anthropic`
- **Channels**: conditionally registered based on env vars. Health-checked every 10s with auto-reconnect
- **Workers**: `reset_engine()` called in Celery workers to get fresh DB connections after fork. Max 3 retries with exponential backoff
- **Frontend**: Next.js 15 App Router, TypeScript, Tailwind. WebSocket for chat at `NEXT_PUBLIC_WS_URL`. REST client in `frontend/src/lib/api.ts`
- **PyPI package name**: `angie-ai`

## CI/CD

Individual workflow files in `.github/workflows/`:

- Backend: lint, format, test (3.12 + 3.13 matrix), security (bandit)
- Frontend: lint, format, typecheck, test, build, security (npm audit)
- Docs: mdformat
- Docker build (push to main only)
- Deploy (`deploy.yml`): triggers on `v*.*.*` tags → PyInstaller binary + GitHub Release + PyPI publish
