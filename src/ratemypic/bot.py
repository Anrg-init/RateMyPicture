"""Telegram bot startup and configuration.

This file sets up the bot, registers our main router, and runs polling.
"""

import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BotCommand, ErrorEvent
from dotenv import load_dotenv

from ratemypic.database import close_database
from ratemypic.handlers import router as main_router

# Set up module-specific logger
logger = logging.getLogger(__name__)


async def run_bot() -> None:
    """Start polling Telegram for messages."""
    load_dotenv()
    bot_token = os.getenv("BOT_TOKEN")

    if not bot_token:
        logger.critical("BOT_TOKEN is missing. Please add it to your .env file.")
        raise ValueError("BOT_TOKEN is missing. Add it to your .env file.")

    # 1. Create dispatcher and register our main handlers router
    dispatcher = Dispatcher()
    dispatcher.include_router(main_router)

    # Global error handler to prevent bot crashing and notify users gracefully
    @dispatcher.error()
    async def global_error_handler(event: ErrorEvent) -> bool:
        exc = event.exception
        # Ignore benign Telegram "message is not modified" errors on fast double taps
        if isinstance(exc, TelegramBadRequest) and "message is not modified" in str(exc):
            logger.debug("Ignored harmless TelegramBadRequest: message is not modified")
            return True

        logger.exception("Global handler caught exception: %s", exc)
        try:
            if event.update.callback_query:
                await event.update.callback_query.answer(
                    "⚠️ An error occurred. Please try again.", show_alert=True
                )
            elif event.update.message:
                await event.update.message.answer(
                    "⚠️ An unexpected error occurred. Please try again."
                )
        except Exception as notify_err:
            logger.debug("Could not deliver error notification to user: %s", notify_err)
        return True

    # 2. Run bot polling loop with proper logging
    async with Bot(token=bot_token) as bot:
        try:
            await bot.set_my_commands(
                [
                    BotCommand(command="start", description="Start or reopen the bot"),
                    BotCommand(command="language", description="Change language"),
                    BotCommand(command="terms", description="View Terms of Service"),
                    BotCommand(command="cancel", description="Cancel the current action"),
                    BotCommand(command="edit", description="Edit your profile or posts"),
                ]
            )
            logger.info("🤖 Bot is starting up and polling Telegram...")
            allowed_updates = dispatcher.resolve_used_update_types()
            await dispatcher.start_polling(
                bot,
                allowed_updates=allowed_updates,
                drop_pending_updates=True,
            )
        except Exception as error:
            logger.exception("Unexpected error occurred while polling: %s", error)
            raise
        finally:
            logger.info("Shutting down bot. Closing database connections...")
            await close_database()
            logger.info("Database connections closed cleanly.")
