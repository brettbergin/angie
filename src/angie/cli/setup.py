"""angie setup — first-run onboarding that generates USER_PROMPTS."""

from __future__ import annotations

import asyncio

import click
from rich.console import Console
from rich.prompt import Prompt

console = Console()

ONBOARDING_QUESTIONS = [
    (
        "personality",
        "How would you like Angie to communicate with you? (formal, casual, friendly, brief, etc.)",
    ),
    ("interests", "What are your main interests and areas Angie should know about?"),
    ("schedule", "Describe your typical daily schedule (work hours, time zone, routines)"),
    ("priorities", "What are your top priorities that Angie should always keep in mind?"),
    (
        "communication",
        "Which communication channels do you prefer and in what order? (Slack, Discord, iMessage, email)",
    ),
    ("home", "Describe your home setup relevant for Angie (smart home devices, location, etc.)"),
    ("work", "Describe your work context (role, tools, projects, workflows)"),
    ("style", "How detailed should Angie's responses be? Any language or tone preferences?"),
]


async def _save_to_db(user_id: str, name: str, content: str) -> None:
    """Persist a user preference to the database."""
    from sqlalchemy import select

    from angie.db.session import get_session_factory
    from angie.models.prompt import Prompt, PromptType

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Prompt).where(
                Prompt.user_id == user_id,
                Prompt.type == PromptType.USER,
                Prompt.name == name,
            )
        )
        prompt = result.scalar_one_or_none()
        if prompt:
            prompt.content = content
            prompt.is_active = True
        else:
            prompt = Prompt(
                user_id=user_id,
                type=PromptType.USER,
                name=name,
                content=content,
                is_active=True,
            )
            session.add(prompt)
        await session.commit()


@click.command()
@click.option("--user-id", default=None, help="User ID (UUID) for storing prompts")
def setup(user_id: str | None):
    """Interactive first-run onboarding. Generates your personal USER_PROMPTS."""
    console.print("\n[bold magenta]👋 Hi! I'm Angie, your personal AI assistant.[/bold magenta]")
    console.print("I'd like to get to know you so I can work better for you.\n")
    console.print("[dim]Answer each question — the more detail, the better I can help.[/dim]\n")

    if not user_id:
        user_id = Prompt.ask("[bold yellow]Enter your user ID (UUID)[/bold yellow]")

    from angie.core.prompts import get_prompt_manager

    pm = get_prompt_manager()

    for name, question in ONBOARDING_QUESTIONS:
        console.print(f"[bold cyan]{question}[/bold cyan]")
        answer = Prompt.ask("> ")
        if answer.strip():
            content = f"# {name.title()}\n\n{answer.strip()}\n"
            # Save to DB
            try:
                asyncio.run(_save_to_db(user_id, name, content))
                console.print("[dim]  ✓ saved to database[/dim]\n")
            except Exception as exc:
                console.print(f"[dim yellow]  ⚠ DB save failed: {exc}[/dim yellow]")
                # Fallback to filesystem if DB unavailable
                path = pm.save_user_prompt(user_id, name, content)
                console.print(f"[dim]  ✓ saved to {path} (filesystem fallback)[/dim]\n")

    console.print("\n[bold green]✅ Setup complete! Angie knows you now.[/bold green]")
    console.print(
        "Run [bold]angie daemon[/bold] to start Angie, or [bold]angie ask[/bold] to chat.\n"
    )
