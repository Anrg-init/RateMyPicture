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

import asyncio
from html import escape
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InputMediaPhoto, Message

from ratemypic.i18n import t
from ratemypic.keyboards import (
    main_menu_keyboard,
    no_more_posts_keyboard,
    post_comments_keyboard,
    skip_comment_keyboard,
    star_rating_keyboard,
)
from ratemypic.notifications import notify_post_owner_of_rating
from ratemypic.services import (
    SOCIAL_REACTIONS,
    get_next_post_to_rate,
    get_post_by_id,
    get_post_comments,
    get_post_reactions,
    get_rating_distribution,
    get_user_by_telegram_id,
    has_already_rated,
    record_post_view,
    save_rating,
    toggle_post_reaction,
)

router = Router()
logger = logging.getLogger(__name__)
COMMENTS_PER_PAGE = 5


class RatingFlow(StatesGroup):
    """FSM states for the Rate Others flow."""

    viewing_post  = State()   # User is looking at a post and must tap a star
    writing_comment = State() # User optionally writes a comment after starring


def _format_post_caption(post, reactions: dict[str, int], lang: str) -> str:
    """Format post text with score and the 8 social reactions."""
    if post.rating_count > 0:
        avg = post.rating_sum / post.rating_count
        rating_line = t("rating.community_score", lang=lang, average=avg, count=post.rating_count)
    else:
        rating_line = t("rating.no_scores", lang=lang)

    rx_line_1 = f"😭 {reactions.get('😭', 0)}   🤣 {reactions.get('🤣', 0)}   ☠️ {reactions.get('☠️', 0)}   😍 {reactions.get('😍', 0)}"
    rx_line_2 = f"💩 {reactions.get('💩', 0)}   🍑 {reactions.get('🍑', 0)}   🍌 {reactions.get('🍌', 0)}   🔥 {reactions.get('🔥', 0)}"
    reactions_block = f"{rx_line_1}\n{rx_line_2}"

    return (
        f"🖼 <b>{escape(post.caption)}</b>\n\n"
        f"{rating_line}\n\n"
        f"{reactions_block}\n\n"
        + t("rating.ask_score", lang=lang)
    )


# ===========================================================================
# Helper: Send the next post to rate
# ===========================================================================
async def send_next_post(chat_id: int, user_id: int, state: FSMContext, bot) -> None:
    """Pick and send the next post to the user based on the alternating algorithm."""
    loading_msg = None
    try:
        loading_msg = await bot.send_message(chat_id=chat_id, text="⏳ Loading next photo...")
    except Exception:
        loading_msg = None

    try:
        # Read current turn from memory (default: start with low-count posts)
        data = await state.get_data()
        turn = data.get("rating_turn", 0)
        lang = data.get("language", "en")
        prefer_low = turn % 3 != 2  # Give low-count posts two turns out of every three

        post = await get_next_post_to_rate(user_id=user_id, prefer_low_count=prefer_low)

        if post is None:
            # No more posts left for this user to rate
            logger.info("No more posts to rate for user_id=%d", user_id)
            await state.clear()
            await bot.send_message(
                chat_id=chat_id,
                text=t("rating.no_posts", lang=lang),
                reply_markup=no_more_posts_keyboard(lang),
                parse_mode="Markdown",
            )
            return

        # Immediately register post as seen by this user so it will never be served again
        await record_post_view(user_id=user_id, post_id=post.id)

        # Fetch 8 social emoji reactions and format post caption
        reactions = await get_post_reactions(post.id)
        caption = _format_post_caption(post, reactions, lang)

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
        try:
            if len(photo_ids) == 1:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=photo_ids[0],
                    caption=caption,
                    reply_markup=star_rating_keyboard(post.id, lang),
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
                    reply_markup=star_rating_keyboard(post.id, lang),
                    parse_mode="HTML",
                )
        except TelegramBadRequest as err:
            logger.warning("Could not send photo for post_id=%d: %s. Sending text fallback.", post.id, err)
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                reply_markup=star_rating_keyboard(post.id, lang),
                parse_mode="HTML",
            )

        logger.info(
            "Showed post_id=%d to user_id=%d (turn=%d, prefer_low=%s)",
            post.id, user_id, turn, prefer_low,
        )
    finally:
        if loading_msg is not None:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=loading_msg.message_id)
            except Exception:
                pass


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
            await callback.message.answer(t("rating.register_first"))
        return

    # Reset turn counter when starting fresh from menu
    lang = getattr(user, "language", "en")
    await state.update_data(rating_turn=0, language=lang)

    if callback.message:
        await callback.message.answer(
            t("rating.entry_title", lang=lang),
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
    lang = data.get("language", "en")
    if (
        post_id != data.get("current_post_id")
        or offset < 0
        or offset % COMMENTS_PER_PAGE != 0
    ):
        await callback.answer(t("rating.expired_comments", lang=lang), show_alert=True)
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
        text = t("rating.comments_title", lang=lang) + "\n\n" + "\n\n".join(comment_lines)
    else:
        text = t("rating.comments_title", lang=lang) + "\n\n" + t("rating.no_comments", lang=lang)

    if callback.message:
        await callback.message.answer(
            text,
            reply_markup=post_comments_keyboard(
                post_id=post_id,
                offset=offset,
                has_previous=offset > 0,
                has_next=has_next,
                lang=lang,
            ),
            parse_mode="HTML",
        )


# ===========================================================================
# 2a. User taps a social reaction button (😭🤣☠️😍💩🍑🍌🔥) -> optional engagement
# ===========================================================================
@router.callback_query(F.data.startswith("react:"))
async def process_emoji_reaction(callback: CallbackQuery, state: FSMContext) -> None:
    """User tapped one of the 8 social emoji reaction buttons."""
    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        await callback.answer()
        return

    try:
        post_id = int(parts[1])
        emoji = parts[2]
    except ValueError:
        await callback.answer()
        return

    if emoji not in SOCIAL_REACTIONS:
        await callback.answer()
        return

    data = await state.get_data()
    lang = data.get("language", "en")
    telegram_id = callback.from_user.id
    user = await get_user_by_telegram_id(telegram_id)
    if user is None:
        await callback.answer(t("rating.register_first", lang=lang), show_alert=True)
        return

    added = await toggle_post_reaction(post_id=post_id, user_id=user.id, reaction=emoji)
    toast = f"Added {emoji}!" if added else f"Removed {emoji}"
    await callback.answer(toast)

    if callback.message:
        post = await get_post_by_id(post_id)
        if post:
            reactions = await get_post_reactions(post_id)
            new_caption = _format_post_caption(post, reactions, lang)
            try:
                if callback.message.caption is not None:
                    await callback.message.edit_caption(
                        caption=new_caption,
                        reply_markup=star_rating_keyboard(post.id, lang),
                        parse_mode="HTML",
                    )
                else:
                    await callback.message.edit_text(
                        text=new_caption,
                        reply_markup=star_rating_keyboard(post.id, lang),
                        parse_mode="HTML",
                    )
            except Exception as e:
                logger.debug("Could not edit message caption/text on reaction toggle: %s", e)


# ===========================================================================
# 2b. User taps Skip -> immediately show next post
# ===========================================================================
@router.callback_query(RatingFlow.viewing_post, F.data.startswith("rate:skip:"))
async def process_skip_post(callback: CallbackQuery, state: FSMContext) -> None:
    """User clicked Skip on the current post. Immediately load next eligible post."""
    await callback.answer()
    telegram_id = callback.from_user.id
    user = await get_user_by_telegram_id(telegram_id)
    if user is None:
        return
    if callback.message:
        await send_next_post(
            chat_id=callback.message.chat.id,
            user_id=user.id,
            state=state,
            bot=callback.bot,
        )


# ===========================================================================
# 2c. User taps a star button -> ask for optional comment
# ===========================================================================
@router.callback_query(RatingFlow.viewing_post, F.data.startswith("rate:"))
async def process_star_rating(callback: CallbackQuery, state: FSMContext) -> None:
    """User tapped a star. Save score, ask for optional comment."""
    data = await state.get_data()
    lang = data.get("language", "en")
    await callback.answer(t("rating.star_received", lang=lang))

    # Parse post_id and score from callback data: "rate:<post_id>:<score>"
    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        if callback.message:
            await callback.message.answer(
                t("rating.expired_star", lang=lang)
            )
        return

    try:
        post_id = int(parts[1])
        score = int(parts[2])
    except ValueError:
        if callback.message:
            await callback.message.answer(
                t("rating.expired_star", lang=lang)
            )
        return

    if not 1 <= score <= 5 or post_id != data.get("current_post_id"):
        if callback.message:
            await callback.message.answer(
                t("rating.expired_star", lang=lang)
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
                t("rating.already_rated", lang=lang),
                reply_markup=main_menu_keyboard(lang),
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
            t("rating.score_prompt", lang=lang, stars=stars, score=score),
            reply_markup=skip_comment_keyboard(post_id, lang),
            parse_mode="HTML",
        )


# ===========================================================================
# 3a. User writes a comment
# ===========================================================================
@router.message(RatingFlow.writing_comment, F.text)
async def process_comment_text(message: Message, state: FSMContext) -> None:
    """User typed a comment after rating."""
    comment = (message.text or "").strip()
    data = await state.get_data()
    lang = data.get("language", "en")

    if len(comment) > 500:
        await message.answer(
            t("rating.comment_too_long", lang=lang)
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
    lang = data.get("language", "en")
    try:
        post_id = int(parts[1]) if len(parts) == 2 else None
    except ValueError:
        post_id = None

    if post_id != data.get("pending_post_id"):
        await callback.answer(t("rating.expired_comment", lang=lang))
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
    lang = data.get("language", "en")

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

        # Notify the post owner in the background without delaying the rater
        asyncio.create_task(
            notify_post_owner_of_rating(
                bot=bot,
                post_id=post_id,
                rater_id=user.id,
                score=score,
                comment=comment,
            )
        )

        stars = "⭐" * score
        confirmation = t("rating.saved", lang=lang, stars=stars, score=score)
        if comment:
            confirmation += t("rating.saved_comment", lang=lang, comment=escape(comment))

        await bot.send_message(
            chat_id=chat_id,
            text=confirmation,
            parse_mode="HTML",
        )

    except Exception as error:
        logger.exception("Failed to save rating for user_id=%d, post_id=%d: %s", user.id, post_id, error)
        await bot.send_message(
            chat_id=chat_id,
            text=t("rating.save_failed", lang=lang),
        )
        return

    # Automatically load the next post
    await send_next_post(
        chat_id=chat_id,
        user_id=user.id,
        state=state,
        bot=bot,
    )
