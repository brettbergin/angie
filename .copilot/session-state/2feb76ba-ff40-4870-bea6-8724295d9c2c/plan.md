# Cron System Full Implementation Plan

## Problem

The cron system is partially implemented: `CronEngine` (APScheduler-backed) and `CronAgent` exist, but cron jobs are **ephemeral** (lost on restart), there's **no REST API**, **no frontend UI**, and the agent creates a **new CronEngine per tool call** instead of persisting jobs. The user wants to `@cron` in chat with natural language, manage schedules via a UI, and have the system enforce a minimum 1-minute interval.

## Approach

**DB-backed persistence** with APScheduler as the runtime scheduler. The daemon syncs from DB on startup and periodically, so jobs survive restarts. The agent writes to DB, the daemon picks them up. A new "Schedules" page in the frontend provides full CRUD + enable/disable.

### Architecture

```
Chat: "@cron run nightly backup at midnight"
  → CronAgent (LLM converts NL → cron expression)
  → Writes ScheduledJob to DB via API
  → Daemon CronEngine syncs from DB (startup + every 60s)
  → APScheduler fires → AngieEvent(CRON) → TaskDispatcher → Celery → Agent

Frontend: /schedules page
  → REST API → DB CRUD
  → Daemon syncs changes automatically
```

---

## Todos

### 1. ScheduledJob Database Model
**File**: `src/angie/models/schedule.py`

Create `ScheduledJob` model:
- `id` (UUID string, PK)
- `user_id` (FK → users.id, NOT NULL)
- `name` (String 255, NOT NULL) — human-friendly name
- `description` (Text, nullable) — what this job does
- `cron_expression` (String 50, NOT NULL) — 5-part cron string
- `agent_slug` (String 100, nullable) — target agent (if any)
- `task_payload` (JSON, default {}) — data passed to the agent
- `is_enabled` (Boolean, default True)
- `last_run_at` (DateTime, nullable)
- `next_run_at` (DateTime, nullable)
- `created_at` / `updated_at` (TimestampMixin)

Add `UniqueConstraint("user_id", "name")` to prevent duplicate names per user.

Generate Alembic migration: `make migrate-new MSG="add scheduled_jobs table"`

### 2. Cron Expression Validation
**File**: `src/angie/core/cron.py`

Add `validate_cron_expression(expression: str) -> tuple[bool, str]`:
- Must be exactly 5 parts
- Each part must be valid for its field (minute 0-59, hour 0-23, etc.)
- Enforce minimum interval: reject sub-minute patterns
- Standard 5-part cron inherently can't go below 1 minute, but validate expression is parseable
- Use `CronTrigger` to validate — if it raises, expression is invalid
- Return `(is_valid, error_message)`

### 3. CronEngine Enhancement — DB Sync
**File**: `src/angie/core/cron.py`

Rework `CronEngine` to be DB-backed:
- `async start()` — start scheduler, run initial `sync_from_db()`
- `async sync_from_db()` — load all enabled `ScheduledJob` records, diff against in-memory `_jobs`, add/remove as needed. Update `next_run_at` on each job.
- `_start_sync_loop()` — periodic task that calls `sync_from_db()` every 60 seconds
- `_fire()` callback — update `last_run_at` in DB after firing
- Keep `add_cron()` / `remove_cron()` for direct in-memory management, but primary source of truth is DB
- `shutdown()` — stop scheduler + sync loop

### 4. Daemon Loop Update
**File**: `src/angie/core/loop.py`

- Change `self.cron.start()` to `await self.cron.start()` (now async for DB loading)
- The rest of the event dispatch flow stays the same — CRON events already flow through

### 5. REST API — Schedules Router
**File**: `src/angie/api/routers/schedules.py`

Endpoints (all JWT-protected, scoped to current user):

| Method | Path | Description |
|--------|------|-------------|
| `GET /` | List all schedules for current user | Filter by `is_enabled` optional |
| `POST /` | Create a new schedule | Validates cron expression |
| `GET /{id}` | Get single schedule | 404 if not found or wrong user |
| `PATCH /{id}` | Update schedule fields | Re-validates cron if changed |
| `DELETE /{id}` | Delete schedule | Removes from DB |
| `PATCH /{id}/toggle` | Toggle is_enabled | Enable/disable |

Pydantic models:
- `ScheduleCreate`: name, description?, cron_expression, agent_slug?, task_payload?, is_enabled?
- `ScheduleUpdate`: all optional fields
- `ScheduleOut`: all fields + computed `cron_human` (human-readable description)

Register in `app.py`: `app.include_router(schedules.router, prefix="/api/v1/schedules", tags=["schedules"])`

### 6. Cron Agent Rewrite
**File**: `src/angie/agents/system/cron.py`

Critical fix: **Stop creating new CronEngine instances per tool call.** Instead, tools should write directly to DB via async session. The daemon's CronEngine picks up changes on next sync cycle (≤60s).

Rewrite tools:
- `create_scheduled_task(expression, task_name, description, agent_slug, user_id)` → validate expression → INSERT ScheduledJob → return job details
- `delete_scheduled_task(job_id)` → DELETE from DB
- `list_scheduled_tasks(user_id)` → SELECT from DB
- `update_scheduled_task(job_id, ...)` → UPDATE in DB

Since pydantic-ai tools run in the Celery worker context (which has its own event loop via `asyncio.run`), use the worker's async session pattern from `angie.db.session`.

Enhance LLM instructions:
- Better natural language → cron conversion examples
- Include timezone awareness (default UTC, mention this)
- Explain minimum interval constraint (1 minute)

### 7. Frontend — API Client
**File**: `frontend/src/lib/api.ts`

Add `Schedule` type and `api.schedules` namespace: `list`, `create`, `get`, `update`, `delete`, `toggle`.

### 8. Frontend — Sidebar Navigation
**File**: `frontend/src/components/layout/Sidebar.tsx`

Add `{ href: "/schedules", label: "Schedules", icon: Clock }` to the "Work" nav section (alongside Events, Tasks, Workflows). Import `Clock` from lucide-react.

### 9. Frontend — Schedules Page
**File**: `frontend/src/app/schedules/page.tsx`

Pattern: Follow the Workflows page structure.

Features:
- **List view**: Cards showing name, description, cron expression (human-readable), next run time, agent slug badge, enable/disable toggle, delete button
- **Create form**: Expandable card with name, description, cron expression input, optional agent slug dropdown, task payload textarea
- **Search/filter**: Search by name, filter by enabled/disabled
- **Enable/disable toggle**: Badge click toggles `is_enabled`
- **Delete**: Confirmation dialog before delete
- **Empty state**: Clock icon with "No schedules yet" message
- **Cron human-readable**: Display `cron_human` from API (e.g., "Every day at midnight UTC")

### 10. Backend Tests
**File**: `tests/unit/test_api_routers.py` (append)

Tests for: list, create (valid + invalid cron + duplicate name), get, get 404, update, delete, toggle, cron validation.

### 11. Frontend Tests
**File**: `frontend/src/__tests__/schedules.test.tsx`

Tests for: renders list, empty state, create form, search filter, toggle.

### 12. Cron Human-Readable Helper
**File**: `src/angie/core/cron.py`

Add `cron_to_human(expression: str) -> str` — converts cron expressions to human-readable strings. Used by `ScheduleOut` response model.

---

## Key Design Decisions

1. **DB as source of truth, APScheduler as runtime**: Jobs persist in MySQL. The daemon's CronEngine syncs from DB on startup + every 60s. Changes take up to 60s to take effect (acceptable for cron-scale operations).

2. **Agent writes to DB, not APScheduler directly**: The CronAgent runs in Celery workers which don't have access to the daemon's scheduler. Writing to DB and letting the daemon sync is the clean, decoupled approach.

3. **Minimum interval = 1 minute**: Standard 5-part cron can't go below 1 minute natively. We validate expressions to reject anything invalid.

4. **User-scoped schedules**: Each schedule belongs to a user. The API filters by `current_user.id`. Users can only see/manage their own schedules.

5. **No Redis signaling needed**: 60-second polling is sufficient for cron job changes. Adding Redis pub/sub would be premature complexity.

6. **cron_human computed server-side**: The human-readable cron description is computed by the API, not the frontend.
