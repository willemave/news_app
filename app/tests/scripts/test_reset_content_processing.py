from __future__ import annotations

from datetime import datetime, timedelta
from typing import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import get_settings
from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Base, Content, ProcessingTask
from scripts.reset_content_processing import ResetOptions, perform_reset

SUMMARY_OVERVIEW = (
    "This overview text is intentionally long to satisfy minimum length requirements."
)
SUMMARY_POINTS = [
    {"text": "First bullet point carries sufficient detail.", "category": "key_finding"},
    {"text": "Second bullet point offers more context here.", "category": "insight"},
    {"text": "Third bullet point wraps up the summary nicely.", "category": "conclusion"},
]


@pytest.fixture()
def session_factory(tmp_path, monkeypatch) -> Generator[sessionmaker, None, None]:
    """Provide an isolated SQLite database session factory for each test."""

    db_path = tmp_path / "reset_content.sqlite"
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
    content_type: ContentType,
    status: ContentStatus,
    processed_delta_hours: float,
) -> int:
    """Seed content and matching processing task; return the content id."""

    processed_at = datetime.utcnow() - timedelta(hours=processed_delta_hours)
    summary_payload = {
        "title": "Valid Content Summary",
        "overview": SUMMARY_OVERVIEW,
        "bullet_points": SUMMARY_POINTS,
        "quotes": [],
        "topics": ["news"],
        "summarization_date": datetime.utcnow().isoformat(),
    }
    metadata_payload = {"summary": summary_payload}
    if content_type is ContentType.PODCAST:
        metadata_payload["audio_url"] = "https://example.com/audio.mp3"

    content = Content(
        content_type=content_type.value,
        url=url,
        source="test-source",
        status=status.value,
        retry_count=2,
        checked_out_by="worker-1",
        checked_out_at=datetime.utcnow(),
        processed_at=processed_at,
        content_metadata=metadata_payload,
    )
    session.add(content)
    session.commit()
    session.refresh(content)

    task = ProcessingTask(
        task_type="process_content",
        content_id=content.id,
        status="processing",
        payload={"content_type": content.content_type, "url": content.url},
    )
    session.add(task)
    session.commit()

    return int(content.id)


def test_perform_reset_cancel_only_removes_tasks(session_factory: sessionmaker) -> None:
    """Ensure cancel-only mode removes tasks without altering content state."""

    with session_factory() as session:
        content_id = _seed_content(
            session,
            url="https://example.com/article",
            content_type=ContentType.ARTICLE,
            status=ContentStatus.PROCESSING,
            processed_delta_hours=1,
        )

    result = perform_reset(ResetOptions(cancel_tasks_only=True))

    assert result.deleted_tasks == 1
    assert result.reset_contents == 0
    assert result.created_tasks == 0

    with session_factory() as session:
        refreshed = session.get(Content, content_id)
        assert refreshed is not None
        assert refreshed.status == ContentStatus.PROCESSING.value
        assert refreshed.content_metadata["summary"]["overview"] == SUMMARY_OVERVIEW
        remaining_tasks = session.query(ProcessingTask).count()
        assert remaining_tasks == 0


def test_perform_reset_hours_filter_targets_recent_content(session_factory: sessionmaker) -> None:
    """Reset should only affect content touched within the requested hour window."""

    with session_factory() as session:
        recent_id = _seed_content(
            session,
            url="https://example.com/recent",
            content_type=ContentType.ARTICLE,
            status=ContentStatus.COMPLETED,
            processed_delta_hours=2,
        )
        stale_id = _seed_content(
            session,
            url="https://example.com/stale",
            content_type=ContentType.ARTICLE,
            status=ContentStatus.COMPLETED,
            processed_delta_hours=48,
        )

    result = perform_reset(ResetOptions(hours=12.0))

    assert result.deleted_tasks == 1
    assert result.reset_contents == 1
    assert result.created_tasks == 1

    with session_factory() as session:
        refreshed_recent = session.get(Content, recent_id)
        assert refreshed_recent is not None
        assert refreshed_recent.status == ContentStatus.NEW.value
        assert refreshed_recent.retry_count == 0
        assert refreshed_recent.checked_out_by is None
        assert refreshed_recent.processed_at is None
        assert refreshed_recent.content_metadata == {}

        refreshed_stale = session.get(Content, stale_id)
        assert refreshed_stale is not None
        assert refreshed_stale.status == ContentStatus.COMPLETED.value

        stale_tasks = session.query(ProcessingTask).filter_by(content_id=stale_id).count()
        assert stale_tasks == 1

        recent_tasks = session.query(ProcessingTask).filter_by(content_id=recent_id).all()
        assert len(recent_tasks) == 1
        assert recent_tasks[0].status == "pending"


def test_perform_reset_filters_by_content_type(session_factory: sessionmaker) -> None:
    """Content type filter should isolate resets to the requested type."""

    with session_factory() as session:
        podcast_id = _seed_content(
            session,
            url="https://example.com/podcast",
            content_type=ContentType.PODCAST,
            status=ContentStatus.COMPLETED,
            processed_delta_hours=3,
        )
        article_id = _seed_content(
            session,
            url="https://example.com/article2",
            content_type=ContentType.ARTICLE,
            status=ContentStatus.COMPLETED,
            processed_delta_hours=3,
        )

    result = perform_reset(ResetOptions(content_type=ContentType.PODCAST))

    assert result.deleted_tasks == 1
    assert result.reset_contents == 1
    assert result.created_tasks == 1

    with session_factory() as session:
        refreshed_podcast = session.get(Content, podcast_id)
        assert refreshed_podcast is not None
        assert refreshed_podcast.status == ContentStatus.NEW.value

        refreshed_article = session.get(Content, article_id)
        assert refreshed_article is not None
        assert refreshed_article.status == ContentStatus.COMPLETED.value

        article_tasks = session.query(ProcessingTask).filter_by(content_id=article_id).count()
        assert article_tasks == 1
        podcast_tasks = session.query(ProcessingTask).filter_by(content_id=podcast_id).count()
        assert podcast_tasks == 1
