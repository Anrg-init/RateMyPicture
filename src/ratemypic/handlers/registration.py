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
from ratemypic.services import get_user_by_telegram_id, save_user, update_user_language
from ratemypic.terms import TERMS_OF_SERVICE
from ratemypic.i18n import t, SUPPORTED_LANGUAGES

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


@router.message(Command("language"))
@router.message(Command("lang"))
async def language_command(message: Message, state: FSMContext) -> None:
    """Allow user to change their language preference at any time."""
    telegram_id = message.from_user.id if message.from_user else 0
    user = await get_user_by_telegram_id(telegram_id)
    lang = getattr(user, "language", "en") if user else "en"

    await message.answer(
        t("registration.choose_language", lang=lang),
        reply_markup=language_keyboard(lang),
    )


@router.callback_query(F.data.startswith("lang:"))
async def process_language_switch_button(callback: CallbackQuery, state: FSMContext) -> None:
    """User clicked a language button to change their language."""
    new_lang = callback.data.split(":")[1] if callback.data else "en"
    if new_lang not in SUPPORTED_LANGUAGES:
        new_lang = "en"

    telegram_id = callback.from_user.id if callback.from_user else 0
    try:
        user = await get_user_by_telegram_id(telegram_id)
    except Exception as error:
        logger.warning("Could not query user for language switch: %s", error)
        user = None

    # 1. Update active FSM session state
    await state.update_data(language=new_lang)

    # 2. If registered, update in PostgreSQL database
    if user is not None and user.status == "active":
        await update_user_language(telegram_id, new_lang)
        await callback.answer(t("language.changed_notice", lang=new_lang))
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                t("language.changed_confirmation", lang=new_lang, language=t(f"language.name.{new_lang}", lang=new_lang)),
                reply_markup=main_menu_keyboard(new_lang),
            )
        return

    # If in onboarding state, proceed to terms
    await state.set_state(Registration.terms)
    await callback.answer()
    acceptance_prompt = t("terms.accept_prompt", lang=new_lang)
    terms = TERMS_OF_SERVICE.get(new_lang, TERMS_OF_SERVICE["en"])
    text = terms + "\n\n" + acceptance_prompt
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            text, reply_markup=terms_keyboard(new_lang), parse_mode="Markdown"
        )


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
            t("menu.welcome_back", lang=existing_user.language, name=existing_user.name),
            reply_markup=main_menu_keyboard(existing_user.language),
            parse_mode="Markdown",
        )
        return

    # 3. If NOT registered -> start registration flow
    logger.info("New/unregistered user (telegram_id=%d) started registration", telegram_id)
    await state.clear()
    await state.set_state(Registration.language)

    await message.answer(
        t("start.welcome"),
        reply_markup=language_keyboard(),
    )


# ===========================================================================
# Step 2: Choose Language -> Ask Terms of Service
# ===========================================================================
@router.callback_query(Registration.language, F.data.startswith("lang:"))
async def process_language_button(callback: CallbackQuery, state: FSMContext) -> None:
    """User clicked an inline language button during onboarding."""
    await process_language_switch_button(callback, state)


@router.message(Registration.language)
async def process_language_text(message: Message, state: FSMContext) -> None:
    """Fallback if user types language instead of clicking the button."""
    text = (message.text or "").strip().lower()

    language_names = {
        "ru": "ru", "russian": "ru", "русский": "ru",
        "en": "en", "english": "en",
        "es": "es", "spanish": "es", "español": "es", "espanol": "es",
        "pt": "pt", "portuguese": "pt", "português": "pt", "portugues": "pt",
        "id": "id", "indonesian": "id", "bahasa indonesia": "id", "bahasa": "id",
    }
    lang = language_names.get(text)
    if lang not in SUPPORTED_LANGUAGES:
        await message.answer(
            t("registration.choose_language"),
            reply_markup=language_keyboard(),
        )
        return

    await state.update_data(language=lang)
    await state.set_state(Registration.terms)
    acceptance_prompt = t("terms.accept_prompt", lang=lang)
    await message.answer(
        TERMS_OF_SERVICE.get(lang, TERMS_OF_SERVICE["en"]) + "\n\n" + acceptance_prompt,
        reply_markup=terms_keyboard(lang),
    )


# ===========================================================================
# Step 3: Accept Terms -> Ask Name
# ===========================================================================
@router.callback_query(Registration.terms, F.data.startswith("terms:"))
async def process_terms_button(callback: CallbackQuery, state: FSMContext) -> None:
    """User clicked Accept or Decline on Terms of Service."""
    decision = callback.data.split(":")[1] if callback.data else ""
    data = await state.get_data()
    lang = data.get("language", "en")
    await callback.answer()

    if decision != "accept":
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                t("terms.declined", lang=lang)
            )
        await state.clear()
        return

    # User accepted: record timestamp and move to name step
    accepted_at = datetime.now(timezone.utc)
    await state.update_data(terms_accepted_at=accepted_at)
    await state.set_state(Registration.name)

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            t("terms.accepted_name", lang=lang)
        )


@router.message(Registration.terms)
async def process_terms_text(message: Message, state: FSMContext) -> None:
    """Fallback if user types response instead of clicking the button."""
    text = (message.text or "").strip().lower()

    data = await state.get_data()
    lang = data.get("language", "en")
    if text in ("yes", "agree", "accept", "i agree", "да", "согласен", "согласна"):
        accepted_at = datetime.now(timezone.utc)
        await state.update_data(terms_accepted_at=accepted_at)
        await state.set_state(Registration.name)
        await message.answer(t("terms.accepted_name", lang=lang))
    else:
        await message.answer(
            t("terms.choose_button", lang=lang),
            reply_markup=terms_keyboard(lang),
        )


# ===========================================================================
# Step 4: Name -> Ask Age
# ===========================================================================
@router.message(Registration.name)
async def process_name(message: Message, state: FSMContext) -> None:
    """Validate name (2 to 50 characters) and ask for age."""
    name = (message.text or "").strip()
    data = await state.get_data()
    lang = data.get("language", "en")

    if not (2 <= len(name) <= 50):
        await message.answer(t("registration.name_invalid", lang=lang))
        return

    await state.update_data(name=name)
    await state.set_state(Registration.age)
    await message.answer(t("registration.greeting_age", lang=lang, name=name))


# ===========================================================================
# Step 5: Age -> Ask Location
# ===========================================================================
@router.message(Registration.age)
async def process_age(message: Message, state: FSMContext) -> None:
    """Validate age (between 18 and 99) and ask for location."""
    raw_age = (message.text or "").strip()
    data = await state.get_data()
    lang = data.get("language", "en")

    if not raw_age.isdigit():
        await message.answer(t("registration.age_numeric", lang=lang))
        return

    age = int(raw_age)
    if not (18 <= age <= 99):
        await message.answer(
            t("registration.age_invalid", lang=lang)
        )
        return

    await state.update_data(age=age)
    await state.set_state(Registration.location)
    await message.answer(
        t("registration.location_prompt", lang=lang),
        reply_markup=location_keyboard(lang),
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
    data = await state.get_data()
    lang = data.get("language", "en")

    if raw_location.lower() == "skip":
        location = None
    elif not (2 <= len(raw_location) <= 100):
        await message.answer(
            t("registration.location_invalid", lang=lang),
            reply_markup=location_keyboard(lang),
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
        confirmation = t(
            "registration.complete",
            lang=language,
            name=name,
            age=age,
            location=location or t("registration.location_missing", lang=language),
            language=t(f"language.name.{language}", lang=language),
        )
        if bot:
            await bot.send_message(
                chat_id=chat_id,
                text=confirmation,
                reply_markup=main_menu_keyboard(language),
                parse_mode="Markdown",
            )
    else:
        confirmation = t("registration.save_failed", lang=language)
        if bot:
            await bot.send_message(chat_id=chat_id, text=confirmation, parse_mode="Markdown")
