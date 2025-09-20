"""Add news content type support"""

from alembic import op
import sqlalchemy as sa


revision = "20250920_02_add_news_content_type"
down_revision = "20250910_01_add_content_unlikes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contents",
        sa.Column("is_aggregate", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "idx_content_aggregate",
        "contents",
        ["content_type", "is_aggregate"],
    )

    # Ensure existing rows receive False without keeping server default
    op.execute("UPDATE contents SET is_aggregate = FALSE WHERE is_aggregate IS NULL")
    op.alter_column("contents", "is_aggregate", server_default=None)


def downgrade() -> None:
    op.drop_index("idx_content_aggregate", table_name="contents")
    op.drop_column("contents", "is_aggregate")

