"""Angie CLI — main entry point."""

import click

from angie.cli.chat import chat
from angie.cli.config import config
from angie.cli.prompts import prompts
from angie.cli.setup import setup
from angie.cli.status import status


@click.group()
@click.version_option(package_name="angie")
def cli():
    """Angie — your personal AI assistant."""


cli.add_command(setup)
cli.add_command(chat)
cli.add_command(config)
cli.add_command(status)
cli.add_command(prompts)


@cli.command()
def daemon():
    """Start the Angie daemon (event loop)."""
    import asyncio

    from angie.core.loop import run_daemon

    click.echo("Starting Angie daemon...")
    asyncio.run(run_daemon())
