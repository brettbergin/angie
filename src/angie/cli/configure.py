"""angie configure — unified configuration wizard."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from angie.cli._env_utils import mask, read_env, write_env

console = Console()

# ── Known models ───────────────────────────────────────────────────────────────

_KNOWN_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "o1-mini",
    "claude-sonnet-4-20250514",
    "claude-opus-4-20250514",
    "claude-haiku-4-20250514",
]

# ── Service key catalogue ──────────────────────────────────────────────────────

_SERVICES: dict[str, list[tuple[str, str, bool]]] = {
    # (env_key, prompt_label, is_secret)
    "llm": [
        ("LLM_PROVIDER", "LLM provider (github, openai, or anthropic)", False),
        ("GITHUB_TOKEN", "GitHub OAuth token (ghp_...)", True),
        ("OPENAI_API_KEY", "OpenAI API key (sk-...)", True),
        ("ANTHROPIC_API_KEY", "Anthropic API key (sk-ant-...)", True),
        ("COPILOT_API_BASE", "Copilot API base URL", False),
    ],
    "slack": [
        ("SLACK_BOT_TOKEN", "Bot token (xoxb-...)", True),
        ("SLACK_APP_TOKEN", "App-level token (xapp-...)", True),
        ("SLACK_SIGNING_SECRET", "Signing secret", True),
    ],
    "discord": [
        ("DISCORD_BOT_TOKEN", "Bot token", True),
    ],
    "imessage": [
        ("BLUEBUBBLES_URL", "BlueBubbles server URL (e.g. https://your-server.ngrok.io)", False),
        ("BLUEBUBBLES_PASSWORD", "BlueBubbles password", True),
    ],
    "email": [
        ("EMAIL_SMTP_HOST", "SMTP host (outbound, e.g. smtp.gmail.com)", False),
        ("EMAIL_SMTP_PORT", "SMTP port", False),
        ("EMAIL_IMAP_HOST", "IMAP host (inbound, e.g. imap.gmail.com)", False),
        ("EMAIL_IMAP_PORT", "IMAP port", False),
        ("EMAIL_USERNAME", "Email address", False),
        ("EMAIL_PASSWORD", "App password", True),
    ],
    "google": [
        ("GOOGLE_CREDENTIALS_FILE", "Path to credentials.json from Google Cloud Console", False),
        ("GOOGLE_TOKEN_FILE", "Path to save OAuth token (default: token.json)", False),
    ],
    "spotify": [
        ("SPOTIFY_CLIENT_ID", "Spotify client ID", False),
        ("SPOTIFY_CLIENT_SECRET", "Spotify client secret", True),
        ("SPOTIFY_REDIRECT_URI", "Redirect URI (default: http://localhost:8080/callback)", False),
    ],
    "hue": [
        ("HUE_BRIDGE_IP", "Philips Hue bridge IP (e.g. 192.168.1.100)", False),
        ("HUE_USERNAME", "Hue API username (from bridge pairing)", True),
    ],
    "homeassistant": [
        ("HOME_ASSISTANT_URL", "Home Assistant URL (e.g. http://homeassistant.local:8123)", False),
        ("HOME_ASSISTANT_TOKEN", "Long-lived access token", True),
    ],
    "unifi": [
        ("UNIFI_HOST", "UniFi controller URL (e.g. https://192.168.1.1)", False),
        ("UNIFI_USERNAME", "Controller admin username", False),
        ("UNIFI_PASSWORD", "Controller admin password", True),
    ],
    "github": [
        ("GITHUB_PAT", "GitHub PAT for GitHub agent (separate from GITHUB_TOKEN)", True),
    ],
}


# ── configure group ────────────────────────────────────────────────────────────


@click.group()
def configure():
    """Unified Angie configuration wizard."""


# ── configure keys ─────────────────────────────────────────────────────────────


@configure.command("keys")
@click.argument("service", type=click.Choice(list(_SERVICES.keys())), metavar="SERVICE")
def keys(service: str):
    """Set API keys for SERVICE.

    SERVICE is one of: llm, slack, discord, imessage, email, google, spotify,
    hue, homeassistant, unifi, github
    """
    env = read_env()
    click.echo(f"\nConfigure {service.upper()}\n")
    updates: dict[str, str] = {}
    for env_key, label, is_secret in _SERVICES[service]:
        current = env.get(env_key)
        hint = f" (current: {mask(current)})" if current else ""
        value = click.prompt(
            f"{label}{hint}",
            hide_input=is_secret,
            default=current or "",
            show_default=False,
        )
        if value:
            updates[env_key] = value
    if updates:
        write_env(updates)
        click.echo(f"\n✓ {service.upper()} configured")
    else:
        click.echo("No changes made.")


# ── configure list ─────────────────────────────────────────────────────────────


@configure.command("list")
def list_keys():
    """Show all configured keys grouped by service."""
    env = read_env()

    table = Table(title="Angie Configuration", show_header=True, header_style="bold magenta")
    table.add_column("Service", style="bold", width=14)
    table.add_column("Variable", width=28)
    table.add_column("Status", width=12)
    table.add_column("Value")

    for service, entries in _SERVICES.items():
        for i, (env_key, _label, is_secret) in enumerate(entries):
            value = env.get(env_key)
            status = "[green]✓ set[/green]" if value else "[red]✗ not set[/red]"
            display = mask(value) if is_secret and value else (value or "")
            table.add_row(
                service.upper() if i == 0 else "",
                env_key,
                status,
                display,
            )

    console.print(table)


# ── configure model ────────────────────────────────────────────────────────────


@configure.command("model")
def model():
    """Select the LLM model and optionally set a custom API base."""
    env = read_env()
    provider = env.get("LLM_PROVIDER", "github")
    current_base = env.get("COPILOT_API_BASE", "https://api.githubcopilot.com")

    if provider == "anthropic":
        current_model = env.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        anthropic_models = [m for m in _KNOWN_MODELS if m.startswith("claude")]
    else:
        current_model = env.get("COPILOT_MODEL", "gpt-4o")

    click.echo(f"\nLLM Model Configuration (provider: {provider})\n")

    if provider == "anthropic":
        display_models = anthropic_models
    else:
        display_models = [m for m in _KNOWN_MODELS if not m.startswith("claude")]

    click.echo(
        "\n".join(f"  {'>' if m == current_model else ' '} {m}" for m in display_models)
        + "\n   (or enter custom)"
    )

    selected = click.prompt("Model", default=current_model)

    if provider == "anthropic":
        write_env({"ANTHROPIC_MODEL": selected})
    else:
        api_base = click.prompt("API base URL", default=current_base)
        write_env({"COPILOT_MODEL": selected, "COPILOT_API_BASE": api_base})
        click.echo(f"✓ API base: {api_base}")

    click.echo(f"\n✓ Model set to {selected}")


# ── configure seed ─────────────────────────────────────────────────────────────


@configure.command("seed")
def seed():
    """Seed the database with a demo user and sample data."""
    import asyncio

    console.print("\n[bold]Seeding demo data...[/bold]\n")

    try:
        asyncio.run(_seed_db())
    except Exception as exc:
        console.print(f"[bold red]✗ Seed failed:[/bold red] {exc}")
        console.print(
            "[dim]Make sure the database is running: make docker-up && make migrate[/dim]"
        )
        raise SystemExit(1) from None


async def _seed_db() -> None:
    """Insert demo records into the database (idempotent)."""
    from sqlalchemy import text

    from angie.api.auth import hash_password
    from angie.db.session import get_session_factory
    from angie.models.event import Event, EventType
    from angie.models.task import Task, TaskStatus
    from angie.models.team import Team
    from angie.models.user import User
    from angie.models.workflow import Workflow, WorkflowStep

    session_factory = get_session_factory()

    async with session_factory() as session:
        # Check idempotency marker
        result = await session.execute(
            text("SELECT id FROM users WHERE email = 'demo@angie.local' LIMIT 1")
        )
        if result.scalar_one_or_none():
            console.print("[yellow]Demo data already seeded — skipping.[/yellow]")
            return

        # ── Demo user ──────────────────────────────────────────────────────────
        demo_user = User(
            email="demo@angie.local",
            username="demo",
            hashed_password=hash_password("demo1234"),
            full_name="Angie Demo",
            is_active=True,
            is_superuser=True,
        )
        session.add(demo_user)
        await session.flush()

        # ── Sample team ────────────────────────────────────────────────────────
        email_team = Team(
            name="Email Team",
            slug="email-team",
            description="Handles all email-related tasks",
        )
        session.add(email_team)
        await session.flush()

        # ── Sample workflow ────────────────────────────────────────────────────
        workflow = Workflow(
            name="Morning Briefing",
            slug="morning-briefing",
            description="Daily morning briefing: calendar + email + Slack summary",
            trigger_event="cron",
            is_enabled=True,
        )
        session.add(workflow)
        await session.flush()

        steps = [
            WorkflowStep(
                workflow_id=workflow.id,
                order=1,
                name="Check calendar",
                config={"agent_slug": "gcal-agent"},
            ),
            WorkflowStep(
                workflow_id=workflow.id,
                order=2,
                name="Summarise email",
                config={"agent_slug": "gmail-agent"},
            ),
            WorkflowStep(
                workflow_id=workflow.id,
                order=3,
                name="Post to Slack",
                config={"agent_slug": "task-manager"},
            ),
        ]
        session.add_all(steps)

        # ── Sample events ──────────────────────────────────────────────────────
        sample_events = [
            Event(
                type=EventType.USER_MESSAGE,
                user_id=demo_user.id,
                source_channel="slack",
                payload={"message": "Hello Angie!"},
            ),
            Event(
                type=EventType.CRON,
                user_id=demo_user.id,
                source_channel="cron",
                payload={"job_id": "morning-briefing"},
            ),
            Event(
                type=EventType.SYSTEM,
                payload={"message": "Daemon started"},
            ),
            Event(
                type=EventType.TASK_COMPLETE,
                user_id=demo_user.id,
                payload={"task_id": "demo-task-1"},
            ),
            Event(
                type=EventType.WEBHOOK,
                payload={"source": "github", "event": "push"},
            ),
        ]
        session.add_all(sample_events)

        # ── Sample tasks ───────────────────────────────────────────────────────
        sample_tasks = [
            Task(
                title="Summarise inbox",
                user_id=demo_user.id,
                status=TaskStatus.SUCCESS,
                source_channel="slack",
                output_data={"summary": "3 unread emails"},
            ),
            Task(
                title="Morning briefing",
                user_id=demo_user.id,
                status=TaskStatus.PENDING,
                source_channel="cron",
            ),
            Task(
                title="Adjust living room lights",
                user_id=demo_user.id,
                status=TaskStatus.FAILURE,
                source_channel="discord",
                error="Bridge unreachable",
            ),
        ]
        session.add_all(sample_tasks)

        await session.commit()

    # ── Summary table ──────────────────────────────────────────────────────────
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("icon", style="green")
    table.add_column("item")

    table.add_row("✓", "Demo user created: [bold]demo@angie.local[/bold] / [bold]demo1234[/bold]")
    table.add_row("✓", "Team created: [bold]email-team[/bold]")
    table.add_row("✓", "Workflow created: [bold]morning-briefing[/bold] (3 steps)")
    table.add_row("✓", "5 sample events inserted")
    table.add_row("✓", "3 sample tasks inserted")

    console.print(table)
    console.print("\n[dim]Login at http://localhost:8000/api/v1/auth/token[/dim]")
