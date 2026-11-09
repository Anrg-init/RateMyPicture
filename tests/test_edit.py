"""Tests for the account and post edit handlers."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from ratemypic.handlers.edit import (
    cancel_command,
    confirm_post_delete,
    edit_command,
    save_post_caption,
    save_profile_age,
)


class EditHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_edit_command_opens_menu_for_active_user(self) -> None:
        message = AsyncMock()
        message.from_user.id = 123
        state = AsyncMock()
        user = SimpleNamespace(status="active")

        with patch(
            "ratemypic.handlers.edit.get_user_by_telegram_id",
            new=AsyncMock(return_value=user),
        ):
            await edit_command(message, state)

        state.clear.assert_awaited_once()
        keyboard = message.answer.await_args.kwargs["reply_markup"]
        callback_data = [
            button.callback_data
            for row in keyboard.inline_keyboard
            for button in row
        ]
        self.assertEqual(
            callback_data,
            ["edit:profile", "edit:posts:0", "edit:account:delete", "menu:back"],
        )

    async def test_cancel_returns_active_user_to_main_menu(self) -> None:
        message = AsyncMock()
        message.from_user.id = 123
        state = AsyncMock()

        with patch(
            "ratemypic.handlers.edit.get_user_by_telegram_id",
            new=AsyncMock(return_value=SimpleNamespace(status="active")),
        ):
            await cancel_command(message, state)

        state.clear.assert_awaited_once()
        self.assertIn("reply_markup", message.answer.await_args.kwargs)

    async def test_invalid_age_does_not_update_profile(self) -> None:
        message = AsyncMock()
        message.text = "17"
        state = AsyncMock()

        with patch("ratemypic.handlers.edit.update_user_profile") as update_profile:
            await save_profile_age(message, state)

        message.answer.assert_awaited_once()
        update_profile.assert_not_awaited()

    async def test_valid_caption_updates_current_post(self) -> None:
        message = AsyncMock()
        message.text = "A new caption"
        message.from_user.id = 123
        state = AsyncMock()
        state.get_data.return_value = {"edit_post_id": 9}
        user = SimpleNamespace(id=4, status="active")

        with (
            patch(
                "ratemypic.handlers.edit.get_user_by_telegram_id",
                new=AsyncMock(return_value=user),
            ),
            patch(
                "ratemypic.handlers.edit.update_post",
                new=AsyncMock(return_value=True),
            ) as update_post,
        ):
            await save_post_caption(message, state)

        update_post.assert_awaited_once_with(4, 9, caption="A new caption")
        state.clear.assert_awaited_once()
        self.assertIn("Caption updated", message.answer.await_args.args[0])

    async def test_post_delete_shows_explicit_confirmation(self) -> None:
        callback = AsyncMock()
        callback.data = "edit:post:delete:17"
        callback.from_user.id = 123
        callback.message = AsyncMock()
        state = AsyncMock()
        user = SimpleNamespace(id=4, status="active")
        post = SimpleNamespace(id=17)

        with (
            patch(
                "ratemypic.handlers.edit.get_user_by_telegram_id",
                new=AsyncMock(return_value=user),
            ),
            patch(
                "ratemypic.handlers.edit.get_owned_post",
                new=AsyncMock(return_value=post),
            ),
        ):
            await confirm_post_delete(callback, state)

        keyboard = callback.message.answer.await_args.kwargs["reply_markup"]
        self.assertEqual(
            keyboard.inline_keyboard[0][0].callback_data,
            "edit:post:delete:confirm:17",
        )


if __name__ == "__main__":
    unittest.main()