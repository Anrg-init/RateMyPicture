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
from html import escape
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, User as TelegramUser

from ratemypic.keyboards import (
    country_selection_keyboard,
    gender_keyboard,
    language_keyboard,
    location_keyboard,
    main_menu_keyboard,
    name_confirm_keyboard,
    target_gender_keyboard,
    terms_keyboard,
    welcome_choice_keyboard,
)
from ratemypic.services import get_user_by_telegram_id, save_user, update_user_language
from ratemypic.terms import TERMS_OF_SERVICE
from ratemypic.i18n import t, SUPPORTED_LANGUAGES
from ratemypic.handlers.rating import send_next_post

# Set up module logger
logger = logging.getLogger(__name__)

router = Router()


class Registration(StatesGroup):
    """The steps (states) in the registration conversation."""

    language = State()
    target_gender = State()
    target_country = State()
    name_confirm = State()
    name = State()
    age = State()
    gender = State()
    country = State()
    terms = State()
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
    """User clicked a language button to change their language or start."""
    new_lang = callback.data.split(":")[1] if callback.data else "en"
    if new_lang not in SUPPORTED_LANGUAGES:
        new_lang = "en"

    telegram_id = callback.from_user.id if callback.from_user else 0
    try:
        user = await get_user_by_telegram_id(telegram_id)
    except Exception as error:
        logger.warning("Could not query user for language switch: %s", error)
        user = None

    raw_name = getattr(callback.from_user, "first_name", "") if callback.from_user else ""
    if not isinstance(raw_name, str):
        first_name = "User"
    else:
        first_name = raw_name.strip()

    if len(first_name) < 2:
        user_name = "User"
    elif len(first_name) > 50:
        user_name = first_name[:50]
    else:
        user_name = first_name

    now = datetime.now(timezone.utc)

    # If already registered and active, update language
    if user is not None and user.status == "active":
        await update_user_language(telegram_id, new_lang)
        display_name = user.name
        await state.clear()
        await callback.answer()
        welcome_text = t("menu.welcome_back", lang=new_lang, name=display_name)
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                welcome_text,
                reply_markup=welcome_choice_keyboard(new_lang),
                parse_mode="Markdown",
            )
        return

    # New / onboarding user: set language in state, move to Target Gender question!
    await state.update_data(language=new_lang)
    await state.set_state(Registration.target_gender)
    await callback.answer()

    prompt_text = t("matching.prompt_target_gender", lang=new_lang)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            prompt_text,
            reply_markup=target_gender_keyboard(new_lang),
            parse_mode="HTML",
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
            reply_markup=welcome_choice_keyboard(existing_user.language),
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
    await state.set_state(Registration.target_gender)
    await message.answer(
        t("matching.prompt_target_gender", lang=lang),
        reply_markup=target_gender_keyboard(lang),
        parse_mode="HTML",
    )


# ===========================================================================
# Step 2: Choose Target Gender -> Ask Target Country
# ===========================================================================
@router.callback_query(Registration.target_gender, F.data.startswith("target_gender:"))
async def process_target_gender_button(callback: CallbackQuery, state: FSMContext) -> None:
    """User selected who they want to rate (Girls, Guys, Anyone)."""
    await callback.answer()
    t_gender = callback.data.split(":")[1] if callback.data else "any"
    if t_gender not in ("female", "male", "any"):
        t_gender = "any"

    await state.update_data(target_gender=t_gender)
    data = await state.get_data()
    lang = data.get("language", "en")

    await state.set_state(Registration.target_country)
    prompt_text = t("matching.prompt_target_country", lang=lang)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            prompt_text,
            reply_markup=country_selection_keyboard("target_country", lang),
            parse_mode="HTML",
        )


# ===========================================================================
# Step 3: Choose Target Country -> 1-Tap Name Confirmation
# ===========================================================================
@router.callback_query(Registration.target_country, F.data.startswith("target_country:"))
async def process_target_country_button(callback: CallbackQuery, state: FSMContext) -> None:
    """User selected target country preference."""
    await callback.answer()
    t_country = callback.data.split(":")[1] if callback.data else "all"

    await state.update_data(target_country=t_country)
    data = await state.get_data()
    lang = data.get("language", "en")

    raw_name = callback.from_user.first_name if callback.from_user else ""
    candidate_name = (raw_name or "").strip()
    if 2 <= len(candidate_name) <= 50:
        await state.update_data(name=candidate_name)
        await state.set_state(Registration.name_confirm)
        prompt_text = t("registration.name_confirm_prompt", lang=lang, name=escape(candidate_name))
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                prompt_text,
                reply_markup=name_confirm_keyboard(lang),
                parse_mode="HTML",
            )
    else:
        await state.set_state(Registration.name)
        prompt_text = t("registration.ask_name", lang=lang)
        if isinstance(callback.message, Message):
            await callback.message.edit_text(prompt_text, parse_mode="HTML")


@router.callback_query(Registration.name_confirm, F.data == "name:confirm")
async def process_name_confirm_yes(callback: CallbackQuery, state: FSMContext) -> None:
    """User confirmed their Telegram name with 1 tap."""
    await callback.answer()
    data = await state.get_data()
    lang = data.get("language", "en")
    name = data.get("name", "User")

    await state.set_state(Registration.age)
    prompt_text = t("registration.greeting_age", lang=lang, name=escape(name))
    if isinstance(callback.message, Message):
        await callback.message.edit_text(prompt_text, parse_mode="HTML")


@router.callback_query(Registration.name_confirm, F.data == "name:change")
async def process_name_confirm_change(callback: CallbackQuery, state: FSMContext) -> None:
    """User wants to type a custom name."""
    await callback.answer()
    data = await state.get_data()
    lang = data.get("language", "en")

    await state.set_state(Registration.name)
    prompt_text = t("registration.ask_custom_name", lang=lang)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(prompt_text, parse_mode="HTML")


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
    await message.answer(t("registration.greeting_age", lang=lang, name=escape(name)), parse_mode="HTML")


# ===========================================================================
# Step 5: Age -> Ask User's Own Gender
# ===========================================================================
@router.message(Registration.age)
async def process_age(message: Message, state: FSMContext) -> None:
    """Validate age (between 18 and 99) and ask for gender."""
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
    await state.set_state(Registration.gender)
    await message.answer(
        t("registration.gender_prompt", lang=lang),
        reply_markup=gender_keyboard(lang),
        parse_mode="HTML",
    )


# ===========================================================================
# Step 6: Gender -> Ask User's Own Country
# ===========================================================================
@router.callback_query(Registration.gender, F.data.startswith("gender:"))
async def process_gender_button(callback: CallbackQuery, state: FSMContext) -> None:
    """User selected their gender via button."""
    await callback.answer()
    gender = callback.data.split(":")[1] if callback.data else "male"
    if gender not in ("male", "female"):
        gender = "male"

    await state.update_data(gender=gender)
    data = await state.get_data()
    lang = data.get("language", "en")

    await state.set_state(Registration.country)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            t("registration.country_prompt", lang=lang),
            reply_markup=country_selection_keyboard("user_country", lang),
            parse_mode="HTML",
        )


# ===========================================================================
# Step 7: User's Country -> Finalize Registration
# ===========================================================================
@router.callback_query(Registration.country, F.data.startswith("user_country:"))
async def process_user_country_button(callback: CallbackQuery, state: FSMContext) -> None:
    """User selected their country via 1-tap button."""
    await callback.answer()
    country_code = callback.data.split(":")[1] if callback.data else "other"
    await state.update_data(country=country_code)

    if isinstance(callback.message, Message):
        await finalize_registration(
            chat_id=callback.message.chat.id,
            bot=callback.bot,
            telegram_user=callback.from_user,
            country=country_code,
            state=state,
        )


# Legacy fallbacks for terms/location if old sessions trigger them
@router.callback_query(Registration.terms, F.data.startswith("terms:"))
async def process_legacy_terms(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    lang = data.get("language", "en")
    await state.set_state(Registration.target_gender)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            t("matching.prompt_target_gender", lang=lang),
            reply_markup=target_gender_keyboard(lang),
            parse_mode="HTML",
        )


@router.callback_query(Registration.location, F.data == "loc:skip")
async def process_location_skip_button(callback: CallbackQuery, state: FSMContext) -> None:
    """Fallback skip button."""
    await callback.answer()
    if isinstance(callback.message, Message):
        await finalize_registration(
            chat_id=callback.message.chat.id,
            bot=callback.bot,
            telegram_user=callback.from_user,
            country="other",
            state=state,
        )


@router.message(Registration.location)
async def process_location_text(message: Message, state: FSMContext) -> None:
    """Fallback typed location."""
    await finalize_registration(
        chat_id=message.chat.id,
        bot=message.bot,
        telegram_user=message.from_user,
        country="other",
        state=state,
    )


# ===========================================================================
# Finalize: Save user into PostgreSQL & launch rating feed
# ===========================================================================
async def finalize_registration(
    chat_id: int,
    bot: Bot | None,
    telegram_user: TelegramUser | None,
    country: str | None,
    state: FSMContext,
) -> None:
    """Save user in the database, send welcome confirmation, and start the feed."""
    data = await state.get_data()
    name = data.get("name", "User")
    age = data.get("age", 21)
    gender = data.get("gender", "male")
    target_gender = data.get("target_gender", "any")
    target_country = data.get("target_country", "all")
    language = data.get("language", "en")
    terms_accepted_at = datetime.now(timezone.utc)

    telegram_id = telegram_user.id if telegram_user else 0
    username = f"@{telegram_user.username}" if (telegram_user and telegram_user.username) else "N/A"

    try:
        user = await save_user(
            telegram_id=telegram_id,
            name=name,
            age=age,
            location=None,
            country=country,
            target_gender=target_gender,
            target_country=target_country,
            language=language,
            terms_accepted_at=terms_accepted_at,
            status="active",
            gender=gender,
        )
        save_success = True
        logger.info(
            "User registration completed: telegram_id=%d, username=%s, name='%s', age=%d, country=%s, gender=%s, target_gender=%s, target_country=%s",
            telegram_id, username, name, age, country, gender, target_gender, target_country
        )
    except Exception as error:
        logger.exception("Failed to save user telegram_id=%d: %s", telegram_id, error)
        save_success = False
        user = None

    target_action = data.get("post_registration_action")
    await state.clear()

    if save_success and user is not None:
        country_display = t(f"country.{country}", lang=language) if country in ("in", "ph", "ru", "us", "es", "br", "id", "other") else (country or "—")
        confirmation = t(
            "registration.complete",
            lang=language,
            name=escape(name),
            age=age,
            location=country_display,
            language=t(f"language.name.{language}", lang=language),
        )

        if target_action == "post:create":
            from ratemypic.handlers.posts import CreatePost
            from ratemypic.keyboards import post_photo_count_keyboard
            await state.update_data(language=language)
            await state.set_state(CreatePost.count)
            if bot:
                await bot.send_message(chat_id=chat_id, text=confirmation, parse_mode="HTML")
                await bot.send_message(
                    chat_id=chat_id,
                    text=t("post.ask_photo_count", lang=language),
                    reply_markup=post_photo_count_keyboard(language),
                )
        elif target_action == "menu:feedback":
            from ratemypic.handlers.posts import render_user_feedback
            if bot:
                await bot.send_message(chat_id=chat_id, text=confirmation, parse_mode="HTML")
                await render_user_feedback(chat_id=chat_id, bot=bot, telegram_id=telegram_id, lang=language)
        elif target_action and target_action.startswith("dm:send:"):
            from ratemypic.handlers.dm import prompt_send_dm
            post_id = int(target_action.split(":")[2])
            if bot:
                await bot.send_message(chat_id=chat_id, text=confirmation, parse_mode="HTML")
                await prompt_send_dm(chat_id=chat_id, telegram_id=telegram_id, post_id=post_id, state=state, bot=bot, lang=language)
        elif target_action and target_action.startswith("dm:reply:"):
            from ratemypic.handlers.dm import prompt_reply_dm
            dm_id = int(target_action.split(":")[2])
            if bot:
                await bot.send_message(chat_id=chat_id, text=confirmation, parse_mode="HTML")
                await prompt_reply_dm(chat_id=chat_id, telegram_id=telegram_id, dm_id=dm_id, state=state, bot=bot, lang=language)
        else:
            if bot:
                await bot.send_message(chat_id=chat_id, text=confirmation, parse_mode="HTML")
                await state.update_data(rating_turn=0, language=language)
                await bot.send_message(
                    chat_id=chat_id,
                    text=t("rating.entry_title", lang=language),
                    parse_mode="HTML",
                )
                await send_next_post(
                    chat_id=chat_id,
                    user_id=user.id,
                    state=state,
                    bot=bot,
                )
    else:
        confirmation = t("registration.save_failed", lang=language)
        if bot:
            await bot.send_message(chat_id=chat_id, text=confirmation, parse_mode="HTML")
