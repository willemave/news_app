"""Persistence and context helpers for live voice sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.schema import (
    ChatMessage,
    ChatSession,
    Content,
    ContentFavorites,
    ContentStatusEntry,
    MessageProcessingStatus,
)
from app.models.user import User

logger = get_logger(__name__)

MAX_CONTEXT_SUMMARY_CHARS = 900
MAX_CONTEXT_TRANSCRIPT_CHARS = 1_200


@dataclass
class VoiceContentContext:
    """Compact content context used for contextual live voice turns."""

    content_id: int
    title: str
    url: str
    source: str | None
    summary: str | None
    transcript_excerpt: str | None


def _truncate(text: str | None, limit: int) -> str | None:
    """Trim text to a maximum length while preserving readability."""

    if text is None:
        return None
    cleaned = text.strip()
    if not cleaned:
        return None
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[:limit].rstrip()}..."


def _extract_summary(content: Content) -> str | None:
    """Extract short summary from content metadata."""

    short_summary = _truncate(content.short_summary, MAX_CONTEXT_SUMMARY_CHARS)
    if short_summary:
        return short_summary

    metadata = content.content_metadata or {}
    if not isinstance(metadata, dict):
        return None

    summary_value = metadata.get("summary")
    if isinstance(summary_value, str):
        return _truncate(summary_value, MAX_CONTEXT_SUMMARY_CHARS)
    if isinstance(summary_value, dict):
        for key in ("overview", "hook", "takeaway", "summary", "text"):
            candidate = summary_value.get(key)
            if isinstance(candidate, str):
                return _truncate(candidate, MAX_CONTEXT_SUMMARY_CHARS)
    return None


def _extract_transcript_excerpt(content: Content) -> str | None:
    """Extract transcript excerpt for podcast or long-form content."""

    metadata = content.content_metadata or {}
    if not isinstance(metadata, dict):
        return None

    transcript_candidates = [
        metadata.get("transcript"),
        metadata.get("full_text"),
    ]
    podcast_metadata = metadata.get("podcast_metadata")
    if isinstance(podcast_metadata, dict):
        transcript_candidates.append(podcast_metadata.get("transcript"))

    for candidate in transcript_candidates:
        if isinstance(candidate, str) and candidate.strip():
            return _truncate(candidate, MAX_CONTEXT_TRANSCRIPT_CHARS)
    return None


def _user_can_access_content(db: Session, user_id: int, content_id: int) -> bool:
    """Return whether the user can access a content item."""

    has_status = (
        db.query(ContentStatusEntry.id)
        .filter(ContentStatusEntry.user_id == user_id, ContentStatusEntry.content_id == content_id)
        .first()
        is not None
    )
    if has_status:
        return True

    has_favorite = (
        db.query(ContentFavorites.id)
        .filter(ContentFavorites.user_id == user_id, ContentFavorites.content_id == content_id)
        .first()
        is not None
    )
    return has_favorite


def load_voice_content_context(
    db: Session,
    *,
    user_id: int,
    content_id: int | None,
) -> VoiceContentContext | None:
    """Load safe, compact content context for voice grounding."""

    if content_id is None:
        return None

    content = db.query(Content).filter(Content.id == content_id).first()
    if content is None:
        return None
    if not _user_can_access_content(db, user_id, content_id):
        return None

    title = (content.title or "").strip() or f"Content {content.id}"
    return VoiceContentContext(
        content_id=content.id,
        title=title,
        url=content.url,
        source=content.source,
        summary=_extract_summary(content),
        transcript_excerpt=_extract_transcript_excerpt(content),
    )


def format_voice_content_context(context: VoiceContentContext | None) -> str | None:
    """Serialize content context for prompt injection."""

    if context is None:
        return None

    lines = [
        f"title: {context.title}",
        f"url: {context.url}",
    ]
    if context.source:
        lines.append(f"source: {context.source}")
    if context.summary:
        lines.append(f"summary: {context.summary}")
    if context.transcript_excerpt:
        lines.append(f"transcript_excerpt: {context.transcript_excerpt}")
    return "\n".join(lines)


def resolve_or_create_voice_chat_session(
    db: Session,
    *,
    user_id: int,
    existing_chat_session_id: int | None,
    context: VoiceContentContext | None,
    launch_mode: str,
    model_spec: str,
) -> ChatSession:
    """Resolve existing voice chat session or create one."""

    if existing_chat_session_id is not None:
        existing = (
            db.query(ChatSession)
            .filter(
                ChatSession.id == existing_chat_session_id,
                ChatSession.user_id == user_id,
                ChatSession.is_archived.is_(False),
            )
            .first()
        )
        if existing is not None:
            return existing

    provider = (model_spec.split(":", 1)[0] or "anthropic").strip().lower()
    if provider not in {"openai", "anthropic", "google", "deep_research"}:
        provider = "anthropic"

    title = "Live Voice"
    if context is not None:
        title = f"Live: {context.title}"

    topic = None
    if launch_mode == "dictate_summary":
        topic = "Dictate summary"
    elif launch_mode == "article_voice":
        topic = "Voice with this article"

    session = ChatSession(
        user_id=user_id,
        content_id=context.content_id if context is not None else None,
        title=title[:500],
        session_type="voice_live",
        topic=topic,
        llm_model=model_spec,
        llm_provider=provider,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def persist_voice_turn(
    db: Session,
    *,
    user_id: int,
    chat_session_id: int,
    transcript: str,
    assistant_text: str,
) -> int | None:
    """Persist one voice turn into the regular chat session/message tables."""

    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == chat_session_id, ChatSession.user_id == user_id)
        .first()
    )
    if session is None:
        return None

    transcript_text = transcript.strip()
    assistant_final = assistant_text.strip()
    model_messages: list[ModelMessage] = []

    if transcript_text:
        model_messages.append(ModelRequest(parts=[UserPromptPart(content=transcript_text)]))
    if assistant_final:
        model_messages.append(ModelResponse(parts=[TextPart(content=assistant_final)]))

    if not model_messages:
        return None

    message_json = ModelMessagesTypeAdapter.dump_json(model_messages).decode("utf-8")
    now = datetime.now(UTC)
    db_message = ChatMessage(
        session_id=session.id,
        message_list=message_json,
        created_at=now,
        status=MessageProcessingStatus.COMPLETED.value,
    )
    session.last_message_at = now
    session.updated_at = now
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message.id


def mark_live_voice_onboarding_complete(db: Session, *, user_id: int) -> bool:
    """Mark live voice onboarding as completed for a user."""

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        return False

    if user.has_completed_live_voice_onboarding:
        return False

    user.has_completed_live_voice_onboarding = True
    db.commit()
    return True


def build_live_intro_text(
    *,
    launch_mode: str,
    context_title: str | None = None,
) -> str:
    """Build spoken intro text for first-use live voice onboarding."""

    if launch_mode == "dictate_summary" and context_title:
        return (
            f"Welcome to Live Voice in Newsly. I can summarize {context_title} out loud, "
            "answer follow-up questions, and search your saved knowledge or the web when needed."
        )

    if launch_mode == "article_voice" and context_title:
        return (
            f"Welcome to Live Voice. We are currently focused on {context_title}. "
            "Ask me to explain the key points, challenge assumptions, or dig deeper "
            "in plain speech."
        )

    return (
        "Welcome to Live Voice in Newsly. You can ask about your saved articles and podcasts, "
        "or ask broad questions and I will search the web when needed. "
        "Speak naturally when you're ready."
    )
