from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import get_settings
from app.models.metadata import ContentStatus
from app.models.schema import Base, Content
from scripts.mark_completed_structured_summary import ScriptOptions, run

SUMMARY_OVERVIEW = (
    "This overview contains sufficient detail to satisfy the validation minimum length."
)
SUMMARY_POINTS = [
    {
        "text": "Bullet point text with enough characters for validation.",
        "category": "insight",
    },
    {
        "text": "Second bullet ensures the structured summary is non-empty.",
        "category": "context",
    },
    {
        "text": "Third bullet point rounds out the structured summary payload.",
        "category": "conclusion",
    },
]


@pytest.fixture()
def session_factory(tmp_path, monkeypatch) -> Generator[sessionmaker]:
    """Provide isolated SQLite session factories for script tests."""

    db_path = tmp_path / "summary_status.sqlite"
    db_url = f"sqlite:///{db_path}"

    monkeypatch.setenv("DATABASE_URL", db_url)
    get_settings.cache_clear()

    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    try:
        yield factory
    finally:
        factory.close_all()
        engine.dispose()
        get_settings.cache_clear()
        monkeypatch.delenv("DATABASE_URL", raising=False)


def _seed_content(
    session: Session,
    *,
    url: str,
    status: ContentStatus,
    include_summary: bool,
) -> int:
    """Insert a content row with optional structured summary payload."""

    metadata_payload: dict[str, object] = {}
    if include_summary:
        metadata_payload["summary"] = {
            "title": "Structured Summary Title",
            "overview": SUMMARY_OVERVIEW,
            "bullet_points": SUMMARY_POINTS,
            "quotes": [],
            "topics": ["ai"],
            "summarization_date": (datetime.utcnow() - timedelta(days=1)).isoformat(),
        }

    content = Content(
        content_type="article",
        url=url,
        source="test-source",
        status=status.value,
        error_message="needs review" if include_summary else None,
        processed_at=None,
        content_metadata=metadata_payload,
    )
    session.add(content)
    session.commit()
    session.refresh(content)

    return int(content.id)


def test_run_updates_status_when_summary_present(session_factory: sessionmaker) -> None:
    """Script should mark content as completed when a structured summary exists."""

    with session_factory() as session:
        content_id = _seed_content(
            session,
            url="https://example.com/article",
            status=ContentStatus.PROCESSING,
            include_summary=True,
        )

    result = run(ScriptOptions())

    assert result.processed == 1
    assert result.updated == 1
    assert result.skipped_missing_summary == 0

    with session_factory() as session:
        refreshed = session.get(Content, content_id)
        assert refreshed is not None
        assert refreshed.status == ContentStatus.COMPLETED.value
        assert refreshed.error_message is None
        assert refreshed.processed_at is not None


def test_run_leaves_rows_untouched_without_summary(session_factory: sessionmaker) -> None:
    """Content without structured summaries must remain unchanged."""

    with session_factory() as session:
        content_id = _seed_content(
            session,
            url="https://example.com/missing-summary",
            status=ContentStatus.PROCESSING,
            include_summary=False,
        )

    result = run(ScriptOptions())

    assert result.processed == 1
    assert result.updated == 0
    assert result.skipped_missing_summary == 1

    with session_factory() as session:
        untouched = session.get(Content, content_id)
        assert untouched is not None
        assert untouched.status == ContentStatus.PROCESSING.value
        assert untouched.error_message is None


def test_run_dry_run_does_not_persist_changes(session_factory: sessionmaker) -> None:
    """Dry-run mode should not commit status updates."""

    with session_factory() as session:
        content_id = _seed_content(
            session,
            url="https://example.com/dry-run",
            status=ContentStatus.PENDING,
            include_summary=True,
        )

    result = run(ScriptOptions(dry_run=True))

    assert result.processed == 1
    assert result.updated == 1

    with session_factory() as session:
        refreshed = session.get(Content, content_id)
        assert refreshed is not None
        assert refreshed.status == ContentStatus.PENDING.value
        assert refreshed.error_message == "needs review"
