"""Commands and menus for editing a user's profile and posts."""

from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InputMediaPhoto, Message

from ratemypic.i18n import t
from ratemypic.keyboards import (
    confirm_delete_keyboard,
    edit_home_keyboard,
    edit_post_keyboard,
    edit_post_photo_keyboard,
    edit_posts_keyboard,
    language_keyboard,
    main_menu_keyboard,
    profile_edit_keyboard,
)
from ratemypic.services import (
    delete_post,
    delete_user,
    get_owned_post,
    get_user_by_telegram_id,
    get_user_posts,
    update_post,
    update_user_profile,
)

router = Router()
POSTS_PER_PAGE = 10


class EditFlow(StatesGroup):
    """Text and photo input steps used by the edit menus."""

    name = State()
    age = State()
    location = State()
    post_caption = State()
    post_photo = State()


async def _get_active_user(telegram_id: int):
    """Find an account that is allowed to use the edit features."""
    user = await get_user_by_telegram_id(telegram_id)
    if user is None or user.status != "active":
        return None
    return user


@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext) -> None:
    """Cancel the current flow and return active users to the main menu."""
    await state.clear()
    telegram_id = message.from_user.id if message.from_user else 0
    user = await _get_active_user(telegram_id)

    if user is None:
        await message.answer(t("edit.cancel_unregistered"))
        return

    await message.answer(
        t("edit.cancelled", lang=getattr(user, "language", "en")),
        reply_markup=main_menu_keyboard(getattr(user, "language", "en")),
    )


@router.message(Command("edit"))
async def edit_command(message: Message, state: FSMContext) -> None:
    """Open the account editing menu for registered users."""
    await state.clear()
    telegram_id = message.from_user.id if message.from_user else 0
    user = await _get_active_user(telegram_id)

    if user is None:
        await message.answer(t("edit.register_first"))
        return

    await message.answer(
        t("edit.choose", lang=getattr(user, "language", "en")),
        reply_markup=edit_home_keyboard(getattr(user, "language", "en")),
    )


@router.callback_query(F.data == "edit:home")
async def show_edit_home(callback: CallbackQuery, state: FSMContext) -> None:
    """Show the account edit menu."""
    await callback.answer()
    await state.clear()
    user = await _get_active_user(callback.from_user.id)
    lang = getattr(user, "language", "en") if user else "en"
    if callback.message:
        await callback.message.answer(
            t("edit.choose", lang=lang),
            reply_markup=edit_home_keyboard(lang),
        )


@router.callback_query(F.data == "edit:profile")
async def show_profile(callback: CallbackQuery, state: FSMContext) -> None:
    """Show current profile information and profile actions."""
    await callback.answer()
    await state.clear()
    user = await _get_active_user(callback.from_user.id)
    lang = getattr(user, "language", "en") if user else "en"
    if user is None:
        if callback.message:
            await callback.message.answer(t("edit.register_first"))
        return

    text = (
        f"{t('edit.profile_title', lang=lang)}\n\n"
        f"{t('edit.profile_name', lang=lang)}: {escape(user.name)}\n"
        f"{t('edit.profile_age', lang=lang)}: {user.age}\n"
        f"{t('edit.profile_location', lang=lang)}: {escape(user.location or t('registration.location_missing', lang=lang))}\n\n"
        f"{t('edit.profile_prompt', lang=lang)}"
    )
    if callback.message:
        await callback.message.answer(
            text,
            reply_markup=profile_edit_keyboard(lang),
            parse_mode="HTML",
        )


@router.callback_query(
    F.data.in_({"edit:profile:name", "edit:profile:age", "edit:profile:location"})
)
async def begin_profile_edit(callback: CallbackQuery, state: FSMContext) -> None:
    """Ask for a new value for the selected profile field."""
    await callback.answer()
    user = await _get_active_user(callback.from_user.id)
    if user is None:
        return

    field = (callback.data or "").split(":")[-1]
    lang = getattr(user, "language", "en")
    prompts = {
        "name": (EditFlow.name, "edit.prompt_name"),
        "age": (EditFlow.age, "edit.prompt_age"),
        "location": (EditFlow.location, "edit.prompt_location"),
    }
    edit_state, prompt_key = prompts[field]
    await state.clear()
    await state.update_data(language=lang)
    await state.set_state(edit_state)
    if callback.message:
        await callback.message.answer(t(prompt_key, lang=lang))


@router.callback_query(F.data == "edit:profile:language")
async def choose_profile_language(callback: CallbackQuery, state: FSMContext) -> None:
    """Prompt the user to select a new language from edit profile menu."""
    await callback.answer()
    user = await _get_active_user(callback.from_user.id)
    lang = getattr(user, "language", "en") if user else "en"
    if callback.message:
        await callback.message.answer(
            t("registration.choose_language", lang=lang),
            reply_markup=language_keyboard(lang),
        )


@router.callback_query(F.data == "edit:profile:location:clear")
async def clear_profile_location(callback: CallbackQuery, state: FSMContext) -> None:
    """Remove the optional profile location."""
    await callback.answer()
    user = await _get_active_user(callback.from_user.id)
    if user is None:
        return

    await update_user_profile(user.telegram_id, user.name, user.age, None)
    await state.clear()
    if callback.message:
        await callback.message.answer(
            t("edit.location_cleared", lang=getattr(user, "language", "en")),
            reply_markup=profile_edit_keyboard(getattr(user, "language", "en")),
        )


@router.message(EditFlow.name)
async def save_profile_name(message: Message, state: FSMContext) -> None:
    """Validate and save a new profile name."""
    name = (message.text or "").strip()
    data = await state.get_data()
    lang = data.get("language", "en") if isinstance(data, dict) else "en"
    if not 2 <= len(name) <= 50:
        await message.answer(t("edit.name_invalid", lang=lang))
        return

    user = await _get_active_user(message.from_user.id if message.from_user else 0)
    if user is None:
        await state.clear()
        await message.answer(t("edit.register_first", lang=lang))
        return

    await update_user_profile(user.telegram_id, name, user.age, user.location)
    await state.clear()
    await message.answer(t("edit.name_updated", lang=lang), reply_markup=edit_home_keyboard(lang))


@router.message(EditFlow.age)
async def save_profile_age(message: Message, state: FSMContext) -> None:
    """Validate and save a new profile age."""
    raw_age = (message.text or "").strip()
    data = await state.get_data()
    lang = data.get("language", "en") if isinstance(data, dict) else "en"
    if not raw_age.isdigit() or not 18 <= int(raw_age) <= 99:
        await message.answer(t("edit.age_invalid", lang=lang))
        return

    user = await _get_active_user(message.from_user.id if message.from_user else 0)
    if user is None:
        await state.clear()
        await message.answer(t("edit.register_first", lang=lang))
        return

    await update_user_profile(user.telegram_id, user.name, int(raw_age), user.location)
    await state.clear()
    await message.answer(t("edit.age_updated", lang=lang), reply_markup=edit_home_keyboard(lang))


@router.message(EditFlow.location)
async def save_profile_location(message: Message, state: FSMContext) -> None:
    """Validate and save or clear the optional profile location."""
    location = (message.text or "").strip()
    data = await state.get_data()
    lang = data.get("language", "en") if isinstance(data, dict) else "en"
    if location.lower() == "skip":
        location = ""
    elif not 2 <= len(location) <= 100:
        await message.answer(t("edit.location_invalid", lang=lang))
        return

    user = await _get_active_user(message.from_user.id if message.from_user else 0)
    if user is None:
        await state.clear()
        await message.answer(t("edit.register_first", lang=lang))
        return

    await update_user_profile(user.telegram_id, user.name, user.age, location or None)
    await state.clear()
    await message.answer(t("edit.location_updated", lang=lang), reply_markup=edit_home_keyboard(lang))


@router.callback_query(F.data.startswith("edit:posts:"))
async def show_posts_page(callback: CallbackQuery, state: FSMContext) -> None:
    """Show a page of the user's posts to edit."""
    await callback.answer()
    await state.clear()
    try:
        offset = int((callback.data or "").split(":")[-1])
    except ValueError:
        return
    if offset < 0 or offset % POSTS_PER_PAGE:
        return

    user = await _get_active_user(callback.from_user.id)
    if user is None:
        return
    lang = getattr(user, "language", "en")
    posts = await get_user_posts(user.id, limit=POSTS_PER_PAGE + 1, offset=offset)

    if not posts and offset == 0:
        if callback.message:
            await callback.message.answer(
                t("edit.no_posts", lang=lang),
                reply_markup=edit_home_keyboard(lang),
            )
        return

    choices = [(post.id, post.caption) for post in posts[:POSTS_PER_PAGE]]
    keyboard = edit_posts_keyboard(choices, offset, len(posts) > POSTS_PER_PAGE, lang)
    if callback.message:
        await callback.message.answer(t("edit.choose_post", lang=lang), reply_markup=keyboard)


@router.callback_query(F.data.startswith("edit:item:"))
async def show_post_edit_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Show edit and delete actions for an owned post."""
    await callback.answer()
    await state.clear()
    try:
        post_id = int((callback.data or "").split(":")[-1])
    except ValueError:
        return

    user = await _get_active_user(callback.from_user.id)
    lang = getattr(user, "language", "en") if user else "en"
    post = await get_owned_post(user.id, post_id) if user else None
    if post is None:
        if callback.message:
            await callback.message.answer(t("edit.post_missing", lang=lang))
        return

    if callback.message:
        photo_ids = [
            post.photo1_file_id,
            post.photo2_file_id,
            post.photo3_file_id,
        ]
        photo_ids = [photo_id for photo_id in photo_ids if photo_id]
        if len(photo_ids) == 1:
            await callback.message.answer_photo(
                photo=photo_ids[0],
                caption=f"<b>{escape(post.caption)}</b>\n\n{t('edit.choose_action', lang=lang)}",
                reply_markup=edit_post_keyboard(post.id, lang),
                parse_mode="HTML",
            )
        else:
            await callback.message.answer_media_group(
                media=[InputMediaPhoto(media=photo_id) for photo_id in photo_ids]
            )
            await callback.message.answer(
                f"<b>{escape(post.caption)}</b>\n\n{t('edit.choose_action', lang=lang)}",
                reply_markup=edit_post_keyboard(post.id, lang),
                parse_mode="HTML",
            )


@router.callback_query(F.data.startswith("edit:post:caption:"))
async def begin_post_caption_edit(callback: CallbackQuery, state: FSMContext) -> None:
    """Ask for a replacement caption for an owned post."""
    await callback.answer()
    try:
        post_id = int((callback.data or "").split(":")[-1])
    except ValueError:
        return
    user = await _get_active_user(callback.from_user.id)
    lang = getattr(user, "language", "en") if user else "en"
    post = await get_owned_post(user.id, post_id) if user else None
    if post is None:
        return

    await state.clear()
    await state.update_data(edit_post_id=post.id, language=lang)
    await state.set_state(EditFlow.post_caption)
    if callback.message:
        await callback.message.answer(t("edit.prompt_caption", lang=lang))


@router.message(EditFlow.post_caption)
async def save_post_caption(message: Message, state: FSMContext) -> None:
    """Validate and save a replacement post caption."""
    caption = (message.text or "").strip()
    data = await state.get_data()
    lang = data.get("language", "en") if isinstance(data, dict) else "en"
    if not 1 <= len(caption) <= 500:
        await message.answer(t("edit.caption_invalid", lang=lang))
        return

    user = await _get_active_user(message.from_user.id if message.from_user else 0)
    post_id = data.get("edit_post_id")
    updated = user is not None and post_id is not None and await update_post(
        user.id,
        post_id,
        caption=caption,
    )
    await state.clear()
    if updated:
        await message.answer(t("edit.caption_updated", lang=lang), reply_markup=edit_home_keyboard(lang))
    else:
        await message.answer(t("edit.post_update_failed", lang=lang))


@router.callback_query(F.data.regexp(r"^edit:post:photo:\d+$"))
async def show_post_photo_slots(callback: CallbackQuery, state: FSMContext) -> None:
    """Show replacement choices for the photos in an owned post."""
    await callback.answer()
    try:
        post_id = int((callback.data or "").split(":")[-1])
    except ValueError:
        return
    user = await _get_active_user(callback.from_user.id)
    lang = getattr(user, "language", "en") if user else "en"
    post = await get_owned_post(user.id, post_id) if user else None
    if post is None:
        return

    photo_ids = [post.photo1_file_id, post.photo2_file_id, post.photo3_file_id]
    photo_count = sum(photo_id is not None for photo_id in photo_ids)
    if callback.message:
        await callback.message.answer(
            t("edit.choose_photo", lang=lang),
            reply_markup=edit_post_photo_keyboard(post.id, photo_count, lang),
        )


@router.callback_query(F.data.regexp(r"^edit:post:photo:\d+:\d+$"))
async def begin_post_photo_edit(callback: CallbackQuery, state: FSMContext) -> None:
    """Ask for a replacement photo for the selected owned-post slot."""
    await callback.answer()
    parts = (callback.data or "").split(":")
    try:
        post_id = int(parts[-2])
        photo_number = int(parts[-1])
    except ValueError:
        return
    user = await _get_active_user(callback.from_user.id)
    lang = getattr(user, "language", "en") if user else "en"
    post = await get_owned_post(user.id, post_id) if user else None
    if post is None:
        return

    current_photo = getattr(post, f"photo{photo_number}_file_id", None)
    if current_photo is None:
        return
    await state.clear()
    await state.update_data(edit_post_id=post.id, edit_photo_number=photo_number, language=lang)
    await state.set_state(EditFlow.post_photo)
    if callback.message:
        await callback.message.answer(t("edit.prompt_photo", lang=lang, number=photo_number))


@router.message(EditFlow.post_photo, F.photo)
async def save_post_photo(message: Message, state: FSMContext) -> None:
    """Save the largest available Telegram photo size to the post."""
    user = await _get_active_user(message.from_user.id if message.from_user else 0)
    data = await state.get_data()
    lang = data.get("language", "en") if isinstance(data, dict) else "en"
    post_id = data.get("edit_post_id")
    photo_number = data.get("edit_photo_number", 1)
    photo = message.photo[-1]
    updated = user is not None and post_id is not None and await update_post(
        user.id,
        post_id,
        photo_file_id=photo.file_id,
        photo_unique_id=photo.file_unique_id,
        photo_number=photo_number,
    )
    await state.clear()
    if updated:
        await message.answer(t("edit.photo_updated", lang=lang), reply_markup=edit_home_keyboard(lang))
    else:
        await message.answer(t("edit.post_update_failed", lang=lang))


@router.message(EditFlow.post_photo)
async def reject_post_photo(message: Message) -> None:
    """Ask again when a replacement photo step receives another message type."""
    await message.answer(t("edit.send_photo"))


@router.callback_query(F.data.regexp(r"^edit:post:delete:\d+$"))
async def confirm_post_delete(callback: CallbackQuery, state: FSMContext) -> None:
    """Ask for confirmation before deleting a post."""
    await callback.answer()
    try:
        post_id = int((callback.data or "").split(":")[-1])
    except ValueError:
        return
    user = await _get_active_user(callback.from_user.id)
    lang = getattr(user, "language", "en") if user else "en"
    post = await get_owned_post(user.id, post_id) if user else None
    if post is None:
        return

    await state.clear()
    if callback.message:
        await callback.message.answer(
            t("edit.confirm_delete_post", lang=lang),
            reply_markup=confirm_delete_keyboard(
                f"edit:post:delete:confirm:{post_id}",
                f"edit:item:{post_id}",
                lang,
            ),
        )


@router.callback_query(F.data.startswith("edit:post:delete:confirm:"))
async def delete_owned_post(callback: CallbackQuery, state: FSMContext) -> None:
    """Delete an owned post after the user confirms."""
    await callback.answer()
    try:
        post_id = int((callback.data or "").split(":")[-1])
    except ValueError:
        return
    user = await _get_active_user(callback.from_user.id)
    lang = getattr(user, "language", "en") if user else "en"
    deleted = user is not None and await delete_post(user.id, post_id)
    await state.clear()
    if callback.message:
        text = t("edit.post_deleted", lang=lang) if deleted else t("edit.post_missing_short", lang=lang)
        await callback.message.answer(text, reply_markup=edit_home_keyboard(lang))


@router.callback_query(F.data == "edit:account:delete")
async def confirm_account_delete(callback: CallbackQuery, state: FSMContext) -> None:
    """Ask for confirmation before deleting the account."""
    await callback.answer()
    await state.clear()
    user = await _get_active_user(callback.from_user.id)
    lang = getattr(user, "language", "en") if user else "en"
    if callback.message:
        await callback.message.answer(
            t("edit.confirm_delete_account", lang=lang),
            reply_markup=confirm_delete_keyboard(
                "edit:account:delete:confirm",
                "edit:home",
                lang,
            ),
        )


@router.callback_query(F.data == "edit:account:delete:confirm")
async def delete_account(callback: CallbackQuery, state: FSMContext) -> None:
    """Delete the user's account after confirmation."""
    await callback.answer()
    user = await _get_active_user(callback.from_user.id)
    lang = getattr(user, "language", "en") if user else "en"
    deleted = await delete_user(callback.from_user.id)
    await state.clear()
    if callback.message:
        if deleted:
            await callback.message.answer(t("edit.account_deleted", lang=lang))
        else:
            await callback.message.answer(t("edit.account_missing", lang=lang))