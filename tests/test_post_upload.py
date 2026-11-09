"""Tests for choosing and uploading multiple post photos."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from ratemypic.handlers.posts import (
    CreatePost,
    choose_post_photo_count,
    process_post_caption,
    process_post_photo,
)


class PostUploadTests(unittest.IsolatedAsyncioTestCase):
    async def test_photo_count_button_starts_upload(self) -> None:
        callback = AsyncMock()
        callback.data = "post:count:3"
        callback.message = AsyncMock()
        state = AsyncMock()

        await choose_post_photo_count(callback, state)

        state.update_data.assert_awaited_once_with(photo_count=3, post_photos=[])
        state.set_state.assert_awaited_once_with(CreatePost.photo)
        self.assertIn("photo 1 of 3", callback.message.answer.await_args.args[0])

    async def test_each_photo_is_requested_in_order(self) -> None:
        message = AsyncMock()
        message.photo = [SimpleNamespace(file_id="id-1", file_unique_id="unique-1")]
        state = AsyncMock()
        state.get_data.return_value = {
            "photo_count": 3,
            "post_photos": [],
        }

        await process_post_photo(message, state)

        state.update_data.assert_awaited_once_with(
            post_photos=[{"file_id": "id-1", "unique_id": "unique-1"}]
        )
        self.assertIn("photo 2 of 3", message.answer.await_args.args[0])
        state.set_state.assert_not_awaited()

    async def test_three_photo_ids_are_saved_with_post(self) -> None:
        message = AsyncMock()
        message.text = "Three photos together"
        message.from_user.id = 123
        state = AsyncMock()
        state.get_data.return_value = {
            "post_photos": [
                {"file_id": "id-1", "unique_id": "unique-1"},
                {"file_id": "id-2", "unique_id": "unique-2"},
                {"file_id": "id-3", "unique_id": "unique-3"},
            ]
        }
        user = SimpleNamespace(id=5)

        with (
            patch(
                "ratemypic.handlers.posts.get_user_by_telegram_id",
                new=AsyncMock(return_value=user),
            ),
            patch(
                "ratemypic.handlers.posts.create_post",
                new=AsyncMock(),
            ) as create_post,
        ):
            await process_post_caption(message, state)

        create_post.assert_awaited_once_with(
            user_id=5,
            photo_file_id="id-1",
            photo_unique_id="unique-1",
            photo2_file_id="id-2",
            photo2_unique_id="unique-2",
            photo3_file_id="id-3",
            photo3_unique_id="unique-3",
            caption="Three photos together",
        )


if __name__ == "__main__":
    unittest.main()
