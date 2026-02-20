# Angie — Personal AI Assistant

> Your 24/7 personal AI assistant. Always on. Always working.

Angie is an event-driven, agent-orchestrated personal AI assistant that runs as a background daemon. She monitors queues, executes scheduled tasks, routes conversations from Slack/Discord/iMessage/Email to the right agent, and keeps you informed. She never does more than asked, always acts with positive intent, and grows smarter the more you tell her about yourself.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                          Channels                               │
│          Slack · Discord · iMessage · Email · Web Chat          │
└───────────────────────────┬─────────────────────────────────────┘
                            │ events
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Angie Daemon Loop                         │
│   EventRouter  →  TaskDispatcher  →  Celery Queue  →  Worker   │
│          ↑                                  ↑                   │
│     CronEngine                       AgentRegistry              │
└─────────────────────────────────────────────────────────────────┘
                            │ resolved agents / teams
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Agent Fleet                             │
│  System: cron · task-manager · workflow-manager · event-manager │
│  Email: gmail · outlook · yahoo · spam · correspondence         │
│  Calendar: gcal   Media: spotify   Dev: github                  │
│  Smart Home: hue · home-assistant   Networking: ubiquiti        │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌───────────────────┐   ┌───────────┐   ┌───────────────────────┐
│   FastAPI (API)   │   │   MySQL   │   │    Redis (cache+queue) │
│  /api/v1/*        │   │ 9 tables  │   │   Celery broker        │
└───────────────────┘   └───────────┘   └───────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              Next.js Web UI  (frontend/)                        │
│  Dashboard · Agents · Teams · Workflows · Tasks · Events        │
│  Real-time Chat · Settings                                      │
└─────────────────────────────────────────────────────────────────┘
```

### Key Concepts

| Concept | Description |
|---|---|
| **Event** | Any trigger: user message, cron tick, webhook, task completion |
| **Task** | A unit of work dispatched from an event to an agent |
| **Agent** | A pydantic-ai powered worker that can handle specific task types |
| **Team** | A named group of agents that collaborate on related tasks |
| **Workflow** | An ordered sequence of steps across agents/teams for a goal |
| **Prompt Hierarchy** | `SYSTEM → ANGIE → AGENT/USER` — layered context fed to every LLM call |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12, uv |
| AI framework | pydantic-ai + github-copilot-sdk |
| API | FastAPI + SQLAlchemy 2.0 async |
| Database | MySQL 8 (aiomysql driver) |
| Cache / Queue | Redis + Celery |
| Scheduler | APScheduler |
| Channels | Slack SDK · discord.py · BlueBubbles REST · SMTP/IMAP |
| CLI | Click |
| Frontend | Next.js 15 · TypeScript · Tailwind CSS v3 |
| Build | PyInstaller (standalone `angie` binary) |
| CI/CD | GitHub Actions |
| Dev | Docker Compose, Ruff, pytest |

---

## Quick Start

### Prerequisites

- Python 3.12+, [uv](https://docs.astral.sh/uv/)
- Docker Desktop (for MySQL + Redis)
- Node.js 20+ (for frontend)

### 1. Clone and install

```bash
git clone https://github.com/your-org/angie.git
cd angie
make install          # uv sync --dev --all-extras
cp .env.example .env  # fill in SECRET_KEY, DB_PASSWORD, GITHUB_TOKEN
```

### 2. Start backing services

```bash
make docker-up        # starts MySQL + Redis containers
make migrate          # runs Alembic migrations
```

### 3. Run Angie

```bash
# Start the daemon (background loop + Celery worker)
angie daemon start

# Or start services individually:
uvicorn angie.api.app:create_app --factory --reload   # API on :8000
celery -A angie.queue.celery_app worker -l info       # Worker

# Frontend dev server:
cd frontend && npm run dev    # UI on :3000
```

### 4. Onboarding

On first run, Angie needs to learn about you:

```bash
angie setup
```

This asks a series of questions and generates personalized `prompts/user/<id>/` markdown files that become part of every LLM interaction.

---

## CLI Reference

```bash
angie --help

# Daemon
angie daemon start          # Start background daemon
angie daemon stop
angie daemon status

# One-shot queries
angie ask "What's on my calendar today?"

# Configuration
angie config slack           # Set Slack bot token
angie config discord         # Set Discord bot token
angie config imessage        # Set BlueBubbles URL
angie config email           # Set SMTP/IMAP credentials

# Prompt management
angie prompts list           # Show all active prompts
angie prompts edit           # Open prompt in $EDITOR
angie prompts reset          # Re-run onboarding for a prompt

# Status
angie status                 # Show active tasks, registered agents
```

---

## Agent Fleet

Agents are pydantic-ai powered workers. Each declares:
- `slug` — unique identifier used for routing
- `capabilities` — keywords that trigger auto-selection
- `execute(task)` — async method that does the work

### Built-in Agents

| Slug | Category | Description |
|---|---|---|
| `cron-manager` | System | Create, list, delete cron jobs |
| `task-manager` | System | Manage task queue and status |
| `workflow-manager` | System | Trigger and monitor workflows |
| `event-manager` | System | Inspect and replay events |
| `gmail-agent` | Email | Gmail read/send/search |
| `outlook-agent` | Email | Office 365 mail |
| `yahoo-agent` | Email | Yahoo Mail |
| `spam-deletion` | Email | Delete spam across providers |
| `correspondence` | Email | Draft and send replies |
| `gcal-agent` | Calendar | Google Calendar CRUD |
| `spotify-agent` | Media | Playback control, playlists |
| `github-agent` | Dev | Issues, PRs, repos |
| `hue-agent` | Smart Home | Philips Hue lighting |
| `home-assistant` | Smart Home | Home Assistant integration |
| `ubiquiti-agent` | Networking | UniFi network management |

### Adding a New Agent

```python
# src/angie/agents/my_category/my_agent.py
from angie.agents.base import BaseAgent

class MyAgent(BaseAgent):
    name = "My Agent"
    slug = "my-agent"
    description = "Does something useful"
    capabilities = ["useful", "something"]

    async def execute(self, task: dict) -> dict:
        # Use the underlying SDK / API here
        return {"status": "success", "result": "done"}
```

Then add to `AGENT_MODULES` in `src/angie/agents/registry.py`.

---

## Teams & Workflows

### Creating a Team (API)

```bash
curl -X POST http://localhost:8000/api/v1/teams/ \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"Email Team","slug":"email","agent_slugs":["gmail-agent","outlook-agent","spam-deletion"]}'
```

### Defining a Workflow (API)

```bash
curl -X POST http://localhost:8000/api/v1/workflows/ \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "Morning Briefing",
    "slug": "morning-briefing",
    "trigger_event": "cron",
    "steps": [
      {"order": 1, "name": "Check calendar", "agent_slug": "gcal-agent"},
      {"order": 2, "name": "Check email", "agent_slug": "gmail-agent"},
      {"order": 3, "name": "Report to Slack", "agent_slug": "task-manager"}
    ]
  }'
```

---

## Prompt Hierarchy

Every LLM call is built from layered prompts:

```
prompts/
  system.md          ← Core safety/persona rules (SYSTEM_PROMPT)
  angie.md           ← Angie's personality and behavior (ANGIE_PROMPT)
  user/<id>/         ← Generated from onboarding (USER_PROMPTS)
    personality.md
    communication.md
    preferences.md
```

For agent tasks: `SYSTEM → ANGIE → AGENT_PROMPT`
For user interactions: `SYSTEM → ANGIE → USER_PROMPTS`

Reconfigure at any time:

```bash
angie prompts edit
angie setup           # re-run full onboarding
```

---

## Development

```bash
make help             # list all targets

make install          # install deps
make check            # lint + format check
make fix              # auto-fix lint + format
make test             # run all tests (unit + e2e)
make test-cov         # with coverage report
make test-single K=test_name  # single test

make migrate-new MSG="add column"  # new migration
make migrate          # apply migrations

make docker-up        # start MySQL + Redis
make docker-down      # stop
make docker-reset     # stop + wipe volumes

make build            # PyInstaller standalone binary → dist/angie
```

### Project Structure

```
angie/
├── src/angie/
│   ├── agents/         # Agent implementations + registry + teams
│   ├── api/            # FastAPI app + routers
│   ├── cache/          # Redis client + @cached decorator
│   ├── channels/       # Slack, Discord, iMessage, Email, WebChat
│   ├── cli/            # Click CLI commands
│   ├── core/           # Events, tasks, prompts, cron, loop, feedback
│   ├── db/             # SQLAlchemy session + generic repository
│   ├── models/         # SQLAlchemy ORM models
│   └── queue/          # Celery app + workers
├── frontend/           # Next.js 15 web UI
├── tests/
│   ├── e2e/            # End-to-end flow tests
│   ├── integration/    # (future) API integration tests
│   └── unit/           # Unit tests
├── prompts/            # Jinja2 prompt templates
├── alembic/            # DB migrations
├── docker/             # Dockerfiles
├── docker-compose.yml
├── Makefile
└── angie.spec          # PyInstaller spec
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | ✅ | JWT signing secret (generate with `openssl rand -hex 32`) |
| `DB_PASSWORD` | ✅ | MySQL password |
| `GITHUB_TOKEN` | ✅ | GitHub PAT for Copilot SDK |
| `DB_HOST` | | MySQL host (default: `localhost`) |
| `DB_NAME` | | Database name (default: `angie`) |
| `REDIS_HOST` | | Redis host (default: `localhost`) |
| `SLACK_BOT_TOKEN` | | Slack bot token (`xoxb-...`) |
| `DISCORD_BOT_TOKEN` | | Discord bot token |
| `BLUEBUBBLES_URL` | | BlueBubbles server URL for iMessage |
| `SMTP_HOST` | | SMTP server for email |
| `COPILOT_MODEL` | | LLM model (default: `gpt-4o`) |

---

## CI/CD

Two GitHub Actions workflows:

- **`ci.yml`** — runs on every push/PR: install → lint → format → test
- **`release.yml`** — runs on `v*` tags: build PyInstaller binary → GitHub Release

---

## License

MIT
