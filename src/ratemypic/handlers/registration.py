"""Registration and onboarding handlers for new users.

This file handles the step-by-step registration conversation:
1. /start -> Select language (en / ru)
2. Accept terms of service
3. Enter name (2-30 characters)
4. Enter age (18-99)
5. Enter location (or skip)
6. Save user to PostgreSQL database
"""

from datetime import datetime, timezone
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, User as TelegramUser

from ratemypic.keyboards import (
    language_keyboard,
    location_keyboard,
    main_menu_keyboard,
    terms_keyboard,
)
from ratemypic.services import get_user_by_telegram_id, save_user
from ratemypic.terms import TERMS_OF_SERVICE

# Set up module logger
logger = logging.getLogger(__name__)

router = Router()


class Registration(StatesGroup):
    """The steps (states) in the registration conversation."""

    language = State()
    terms = State()
    name = State()
    age = State()
    location = State()


@router.message(Command("terms"))
async def terms_command(message: Message, state: FSMContext) -> None:
    """Show the current Terms of Service in the user's preferred language."""
    data = await state.get_data()
    language = data.get("language")

    if language not in TERMS_OF_SERVICE and message.from_user:
        try:
            user = await get_user_by_telegram_id(message.from_user.id)
            language = user.language if user else "en"
        except Exception as error:
            logger.warning("Could not load language preference for /terms: %s", error)
            language = "en"

    await message.answer(TERMS_OF_SERVICE.get(language, TERMS_OF_SERVICE["en"]))


# ===========================================================================
# Step 1: /start command -> Check if registered or Choose Language
# ===========================================================================
@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext) -> None:
    """Triggered when the user sends /start."""
    telegram_id = message.from_user.id if message.from_user else 0

    # 1. Check if user already exists in PostgreSQL
    try:
        existing_user = await get_user_by_telegram_id(telegram_id)
    except Exception as error:
        logger.error("Could not check user registration for telegram_id=%d: %s", telegram_id, error)
        existing_user = None

    # 2. If already registered and active -> show the two main options directly!
    if existing_user is not None and existing_user.status == "active":
        logger.info("Registered user %s (telegram_id=%d) triggered /start", existing_user.name, telegram_id)
        await state.clear()
        await message.answer(
            f"👋 Welcome back, *{existing_user.name}*!\n\n"
            "📸 Share your photos and get ratings from real people.\n"
            "See what the community thinks, rate other photos, and leave comments.\n\n"
            "What would you like to do?",
            reply_markup=main_menu_keyboard(),
            parse_mode="Markdown",
        )
        return

    # 3. If NOT registered -> start registration flow
    logger.info("New/unregistered user (telegram_id=%d) started registration", telegram_id)
    await state.clear()
    await state.set_state(Registration.language)

    await message.answer(
        "👋 Welcome to Rate My Picture!\n\n"
        "📸 Share your photos and get ratings from real people.\n"
        "See what the community thinks, rate other photos, and leave comments.\n\n"
        "🌐 Please choose your preferred language:",
        reply_markup=language_keyboard(),
    )


# ===========================================================================
# Step 2: Choose Language -> Ask Terms of Service
# ===========================================================================
@router.callback_query(Registration.language, F.data.startswith("lang:"))
async def process_language_button(callback: CallbackQuery, state: FSMContext) -> None:
    """User clicked an inline language button."""
    # Extract language code (e.g. "en" or "ru")
    lang = callback.data.split(":")[1] if callback.data else "en"
    if lang not in ("en", "ru"):
        lang = "en"

    # Save to memory
    await state.update_data(language=lang)
    await state.set_state(Registration.terms)
    await callback.answer()

    acceptance_prompt = (
        "✅ Do you accept these Terms of Service?"
        if lang == "en"
        else "✅ Вы принимаете эти условия использования?"
    )
    text = TERMS_OF_SERVICE[lang] + "\n\n" + acceptance_prompt

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            text, reply_markup=terms_keyboard(), parse_mode="Markdown"
        )


@router.message(Registration.language)
async def process_language_text(message: Message, state: FSMContext) -> None:
    """Fallback if user types language instead of clicking the button."""
    text = (message.text or "").strip().lower()

    if text in ("ru", "russian", "русский"):
        lang = "ru"
    elif text in ("en", "english"):
        lang = "en"
    else:
        await message.answer(
            "🌐 Please use the buttons below to choose a language:",
            reply_markup=language_keyboard(),
        )
        return

    await state.update_data(language=lang)
    await state.set_state(Registration.terms)
    acceptance_prompt = (
        "✅ Do you accept these Terms of Service?"
        if lang == "en"
        else "✅ Вы принимаете эти условия использования?"
    )
    await message.answer(
        TERMS_OF_SERVICE[lang] + "\n\n" + acceptance_prompt,
        reply_markup=terms_keyboard(),
    )


# ===========================================================================
# Step 3: Accept Terms -> Ask Name
# ===========================================================================
@router.callback_query(Registration.terms, F.data.startswith("terms:"))
async def process_terms_button(callback: CallbackQuery, state: FSMContext) -> None:
    """User clicked Accept or Decline on Terms of Service."""
    decision = callback.data.split(":")[1] if callback.data else ""
    await callback.answer()

    if decision != "accept":
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                "❌ You must accept the terms to use this bot.\n"
                "Send /start whenever you want to try again. 🔄"
            )
        await state.clear()
        return

    # User accepted: record timestamp and move to name step
    accepted_at = datetime.now(timezone.utc)
    await state.update_data(terms_accepted_at=accepted_at)
    await state.set_state(Registration.name)

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "✅ Terms accepted!\n\n"
            "👤 What is your name? (Between 2 and 30 characters):"
        )


@router.message(Registration.terms)
async def process_terms_text(message: Message, state: FSMContext) -> None:
    """Fallback if user types response instead of clicking the button."""
    text = (message.text or "").strip().lower()

    if text in ("yes", "agree", "accept", "i agree", "да"):
        accepted_at = datetime.now(timezone.utc)
        await state.update_data(terms_accepted_at=accepted_at)
        await state.set_state(Registration.name)
        await message.answer("✅ Terms accepted!\n\n👤 What is your name? (Between 2 and 30 characters):")
    else:
        await message.answer(
            "👇 Please click one of the buttons below to continue:",
            reply_markup=terms_keyboard(),
        )


# ===========================================================================
# Step 4: Name -> Ask Age
# ===========================================================================
@router.message(Registration.name)
async def process_name(message: Message, state: FSMContext) -> None:
    """Validate name (2 to 30 characters) and ask for age."""
    name = (message.text or "").strip()

    if not (2 <= len(name) <= 30):
        await message.answer("⚠️ Name must be between 2 and 30 characters. Please try again:")
        return

    await state.update_data(name=name)
    await state.set_state(Registration.age)
    await message.answer(f"🤝 Nice to meet you, {name}! How old are you? (Must be between 18 and 99):")


# ===========================================================================
# Step 5: Age -> Ask Location
# ===========================================================================
@router.message(Registration.age)
async def process_age(message: Message, state: FSMContext) -> None:
    """Validate age (between 18 and 99) and ask for location."""
    raw_age = (message.text or "").strip()

    if not raw_age.isdigit():
        await message.answer("🔢 Please enter your age using numbers only (e.g. 25):")
        return

    age = int(raw_age)
    if not (18 <= age <= 99):
        await message.answer(
            "⚠️ You must be between 18 and 99 years old to use Rate My Picture.\n"
            "Please enter a valid age:"
        )
        return

    await state.update_data(age=age)
    await state.set_state(Registration.location)
    await message.answer(
        "📍 Where are you located (City / Country)?\n"
        "(Optional: 2 to 60 characters, or press 'Skip location')",
        reply_markup=location_keyboard(),
    )


# ===========================================================================
# Step 6: Location -> Save to Database
# ===========================================================================
@router.callback_query(Registration.location, F.data == "loc:skip")
async def process_location_skip_button(callback: CallbackQuery, state: FSMContext) -> None:
    """User clicked 'Skip location'."""
    await callback.answer()
    if isinstance(callback.message, Message):
        await finalize_registration(
            chat_id=callback.message.chat.id,
            bot=callback.bot,
            telegram_user=callback.from_user,
            location=None,
            state=state,
        )


@router.message(Registration.location)
async def process_location_text(message: Message, state: FSMContext) -> None:
    """User typed their location (or 'skip')."""
    raw_location = (message.text or "").strip()

    if raw_location.lower() == "skip":
        location = None
    elif not (2 <= len(raw_location) <= 60):
        await message.answer(
            "⚠️ Location must be between 2 and 60 characters (or press 'Skip location'):",
            reply_markup=location_keyboard(),
        )
        return
    else:
        location = raw_location

    await finalize_registration(
        chat_id=message.chat.id,
        bot=message.bot,
        telegram_user=message.from_user,
        location=location,
        state=state,
    )


# ===========================================================================
# Finalize: Save user into PostgreSQL & send confirmation
# ===========================================================================
async def finalize_registration(
    chat_id: int,
    bot: Bot | None,
    telegram_user: TelegramUser | None,
    location: str | None,
    state: FSMContext,
) -> None:
    """Save user in the database, print confirmation to terminal, and clear state."""
    # 1. Retrieve all stored answers from memory
    data = await state.get_data()
    name = data.get("name")
    age = data.get("age")
    language = data.get("language", "en")
    terms_accepted_at: datetime = data.get("terms_accepted_at") or datetime.now(timezone.utc)

    telegram_id = telegram_user.id if telegram_user else 0
    username = f"@{telegram_user.username}" if (telegram_user and telegram_user.username) else "N/A"

    # 2. Save into PostgreSQL using our simple helper function
    try:
        await save_user(
            telegram_id=telegram_id,
            name=name,
            age=age,
            location=location,
            language=language,
            terms_accepted_at=terms_accepted_at,
        )
        save_success = True
        logger.info(
            "User registration completed: telegram_id=%d, username=%s, name='%s', age=%d, location='%s', language=%s",
            telegram_id,
            username,
            name,
            age,
            location or "None",
            language,
        )
    except Exception as error:
        logger.exception("Failed to save user telegram_id=%d to database: %s", telegram_id, error)
        save_success = False

    # 4. Clear temporary FSM conversation data
    await state.clear()

    # 5. Send confirmation message to the Telegram user with the 2 main options
    if save_success:
        confirmation = (
            f"🎉 *Registration Complete!*\n\n"
            f"👤 *Name:* {name}\n"
            f"🎂 *Age:* {age}\n"
            f"📍 *Location:* {location or 'Not provided'}\n"
            f"🌐 *Language:* {language}\n\n"
            f"✨ What would you like to do?"
        )
        if bot:
            await bot.send_message(
                chat_id=chat_id,
                text=confirmation,
                reply_markup=main_menu_keyboard(),
                parse_mode="Markdown",
            )
    else:
        confirmation = (
            "⚠️ There was an issue saving your data to the database.\n"
            "Please contact the administrator or try again later with /start. 🔄"
        )
        if bot:
            await bot.send_message(chat_id=chat_id, text=confirmation, parse_mode="Markdown")
