"""Database helper functions (CRUD operations).

This file contains simple functions to save and read data from PostgreSQL.
All functions use simple syntax with clear comments and production logging.
"""

from datetime import datetime
import logging
from sqlalchemy import delete, func, select, update
from sqlalchemy.sql.expression import not_

from ratemypic.database import session_scope
from ratemypic.models import Post, Rating, User

logger = logging.getLogger(__name__)


async def save_user(
    telegram_id: int,
    name: str,
    age: int,
    location: str | None,
    language: str = "en",
    terms_accepted_at: datetime | None = None,
) -> User:
    """Save a new user or update an existing user in PostgreSQL."""
    async with session_scope() as session:
        query = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(query)
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                telegram_id=telegram_id,
                name=name,
                age=age,
                location=location,
                language=language,
                status="active",
                terms_accepted_at=terms_accepted_at,
            )
            session.add(user)
            logger.info("Created new user: telegram_id=%d, name='%s'", telegram_id, name)
        else:
            user.name = name
            user.age = age
            user.location = location
            user.language = language
            user.status = "active"
            user.terms_accepted_at = terms_accepted_at
            logger.info("Updated user: telegram_id=%d, name='%s'", telegram_id, name)

        return user


async def get_user_by_telegram_id(telegram_id: int) -> User | None:
    """Find a user in the database by their Telegram ID."""
    logger.debug("Looking up user with telegram_id=%d", telegram_id)
    async with session_scope() as session:
        query = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()


# ===========================================================================
# Post operations
# ===========================================================================
async def get_user_posts(
    user_id: int,
    limit: int | None = None,
    offset: int = 0,
) -> list[Post]:
    """Fetch a user's posts, newest first, optionally paginated."""
    async with session_scope() as session:
        query = (
            select(Post)
            .where(Post.user_id == user_id)
            .order_by(Post.created_at.desc())
            .offset(offset)
        )
        if limit is not None:
            query = query.limit(limit)
        result = await session.execute(query)
        posts = list(result.scalars().all())
        logger.debug("Fetched %d posts for user_id=%d", len(posts), user_id)
        return posts


async def get_owned_post(user_id: int, post_id: int) -> Post | None:
    """Return a post only when it belongs to the given user."""
    async with session_scope() as session:
        query = select(Post).where(Post.id == post_id, Post.user_id == user_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()


async def update_user_profile(
    telegram_id: int,
    name: str,
    age: int,
    location: str | None,
) -> bool:
    """Update the editable profile fields for one Telegram account."""
    async with session_scope() as session:
        query = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(query)
        user = result.scalar_one_or_none()
        if user is None:
            return False

        user.name = name
        user.age = age
        user.location = location
        return True


async def update_post(
    user_id: int,
    post_id: int,
    caption: str | None = None,
    photo_file_id: str | None = None,
    photo_unique_id: str | None = None,
    photo_number: int = 1,
) -> bool:
    """Update a post only when it belongs to the given user."""
    async with session_scope() as session:
        query = select(Post).where(Post.id == post_id, Post.user_id == user_id)
        result = await session.execute(query)
        post = result.scalar_one_or_none()
        if post is None:
            return False

        if caption is not None:
            post.caption = caption
        if photo_file_id is not None and photo_unique_id is not None:
            if photo_number not in (1, 2, 3):
                return False
            setattr(post, f"photo{photo_number}_file_id", photo_file_id)
            setattr(post, f"photo{photo_number}_unique_id", photo_unique_id)
        return True


async def delete_post(user_id: int, post_id: int) -> bool:
    """Delete one post only when it belongs to the given user."""
    async with session_scope() as session:
        query = delete(Post).where(Post.id == post_id, Post.user_id == user_id)
        result = await session.execute(query)
        return result.rowcount > 0


async def delete_user(telegram_id: int) -> bool:
    """Delete a Telegram account and its database-cascaded content."""
    async with session_scope() as session:
        query = delete(User).where(User.telegram_id == telegram_id)
        result = await session.execute(query)
        return result.rowcount > 0


async def create_post(
    user_id: int,
    photo_file_id: str,
    photo_unique_id: str,
    caption: str,
    photo2_file_id: str | None = None,
    photo2_unique_id: str | None = None,
    photo3_file_id: str | None = None,
    photo3_unique_id: str | None = None,
) -> Post:
    """Insert a new post into PostgreSQL."""
    async with session_scope() as session:
        post = Post(
            user_id=user_id,
            photo1_file_id=photo_file_id,
            photo1_unique_id=photo_unique_id,
            photo2_file_id=photo2_file_id,
            photo2_unique_id=photo2_unique_id,
            photo3_file_id=photo3_file_id,
            photo3_unique_id=photo3_unique_id,
            caption=caption,
            status="approved",
            rating_count=0,
            rating_sum=0,
        )
        session.add(post)
        logger.info("Created post for user_id=%d (caption: '%.30s')", user_id, caption)
        return post


async def get_post_comments(
    post_id: int,
    limit: int = 3,
    offset: int = 0,
) -> list[Rating]:
    """Fetch the latest non-empty comments for a specific post."""
    async with session_scope() as session:
        query = (
            select(Rating)
            .where(Rating.post_id == post_id)
            .where(Rating.comment.is_not(None), Rating.comment != "")
            .order_by(Rating.created_at.desc(), Rating.id.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(query)
        comments = list(result.scalars().all())
        logger.debug("Fetched %d comments for post_id=%d", len(comments), post_id)
        return comments


# ===========================================================================
# Rating algorithm
# ===========================================================================
async def get_next_post_to_rate(user_id: int, prefer_low_count: bool) -> Post | None:
    """Pick the next post to show for rating using the alternating algorithm.

    Algorithm:
    - Even turn  (prefer_low_count=True):  find a random approved post with rating_count < 10
    - Odd turn   (prefer_low_count=False): find a random approved post with rating_count >= 10
    - Skip posts owned by this user.
    - Skip posts already rated by this user.
    - If preferred bucket is empty, fall back to the other bucket.

    Args:
        user_id: The database ID of the user requesting the feed.
        prefer_low_count: True = show low-rated post first, False = show popular post.

    Returns:
        A Post object or None if no eligible posts remain.
    """
    async with session_scope() as session:
        # Subquery: IDs of posts this user has already rated
        already_rated_subquery = (
            select(Rating.post_id).where(Rating.rater_id == user_id)
        )

        def base_query(low_count: bool | None):
            query = (
                select(Post)
                .where(Post.status == "approved")
                .where(Post.user_id != user_id)
                .where(not_(Post.id.in_(already_rated_subquery)))
            )
            if low_count is not None:
                count_filter = (
                    Post.rating_count < 10
                    if low_count
                    else Post.rating_count >= 10
                )
                query = query.where(count_filter)
            return query.order_by(func.random()).limit(1)

        # Try preferred bucket first
        result = await session.execute(base_query(prefer_low_count))
        post = result.scalar_one_or_none()

        # Fallback to the other bucket if the preferred one is empty.
        if post is None:
            result = await session.execute(base_query(not prefer_low_count))
            post = result.scalar_one_or_none()

        # As a final fallback, search all eligible posts regardless of rating count.
        if post is None:
            result = await session.execute(base_query(None))
            post = result.scalar_one_or_none()

        if post:
            logger.debug(
                "Serving post_id=%d to user_id=%d (prefer_low=%s, rating_count=%d)",
                post.id, user_id, prefer_low_count, post.rating_count,
            )

        return post


async def save_rating(
    post_id: int,
    rater_id: int,
    score: int,
    comment: str | None,
) -> Rating:
    """Save a user's rating and update the post's running totals atomically."""
    async with session_scope() as session:
        # Create the rating row
        rating = Rating(
            post_id=post_id,
            rater_id=rater_id,
            score=score,
            comment=comment,
        )
        session.add(rating)

        # Increment in SQL so concurrent ratings cannot overwrite each other.
        query = (
            update(Post)
            .where(Post.id == post_id)
            .values(
                rating_count=Post.rating_count + 1,
                rating_sum=Post.rating_sum + score,
            )
            .returning(Post.rating_count, Post.rating_sum)
        )
        result = await session.execute(query)
        rating_count, rating_sum = result.one()

        logger.info(
            "Rating saved: rater_id=%d, post_id=%d, score=%d (new avg=%.2f)",
            rater_id, post_id, score,
            rating_sum / rating_count,
        )

        return rating


async def has_already_rated(user_id: int, post_id: int) -> bool:
    """Return True if this user has already rated this post."""
    async with session_scope() as session:
        query = select(Rating).where(
            Rating.rater_id == user_id,
            Rating.post_id == post_id,
        )
        result = await session.execute(query)
        return result.scalar_one_or_none() is not None
