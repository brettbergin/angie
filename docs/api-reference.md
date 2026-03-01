# Angie API Reference

Base URL: `http://localhost:8000`

## Authentication

JWT Bearer tokens via OAuth2. Obtain tokens from `/api/v1/auth/token`.
Include in requests as `Authorization: Bearer <token>`.

Two endpoints use query-parameter auth instead (for img src / WebSocket use):
`/api/v1/media/{filename}?token=<jwt>` and `/api/v1/chat/ws?token=<jwt>`.

______________________________________________________________________

## Health

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| GET | `/health` | No | Basic status check (`{"status": "ok", "service": "angie-api"}`) |
| GET | `/api/v1/health` | No | Detailed check with DB/Redis connectivity and uptime |

______________________________________________________________________

## Auth (`/api/v1/auth`)

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| POST | `/auth/register` | No | Create account, returns access + refresh tokens |
| POST | `/auth/token` | No | Login with username/password, returns tokens |

### POST `/auth/register`

**Request:**

```json
{
  "email": "user@example.com",
  "username": "user",
  "password": "secret",
  "full_name": "Jane Doe"
}
```

**Response (201):**

```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

### POST `/auth/token`

Standard OAuth2 password flow (`application/x-www-form-urlencoded`):
`username=user&password=secret`

**Response (200):** Same `TokenResponse` as register.

______________________________________________________________________

## Users (`/api/v1/users`)

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| GET | `/users/me` | Yes | Get current user profile |
| PATCH | `/users/me` | Yes | Update profile (`full_name`, `timezone`) |
| POST | `/users/me/password` | Yes | Change password (`current_password`, `new_password`) |

______________________________________________________________________

## Agents (`/api/v1/agents`)

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| GET | `/agents/` | Yes | List all registered agents |
| GET | `/agents/{slug}` | Yes | Agent detail (includes instructions, system prompt, module path) |

### Agent response fields

| Field | Type | Description |
| ----- | ---- | ----------- |
| `slug` | string | Unique identifier |
| `name` | string | Display name |
| `description` | string | What the agent does |
| `capabilities` | list\[string\] | Keywords for routing |
| `category` | string | Agent category |
| `instructions` | string | (detail only) Agent instructions |
| `system_prompt` | string | (detail only) Composed system prompt |
| `module_path` | string | (detail only) Python module path |

______________________________________________________________________

## Teams (`/api/v1/teams`)

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| GET | `/teams/` | Yes | List teams (`?enabled_only=true` to filter) |
| POST | `/teams/` | Yes | Create team |
| GET | `/teams/{team_id}` | Yes | Get team |
| PATCH | `/teams/{team_id}` | Yes | Update team |
| DELETE | `/teams/{team_id}` | Yes | Delete team (204) |

### Create/update fields

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `name` | string | yes | Team name |
| `slug` | string | yes (create) | Team slug |
| `description` | string | no | Description |
| `goal` | string | no | Team objective |
| `agent_slugs` | list\[string\] | no | Agent slugs in team |
| `is_enabled` | bool | no | Default `true` |

______________________________________________________________________

## Workflows (`/api/v1/workflows`)

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| GET | `/workflows/` | Yes | List all workflows |
| POST | `/workflows/` | Yes | Create workflow |
| GET | `/workflows/{workflow_id}` | Yes | Get workflow |
| PATCH | `/workflows/{workflow_id}` | Yes | Update workflow |
| DELETE | `/workflows/{workflow_id}` | Yes | Delete workflow (204) |

### Create/update fields

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `name` | string | yes | Workflow name |
| `slug` | string | yes (create) | Workflow slug |
| `description` | string | no | Description |
| `team_id` | string | no | Associated team |
| `trigger_event` | string | no | Event type that triggers this workflow |
| `is_enabled` | bool | no | Default `true` |

______________________________________________________________________

## Tasks (`/api/v1/tasks`)

Users can only access their own tasks.

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| GET | `/tasks/` | Yes | List tasks (newest first) |
| POST | `/tasks/` | Yes | Create task |
| GET | `/tasks/{task_id}` | Yes | Get task |
| PATCH | `/tasks/{task_id}` | Yes | Update status/output |
| DELETE | `/tasks/{task_id}` | Yes | Delete task (204) |

### Task response fields

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | string | Task ID |
| `title` | string | Task title |
| `status` | string | `pending`, `queued`, `running`, `success`, `failure`, `cancelled`, `retrying` |
| `input_data` | dict | Input parameters |
| `output_data` | dict | Task output |
| `error` | string \| null | Error message if failed |
| `source_channel` | string \| null | Originating channel |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last update timestamp |

______________________________________________________________________

## Events (`/api/v1/events`)

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| GET | `/events/` | Yes | List events (max 200, newest first) |
| POST | `/events/` | Yes | Create event |

### Create fields

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `type` | string | yes | Event type |
| `payload` | dict | no | Event data |
| `source_channel` | string | no | Source channel |

______________________________________________________________________

## Prompts / Preferences (`/api/v1/prompts`)

User preferences that shape LLM interactions. Valid names: `personality`, `interests`, `schedule`, `priorities`, `communication`, `home`, `work`, `style`.

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| GET | `/prompts/definitions` | Yes | List all preference definitions with labels and placeholders |
| GET | `/prompts/` | Yes | List user's preferences (auto-seeds defaults if empty) |
| GET | `/prompts/{name}` | Yes | Get specific preference |
| PUT | `/prompts/{name}` | Yes | Create or update preference (max 10,000 chars) |
| DELETE | `/prompts/{name}` | Yes | Delete preference |
| POST | `/prompts/reset` | Yes | Reset all preferences to defaults |

______________________________________________________________________

## Schedules (`/api/v1/schedules`)

Cron-based scheduled jobs. Users can only access their own schedules.

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| GET | `/schedules/` | Yes | List schedules |
| POST | `/schedules/` | Yes | Create schedule |
| GET | `/schedules/{schedule_id}` | Yes | Get schedule |
| PATCH | `/schedules/{schedule_id}` | Yes | Update schedule |
| DELETE | `/schedules/{schedule_id}` | Yes | Delete schedule (204) |
| PATCH | `/schedules/{schedule_id}/toggle` | Yes | Toggle enabled/disabled |

### Create/update fields

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `name` | string | yes | Schedule name (max 255) |
| `description` | string | no | Description |
| `cron_expression` | string | yes (create) | Cron expression (max 50, validated). Supports standard 5-field cron syntax or `@once` for a one-time run. |
| `next_run_at` | datetime | yes (create, when `cron_expression` is `@once`) | First/only execution time for `@once` schedules (ISO 8601, UTC). Required when using `@once`. |
| `agent_slug` | string | no | Agent to execute |
| `task_payload` | dict | no | Task parameters |
| `is_enabled` | bool | no | Default `true` |
| `conversation_id` | string | no | Conversation to deliver results to (web chat). |

### Schedule response extras

| Field | Type | Description |
| ----- | ---- | ----------- |
| `cron_human` | string | Human-readable cron description |
| `last_run_at` | datetime \| null | Last execution time |
| `next_run_at` | datetime \| null | Next scheduled execution |

______________________________________________________________________

## Channels (`/api/v1/channels`)

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| GET | `/channels/` | Yes | List channel configurations |
| PUT | `/channels/{channel_type}` | Yes | Create or update channel config (upsert) |

### Upsert fields

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `type` | string | yes | Channel type identifier |
| `is_enabled` | bool | no | Default `true` |
| `config` | dict | no | Channel-specific configuration |

______________________________________________________________________

## Connections (`/api/v1/connections`)

Service connections with encrypted credential storage.

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| GET | `/connections/services` | Yes | List available service definitions and required fields |
| GET | `/connections/` | Yes | List user's connections (credentials masked) |
| GET | `/connections/{connection_id}` | Yes | Get connection (credentials masked) |
| POST | `/connections/` | Yes | Create connection |
| PATCH | `/connections/{connection_id}` | Yes | Update credentials or display name |
| DELETE | `/connections/{connection_id}` | Yes | Delete connection (204) |
| POST | `/connections/{connection_id}/test` | Yes | Test connection validity against service endpoint |

### Create fields

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `service_type` | string | yes | Service type key |
| `credentials` | dict | yes | Service credentials (encrypted at rest) |
| `display_name` | string | no | Custom display name |

### Test response

```json
{
  "success": true,
  "message": "Connection is working",
  "status": "CONNECTED"
}
```

______________________________________________________________________

## Conversations (`/api/v1/conversations`)

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| GET | `/conversations/` | Yes | List conversations (paginated: `?limit=20&offset=0`) |
| POST | `/conversations/` | Yes | Create conversation (optional `title`, defaults to "New Chat") |
| GET | `/conversations/{conversation_id}` | Yes | Get conversation |
| GET | `/conversations/{conversation_id}/messages` | Yes | Get all messages (oldest first) |
| PATCH | `/conversations/{conversation_id}` | Yes | Update title |
| DELETE | `/conversations/{conversation_id}` | Yes | Delete conversation and messages (204) |

### Pagination response

```json
{
  "items": [...],
  "total": 42,
  "has_more": true
}
```

### Message fields

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | string | Message ID |
| `conversation_id` | string | Parent conversation |
| `role` | string | `USER` or `ASSISTANT` |
| `content` | string | Message content (may contain markdown) |
| `agent_slug` | string \| null | Agent that produced the response |
| `created_at` | datetime | Timestamp |

______________________________________________________________________

## Chat WebSocket (`/api/v1/chat/ws`)

Real-time chat with LLM-powered responses and agent task dispatch.

**Connect:** `ws://localhost:8000/api/v1/chat/ws?token=<jwt>&conversation_id=<optional>`

### Send message

```json
{"content": "What's the weather in NYC?"}
```

Plain text (non-JSON) is also accepted as message content.

### Receive response

```json
{
  "content": "Let me check the weather for you...",
  "role": "assistant",
  "conversation_id": "conv-id-123",
  "task_dispatched": true
}
```

### Heartbeat

Send `{"type": "ping"}`, receive `{"type": "pong"}`.

### Agent routing

- Use `@agent-slug` in your message to route to a specific agent (e.g., `@github list my PRs`)
- Use `@team-slug` to route to a team
- Without @-mentions, Angie decides whether to answer directly or dispatch to an agent

### Task results

When a dispatched task completes, the result is pushed to the WebSocket via Redis pub/sub.

______________________________________________________________________

## Media (`/api/v1/media`)

Serves files generated by agents (screenshots, images).

| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| GET | `/media/{filename}?token=<jwt>` | Yes (query param) | Serve media file |

Auth is via query parameter so URLs work in `<img src="...">` tags.
Path traversal is blocked — only bare filenames are accepted.

______________________________________________________________________

## Quick Reference

| Method | Path | Auth | Status |
| ------ | ---- | ---- | ------ |
| GET | `/health` | No | 200 |
| GET | `/api/v1/health` | No | 200 |
| POST | `/api/v1/auth/register` | No | 201 |
| POST | `/api/v1/auth/token` | No | 200 |
| GET | `/api/v1/users/me` | Yes | 200 |
| PATCH | `/api/v1/users/me` | Yes | 200 |
| POST | `/api/v1/users/me/password` | Yes | 200 |
| GET | `/api/v1/agents/` | Yes | 200 |
| GET | `/api/v1/agents/{slug}` | Yes | 200 |
| GET | `/api/v1/teams/` | Yes | 200 |
| POST | `/api/v1/teams/` | Yes | 201 |
| GET | `/api/v1/teams/{team_id}` | Yes | 200 |
| PATCH | `/api/v1/teams/{team_id}` | Yes | 200 |
| DELETE | `/api/v1/teams/{team_id}` | Yes | 204 |
| GET | `/api/v1/workflows/` | Yes | 200 |
| POST | `/api/v1/workflows/` | Yes | 201 |
| GET | `/api/v1/workflows/{workflow_id}` | Yes | 200 |
| PATCH | `/api/v1/workflows/{workflow_id}` | Yes | 200 |
| DELETE | `/api/v1/workflows/{workflow_id}` | Yes | 204 |
| GET | `/api/v1/tasks/` | Yes | 200 |
| POST | `/api/v1/tasks/` | Yes | 201 |
| GET | `/api/v1/tasks/{task_id}` | Yes | 200 |
| PATCH | `/api/v1/tasks/{task_id}` | Yes | 200 |
| DELETE | `/api/v1/tasks/{task_id}` | Yes | 204 |
| GET | `/api/v1/events/` | Yes | 200 |
| POST | `/api/v1/events/` | Yes | 201 |
| GET | `/api/v1/prompts/definitions` | Yes | 200 |
| GET | `/api/v1/prompts/` | Yes | 200 |
| GET | `/api/v1/prompts/{name}` | Yes | 200 |
| PUT | `/api/v1/prompts/{name}` | Yes | 200 |
| DELETE | `/api/v1/prompts/{name}` | Yes | 200 |
| POST | `/api/v1/prompts/reset` | Yes | 200 |
| GET | `/api/v1/schedules/` | Yes | 200 |
| POST | `/api/v1/schedules/` | Yes | 201 |
| GET | `/api/v1/schedules/{schedule_id}` | Yes | 200 |
| PATCH | `/api/v1/schedules/{schedule_id}` | Yes | 200 |
| DELETE | `/api/v1/schedules/{schedule_id}` | Yes | 204 |
| PATCH | `/api/v1/schedules/{schedule_id}/toggle` | Yes | 200 |
| GET | `/api/v1/channels/` | Yes | 200 |
| PUT | `/api/v1/channels/{channel_type}` | Yes | 200 |
| GET | `/api/v1/connections/services` | Yes | 200 |
| GET | `/api/v1/connections/` | Yes | 200 |
| GET | `/api/v1/connections/{connection_id}` | Yes | 200 |
| POST | `/api/v1/connections/` | Yes | 201 |
| PATCH | `/api/v1/connections/{connection_id}` | Yes | 200 |
| DELETE | `/api/v1/connections/{connection_id}` | Yes | 204 |
| POST | `/api/v1/connections/{connection_id}/test` | Yes | 200 |
| GET | `/api/v1/conversations/` | Yes | 200 |
| POST | `/api/v1/conversations/` | Yes | 201 |
| GET | `/api/v1/conversations/{conversation_id}` | Yes | 200 |
| GET | `/api/v1/conversations/{conversation_id}/messages` | Yes | 200 |
| PATCH | `/api/v1/conversations/{conversation_id}` | Yes | 200 |
| DELETE | `/api/v1/conversations/{conversation_id}` | Yes | 204 |
| WS | `/api/v1/chat/ws` | Yes (query) | - |
| GET | `/api/v1/media/{filename}` | Yes (query) | 200 |
