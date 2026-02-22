"""Angie CLI — main entry point."""

import click

from angie.cli.chat import chat
from angie.cli.config import config
from angie.cli.configure import configure
from angie.cli.setup import setup
from angie.cli.status import status


@click.group()
@click.version_option(package_name="angie")
def cli():
    """Angie — your personal AI assistant."""


cli.add_command(setup)
cli.add_command(chat)
cli.add_command(config)
cli.add_command(configure)
cli.add_command(status)


@cli.command()
def daemon():
    """Start the Angie daemon (event loop)."""
    import asyncio

    from angie.core.loop import run_daemon

    click.echo("Starting Angie daemon...")
    asyncio.run(run_daemon())


@cli.command()
@click.argument("question")
@click.option("--user-id", default="default", help="User ID for personalised prompt context")
def ask(question: str, user_id: str):
    """Ask Angie a one-shot question and print the response."""
    import asyncio

    from rich.console import Console
    from rich.markdown import Markdown

    from angie.llm import is_llm_configured

    console = Console()

    if not is_llm_configured():
        console.print(
            "[bold red]No LLM configured.[/bold red] Set GITHUB_TOKEN or OPENAI_API_KEY in your .env."
        )
        raise SystemExit(1)

    async def _ask():
        from pydantic_ai import Agent

        from angie.core.prompts import get_prompt_manager, load_user_prompts_from_db
        from angie.llm import get_llm_model

        pm = get_prompt_manager()
        user_prompts = await load_user_prompts_from_db(user_id)
        system_prompt = pm.compose_with_user_prompts(user_prompts)
        model = get_llm_model()
        agent = Agent(model=model, system_prompt=system_prompt)
        result = await agent.run(question)
        return str(result.output)

    with console.status("[bold magenta]Thinking…[/bold magenta]"):
        answer = asyncio.run(_ask())

    console.print(Markdown(answer))
