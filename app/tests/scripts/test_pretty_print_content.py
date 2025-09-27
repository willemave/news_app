from __future__ import annotations

from datetime import datetime

import pytest

from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content
from scripts.pretty_print_content import (  # type: ignore[import-not-found]
    PrettyPrintArgs,
    pretty_print_content,
)


def _insert_content(
    session,
    content_type: ContentType,
    url: str,
    title: str,
    created_at: datetime,
) -> Content:
    """Helper to seed a content row for tests."""

    content = Content(
        content_type=content_type.value,
        url=url,
        title=title,
        source="test",
        platform="cli",
        status=ContentStatus.COMPLETED.value,
        classification=None,
        is_aggregate=False,
        created_at=created_at,
        processed_at=created_at,
        content_metadata={"notes": "seed"},
    )
    session.add(content)
    session.commit()
    session.refresh(content)
    return content


def test_pretty_print_by_id_returns_single_payload(db_session) -> None:
    """Fetching by ID should return exactly one payload with matching attributes."""

    created_at = datetime(2025, 9, 20, 12, 0, 0)
    content = _insert_content(
        db_session,
        ContentType.ARTICLE,
        url="https://example.com/article",
        title="Test Article",
        created_at=created_at,
    )

    args = PrettyPrintArgs(content_id=content.id)
    result = pretty_print_content(db_session, args)

    assert len(result.contents) == 1
    payload = result.contents[0]
    assert payload.id == content.id
    assert payload.content_type == ContentType.ARTICLE
    assert payload.metadata["notes"] == "seed"
    assert payload.created_at == created_at


def test_pretty_print_random_sample_respects_count(db_session) -> None:
    """Random sample fetch should return the requested number of records."""

    base_time = datetime(2025, 9, 20, 13, 0, 0)
    for index in range(5):
        _insert_content(
            db_session,
            ContentType.NEWS,
            url=f"https://example.com/news/{index}",
            title=f"News {index}",
            created_at=base_time,
        )

    args = PrettyPrintArgs(content_type=ContentType.NEWS, count=2)
    result = pretty_print_content(db_session, args)

    assert len(result.contents) == 2
    for payload in result.contents:
        assert payload.content_type == ContentType.NEWS


def test_pretty_print_missing_content_raises_lookup_error(db_session) -> None:
    """Missing content ID should raise LookupError before returning payload."""

    args = PrettyPrintArgs(content_id=999)

    with pytest.raises(LookupError):
        pretty_print_content(db_session, args)
