"""Helpers for bullet-scoped news digest chats."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.schema import (
    ChatMessage,
    ChatSession,
    NewsDigest,
    NewsDigestBullet,
    NewsDigestBulletSource,
    NewsItem,
)
from app.services.chat_agent import create_processing_message
from app.services.llm_models import DEFAULT_MODEL, DEFAULT_PROVIDER

NEWS_DIGEST_BULLET_DIG_DEEPER_PROMPT = (
    "Dig deeper into this news digest bullet. Explain what happened, why it matters, "
    "and how the cited items support it. If evidence is missing or conflicting, say so plainly."
)


def _build_bullet_context_snapshot(
    bullet: NewsDigestBullet,
    source_items: list[NewsItem],
) -> str:
    lines = [
        "Selected digest bullet:",
        f"- Topic: {bullet.topic}",
        f"- Details: {bullet.details}",
    ]
    if source_items:
        lines.extend(["", "Cited evidence:"])
        for item in source_items:
            label = item.source_label or item.platform or "Source"
            title = item.summary_title or item.article_title or f"News item {item.id}"
            url = item.discussion_url or item.canonical_item_url or item.article_url
            if url:
                lines.append(f"- [{item.id}] {label}: {title} ({url})")
            else:
                lines.append(f"- [{item.id}] {label}: {title}")

            discussion_payload = item.raw_metadata.get("discussion_payload")
            if isinstance(discussion_payload, dict):
                compact_comments = discussion_payload.get("compact_comments")
                if isinstance(compact_comments, list):
                    for comment in compact_comments[:2]:
                        if isinstance(comment, str) and comment.strip():
                            lines.append(f'  Discussion: "{comment.strip()}"')

    return "\n".join(lines)


def start_news_digest_bullet_chat(
    db: Session,
    *,
    digest: NewsDigest,
    bullet: NewsDigestBullet,
    user_id: int,
) -> tuple[ChatSession, ChatMessage, str]:
    """Create a fresh chat session for one news digest bullet."""
    bullet_sources = (
        db.query(NewsDigestBulletSource)
        .filter(NewsDigestBulletSource.bullet_id == bullet.id)
        .order_by(NewsDigestBulletSource.position.asc())
        .all()
    )
    source_ids = [row.news_item_id for row in bullet_sources]
    source_items: list[NewsItem] = []
    if source_ids:
        source_items = (
            db.query(NewsItem)
            .filter(NewsItem.id.in_(source_ids))
            .order_by(NewsItem.ingested_at.desc(), NewsItem.id.desc())
            .all()
        )

    context_snapshot = _build_bullet_context_snapshot(bullet, source_items)
    session = ChatSession(
        user_id=user_id,
        content_id=None,
        title=digest.title,
        session_type="news_digest_brain",
        topic=bullet.topic,
        context_snapshot=context_snapshot,
        llm_provider=DEFAULT_PROVIDER,
        llm_model=DEFAULT_MODEL,
        created_at=datetime.now(UTC),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    message = create_processing_message(db, session.id, NEWS_DIGEST_BULLET_DIG_DEEPER_PROMPT)
    return session, message, NEWS_DIGEST_BULLET_DIG_DEEPER_PROMPT
