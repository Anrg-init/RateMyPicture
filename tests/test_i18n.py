"""Tests for the supported user-interface locales."""

import unittest

from ratemypic.i18n import SUPPORTED_LANGUAGES, t
from ratemypic.keyboards import language_keyboard, main_menu_keyboard


class LocalizationTests(unittest.TestCase):
    def test_only_locales_with_real_catalogs_are_offered(self) -> None:
        self.assertEqual(set(SUPPORTED_LANGUAGES), {"en", "ru", "es", "pt", "id"})

    def test_all_supported_locales_have_terms_and_catalogs(self) -> None:
        from ratemypic.terms import TERMS_OF_SERVICE
        for lang in SUPPORTED_LANGUAGES:
            self.assertIn(lang, TERMS_OF_SERVICE)
            self.assertGreater(len(TERMS_OF_SERVICE[lang]), 100)
            self.assertIn("18", t("registration.age_invalid", lang=lang))

    def test_selected_locale_changes_registration_copy(self) -> None:
        english = t("registration.age_invalid", lang="en")
        russian = t("registration.age_invalid", lang="ru")

        self.assertNotEqual(english, russian)
        self.assertIn("18 and 99", english)
        self.assertIn("18 до 99", russian)

    def test_unknown_locale_falls_back_to_english(self) -> None:
        self.assertEqual(
            t("registration.age_invalid", lang="unsupported"),
            t("registration.age_invalid", lang="en"),
        )

    def test_language_and_main_menu_keyboards_use_selected_locale(self) -> None:
        language_labels = [
            button.text
            for row in language_keyboard("ru").inline_keyboard
            for button in row
        ]
        menu_labels = [
            button.text
            for row in main_menu_keyboard("ru").inline_keyboard
            for button in row
        ]

        self.assertIn("Русский 🇷🇺", language_labels)
        self.assertIn("Мой профиль", menu_labels[0])
        self.assertIn("Оценивать фото", menu_labels[1])


if __name__ == "__main__":
    unittest.main()
