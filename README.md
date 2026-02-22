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

- **Real time chat interface** — Chat directly with Angie and your fleet of AI agents.
- **Unified inbox** — (UNDER DEVELOPMENT) Connect Slack, Discord, iMessage, and email in one place. Angie routes incoming messages to the right agent automatically.
- **Scheduled tasks** — (UNDER DEVELOPMENT) Set cron jobs that run agents on a schedule ("every weekday at 8am, summarize my email and post to Slack").
- **Multi-step workflows** — (UNDER DEVELOPMENT) Chain agents together: check calendar → summarize emails → control smart lights → send morning briefing.
- **Smart home control** — (UNDER DEVELOPMENT) Adjust Philips Hue lighting and Home Assistant automations via natural language.
- **Developer workflows** — Query GitHub issues, open PRs, and summarize repository activity.
- **Media control** — (UNDER DEVELOPMENT) Control Spotify playback, switch playlists, and manage your queue.
- **Network management** — (UNDER DEVELOPMENT) Inspect your UniFi network, connected devices, and bandwidth stats.
- **Personalized context** — Onboarding builds a private profile (personality, communication style, preferences) that shapes every LLM interaction.
- **REST API + Web UI** — Full FastAPI backend with a Next.js dashboard for managing agents, teams, workflows, tasks, and events in real time.

______________________________________________________________________

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                          Channels                               │
│  Slack(soon) · Discord(soon) · iMessage (soon) · Angie UI Chat  │
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
│  Email: gmail · outlook · yahoo · spam · correspondence         │
│  Calendar: gcal   Media: spotify   Dev: github                  │
│  Smart Home: hue · home-assistant   Networking: ubiquiti        │
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
| AI framework  | pydantic-ai + github-copilot-sdk                      |
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

______________________________________________________________________

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

______________________________________________________________________

## Agent Fleet

Agents are pydantic-ai powered workers. Each declares:

- `slug` — unique identifier used for routing
- `capabilities` — keywords that trigger auto-selection
- `execute(task)` — async method that does the work

### Built-in Agents

| Slug               | Category   | Description                    |
| ------------------ | ---------- | ------------------------------ |
| `cron-manager`     | System     | Create, list, delete cron jobs |
| `task-manager`     | System     | Manage task queue and status   |
| `workflow-manager` | System     | Trigger and monitor workflows  |
| `event-manager`    | System     | Inspect and replay events      |
| `gmail-agent`      | Email      | Gmail read/send/search         |
| `outlook-agent`    | Email      | Office 365 mail                |
| `yahoo-agent`      | Email      | Yahoo Mail                     |
| `spam-deletion`    | Email      | Delete spam across providers   |
| `correspondence`   | Email      | Draft and send replies         |
| `gcal-agent`       | Calendar   | Google Calendar CRUD           |
| `spotify-agent`    | Media      | Playback control, playlists    |
| `github-agent`     | Dev        | Issues, PRs, repos             |
| `hue-agent`        | Smart Home | Philips Hue lighting           |
| `home-assistant`   | Smart Home | Home Assistant integration     |
| `ubiquiti-agent`   | Networking | UniFi network management       |

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

______________________________________________________________________

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
angie prompts edit
angie setup           # re-run full onboarding
```

______________________________________________________________________

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

### LLM — GitHub Copilot (required for AI features)

| Variable           | Description                                                                          |
| ------------------ | ------------------------------------------------------------------------------------ |
| `GITHUB_TOKEN`     | GitHub OAuth token used to obtain a short-lived Copilot session token.               |
| `COPILOT_MODEL`    | Model to use (default: `gpt-4o`). Other options: `gpt-4o-mini`, `claude-3.5-sonnet`. |
| `COPILOT_API_BASE` | Copilot OpenAI-compatible endpoint (default: `https://api.githubcopilot.com`).       |

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

### OpenAI (optional fallback)

| Variable         | Description                                                   |
| ---------------- | ------------------------------------------------------------- |
| `OPENAI_API_KEY` | OpenAI API key (`sk-...`). Used if `GITHUB_TOKEN` is not set. |

Get from: **platform.openai.com → API Keys → Create new secret key**. No special permissions needed — any key with access to `gpt-4o` works.

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

### Email — SMTP/IMAP (optional)

| Variable          | Description                                          |
| ----------------- | ---------------------------------------------------- |
| `EMAIL_SMTP_HOST` | SMTP server hostname (e.g. `smtp.gmail.com`)         |
| `EMAIL_SMTP_PORT` | SMTP port (default: `587` for STARTTLS)              |
| `EMAIL_IMAP_HOST` | IMAP server hostname (e.g. `imap.gmail.com`)         |
| `EMAIL_IMAP_PORT` | IMAP port (default: `993` for SSL)                   |
| `EMAIL_USERNAME`  | Email address (e.g. `you@gmail.com`)                 |
| `EMAIL_PASSWORD`  | App password (not your regular password — see below) |

**Gmail setup:**

1. Enable **2-Step Verification** on your Google account
1. Go to **Google Account → Security → App passwords**
1. Create an app password for "Mail" → use this as `EMAIL_PASSWORD`
1. SMTP: `smtp.gmail.com:587`, IMAP: `imap.gmail.com:993`

**Other providers:** Use standard SMTP/IMAP settings. For Office 365: SMTP `smtp.office365.com:587`, IMAP `outlook.office365.com:993`.

______________________________________________________________________

### Google Calendar (optional)

| Variable                  | Description                                                     |
| ------------------------- | --------------------------------------------------------------- |
| `GOOGLE_CREDENTIALS_FILE` | Path to your `credentials.json` from Google Cloud Console       |
| `GOOGLE_TOKEN_FILE`       | Path where Angie stores the OAuth token (default: `token.json`) |

**Setup:**

1. Go to [console.cloud.google.com](https://console.cloud.google.com) → create a project
1. Enable the **Google Calendar API**
1. Under **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID** (Desktop app)
1. Download the JSON → save as `credentials.json` → set `GOOGLE_CREDENTIALS_FILE`
1. Required OAuth scopes:
   - `https://www.googleapis.com/auth/calendar` — full read/write access to calendars
   - `https://www.googleapis.com/auth/calendar.events` — create/edit/delete events
1. On first run, a browser window opens for authorization; the token is saved automatically

______________________________________________________________________

### Spotify (optional)

| Variable                | Description                                                    |
| ----------------------- | -------------------------------------------------------------- |
| `SPOTIFY_CLIENT_ID`     | Spotify app client ID                                          |
| `SPOTIFY_CLIENT_SECRET` | Spotify app client secret                                      |
| `SPOTIFY_REDIRECT_URI`  | OAuth callback URL (default: `http://localhost:8080/callback`) |

**Setup:**

1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) → **Create app**
1. Set the Redirect URI to `http://localhost:8080/callback`
1. Copy **Client ID** and **Client Secret**
1. Required scopes (requested at runtime):
   - `user-read-playback-state` — current track and device
   - `user-modify-playback-state` — play/pause/skip/volume
   - `user-read-currently-playing` — now-playing info
   - `playlist-read-private` — access private playlists
   - `playlist-modify-public`, `playlist-modify-private` — create/edit playlists

______________________________________________________________________

### Philips Hue (optional)

| Variable        | Description                                                |
| --------------- | ---------------------------------------------------------- |
| `HUE_BRIDGE_IP` | Local IP address of your Hue Bridge (e.g. `192.168.1.100`) |
| `HUE_USERNAME`  | API username registered on the bridge                      |

**Setup:**

1. Find your bridge IP in the Hue app or at [discovery.meethue.com](https://discovery.meethue.com)
1. Press the **link button** on the physical bridge
1. Within 30 seconds, POST to `http://<bridge_ip>/api` with `{"devicetype":"angie"}` to get your username
1. No cloud account or API key needed — this is a local LAN API

______________________________________________________________________

### Home Assistant (optional)

| Variable               | Description                                                                       |
| ---------------------- | --------------------------------------------------------------------------------- |
| `HOME_ASSISTANT_URL`   | Base URL of your Home Assistant instance (e.g. `http://homeassistant.local:8123`) |
| `HOME_ASSISTANT_TOKEN` | Long-lived access token                                                           |

**Setup:**

1. In Home Assistant, go to **Profile → Long-Lived Access Tokens → Create Token**
1. Give it a name (e.g. "Angie") and copy the token
1. The token inherits your user's permissions — use an account with access to the devices Angie should control

______________________________________________________________________

### UniFi / Ubiquiti (optional)

| Variable         | Description                                                                 |
| ---------------- | --------------------------------------------------------------------------- |
| `UNIFI_HOST`     | UniFi Controller URL (e.g. `https://192.168.1.1` or `https://unifi.ui.com`) |
| `UNIFI_USERNAME` | Controller admin username                                                   |
| `UNIFI_PASSWORD` | Controller admin password                                                   |

**Requirements:**

- A local UniFi Network Controller (self-hosted) or UniFi Cloud (unifi.ui.com)
- Admin credentials — a read-only account works for monitoring; admin is needed for device management
- For cloud access, use your Ubiquiti SSO credentials

______________________________________________________________________

### GitHub Agent (optional — separate from Copilot token)

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

Two GitHub Actions workflows:

- **`ci.yml`** — runs on every push/PR: install → lint → format → test
- **`release.yml`** — runs on `v*` tags: build PyInstaller binary → GitHub Release

______________________________________________________________________

## License

MIT
