"""Post management and feedback handlers.

Handles:
1. Viewing user's posts and their community ratings/reviews (My Feedback).
2. Creating a new photo post (FSM: upload photo -> add caption -> save to DB).
"""

from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InputMediaPhoto, Message

from ratemypic.keyboards import (
    cancel_post_keyboard,
    empty_posts_keyboard,
    main_menu_keyboard,
    post_photo_count_keyboard,
    posts_list_keyboard,
)
from ratemypic.services import (
    create_post,
    get_post_comments,
    get_user_by_telegram_id,
    get_user_posts,
)

router = Router()


class CreatePost(StatesGroup):
    """FSM steps for creating a new post."""

    count = State()
    photo = State()
    caption = State()


# ===========================================================================
# 1. My Feedback - View user's posts and ratings
# ===========================================================================
@router.callback_query(F.data == "menu:feedback")
async def show_my_feedback(callback: CallbackQuery) -> None:
    """Fetch user's posts from database and display ratings."""
    await callback.answer()
    telegram_id = callback.from_user.id

    # 1. Look up user in database
    user = await get_user_by_telegram_id(telegram_id)
    if user is None:
        if callback.message:
            await callback.message.answer("👋 Please register first using /start.")
        return

    # 2. Query all posts for this user
    posts = await get_user_posts(user.id)

    # CASE A: No posts yet
    if not posts:
        text = (
            "📸 *You haven't posted anything yet!*\n\n"
            "Share a photo to start receiving ratings and feedback from the community. 🌟"
        )
        if callback.message:
            await callback.message.answer(
                text,
                reply_markup=empty_posts_keyboard(),
                parse_mode="Markdown",
            )
        return

    # CASE B: User has posts -> display each one with its ratings
    if callback.message:
        await callback.message.answer(
            "📊 *Your photos and community feedback:*",
            parse_mode="Markdown",
        )

        for post in posts:
            # Calculate average rating
            if post.rating_count > 0:
                avg_score = post.rating_sum / post.rating_count
                rating_display = f"⭐ {avg_score:.1f} / 5.0 ({post.rating_count} ratings)"
            else:
                rating_display = "⭐ No ratings yet"

            # Fetch the latest comments, skipping ratings without comments.
            recent_comments = await get_post_comments(post.id, limit=3)

            # Escape user-entered text before sending it as Telegram HTML.
            post_text = (
                f"💬 <b>Caption:</b> {escape(post.caption)}\n"
                f"📈 <b>Rating:</b> {rating_display}\n"
                f"📌 <b>Status:</b> {escape(post.status.capitalize())}\n"
                "\n📝 <b>Recent Comments:</b>\n"
            )

            if recent_comments:
                for rating in recent_comments:
                    post_text += (
                        f"• <b>{rating.score}/5 stars:</b> "
                        f"{escape(rating.comment)}\n"
                    )
            else:
                post_text += "No comments yet.\n"

            photo_ids = [
                post.photo1_file_id,
                post.photo2_file_id,
                post.photo3_file_id,
            ]
            photo_ids = [photo_id for photo_id in photo_ids if photo_id]
            if len(photo_ids) == 1:
                await callback.message.answer_photo(
                    photo=photo_ids[0],
                    caption=post_text,
                    parse_mode="HTML",
                )
            else:
                await callback.message.answer_media_group(
                    media=[InputMediaPhoto(media=photo_id) for photo_id in photo_ids]
                )
                await callback.message.answer(post_text, parse_mode="HTML")

        # Bottom navigation
        await callback.message.answer(
            "✨ What would you like to do next?",
            reply_markup=posts_list_keyboard(),
        )


# ===========================================================================
# 2. Create Post Wizard (Photo -> Caption -> Database)
# ===========================================================================
@router.callback_query(F.data == "post:create")
async def start_create_post(callback: CallbackQuery, state: FSMContext) -> None:
    """Ask how many photos the new post should contain."""
    await callback.answer()
    await state.clear()
    await state.set_state(CreatePost.count)

    if callback.message:
        await callback.message.answer(
            "📸 How many photos do you want to add? Choose 1, 2, or 3:",
            reply_markup=post_photo_count_keyboard(),
        )


@router.callback_query(CreatePost.count, F.data.startswith("post:count:"))
async def choose_post_photo_count(callback: CallbackQuery, state: FSMContext) -> None:
    """Save the selected photo count and request the first photo."""
    try:
        photo_count = int((callback.data or "").split(":")[-1])
    except ValueError:
        await callback.answer("Choose 1, 2, or 3 photos.", show_alert=True)
        return

    if photo_count not in (1, 2, 3):
        await callback.answer("Choose 1, 2, or 3 photos.", show_alert=True)
        return

    await callback.answer()
    await state.update_data(photo_count=photo_count, post_photos=[])
    await state.set_state(CreatePost.photo)
    if callback.message:
        await callback.message.answer(
            f"📸 Send photo 1 of {photo_count}:",
            reply_markup=cancel_post_keyboard(),
        )


@router.message(CreatePost.photo, F.photo)
async def process_post_photo(message: Message, state: FSMContext) -> None:
    """Save each photo and continue until the chosen count is reached."""
    data = await state.get_data()
    photos = data.get("post_photos", [])
    photo_count = data.get("photo_count", 1)
    best_photo = message.photo[-1]
    photos.append({
        "file_id": best_photo.file_id,
        "unique_id": best_photo.file_unique_id,
    })
    await state.update_data(post_photos=photos)

    if len(photos) < photo_count:
        await message.answer(f"📸 Send photo {len(photos) + 1} of {photo_count}:")
        return

    await state.set_state(CreatePost.caption)
    await message.answer(
        "✍️ Add a caption (between 1 and 150 characters):",
        reply_markup=cancel_post_keyboard(),
    )


@router.message(CreatePost.photo)
async def process_invalid_photo(message: Message, state: FSMContext) -> None:
    """Ask for a photo when another message type is sent during upload."""
    data = await state.get_data()
    photos = data.get("post_photos", [])
    photo_count = data.get("photo_count", 1)
    await message.answer(
        f"⚠️ Please send photo {len(photos) + 1} of {photo_count}, or press Cancel:",
        reply_markup=cancel_post_keyboard(),
    )


@router.message(CreatePost.caption, F.text)
async def process_post_caption(message: Message, state: FSMContext) -> None:
    """Validate the caption and save the post and all selected photo IDs."""
    caption = (message.text or "").strip()

    if not (1 <= len(caption) <= 150):
        await message.answer(
            "⚠️ Caption must be between 1 and 150 characters. Please try again:"
        )
        return

    data = await state.get_data()
    photos = data.get("post_photos", [])
    if not photos:
        await state.clear()
        await message.answer("No photos were received. Please start again with /start.")
        return

    user = await get_user_by_telegram_id(message.from_user.id if message.from_user else 0)
    if not user:
        await message.answer("👋 Your account wasn't found. Please type /start.")
        await state.clear()
        return

    try:
        await create_post(
            user_id=user.id,
            photo_file_id=photos[0]["file_id"],
            photo_unique_id=photos[0]["unique_id"],
            photo2_file_id=photos[1]["file_id"] if len(photos) > 1 else None,
            photo2_unique_id=photos[1]["unique_id"] if len(photos) > 1 else None,
            photo3_file_id=photos[2]["file_id"] if len(photos) > 2 else None,
            photo3_unique_id=photos[2]["unique_id"] if len(photos) > 2 else None,
            caption=caption,
        )
        await state.clear()

        await message.answer(
            "🎉 Your photo post has been published! Other people can now see and rate it.",
            reply_markup=main_menu_keyboard(),
        )
    except Exception:
        await message.answer(
            "⚠️ Couldn't publish your post. Please try again later.",
            reply_markup=main_menu_keyboard(),
        )
        await state.clear()


@router.callback_query(F.data == "post:cancel")
async def cancel_create_post(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel post creation and return to menu."""
    await callback.answer("Cancelled")
    await state.clear()
    if callback.message:
        await callback.message.answer(
            "❌ Photo upload cancelled. What would you like to do?",
            reply_markup=main_menu_keyboard(),
        )
