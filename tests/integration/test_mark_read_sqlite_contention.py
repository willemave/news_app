"""Integration tests for mark-read behavior under SQLite write contention."""

from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

import app.core.db as core_db
from app.main import app
from app.models.schema import Base, Content, ContentReadStatus, NewsItem, NewsItemReadStatus
from app.models.user import User


@dataclass(frozen=True)
class _ContentionHarness:
    client: TestClient
    db_path: Path
    session_factory: sessionmaker
    user: User


def _create_file_backed_engine(db_path: Path):
    """Create a SQLite engine that mirrors production's WAL-oriented setup."""
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _configure_connection(dbapi_conn, _connection_record) -> None:  # noqa: ANN001
        cursor = dbapi_conn.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.fetchone()
            cursor.execute("PRAGMA synchronous=NORMAL")
        finally:
            cursor.close()

    return engine


def _seed_user(session: Session) -> User:
    """Create the authenticated user for the integration client."""
    user = User(
        apple_id="mark-read-contention-user",
        email="mark-read-contention@example.com",
        full_name="Mark Read Contention",
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    session.expunge(user)
    return user


def _seed_content(session: Session, *, url: str, title: str) -> Content:
    """Create a content row suitable for bulk mark-read tests."""
    content = Content(
        content_type="article",
        url=url,
        title=title,
        source="example.com",
        status="completed",
        content_metadata={},
    )
    session.add(content)
    session.commit()
    session.refresh(content)
    session.expunge(content)
    return content


def _seed_news_item(session: Session, *, ingest_key: str, title: str) -> NewsItem:
    """Create a visible representative news item suitable for mark-read tests."""
    news_item = NewsItem(
        ingest_key=ingest_key,
        visibility_scope="global",
        platform="hackernews",
        source_type="hackernews",
        source_label="Hacker News",
        source_external_id=ingest_key,
        canonical_item_url=f"https://news.ycombinator.com/item?id={ingest_key}",
        canonical_story_url=f"https://example.com/{ingest_key}",
        article_url=f"https://example.com/{ingest_key}",
        article_title=title,
        article_domain="example.com",
        discussion_url=f"https://news.ycombinator.com/item?id={ingest_key}",
        summary_title=title,
        summary_key_points=["Point one"],
        summary_text=f"{title} summary",
        raw_metadata={
            "cluster": {
                "member_ids": [ingest_key],
                "source_labels": ["Hacker News"],
                "domains": ["example.com"],
                "discussion_snippets": ["Useful comment"],
                "related_titles": [title],
                "latest_member_ingested_at": datetime.now(UTC).isoformat(),
            }
        },
        representative_news_item_id=None,
        cluster_size=1,
        status="ready",
        ingested_at=datetime.now(UTC).replace(tzinfo=None),
        processed_at=datetime.now(UTC).replace(tzinfo=None),
    )
    session.add(news_item)
    session.commit()
    session.refresh(news_item)
    session.expunge(news_item)
    return news_item


def _count_content_read_rows(
    session_factory: sessionmaker,
    *,
    user_id: int,
    content_id: int,
) -> int:
    with session_factory() as session:
        return (
            session.query(ContentReadStatus)
            .filter(
                ContentReadStatus.user_id == user_id,
                ContentReadStatus.content_id == content_id,
            )
            .count()
        )


def _count_news_read_rows(
    session_factory: sessionmaker,
    *,
    user_id: int,
    news_item_id: int,
) -> int:
    with session_factory() as session:
        return (
            session.query(NewsItemReadStatus)
            .filter(
                NewsItemReadStatus.user_id == user_id,
                NewsItemReadStatus.news_item_id == news_item_id,
            )
            .count()
        )


def _hold_sqlite_write_lock(
    db_path: Path,
    *,
    locked_event: threading.Event,
    release_event: threading.Event,
) -> None:
    """Hold a write lock with BEGIN IMMEDIATE until released."""
    connection = sqlite3.connect(
        str(db_path),
        timeout=0,
        isolation_level=None,
        check_same_thread=False,
    )
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("BEGIN IMMEDIATE")
        locked_event.set()
        release_event.wait(timeout=5)
        connection.rollback()
    finally:
        connection.close()


@contextmanager
def _write_lock(db_path: Path) -> Iterator[threading.Event]:
    """Start a background thread that keeps the SQLite write lock held."""
    locked_event = threading.Event()
    release_event = threading.Event()
    worker = threading.Thread(
        target=_hold_sqlite_write_lock,
        kwargs={
            "db_path": db_path,
            "locked_event": locked_event,
            "release_event": release_event,
        },
        daemon=True,
    )
    worker.start()
    assert locked_event.wait(timeout=2), "failed to acquire test SQLite write lock"
    try:
        yield release_event
    finally:
        release_event.set()
        worker.join(timeout=2)
        assert not worker.is_alive(), "test SQLite lock thread did not exit"


@pytest.fixture
def contention_harness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[_ContentionHarness]:
    """Create a file-backed SQLite app harness for contention integration tests."""
    from app.core.db import get_db_session, get_readonly_db_session
    from app.core.deps import get_current_user

    db_path = tmp_path / "mark-read-contention.sqlite3"
    engine = _create_file_backed_engine(db_path)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    previous_engine = core_db._engine
    previous_session_local = core_db._SessionLocal
    previous_sqlite_log_flag = core_db._sqlite_runtime_diagnostics_logged
    Base.metadata.create_all(bind=engine)

    base_settings = core_db.get_settings()
    patched_settings = base_settings.model_copy(
        update={"sqlite_busy_timeout_ms": 30_000, "sqlite_write_retry_attempts": 1}
    )
    monkeypatch.setattr(
        core_db,
        "get_settings",
        lambda: patched_settings,
    )
    core_db._engine = engine
    core_db._SessionLocal = session_factory
    core_db._sqlite_runtime_diagnostics_logged = False

    with session_factory() as session:
        user = _seed_user(session)

    def override_get_db() -> Iterator[Session]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def override_get_current_user() -> User:
        return user

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_readonly_db_session] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        with TestClient(app) as client:
            yield _ContentionHarness(
                client=client,
                db_path=db_path,
                session_factory=session_factory,
                user=user,
            )
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        core_db._engine = previous_engine
        core_db._SessionLocal = previous_session_local
        core_db._sqlite_runtime_diagnostics_logged = previous_sqlite_log_flag
        engine.dispose()


@pytest.mark.integration
def test_news_mark_read_waits_for_transient_sqlite_write_lock(
    contention_harness: _ContentionHarness,
) -> None:
    """A short write lock should delay the request, not break it."""
    with contention_harness.session_factory() as session:
        news_item = _seed_news_item(
            session,
            ingest_key="contention-news-success",
            title="SQLite lock success",
        )

    with _write_lock(contention_harness.db_path) as release_event:
        release_timer = threading.Timer(0.15, release_event.set)
        release_timer.start()
        started_at = time.perf_counter()
        response = contention_harness.client.post(
            "/api/news/items/mark-read",
            json={"content_ids": [news_item.id]},
        )
        duration_seconds = time.perf_counter() - started_at
        release_timer.join(timeout=1)

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "marked_count": 1,
        "failed_ids": [],
        "total_requested": 1,
    }
    assert duration_seconds >= 0.1
    assert (
        _count_news_read_rows(
            contention_harness.session_factory,
            user_id=contention_harness.user.id,
            news_item_id=news_item.id,
        )
        == 1
    )


@pytest.mark.integration
def test_news_mark_read_returns_failed_ids_when_sqlite_write_lock_persists(
    contention_harness: _ContentionHarness,
) -> None:
    """A long-held write lock should degrade to failed_ids instead of a 500."""
    with contention_harness.session_factory() as session:
        news_item = _seed_news_item(
            session,
            ingest_key="contention-news-failure",
            title="SQLite lock failure",
        )

    with _write_lock(contention_harness.db_path):
        started_at = time.perf_counter()
        response = contention_harness.client.post(
            "/api/news/items/mark-read",
            json={"content_ids": [news_item.id]},
        )
        duration_seconds = time.perf_counter() - started_at

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "marked_count": 0,
        "failed_ids": [news_item.id],
        "total_requested": 1,
    }
    assert duration_seconds >= 0.2
    assert (
        _count_news_read_rows(
            contention_harness.session_factory,
            user_id=contention_harness.user.id,
            news_item_id=news_item.id,
        )
        == 0
    )


@pytest.mark.integration
def test_bulk_content_mark_read_returns_failed_ids_when_sqlite_write_lock_persists(
    contention_harness: _ContentionHarness,
) -> None:
    """The content bulk endpoint should also fail soft under a sustained write lock."""
    with contention_harness.session_factory() as session:
        content = _seed_content(
            session,
            url="https://example.com/contention-content-failure",
            title="SQLite content lock failure",
        )

    with _write_lock(contention_harness.db_path):
        started_at = time.perf_counter()
        response = contention_harness.client.post(
            "/api/content/bulk-mark-read",
            json={"content_ids": [content.id]},
        )
        duration_seconds = time.perf_counter() - started_at

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "marked_count": 0,
        "failed_ids": [content.id],
        "total_requested": 1,
    }
    assert duration_seconds >= 0.2
    assert (
        _count_content_read_rows(
            contention_harness.session_factory,
            user_id=contention_harness.user.id,
            content_id=content.id,
        )
        == 0
    )
