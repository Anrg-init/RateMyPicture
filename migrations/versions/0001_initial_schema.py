"""Create the initial RateMyPic schema."""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all application tables, indexes, and database rules."""
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("language", sa.Text(), server_default="en", nullable=False),
        sa.Column(
            "status", sa.Text(), server_default="onboarding", nullable=False
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("age", sa.SmallInteger(), nullable=False),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("strikes", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("language IN ('en', 'ru')", name="ck_users_language"),
        sa.CheckConstraint(
            "status IN ('onboarding', 'active', 'banned')", name="ck_users_status"
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 2 AND 30", name="ck_users_name_length"
        ),
        sa.CheckConstraint("age BETWEEN 18 AND 99", name="ck_users_age"),
        sa.CheckConstraint(
            "location IS NULL OR char_length(location) BETWEEN 2 AND 60",
            name="ck_users_location_length",
        ),
        sa.CheckConstraint("strikes >= 0", name="ck_users_strikes"),
        sa.CheckConstraint(
            "status != 'active' OR terms_accepted_at IS NOT NULL",
            name="ck_users_active_terms",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_id"),
    )

    op.create_table(
        "posts",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("photo1_file_id", sa.Text(), nullable=False),
        sa.Column("photo1_unique_id", sa.Text(), nullable=False),
        sa.Column("photo2_file_id", sa.Text(), nullable=True),
        sa.Column("photo2_unique_id", sa.Text(), nullable=True),
        sa.Column("caption", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="approved", nullable=False),
        sa.Column("rating_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rating_sum", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('approved', 'nsfw', 'pending', 'rejected')",
            name="ck_posts_status",
        ),
        sa.CheckConstraint(
            "char_length(caption) BETWEEN 1 AND 150 AND caption ~ '[^[:space:]]'",
            name="ck_posts_caption",
        ),
        sa.CheckConstraint("rating_count >= 0", name="ck_posts_rating_count"),
        sa.CheckConstraint(
            "rating_sum >= rating_count AND rating_sum <= 5 * rating_count",
            name="ck_posts_rating_sum",
        ),
        sa.CheckConstraint(
            "(photo2_file_id IS NULL) = (photo2_unique_id IS NULL)",
            name="ck_posts_second_photo_pair",
        ),
        sa.CheckConstraint(
            "photo2_unique_id IS NULL OR photo2_unique_id != photo1_unique_id",
            name="ck_posts_unique_photos",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "ratings",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("post_id", sa.BigInteger(), nullable=False),
        sa.Column("rater_id", sa.BigInteger(), nullable=False),
        sa.Column("score", sa.SmallInteger(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("score BETWEEN 1 AND 5", name="ck_ratings_score"),
        sa.CheckConstraint(
            "comment IS NULL OR char_length(comment) <= 200",
            name="ck_ratings_comment_length",
        ),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rater_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("post_id", "rater_id", name="uq_ratings_post_rater"),
    )

    op.create_table(
        "reports",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("post_id", sa.BigInteger(), nullable=False),
        sa.Column("reporter_id", sa.BigInteger(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "reason IN ('nudity', 'minor', 'fake', 'harassment', 'other')",
            name="ck_reports_reason",
        ),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("post_id", "reporter_id", name="uq_reports_post_reporter"),
    )

    op.create_index(
        "ix_posts_approved_rating_count",
        "posts",
        ["rating_count"],
        postgresql_where=sa.text("status = 'approved'"),
    )
    op.execute(
        "CREATE INDEX ix_posts_user_created_at "
        "ON posts (user_id, created_at DESC)"
    )
    op.create_index("ix_ratings_rater_id", "ratings", ["rater_id"])
    op.create_index("ix_reports_reporter_id", "reports", ["reporter_id"])

    op.execute(
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
    )
    op.execute(
        """
        CREATE TRIGGER prevent_unbanning_user_trigger
        BEFORE UPDATE OF status ON users
        FOR EACH ROW
        EXECUTE FUNCTION prevent_unbanning_user()
        """
    )


def downgrade() -> None:
    """Remove the tables and indexes created by this revision."""
    op.drop_index("ix_reports_reporter_id", table_name="reports")
    op.drop_index("ix_ratings_rater_id", table_name="ratings")
    op.drop_index("ix_posts_approved_rating_count", table_name="posts")
    op.execute("DROP INDEX ix_posts_user_created_at")
    op.drop_table("reports")
    op.drop_table("ratings")
    op.drop_table("posts")
    op.drop_table("users")
    op.execute("DROP FUNCTION IF EXISTS prevent_unbanning_user()")