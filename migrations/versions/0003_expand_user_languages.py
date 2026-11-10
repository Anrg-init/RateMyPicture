"""Update users language check constraint for es, pt, id."""

from alembic import op
import sqlalchemy as sa

revision = "0003_expand_user_languages"
down_revision = "0002_add_third_post_photo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Allow 'es', 'pt', 'id' in addition to 'en', 'ru' in users.language."""
    op.drop_constraint("ck_users_language", "users", type_="check")
    op.create_check_constraint(
        "ck_users_language",
        "users",
        "language IN ('en', 'ru', 'es', 'pt', 'id')",
    )


def downgrade() -> None:
    """Revert users.language check constraint to 'en', 'ru'."""
    op.drop_constraint("ck_users_language", "users", type_="check")
    op.create_check_constraint(
        "ck_users_language",
        "users",
        "language IN ('en', 'ru')",
    )
