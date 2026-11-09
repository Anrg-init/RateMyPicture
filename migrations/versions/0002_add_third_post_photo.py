"""Add the third optional photo to posts."""

from alembic import op
import sqlalchemy as sa

revision = "0002_add_third_post_photo"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add third-photo identifiers and their consistency checks."""
    op.add_column("posts", sa.Column("photo3_file_id", sa.Text(), nullable=True))
    op.add_column("posts", sa.Column("photo3_unique_id", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_posts_third_photo_pair",
        "posts",
        "(photo3_file_id IS NULL) = (photo3_unique_id IS NULL)",
    )
    op.create_check_constraint(
        "ck_posts_third_photo_unique",
        "posts",
        "photo3_unique_id IS NULL OR (photo3_unique_id != photo1_unique_id "
        "AND (photo2_unique_id IS NULL OR photo3_unique_id != photo2_unique_id))",
    )


def downgrade() -> None:
    """Remove the third-photo identifiers and checks."""
    op.drop_constraint("ck_posts_third_photo_unique", "posts", type_="check")
    op.drop_constraint("ck_posts_third_photo_pair", "posts", type_="check")
    op.drop_column("posts", "photo3_unique_id")
    op.drop_column("posts", "photo3_file_id")