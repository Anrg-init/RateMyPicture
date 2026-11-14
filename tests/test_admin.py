"""Tests for admin stats dashboard."""

import unittest
from unittest.mock import AsyncMock, patch

from ratemypic.handlers.admin import format_admin_stats, handle_admin_stats_command, handle_admin_refresh_stats


class AdminDashboardTests(unittest.IsolatedAsyncioTestCase):
    def test_format_admin_stats(self) -> None:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        stats = {
            "total_users": 24,
            "joined_today": 3,
            "active_users": 24,
            "banned_users": 0,
            "languages": [("en", 13), ("ru", 9), ("es", 2)],
            "top_locations": [("Moscow", 4), ("London", 3), ("New Delhi", 2)],
            "unspecified_locations": 15,
            "avg_age": 23.4,
            "min_age": 19,
            "max_age": 34,
            "recent_users": [
                {
                    "id": 25,
                    "telegram_id": 8398266486,
                    "name": "Ritik",
                    "age": 19,
                    "location": "India",
                    "language": "en",
                    "created_at": now,
                }
            ],
            "total_posts": 26,
            "posts_today": 2,
            "approved_posts": 26,
            "recent_posts": [
                {
                    "id": 26,
                    "user_id": 1,
                    "owner_name": "Anurag",
                    "caption": "rate my photo",
                    "rating_count": 8,
                    "rating_sum": 32,
                    "status": "approved",
                    "created_at": now,
                }
            ],
        }
        text = format_admin_stats(stats)
        self.assertIn("Admin Dashboard", text)
        self.assertIn("Total Users: 24", text)
        self.assertIn("Joined Today: +3", text)
        self.assertIn("Active Users: 24 | Banned: 0", text)
        self.assertIn("🇬🇧 EN: 54% (13 users)", text)
        self.assertIn("📍 Moscow (4)", text)
        self.assertIn("Other / Not specified (15)", text)
        self.assertIn("Avg Age: 23.4 yrs (range: 19–34)", text)
        self.assertIn("#25 Ritik", text)
        self.assertIn("TG: <code>8398266486</code>", text)
        self.assertIn("Post #26", text)
        self.assertIn("Anurag", text)

    async def test_non_admin_cannot_access_stats(self) -> None:
        message = AsyncMock()
        message.from_user.id = 999999999  # Not admin

        with (
            patch("ratemypic.handlers.admin.os.getenv", return_value="1954359757"),
            patch("ratemypic.handlers.admin.get_admin_dashboard_stats") as mock_stats,
        ):
            await handle_admin_stats_command(message)

        mock_stats.assert_not_awaited()
        message.answer.assert_not_awaited()

    async def test_admin_can_access_stats(self) -> None:
        message = AsyncMock()
        message.from_user.id = 1954359757

        sample_stats = {
            "total_users": 10,
            "joined_today": 1,
            "active_users": 10,
            "banned_users": 0,
            "languages": [("en", 10)],
            "top_locations": [],
            "unspecified_locations": 10,
            "avg_age": 25.0,
            "min_age": 20,
            "max_age": 30,
        }

        with (
            patch("ratemypic.handlers.admin.os.getenv", return_value="1954359757"),
            patch("ratemypic.handlers.admin.get_admin_dashboard_stats", new=AsyncMock(return_value=sample_stats)),
        ):
            await handle_admin_stats_command(message)

        message.answer.assert_awaited_once()
        self.assertIn("Total Users: 10", message.answer.await_args.args[0])


if __name__ == "__main__":
    unittest.main()
