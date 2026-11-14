"""Tests for rating notifications, milestone alerts, and retention reminders."""

from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from ratemypic.notifications import notify_post_owner_of_rating, send_retention_broadcast


class NotificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_owner_receives_rating_notification(self) -> None:
        bot = AsyncMock()
        owner = SimpleNamespace(
            id=10,
            telegram_id=123456789,
            language="en",
            notifications_enabled=True,
        )
        post = SimpleNamespace(
            id=5,
            user_id=10,
            rating_count=3,
            rating_sum=12,
        )

        with (
            patch("ratemypic.notifications.get_post_owner_for_notification", new=AsyncMock(return_value=owner)),
            patch("ratemypic.notifications.get_post_by_id", new=AsyncMock(return_value=post)),
        ):
            success = await notify_post_owner_of_rating(
                bot=bot,
                post_id=5,
                rater_id=20,  # Different user
                score=5,
                comment="Awesome picture!",
            )

        self.assertTrue(success)
        bot.send_message.assert_awaited_once()
        sent_args = bot.send_message.await_args
        self.assertEqual(sent_args.kwargs["chat_id"], 123456789)
        self.assertIn("New rating on your photo", sent_args.kwargs["text"])
        self.assertIn("Score:", sent_args.kwargs["text"])
        self.assertIn("Awesome picture!", sent_args.kwargs["text"])

    async def test_guard_against_self_rating_notification(self) -> None:
        bot = AsyncMock()
        owner = SimpleNamespace(
            id=10,
            telegram_id=123456789,
            language="en",
            notifications_enabled=True,
        )

        with (
            patch("ratemypic.notifications.get_post_owner_for_notification", new=AsyncMock(return_value=owner)),
        ):
            # rater_id is same as owner.id
            success = await notify_post_owner_of_rating(
                bot=bot,
                post_id=5,
                rater_id=10,
                score=5,
                comment="Self rating",
            )

        self.assertFalse(success)
        bot.send_message.assert_not_awaited()

    async def test_notifications_disabled_does_not_send(self) -> None:
        bot = AsyncMock()
        owner = SimpleNamespace(
            id=10,
            telegram_id=123456789,
            language="en",
            notifications_enabled=False,  # Turned OFF
        )

        with (
            patch("ratemypic.notifications.get_post_owner_for_notification", new=AsyncMock(return_value=owner)),
        ):
            success = await notify_post_owner_of_rating(
                bot=bot,
                post_id=5,
                rater_id=20,
                score=4,
                comment=None,
            )

        self.assertFalse(success)
        bot.send_message.assert_not_awaited()

    async def test_milestone_alert_included_when_milestone_hit(self) -> None:
        bot = AsyncMock()
        owner = SimpleNamespace(
            id=10,
            telegram_id=123456789,
            language="en",
            notifications_enabled=True,
        )
        post = SimpleNamespace(
            id=5,
            user_id=10,
            rating_count=10,  # Milestone 10!
            rating_sum=42,
        )

        with (
            patch("ratemypic.notifications.get_post_owner_for_notification", new=AsyncMock(return_value=owner)),
            patch("ratemypic.notifications.get_post_by_id", new=AsyncMock(return_value=post)),
        ):
            success = await notify_post_owner_of_rating(
                bot=bot,
                post_id=5,
                rater_id=20,
                score=5,
                comment=None,
            )

        self.assertTrue(success)
        bot.send_message.assert_awaited_once()
        text = bot.send_message.await_args.kwargs["text"]
        self.assertIn("Milestone reached", text)
        self.assertIn("10", text)

    async def test_retention_broadcast_sends_to_inactive_users(self) -> None:
        bot = AsyncMock()
        inactive_user = SimpleNamespace(
            id=15,
            telegram_id=987654321,
            language="en",
        )
        post = SimpleNamespace(id=2)

        with (
            patch("ratemypic.notifications.get_inactive_users_for_retention", new=AsyncMock(return_value=[inactive_user])),
            patch("ratemypic.notifications.get_next_post_to_rate", new=AsyncMock(return_value=post)),
            patch("ratemypic.notifications.mark_user_notified", new=AsyncMock()) as mock_mark,
        ):
            count = await send_retention_broadcast(bot=bot, hours_inactive=48, limit=10)

        self.assertEqual(count, 1)
        bot.send_message.assert_awaited_once()
        self.assertEqual(bot.send_message.await_args.kwargs["chat_id"], 987654321)
        mock_mark.assert_awaited_once_with(15)


if __name__ == "__main__":
    unittest.main()
