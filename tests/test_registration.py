"""Tests for registration and Terms of Service handlers."""

import unittest
from unittest.mock import AsyncMock, patch

from ratemypic.handlers.registration import process_language_button, terms_command
from ratemypic.i18n import SUPPORTED_LANGUAGES


class TermsCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_terms_command_uses_language_selected_during_registration(self) -> None:
        message = AsyncMock()
        state = AsyncMock()
        state.get_data.return_value = {"language": "ru"}

        await terms_command(message, state)

        terms_text = message.answer.await_args.args[0]
        self.assertIn("УСЛОВИЯ ИСПОЛЬЗОВАНИЯ", terms_text)
        self.assertIn("старше 18 лет", terms_text)

    async def test_terms_command_defaults_to_english(self) -> None:
        message = AsyncMock()
        state = AsyncMock()
        state.get_data.return_value = {}

        await terms_command(message, state)

        terms_text = message.answer.await_args.args[0]
        self.assertIn("TERMS OF SERVICE", terms_text)
        self.assertIn("at least 18 years old", terms_text)


class LanguageSelectionTests(unittest.IsolatedAsyncioTestCase):
    @patch("ratemypic.handlers.registration.send_next_post")
    @patch("ratemypic.handlers.registration.save_user")
    @patch("ratemypic.handlers.registration.get_user_by_telegram_id")
    async def test_every_supported_language_can_continue_registration(
        self,
        mock_get_user: AsyncMock,
        mock_save_user: AsyncMock,
        mock_send_next: AsyncMock,
    ) -> None:
        mock_get_user.return_value = None
        mock_user = AsyncMock()
        mock_user.id = 1
        mock_user.name = "Alex"
        mock_save_user.return_value = mock_user

        for language in SUPPORTED_LANGUAGES:
            with self.subTest(language=language):
                callback = AsyncMock()
                callback.data = f"lang:{language}"
                callback.from_user.id = 12345
                callback.from_user.first_name = "Alex"
                state = AsyncMock()

                await process_language_button(callback, state)

                state.clear.assert_awaited_once()
                callback.answer.assert_awaited_once()
                mock_save_user.assert_awaited()
                mock_send_next.assert_awaited()

    @patch("ratemypic.handlers.registration.save_user")
    async def test_gender_step_and_finalize_registration(self, mock_save_user: AsyncMock) -> None:
        from ratemypic.handlers.registration import process_gender_button, finalize_registration, Registration

        callback = AsyncMock()
        callback.data = "gender:female"
        state = AsyncMock()
        state.get_data.return_value = {"language": "en"}

        await process_gender_button(callback, state)

        state.update_data.assert_awaited_once_with(gender="female")
        state.set_state.assert_awaited_once_with(Registration.location)

        # Test finalize registration passes gender to save_user
        state.get_data.return_value = {
            "name": "Anna",
            "age": 22,
            "gender": "female",
            "language": "en",
        }
        telegram_user = AsyncMock()
        telegram_user.id = 999
        telegram_user.username = "anna_test"

        await finalize_registration(
            chat_id=123,
            bot=AsyncMock(),
            telegram_user=telegram_user,
            location="Berlin",
            state=state,
        )

        mock_save_user.assert_awaited_once()
        kwargs = mock_save_user.await_args.kwargs
        self.assertEqual(kwargs.get("gender"), "female")
        self.assertEqual(kwargs.get("name"), "Anna")
        self.assertEqual(kwargs.get("age"), 22)
        self.assertEqual(kwargs.get("status"), "active")


if __name__ == "__main__":
    unittest.main()