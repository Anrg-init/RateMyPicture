"""Increase text limits for caption, comment, name, and location."""

from alembic import op
import sqlalchemy as sa

revision = "0004_increase_text_limits"
down_revision = "0003_expand_user_languages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Increase limits on posts.caption, ratings.comment, users.name, and users.location."""
    # 1. posts caption: 150 -> 500
    op.drop_constraint("ck_posts_caption", "posts", type_="check")
    op.create_check_constraint(
        "ck_posts_caption",
        "posts",
        "char_length(caption) BETWEEN 1 AND 500 AND caption ~ '[^[:space:]]'",
    )

    # 2. ratings comment: 200 -> 500
    op.drop_constraint("ck_ratings_comment_length", "ratings", type_="check")
    op.create_check_constraint(
        "ck_ratings_comment_length",
        "ratings",
        "comment IS NULL OR char_length(comment) <= 500",
    )

    # 3. users name: 30 -> 50
    op.drop_constraint("ck_users_name_length", "users", type_="check")
    op.create_check_constraint(
        "ck_users_name_length",
        "users",
        "char_length(name) BETWEEN 2 AND 50",
    )

    # 4. users location: 60 -> 100
    op.drop_constraint("ck_users_location_length", "users", type_="check")
    op.create_check_constraint(
        "ck_users_location_length",
        "users",
        "location IS NULL OR char_length(location) BETWEEN 2 AND 100",
    )


def downgrade() -> None:
    """Revert limits on posts.caption, ratings.comment, users.name, and users.location."""
    op.drop_constraint("ck_users_location_length", "users", type_="check")
    op.create_check_constraint(
        "ck_users_location_length",
        "users",
        "location IS NULL OR char_length(location) BETWEEN 2 AND 60",
    )

    op.drop_constraint("ck_users_name_length", "users", type_="check")
    op.create_check_constraint(
        "ck_users_name_length",
        "users",
        "char_length(name) BETWEEN 2 AND 30",
    )

    op.drop_constraint("ck_ratings_comment_length", "ratings", type_="check")
    op.create_check_constraint(
        "ck_ratings_comment_length",
        "ratings",
        "comment IS NULL OR char_length(comment) <= 200",
    )

    op.drop_constraint("ck_posts_caption", "posts", type_="check")
    op.create_check_constraint(
        "ck_posts_caption",
        "posts",
        "char_length(caption) BETWEEN 1 AND 150 AND caption ~ '[^[:space:]]'",
    )
