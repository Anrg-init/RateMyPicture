"""Admin-only commands and statistics."""

from html import escape
import logging
import os

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from ratemypic.services import get_admin_dashboard_stats

router = Router()
logger = logging.getLogger(__name__)

FLAG_MAP = {
    "en": "🇬🇧",
    "ru": "🇷🇺",
    "es": "🇪🇸",
    "pt": "🇵🇹",
    "id": "🇮🇩",
}


def _get_admin_id() -> int | None:
    admin_id_str = os.getenv("ADMIN_ID")
    if not admin_id_str:
        return None
    try:
        return int(admin_id_str)
    except ValueError:
        return None


def format_admin_stats(stats: dict) -> str:
    """Format dashboard text matching exact user specifications."""
    total = stats["total_users"]
    joined_today = stats["joined_today"]
    active = stats["active_users"]
    banned = stats["banned_users"]

    # Recent Users
    user_lines = []
    for u in stats.get("recent_users", []):
        flag = FLAG_MAP.get(u["language"], "🌐")
        loc_str = f"📍 {escape(u['location'])}" if u.get("location") else "📍 Not specified"
        time_str = u["created_at"].strftime("%b %d, %H:%M UTC") if u.get("created_at") else "N/A"
        user_lines.append(
            f"• <b>#{u['id']} {escape(u['name'])}</b> ({u['age']} y/o)\n"
            f"  ├ 🆔 TG: <code>{u['telegram_id']}</code> | {flag} {u['language'].upper()}\n"
            f"  ├ {loc_str}\n"
            f"  └ 🕒 Joined: {time_str}"
        )
    recent_users_text = "\n".join(user_lines) if user_lines else "• None"

    # Recent Posts
    total_posts = stats.get("total_posts", 0)
    posts_today = stats.get("posts_today", 0)
    approved_posts = stats.get("approved_posts", 0)

    post_lines = []
    for p in stats.get("recent_posts", []):
        avg = (p["rating_sum"] / p["rating_count"]) if p.get("rating_count") else 0.0
        caption_preview = escape(p["caption"][:35] + ("..." if len(p["caption"]) > 35 else ""))
        time_str = p["created_at"].strftime("%b %d, %H:%M UTC") if p.get("created_at") else "N/A"
        post_lines.append(
            f"• <b>Post #{p['id']}</b> by <b>{escape(p['owner_name'])}</b> (User ID: {p['user_id']})\n"
            f"  ├ 📝 \"<i>{caption_preview}</i>\"\n"
            f"  ├ ⭐ {avg:.1f}/5 ({p['rating_count']} ratings) | Status: {p['status']}\n"
            f"  └ 🕒 Uploaded: {time_str}"
        )
    recent_posts_text = "\n".join(post_lines) if post_lines else "• None"

    # Languages
    lang_lines = []
    for lang_code, count in stats["languages"]:
        flag = FLAG_MAP.get(lang_code, "🌐")
        pct = (count / total * 100) if total else 0
        lang_lines.append(f"  {flag} {lang_code.upper()}: {pct:.0f}% ({count} users)")
    lang_text = "\n".join(lang_lines) if lang_lines else "  None"

    # Locations
    loc_lines = []
    for loc, count in stats["top_locations"]:
        loc_lines.append(f"  📍 {escape(loc)} ({count})")
    if stats["unspecified_locations"] > 0:
        loc_lines.append(f"  📍 Other / Not specified ({stats['unspecified_locations']})")
    loc_text = "\n".join(loc_lines) if loc_lines else "  📍 None"

    # Demographics
    avg_age = stats["avg_age"]
    min_age = stats["min_age"]
    max_age = stats["max_age"]

    return (
        "📊 <b>RateMyPic — Admin Dashboard</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👥 <b>User Growth:</b>\n"
        f"• Total Users: {total}\n"
        f"• Joined Today: +{joined_today}\n"
        f"• Active Users: {active} | Banned: {banned}\n\n"
        "🆕 <b>Latest Users:</b>\n"
        f"{recent_users_text}\n\n"
        "📸 <b>Posts Activity:</b>\n"
        f"• Total Posts: {total_posts}\n"
        f"• Uploaded Today: +{posts_today}\n"
        f"• Approved: {approved_posts}\n\n"
        "🆕 <b>Latest Posts:</b>\n"
        f"{recent_posts_text}\n\n"
        "🌍 <b>Audience & Demographics:</b>\n"
        "• <b>Top Languages:</b>\n"
        f"{lang_text}\n"
        "• <b>Top Locations:</b>\n"
        f"{loc_text}\n"
        "• <b>Demographics:</b>\n"
        f"  Avg Age: {avg_age:.1f} yrs (range: {min_age}–{max_age})"
    )


def admin_stats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Refresh", callback_data="admin:refresh_stats")
            ]
        ]
    )


@router.message(Command("stats"))
async def handle_admin_stats_command(message: Message) -> None:
    admin_id = _get_admin_id()
    if not admin_id or not message.from_user or message.from_user.id != admin_id:
        # Silently ignore for non-admins so unauthorized users don't even know it exists
        return

    stats = await get_admin_dashboard_stats()
    text = format_admin_stats(stats)
    await message.answer(text, reply_markup=admin_stats_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "admin:refresh_stats")
async def handle_admin_refresh_stats(callback: CallbackQuery) -> None:
    admin_id = _get_admin_id()
    if not admin_id or callback.from_user.id != admin_id:
        await callback.answer("⛔ Unauthorized", show_alert=True)
        return

    await callback.answer("Stats refreshed!")
    stats = await get_admin_dashboard_stats()
    text = format_admin_stats(stats)

    if callback.message:
        try:
            await callback.message.edit_text(
                text=text,
                reply_markup=admin_stats_keyboard(),
                parse_mode="HTML",
            )
        except Exception:
            pass


@router.message(Command("remind"))
async def handle_admin_remind_command(message: Message) -> None:
    """Admin-only manual trigger for sending retention reminders."""
    admin_id = _get_admin_id()
    if not admin_id or not message.from_user or message.from_user.id != admin_id:
        return

    status_msg = await message.answer("⏳ Checking and sending retention reminders...")
    from ratemypic.notifications import send_retention_broadcast

    sent_count = await send_retention_broadcast(message.bot, hours_inactive=24, limit=50)
    await status_msg.edit_text(
        f"✅ Retention broadcast finished: sent reminders to <b>{sent_count}</b> inactive users.",
        parse_mode="HTML",
    )
