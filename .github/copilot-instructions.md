# Angie — Copilot Instructions

## Build & Dev Commands

```bash
make install          # Install all deps (uv sync --dev --all-extras)
make check            # Lint + format check (no changes)
make fix              # Auto-fix lint + format
make test             # Run all tests
make test-single K=test_name  # Run one test by keyword
make test-cov         # Tests with coverage
make migrate          # Run DB migrations (alembic upgrade head)
make migrate-new MSG="description"  # Generate new migration
make docker-up        # Start all services
make docker-down      # Stop all services
make docker-build     # Rebuild images
make build            # Build angie CLI binary (PyInstaller)
```

> **Important:** `uv run pytest` picks up the system Python. Always use `.venv/bin/pytest` or `make test`.

Run API locally (no Docker):

```bash
uv run uvicorn angie.api.app:app --reload
```

Run daemon locally:

```bash
uv run python -m angie.main
```

Run Celery worker:

```bash
uv run celery -A angie.queue.celery_app worker --loglevel=info
```

## Architecture

Angie is an **event-driven, always-on daemon** that orchestrates a fleet of specialized agents.

### Event Flow

```
Channel (Slack/Discord/iMessage/Email/Web)
  → AngieEvent
  → EventRouter.dispatch()
  → TaskDispatcher
  → Celery Queue
  → Worker → AgentRegistry.resolve() → BaseAgent.execute()
  → FeedbackManager → Channel (notify user)
```

### Key Concepts

- **AngieEvent** (`src/angie/core/events.py`): Everything entering the system is an event. Types: `USER_MESSAGE`, `CRON`, `WEBHOOK`, `TASK_COMPLETE`, `TASK_FAILED`, `SYSTEM`, `CHANNEL_MESSAGE`, `API_CALL`.
- **AngieTask** (`src/angie/core/tasks.py`): A unit of work created from an event. Enqueued via Celery.
- **BaseAgent** (`src/angie/agents/base.py`): All agents extend this. Must implement `execute(task)`. Declare `name`, `slug`, `description`, `capabilities` as `ClassVar`.
- **AgentRegistry** (`src/angie/agents/registry.py`): Auto-discovers agents from `AGENT_MODULES`. Use `registry.get(slug)` or `registry.resolve(task)`.
- **Team**: Named group of agents collaborating on a goal.
- **Workflow**: Ordered steps across agents/teams. Executed by `WorkflowExecutor` (`src/angie/core/workflows.py`).
- **Prompt Hierarchy**: `SYSTEM_PROMPT → ANGIE_PROMPT → AGENT_PROMPT` (agent tasks) or `SYSTEM_PROMPT → ANGIE_PROMPT → USER_PROMPTS` (user interactions). Managed by `PromptManager` (`src/angie/core/prompts.py`). Templates live in `prompts/`, user prompts in `prompts/user/{user_id}/*.md`.

### Services (Docker Compose)

| Service    | Port | Purpose                  |
| ---------- | ---- | ------------------------ |
| `api`      | 8000 | FastAPI REST + WebSocket |
| `worker`   | —    | Celery task workers      |
| `daemon`   | —    | Angie event loop         |
| `frontend` | 3000 | Next.js web UI           |
| `mysql`    | 3306 | Primary database         |
| `redis`    | 6379 | Cache + Celery broker    |

### Directory Layout

```
src/angie/
├── main.py              # Daemon entry point
├── config.py            # pydantic-settings (all config via env vars)
├── core/
│   ├── events.py        # AngieEvent, EventRouter
│   ├── tasks.py         # AngieTask, TaskDispatcher
│   ├── loop.py          # AngieLoop daemon
│   ├── prompts.py       # PromptManager (Jinja2)
│   ├── workflows.py     # WorkflowExecutor
│   ├── cron.py          # APScheduler cron engine
│   └── feedback.py      # FeedbackManager
├── models/              # SQLAlchemy 2.0 models (all async)
├── db/
│   ├── session.py       # Async engine, get_session() FastAPI dep
│   └── repository.py    # Generic CRUD base
├── cache/redis.py       # Redis helpers, @cached decorator
├── queue/
│   ├── celery_app.py    # Celery config
│   └── workers.py       # execute_task, execute_workflow Celery tasks
├── agents/
│   ├── base.py          # BaseAgent (abstract)
│   ├── registry.py      # AgentRegistry, @agent decorator
│   ├── system/          # cron, task_manager, workflow_manager, event_manager
│   ├── email/           # gmail, outlook, yahoo, spam, correspondence
│   ├── calendar/        # gcal
│   ├── smart_home/      # hue, home_assistant
│   ├── networking/      # ubiquiti
│   ├── media/           # spotify
│   └── dev/             # github
├── channels/
│   ├── base.py          # BaseChannel, ChannelManager
│   ├── slack.py         # Slack (slack-sdk)
│   ├── discord.py       # Discord (discord.py)
│   ├── imessage.py      # iMessage (BlueBubbles REST API)
│   ├── email.py         # Email (SMTP/IMAP)
│   └── web_chat.py      # WebSocket web chat
├── api/
│   ├── app.py           # FastAPI app factory
│   ├── auth.py          # JWT, bcrypt, OAuth2
│   └── routers/         # auth, users, agents, teams, workflows, tasks, events, prompts, chat
└── cli/                 # Click CLI
    ├── main.py          # Entry point (angie command)
    ├── setup.py         # angie setup (onboarding)
    ├── chat.py          # angie ask "..."
    ├── config.py        # angie config slack|discord|imessage|email
    ├── status.py        # angie status
    └── prompts.py       # angie prompts list|edit|reset
```

## Key Conventions

### Adding a New Agent

1. Create `src/angie/agents/<category>/<slug>.py`
1. Extend `BaseAgent`, declare `name`, `slug`, `description`, `capabilities` as `ClassVar[str]`/`ClassVar[list[str]]`
1. Implement `async def execute(self, task: dict[str, Any]) -> dict[str, Any]`
1. Add the module path to `AGENT_MODULES` in `src/angie/agents/registry.py`

### Configuration

All config is via environment variables / `.env` file using pydantic-settings. Never hardcode secrets. See `.env.example` for all options. Access via `from angie.config import get_settings; settings = get_settings()`.

### Database

- All models live in `src/angie/models/`. Import from `angie.db.session.Base`.
- Use `TimestampMixin` from `angie.models.base` for `created_at`/`updated_at`.
- IDs are UUID strings: use `new_uuid` default.
- Always use async SQLAlchemy sessions. FastAPI dep: `Depends(get_session)`.
- After changing models: `make migrate-new MSG="description"` then `make migrate`.

### API Patterns

- All routes require JWT auth via `Depends(get_current_user)`.
- Pydantic response models use `model_config = {"from_attributes": True}`.
- Router prefix: `/api/v1/<resource>`.

### Prompt Hierarchy

- `prompts/system.md` — global system rules (Angie's core identity)
- `prompts/angie.md` — Angie's personality and behavior
- `prompts/agents/<slug>.md` — per-agent context (optional)
- `prompts/user/<user_id>/*.md` — generated during `angie setup`, user-specific context

### iMessage

Uses [BlueBubbles](https://bluebubbles.app/) REST API. Requires BlueBubbles Server running on macOS. **Not containerized.** Configure with `angie config imessage`.

### Tech Stack

- **Python 3.12+**, managed with `uv`
- **pydantic-ai** — agent schemas, tools, structured LLM I/O
- **github-copilot-sdk** — LLM engine (sessions, streaming, model selection)
- **FastAPI** — async REST API
- **SQLAlchemy 2.0** async + **Alembic** — database ORM and migrations
- **MySQL 8** — primary database
- **Redis** — cache + Celery broker
- **Celery** — async task queue
- **Next.js** — React frontend
- **Click + Rich** — CLI
- **APScheduler** — cron engine
- **Ruff** — linting and formatting
- **pytest** — testing
