"""Create post_reactions table for social emoji reactions."""

from alembic import op
import sqlalchemy as sa

revision = "0005_add_post_reactions"
down_revision = "0004_increase_text_limits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create post_reactions table with 8 allowed social emojis."""
    op.create_table(
        "post_reactions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("post_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("reaction", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("post_id", "user_id", "reaction", name="uq_post_reactions_post_user_emoji"),
        sa.CheckConstraint(
            "reaction IN ('😭', '🤣', '☠️', '😍', '💩', '🍑', '🍌', '🔥')",
            name="ck_post_reactions_emoji",
        ),
    )
    op.create_index(
        "ix_post_reactions_post_id",
        "post_reactions",
        ["post_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop post_reactions table."""
    op.drop_index("ix_post_reactions_post_id", table_name="post_reactions")
    op.drop_table("post_reactions")
