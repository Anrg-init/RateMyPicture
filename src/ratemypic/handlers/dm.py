"""Direct message handlers.

Allows users to send private notes on photos and reply to received direct messages.
"""

from html import escape
import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from ratemypic.i18n import t
from ratemypic.keyboards import (
    cancel_dm_keyboard,
    dm_notification_keyboard,
    inbox_dms_keyboard,
    welcome_choice_keyboard,
)
from ratemypic.services import (
    count_user_inbox_dms,
    create_direct_message,
    get_direct_message,
    get_post_by_id,
    get_user_by_id,
    get_user_by_telegram_id,
    get_user_inbox_dms,
)
from ratemypic.terms import TERMS_OF_SERVICE

logger = logging.getLogger(__name__)
router = Router()


class DMFlow(StatesGroup):
    """FSM states for direct messaging."""

    writing_dm = State()     # User is typing a private message for a photo author
    writing_reply = State()  # User is typing a reply to a received DM


async def prompt_send_dm(
    chat_id: int,
    telegram_id: int,
    post_id: int,
    state: FSMContext,
    bot: Bot,
    lang: str = "en",
) -> None:
    """Show the prompt asking user to type their private message."""
    post = await get_post_by_id(post_id)
    if not post:
        await bot.send_message(chat_id=chat_id, text="⚠️ Photo not found.")
        return

    user = await get_user_by_telegram_id(telegram_id)
    if user and post.user_id == user.id:
        await bot.send_message(chat_id=chat_id, text=t("dm.cannot_dm_self", lang=lang))
        return

    await state.update_data(target_post_id=post_id, recipient_id=post.user_id, language=lang)
    await state.set_state(DMFlow.writing_dm)
    await bot.send_message(
        chat_id=chat_id,
        text=t("dm.prompt_text", lang=lang),
        reply_markup=cancel_dm_keyboard(lang),
        parse_mode="HTML",
    )


async def prompt_reply_dm(
    chat_id: int,
    telegram_id: int,
    dm_id: int,
    state: FSMContext,
    bot: Bot,
    lang: str = "en",
) -> None:
    """Show the prompt asking user to type their reply."""
    dm = await get_direct_message(dm_id)
    if not dm:
        await bot.send_message(chat_id=chat_id, text="⚠️ Message not found.")
        return

    sender = await get_user_by_id(dm.sender_id)
    sender_name = sender.name if sender else "User"

    await state.update_data(
        reply_to_dm_id=dm_id,
        recipient_id=dm.sender_id,
        post_id=dm.post_id,
        language=lang,
    )
    await state.set_state(DMFlow.writing_reply)
    await bot.send_message(
        chat_id=chat_id,
        text=t("dm.reply_prompt", lang=lang, name=escape(sender_name)),
        reply_markup=cancel_dm_keyboard(lang),
        parse_mode="HTML",
    )


# ===========================================================================
# 1. User clicks [ 💌 Send DM ] on a photo
# ===========================================================================
@router.callback_query(F.data.startswith("dm:send:"))
async def on_send_dm_clicked(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle click on Send DM button below a photo."""
    await callback.answer()
    parts = (callback.data or "").split(":")
    if len(parts) < 3:
        return
    try:
        post_id = int(parts[2])
    except ValueError:
        return

    telegram_id = callback.from_user.id if callback.from_user else 0
    user = await get_user_by_telegram_id(telegram_id)
    lang = getattr(user, "language", "en") if user else "en"

    # If user is in onboarding or unregistered -> require registration first
    if user is None or user.status != "active":
        from ratemypic.handlers.registration import Registration
        from ratemypic.keyboards import terms_keyboard

        await state.update_data(language=lang, post_registration_action=f"dm:send:{post_id}")
        await state.set_state(Registration.terms)
        acceptance_prompt = t("terms.accept_prompt", lang=lang)
        terms = TERMS_OF_SERVICE.get(lang, TERMS_OF_SERVICE["en"])
        text = (
            t("dm.registration_required", lang=lang)
            + "\n\n"
            + terms
            + "\n\n"
            + acceptance_prompt
        )
        if callback.message:
            await callback.message.answer(text, reply_markup=terms_keyboard(lang), parse_mode="Markdown")
        return

    if callback.message and callback.bot:
        await prompt_send_dm(
            chat_id=callback.message.chat.id,
            telegram_id=telegram_id,
            post_id=post_id,
            state=state,
            bot=callback.bot,
            lang=lang,
        )


# ===========================================================================
# 2. User types the DM message
# ===========================================================================
@router.message(DMFlow.writing_dm, F.text)
async def process_dm_text(message: Message, state: FSMContext) -> None:
    """Save direct message and notify recipient."""
    data = await state.get_data()
    lang = data.get("language", "en")
    recipient_id = data.get("recipient_id")
    post_id = data.get("target_post_id")

    text = (message.text or "").strip()
    if not (1 <= len(text) <= 500):
        await message.answer(t("dm.invalid_length", lang=lang))
        return

    sender = await get_user_by_telegram_id(message.from_user.id if message.from_user else 0)
    if not sender or not recipient_id:
        await message.answer("⚠️ Session expired. Please try again.")
        await state.clear()
        return

    dm = await create_direct_message(
        sender_id=sender.id,
        recipient_id=recipient_id,
        text=text,
        post_id=post_id,
    )
    await state.clear()

    await message.answer(
        t("dm.sent_success", lang=lang),
        reply_markup=welcome_choice_keyboard(lang),
        parse_mode="HTML",
    )

    recipient = await get_user_by_id(recipient_id)
    if recipient and message.bot:
        rec_lang = recipient.language
        gender_str = t(f"registration.gender_{sender.gender}", lang=rec_lang) if sender.gender else "—"
        notification_text = t(
            "dm.notification",
            lang=rec_lang,
            name=escape(sender.name),
            age=sender.age,
            gender=gender_str,
            location=escape(sender.location or "—"),
            text=escape(text),
        )
        try:
            await message.bot.send_message(
                chat_id=recipient.telegram_id,
                text=notification_text,
                reply_markup=dm_notification_keyboard(dm.id, rec_lang),
                parse_mode="HTML",
            )
        except Exception as error:
            logger.warning("Could not deliver DM notification to telegram_id=%d: %s", recipient.telegram_id, error)


# ===========================================================================
# 3. User clicks [ ↩️ Reply ]
# ===========================================================================
@router.callback_query(F.data.startswith("dm:reply:"))
async def on_reply_dm_clicked(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle click on reply button below a DM notification or in inbox."""
    await callback.answer()
    parts = (callback.data or "").split(":")
    if len(parts) < 3:
        return
    try:
        dm_id = int(parts[2])
    except ValueError:
        return

    telegram_id = callback.from_user.id if callback.from_user else 0
    user = await get_user_by_telegram_id(telegram_id)
    lang = getattr(user, "language", "en") if user else "en"

    if user is None or user.status != "active":
        from ratemypic.handlers.registration import Registration
        from ratemypic.keyboards import terms_keyboard

        await state.update_data(language=lang, post_registration_action=f"dm:reply:{dm_id}")
        await state.set_state(Registration.terms)
        acceptance_prompt = t("terms.accept_prompt", lang=lang)
        terms = TERMS_OF_SERVICE.get(lang, TERMS_OF_SERVICE["en"])
        text = (
            t("dm.registration_required", lang=lang)
            + "\n\n"
            + terms
            + "\n\n"
            + acceptance_prompt
        )
        if callback.message:
            await callback.message.answer(text, reply_markup=terms_keyboard(lang), parse_mode="Markdown")
        return

    if callback.message and callback.bot:
        await prompt_reply_dm(
            chat_id=callback.message.chat.id,
            telegram_id=telegram_id,
            dm_id=dm_id,
            state=state,
            bot=callback.bot,
            lang=lang,
        )


# ===========================================================================
# 4. User types the reply
# ===========================================================================
@router.message(DMFlow.writing_reply, F.text)
async def process_reply_text(message: Message, state: FSMContext) -> None:
    """Save reply direct message and notify recipient."""
    data = await state.get_data()
    lang = data.get("language", "en")
    recipient_id = data.get("recipient_id")
    post_id = data.get("post_id")

    text = (message.text or "").strip()
    if not (1 <= len(text) <= 500):
        await message.answer(t("dm.invalid_length", lang=lang))
        return

    sender = await get_user_by_telegram_id(message.from_user.id if message.from_user else 0)
    if not sender or not recipient_id:
        await message.answer("⚠️ Session expired. Please try again.")
        await state.clear()
        return

    dm = await create_direct_message(
        sender_id=sender.id,
        recipient_id=recipient_id,
        text=text,
        post_id=post_id,
    )
    await state.clear()

    await message.answer(
        t("dm.reply_sent", lang=lang),
        reply_markup=welcome_choice_keyboard(lang),
        parse_mode="HTML",
    )

    recipient = await get_user_by_id(recipient_id)
    if recipient and message.bot:
        rec_lang = recipient.language
        reply_notification_text = t(
            "dm.reply_notification",
            lang=rec_lang,
            name=escape(sender.name),
            text=escape(text),
        )
        try:
            await message.bot.send_message(
                chat_id=recipient.telegram_id,
                text=reply_notification_text,
                reply_markup=dm_notification_keyboard(dm.id, rec_lang),
                parse_mode="HTML",
            )
        except Exception as error:
            logger.warning("Could not deliver DM reply to telegram_id=%d: %s", recipient.telegram_id, error)


# ===========================================================================
# 5. Cancel DM writing
# ===========================================================================
@router.callback_query(F.data == "dm:cancel")
async def on_cancel_dm(callback: CallbackQuery, state: FSMContext) -> None:
    """User cancelled writing a DM."""
    await state.clear()
    await callback.answer()
    telegram_id = callback.from_user.id if callback.from_user else 0
    user = await get_user_by_telegram_id(telegram_id)
    lang = getattr(user, "language", "en") if user else "en"

    if callback.message:
        await callback.message.answer(
            t("dm.cancelled", lang=lang),
            reply_markup=welcome_choice_keyboard(lang),
            parse_mode="HTML",
        )


# ===========================================================================
# 6. View My DMs Inbox (`dm:inbox:<offset>`)
# ===========================================================================
@router.callback_query(F.data.startswith("dm:inbox:"))
async def on_view_inbox_dms(callback: CallbackQuery, state: FSMContext) -> None:
    """Display received private messages in a clean list."""
    await callback.answer()
    await state.clear()

    parts = (callback.data or "").split(":")
    offset = 0
    if len(parts) >= 3:
        try:
            offset = int(parts[2])
        except ValueError:
            offset = 0

    telegram_id = callback.from_user.id if callback.from_user else 0
    user = await get_user_by_telegram_id(telegram_id)
    lang = getattr(user, "language", "en") if user else "en"

    if not user:
        return

    dms = await get_user_inbox_dms(user.id, limit=5, offset=offset)
    total = await count_user_inbox_dms(user.id)

    if not dms:
        if callback.message:
            await callback.message.answer(
                t("dm.inbox_empty", lang=lang),
                reply_markup=welcome_choice_keyboard(lang),
                parse_mode="HTML",
            )
        return

    lines = [t("dm.inbox_title", lang=lang, count=total)]
    for idx, (dm, sender) in enumerate(dms, start=offset + 1):
        s_name = escape(sender.name if sender else "User")
        s_gender = t(f"registration.gender_{sender.gender}", lang=lang) if (sender and sender.gender) else "—"
        s_loc = escape(sender.location or "—") if sender else "—"
        lines.append(
            f"\n<b>{idx}. 👤 {s_name}</b>, {sender.age if sender else '?'} ({s_gender}) 📍 {s_loc}\n"
            f"💬 <i>\"{escape(dm.text)}\"</i>\n"
            f"📅 {dm.created_at.strftime('%d.%m %H:%M')}"
        )

    text = "\n".join(lines)
    has_next = (offset + 5 < total)

    if callback.message:
        await callback.message.answer(
            text,
            reply_markup=inbox_dms_keyboard(dms, offset, has_next, lang),
            parse_mode="HTML",
        )
