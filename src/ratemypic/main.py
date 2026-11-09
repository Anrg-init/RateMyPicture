"""Command-line entry point for the Telegram bot."""

import asyncio

from ratemypic.bot import run_bot
from ratemypic.logging_config import setup_logging


def main() -> None:
    """Initialize logging and start the bot's event loop."""
    setup_logging()
    asyncio.run(run_bot())
