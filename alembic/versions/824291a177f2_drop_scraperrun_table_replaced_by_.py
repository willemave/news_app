"""Drop ScraperRun table - replaced by EventLog

Revision ID: 824291a177f2
Revises: 65a196dd7bed
Create Date: 2025-06-19 21:07:03.365317

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '824291a177f2'
down_revision: Union[str, None] = '65a196dd7bed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop indexes first
    op.drop_index('idx_run_type_started', table_name='scraper_runs')
    op.drop_index('idx_run_started', table_name='scraper_runs')
    op.drop_index('idx_run_status', table_name='scraper_runs')
    op.drop_index('ix_scraper_runs_status', table_name='scraper_runs')
    
    # Drop the table
    op.drop_table('scraper_runs')


def downgrade() -> None:
    """Downgrade schema."""
    # Recreate the table
    op.create_table('scraper_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('total_scraped', sa.Integer(), nullable=True),
        sa.Column('total_saved', sa.Integer(), nullable=True),
        sa.Column('total_duplicates', sa.Integer(), nullable=True),
        sa.Column('total_errors', sa.Integer(), nullable=True),
        sa.Column('scraper_stats', sa.JSON(), nullable=True),
        sa.Column('processing_stats', sa.JSON(), nullable=True),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_details', sa.JSON(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Recreate indexes
    op.create_index('idx_run_status', 'scraper_runs', ['status'], unique=False)
    op.create_index('idx_run_started', 'scraper_runs', ['started_at'], unique=False)
    op.create_index('idx_run_type_started', 'scraper_runs', ['run_type', 'started_at'], unique=False)
    op.create_index('ix_scraper_runs_status', 'scraper_runs', ['status'], unique=False)
