"""Angie daemon entry point."""

import asyncio

from angie.core.loop import run_daemon

if __name__ == "__main__":
    asyncio.run(run_daemon())
