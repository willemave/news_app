"""Tests for terminal content-worker failure paths."""

from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy.exc import IntegrityError

from app.domain.converters import content_to_domain
from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content
from app.pipeline.worker import ContentWorker


def _patch_worker_db(monkeypatch, db_session) -> None:
    @contextmanager
    def _get_db_override():
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    monkeypatch.setattr("app.pipeline.worker.get_db", _get_db_override)


def test_update_canonical_url_marks_existing_content_id(monkeypatch, db_session) -> None:
    _patch_worker_db(monkeypatch, db_session)

    existing = Content(
        content_type=ContentType.ARTICLE.value,
        url="https://example.com/canonical",
        status=ContentStatus.NEW.value,
        content_metadata={},
    )
    incoming = Content(
        content_type=ContentType.ARTICLE.value,
        url="https://example.com/original",
        status=ContentStatus.NEW.value,
        content_metadata={},
    )
    db_session.add_all([existing, incoming])
    db_session.commit()
    db_session.refresh(existing)
    db_session.refresh(incoming)

    worker = ContentWorker()
    domain_content = content_to_domain(incoming)
    worker._update_canonical_url(domain_content, "https://example.com/canonical")

    assert domain_content.metadata["canonical_content_id"] == existing.id
    assert str(domain_content.url) == "https://example.com/original"


def test_handle_canonical_integrity_conflict_marks_content_skipped(monkeypatch, db_session) -> None:
    _patch_worker_db(monkeypatch, db_session)

    existing = Content(
        content_type=ContentType.ARTICLE.value,
        url="https://example.com/dupe",
        status=ContentStatus.PROCESSING.value,
        content_metadata={},
    )
    incoming = Content(
        content_type=ContentType.ARTICLE.value,
        url="https://example.com/unique",
        status=ContentStatus.PROCESSING.value,
        content_metadata={},
    )
    db_session.add_all([existing, incoming])
    db_session.commit()
    db_session.refresh(existing)
    db_session.refresh(incoming)

    worker = ContentWorker()
    domain_content = content_to_domain(incoming)
    domain_content.url = "https://example.com/dupe"
    integrity_error = IntegrityError(
        "UPDATE contents ...",
        {},
        Exception("UNIQUE constraint failed: contents.url, contents.content_type"),
    )

    handled = worker._handle_canonical_integrity_conflict(domain_content, integrity_error)
    assert handled is True

    db_session.refresh(incoming)
    assert incoming.status == ContentStatus.SKIPPED.value
    assert incoming.content_metadata["canonical_content_id"] == existing.id


def test_process_content_handles_integrity_error_from_worker(monkeypatch, db_session) -> None:
    _patch_worker_db(monkeypatch, db_session)

    existing = Content(
        content_type=ContentType.ARTICLE.value,
        url="https://example.com/dupe-worker",
        status=ContentStatus.PROCESSING.value,
        content_metadata={},
    )
    incoming = Content(
        content_type=ContentType.ARTICLE.value,
        url="https://example.com/original-worker",
        status=ContentStatus.PROCESSING.value,
        content_metadata={},
    )
    db_session.add_all([existing, incoming])
    db_session.commit()
    db_session.refresh(existing)
    db_session.refresh(incoming)

    def _raise_integrity(_self, content):  # noqa: ANN001
        content.url = "https://example.com/dupe-worker"
        raise IntegrityError(
            "UPDATE contents ...",
            {},
            Exception("UNIQUE constraint failed: contents.url, contents.content_type"),
        )

    monkeypatch.setattr(ContentWorker, "_process_article", _raise_integrity)

    worker = ContentWorker()
    handled = worker.process_content(incoming.id, "test-worker")

    assert handled is True
    db_session.refresh(incoming)
    assert incoming.status == ContentStatus.SKIPPED.value
    assert incoming.content_metadata["canonical_content_id"] == existing.id
