"""add_performance_indexes

Revision ID: 281258c08af5
Revises: cdcc53c1ac56
Create Date: 2025-12-07 10:37:11.867536

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '281258c08af5'
down_revision: Union[str, None] = 'cdcc53c1ac56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add performance indexes for slow queries.

    Key optimizations:
    1. content_status composite index - speeds up inbox_exists correlated subquery
    2. contents visibility index - speeds up filtered content list queries
    """
    # Critical: composite index for inbox_exists subquery lookups
    # Query pattern: WHERE user_id=? AND status='inbox' AND content_id=?
    op.create_index(
        "idx_content_status_user_status_content",
        "content_status",
        ["user_id", "status", "content_id"],
        unique=False,
    )

    # Index for content visibility queries (summarized non-skipped content)
    # Query pattern: WHERE classification != 'skip' OR classification IS NULL
    op.create_index(
        "idx_contents_classification_status",
        "contents",
        ["classification", "status", "content_type"],
        unique=False,
    )


def downgrade() -> None:
    """Remove performance indexes."""
    op.drop_index("idx_content_status_user_status_content", table_name="content_status")
    op.drop_index("idx_contents_classification_status", table_name="contents")
