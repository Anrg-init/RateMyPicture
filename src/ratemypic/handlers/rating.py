"""Rate Others handler.

Full flow:
1. User clicks "⭐ Rate Others".
2. Algorithm picks the next post to show, prioritizing posts with fewer ratings.
3. Post photo + caption + rating_count is shown with 1-5 star buttons.
4. User MUST tap a star to proceed (no skipping without rating).
5. User is asked for an optional comment (can skip).
6. Rating is saved to PostgreSQL, post totals updated atomically.
7. Next post is automatically loaded using the algorithm.

Algorithm (three-turn cycle):
- Turns 1 and 2: show a random post with rating_count < 10 (helps newer posts).
- Turn 3: show a random post with rating_count >= 10, then repeat the cycle.
"""

from html import escape
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InputMediaPhoto, Message

from ratemypic.keyboards import (
    main_menu_keyboard,
    no_more_posts_keyboard,
    post_comments_keyboard,
    skip_comment_keyboard,
    star_rating_keyboard,
)
from ratemypic.services import (
    get_next_post_to_rate,
    get_post_comments,
    get_user_by_telegram_id,
    has_already_rated,
    save_rating,
)

router = Router()
logger = logging.getLogger(__name__)
COMMENTS_PER_PAGE = 5


class RatingFlow(StatesGroup):
    """FSM states for the Rate Others flow."""

    viewing_post  = State()   # User is looking at a post and must tap a star
    writing_comment = State() # User optionally writes a comment after starring


# ===========================================================================
# Helper: Send the next post to rate
# ===========================================================================
async def send_next_post(chat_id: int, user_id: int, state: FSMContext, bot) -> None:
    """Pick and send the next post to the user based on the alternating algorithm."""
    # Read current turn from memory (default: start with low-count posts)
    data = await state.get_data()
    turn = data.get("rating_turn", 0)
    prefer_low = turn % 3 != 2  # Give low-count posts two turns out of every three

    post = await get_next_post_to_rate(user_id=user_id, prefer_low_count=prefer_low)

    if post is None:
        # No more posts left for this user to rate
        logger.info("No more posts to rate for user_id=%d", user_id)
        await state.clear()
        await bot.send_message(
            chat_id=chat_id,
            text=(
                "🎉 *Amazing work!*\n\n"
                "You've rated all available posts for now.\n"
                "Come back later to rate new uploads!\n\n"
                "Thank you for helping the community ❤️"
            ),
            reply_markup=no_more_posts_keyboard(),
            parse_mode="Markdown",
        )
        return

    # Build a nice display for the post
    if post.rating_count > 0:
        avg = post.rating_sum / post.rating_count
        rating_line = (
            f"📊 <b>Community rating:</b> ⭐ {avg:.1f}/5 "
            f"({post.rating_count} ratings)"
        )
    else:
        rating_line = "✨ <b>No ratings yet.</b> Be the first to rate this photo!"

    caption = (
        f"🖼 <b>{escape(post.caption)}</b>\n\n"
        f"{rating_line}\n\n"
        "👇 <b>How would you rate this photo?</b>\n"
        "Choose a score from 1 to 5."
    )

    # Save current post and increment the turn for next time
    await state.update_data(
        current_post_id=post.id,
        rating_turn=turn + 1,
    )
    await state.set_state(RatingFlow.viewing_post)

    photo_ids = [
        post.photo1_file_id,
        post.photo2_file_id,
        post.photo3_file_id,
    ]
    photo_ids = [photo_id for photo_id in photo_ids if photo_id]
    if len(photo_ids) == 1:
        await bot.send_photo(
            chat_id=chat_id,
            photo=photo_ids[0],
            caption=caption,
            reply_markup=star_rating_keyboard(post.id),
            parse_mode="HTML",
        )
    else:
        await bot.send_media_group(
            chat_id=chat_id,
            media=[InputMediaPhoto(media=photo_id) for photo_id in photo_ids],
        )
        await bot.send_message(
            chat_id=chat_id,
            text=caption,
            reply_markup=star_rating_keyboard(post.id),
            parse_mode="HTML",
        )

    logger.info(
        "Showed post_id=%d to user_id=%d (turn=%d, prefer_low=%s)",
        post.id, user_id, turn, prefer_low,
    )


# ===========================================================================
# 1. Entry Point: User clicks "Rate Others"
# ===========================================================================
@router.callback_query(F.data == "menu:rate")
async def start_rating_feed(callback: CallbackQuery, state: FSMContext) -> None:
    """User clicked 'Rate Others' - start the rating feed."""
    await callback.answer()
    telegram_id = callback.from_user.id

    user = await get_user_by_telegram_id(telegram_id)
    if user is None:
        if callback.message:
            await callback.message.answer("👋 Please register first with /start.")
        return

    # Reset turn counter when starting fresh from menu
    await state.update_data(rating_turn=0)

    if callback.message:
        await callback.message.answer(
            "⭐ <b>Rate community photos</b>\n\n"
            "Give each photo a score from 1 to 5. You can also leave an "
            "optional, thoughtful comment. 💬",
            parse_mode="HTML",
        )
        await send_next_post(
            chat_id=callback.message.chat.id,
            user_id=user.id,
            state=state,
            bot=callback.bot,
        )


@router.callback_query(RatingFlow.viewing_post, F.data.startswith("comments:"))
async def show_post_comments(callback: CallbackQuery, state: FSMContext) -> None:
    """Show a page of comments for the post currently shown in the feed."""
    parts = (callback.data or "").split(":")
    try:
        post_id = int(parts[1]) if len(parts) == 3 else None
        offset = int(parts[2]) if len(parts) == 3 else -1
    except ValueError:
        post_id = None
        offset = -1

    data = await state.get_data()
    if (
        post_id != data.get("current_post_id")
        or offset < 0
        or offset % COMMENTS_PER_PAGE != 0
    ):
        await callback.answer("That comments button has expired.", show_alert=True)
        return

    await callback.answer()
    comments = await get_post_comments(
        post_id,
        limit=COMMENTS_PER_PAGE + 1,
        offset=offset,
    )
    has_next = len(comments) > COMMENTS_PER_PAGE
    comments = comments[:COMMENTS_PER_PAGE]

    if comments:
        comment_lines = [
            f"⭐ <b>{comment.score}/5</b>\n{escape(comment.comment or '')}"
            for comment in comments
        ]
        text = "💬 <b>Comments on this photo</b>\n\n" + "\n\n".join(comment_lines)
    else:
        text = "💬 <b>Comments on this photo</b>\n\nNo written comments yet."

    if callback.message:
        await callback.message.answer(
            text,
            reply_markup=post_comments_keyboard(
                post_id=post_id,
                offset=offset,
                has_previous=offset > 0,
                has_next=has_next,
            ),
            parse_mode="HTML",
        )


# ===========================================================================
# 2. User taps a star button -> ask for optional comment
# ===========================================================================
@router.callback_query(RatingFlow.viewing_post, F.data.startswith("rate:"))
async def process_star_rating(callback: CallbackQuery, state: FSMContext) -> None:
    """User tapped a star. Save score, ask for optional comment."""
    await callback.answer("⭐ Star received!")

    # Parse post_id and score from callback data: "rate:<post_id>:<score>"
    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        if callback.message:
            await callback.message.answer(
                "⌛ That rating button has expired. Use the current photo's buttons."
            )
        return

    try:
        post_id = int(parts[1])
        score = int(parts[2])
    except ValueError:
        if callback.message:
            await callback.message.answer(
                "⌛ That rating button has expired. Use the current photo's buttons."
            )
        return

    data = await state.get_data()
    if not 1 <= score <= 5 or post_id != data.get("current_post_id"):
        if callback.message:
            await callback.message.answer(
                "⌛ That rating button has expired. Use the current photo's buttons."
            )
        return

    telegram_id = callback.from_user.id

    user = await get_user_by_telegram_id(telegram_id)
    if user is None:
        return

    # Guard: prevent double-rating (e.g., user taps twice fast)
    if await has_already_rated(user.id, post_id):
        if callback.message:
            await callback.message.answer(
                "⚠️ You've already rated this photo. Loading the next one...",
                reply_markup=main_menu_keyboard(),
            )
        await send_next_post(
            chat_id=callback.message.chat.id,
            user_id=user.id,
            state=state,
            bot=callback.bot,
        )
        return

    # Save the score and post_id in memory (we still need a possible comment)
    await state.update_data(pending_score=score, pending_post_id=post_id)
    await state.set_state(RatingFlow.writing_comment)

    stars = "⭐" * score
    if callback.message:
        await callback.message.answer(
            f"✅ <b>Your score: {stars} ({score}/5)</b>\n\n"
            "Would you like to leave a comment?\n"
            "<i>Optional, up to 200 characters.</i>",
            reply_markup=skip_comment_keyboard(post_id),
            parse_mode="HTML",
        )


# ===========================================================================
# 3a. User writes a comment
# ===========================================================================
@router.message(RatingFlow.writing_comment, F.text)
async def process_comment_text(message: Message, state: FSMContext) -> None:
    """User typed a comment after rating."""
    comment = (message.text or "").strip()

    if len(comment) > 200:
        await message.answer(
            "⚠️ Comment is too long (max 200 characters). Please shorten it and try again:"
        )
        return

    await _finalize_rating(
        chat_id=message.chat.id,
        telegram_id=message.from_user.id if message.from_user else 0,
        comment=comment,
        state=state,
        bot=message.bot,
    )


# ===========================================================================
# 3b. User clicks "Skip comment"
# ===========================================================================
@router.callback_query(RatingFlow.writing_comment, F.data.startswith("skipcomment:"))
async def process_skip_comment(callback: CallbackQuery, state: FSMContext) -> None:
    """User skipped writing a comment."""
    parts = (callback.data or "").split(":")
    data = await state.get_data()
    try:
        post_id = int(parts[1]) if len(parts) == 2 else None
    except ValueError:
        post_id = None

    if post_id != data.get("pending_post_id"):
        await callback.answer("That comment prompt has expired.")
        return

    await callback.answer()
    if callback.message:
        await _finalize_rating(
            chat_id=callback.message.chat.id,
            telegram_id=callback.from_user.id,
            comment=None,
            state=state,
            bot=callback.bot,
        )


# ===========================================================================
# Internal: Save rating + load next post
# ===========================================================================
async def _finalize_rating(
    chat_id: int,
    telegram_id: int,
    comment: str | None,
    state: FSMContext,
    bot,
) -> None:
    """Save the rating to PostgreSQL and immediately show the next post."""
    data = await state.get_data()
    score = data.get("pending_score")
    post_id = data.get("pending_post_id")

    user = await get_user_by_telegram_id(telegram_id)
    if user is None or not score or not post_id:
        logger.error("Missing rating data for telegram_id=%d", telegram_id)
        return

    try:
        await save_rating(
            post_id=post_id,
            rater_id=user.id,
            score=score,
            comment=comment,
        )

        stars = "⭐" * score
        confirmation = (
            f"✅ <b>Your rating is saved</b>\n"
            f"Score: {stars} ({score}/5)"
        )
        if comment:
            confirmation += f"\n\n💬 <b>Your comment</b>\n{escape(comment)}"

        await bot.send_message(
            chat_id=chat_id,
            text=confirmation,
            parse_mode="HTML",
        )

    except Exception as error:
        logger.exception("Failed to save rating for user_id=%d, post_id=%d: %s", user.id, post_id, error)
        await bot.send_message(
            chat_id=chat_id,
            text="⚠️ Couldn't save your rating. Please try again.",
        )
        return

    # Automatically load the next post
    await send_next_post(
        chat_id=chat_id,
        user_id=user.id,
        state=state,
        bot=bot,
    )
