"""add_chat_tables

Revision ID: 1620a8545d8c
Revises: 20250630_02
Create Date: 2025-11-28 12:55:58.174961

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1620a8545d8c'
down_revision: Union[str, None] = '20250630_02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create chat_sessions table
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("content_id", sa.Integer(), nullable=True, index=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("session_type", sa.String(50), nullable=True),
        sa.Column("topic", sa.String(500), nullable=True),
        sa.Column("llm_model", sa.String(100), nullable=False, server_default="openai:gpt-5.1"),
        sa.Column("llm_provider", sa.String(50), nullable=False, server_default="openai"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True, onupdate=sa.func.now()),
        sa.Column("last_message_at", sa.DateTime(), nullable=True, index=True),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index(
        "idx_chat_sessions_user_time",
        "chat_sessions",
        ["user_id", "last_message_at"],
    )
    op.create_index(
        "idx_chat_sessions_content",
        "chat_sessions",
        ["user_id", "content_id"],
    )

    # Create chat_messages table
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), nullable=False, index=True),
        sa.Column("message_list", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_chat_messages_session_created",
        "chat_messages",
        ["session_id", "created_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_chat_messages_session_created", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("idx_chat_sessions_content", table_name="chat_sessions")
    op.drop_index("idx_chat_sessions_user_time", table_name="chat_sessions")
    op.drop_table("chat_sessions")
