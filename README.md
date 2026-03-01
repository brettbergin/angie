# Angie — Personal AI Assistant

![CI](https://github.com/brettbergin/angie/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-000000?logo=next.js&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?logo=sqlalchemy&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-4479A1?logo=mysql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?logo=redis&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-37814A?logo=celery&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)
![Ruff](https://img.shields.io/badge/Ruff-D7FF64?logo=ruff&logoColor=black)
![License](https://img.shields.io/github/license/brettbergin/angie)

> Your 24/7 personal AI assistant. Always on. Always working.

Angie is a self-hosted, event-driven AI assistant that runs as a persistent background daemon on your infrastructure. Angie connects to your real-world tools — email, calendar, smart home devices, music, GitHub, Slack, Discord, and more — and acts on your behalf through a fleet of specialized agents powered by GitHub Copilot's LLM.

Unlike chat-only AI tools, Angie is **proactive and persistent**: Angie wakes up on a schedule, monitors your channels, executes multi-step workflows, and reports back without being asked. Angie remembers context about you through a layered prompt hierarchy, so every interaction is personalized to your preferences, communication style, and routines.

### What Angie can do

- **Real-time chat interface** — Chat directly with Angie and your fleet of AI agents from the terminal or the web UI.
- **Developer workflows** — Query GitHub issues, open PRs, summarize repository activity, and turn issues into pull requests autonomously.
- **Web browsing** — Browse URLs, take screenshots, extract content, and summarize web pages.
- **Weather** — Get current conditions, forecasts, and severe weather alerts.
- **Unified inbox** — (planned) Connect Slack, Discord, iMessage, and email in one place. Angie routes incoming messages to the right agent automatically.
- **Scheduled tasks** — (planned) Set cron jobs that run agents on a schedule ("every weekday at 8am, summarize my email and post to Slack").
- **Multi-step workflows** — (planned) Chain agents together: check calendar → summarize emails → control smart lights → send morning briefing.
- **Smart home control** — (planned) Adjust Philips Hue lighting and Home Assistant automations via natural language.
- **Media control** — (planned) Control Spotify playback, switch playlists, and manage your queue.
- **Network management** — (planned) Inspect your UniFi network, connected devices, and bandwidth stats.
- **Personalized context** — Onboarding builds a private profile (personality, communication style, preferences) that shapes every LLM interaction.
- **REST API + Web UI** — Full FastAPI backend with a Next.js dashboard for managing agents, teams, workflows, tasks, and events in real time.

______________________________________________________________________

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                          Channels                               │
│  Slack · Discord · iMessage · Email · Angie UI Chat             │
└───────────────────────────┬─────────────────────────────────────┘
                            │ Events: infer task from user input
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Angie Daemon Loop                         │
│   EventRouter  →  TaskDispatcher  →  Celery Queue  →  Worker    │
│          ↑                                  ↑                   │
│     CronEngine                       AgentRegistry              │
└─────────────────────────────────────────────────────────────────┘
                            │ Task: units of work, assigned to agents/teams
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Agent Fleet                             │
│  System: cron · task-manager · workflow-manager · event-manager │
│  Dev: github · software-dev                                     │
│  Productivity: web   Lifestyle: weather                         │
└─────────────────────────────────────────────────────────────────┘
                            │ Agents & Teams: single teams of AI agents
                            ▼
┌───────────┐   ┌───────────────────┐   ┌───────────────────────┐
│   MySQL   │-->│   FastAPI (API)   │<->│     Redis Cache       │
│    DB     │<--│     /api/v1/*     │<->│    Celery broker      │
└───────────┘   └───────────────────┘   └───────────────────────┘
                           │ 
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              Next.js Web UI  (frontend/)                        │
│  Dashboard · Agents · Teams · Workflows · Tasks · Events        │
│  Real-time Chat · Settings                                      │
└─────────────────────────────────────────────────────────────────┘
```

### Key Concepts

| Concept              | Description                                                           |
| -------------------- | --------------------------------------------------------------------- |
| **Event**            | Any trigger: user message, cron tick, webhook, task completion        |
| **Task**             | A unit of work dispatched from an event to an agent                   |
| **Agent**            | A pydantic-ai powered worker that can handle specific task types      |
| **Team**             | A named group of agents that collaborate on related tasks             |
| **Workflow**         | An ordered sequence of steps across agents/teams for a goal           |
| **Prompt Hierarchy** | `SYSTEM → ANGIE → AGENT/USER` — layered context fed to every LLM call |

______________________________________________________________________

## Tech Stack

| Layer         | Technology                                            |
| ------------- | ----------------------------------------------------- |
| Language      | Python 3.12, uv                                       |
| AI framework  | pydantic-ai (GitHub Models, OpenAI, Anthropic)        |
| API           | FastAPI + SQLAlchemy 2.0 async                        |
| Database      | MySQL 8 (aiomysql driver)                             |
| Cache / Queue | Redis + Celery                                        |
| Scheduler     | APScheduler                                           |
| Channels      | Slack SDK · discord.py · BlueBubbles REST · SMTP/IMAP |
| CLI           | Click                                                 |
| Frontend      | Next.js 15 · TypeScript · Tailwind CSS v3             |
| Build         | PyInstaller (standalone `angie` binary)               |
| CI/CD         | GitHub Actions                                        |
| Dev           | Docker Compose, Ruff, pytest                          |

______________________________________________________________________

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
angie daemon

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

______________________________________________________________________

## CLI Reference

```bash
angie --help

# Daemon
angie daemon                 # Start background daemon (event loop)

# One-shot queries
angie ask "What's on my calendar today?"

# Interactive chat
angie chat "Hello Angie"             # Chat from the terminal
angie chat --agent github "List PRs" # Route directly to a specific agent

# Channel configuration
angie config slack           # Set Slack bot token
angie config discord         # Set Discord bot token
angie config imessage        # Set BlueBubbles URL
angie config email           # Set SMTP/IMAP credentials
angie config channels        # Show status of all configured channels

# Unified configuration wizard
angie configure keys slack   # Set API keys for a service
angie configure list         # Show all configured keys grouped by service
angie configure model        # Select the LLM model
angie configure seed         # Seed the database with demo data

# Onboarding
angie setup                  # Interactive first-run onboarding

# Status
angie status                 # Show active tasks, registered agents
```

______________________________________________________________________

## Agent Fleet

Agents are pydantic-ai powered workers. Each declares:

- `slug` — unique identifier used for routing
- `capabilities` — keywords that trigger auto-selection
- `execute(task)` — async method that does the work

### Built-in Agents

| Slug               | Category (group) | Description                                                    |
| ------------------ | ---------------- | -------------------------------------------------------------- |
| `cron`             | System           | Create, delete, and list cron scheduled tasks                  |
| `task-manager`     | System           | List, cancel, and retry Angie tasks                            |
| `workflow-manager` | System           | Manage and trigger Angie workflows                             |
| `event-manager`    | System           | Query, filter, and manage Angie events                         |
| `github`           | Dev              | GitHub repository and PR management                            |
| `software-dev`     | Dev              | Turn GitHub issues into pull requests autonomously             |
| `web`              | Productivity     | Browse URLs, take screenshots, extract and summarize web pages |
| `weather`          | Lifestyle        | Weather conditions, forecasts, and severe weather alerts       |

More agents are planned — see the environment variables section below for services Angie will support.

### Adding a New Agent

```python
# src/angie/agents/my_category/my_agent.py
from angie.agents.base import BaseAgent

class MyAgent(BaseAgent):
    name = "My Agent"
    slug = "my-agent"
    description = "Does something useful"
    category = "General"
    capabilities = ["useful", "something"]

    async def execute(self, task: dict) -> dict:
        # Use the underlying SDK / API here
        return {"status": "success", "result": "done"}
```

Then add to `AGENT_MODULES` in `src/angie/agents/registry.py`.

______________________________________________________________________

## Teams & Workflows

### Creating a Team (API)

```bash
curl -X POST http://localhost:8000/api/v1/teams/ \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"Dev Team","slug":"dev","agent_slugs":["github","software-dev"]}'
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
      {"order": 1, "name": "Check weather", "agent_slug": "weather"},
      {"order": 2, "name": "Browse news", "agent_slug": "web"},
      {"order": 3, "name": "Report status", "agent_slug": "task-manager"}
    ]
  }'
```

______________________________________________________________________

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
angie setup           # re-run full onboarding
```

______________________________________________________________________

## Development

```bash
make help             # list all targets

make install          # install deps
make check            # lint + format check
make fix              # auto-fix lint + format
make md-check         # check Markdown formatting
make md-fix           # auto-format Markdown files
make test             # run all tests (unit + e2e)
make test-cov         # with coverage report
make test-single K=test_name  # single test

make migrate-new MSG="add column"  # new migration
make migrate          # apply migrations

make docker-up        # start MySQL + Redis
make docker-down      # stop
make docker-reset     # stop + wipe volumes

make build            # PyInstaller standalone binary → dist/angie
make dist             # build sdist + wheel into dist/
make clean-dist       # remove distribution artifacts
make clean            # remove all build artifacts
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

______________________________________________________________________

## Environment Variables & API Key Permissions

Copy `.env.example` to `.env`. The sections below describe every credential, where to obtain it, and the exact permissions/scopes required.

______________________________________________________________________

### Core (required)

| Variable      | Description                                                                  |
| ------------- | ---------------------------------------------------------------------------- |
| `SECRET_KEY`  | JWT signing secret. Generate with `openssl rand -hex 32`. Keep this private. |
| `DB_PASSWORD` | MySQL password for the `angie` database user.                                |

______________________________________________________________________

### LLM Provider Selection

Angie supports three LLM providers. Set `LLM_PROVIDER` to choose:

| Provider                    | `LLM_PROVIDER` | Required Variables                     |
| --------------------------- | -------------- | -------------------------------------- |
| GitHub Models API (default) | `github`       | `GITHUB_TOKEN`, `COPILOT_MODEL`        |
| OpenAI                      | `openai`       | `OPENAI_API_KEY`, `COPILOT_MODEL`      |
| Anthropic Claude            | `anthropic`    | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` |

______________________________________________________________________

### LLM — GitHub Models API (default)

| Variable           | Description                                                                    |
| ------------------ | ------------------------------------------------------------------------------ |
| `GITHUB_TOKEN`     | GitHub OAuth token used to obtain a short-lived Copilot session token.         |
| `COPILOT_MODEL`    | Model to use (default: `gpt-4o`). Other options: `gpt-4o-mini`, `o1-mini`.     |
| `COPILOT_API_BASE` | Copilot OpenAI-compatible endpoint (default: `https://api.githubcopilot.com`). |

**How to get `GITHUB_TOKEN`:**

1. Go to **GitHub → Settings → Developer Settings → Personal Access Tokens → Tokens (classic)**
1. Click **Generate new token (classic)**
1. Under **Scopes**, enable:
   - `read:user` — required to identify your account
   - No additional scopes are needed; Copilot access is governed by your GitHub Copilot subscription, not token scopes
1. You must have an active **GitHub Copilot Individual, Business, or Enterprise** subscription
1. Paste the `ghp_...` token as `GITHUB_TOKEN`

> **Alternative:** Run `gh auth token` after authenticating with the [GitHub CLI](https://cli.github.com/) to get a token that already has the right access.

______________________________________________________________________

### OpenAI

| Variable         | Description                       |
| ---------------- | --------------------------------- |
| `OPENAI_API_KEY` | OpenAI API key (`sk-...`).        |
| `COPILOT_MODEL`  | Model to use (default: `gpt-4o`). |

Get from: **platform.openai.com → API Keys → Create new secret key**. No special permissions needed — any key with access to `gpt-4o` works.

______________________________________________________________________

### Anthropic Claude

| Variable            | Description                                                                                                             |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `ANTHROPIC_API_KEY` | Anthropic API key (`sk-ant-...`).                                                                                       |
| `ANTHROPIC_MODEL`   | Model to use (default: `claude-sonnet-4-20250514`). Other options: `claude-opus-4-20250514`, `claude-haiku-4-20250514`. |

Get from: **console.anthropic.com → API Keys → Create Key**.

______________________________________________________________________

### Slack (optional)

| Variable               | Description                                                                                     |
| ---------------------- | ----------------------------------------------------------------------------------------------- |
| `SLACK_BOT_TOKEN`      | Bot OAuth token (`xoxb-...`) — for posting messages and reading channel events                  |
| `SLACK_APP_TOKEN`      | App-level token (`xapp-...`) — required for Socket Mode (real-time events without a public URL) |
| `SLACK_SIGNING_SECRET` | Used to verify that incoming webhooks are from Slack                                            |

**How to create a Slack app:**

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App → From scratch**
1. Under **OAuth & Permissions → Bot Token Scopes**, add:
   - `channels:history` — read messages in public channels
   - `channels:read` — list channels
   - `chat:write` — post messages as the bot
   - `im:history` — read direct messages
   - `im:read` — list DM conversations
   - `im:write` — open DM conversations
   - `users:read` — look up user info (for @-mentioning)
   - `app_mentions:read` — receive `@Angie` mentions
1. Under **Event Subscriptions**, enable and subscribe to:
   - `message.channels`, `message.im`, `app_mention`
1. Under **Socket Mode**, enable Socket Mode and generate an **App-Level Token** with scope `connections:write` → this becomes `SLACK_APP_TOKEN`
1. Install the app to your workspace → copy the **Bot User OAuth Token** → `SLACK_BOT_TOKEN`
1. Under **Basic Information → Signing Secret** → `SLACK_SIGNING_SECRET`

______________________________________________________________________

### Discord (optional)

| Variable            | Description                                 |
| ------------------- | ------------------------------------------- |
| `DISCORD_BOT_TOKEN` | Bot token from the Discord Developer Portal |

**How to create a Discord bot:**

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications) → **New Application**
1. Under **Bot**, click **Add Bot** → copy the **Token** → `DISCORD_BOT_TOKEN`
1. Under **Bot → Privileged Gateway Intents**, enable:
   - **Message Content Intent** — required to read message text
   - **Server Members Intent** — required to look up user info
   - **Presence Intent** — optional, for presence-aware responses
1. Under **OAuth2 → URL Generator**, select scopes:
   - `bot` with permissions: `Send Messages`, `Read Message History`, `View Channels`, `Add Reactions`
1. Use the generated URL to invite the bot to your server

______________________________________________________________________

### iMessage via BlueBubbles (optional)

| Variable               | Description                                                          |
| ---------------------- | -------------------------------------------------------------------- |
| `BLUEBUBBLES_URL`      | URL of your BlueBubbles server (e.g. `https://your-server.ngrok.io`) |
| `BLUEBUBBLES_PASSWORD` | BlueBubbles server password                                          |

**Requirements:**

- A Mac that stays on with iMessage signed in
- [BlueBubbles Server](https://bluebubbles.app/) installed and running on that Mac
- A way to expose the server publicly (ngrok, Cloudflare Tunnel, or static IP)
- No Apple credentials needed — BlueBubbles uses the Mac's existing iMessage session

______________________________________________________________________

### GitHub Agent (optional — separate from Copilot API token)

This should be set from the Connections page in the Angie web UI. If not, we have:

| Variable     | Description                                                            |
| ------------ | ---------------------------------------------------------------------- |
| `GITHUB_PAT` | Personal Access Token for the GitHub agent (repo queries, PRs, issues) |

This is **separate** from `GITHUB_TOKEN` (which is for LLM). Create a fine-grained token at **GitHub → Settings → Developer Settings → Fine-grained tokens** with:

- `Contents: Read` — read repository files
- `Issues: Read and Write` — create/update issues
- `Pull requests: Read and Write` — create/update PRs
- `Metadata: Read` — required for all fine-grained tokens

______________________________________________________________________

## CI/CD

Three GitHub Actions workflows:

- **`ci.yml`** — runs on every push/PR: lint → format → markdown format → test → security → Docker build
- **`deploy.yml`** — runs on `v*.*.*` tags: build PyInstaller binary → GitHub Release + publish `angie-ai` to PyPI (via `PYPI_TOKEN`)

______________________________________________________________________

## License

MIT
