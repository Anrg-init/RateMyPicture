"""Main menu navigation handlers.

Handles returning to the main menu from other views.
"""

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ratemypic.i18n import t
from ratemypic.keyboards import main_menu_keyboard, welcome_choice_keyboard
from ratemypic.services import get_user_by_telegram_id

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("menu"))
async def menu_command(message: Message, state: FSMContext) -> None:
    """Show the main menu when user sends /menu."""
    await state.clear()
    telegram_id = message.from_user.id if message.from_user else 0
    lang = "en"
    try:
        user = await get_user_by_telegram_id(telegram_id)
        if user is not None:
            lang = getattr(user, "language", "en")
    except Exception as error:
        logger.warning("Could not load language for /menu: %s", error)

    await message.answer(
        t("menu.title", lang=lang),
        reply_markup=welcome_choice_keyboard(lang),
    )


# ===========================================================================
# Back to Main Menu
# ===========================================================================
@router.callback_query(F.data == "menu:back")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Return to main menu from any sub-view."""
    data = await state.get_data()
    lang = data.get("language", "en")
    try:
        user = await get_user_by_telegram_id(callback.from_user.id)
        if user is not None:
            lang = getattr(user, "language", lang)
    except Exception as error:
        logger.warning("Could not load language preference for main menu: %s", error)
    await callback.answer()
    await state.clear()

    if callback.message:
        await callback.message.answer(
            t("menu.title", lang=lang),
            reply_markup=welcome_choice_keyboard(lang),
        )
