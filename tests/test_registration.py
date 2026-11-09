"""Tests for registration and Terms of Service handlers."""

import unittest
from unittest.mock import AsyncMock

from ratemypic.handlers.registration import terms_command


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


if __name__ == "__main__":
    unittest.main()