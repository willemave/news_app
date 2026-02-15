"""Helpers for auto-starting dig-deeper chats."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.domain.converters import content_to_domain
from app.models.schema import ChatSession, Content, ProcessingTask
from app.services.chat_agent import create_processing_message, process_message_async
from app.services.llm_models import DEFAULT_MODEL, DEFAULT_PROVIDER
from app.services.queue import TaskQueue, TaskStatus, TaskType

logger = get_logger(__name__)

DIG_DEEPER_PROMPT_TEMPLATE = (
    "Dig deeper into the key points of {title}. For each main point, explain reasoning, "
    "supporting evidence, and practical implications. Keep answers concise and numbered."
)


def resolve_display_title(content: Content) -> str:
    """Resolve a display-friendly title for dig-deeper prompts.

    Args:
        content: Content record.

    Returns:
        Display title string.
    """
    try:
        return content_to_domain(content).display_title
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to resolve display title for content %s: %s",
            content.id,
            exc,
            extra={
                "component": "dig_deeper",
                "operation": "resolve_display_title",
                "item_id": content.id,
            },
        )
        return content.title or "this content"


def build_dig_deeper_prompt(content: Content) -> str:
    """Build the default dig-deeper prompt for content.

    Args:
        content: Content record to reference in the prompt.

    Returns:
        Prompt string for the chat agent.
    """
    title = resolve_display_title(content)
    return DIG_DEEPER_PROMPT_TEMPLATE.format(title=title)


def get_or_create_dig_deeper_session(
    db: Session,
    content: Content,
    user_id: int,
) -> ChatSession:
    """Get or create a chat session for dig-deeper workflows.

    Args:
        db: Database session.
        content: Content record.
        user_id: User requesting the dig-deeper chat.

    Returns:
        ChatSession for the content/user.
    """
    existing = (
        db.query(ChatSession)
        .filter(
            ChatSession.content_id == content.id,
            ChatSession.user_id == user_id,
            ChatSession.is_archived == False,  # noqa: E712
        )
        .first()
    )
    if existing:
        return existing

    title = resolve_display_title(content)
    session = ChatSession(
        user_id=user_id,
        content_id=content.id,
        title=title,
        session_type="article_brain",
        llm_provider=DEFAULT_PROVIDER,
        llm_model=DEFAULT_MODEL,
        created_at=datetime.now(UTC),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def create_dig_deeper_message(
    db: Session,
    content: Content,
    user_id: int,
) -> tuple[int, int, str]:
    """Create a processing message for a dig-deeper chat.

    Args:
        db: Database session.
        content: Content record.
        user_id: User requesting the dig-deeper chat.

    Returns:
        Tuple of (session_id, message_id, prompt).
    """
    session = get_or_create_dig_deeper_session(db, content, user_id)
    prompt = build_dig_deeper_prompt(content)
    message = create_processing_message(db, session.id, prompt)
    return session.id, message.id, prompt


def run_dig_deeper_message(session_id: int, message_id: int, prompt: str) -> None:
    """Run the dig-deeper message processing synchronously.

    Args:
        session_id: Chat session ID.
        message_id: Chat message ID created for processing.
        prompt: Prompt string to send.
    """
    asyncio.run(process_message_async(session_id, message_id, prompt))


def enqueue_dig_deeper_task(db: Session, content_id: int, user_id: int) -> int:
    """Enqueue a dig-deeper task for later processing.

    Args:
        db: Database session.
        content_id: Content ID to chat about.
        user_id: User requesting dig-deeper.

    Returns:
        Processing task ID.
    """
    payload: dict[str, Any] = {"user_id": user_id}
    task = ProcessingTask(
        task_type=TaskType.DIG_DEEPER.value,
        content_id=content_id,
        payload=payload,
        status=TaskStatus.PENDING.value,
        queue_name=TaskQueue.CHAT.value,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task.id
