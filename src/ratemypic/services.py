"""Database helper functions (CRUD operations).

This file contains simple functions to save and read data from PostgreSQL.
All functions use simple syntax with clear comments and production logging.
"""

from datetime import datetime, timedelta, timezone
import logging
from sqlalchemy import and_, case, delete, func, or_, select, update, text as sa_text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased
from sqlalchemy.sql.expression import not_

from ratemypic.database import session_scope
from ratemypic.models import DirectMessage, Post, PostReaction, PostView, Rating, User

logger = logging.getLogger(__name__)


async def save_user(
    telegram_id: int,
    name: str,
    age: int,
    location: str | None,
    language: str = "en",
    terms_accepted_at: datetime | None = None,
    status: str = "active",
    gender: str | None = None,
    country: str | None = None,
    target_gender: str | None = None,
    target_country: str | None = None,
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
                gender=gender,
                country=country,
                target_gender=target_gender or "any",
                target_country=target_country or "all",
                location=location,
                language=language,
                status=status,
                terms_accepted_at=terms_accepted_at,
            )
            session.add(user)
            logger.info("Created new user: telegram_id=%d, name='%s', status='%s'", telegram_id, name, status)
        else:
            user.name = name
            user.age = age
            if gender is not None:
                user.gender = gender
            if country is not None:
                user.country = country
            if target_gender is not None:
                user.target_gender = target_gender
            if target_country is not None:
                user.target_country = target_country
            user.location = location
            user.language = language
            user.status = status
            user.terms_accepted_at = terms_accepted_at
            logger.info("Updated user: telegram_id=%d, name='%s', status='%s'", telegram_id, name, status)

        return user


async def update_user_preferences(
    telegram_id: int,
    target_gender: str,
    target_country: str,
) -> User | None:
    """Update target gender and target country preferences for a user."""
    async with session_scope() as session:
        query = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(query)
        user = result.scalar_one_or_none()
        if user:
            user.target_gender = target_gender
            user.target_country = target_country
            logger.info(
                "Updated preferences for telegram_id=%d: gender=%s, country=%s",
                telegram_id,
                target_gender,
                target_country,
            )
        return user


async def get_user_by_telegram_id(telegram_id: int) -> User | None:
    """Find a user in the database by their Telegram ID."""
    logger.debug("Looking up user with telegram_id=%d", telegram_id)
    async with session_scope() as session:
        query = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()


async def get_user_by_id(user_id: int) -> User | None:
    """Find a user in the database by their internal primary key ID."""
    async with session_scope() as session:
        query = select(User).where(User.id == user_id)
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


async def update_user_language(telegram_id: int, language: str) -> bool:
    """Update the preferred language for one Telegram account."""
    async with session_scope() as session:
        query = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(query)
        user = result.scalar_one_or_none()
        if user is None:
            return False

        user.language = language
        logger.info("Updated language for user telegram_id=%d to '%s'", telegram_id, language)
        return True


async def toggle_user_notifications(telegram_id: int) -> bool | None:
    """Toggle notification preference for a user. Returns new state or None if user not found."""
    async with session_scope() as session:
        query = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(query)
        user = result.scalar_one_or_none()
        if user is None:
            return None
        user.notifications_enabled = not user.notifications_enabled
        logger.info(
            "Toggled notifications for telegram_id=%d to %s",
            telegram_id,
            user.notifications_enabled,
        )
        return user.notifications_enabled


async def get_post_owner_for_notification(post_id: int) -> User | None:
    """Fetch the post owner User model for delivering notifications."""
    async with session_scope() as session:
        query = (
            select(User)
            .join(Post, Post.user_id == User.id)
            .where(Post.id == post_id)
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()


async def get_inactive_users_for_retention(
    hours_inactive: int = 48,
    limit: int = 50,
) -> list[User]:
    """Find active users with notifications enabled who have not been notified recently."""
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(hours=hours_inactive)
    async with session_scope() as session:
        query = (
            select(User)
            .where(User.status == "active")
            .where(User.notifications_enabled.is_(True))
            .where(
                (User.last_notified_at.is_(None))
                | (User.last_notified_at < threshold)
            )
            .order_by(User.last_notified_at.asc().nullsfirst())
            .limit(limit)
        )
        result = await session.execute(query)
        return list(result.scalars().all())


async def mark_user_notified(user_id: int) -> None:
    """Update last_notified_at timestamp for a user."""
    now = datetime.now(timezone.utc)
    async with session_scope() as session:
        query = update(User).where(User.id == user_id).values(last_notified_at=now)
        await session.execute(query)


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
    """Archive a user account so their Telegram ID is freed for re-registration,
    while preserving all posts, ratings count, and emoji likes count in the community."""
    async with session_scope() as session:
        query = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(query)
        user = result.scalar_one_or_none()
        if user is None:
            return False

        # Free the real telegram_id with a unique negative offset
        archived_id = -abs(user.telegram_id)
        count_res = await session.execute(
            select(func.count(User.id)).where(User.telegram_id <= archived_id)
        )
        offset = count_res.scalar() or 0
        user.telegram_id = archived_id - offset - 1
        user.name = "Deleted User"
        return True


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
async def record_post_view(user_id: int, post_id: int) -> bool:
    """Record that a user has seen/viewed a post in their feed."""
    async with session_scope() as session:
        query = select(PostView).where(
            PostView.user_id == user_id,
            PostView.post_id == post_id,
        )
        result = await session.execute(query)
        if result.scalar_one_or_none() is not None:
            return False

        try:
            view = PostView(user_id=user_id, post_id=post_id)
            session.add(view)
            await session.flush()
            logger.debug("Recorded post_view: user_id=%d, post_id=%d", user_id, post_id)
            return True
        except IntegrityError:
            return False


async def get_next_post_to_rate(
    user_id: int,
    prefer_low_count: bool,
    target_gender: str = "any",
    target_country: str = "all",
) -> Post | None:
    """Pick the next post to show for rating using the alternating algorithm.

    Algorithm:
    - Even turn  (prefer_low_count=True):  find a random approved post with rating_count < 10
    - Odd turn   (prefer_low_count=False): find a random approved post with rating_count >= 10
    - Strictly exclude posts owned by this user (Post.user_id != user_id).
    - Strictly exclude posts already rated by this user (Rating.rater_id == user_id).
    - Strictly exclude posts already liked/reacted to by this user (PostReaction.user_id == user_id).
    - Strictly exclude posts already seen/viewed by this user (PostView.user_id == user_id).
    - Filters by target_gender ('female', 'male', 'any') and target_country ('in', 'ph', etc., 'all').
    - If preferred bucket is empty, fall back to the other bucket.
    - If both are empty, search all eligible posts without rating_count filter.

    Args:
        user_id: The database ID of the user requesting the feed.
        prefer_low_count: True = show low-rated post first, False = show popular post.
        target_gender: Filter for preferred gender ('female', 'male', 'any').
        target_country: Filter for preferred country ('all', 'in', etc.).

    Returns:
        A Post object or None if no eligible posts remain.
    """
    async with session_scope() as session:
        effective_gender = target_gender or "any"
        effective_country = target_country or "all"

        # Subqueries for exclusion: rated, reacted (liked), and seen (viewed)
        already_rated_subquery = (
            select(Rating.post_id).where(Rating.rater_id == user_id)
        )
        already_reacted_subquery = (
            select(PostReaction.post_id).where(PostReaction.user_id == user_id)
        )
        already_viewed_subquery = (
            select(PostView.post_id).where(PostView.user_id == user_id)
        )

        def base_query(low_count: bool | None):
            query = (
                select(Post)
                .where(Post.status == "approved")
                .where(Post.user_id != user_id)
                .where(not_(Post.id.in_(already_rated_subquery)))
                .where(not_(Post.id.in_(already_reacted_subquery)))
                .where(not_(Post.id.in_(already_viewed_subquery)))
            )
            if (effective_gender and effective_gender != "any") or (effective_country and effective_country != "all"):
                query = query.join(User, Post.user_id == User.id)
                if effective_gender and effective_gender != "any":
                    query = query.where(User.gender == effective_gender)
                if effective_country and effective_country != "all":
                    query = query.where(User.country == effective_country)

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


async def get_rating_distribution(post_id: int) -> dict[int, int]:
    """Return counts for each rating score (1-5) for a post."""
    async with session_scope() as session:
        query = (
            select(Rating.score, func.count(Rating.id))
            .where(Rating.post_id == post_id)
            .group_by(Rating.score)
        )
        result = await session.execute(query)
        distribution = {score: 0 for score in range(1, 6)}
        for score, count in result.all():
            distribution[score] = count
        return distribution


async def get_admin_dashboard_stats() -> dict:
    """Fetch user growth, audience, and demographic stats for admin dashboard."""
    from datetime import timezone
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    async with session_scope() as session:
        total_users = await session.scalar(select(func.count(User.id))) or 0
        active_users = (
            await session.scalar(
                select(func.count(User.id)).where(User.status == "active")
            )
            or 0
        )
        banned_users = (
            await session.scalar(
                select(func.count(User.id)).where(User.status == "banned")
            )
            or 0
        )
        joined_today = (
            await session.scalar(
                select(func.count(User.id)).where(User.created_at >= today_start)
            )
            or 0
        )

        langs_result = await session.execute(
            select(User.language, func.count(User.id))
            .group_by(User.language)
            .order_by(func.count(User.id).desc())
        )
        languages = langs_result.all()

        locs_result = await session.execute(
            select(User.location, func.count(User.id))
            .where(User.location.is_not(None), User.location != "")
            .group_by(User.location)
            .order_by(func.count(User.id).desc())
            .limit(5)
        )
        top_locations = locs_result.all()

        unspecified_locs = (
            await session.scalar(
                select(func.count(User.id)).where(
                    (User.location.is_(None)) | (User.location == "")
                )
            )
            or 0
        )

        age_result = await session.execute(
            select(func.avg(User.age), func.min(User.age), func.max(User.age))
        )
        avg_age, min_age, max_age = age_result.one()

        # Recent 5 registered users
        recent_users_res = await session.execute(
            select(User).order_by(User.id.desc()).limit(5)
        )
        recent_users = [
            {
                "id": u.id,
                "telegram_id": u.telegram_id,
                "name": u.name,
                "age": u.age,
                "location": u.location,
                "language": u.language,
                "created_at": u.created_at,
            }
            for u in recent_users_res.scalars().all()
        ]

        # Posts activity & recent 5 posts
        total_posts = await session.scalar(select(func.count(Post.id))) or 0
        posts_today = (
            await session.scalar(
                select(func.count(Post.id)).where(Post.created_at >= today_start)
            )
            or 0
        )
        approved_posts = (
            await session.scalar(
                select(func.count(Post.id)).where(Post.status == "approved")
            )
            or 0
        )

        recent_posts_res = await session.execute(
            select(Post, User.name)
            .join(User, Post.user_id == User.id)
            .order_by(Post.id.desc())
            .limit(5)
        )
        recent_posts = [
            {
                "id": p.id,
                "user_id": p.user_id,
                "owner_name": owner_name,
                "caption": p.caption,
                "rating_count": p.rating_count,
                "rating_sum": p.rating_sum,
                "status": p.status,
                "created_at": p.created_at,
            }
            for p, owner_name in recent_posts_res.all()
        ]

        return {
            "total_users": total_users,
            "active_users": active_users,
            "banned_users": banned_users,
            "joined_today": joined_today,
            "languages": languages,
            "top_locations": top_locations,
            "unspecified_locations": unspecified_locs,
            "avg_age": float(avg_age) if avg_age is not None else 0.0,
            "min_age": min_age or 0,
            "max_age": max_age or 0,
            "recent_users": recent_users,
            "total_posts": total_posts,
            "posts_today": posts_today,
            "approved_posts": approved_posts,
            "recent_posts": recent_posts,
        }


async def get_post_by_id(post_id: int) -> Post | None:
    """Fetch a single post by its ID."""
    async with session_scope() as session:
        query = select(Post).where(Post.id == post_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()


SOCIAL_REACTIONS = ("😭", "🤣", "☠️", "😍", "💩", "🍑", "🍌", "🔥")


async def toggle_post_reaction(post_id: int, user_id: int, reaction: str) -> bool:
    """Add or toggle an emoji reaction for a user on a post. Returns True if added, False if removed."""
    if reaction not in SOCIAL_REACTIONS:
        return False
    try:
        async with session_scope() as session:
            query = select(PostReaction).where(
                PostReaction.post_id == post_id,
                PostReaction.user_id == user_id,
                PostReaction.reaction == reaction,
            )
            result = await session.execute(query)
            existing = result.scalar_one_or_none()
            if existing:
                await session.delete(existing)
                logger.info("Removed reaction '%s' on post_id=%d by user_id=%d", reaction, post_id, user_id)
                return False
            else:
                new_reaction = PostReaction(post_id=post_id, user_id=user_id, reaction=reaction)
                session.add(new_reaction)
                logger.info("Added reaction '%s' on post_id=%d by user_id=%d", reaction, post_id, user_id)
                return True
    except IntegrityError:
        logger.warning(
            "Race condition on reaction toggle: post_id=%d, user_id=%d, reaction=%s",
            post_id, user_id, reaction,
        )
        return True


async def get_post_reactions(post_id: int) -> dict[str, int]:
    """Return counts for each of the 8 allowed social emoji reactions."""
    async with session_scope() as session:
        query = (
            select(PostReaction.reaction, func.count(PostReaction.id))
            .where(PostReaction.post_id == post_id)
            .group_by(PostReaction.reaction)
        )
        result = await session.execute(query)
        counts = {r: 0 for r in SOCIAL_REACTIONS}
        for emoji_char, count in result.all():
            if emoji_char in counts:
                counts[emoji_char] = count
        return counts


# ===========================================================================
# Direct Messages (Private Notes)
# ===========================================================================
async def create_direct_message(
    sender_id: int,
    recipient_id: int,
    text: str,
    post_id: int | None = None,
) -> DirectMessage:
    """Save a private direct message from sender to recipient."""
    async with session_scope() as session:
        dm = DirectMessage(
            sender_id=sender_id,
            recipient_id=recipient_id,
            post_id=post_id,
            text=text.strip(),
        )
        session.add(dm)
        await session.flush()
        logger.info("Sent DM from user_id=%d to user_id=%d (dm_id=%d)", sender_id, recipient_id, dm.id)
        return dm


async def get_direct_message(dm_id: int) -> DirectMessage | None:
    """Fetch a direct message by ID."""
    async with session_scope() as session:
        query = select(DirectMessage).where(DirectMessage.id == dm_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()


async def get_user_inbox_dms(
    user_id: int, limit: int = 5, offset: int = 0
) -> list[tuple[DirectMessage, User]]:
    """Fetch DMs received by a user with the sender's profile info."""
    async with session_scope() as session:
        query = (
            select(DirectMessage, User)
            .join(User, DirectMessage.sender_id == User.id)
            .where(DirectMessage.recipient_id == user_id)
            .order_by(DirectMessage.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(query)
        return list(result.all())


async def count_user_inbox_dms(user_id: int) -> int:
    """Count how many total DMs a user has received."""
    async with session_scope() as session:
        query = select(func.count(DirectMessage.id)).where(DirectMessage.recipient_id == user_id)
        result = await session.execute(query)
        return result.scalar_one() or 0


async def get_user_inbox_conversations(
    user_id: int, limit: int = 5, offset: int = 0
) -> list[dict]:
    """Fetch conversation summaries for a user's inbox, grouped by sender.

    Each item in the returned list is a dict:
    {
        "sender": User,
        "latest_dm": DirectMessage,
        "total_count": int,
        "unread_count": int,
    }
    """
    async with session_scope() as session:
        conv_stats = (
            select(
                DirectMessage.sender_id.label("sender_id"),
                func.count(DirectMessage.id).label("total_count"),
                func.count(case((DirectMessage.read_at.is_(None), 1))).label("unread_count"),
                func.max(DirectMessage.id).label("latest_dm_id"),
                func.max(DirectMessage.created_at).label("latest_at"),
            )
            .where(DirectMessage.recipient_id == user_id)
            .group_by(DirectMessage.sender_id)
            .order_by(func.max(DirectMessage.created_at).desc())
            .limit(limit)
            .offset(offset)
            .subquery()
        )

        query = (
            select(User, DirectMessage, conv_stats.c.total_count, conv_stats.c.unread_count)
            .join(conv_stats, User.id == conv_stats.c.sender_id)
            .join(DirectMessage, DirectMessage.id == conv_stats.c.latest_dm_id)
            .order_by(conv_stats.c.latest_at.desc())
        )
        result = await session.execute(query)
        conversations = []
        for sender, latest_dm, total_count, unread_count in result.all():
            conversations.append({
                "sender": sender,
                "latest_dm": latest_dm,
                "total_count": int(total_count),
                "unread_count": int(unread_count),
            })
        return conversations


async def count_user_inbox_conversations(user_id: int) -> int:
    """Count total number of distinct conversation senders in user's inbox."""
    async with session_scope() as session:
        query = select(func.count(func.distinct(DirectMessage.sender_id))).where(DirectMessage.recipient_id == user_id)
        result = await session.execute(query)
        return result.scalar_one() or 0


async def get_conversation_messages(
    user_id: int, other_user_id: int, limit: int = 15
) -> list[tuple[DirectMessage, User]]:
    """Fetch recent messages exchanged between user_id and other_user_id."""
    async with session_scope() as session:
        query = (
            select(DirectMessage, User)
            .join(User, DirectMessage.sender_id == User.id)
            .where(
                or_(
                    and_(DirectMessage.sender_id == other_user_id, DirectMessage.recipient_id == user_id),
                    and_(DirectMessage.sender_id == user_id, DirectMessage.recipient_id == other_user_id),
                )
            )
            .order_by(DirectMessage.created_at.asc())
            .limit(limit)
        )
        result = await session.execute(query)
        return list(result.all())


async def mark_conversation_as_read(user_id: int, sender_id: int) -> None:
    """Mark all unread DMs from sender_id to user_id as read."""
    async with session_scope() as session:
        query = (
            update(DirectMessage)
            .where(
                DirectMessage.recipient_id == user_id,
                DirectMessage.sender_id == sender_id,
                DirectMessage.read_at.is_(None),
            )
            .values(read_at=datetime.now(timezone.utc))
        )
        await session.execute(query)


async def has_user_approved_post(user_id: int) -> bool:
    """Return True if user has at least one approved post published in the feed."""
    async with session_scope() as session:
        query = select(func.count(Post.id)).where(Post.user_id == user_id, Post.status == "approved")
        result = await session.execute(query)
        return (result.scalar() or 0) > 0


async def get_admin_recent_comments(limit: int = 10) -> list[dict]:
    """Fetch latest user comments across all posts for admin moderation/monitoring."""
    async with session_scope() as session:
        query = (
            select(
                Rating.id,
                Rating.post_id,
                Rating.score,
                Rating.comment,
                Rating.created_at,
                User.name.label("rater_name"),
                User.id.label("rater_id"),
            )
            .join(User, Rating.rater_id == User.id)
            .where(Rating.comment.is_not(None), func.length(func.trim(Rating.comment)) > 0)
            .order_by(Rating.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(query)
        rows = result.all()
        return [
            {
                "id": r.id,
                "post_id": r.post_id,
                "score": r.score,
                "comment": r.comment,
                "created_at": r.created_at,
                "rater_name": r.rater_name,
                "rater_id": r.rater_id,
            }
            for r in rows
        ]


async def get_admin_recent_dms(limit: int = 10) -> list[dict]:
    """Fetch latest direct messages between users for admin oversight."""
    sender_user = aliased(User)
    recipient_user = aliased(User)
    async with session_scope() as session:
        query = (
            select(
                DirectMessage.id,
                DirectMessage.post_id,
                DirectMessage.text,
                DirectMessage.created_at,
                sender_user.name.label("sender_name"),
                sender_user.id.label("sender_id"),
                recipient_user.name.label("recipient_name"),
                recipient_user.id.label("recipient_id"),
            )
            .join(sender_user, DirectMessage.sender_id == sender_user.id)
            .join(recipient_user, DirectMessage.recipient_id == recipient_user.id)
            .order_by(DirectMessage.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(query)
        rows = result.all()
        return [
            {
                "id": r.id,
                "post_id": r.post_id,
                "text": r.text,
                "created_at": r.created_at,
                "sender_name": r.sender_name,
                "sender_id": r.sender_id,
                "recipient_name": r.recipient_name,
                "recipient_id": r.recipient_id,
            }
            for r in rows
        ]



