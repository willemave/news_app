from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import get_settings
from app.models.metadata import ContentClassification, ContentStatus, ContentType
from app.models.schema import (
    Base,
    Content,
    ContentFavorites,
    ContentReadStatus,
    EventLog,
    ProcessingTask,
)
from scripts.dump_system_stats import (
    StatsOptions,
    format_system_stats,
    gather_system_stats,
)


@pytest.fixture()
def session_factory(tmp_path, monkeypatch) -> Generator[sessionmaker, None, None]:
    """Provide an isolated SQLite database for each test."""

    db_path = tmp_path / "stats.sqlite"
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


def _seed_content_data(session: Session) -> None:
    """Seed representative content, task, and engagement data."""

    now = datetime.utcnow()
    content_rows = [
        Content(
            content_type=ContentType.ARTICLE.value,
            url="https://example.com/article-1",
            source="hackernews",
            platform="web",
            status=ContentStatus.COMPLETED.value,
            classification=ContentClassification.TO_READ.value,
            is_aggregate=False,
            created_at=now - timedelta(days=2),
            processed_at=now - timedelta(days=1),
            content_metadata={},
        ),
        Content(
            content_type=ContentType.ARTICLE.value,
            url="https://example.com/article-2",
            source="hackernews",
            platform="ios",
            status=ContentStatus.FAILED.value,
            classification=ContentClassification.SKIP.value,
            is_aggregate=True,
            created_at=now - timedelta(hours=6),
            processed_at=None,
            content_metadata={},
        ),
        Content(
            content_type=ContentType.PODCAST.value,
            url="https://example.com/podcast-1",
            source="nyt-daily",
            platform=None,
            status=ContentStatus.NEW.value,
            classification=None,
            is_aggregate=False,
            created_at=now - timedelta(hours=1),
            processed_at=None,
            content_metadata={},
        ),
    ]
    session.add_all(content_rows)
    session.flush()

    pending_task = ProcessingTask(
        task_type="process_content",
        content_id=content_rows[2].id,
        status="pending",
        created_at=now - timedelta(hours=3),
        retry_count=0,
    )
    processing_task = ProcessingTask(
        task_type="summarize",
        content_id=content_rows[0].id,
        status="processing",
        created_at=now - timedelta(hours=2),
        started_at=now - timedelta(hours=1, minutes=30),
        retry_count=1,
    )
    failed_task = ProcessingTask(
        task_type="scrape",
        content_id=None,
        status="failed",
        created_at=now - timedelta(hours=4),
        completed_at=now - timedelta(minutes=30),
        retry_count=3,
    )
    session.add_all([pending_task, processing_task, failed_task])

    session.add_all(
        [
            ContentReadStatus(session_id="abc", content_id=content_rows[0].id),
            ContentReadStatus(session_id="def", content_id=content_rows[1].id),
            ContentFavorites(session_id="abc", content_id=content_rows[0].id),
        ]
    )

    session.add_all(
        [
            EventLog(event_type="scraper_run", event_name="hackernews", data={}),
            EventLog(event_type="processing_batch", event_name="worker", data={}),
        ]
    )

    session.commit()


def test_gather_system_stats_returns_expected_counts(session_factory: sessionmaker) -> None:
    """System stats aggregation should reflect seeded database rows accurately."""

    with session_factory() as session:
        _seed_content_data(session)
        stats = gather_system_stats(
            session,
            options=StatsOptions(output_format="json", source_limit=5, platform_limit=5),
        )

    assert stats.content.total == 3
    assert stats.content.by_type[ContentType.ARTICLE.value] == 2
    assert stats.content.by_status[ContentStatus.COMPLETED.value] == 1
    assert stats.content.by_status[ContentStatus.NEW.value] == 1
    assert stats.content.by_type_and_status[ContentType.PODCAST.value][ContentStatus.NEW.value] == 1
    assert stats.content.aggregate_counts["aggregate"] == 1
    assert stats.content.aggregate_counts["non_aggregate"] == 2
    assert stats.content.classification[ContentClassification.TO_READ.value] == 1
    assert stats.content.classification[ContentClassification.SKIP.value] == 1

    source_labels = [item.label for item in stats.content.top_sources]
    assert source_labels[0] == "hackernews"
    assert "nyt-daily" in source_labels

    platform_labels = [item.label for item in stats.content.top_platforms]
    assert "web" in platform_labels
    assert "ios" in platform_labels

    assert stats.tasks.total == 3
    assert stats.tasks.by_status["failed"] == 1
    assert stats.tasks.pending_by_type["process_content"] == 1
    assert stats.tasks.processing_by_type["summarize"] == 1
    assert stats.tasks.recent_failures_last_hour == 1
    assert stats.tasks.max_retry_count == 3

    assert stats.engagement.total_read_marks == 2
    assert stats.engagement.total_favorites == 1

    assert stats.event_logs.total == 2
    assert stats.event_logs.by_type["scraper_run"] == 1


def test_format_system_stats_table_includes_key_sections(session_factory: sessionmaker) -> None:
    """Table formatter should include all key sections in output."""

    with session_factory() as session:
        _seed_content_data(session)
        stats = gather_system_stats(
            session,
            options=StatsOptions(output_format="table", source_limit=3, platform_limit=3),
        )

    report = format_system_stats(stats, output_format="table")

    assert "== Content ==" in report
    assert "== Tasks ==" in report
    assert "== Engagement ==" in report
    assert "== Event Logs ==" in report
    assert "hackernews" in report
    assert "process_content" in report


def test_parse_args_enforces_positive_limits() -> None:
    """CLI parser should enforce positive limits through validation."""

    with pytest.raises(ValidationError):
        StatsOptions(output_format="table", source_limit=0, platform_limit=5)

