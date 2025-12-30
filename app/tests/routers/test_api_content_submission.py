"""Tests for user-submitted content endpoint."""

from app.constants import SELF_SUBMISSION_SOURCE
from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content, ProcessingTask
from app.services.queue import TaskStatus, TaskType


def test_submit_url_creates_content_and_analyze_task(client, db_session):
    """Submitting a new URL should persist content with UNKNOWN type and enqueue ANALYZE_URL."""
    response = client.post("/api/content/submit", json={"url": "https://example.com/article"})

    assert response.status_code == 201
    data = response.json()

    # New submissions always have UNKNOWN type until analyzed
    assert data["content_type"] == ContentType.UNKNOWN.value
    assert data["already_exists"] is False
    assert data["source"] == SELF_SUBMISSION_SOURCE
    assert data["message"] == "Content queued for analysis"

    created = db_session.query(Content).filter(Content.id == data["content_id"]).first()
    assert created is not None
    assert created.source == SELF_SUBMISSION_SOURCE
    assert created.status == ContentStatus.NEW.value
    assert created.content_type == ContentType.UNKNOWN.value
    assert created.classification == "to_read"

    # Task should be ANALYZE_URL, not PROCESS_CONTENT
    task = db_session.query(ProcessingTask).filter_by(content_id=created.id).first()
    assert task is not None
    assert task.task_type == TaskType.ANALYZE_URL.value
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
        json={"url": existing.url},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["already_exists"] is True
    assert data["content_id"] == existing.id
    # Existing content keeps its type
    assert data["content_type"] == ContentType.ARTICLE.value

    contents = db_session.query(Content).filter(Content.url == existing.url).all()
    assert len(contents) == 1

    # Should have either ANALYZE_URL or PROCESS_CONTENT task
    tasks = (
        db_session.query(ProcessingTask)
        .filter_by(content_id=existing.id)
        .filter(
            ProcessingTask.task_type.in_(
                [TaskType.ANALYZE_URL.value, TaskType.PROCESS_CONTENT.value]
            )
        )
        .all()
    )
    assert len(tasks) == 1


def test_submit_spotify_url_creates_unknown_type(client, db_session):
    """Spotify URLs are submitted with UNKNOWN type; type detection happens async."""
    response = client.post(
        "/api/content/submit",
        json={"url": "https://open.spotify.com/episode/abcdef"},
    )

    assert response.status_code == 201
    data = response.json()
    # All new submissions have UNKNOWN type - ANALYZE_URL task will determine actual type
    assert data["content_type"] == ContentType.UNKNOWN.value
    # Platform is not set until ANALYZE_URL task runs
    assert data["platform"] is None


def test_submit_accepts_instruction_alias(client, db_session):
    """Instruction/note field should be accepted and added to ANALYZE_URL payload."""
    response = client.post(
        "/api/content/submit",
        json={
            "url": "https://example.com/article",
            "note": "Add all links from the page",
        },
    )

    assert response.status_code == 201
    data = response.json()

    created = db_session.query(Content).filter(Content.id == data["content_id"]).first()
    assert created is not None
    assert "instruction" not in (created.content_metadata or {})

    task = db_session.query(ProcessingTask).filter_by(content_id=created.id).first()
    assert task is not None
    assert task.payload.get("instruction") == "Add all links from the page"


def test_reject_invalid_scheme(client):
    """Non-http(s) schemes should fail validation."""
    response = client.post("/api/content/submit", json={"url": "ftp://example.com/file"})

    assert response.status_code == 422
