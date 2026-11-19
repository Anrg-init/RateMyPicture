"""Add country, target_gender, target_country to users.

Revision ID: 0011_add_matching_preferences
Revises: 0010_add_direct_messages
Create Date: 2026-11-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0011_add_matching_preferences"
down_revision = "0010_add_direct_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("country", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("target_gender", sa.Text(), nullable=True, server_default="any"))
    op.add_column("users", sa.Column("target_country", sa.Text(), nullable=True, server_default="all"))

    op.create_check_constraint(
        "ck_users_country",
        "users",
        "country IS NULL OR country IN ('in', 'ph', 'ru', 'us', 'es', 'br', 'id', 'other')",
    )
    op.create_check_constraint(
        "ck_users_target_gender",
        "users",
        "target_gender IS NULL OR target_gender IN ('female', 'male', 'any')",
    )
    op.create_check_constraint(
        "ck_users_target_country",
        "users",
        "target_country IS NULL OR target_country IN ('in', 'ph', 'ru', 'us', 'es', 'br', 'id', 'all')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_target_country", "users", type_="check")
    op.drop_constraint("ck_users_target_gender", "users", type_="check")
    op.drop_constraint("ck_users_country", "users", type_="check")
    op.drop_column("users", "target_country")
    op.drop_column("users", "target_gender")
    op.drop_column("users", "country")
