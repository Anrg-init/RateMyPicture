"""Notification and retention engine for RateMyPic bot.

Handles:
- Real-time alerts to post owners when someone rates or comments on their photo.
- Milestone alerts (e.g. 5th, 10th, 25th rating).
- Re-engagement & retention reminders to bring inactive users back.
"""

import asyncio
from html import escape
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ratemypic.i18n import t
from ratemypic.services import (
    get_inactive_users_for_retention,
    get_next_post_to_rate,
    get_post_by_id,
    get_post_owner_for_notification,
    mark_user_notified,
)

logger = logging.getLogger(__name__)

MILESTONES = {5, 10, 25, 50, 100}


async def notify_post_owner_of_rating(
    bot: Bot,
    post_id: int,
    rater_id: int,
    score: int,
    comment: str | None,
) -> bool:
    """Send an instant alert to the post owner when a new rating is submitted."""
    try:
        owner = await get_post_owner_for_notification(post_id)
        if owner is None:
            logger.debug("Post %d has no owner found for notification", post_id)
            return False

        # Guard: Never notify a user if they rate their own photo (self-rating)
        if owner.id == rater_id:
            logger.debug("Skipping self-notification for owner_id=%d on post_id=%d", owner.id, post_id)
            return False

        # Check user notification preference
        if not getattr(owner, "notifications_enabled", True):
            logger.debug("Notifications disabled for owner telegram_id=%d", owner.telegram_id)
            return False

        post = await get_post_by_id(post_id)
        if post is None:
            return False

        lang = getattr(owner, "language", "en")
        stars = "⭐" * score
        avg = (post.rating_sum / post.rating_count) if post.rating_count > 0 else float(score)

        # Build notification message
        msg_parts = [
            t("notify.new_rating_title", lang=lang),
            "",
            t("notify.score", lang=lang, stars=stars, score=score),
        ]

        if comment:
            msg_parts.append(t("notify.comment", lang=lang, comment=escape(comment)))

        msg_parts.append(t("notify.average", lang=lang, average=avg, count=post.rating_count))

        # Check for milestone celebration
        if post.rating_count in MILESTONES:
            msg_parts.append("")
            msg_parts.append(t("notify.milestone", lang=lang, count=post.rating_count))

        text = "\n".join(msg_parts)

        # Inline button to view their post
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=t("notify.button_view", lang=lang),
                        callback_data=f"edit:item:{post.id}",
                    )
                ]
            ]
        )

        await bot.send_message(
            chat_id=owner.telegram_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        logger.info(
            "Delivered rating notification to owner telegram_id=%d for post_id=%d (score=%d)",
            owner.telegram_id,
            post_id,
            score,
        )
        return True

    except TelegramForbiddenError:
        logger.info("Cannot notify user %d: bot was blocked by user", owner.telegram_id if owner else 0)
        return False
    except TelegramBadRequest as err:
        logger.warning("TelegramBadRequest while sending notification to user %s: %s", getattr(owner, "telegram_id", None), err)
        return False
    except Exception as err:
        logger.exception("Unexpected error delivering rating notification for post_id=%d: %s", post_id, err)
        return False


async def send_retention_broadcast(
    bot: Bot,
    hours_inactive: int = 48,
    limit: int = 50,
) -> int:
    """Send re-engagement reminders to inactive users who have fresh photos to rate."""
    inactive_users = await get_inactive_users_for_retention(
        hours_inactive=hours_inactive,
        limit=limit,
    )
    if not inactive_users:
        logger.info("No inactive users eligible for retention reminders at this time.")
        return 0

    sent_count = 0
    for user in inactive_users:
        try:
            # Check if there are actually photos available for this user to rate
            available_post = await get_next_post_to_rate(user_id=user.id, prefer_low_count=True)
            if not available_post:
                continue

            lang = getattr(user, "language", "en")
            text = t("notify.retention_text", lang=lang)
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=t("notify.button_rate", lang=lang),
                            callback_data="menu:rate",
                        )
                    ]
                ]
            )

            await bot.send_message(
                chat_id=user.telegram_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            await mark_user_notified(user.id)
            sent_count += 1
            logger.info("Sent retention reminder to telegram_id=%d", user.telegram_id)

            # Prevent Telegram rate-limiting
            await asyncio.sleep(0.1)

        except TelegramForbiddenError:
            logger.info("User telegram_id=%d has blocked the bot; skipping", user.telegram_id)
            await mark_user_notified(user.id)
        except Exception as err:
            logger.warning("Could not send retention reminder to telegram_id=%d: %s", user.telegram_id, err)

    logger.info("Retention broadcast finished: sent %d reminders", sent_count)
    return sent_count


async def retention_reminder_loop(bot: Bot, interval_seconds: int = 43200) -> None:
    """Background standing task that periodically dispatches retention reminders."""
    logger.info("Started background retention reminder loop (runs every %d seconds)", interval_seconds)
    # Initial sleep on startup so bot finishes initializing cleanly
    await asyncio.sleep(60)
    while True:
        try:
            await send_retention_broadcast(bot, hours_inactive=48, limit=50)
        except asyncio.CancelledError:
            logger.info("Retention reminder loop cancelled.")
            break
        except Exception as err:
            logger.exception("Error in retention reminder loop: %s", err)
        await asyncio.sleep(interval_seconds)
