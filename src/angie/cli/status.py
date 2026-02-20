"""angie status — show current daemon activity."""

from __future__ import annotations

import asyncio

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.command()
def status():
    """Show Angie's current status, active tasks, and recent events."""
    asyncio.run(_show_status())


async def _show_status() -> None:
    console.print("\n[bold magenta]Angie Status[/bold magenta]\n")

    # Celery inspect
    try:
        from angie.queue.celery_app import celery_app

        inspect = celery_app.control.inspect(timeout=2.0)
        active = inspect.active() or {}

        table = Table(title="Active Tasks", show_header=True)
        table.add_column("Worker")
        table.add_column("Task ID")
        table.add_column("Name")

        for worker, tasks in active.items():
            for t in tasks:
                table.add_row(worker, t.get("id", ""), t.get("name", ""))

        if not any(active.values()):
            console.print("[dim]No active tasks[/dim]")
        else:
            console.print(table)
    except Exception as e:
        console.print(f"[yellow]Could not reach Celery workers: {e}[/yellow]")

    # Registered agents
    try:
        from angie.agents.registry import get_registry

        agents = get_registry().list_all()
        console.print(f"\n[bold]Registered agents:[/bold] {len(agents)}")
        for a in agents:
            console.print(f"  • [cyan]{a.slug}[/cyan] — {a.description}")
    except Exception as e:
        console.print(f"[yellow]Could not load agents: {e}[/yellow]")

    console.print()
