"""Commands and menus for editing a user's profile and posts."""

from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InputMediaPhoto, Message

from ratemypic.keyboards import (
    confirm_delete_keyboard,
    edit_home_keyboard,
    edit_post_keyboard,
    edit_post_photo_keyboard,
    edit_posts_keyboard,
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
        await message.answer("Current action cancelled. Send /start to begin.")
        return

    await message.answer(
        "Current action cancelled. What would you like to do?",
        reply_markup=main_menu_keyboard(),
    )


@router.message(Command("edit"))
async def edit_command(message: Message, state: FSMContext) -> None:
    """Open the account editing menu for registered users."""
    await state.clear()
    telegram_id = message.from_user.id if message.from_user else 0
    user = await _get_active_user(telegram_id)

    if user is None:
        await message.answer("Please register first using /start.")
        return

    await message.answer(
        "✏️ What would you like to edit?",
        reply_markup=edit_home_keyboard(),
    )


@router.callback_query(F.data == "edit:home")
async def show_edit_home(callback: CallbackQuery, state: FSMContext) -> None:
    """Show the account edit menu."""
    await callback.answer()
    await state.clear()
    if callback.message:
        await callback.message.answer(
            "✏️ What would you like to edit?",
            reply_markup=edit_home_keyboard(),
        )


@router.callback_query(F.data == "edit:profile")
async def show_profile(callback: CallbackQuery, state: FSMContext) -> None:
    """Show current profile information and profile actions."""
    await callback.answer()
    await state.clear()
    user = await _get_active_user(callback.from_user.id)
    if user is None:
        if callback.message:
            await callback.message.answer("Please register first using /start.")
        return

    text = (
        "👤 <b>Your Profile</b>\n\n"
        f"Name: {escape(user.name)}\n"
        f"Age: {user.age}\n"
        f"Location: {escape(user.location or 'Not provided')}\n\n"
        "Choose a field to change:"
    )
    if callback.message:
        await callback.message.answer(
            text,
            reply_markup=profile_edit_keyboard(),
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
    prompts = {
        "name": (EditFlow.name, "Enter your name (2 to 30 characters):"),
        "age": (EditFlow.age, "Enter your age (18 to 99):"),
        "location": (EditFlow.location, "Enter your location (2 to 60 characters), or type 'skip' to clear it:"),
    }
    edit_state, prompt = prompts[field]
    await state.clear()
    await state.set_state(edit_state)
    if callback.message:
        await callback.message.answer(prompt)


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
            "Location cleared.",
            reply_markup=profile_edit_keyboard(),
        )


@router.message(EditFlow.name)
async def save_profile_name(message: Message, state: FSMContext) -> None:
    """Validate and save a new profile name."""
    name = (message.text or "").strip()
    if not 2 <= len(name) <= 30:
        await message.answer("Name must be between 2 and 30 characters. Try again:")
        return

    user = await _get_active_user(message.from_user.id if message.from_user else 0)
    if user is None:
        await state.clear()
        await message.answer("Please register first using /start.")
        return

    await update_user_profile(user.telegram_id, name, user.age, user.location)
    await state.clear()
    await message.answer("Name updated.", reply_markup=edit_home_keyboard())


@router.message(EditFlow.age)
async def save_profile_age(message: Message, state: FSMContext) -> None:
    """Validate and save a new profile age."""
    raw_age = (message.text or "").strip()
    if not raw_age.isdigit() or not 18 <= int(raw_age) <= 99:
        await message.answer("Age must be a number from 18 to 99. Try again:")
        return

    user = await _get_active_user(message.from_user.id if message.from_user else 0)
    if user is None:
        await state.clear()
        await message.answer("Please register first using /start.")
        return

    await update_user_profile(user.telegram_id, user.name, int(raw_age), user.location)
    await state.clear()
    await message.answer("Age updated.", reply_markup=edit_home_keyboard())


@router.message(EditFlow.location)
async def save_profile_location(message: Message, state: FSMContext) -> None:
    """Validate and save or clear the optional profile location."""
    location = (message.text or "").strip()
    if location.lower() == "skip":
        location = ""
    elif not 2 <= len(location) <= 60:
        await message.answer("Location must be 2 to 60 characters, or type 'skip':")
        return

    user = await _get_active_user(message.from_user.id if message.from_user else 0)
    if user is None:
        await state.clear()
        await message.answer("Please register first using /start.")
        return

    await update_user_profile(user.telegram_id, user.name, user.age, location or None)
    await state.clear()
    await message.answer("Location updated.", reply_markup=edit_home_keyboard())


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
    posts = await get_user_posts(user.id, limit=POSTS_PER_PAGE + 1, offset=offset)

    if not posts and offset == 0:
        if callback.message:
            await callback.message.answer(
                "You haven't created any posts yet.",
                reply_markup=edit_home_keyboard(),
            )
        return

    choices = [(post.id, post.caption) for post in posts[:POSTS_PER_PAGE]]
    keyboard = edit_posts_keyboard(choices, offset, len(posts) > POSTS_PER_PAGE)
    if callback.message:
        await callback.message.answer("Choose one of your posts:", reply_markup=keyboard)


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
    post = await get_owned_post(user.id, post_id) if user else None
    if post is None:
        if callback.message:
            await callback.message.answer("That post could not be found in your account.")
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
                caption=f"<b>{escape(post.caption)}</b>\n\nChoose an action:",
                reply_markup=edit_post_keyboard(post.id),
                parse_mode="HTML",
            )
        else:
            await callback.message.answer_media_group(
                media=[InputMediaPhoto(media=photo_id) for photo_id in photo_ids]
            )
            await callback.message.answer(
                f"<b>{escape(post.caption)}</b>\n\nChoose an action:",
                reply_markup=edit_post_keyboard(post.id),
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
    post = await get_owned_post(user.id, post_id) if user else None
    if post is None:
        return

    await state.clear()
    await state.update_data(edit_post_id=post.id)
    await state.set_state(EditFlow.post_caption)
    if callback.message:
        await callback.message.answer("Enter a new caption (1 to 150 characters):")


@router.message(EditFlow.post_caption)
async def save_post_caption(message: Message, state: FSMContext) -> None:
    """Validate and save a replacement post caption."""
    caption = (message.text or "").strip()
    if not 1 <= len(caption) <= 150:
        await message.answer("Caption must be between 1 and 150 characters. Try again:")
        return

    user = await _get_active_user(message.from_user.id if message.from_user else 0)
    data = await state.get_data()
    post_id = data.get("edit_post_id")
    updated = user is not None and post_id is not None and await update_post(
        user.id,
        post_id,
        caption=caption,
    )
    await state.clear()
    if updated:
        await message.answer("Caption updated.", reply_markup=edit_home_keyboard())
    else:
        await message.answer("That post could not be updated. Open /edit and try again.")


@router.callback_query(F.data.regexp(r"^edit:post:photo:\d+$"))
async def show_post_photo_slots(callback: CallbackQuery, state: FSMContext) -> None:
    """Show replacement choices for the photos in an owned post."""
    await callback.answer()
    try:
        post_id = int((callback.data or "").split(":")[-1])
    except ValueError:
        return
    user = await _get_active_user(callback.from_user.id)
    post = await get_owned_post(user.id, post_id) if user else None
    if post is None:
        return

    photo_ids = [post.photo1_file_id, post.photo2_file_id, post.photo3_file_id]
    photo_count = sum(photo_id is not None for photo_id in photo_ids)
    if callback.message:
        await callback.message.answer(
            "Choose which photo you want to replace:",
            reply_markup=edit_post_photo_keyboard(post.id, photo_count),
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
    post = await get_owned_post(user.id, post_id) if user else None
    if post is None:
        return

    current_photo = getattr(post, f"photo{photo_number}_file_id", None)
    if current_photo is None:
        return
    await state.clear()
    await state.update_data(edit_post_id=post.id, edit_photo_number=photo_number)
    await state.set_state(EditFlow.post_photo)
    if callback.message:
        await callback.message.answer(f"Send the replacement for photo {photo_number}:")


@router.message(EditFlow.post_photo, F.photo)
async def save_post_photo(message: Message, state: FSMContext) -> None:
    """Save the largest available Telegram photo size to the post."""
    user = await _get_active_user(message.from_user.id if message.from_user else 0)
    data = await state.get_data()
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
        await message.answer("Photo updated.", reply_markup=edit_home_keyboard())
    else:
        await message.answer("That post could not be updated. Open /edit and try again.")


@router.message(EditFlow.post_photo)
async def reject_post_photo(message: Message) -> None:
    """Ask again when a replacement photo step receives another message type."""
    await message.answer("Please send a photo, or use /cancel to stop.")


@router.callback_query(F.data.regexp(r"^edit:post:delete:\d+$"))
async def confirm_post_delete(callback: CallbackQuery, state: FSMContext) -> None:
    """Ask for confirmation before deleting a post."""
    await callback.answer()
    try:
        post_id = int((callback.data or "").split(":")[-1])
    except ValueError:
        return
    user = await _get_active_user(callback.from_user.id)
    post = await get_owned_post(user.id, post_id) if user else None
    if post is None:
        return

    await state.clear()
    if callback.message:
        await callback.message.answer(
            "Delete this post and its ratings? This cannot be undone.",
            reply_markup=confirm_delete_keyboard(
                f"edit:post:delete:confirm:{post_id}",
                f"edit:item:{post_id}",
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
    deleted = user is not None and await delete_post(user.id, post_id)
    await state.clear()
    if callback.message:
        text = "Post deleted." if deleted else "That post could not be found."
        await callback.message.answer(text, reply_markup=edit_home_keyboard())


@router.callback_query(F.data == "edit:account:delete")
async def confirm_account_delete(callback: CallbackQuery, state: FSMContext) -> None:
    """Ask for confirmation before deleting the account."""
    await callback.answer()
    await state.clear()
    if callback.message:
        await callback.message.answer(
            "Delete your account, profile, posts, and ratings? This cannot be undone.",
            reply_markup=confirm_delete_keyboard(
                "edit:account:delete:confirm",
                "edit:home",
            ),
        )


@router.callback_query(F.data == "edit:account:delete:confirm")
async def delete_account(callback: CallbackQuery, state: FSMContext) -> None:
    """Delete the user's account after confirmation."""
    await callback.answer()
    deleted = await delete_user(callback.from_user.id)
    await state.clear()
    if callback.message:
        if deleted:
            await callback.message.answer("Your account has been deleted. Send /start to register again.")
        else:
            await callback.message.answer("Your account could not be found. Send /start to continue.")