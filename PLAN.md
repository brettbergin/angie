# Angie — Personal AI Assistant · Implementation Plan

## Problem Statement

Build **Angie**, a 24/7 personal AI assistant that runs as an always-on daemon.
Angie is event-driven and orchestrates a fleet of specialized agents organized into
teams that execute workflows. Users interact with Angie via Slack, Discord, iMessage
(BlueBubbles), Email, a CLI, and a web UI.

## Decided Tech Stack

| Layer            | Technology                                                                                                    |
| ---------------- | ------------------------------------------------------------------------------------------------------------- |
| Language         | Python 3.12+ (managed with `uv`)                                                                              |
| AI Engines       | `pydantic-ai` (agent schemas, tools, structured I/O) + `github-copilot-sdk` (LLM engine, sessions, streaming) |
| API              | FastAPI (async)                                                                                               |
| Database         | MySQL 8 via SQLAlchemy 2.0 (async) + Alembic migrations                                                       |
| Cache            | Redis                                                                                                         |
| Task Queue       | Celery (Redis broker)                                                                                         |
| Frontend         | Next.js (React, SSR)                                                                                          |
| Containerization | Docker Compose (cloud-ready later)                                                                            |
| CLI              | `click`                                                                                                       |
| Build/Dev        | Makefile, pytest, ruff, pyinstaller                                                                           |
| Auth             | Multi-user, JWT-based                                                                                         |

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Communication Layer                         │
│  Slack · Discord · iMessage (BlueBubbles) · Email · Web Chat · CLI │
└────────────────────────────┬────────────────────────────────────────┘
                             │ Events
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Angie Core Event Loop                          │
│  Event Router → Task Dispatcher → Agent/Team Resolver → Executor  │
│                         ▲                                          │
│              Prompt Hierarchy                                      │
│   SYSTEM_PROMPT > ANGIE_PROMPT > AGENT_PROMPT | USER_PROMPTS       │
└────┬──────────┬────────────┬───────────────────────────────────────┘
     │          │            │
     ▼          ▼            ▼
┌─────────┐ ┌────────┐ ┌──────────┐
│  Celery │ │  Redis  │ │  MySQL   │
│ Workers │ │  Cache  │ │    DB    │
└─────────┘ └────────┘ └──────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Agent Fleet                                  │
│  Email · Calendar · Smart Home · Networking · Spotify · GitHub      │
│  Home Assistant · Cron · Task Mgr · Workflow Mgr · Event Mgr · ... │
└─────────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     External Services / SDKs                        │
│  Gmail API · O365 · Slack SDK · Discord.py · phue · Unifi API      │
│  Spotipy · BlueBubbles REST · GitHub API · Home Assistant API       │
└─────────────────────────────────────────────────────────────────────┘
```

## Key Concepts

- **Event**: Generic trigger (cron tick, user message, webhook, API call). Events are the sole input to Angie's core loop.
- **Task (AngieTask)**: A unit of work created from an event and placed on a queue.
- **Agent**: A pydantic-ai agent wrapping an external SDK. Has its own AGENT_PROMPT, tools, and structured I/O schema.
- **Team**: A named group of agents that collaborate on related tasks.
- **Workflow**: An ordered set of steps across one or more agents/teams to achieve a goal.
- **Prompt Hierarchy**: `SYSTEM_PROMPT → ANGIE_PROMPT → AGENT_PROMPT` for agent tasks; `SYSTEM_PROMPT → ANGIE_PROMPT → USER_PROMPTS` for user interactions. USER_PROMPTS are markdown files generated during onboarding.

## Repository Structure (target)

```
angie/
├── docker-compose.yml
├── Makefile
├── pyproject.toml              # uv-managed, single source of deps
├── alembic/                    # DB migrations
├── src/
│   └── angie/
│       ├── __init__.py
│       ├── main.py             # daemon entry point (event loop)
│       ├── config.py           # pydantic-settings based config
│       ├── core/
│       │   ├── events.py       # Event base class, EventRouter
│       │   ├── tasks.py        # AngieTask model, dispatcher
│       │   ├── loop.py         # Main event loop / daemon
│       │   └── prompts.py      # Prompt hierarchy manager
│       ├── models/             # SQLAlchemy models
│       │   ├── base.py
│       │   ├── user.py
│       │   ├── agent.py
│       │   ├── team.py
│       │   ├── workflow.py
│       │   ├── task.py
│       │   └── event.py
│       ├── db/
│       │   ├── session.py      # async engine + session factory
│       │   └── repository.py   # generic CRUD base
│       ├── cache/
│       │   └── redis.py        # Redis client, cache decorators
│       ├── queue/
│       │   ├── celery_app.py   # Celery config
│       │   └── workers.py      # Task execution workers
│       ├── agents/             # Agent fleet
│       │   ├── base.py         # BaseAgent (pydantic-ai agent wrapper)
│       │   ├── registry.py     # Agent registry (discover + load)
│       │   ├── email/
│       │   │   ├── gmail.py
│       │   │   ├── outlook.py
│       │   │   ├── yahoo.py
│       │   │   └── spam.py
│       │   ├── calendar/
│       │   │   └── gcal.py
│       │   ├── smart_home/
│       │   │   ├── hue.py
│       │   │   └── home_assistant.py
│       │   ├── networking/
│       │   │   └── ubiquiti.py
│       │   ├── media/
│       │   │   └── spotify.py
│       │   ├── dev/
│       │   │   └── github.py
│       │   ├── system/
│       │   │   ├── cron.py
│       │   │   ├── task_manager.py
│       │   │   ├── workflow_manager.py
│       │   │   └── event_manager.py
│       │   └── ...
│       ├── channels/           # Communication adapters
│       │   ├── base.py         # BaseChannel interface
│       │   ├── slack.py
│       │   ├── discord.py
│       │   ├── imessage.py     # BlueBubbles REST wrapper
│       │   ├── email.py
│       │   └── web_chat.py     # WebSocket for web UI chat
│       ├── api/                # FastAPI application
│       │   ├── app.py
│       │   ├── auth.py         # JWT auth
│       │   ├── deps.py         # dependency injection
│       │   └── routers/
│       │       ├── agents.py
│       │       ├── teams.py
│       │       ├── workflows.py
│       │       ├── tasks.py
│       │       ├── events.py
│       │       ├── users.py
│       │       ├── prompts.py
│       │       └── chat.py     # WebSocket chat endpoint
│       └── cli/                # Click CLI
│           ├── __init__.py
│           ├── main.py
│           ├── setup.py        # First-run onboarding (USER_PROMPTS)
│           ├── chat.py         # Quick questions
│           ├── config.py       # Manage integrations (Slack, Discord, etc.)
│           └── status.py       # What is Angie doing right now?
├── frontend/                   # Next.js app
│   ├── package.json
│   ├── next.config.js
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   ├── dashboard/
│   │   │   ├── agents/
│   │   │   ├── teams/
│   │   │   ├── workflows/
│   │   │   ├── tasks/
│   │   │   ├── events/
│   │   │   ├── chat/
│   │   │   └── settings/
│   │   ├── components/
│   │   └── lib/
│   └── ...
├── prompts/                    # Prompt templates (markdown)
│   ├── system.md
│   ├── angie.md
│   └── onboarding/             # USER_PROMPTS templates
│       ├── personality.md
│       ├── communication.md
│       └── preferences.md
├── tests/
│   ├── conftest.py
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── .github/
│   ├── copilot-instructions.md
│   └── workflows/
│       ├── ci.yml
│       └── release.yml
└── docker/
    ├── Dockerfile.api
    ├── Dockerfile.worker
    ├── Dockerfile.frontend
    └── Dockerfile.daemon
```

## Implementation Phases

### Phase 1 — Project Skeleton & Dev Environment

Set up the monorepo structure, tooling, and dev workflow so every subsequent phase has a solid foundation.

1. **project-init**: Initialize `pyproject.toml` with `uv`, configure ruff, pytest, and project metadata.
1. **makefile**: Create Makefile with targets: `install`, `lint`, `lint-fix`, `format`, `format-fix`, `check` (lint+format+typecheck), `fix` (lint-fix+format-fix), `test`, `test-single` (run one test), `build`, `docker-up`, `docker-down`, `docker-build`, `clean`.
1. **docker-compose**: Define services — `mysql`, `redis`, `api`, `worker`, `daemon`, `frontend`. Include health checks, volumes, networks.
1. **dockerfiles**: Create Dockerfiles for each service (`docker/`).
1. **github-ci**: CI workflow — lint, test, build on push/PR. Release workflow stub.
1. **copilot-instructions**: `.github/copilot-instructions.md` with project conventions.

### Phase 2 — Database & Core Models

Stand up the data layer that everything else depends on.

7. **db-setup**: SQLAlchemy async engine, session factory, Alembic init. `src/angie/db/`.
1. **models**: Define all SQLAlchemy models — User, Agent, Team, Workflow, WorkflowStep, Task, Event, Prompt, Channel config. `src/angie/models/`.
1. **migrations**: Initial Alembic migration generating all tables.
1. **cache-layer**: Redis client wrapper with cache decorators. `src/angie/cache/`.

### Phase 3 — Config, Prompts & Auth

The prompt system and config are foundational to every agent interaction.

11. **config**: pydantic-settings based config loading (env vars, `.env` file). `src/angie/config.py`.
01. **prompt-hierarchy**: Prompt manager that loads and composes `SYSTEM_PROMPT → ANGIE_PROMPT → AGENT_PROMPT / USER_PROMPTS`. Template rendering with Jinja2. `src/angie/core/prompts.py` + `prompts/` directory.
01. **auth**: JWT-based auth (login, register, token refresh). Password hashing with bcrypt. `src/angie/api/auth.py`.

### Phase 4 — Event System & Task Queue

The nervous system of Angie — how work enters and flows through the system.

14. **event-system**: Event base class, event types enum, EventRouter that maps events to handlers. `src/angie/core/events.py`.
01. **celery-setup**: Celery app config with Redis broker, result backend. Task serialization. `src/angie/queue/`.
01. **task-dispatcher**: AngieTask model, dispatcher that creates tasks from events and enqueues them via Celery. `src/angie/core/tasks.py`.
01. **workers**: Celery workers that pick up tasks, resolve the target agent/team, and execute. `src/angie/queue/workers.py`.

### Phase 5 — Agent Framework

The pluggable agent system — the core abstraction layer.

18. **base-agent**: `BaseAgent` class wrapping pydantic-ai. Defines interface: `name`, `description`, `tools`, `prompt`, `execute()`, `can_handle()`. Integrates copilot-sdk for LLM sessions. `src/angie/agents/base.py`.
01. **agent-registry**: Auto-discovery registry. Agents register by decorator or config. Supports listing, lookup by capability. `src/angie/agents/registry.py`.
01. **team-model**: Team abstraction — a named group of agents. Team resolver picks the right agent(s) for a task. `src/angie/agents/teams.py` (runtime) + DB model.
01. **workflow-engine**: Workflow executor — runs ordered steps, passes context between agents, handles branching/failure. `src/angie/core/workflows.py`.

### Phase 6 — API Layer

CRUD API for all entities plus real-time chat.

22. **fastapi-app**: FastAPI app with middleware (CORS, auth, error handling), dependency injection. `src/angie/api/app.py`.
01. **crud-routers**: REST routers for agents, teams, workflows, tasks, events, users, prompts. Standard CRUD patterns. `src/angie/api/routers/`.
01. **chat-endpoint**: WebSocket endpoint for real-time chat with Angie from the web UI. `src/angie/api/routers/chat.py`.

### Phase 7 — Communication Channels

Pluggable adapters for each communication platform.

25. **channel-base**: `BaseChannel` abstract class — `send()`, `receive()`, `mention_user()`, `listen()`. `src/angie/channels/base.py`.
01. **slack-channel**: Slack integration using `slack-sdk`. Bot that listens in configured channels, can @-mention user. `src/angie/channels/slack.py`.
01. **discord-channel**: Discord integration using `discord.py`. Similar bot pattern. `src/angie/channels/discord.py`.
01. **imessage-channel**: BlueBubbles REST API wrapper for iMessage send/receive/webhooks. `src/angie/channels/imessage.py`.
01. **email-channel**: Email send/receive (SMTP/IMAP) for notifications. `src/angie/channels/email.py`.
01. **web-chat-channel**: WebSocket bridge connecting the API chat endpoint to the channel system. `src/angie/channels/web_chat.py`.

### Phase 8 — Core Event Loop (Angie Daemon)

The main daemon that ties everything together.

31. **daemon**: Main Angie daemon — starts event loop, initializes channels, polls cron registry, processes task queue results, handles feedback/logging. Runs as a long-lived process. `src/angie/core/loop.py` + `src/angie/main.py`.
01. **cron-engine**: Cron scheduler within the daemon — evaluates cron expressions, fires events. Uses APScheduler or similar. `src/angie/core/cron.py`.
01. **feedback-system**: Logging + user feedback — Angie reports success/failure back through the originating channel. `src/angie/core/feedback.py`.

### Phase 9 — CLI

User-facing CLI for setup, quick interaction, and management.

34. **cli-framework**: Click-based CLI entry point. `src/angie/cli/main.py`.
01. **cli-onboarding**: `angie setup` — interactive first-run that asks questions, generates USER_PROMPTS markdown files, persists to DB. `src/angie/cli/setup.py`.
01. **cli-chat**: `angie ask "..."` — quick question to Angie from terminal. `src/angie/cli/chat.py`.
01. **cli-config**: `angie config slack|discord|email|imessage` — configure channel integrations. `src/angie/cli/config.py`.
01. **cli-status**: `angie status` — what is Angie doing right now, active tasks, recent events. `src/angie/cli/status.py`.
01. **cli-prompts**: `angie prompts edit|list|reset` — manage USER_PROMPTS. `src/angie/cli/prompts.py`.

### Phase 10 — Agent Fleet (Initial Set)

Implement the first batch of agents, each wrapping its respective SDK.

40. **agent-cron**: Cron task manager agent (create/delete/list crons). `src/angie/agents/system/cron.py`.
01. **agent-task-mgr**: Task manager agent (list/cancel/retry tasks). `src/angie/agents/system/task_manager.py`.
01. **agent-workflow-mgr**: Workflow manager agent. `src/angie/agents/system/workflow_manager.py`.
01. **agent-event-mgr**: Event manager agent. `src/angie/agents/system/event_manager.py`.
01. **agent-gmail**: Gmail agent (send, read, search, labels) via `google-api-python-client`. `src/angie/agents/email/gmail.py`.
01. **agent-outlook**: Office 365 mail agent via `O365` SDK. `src/angie/agents/email/outlook.py`.
01. **agent-yahoo**: Yahoo mail agent. `src/angie/agents/email/yahoo.py`.
01. **agent-spam**: Email spam deletion agent (works across all mail agents). `src/angie/agents/email/spam.py`.
01. **agent-gcal**: Google Calendar agent via `google-api-python-client`. `src/angie/agents/calendar/gcal.py`.
01. **agent-hue**: Philips Hue agent via `phue`. `src/angie/agents/smart_home/hue.py`.
01. **agent-ha**: Home Assistant agent via `homeassistant-api`. `src/angie/agents/smart_home/home_assistant.py`.
01. **agent-ubiquiti**: UniFi networking agent via `aiounifi` or `pyunifi`. `src/angie/agents/networking/ubiquiti.py`.
01. **agent-spotify**: Spotify agent via `spotipy`. `src/angie/agents/media/spotify.py`.
01. **agent-github**: GitHub agent via `PyGithub` or `githubkit`. `src/angie/agents/dev/github.py`.
01. **agent-email-correspond**: Email correspondence agent (drafts context-aware replies). `src/angie/agents/email/correspondence.py`.

### Phase 11 — Frontend (Next.js)

Rich web application for managing everything.

55. **frontend-init**: Next.js project setup with TypeScript, Tailwind, shadcn/ui component library. `frontend/`.
01. **frontend-auth**: Login/register pages, JWT token management, auth context. `frontend/src/app/(auth)/`.
01. **frontend-dashboard**: Dashboard — task history, event timeline, success/failure stats, active agents. `frontend/src/app/dashboard/`.
01. **frontend-agents**: Agent fleet management — list, create, edit, delete agents. `frontend/src/app/agents/`.
01. **frontend-teams**: Team management — group agents, assign roles. `frontend/src/app/teams/`.
01. **frontend-workflows**: Workflow builder — define steps, assign agents/teams, visual editor. `frontend/src/app/workflows/`.
01. **frontend-tasks**: Task history — list, filter, view details, retry. `frontend/src/app/tasks/`.
01. **frontend-events**: Event log — past events, future scheduled events, cron status. `frontend/src/app/events/`.
01. **frontend-chat**: Chat interface — real-time WebSocket chat with Angie. `frontend/src/app/chat/`.
01. **frontend-settings**: User settings — channel config, prompt management, profile. `frontend/src/app/settings/`.

### Phase 12 — Polish & Release

Final integration, testing, and packaging.

65. **e2e-tests**: End-to-end tests covering critical flows (onboarding → create agent → run task → get feedback).
01. **pyinstaller**: PyInstaller config to build standalone `angie` CLI binary.
01. **docs**: README overhaul, architecture docs, quickstart guide.

## Key Design Decisions

1. **Event-driven, not request-driven**: Everything enters via events. User messages, cron ticks, webhooks, API calls — all become events. This makes the system pluggable.

1. **Agent = pydantic-ai Agent + SDK wrapper**: Each agent defines its pydantic-ai schema (tools, structured I/O) and uses the underlying service SDK for actual work. copilot-sdk provides the LLM session/engine.

1. **Prompt composition at runtime**: Prompts are Jinja2 markdown templates. The prompt manager composes `SYSTEM + ANGIE + (AGENT | USER_PROMPTS)` at request time, injecting user context and agent capabilities.

1. **Celery for async task execution**: User-facing requests return immediately. Tasks execute asynchronously in Celery workers. Results flow back through channels.

1. **Channel abstraction**: All communication platforms implement the same `BaseChannel` interface. Angie doesn't know or care which platform she's talking through.

1. **Redis for caching AND Celery broker**: Single Redis instance serves dual purpose. Cache invalidation via TTL and event-based clearing.

1. **Multi-user from day one**: JWT auth, per-user prompt configs, per-user channel bindings. Users are isolated.

## Notes

- iMessage via BlueBubbles requires a Mac running the BlueBubbles server. This is a host-level dependency, not containerized.
- copilot-sdk is in technical preview — API may change. Isolate behind an abstraction layer.
- The agent fleet is large (14+ agents). Implement system agents first (cron, task, workflow, event managers), then communication agents, then service agents. Each agent should be independently testable.
- The frontend is a full application. Consider using shadcn/ui for consistent, accessible components.

______________________________________________________________________

## Appendix: Original Requirements (User Input)

We are going to build me a personal ai assistant who runs 24 hours a day, doing work for me, helping with my daily digital life. Her name is angie and shes your digital companion. Here is what I am thinking for the tech stack: 1. python 2. pydantic-ai 3. copilot-sdk 4. mysql and sqlalchemy. docker compose with docker containers for various things we will talk about more in detail later. I want to primarily interact with angie view channels on slack and discord. When I ask angie to do things, she should be able to determine the corresponding agent and/or skills we have in our fleet of agents and use it to complete the task. tasks are things that are asked for angie to do. angie should always have a positive intent for the user. Angie should not do more than asked of her. I want this to be an event driven system that are "pluggable" or "adaptable" if you understand what I mean. Example: an event, can be a cron trigger, task request, user message, etc. Events are generic ways of describing the event that can invoke a single agent AND ALSO A team of agents. Groups of agents are known as "teams". Teams of agents have common tasks that work together to achieve a common goal. This set of "common tasks that work together" for the common goal are known as "workflows". I hope you are starting to understand where I am going with this. I want to make sure we design the proper caching layers. I want user interface features to fully manage the workflows, teams, agents, tasks, events, etc. I want angie to have a cli that allows me to quickly ask questions about what shes doing. I think we need something like celery ask a queuing system, but I will let you make best judgement. I mention this as a way to give you an idea of how I want things processed, not a tech requirements. I want angie to be able to communicate with me and @-mention me in the channels weve established when she needs to. I want the angie-cli to support setting up the slack/discord integration based on user preference. I want to be able to chat with angie via a chat interface in the angie web UI. The tech stack must haves: 1. A client side rich application (react) showing task history, event history, future events, their sucess and failure, etc. - The application should allow the user to group agents in the fleet and define workflows. 2. An api that can be used to CRUD data into the Mysql DB. 3. The mysql database itself. 4. A queuing system (celery?) 5. A caching system (redis) Communication I want angie to support: - IMessage - Slack - Discord - Email (user configured) Agent Fleet for angie to be able to use: - Email correspondence agent - Email mangement agent - Gmail calendar management agent - Smart Home Lighting (Hue) agent - Home networking agent (ubiquiti) - Cron-task Manager (Create a cron, delete, etc) - spotify agent - Home assistant agent - Task manager agent - Workflow manager agent - Event Manager agent - Github agent - Office 265 (mail) Agent - Gmail Agent - Yahoo Mail Agent - Email Spam Deletion Here is the important part about the agents. Many of the things I've listed, already have python sdks that help handle the general intergartion tasks we want. Where the agentic aspect of this comes in is we will use the SDKs to perform the behaviors we need, and we will wraps them with the pydantic-ai sdk to define the agents abilities. The input system. Angie should have a heirchary of PROMPTS that formulate the initial prompt in a copitlot session or howver this actually works. I want there to be a SYSTEM_PROMPT > ANGIE_PROMPT > AGENT_PROMPT. As well as: SYSTEM_PROMPT > ANGIE_PROMPT > USER PROMPTS. Notice the S on USER PROMPTS. when angie fist starts, she needs to get to know the user. Shes needs to ask everything she can to formulate as much detail to help understand how to correspond, behave, function, as angie the digital personal assitant.Angie should have a cli command to take input from the user on first usage. She should ask the user a set of questions that help her produce a set of markdown files that will then be persisted as the USER PROMPTS. all of these prompts needs to be used by pydantic-ai as part of our LLM interactions for angie. User inputs The user should be able to: 1. reconfigure their prompts at any time. the cli should provide full support for this. 2. configure the agent fleet from the user interface. we should be able to add them, delete them, update them, group them, define teams, etc. Angie herself Angie is an event loop. On each event, she looks for AngieTasks in queues, AngiesCrons to execute, Users her agents to process Workflows, Gives the user feedback. Logs the success and failure along the way. She is an alway on system that should run as a daemon on the system. Dev environement: uv for python Make system supporting the application linting, formatting, testing, docker management. I want check AND fix commands that correspond. I want a make build. Pytest Ruff PyInstaller / build system. Github CICD Workflows
