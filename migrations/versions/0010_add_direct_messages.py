"""Add direct_messages table.

Revision ID: 0010_add_direct_messages
Revises: 0009_add_gender_to_users
Create Date: 2026-11-18
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_add_direct_messages"
down_revision = "0009_add_gender_to_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "direct_messages",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("sender_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recipient_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("post_id", sa.BigInteger(), sa.ForeignKey("posts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("char_length(text) BETWEEN 1 AND 500", name="ck_direct_messages_text_len"),
    )
    op.create_index("ix_direct_messages_recipient_created", "direct_messages", ["recipient_id", "created_at"])
    op.create_index("ix_direct_messages_sender_created", "direct_messages", ["sender_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_direct_messages_sender_created", table_name="direct_messages")
    op.drop_index("ix_direct_messages_recipient_created", table_name="direct_messages")
    op.drop_table("direct_messages")

