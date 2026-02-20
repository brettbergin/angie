"""angie ask — quick chat with Angie from the terminal."""

from __future__ import annotations

import asyncio

import click
from rich.console import Console
from rich.markdown import Markdown

console = Console()


@click.command()
@click.argument("message", nargs=-1, required=True)
@click.option("--user-id", default="default", help="User ID")
@click.option("--agent", default=None, help="Route directly to a specific agent slug")
def chat(message: tuple[str, ...], user_id: str, agent: str | None):
    """Ask Angie a question from the terminal.\n\n  Examples:\n\n    angie ask what tasks are running\n\n    angie ask --agent cron list my crons"""
    text = " ".join(message)
    asyncio.run(_ask(text, user_id, agent))


async def _ask(text: str, user_id: str, agent_slug: str | None) -> None:
    from angie.agents.registry import get_registry
    from angie.core.prompts import get_prompt_manager

    console.print(f"\n[dim]You:[/dim] {text}\n")

    registry = get_registry()

    task = {
        "title": text,
        "user_id": user_id,
        "input_data": {"message": text},
        "agent_slug": agent_slug,
    }

    if agent_slug:
        ag = registry.get(agent_slug)
    else:
        ag = registry.resolve(task)

    if ag:
        result = await ag.execute(task)
        console.print("[dim]Angie:[/dim]")
        console.print(Markdown(str(result)))
    else:
        # Fall back to LLM with user prompts
        pm = get_prompt_manager()
        system = pm.compose_for_user(user_id)
        from angie.agents.base import BaseAgent

        class _TempAgent(BaseAgent):
            name = "angie"
            slug = "angie"
            description = "Direct chat"
            capabilities = []

            async def execute(self, t):
                return await self.ask_llm(t["input_data"]["message"])

        temp = _TempAgent()
        response = await temp.ask_llm(text, system=system)
        console.print(f"\n[bold]Angie:[/bold] {response}\n")
