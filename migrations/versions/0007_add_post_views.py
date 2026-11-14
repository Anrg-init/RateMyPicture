"""Create post_views table to track seen posts.

Revision ID: 0007_add_post_views
Revises: 0006_performance_indexes
Create Date: 2026-11-10
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_add_post_views"
down_revision = "0006_performance_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "post_views",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("post_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("post_id", "user_id", name="uq_post_views_post_user"),
    )
    op.create_index(
        "ix_post_views_user_post",
        "post_views",
        ["user_id", "post_id"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_post_reactions_user_post",
        "post_reactions",
        ["user_id", "post_id"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_post_reactions_user_post", table_name="post_reactions", if_exists=True)
    op.drop_index("ix_post_views_user_post", table_name="post_views", if_exists=True)
    op.drop_table("post_views")
