"""Tests for database search backend selection and ranking."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.contracts import ContentStatus, ContentType
from app.models.schema import Content, ContentStatusEntry
from app.repositories.content_card_repository import search_contents
from app.repositories.search_backend import get_search_backend


def _add_inbox_content(db_session, user_id: int, *, title: str, search_text: str) -> Content:
    """Create a searchable inbox item."""
    content = Content(
        url=f"https://example.com/{title.lower().replace(' ', '-')}",
        title=title,
        content_type=ContentType.ARTICLE.value,
        status=ContentStatus.COMPLETED.value,
        search_text=search_text,
        content_metadata={
            "summary": {
                "title": title,
                "overview": f"{title} overview",
                "bullet_points": [],
                "quotes": [],
                "topics": [],
                "classification": "to_read",
            },
            "summary_kind": "long_structured",
            "summary_version": 1,
            "image_generated_at": "2026-01-01T00:00:00Z",
        },
        created_at=datetime.now(UTC),
    )
    db_session.add(content)
    db_session.flush()
    db_session.add(
        ContentStatusEntry(
            user_id=user_id,
            content_id=content.id,
            status="inbox",
        )
    )
    db_session.commit()
    db_session.refresh(content)
    return content


def test_get_search_backend_prefers_postgres_for_postgres_bind(db_session) -> None:
    """The active test harness should resolve to the native Postgres backend."""
    backend = get_search_backend(db_session)
    assert backend.supports_full_text() is True


def test_postgres_search_ranks_title_matches_before_body_matches(db_session, test_user) -> None:
    """Title matches should outrank body-only matches under the native backend."""
    title_match = _add_inbox_content(
        db_session,
        test_user.id,
        title="Framework release notes",
        search_text="brief update",
    )
    body_match = _add_inbox_content(
        db_session,
        test_user.id,
        title="Unrelated notes",
        search_text="framework release notes with implementation detail",
    )

    rows = search_contents(
        db_session,
        user_id=test_user.id,
        query_text="framework",
        content_type="all",
        search_backend=get_search_backend(db_session),
        cursor=(None, None, None),
        limit=10,
        offset=0,
    )

    assert [row[0].id for row in rows[:2]] == [title_match.id, body_match.id]
    assert rows[0][3] is not None
    assert rows[1][3] is not None
    assert rows[0][3] > rows[1][3]


def test_postgres_search_handles_typo_with_trigram_when_available(db_session, test_user) -> None:
    """Typo-tolerant fallback should return title matches."""
    typo_match = _add_inbox_content(
        db_session,
        test_user.id,
        title="Framework release notes",
        search_text="brief update",
    )

    rows = search_contents(
        db_session,
        user_id=test_user.id,
        query_text="framwork",
        content_type="all",
        search_backend=get_search_backend(db_session),
        cursor=(None, None, None),
        limit=10,
        offset=0,
    )

    assert rows
    assert rows[0][0].id == typo_match.id
