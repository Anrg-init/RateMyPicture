"""Unit tests for direct message (DM) handlers."""

from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from ratemypic.handlers.dm import (
    DMFlow,
    on_cancel_dm,
    on_reply_dm_clicked,
    on_send_dm_clicked,
    on_view_inbox_dms,
    process_dm_text,
    process_reply_text,
)


class DMHandlerTests(unittest.IsolatedAsyncioTestCase):
    @patch("ratemypic.handlers.dm.get_user_by_telegram_id")
    async def test_unregistered_user_redirected_to_registration(self, mock_get_user: AsyncMock) -> None:
        mock_get_user.return_value = None
        callback = AsyncMock()
        callback.data = "dm:send:42"
        callback.from_user.id = 12345
        callback.message = AsyncMock()
        state = AsyncMock()

        await on_send_dm_clicked(callback, state)

        state.update_data.assert_awaited_once_with(language="en", post_registration_action="dm:send:42")
        state.set_state.assert_awaited_once()
        callback.message.answer.assert_awaited_once()

    @patch("ratemypic.handlers.dm.get_post_by_id")
    @patch("ratemypic.handlers.dm.get_user_by_telegram_id")
    async def test_cannot_dm_own_photo(self, mock_get_user: AsyncMock, mock_get_post: AsyncMock) -> None:
        mock_user = SimpleNamespace(id=1, status="active", language="en")
        mock_post = SimpleNamespace(id=42, user_id=1)
        mock_get_user.return_value = mock_user
        mock_get_post.return_value = mock_post

        callback = AsyncMock()
        callback.data = "dm:send:42"
        callback.from_user.id = 12345
        callback.message = AsyncMock()
        callback.bot = AsyncMock()
        state = AsyncMock()

        await on_send_dm_clicked(callback, state)

        callback.bot.send_message.assert_awaited_once()
        args, kwargs = callback.bot.send_message.await_args
        self.assertIn("cannot send a private note to your own photo", kwargs.get("text", args[0] if args else ""))

    @patch("ratemypic.handlers.dm.get_user_by_id")
    @patch("ratemypic.handlers.dm.create_direct_message")
    @patch("ratemypic.handlers.dm.get_user_by_telegram_id")
    async def test_process_dm_text_creates_dm_and_notifies_author(
        self,
        mock_get_sender: AsyncMock,
        mock_create_dm: AsyncMock,
        mock_get_recipient: AsyncMock,
    ) -> None:
        sender = SimpleNamespace(id=10, name="Alex", age=25, gender="male", location="London")
        recipient = SimpleNamespace(id=20, telegram_id=999888, language="en")
        mock_dm = SimpleNamespace(id=101)

        mock_get_sender.return_value = sender
        mock_create_dm.return_value = mock_dm
        mock_get_recipient.return_value = recipient

        message = AsyncMock()
        message.text = "Hey, love your photo!"
        message.from_user.id = 12345
        message.bot = AsyncMock()
        state = AsyncMock()
        state.get_data.return_value = {
            "language": "en",
            "recipient_id": 20,
            "target_post_id": 42,
        }

        await process_dm_text(message, state)

        mock_create_dm.assert_awaited_once_with(
            sender_id=10,
            recipient_id=20,
            text="Hey, love your photo!",
            post_id=42,
        )
        state.clear.assert_awaited_once()
        message.answer.assert_awaited_once()
        message.bot.send_message.assert_awaited_once()

    @patch("ratemypic.handlers.dm.get_user_by_telegram_id")
    async def test_cancel_dm(self, mock_get_user: AsyncMock) -> None:
        mock_get_user.return_value = SimpleNamespace(id=1, language="en")
        callback = AsyncMock()
        callback.from_user.id = 12345
        callback.message = AsyncMock()
        state = AsyncMock()

        await on_cancel_dm(callback, state)

        state.clear.assert_awaited_once()
        callback.answer.assert_awaited_once()
        callback.message.answer.assert_awaited_once()

    @patch("ratemypic.handlers.dm.count_user_inbox_conversations")
    @patch("ratemypic.handlers.dm.get_user_inbox_conversations")
    @patch("ratemypic.handlers.dm.get_user_by_telegram_id")
    async def test_view_inbox_conversations_grouped(
        self,
        mock_get_user: AsyncMock,
        mock_get_convs: AsyncMock,
        mock_count: AsyncMock,
    ) -> None:
        user = SimpleNamespace(id=1, language="en")
        mock_get_user.return_value = user

        sender = SimpleNamespace(id=10, name="Sirza", age=24, gender="female", country="ru", location=None)
        latest_dm = SimpleNamespace(id=101, text="Yesss")
        mock_get_convs.return_value = [
            {"sender": sender, "latest_dm": latest_dm, "total_count": 2, "unread_count": 1}
        ]
        mock_count.return_value = 1

        callback = AsyncMock()
        callback.data = "dm:inbox:0"
        callback.from_user.id = 12345
        callback.message = AsyncMock()
        state = AsyncMock()

        await on_view_inbox_dms(callback, state)

        mock_get_convs.assert_awaited_once_with(1, limit=5, offset=0)
        callback.message.answer.assert_awaited_once()
        args, kwargs = callback.message.answer.await_args
        text = args[0]
        self.assertIn("Sirza", text)
        self.assertIn("Yesss", text)
        # Verify ugly dashes are NOT in text
        self.assertNotIn("(-)", text)
        self.assertNotIn("📍 -", text)


if __name__ == "__main__":
    unittest.main()
