"""Database tables for users, posts, ratings, and reports."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DDL,
    DateTime,
    event,
    ForeignKey,
    Identity,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class that SQLAlchemy uses to find our tables."""


class User(Base):
    """A person who uses the bot."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False, server_default="en")
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="onboarding"
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    age: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    terms_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    strikes: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    notifications_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    last_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )

    __table_args__ = (
        CheckConstraint("language IN ('en', 'ru', 'es', 'pt', 'id')", name="ck_users_language"),
        CheckConstraint(
            "status IN ('onboarding', 'active', 'banned')", name="ck_users_status"
        ),
        CheckConstraint(
            "char_length(name) BETWEEN 2 AND 50", name="ck_users_name_length"
        ),
        CheckConstraint("age BETWEEN 18 AND 99", name="ck_users_age"),
        CheckConstraint(
            "location IS NULL OR char_length(location) BETWEEN 2 AND 100",
            name="ck_users_location_length",
        ),
        CheckConstraint("strikes >= 0", name="ck_users_strikes"),
        CheckConstraint(
            "status != 'active' OR terms_accepted_at IS NOT NULL",
            name="ck_users_active_terms",
        ),
    )


# CHECK constraints validate one row's values. This trigger also checks changes
# over time, so a banned user cannot later be changed back to another status.
event.listen(
    User.__table__,
    "after_create",
    DDL(
        """
        CREATE OR REPLACE FUNCTION prevent_unbanning_user()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.status = 'banned' AND NEW.status != 'banned' THEN
                RAISE EXCEPTION 'A banned user cannot be reactivated';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    ).execute_if(dialect="postgresql"),
)
event.listen(
    User.__table__,
    "after_create",
    DDL(
        """
        CREATE TRIGGER prevent_unbanning_user_trigger
        BEFORE UPDATE OF status ON users
        FOR EACH ROW
        EXECUTE FUNCTION prevent_unbanning_user()
        """
    ).execute_if(dialect="postgresql"),
)
event.listen(
    User.__table__,
    "after_drop",
    DDL("DROP FUNCTION IF EXISTS prevent_unbanning_user()")
    .execute_if(dialect="postgresql"),
)


class Post(Base):
    """A user's photo post and its running rating total."""

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    photo1_file_id: Mapped[str] = mapped_column(Text, nullable=False)
    photo1_unique_id: Mapped[str] = mapped_column(Text, nullable=False)
    photo2_file_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo2_unique_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo3_file_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo3_unique_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    caption: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="approved")
    rating_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    rating_sum: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('approved', 'nsfw', 'pending', 'rejected')",
            name="ck_posts_status",
        ),
        CheckConstraint(
            "char_length(caption) BETWEEN 1 AND 500 AND caption ~ '[^[:space:]]'",
            name="ck_posts_caption",
        ),
        CheckConstraint("rating_count >= 0", name="ck_posts_rating_count"),
        CheckConstraint(
            "rating_sum >= rating_count AND rating_sum <= 5 * rating_count",
            name="ck_posts_rating_sum",
        ),
        CheckConstraint(
            "(photo2_file_id IS NULL) = (photo2_unique_id IS NULL)",
            name="ck_posts_second_photo_pair",
        ),
        CheckConstraint(
            "(photo3_file_id IS NULL) = (photo3_unique_id IS NULL)",
            name="ck_posts_third_photo_pair",
        ),
        CheckConstraint(
            "photo2_unique_id IS NULL OR photo2_unique_id != photo1_unique_id",
            name="ck_posts_unique_photos",
        ),
        CheckConstraint(
            "photo3_unique_id IS NULL OR (photo3_unique_id != photo1_unique_id "
            "AND (photo2_unique_id IS NULL OR photo3_unique_id != photo2_unique_id))",
            name="ck_posts_third_photo_unique",
        ),
        Index(
            "ix_posts_approved_rating_count",
            "rating_count",
            postgresql_where=text("status = 'approved'"),
        ),
        Index("ix_posts_user_created_at", "user_id", created_at.desc()),
    )


class Rating(Base):
    """One user's score and optional comment on a post."""

    __tablename__ = "ratings"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    post_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    rater_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint("score BETWEEN 1 AND 5", name="ck_ratings_score"),
        CheckConstraint(
            "comment IS NULL OR char_length(comment) <= 500",
            name="ck_ratings_comment_length",
        ),
        UniqueConstraint("post_id", "rater_id", name="uq_ratings_post_rater"),
        Index("ix_ratings_rater_id", "rater_id"),
        Index("ix_ratings_rater_post", "rater_id", "post_id"),
        Index(
            "ix_ratings_post_comments",
            "post_id",
            created_at.desc(),
            postgresql_where=text("comment IS NOT NULL"),
        ),
    )


class Report(Base):
    """A report that a user has made about a post."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    post_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    reporter_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "reason IN ('nudity', 'minor', 'fake', 'harassment', 'other')",
            name="ck_reports_reason",
        ),
        UniqueConstraint("post_id", "reporter_id", name="uq_reports_post_reporter"),
        Index("ix_reports_reporter_id", "reporter_id"),
    )


class PostReaction(Base):
    """User emoji reactions on a post (optional social engagement)."""

    __tablename__ = "post_reactions"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    post_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    reaction: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "reaction IN ('😭', '🤣', '☠️', '😍', '💩', '🍑', '🍌', '🔥')",
            name="ck_post_reactions_emoji",
        ),
        UniqueConstraint("post_id", "user_id", "reaction", name="uq_post_reactions_post_user_emoji"),
        Index("ix_post_reactions_post_id", "post_id"),
        Index("ix_post_reactions_post_emoji", "post_id", "reaction"),
        Index("ix_post_reactions_user_post", "user_id", "post_id"),
    )


class PostView(Base):
    """Tracks when a user has seen/viewed a post in their feed."""

    __tablename__ = "post_views"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    post_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("post_id", "user_id", name="uq_post_views_post_user"),
        Index("ix_post_views_user_post", "user_id", "post_id"),
    )
