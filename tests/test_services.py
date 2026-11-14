"""Unit tests for services functions."""

from datetime import datetime, timezone
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from ratemypic.models import Rating
from ratemypic.services import (
    get_next_post_to_rate,
    save_rating,
    save_user,
    update_post,
    update_user_profile,
)


class SaveUserTests(unittest.IsolatedAsyncioTestCase):
    async def test_save_new_user(self) -> None:
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        @patch("ratemypic.services.session_scope")
        async def run_test(mock_scope):
            mock_scope.return_value.__aenter__.return_value = mock_session

            user = await save_user(
                telegram_id=123456789,
                name="Alice",
                age=25,
                location="London",
                language="en",
                terms_accepted_at=datetime.now(timezone.utc),
            )

            self.assertEqual(user.telegram_id, 123456789)
            self.assertEqual(user.name, "Alice")
            self.assertEqual(user.age, 25)
            self.assertEqual(user.location, "London")
            self.assertEqual(user.status, "active")
            mock_session.add.assert_called_once_with(user)

        await run_test()


class SaveRatingTests(unittest.IsolatedAsyncioTestCase):
    async def test_rating_totals_use_atomic_sql_increments(self) -> None:
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_result = MagicMock()
        mock_result.one.return_value = (4, 16)
        mock_session.execute.return_value = mock_result

        @patch("ratemypic.services.session_scope")
        async def run_test(mock_scope):
            mock_scope.return_value.__aenter__.return_value = mock_session

            rating = await save_rating(
                post_id=10,
                rater_id=20,
                score=5,
                comment="Nice picture",
            )

            self.assertIsInstance(rating, Rating)
            self.assertEqual(rating.post_id, 10)
            self.assertEqual(rating.rater_id, 20)
            mock_session.add.assert_called_once_with(rating)

            statement = str(mock_session.execute.await_args.args[0])
            self.assertIn("posts.rating_count +", statement)
            self.assertIn("posts.rating_sum +", statement)
            self.assertIn("RETURNING posts.rating_count, posts.rating_sum", statement)

        await run_test()


class NextPostToRateTests(unittest.IsolatedAsyncioTestCase):
    async def test_falls_back_to_any_unrated_post_after_both_buckets(self) -> None:
        empty_result = MagicMock()
        empty_result.scalar_one_or_none.return_value = None
        selected_post = SimpleNamespace(id=10, rating_count=14)
        final_result = MagicMock()
        final_result.scalar_one_or_none.return_value = selected_post
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            side_effect=[empty_result, empty_result, final_result]
        )

        with patch("ratemypic.services.session_scope") as mock_scope:
            mock_scope.return_value.__aenter__.return_value = mock_session
            post = await get_next_post_to_rate(user_id=7, prefer_low_count=True)

        self.assertIs(post, selected_post)
        self.assertEqual(mock_session.execute.await_count, 3)
        fallback_query = str(mock_session.execute.await_args_list[2].args[0])
        self.assertIn("posts.status =", fallback_query)
        self.assertIn("posts.user_id !=", fallback_query)
        self.assertIn("posts.id NOT IN", fallback_query)
        self.assertIn("ratings.post_id", fallback_query)
        self.assertIn("post_reactions.post_id", fallback_query)
        self.assertIn("post_views.post_id", fallback_query)
        self.assertNotIn("posts.rating_count <", fallback_query)
        self.assertNotIn("posts.rating_count >=", fallback_query)

    async def test_record_post_view_creates_view_record(self) -> None:
        from ratemypic.services import record_post_view
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("ratemypic.services.session_scope") as mock_scope:
            mock_scope.return_value.__aenter__.return_value = mock_session
            saved = await record_post_view(user_id=7, post_id=10)

        self.assertTrue(saved)
        mock_session.add.assert_called_once()
        added_view = mock_session.add.call_args.args[0]
        self.assertEqual(added_view.user_id, 7)
        self.assertEqual(added_view.post_id, 10)


class EditServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_update_profile_changes_only_editable_fields(self) -> None:
        user = SimpleNamespace(name="Alice", age=25, location="London")
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_session.execute.return_value = mock_result

        with patch("ratemypic.services.session_scope") as mock_scope:
            mock_scope.return_value.__aenter__.return_value = mock_session
            updated = await update_user_profile(123, "Alicia", 26, "Paris")

        self.assertTrue(updated)
        self.assertEqual(user.name, "Alicia")
        self.assertEqual(user.age, 26)
        self.assertEqual(user.location, "Paris")

    async def test_update_post_query_is_scoped_to_owner(self) -> None:
        post = SimpleNamespace(caption="Old caption")
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = post
        mock_session.execute.return_value = mock_result

        with patch("ratemypic.services.session_scope") as mock_scope:
            mock_scope.return_value.__aenter__.return_value = mock_session
            updated = await update_post(4, 17, caption="New caption")

        self.assertTrue(updated)
        self.assertEqual(post.caption, "New caption")
        statement = str(mock_session.execute.await_args.args[0])
        self.assertIn("posts.user_id", statement)
        self.assertIn("posts.id", statement)

    async def test_update_missing_post_returns_false(self) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with patch("ratemypic.services.session_scope") as mock_scope:
            mock_scope.return_value.__aenter__.return_value = mock_session
            updated = await update_post(4, 17, caption="New caption")

        self.assertFalse(updated)


if __name__ == "__main__":
    unittest.main()
