"""Unit tests for menu and post handlers."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from ratemypic.handlers.posts import show_my_feedback


class MenuHandlerTests(unittest.IsolatedAsyncioTestCase):
    @patch("ratemypic.handlers.posts.get_user_posts")
    @patch("ratemypic.handlers.posts.get_user_by_telegram_id")
    async def test_feedback_handler_empty_posts(self, mock_get_user, mock_get_posts) -> None:
        mock_user = AsyncMock()
        mock_user.id = 1
        mock_get_user.return_value = mock_user
        mock_get_posts.return_value = []

        callback = AsyncMock()
        callback.from_user.id = 123456
        callback.message = AsyncMock()

        await show_my_feedback(callback)

        callback.answer.assert_called_once()
        self.assertEqual(callback.message.answer.call_count, 2)
        callback.message.answer.return_value.delete.assert_awaited_once()

    @patch("ratemypic.handlers.posts.get_post_reactions")
    @patch("ratemypic.handlers.posts.get_rating_distribution")
    @patch("ratemypic.handlers.posts.get_post_comments")
    @patch("ratemypic.handlers.posts.get_user_posts")
    @patch("ratemypic.handlers.posts.get_user_by_telegram_id")
    async def test_feedback_handler_with_posts(
        self, mock_get_user, mock_get_posts, mock_get_ratings, mock_get_dist, mock_get_reactions
    ) -> None:
        mock_get_reactions.return_value = {
            "😭": 0, "🤣": 0, "☠️": 0, "😍": 1, "💩": 0, "🍑": 0, "🍌": 0, "🔥": 2
        }
        mock_user = AsyncMock()
        mock_user.id = 1
        mock_user.language = "en"
        mock_get_user.return_value = mock_user

        mock_post = AsyncMock()
        mock_post.id = 10
        mock_post.caption = "Test photo"
        mock_post.photo1_file_id = "file_123"
        mock_post.photo2_file_id = None
        mock_post.photo3_file_id = None
        mock_post.rating_count = 2
        mock_post.rating_sum = 8
        mock_post.status = "approved"

        mock_get_posts.return_value = [mock_post]
        mock_get_ratings.return_value = [
            SimpleNamespace(score=5, comment="Great <photo> & frame")
        ]
        mock_get_dist.return_value = {1: 0, 2: 0, 3: 0, 4: 1, 5: 1}
        mock_get_user.return_value = mock_user

        mock_post = AsyncMock()
        mock_post.id = 10
        mock_post.caption = "Test photo"
        mock_post.photo1_file_id = "file_123"
        mock_post.photo2_file_id = None
        mock_post.photo3_file_id = None
        mock_post.rating_count = 2
        mock_post.rating_sum = 8
        mock_post.status = "approved"

        mock_get_posts.return_value = [mock_post]
        mock_get_ratings.return_value = [
            SimpleNamespace(score=5, comment="Great <photo> & frame")
        ]

        callback = AsyncMock()
        callback.from_user.id = 123456
        callback.message = AsyncMock()

        await show_my_feedback(callback)

        callback.answer.assert_called_once()
        callback.message.answer_photo.assert_called_once()
        sent_photo = callback.message.answer_photo.await_args.kwargs
        self.assertIn("Great &lt;photo&gt; &amp; frame", sent_photo["caption"])
        self.assertEqual(sent_photo["parse_mode"], "HTML")

    @patch("ratemypic.handlers.posts.get_user_by_telegram_id")
    async def test_feedback_handler_redirects_onboarding_user(self, mock_get_user) -> None:
        mock_user = SimpleNamespace(id=1, status="onboarding", language="en", terms_accepted_at=None)
        mock_get_user.return_value = mock_user

        callback = AsyncMock()
        callback.from_user.id = 123456
        callback.message = AsyncMock()
        state = AsyncMock()

        await show_my_feedback(callback, state)

        state.update_data.assert_awaited_once_with(language="en", post_registration_action="menu:feedback")
        state.set_state.assert_awaited_once()
        callback.message.answer.assert_awaited_once()

    @patch("ratemypic.handlers.posts.get_user_by_telegram_id")
    async def test_create_post_redirects_onboarding_user(self, mock_get_user) -> None:
        from ratemypic.handlers.posts import start_create_post
        mock_user = SimpleNamespace(id=1, status="onboarding", language="en", terms_accepted_at=None)
        mock_get_user.return_value = mock_user

        callback = AsyncMock()
        callback.from_user.id = 123456
        callback.message = AsyncMock()
        state = AsyncMock()

        await start_create_post(callback, state)

        state.update_data.assert_awaited_once_with(language="en", post_registration_action="post:create")
        state.set_state.assert_awaited_once()
        callback.message.answer.assert_awaited_once()

if __name__ == "__main__":
    unittest.main()
