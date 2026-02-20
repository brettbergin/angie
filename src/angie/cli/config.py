"""angie config — configure channel integrations."""

from __future__ import annotations

import click
from rich.console import Console
from rich.prompt import Prompt

console = Console()


@click.group()
def config():
    """Configure Angie channel integrations."""


@config.command()
def slack():
    """Configure Slack integration."""
    console.print("\n[bold]Slack Integration Setup[/bold]\n")
    bot_token = Prompt.ask("Bot token (xoxb-...)")
    app_token = Prompt.ask("App-level token (xapp-...)", default="")
    signing_secret = Prompt.ask("Signing secret")
    _write_env(
        {
            "SLACK_BOT_TOKEN": bot_token,
            "SLACK_APP_TOKEN": app_token,
            "SLACK_SIGNING_SECRET": signing_secret,
        }
    )
    console.print("[green]✓ Slack configured[/green]")


@config.command()
def discord():
    """Configure Discord integration."""
    console.print("\n[bold]Discord Integration Setup[/bold]\n")
    bot_token = Prompt.ask("Bot token")
    _write_env({"DISCORD_BOT_TOKEN": bot_token})
    console.print("[green]✓ Discord configured[/green]")


@config.command()
def imessage():
    """Configure iMessage via BlueBubbles."""
    console.print("\n[bold]BlueBubbles (iMessage) Setup[/bold]\n")
    console.print("[dim]Requires BlueBubbles Server running on macOS.[/dim]\n")
    url = Prompt.ask("BlueBubbles server URL (e.g. https://your-server.ngrok.io)")
    password = Prompt.ask("BlueBubbles password", password=True)
    _write_env({"BLUEBUBBLES_URL": url, "BLUEBUBBLES_PASSWORD": password})
    console.print("[green]✓ iMessage configured[/green]")


@config.command()
def email():
    """Configure email integration (SMTP + IMAP)."""
    console.print("\n[bold]Email Setup[/bold]\n")
    smtp_host = Prompt.ask("SMTP host (outbound)", default="smtp.gmail.com")
    smtp_port = Prompt.ask("SMTP port", default="587")
    imap_host = Prompt.ask("IMAP host (inbound)", default="imap.gmail.com")
    imap_port = Prompt.ask("IMAP port", default="993")
    username = Prompt.ask("Username / email address")
    password = Prompt.ask("App password", password=True)
    _write_env(
        {
            "EMAIL_SMTP_HOST": smtp_host,
            "EMAIL_SMTP_PORT": smtp_port,
            "EMAIL_IMAP_HOST": imap_host,
            "EMAIL_IMAP_PORT": imap_port,
            "EMAIL_USERNAME": username,
            "EMAIL_PASSWORD": password,
        }
    )
    console.print("[green]✓ Email configured[/green]")


@config.command()
def channels():
    """Show the status of all configured channels."""
    from angie.config import get_settings

    from rich.table import Table

    s = get_settings()
    table = Table(title="Channel Status", show_header=True)
    table.add_column("Channel", style="bold")
    table.add_column("Configured")

    def _status(val: str | None) -> str:
        return "[green]✓ yes[/green]" if val else "[red]✗ no[/red]"

    table.add_row("Slack", _status(s.slack_bot_token))
    table.add_row("Discord", _status(s.discord_bot_token))
    table.add_row("iMessage (BlueBubbles)", _status(s.bluebubbles_url))
    table.add_row("Email (SMTP)", _status(s.email_smtp_host))
    table.add_row("Email (IMAP receive)", _status(s.email_imap_host))
    console.print(table)


def _write_env(values: dict[str, str]) -> None:
    """Append / update .env file with key=value pairs."""
    env_path = ".env"
    try:
        with open(env_path) as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []

    existing_keys = {line.split("=")[0].strip() for line in lines if "=" in line}
    with open(env_path, "a") as f:
        for key, value in values.items():
            if key not in existing_keys and value:
                f.write(f"{key}={value}\n")
    console.print(f"[dim]Updated {env_path}[/dim]")
