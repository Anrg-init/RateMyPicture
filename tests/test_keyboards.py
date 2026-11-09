"""Tests for Telegram inline keyboard button styling."""

import unittest

from ratemypic.keyboards import (
    cancel_post_keyboard,
    confirm_delete_keyboard,
    edit_home_keyboard,
    edit_post_keyboard,
    edit_post_photo_keyboard,
    edit_posts_keyboard,
    empty_posts_keyboard,
    language_keyboard,
    location_keyboard,
    main_menu_keyboard,
    no_more_posts_keyboard,
    post_comments_keyboard,
    post_photo_count_keyboard,
    posts_list_keyboard,
    profile_edit_keyboard,
    skip_comment_keyboard,
    star_rating_keyboard,
    terms_keyboard,
)


class KeyboardStyleTests(unittest.TestCase):
    def test_every_keyboard_button_has_a_color_style(self) -> None:
        keyboards = [
            language_keyboard(),
            terms_keyboard(),
            location_keyboard(),
            main_menu_keyboard(),
            edit_home_keyboard(),
            profile_edit_keyboard(),
            edit_posts_keyboard([], offset=0, has_next=False),
            edit_post_keyboard(1),
            edit_post_photo_keyboard(1, photo_count=2),
            confirm_delete_keyboard("confirm", "cancel"),
            empty_posts_keyboard(),
            posts_list_keyboard(),
            cancel_post_keyboard(),
            post_photo_count_keyboard(),
            star_rating_keyboard(1),
            post_comments_keyboard(1, offset=0, has_previous=False, has_next=True),
            skip_comment_keyboard(1),
            no_more_posts_keyboard(),
        ]

        for keyboard in keyboards:
            for row in keyboard.inline_keyboard:
                for item in row:
                    with self.subTest(button=item.text):
                        self.assertIn(item.style, {"primary", "success", "danger"})

    def test_button_colors_match_action_meaning(self) -> None:
        terms_buttons = terms_keyboard().inline_keyboard[0]
        menu_buttons = main_menu_keyboard().inline_keyboard
        delete_buttons = confirm_delete_keyboard("confirm", "cancel").inline_keyboard[0]

        self.assertEqual([item.style for item in terms_buttons], ["success", "danger"])
        self.assertEqual(menu_buttons[1][0].style, "success")
        self.assertEqual([item.style for item in delete_buttons], ["danger", "primary"])


if __name__ == "__main__":
    unittest.main()
