"""Add notifications_enabled and last_notified_at to users table.

Revision ID: 0008_add_notifications
Revises: 0007_add_post_views
Create Date: 2026-11-12
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_add_notifications"
down_revision = "0007_add_post_views"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "notifications_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "last_notified_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "last_notified_at")
    op.drop_column("users", "notifications_enabled")
