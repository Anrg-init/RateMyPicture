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

from ratemypic.i18n import t
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
    get_post_reactions,
    get_rating_distribution,
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
            await callback.message.answer(t("post.feedback_register"))
        return
    lang = getattr(user, "language", "en")

    # 2. Query all posts for this user
    posts = await get_user_posts(user.id)

    # CASE A: No posts yet
    if not posts:
        text = t("post.none_yet", lang=lang)
        if callback.message:
            await callback.message.answer(
                text,
                reply_markup=empty_posts_keyboard(lang),
                parse_mode="Markdown",
            )
        return

    # CASE B: User has posts -> display each one with its ratings
    if callback.message:
        await callback.message.answer(
            t("post.feedback_title", lang=lang),
            parse_mode="Markdown",
        )

        for post in posts:
            # Calculate average rating
            if post.rating_count > 0:
                avg_score = post.rating_sum / post.rating_count
                rating_display = t(
                    "post.rating_summary",
                    lang=lang,
                    average=avg_score,
                    count=post.rating_count,
                )
            else:
                rating_display = t("post.no_ratings", lang=lang)

            # Social reactions display (8 standard emojis)
            reactions = await get_post_reactions(post.id)
            rx_line_1 = f"😭 {reactions.get('😭', 0)}   🤣 {reactions.get('🤣', 0)}   ☠️ {reactions.get('☠️', 0)}   😍 {reactions.get('😍', 0)}"
            rx_line_2 = f"💩 {reactions.get('💩', 0)}   🍑 {reactions.get('🍑', 0)}   🍌 {reactions.get('🍌', 0)}   🔥 {reactions.get('🔥', 0)}"
            reactions_display = f"{rx_line_1}\n{rx_line_2}"

            # Fetch the latest comments, skipping ratings without comments.
            recent_comments = await get_post_comments(post.id, limit=3)

            # Escape user-entered text before sending it as Telegram HTML.
            post_text = (
                f"{t('post.caption_label', lang=lang)} {escape(post.caption)}\n"
                f"{t('post.rating_label', lang=lang)} {rating_display}\n\n"
                f"{reactions_display}\n\n"
                f"{t('post.status_label', lang=lang)} "
                f"{t(f'post.status.{post.status}', lang=lang)}\n"
                f"\n{t('post.recent_comments', lang=lang)}\n"
            )

            if recent_comments:
                for rating in recent_comments:
                    post_text += (
                        t(
                            "post.comment_score",
                            lang=lang,
                            score=rating.score,
                            comment=escape(rating.comment or ""),
                        )
                        + "\n"
                    )
            else:
                post_text += t("post.no_comments", lang=lang) + "\n"

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
            t("post.what_next", lang=lang),
            reply_markup=posts_list_keyboard(lang),
        )


# ===========================================================================
# 2. Create Post Wizard (Photo -> Caption -> Database)
# ===========================================================================
@router.callback_query(F.data == "post:create")
async def start_create_post(callback: CallbackQuery, state: FSMContext) -> None:
    """Ask how many photos the new post should contain."""
    await callback.answer()
    await state.clear()
    user = await get_user_by_telegram_id(callback.from_user.id)
    lang = getattr(user, "language", "en") if user else "en"
    await state.update_data(language=lang)
    await state.set_state(CreatePost.count)

    if callback.message:
        await callback.message.answer(
            t("post.ask_photo_count", lang=lang),
            reply_markup=post_photo_count_keyboard(lang),
        )


@router.callback_query(CreatePost.count, F.data.startswith("post:count:"))
async def choose_post_photo_count(callback: CallbackQuery, state: FSMContext) -> None:
    """Save the selected photo count and request the first photo."""
    try:
        photo_count = int((callback.data or "").split(":")[-1])
    except ValueError:
        data = await state.get_data()
        lang = data.get("language", "en") if isinstance(data, dict) else "en"
        await callback.answer(t("post.invalid_photo_count", lang=lang), show_alert=True)
        return

    if photo_count not in (1, 2, 3):
        data = await state.get_data()
        lang = data.get("language", "en") if isinstance(data, dict) else "en"
        await callback.answer(t("post.invalid_photo_count", lang=lang), show_alert=True)
        return

    await callback.answer()
    data = await state.get_data()
    lang = data.get("language", "en") if isinstance(data, dict) else "en"
    await state.update_data(photo_count=photo_count, post_photos=[])
    await state.set_state(CreatePost.photo)
    if callback.message:
        await callback.message.answer(
            t("post.send_photo", lang=lang, current=1, total=photo_count),
            reply_markup=cancel_post_keyboard(lang),
        )


@router.message(CreatePost.photo, F.photo)
async def process_post_photo(message: Message, state: FSMContext) -> None:
    """Save each photo and continue until the chosen count is reached."""
    data = await state.get_data()
    lang = data.get("language", "en") if isinstance(data, dict) else "en"
    photos = data.get("post_photos", [])
    photo_count = data.get("photo_count", 1)
    best_photo = message.photo[-1]
    photos.append({
        "file_id": best_photo.file_id,
        "unique_id": best_photo.file_unique_id,
    })
    await state.update_data(post_photos=photos)

    if len(photos) < photo_count:
        await message.answer(t("post.send_photo", lang=lang, current=len(photos) + 1, total=photo_count))
        return

    await state.set_state(CreatePost.caption)
    await message.answer(
        t("post.ask_caption", lang=lang),
        reply_markup=cancel_post_keyboard(lang),
    )


@router.message(CreatePost.photo)
async def process_invalid_photo(message: Message, state: FSMContext) -> None:
    """Ask for a photo when another message type is sent during upload."""
    data = await state.get_data()
    lang = data.get("language", "en") if isinstance(data, dict) else "en"
    photos = data.get("post_photos", [])
    photo_count = data.get("photo_count", 1)
    await message.answer(
        t("post.invalid_photo", lang=lang, current=len(photos) + 1, total=photo_count),
        reply_markup=cancel_post_keyboard(lang),
    )


@router.message(CreatePost.caption, F.text)
async def process_post_caption(message: Message, state: FSMContext) -> None:
    """Validate the caption and save the post and all selected photo IDs."""
    caption = (message.text or "").strip()
    data = await state.get_data()
    lang = data.get("language", "en") if isinstance(data, dict) else "en"

    if not (1 <= len(caption) <= 500):
        await message.answer(
            t("post.invalid_caption", lang=lang)
        )
        return

    photos = data.get("post_photos", [])
    if not photos:
        await state.clear()
        await message.answer(t("post.no_photos", lang=lang))
        return

    user = await get_user_by_telegram_id(message.from_user.id if message.from_user else 0)
    if not user:
        await message.answer(t("post.account_missing", lang=lang))
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
            t("post.published", lang=lang),
            reply_markup=main_menu_keyboard(lang),
        )
    except Exception:
        await message.answer(
            t("post.publish_failed", lang=lang),
            reply_markup=main_menu_keyboard(lang),
        )
        await state.clear()


@router.callback_query(F.data == "post:cancel")
async def cancel_create_post(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel post creation and return to menu."""
    data = await state.get_data()
    lang = data.get("language", "en")
    await callback.answer(t("post.cancel_callback", lang=lang))
    await state.clear()
    if callback.message:
        await callback.message.answer(
            t("post.cancelled", lang=lang),
            reply_markup=main_menu_keyboard(lang),
        )
