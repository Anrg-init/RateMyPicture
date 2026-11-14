"""Tests for the rating flow handlers."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from ratemypic.handlers.rating import (
    process_emoji_reaction,
    process_skip_comment,
    process_star_rating,
    send_next_post,
    show_post_comments,
    start_rating_feed,
)
from ratemypic.keyboards import post_comments_keyboard, star_rating_keyboard


DEFAULT_REACTIONS = {"😭": 0, "🤣": 0, "☠️": 0, "😍": 0, "💩": 0, "🍑": 0, "🍌": 0, "🔥": 0}


class RatingHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_post_keyboard_places_comments_before_menu(self) -> None:
        keyboard = star_rating_keyboard(10)
        buttons = [button for row in keyboard.inline_keyboard for button in row]

        # 5 Star ratings
        self.assertEqual(
            [button.callback_data for button in buttons[:5]],
            [f"rate:10:{score}" for score in (5, 4, 3, 2, 1)],
        )
        self.assertEqual(
            [button.style for button in buttons[:5]],
            ["success", "success", "primary", "danger", "danger"],
        )

        # 8 Social reactions
        self.assertEqual(
            [button.callback_data for button in buttons[5:13]],
            [f"react:10:{e}" for e in ("😭", "🤣", "☠️", "😍", "💩", "🍑", "🍌", "🔥")],
        )

        self.assertEqual(buttons[-2].text, "💬 Show comments")
        self.assertEqual(buttons[-2].callback_data, "comments:10:0")
        self.assertEqual(buttons[-1].callback_data, "menu:back")

    async def test_comment_view_shows_page_and_next_button(self) -> None:
        callback = AsyncMock()
        callback.data = "comments:10:0"
        callback.message = AsyncMock()
        state = AsyncMock()
        state.get_data.return_value = {"current_post_id": 10}
        comments = [
            SimpleNamespace(score=5, comment="Nice <photo> & frame")
            for _ in range(6)
        ]

        with patch(
            "ratemypic.handlers.rating.get_post_comments",
            new=AsyncMock(return_value=comments),
        ) as get_comments:
            await show_post_comments(callback, state)

        get_comments.assert_awaited_once_with(10, limit=6, offset=0)
        sent_message = callback.message.answer.await_args.kwargs
        sent_text = callback.message.answer.await_args.args[0]
        self.assertIn("Nice &lt;photo&gt; &amp; frame", sent_text)
        self.assertIn("\n\n", sent_text)
        self.assertEqual(sent_message["parse_mode"], "HTML")
        self.assertEqual(
            sent_message["reply_markup"].inline_keyboard[0][0].callback_data,
            "comments:10:5",
        )

    async def test_stale_comment_button_is_rejected(self) -> None:
        callback = AsyncMock()
        callback.data = "comments:9:0"
        state = AsyncMock()
        state.get_data.return_value = {"current_post_id": 10}

        with patch("ratemypic.handlers.rating.get_post_comments") as get_comments:
            await show_post_comments(callback, state)

        callback.answer.assert_awaited_once_with(
            "That comments button has expired.", show_alert=True
        )
        get_comments.assert_not_called()

    async def test_comment_pagination_has_previous_and_next_buttons(self) -> None:
        keyboard = post_comments_keyboard(
            post_id=10,
            offset=5,
            has_previous=True,
            has_next=True,
        )

        self.assertEqual(
            [button.callback_data for button in keyboard.inline_keyboard[0]],
            ["comments:10:0", "comments:10:10"],
        )

    async def test_stale_star_button_is_rejected(self) -> None:
        callback = AsyncMock()
        callback.data = "rate:9:4"
        callback.from_user.id = 123
        callback.message = AsyncMock()
        state = AsyncMock()
        state.get_data.return_value = {"current_post_id": 10}

        with patch("ratemypic.handlers.rating.get_user_by_telegram_id") as get_user:
            await process_star_rating(callback, state)

        callback.message.answer.assert_awaited_once()
        state.update_data.assert_not_awaited()
        get_user.assert_not_called()

    async def test_out_of_range_star_score_is_rejected(self) -> None:
        callback = AsyncMock()
        callback.data = "rate:10:6"
        callback.from_user.id = 123
        callback.message = AsyncMock()
        state = AsyncMock()
        state.get_data.return_value = {"current_post_id": 10}

        with patch("ratemypic.handlers.rating.get_user_by_telegram_id") as get_user:
            await process_star_rating(callback, state)

        callback.message.answer.assert_awaited_once()
        state.update_data.assert_not_awaited()
        get_user.assert_not_called()

    async def test_stale_skip_button_does_not_finalize_current_rating(self) -> None:
        callback = AsyncMock()
        callback.data = "skipcomment:9"
        callback.message = AsyncMock()
        callback.from_user.id = 123
        state = AsyncMock()
        state.get_data.return_value = {"pending_post_id": 10}

        with patch("ratemypic.handlers.rating._finalize_rating") as finalize:
            await process_skip_comment(callback, state)

        callback.answer.assert_awaited_once_with("That comment prompt has expired.")
        finalize.assert_not_awaited()

    async def test_rate_menu_starts_the_real_rating_feed(self) -> None:
        callback = AsyncMock()
        callback.from_user.id = 123
        callback.message.chat.id = 456
        state = AsyncMock()
        state.get_data.return_value = {"rating_turn": 0}
        user = SimpleNamespace(id=7)
        post = SimpleNamespace(
            id=10,
            caption="A <photo>",
            rating_count=0,
            rating_sum=0,
            photo1_file_id="photo-file-id",
            photo2_file_id=None,
            photo3_file_id=None,
        )

        with (
            patch(
                "ratemypic.handlers.rating.get_user_by_telegram_id",
                new=AsyncMock(return_value=user),
            ),
            patch(
                "ratemypic.handlers.rating.get_next_post_to_rate",
                new=AsyncMock(return_value=post),
            ) as get_next_post,
            patch(
                "ratemypic.handlers.rating.get_post_reactions",
                new=AsyncMock(return_value=DEFAULT_REACTIONS),
            ),
            patch(
                "ratemypic.handlers.rating.record_post_view",
                new=AsyncMock(return_value=True),
            ) as record_view,
        ):
            await start_rating_feed(callback, state)

        get_next_post.assert_awaited_once_with(user_id=7, prefer_low_count=True)
        record_view.assert_awaited_once_with(user_id=7, post_id=10)
        callback.bot.send_photo.assert_awaited_once()
        sent_photo = callback.bot.send_photo.await_args.kwargs
        self.assertIn("A &lt;photo&gt;", sent_photo["caption"])
        self.assertEqual(sent_photo["parse_mode"], "HTML")
        state.set_state.assert_awaited_once()

    async def test_rating_feed_sends_multiple_photos_as_album(self) -> None:
        state = AsyncMock()
        state.get_data.return_value = {"rating_turn": 0}
        bot = AsyncMock()
        post = SimpleNamespace(
            id=10,
            caption="A photo set",
            rating_count=0,
            rating_sum=0,
            photo1_file_id="photo-one",
            photo2_file_id="photo-two",
            photo3_file_id=None,
        )

        with (
            patch(
                "ratemypic.handlers.rating.get_next_post_to_rate",
                new=AsyncMock(return_value=post),
            ),
            patch(
                "ratemypic.handlers.rating.get_post_reactions",
                new=AsyncMock(return_value=DEFAULT_REACTIONS),
            ),
            patch(
                "ratemypic.handlers.rating.record_post_view",
                new=AsyncMock(return_value=True),
            ),
        ):
            await send_next_post(chat_id=456, user_id=7, state=state, bot=bot)

        bot.send_media_group.assert_awaited_once()
        media = bot.send_media_group.await_args.kwargs["media"]
        self.assertEqual([item.media for item in media], ["photo-one", "photo-two"])
        self.assertEqual(bot.send_message.call_count, 2)
        album_caption_call = bot.send_message.call_args_list[1]
        self.assertEqual(
            album_caption_call.kwargs["reply_markup"].inline_keyboard[-1][0].callback_data,
            "menu:back",
        )
        bot.delete_message.assert_awaited_once()

    async def test_rating_feed_prioritizes_low_count_posts_two_to_one(self) -> None:
        state = AsyncMock()
        state.get_data.side_effect = [
            {"rating_turn": turn} for turn in range(3)
        ]
        bot = AsyncMock()
        post = SimpleNamespace(
            id=10,
            caption="A photo",
            rating_count=0,
            rating_sum=0,
            photo1_file_id="photo-one",
            photo2_file_id=None,
            photo3_file_id=None,
        )

        with (
            patch(
                "ratemypic.handlers.rating.get_next_post_to_rate",
                new=AsyncMock(return_value=post),
            ) as get_next_post,
            patch(
                "ratemypic.handlers.rating.get_post_reactions",
                new=AsyncMock(return_value=DEFAULT_REACTIONS),
            ),
            patch(
                "ratemypic.handlers.rating.record_post_view",
                new=AsyncMock(return_value=True),
            ),
        ):
            for _ in range(3):
                await send_next_post(chat_id=456, user_id=7, state=state, bot=bot)

        self.assertEqual(
            [call.kwargs["prefer_low_count"] for call in get_next_post.await_args_list],
            [True, True, False],
        )

    async def test_emoji_reaction_toggles_and_answers_toast(self) -> None:
        callback = AsyncMock()
        callback.data = "react:10:🔥"
        callback.from_user.id = 123
        callback.message = AsyncMock()
        callback.message.caption = "Caption"
        state = AsyncMock()
        state.get_data.return_value = {"current_post_id": 10, "language": "en"}

        user = SimpleNamespace(id=7)
        post = SimpleNamespace(
            id=10,
            caption="A photo",
            rating_count=1,
            rating_sum=5,
        )

        with (
            patch("ratemypic.handlers.rating.get_user_by_telegram_id", new=AsyncMock(return_value=user)),
            patch("ratemypic.handlers.rating.toggle_post_reaction", new=AsyncMock(return_value=True)) as toggle_rx,
            patch("ratemypic.handlers.rating.get_post_by_id", new=AsyncMock(return_value=post)),
            patch("ratemypic.handlers.rating.get_post_reactions", new=AsyncMock(return_value=DEFAULT_REACTIONS)),
        ):
            await process_emoji_reaction(callback, state)

        toggle_rx.assert_awaited_once_with(post_id=10, user_id=7, reaction="🔥")
        callback.answer.assert_awaited_once_with("Added 🔥!")
        callback.message.edit_caption.assert_awaited_once()

    async def test_skip_post_loads_next_post(self) -> None:
        from ratemypic.handlers.rating import process_skip_post
        callback = AsyncMock()
        callback.data = "rate:skip:10"
        callback.from_user.id = 123
        callback.message = AsyncMock()
        callback.message.chat.id = 456
        state = AsyncMock()
        user = SimpleNamespace(id=7)

        with (
            patch("ratemypic.handlers.rating.get_user_by_telegram_id", new=AsyncMock(return_value=user)),
            patch("ratemypic.handlers.rating.send_next_post", new=AsyncMock()) as send_mock,
        ):
            await process_skip_post(callback, state)

        callback.answer.assert_awaited_once()
        send_mock.assert_awaited_once_with(
            chat_id=456,
            user_id=7,
            state=state,
            bot=callback.bot,
        )


if __name__ == "__main__":
    unittest.main()