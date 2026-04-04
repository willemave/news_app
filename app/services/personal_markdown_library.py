"""Per-user markdown library persisted from canonical content bodies."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml
from sqlalchemy import distinct
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.models.schema import ChatSession, Content, ContentFavorites
from app.services.content_bodies import ContentBodyVariant, get_content_body_resolver
from app.utils.summary_utils import extract_short_summary, extract_summary_text

logger = get_logger(__name__)

CONTENT_ID_PATTERN = re.compile(r"__c(?P<content_id>\d+)\.md$")
VARIANT_SOURCE = "source"
VARIANT_SUMMARY = "summary"


@dataclass(frozen=True)
class PersonalMarkdownReasons:
    """Reasons a content item belongs in one user's personal library."""

    is_favorited: bool
    chat_session_ids: list[int]

    @property
    def labels(self) -> list[str]:
        labels: list[str] = []
        if self.is_favorited:
            labels.append("favorited")
        if self.chat_session_ids:
            labels.append("chatted")
        return labels


@dataclass(frozen=True)
class PersonalMarkdownSyncResult:
    """Summary of one sync pass."""

    user_id: int
    written_files: list[Path]
    deleted_files: list[Path]


def get_personal_markdown_user_root(user_id: int) -> Path:
    """Return the filesystem root for one user's markdown library."""
    settings = get_settings()
    return (settings.personal_markdown_root_dir / str(user_id)).resolve()


def sync_personal_markdown_library_for_user(
    db: Session,
    *,
    user_id: int,
) -> PersonalMarkdownSyncResult:
    """Reconcile one user's markdown library from favorites and chat sessions."""
    settings = get_settings()
    if not settings.personal_markdown_enabled:
        return PersonalMarkdownSyncResult(user_id=user_id, written_files=[], deleted_files=[])

    user_root = get_personal_markdown_user_root(user_id)
    user_root.mkdir(parents=True, exist_ok=True)

    qualifying_reasons = _load_qualifying_content_reasons(db, user_id=user_id)
    written_files: list[Path] = []
    deleted_files: list[Path] = []

    existing_content_ids = _scan_existing_content_ids(user_root)
    desired_content_ids = set(qualifying_reasons)

    for stale_content_id in sorted(existing_content_ids - desired_content_ids):
        deleted_files.extend(_delete_content_files(user_root, stale_content_id))

    for content_id, reasons in qualifying_reasons.items():
        content = db.query(Content).filter(Content.id == content_id).first()
        if content is None:
            deleted_files.extend(_delete_content_files(user_root, content_id))
            continue
        written_files.extend(
            _sync_content_markdown_files(
                db=db,
                user_root=user_root,
                user_id=user_id,
                content=content,
                reasons=reasons,
            )
        )

    return PersonalMarkdownSyncResult(
        user_id=user_id,
        written_files=written_files,
        deleted_files=deleted_files,
    )


def sync_personal_markdown_for_content(
    db: Session,
    *,
    user_id: int,
    content_id: int,
) -> PersonalMarkdownSyncResult:
    """Reconcile a single content item inside one user's library."""
    settings = get_settings()
    if not settings.personal_markdown_enabled:
        return PersonalMarkdownSyncResult(user_id=user_id, written_files=[], deleted_files=[])

    user_root = get_personal_markdown_user_root(user_id)
    user_root.mkdir(parents=True, exist_ok=True)

    reasons = _load_reasons_for_content(db, user_id=user_id, content_id=content_id)
    if not reasons.labels:
        deleted_files = _delete_content_files(user_root, content_id)
        return PersonalMarkdownSyncResult(
            user_id=user_id,
            written_files=[],
            deleted_files=deleted_files,
        )

    content = db.query(Content).filter(Content.id == content_id).first()
    if content is None:
        deleted_files = _delete_content_files(user_root, content_id)
        return PersonalMarkdownSyncResult(
            user_id=user_id,
            written_files=[],
            deleted_files=deleted_files,
        )

    written_files = _sync_content_markdown_files(
        db=db,
        user_root=user_root,
        user_id=user_id,
        content=content,
        reasons=reasons,
    )
    return PersonalMarkdownSyncResult(
        user_id=user_id,
        written_files=written_files,
        deleted_files=[],
    )


def _load_qualifying_content_reasons(
    db: Session,
    *,
    user_id: int,
) -> dict[int, PersonalMarkdownReasons]:
    favorite_ids = {
        int(content_id)
        for content_id, in (
            db.query(ContentFavorites.content_id)
            .filter(ContentFavorites.user_id == user_id)
            .all()
        )
    }

    chat_rows = (
        db.query(ChatSession.content_id, ChatSession.id)
        .filter(
            ChatSession.user_id == user_id,
            ChatSession.content_id.is_not(None),
            ChatSession.is_archived == False,  # noqa: E712
        )
        .all()
    )

    chat_session_map: dict[int, list[int]] = {}
    for content_id, session_id in chat_rows:
        if content_id is None:
            continue
        chat_session_map.setdefault(int(content_id), []).append(int(session_id))

    all_content_ids = favorite_ids | set(chat_session_map)
    return {
        content_id: PersonalMarkdownReasons(
            is_favorited=content_id in favorite_ids,
            chat_session_ids=sorted(chat_session_map.get(content_id, [])),
        )
        for content_id in sorted(all_content_ids)
    }


def _load_reasons_for_content(
    db: Session,
    *,
    user_id: int,
    content_id: int,
) -> PersonalMarkdownReasons:
    is_favorited = (
        db.query(ContentFavorites.id)
        .filter(ContentFavorites.user_id == user_id, ContentFavorites.content_id == content_id)
        .first()
        is not None
    )
    chat_session_ids = [
        int(session_id)
        for session_id, in (
            db.query(distinct(ChatSession.id))
            .filter(
                ChatSession.user_id == user_id,
                ChatSession.content_id == content_id,
                ChatSession.is_archived == False,  # noqa: E712
            )
            .all()
        )
    ]
    return PersonalMarkdownReasons(
        is_favorited=is_favorited,
        chat_session_ids=sorted(chat_session_ids),
    )


def _sync_content_markdown_files(
    *,
    db: Session,
    user_root: Path,
    user_id: int,
    content: Content,
    reasons: PersonalMarkdownReasons,
) -> list[Path]:
    resolver = get_content_body_resolver()
    source_text = resolver.resolve_text(db, content=content, variant=ContentBodyVariant.SOURCE)
    summary_text = resolver.resolve_text(db, content=content, variant=ContentBodyVariant.RENDERED)
    if not summary_text:
        summary_text = _build_summary_markdown(content)

    deleted_files = _delete_content_files(user_root, int(content.id))
    if deleted_files:
        logger.debug(
            "Rewriting personal markdown files for content_id=%s user_id=%s",
            content.id,
            user_id,
        )

    source_slug = _slugify_segment(_content_source_name(content))
    content_type = _slugify_segment(content.content_type or "unknown")
    base_dir = user_root / content_type / source_slug
    base_dir.mkdir(parents=True, exist_ok=True)

    written_files: list[Path] = []
    for variant, body in ((VARIANT_SOURCE, source_text), (VARIANT_SUMMARY, summary_text)):
        cleaned_body = (body or "").strip()
        if not cleaned_body:
            continue

        path = base_dir / _build_filename(content=content, variant=variant)
        path.write_text(
            _render_markdown_document(
                user_id=user_id,
                content=content,
                variant=variant,
                body=cleaned_body,
                reasons=reasons,
            ),
            encoding="utf-8",
        )
        written_files.append(path)

    _prune_empty_dirs(base_dir, stop_at=user_root)
    return written_files


def _build_filename(*, content: Content, variant: str) -> str:
    settings = get_settings()
    slug = _slugify_segment(
        content.title or "untitled",
        max_length=settings.personal_markdown_max_slug_length,
    )
    date_value = _content_date(content).strftime("%Y-%m-%d")
    return f"{slug}__{date_value}__{variant}__c{int(content.id)}.md"


def _render_markdown_document(
    *,
    user_id: int,
    content: Content,
    variant: str,
    body: str,
    reasons: PersonalMarkdownReasons,
) -> str:
    frontmatter = {
        "content_id": int(content.id),
        "user_id": user_id,
        "content_type": content.content_type,
        "variant": variant,
        "title": content.title or "Untitled",
        "source": _content_source_name(content),
        "url": content.url,
        "published_at": _isoformat(_content_date(content)),
        "saved_at": _isoformat(datetime.now(UTC)),
        "reasons": reasons.labels,
        "chat_session_ids": reasons.chat_session_ids,
    }
    frontmatter_text = yaml.safe_dump(
        frontmatter,
        sort_keys=False,
        allow_unicode=False,
    ).strip()
    return f"---\n{frontmatter_text}\n---\n\n{body}\n"


def _build_summary_markdown(content: Content) -> str | None:
    metadata = content.content_metadata if isinstance(content.content_metadata, dict) else {}
    summary = metadata.get("summary")
    if not isinstance(summary, dict):
        return None

    sections: list[str] = []
    title = str(summary.get("title") or content.title or "").strip()
    if title:
        sections.append(f"# {title}")

    overview = extract_summary_text(summary) or extract_short_summary(summary)
    if overview:
        sections.append(overview.strip())

    bullet_points = summary.get("bullet_points") or summary.get("key_points")
    if isinstance(bullet_points, list) and bullet_points:
        rendered_points: list[str] = []
        for item in bullet_points:
            if isinstance(item, dict):
                text = str(item.get("text") or item.get("point") or "").strip()
            else:
                text = str(item).strip()
            if text:
                rendered_points.append(f"- {text}")
        if rendered_points:
            sections.append("## Key Points")
            sections.extend(rendered_points)

    topics = summary.get("topics")
    if isinstance(topics, list):
        cleaned_topics = [str(topic).strip() for topic in topics if str(topic).strip()]
        if cleaned_topics:
            sections.append("## Topics")
            sections.extend(f"- {topic}" for topic in cleaned_topics)

    rendered = "\n\n".join(section for section in sections if section.strip()).strip()
    return rendered or None


def _content_source_name(content: Content) -> str:
    metadata = content.content_metadata if isinstance(content.content_metadata, dict) else {}
    for candidate in (
        content.source,
        metadata.get("podcast_title"),
        metadata.get("show_name"),
        metadata.get("source"),
    ):
        value = str(candidate or "").strip()
        if value:
            return value
    return "unknown-source"


def _content_date(content: Content) -> datetime:
    for candidate in (content.publication_date, content.created_at, content.updated_at):
        if isinstance(candidate, datetime):
            return candidate
    return datetime.now(UTC).replace(tzinfo=None)


def _slugify_segment(raw: str, *, max_length: int | None = None) -> str:
    normalized = raw.lower().strip()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = normalized.strip("-") or "untitled"
    if max_length is not None:
        normalized = normalized[:max_length].strip("-") or "untitled"
    return normalized


def _scan_existing_content_ids(user_root: Path) -> set[int]:
    content_ids: set[int] = set()
    if not user_root.exists():
        return content_ids

    for path in user_root.rglob("*.md"):
        match = CONTENT_ID_PATTERN.search(path.name)
        if match:
            content_ids.add(int(match.group("content_id")))
    return content_ids


def _delete_content_files(user_root: Path, content_id: int) -> list[Path]:
    deleted: list[Path] = []
    if not user_root.exists():
        return deleted

    for path in user_root.rglob(f"*__c{content_id}.md"):
        if path.exists():
            path.unlink()
            deleted.append(path)
            _prune_empty_dirs(path.parent, stop_at=user_root)
    return deleted


def _prune_empty_dirs(path: Path, *, stop_at: Path) -> None:
    current = path
    while current != stop_at and current.exists():
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC).isoformat()
    return value.astimezone(UTC).isoformat()
