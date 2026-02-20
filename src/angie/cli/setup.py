"""angie setup — first-run onboarding that generates USER_PROMPTS."""

from __future__ import annotations

import click
from rich.console import Console
from rich.prompt import Prompt

console = Console()

ONBOARDING_QUESTIONS = [
    ("personality", "How would you like Angie to communicate with you? (formal, casual, friendly, brief, etc.)"),
    ("interests", "What are your main interests and areas Angie should know about?"),
    ("schedule", "Describe your typical daily schedule (work hours, time zone, routines)"),
    ("priorities", "What are your top priorities that Angie should always keep in mind?"),
    ("communication", "Which communication channels do you prefer and in what order? (Slack, Discord, iMessage, email)"),
    ("home", "Describe your home setup relevant for Angie (smart home devices, location, etc.)"),
    ("work", "Describe your work context (role, tools, projects, workflows)"),
    ("style", "How detailed should Angie's responses be? Any language or tone preferences?"),
]


@click.command()
@click.option("--user-id", default="default", help="User ID for storing prompts")
def setup(user_id: str):
    """Interactive first-run onboarding. Generates your personal USER_PROMPTS."""
    console.print("\n[bold magenta]👋 Hi! I'm Angie, your personal AI assistant.[/bold magenta]")
    console.print("I'd like to get to know you so I can work better for you.\n")
    console.print("[dim]Answer each question — the more detail, the better I can help.[/dim]\n")

    from angie.core.prompts import get_prompt_manager
    pm = get_prompt_manager()

    for name, question in ONBOARDING_QUESTIONS:
        console.print(f"[bold cyan]{question}[/bold cyan]")
        answer = Prompt.ask("> ")
        if answer.strip():
            content = f"# {name.title()}\n\n{answer.strip()}\n"
            path = pm.save_user_prompt(user_id, name, content)
            console.print(f"[dim]  ✓ saved to {path}[/dim]\n")

    console.print("\n[bold green]✅ Setup complete! Angie knows you now.[/bold green]")
    console.print("Run [bold]angie daemon[/bold] to start Angie, or [bold]angie ask[/bold] to chat.\n")
