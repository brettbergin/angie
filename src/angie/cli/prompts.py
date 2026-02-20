"""angie prompts — manage USER_PROMPTS."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
def prompts():
    """Manage your personal USER_PROMPTS."""


@prompts.command("list")
@click.option("--user-id", default="default")
def list_prompts(user_id: str):
    """List all USER_PROMPT files for a user."""
    from angie.core.prompts import get_prompt_manager
    pm = get_prompt_manager()
    user_dir = pm.user_prompts_dir / user_id

    if not user_dir.exists():
        console.print("[dim]No prompts found. Run [bold]angie setup[/bold] first.[/dim]")
        return

    table = Table(title=f"USER_PROMPTS for {user_id}")
    table.add_column("File")
    table.add_column("Size")
    for f in sorted(user_dir.glob("*.md")):
        table.add_row(f.name, f"{f.stat().st_size} bytes")
    console.print(table)


@prompts.command()
@click.argument("name")
@click.option("--user-id", default="default")
def edit(name: str, user_id: str):
    """Open a USER_PROMPT in your default editor."""
    from angie.core.prompts import get_prompt_manager
    pm = get_prompt_manager()
    path = pm.user_prompts_dir / user_id / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(f"# {name.title()}\n\n", encoding="utf-8")

    click.edit(filename=str(path))
    pm.invalidate_cache()
    console.print(f"[green]✓ Updated {path}[/green]")


@prompts.command()
@click.option("--user-id", default="default")
@click.confirmation_option(prompt="Reset ALL user prompts? This cannot be undone.")
def reset(user_id: str):
    """Delete all USER_PROMPTS for a user."""
    from angie.core.prompts import get_prompt_manager
    pm = get_prompt_manager()
    user_dir = pm.user_prompts_dir / user_id

    if user_dir.exists():
        import shutil
        shutil.rmtree(user_dir)
        pm.invalidate_cache()
        console.print(f"[green]✓ Cleared prompts for {user_id}[/green]")
    else:
        console.print("[dim]No prompts to reset.[/dim]")
