"""Add gender column to users table.

Revision ID: 0009_add_gender_to_users
Revises: 0008_add_notifications
Create Date: 2026-11-18
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_add_gender_to_users"
down_revision = "0008_add_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "gender",
            sa.Text(),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_users_gender",
        "users",
        "gender IS NULL OR gender IN ('male', 'female')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_gender", "users", type_="check")
    op.drop_column("users", "gender")
