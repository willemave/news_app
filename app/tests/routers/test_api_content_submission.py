"""Tests for user-submitted content endpoint."""

from app.constants import SELF_SUBMISSION_SOURCE
from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content, ProcessingTask
from app.services.queue import TaskStatus, TaskType


def test_submit_article_creates_content_and_task(client, db_session):
    """Submitting a new article should persist content and enqueue processing."""
    response = client.post("/api/content/submit", json={"url": "https://example.com/article"})

    assert response.status_code == 201
    data = response.json()

    assert data["content_type"] == ContentType.ARTICLE.value
    assert data["already_exists"] is False
    assert data["source"] == SELF_SUBMISSION_SOURCE

    created = db_session.query(Content).filter(Content.id == data["content_id"]).first()
    assert created is not None
    assert created.source == SELF_SUBMISSION_SOURCE
    assert created.status == ContentStatus.NEW.value
    assert created.classification == "to_read"

    task = db_session.query(ProcessingTask).filter_by(content_id=created.id).first()
    assert task is not None
    assert task.task_type == TaskType.PROCESS_CONTENT.value
    assert task.status == TaskStatus.PENDING.value


def test_duplicate_submission_reuses_existing_record(client, db_session):
    """Submitting the same URL should reuse the record and avoid duplicates."""
    existing = Content(
        url="https://example.com/article",
        content_type=ContentType.ARTICLE.value,
        status=ContentStatus.NEW.value,
        source=SELF_SUBMISSION_SOURCE,
    )
    db_session.add(existing)
    db_session.commit()

    response = client.post(
        "/api/content/submit",
        json={"url": existing.url, "content_type": ContentType.ARTICLE.value},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["already_exists"] is True
    assert data["content_id"] == existing.id

    contents = db_session.query(Content).filter(Content.url == existing.url).all()
    assert len(contents) == 1

    tasks = (
        db_session.query(ProcessingTask)
        .filter_by(content_id=existing.id, task_type=TaskType.PROCESS_CONTENT.value)
        .all()
    )
    assert len(tasks) == 1


def test_submit_podcast_infers_platform(client, db_session):
    """Spotify URLs should be treated as podcasts with platform hint."""
    response = client.post(
        "/api/content/submit",
        json={"url": "https://open.spotify.com/episode/abcdef"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["content_type"] == ContentType.PODCAST.value
    assert data["platform"] == "spotify"


def test_reject_invalid_scheme(client):
    """Non-http(s) schemes should fail validation."""
    response = client.post("/api/content/submit", json={"url": "ftp://example.com/file"})

    assert response.status_code == 422
