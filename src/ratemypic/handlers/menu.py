"""Main menu navigation handlers.

Handles returning to the main menu from other views.
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from ratemypic.keyboards import main_menu_keyboard

router = Router()


# ===========================================================================
# Back to Main Menu
# ===========================================================================
@router.callback_query(F.data == "menu:back")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Return to main menu from any sub-view."""
    await callback.answer()
    await state.clear()

    if callback.message:
        await callback.message.answer(
            "🏠 Main Menu\n\nWhat would you like to do?",
            reply_markup=main_menu_keyboard(),
        )
