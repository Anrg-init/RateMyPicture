"""Add high-performance indexes for production rating and reaction queries.

Revision ID: 0006_performance_indexes
Revises: 0005_add_post_reactions
Create Date: 2026-11-10
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_performance_indexes"
down_revision = "0005_add_post_reactions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Covering index for get_next_post_to_rate: SELECT post_id FROM ratings WHERE rater_id = $1
    op.create_index(
        "ix_ratings_rater_post",
        "ratings",
        ["rater_id", "post_id"],
        unique=False,
        if_not_exists=True,
    )

    # 2. Partial index for comment pagination: WHERE comment IS NOT NULL ORDER BY created_at DESC
    op.create_index(
        "ix_ratings_post_comments",
        "ratings",
        ["post_id", sa.text("created_at DESC")],
        unique=False,
        postgresql_where=sa.text("comment IS NOT NULL"),
        if_not_exists=True,
    )

    # 3. Covering index for get_post_reactions: GROUP BY reaction WHERE post_id = $1
    op.create_index(
        "ix_post_reactions_post_emoji",
        "post_reactions",
        ["post_id", "reaction"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_post_reactions_post_emoji", table_name="post_reactions", if_exists=True)
    op.drop_index("ix_ratings_post_comments", table_name="ratings", if_exists=True)
    op.drop_index("ix_ratings_rater_post", table_name="ratings", if_exists=True)
