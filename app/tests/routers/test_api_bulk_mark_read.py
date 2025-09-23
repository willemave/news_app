"""Tests for the bulk mark read API endpoint."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.schema import Content, ContentReadStatus


def _create_content(db_session: Session, index: int) -> Content:
    """Create content fixture for API tests."""

    content = Content(
        content_type="article",
        url=f"https://example.com/api-bulk-{index}",
        title=f"API Bulk Article {index}",
        status="completed",
        content_metadata={"summary": f"Summary {index}"},
    )
    db_session.add(content)
    db_session.commit()
    db_session.refresh(content)
    return content


def test_bulk_mark_read_endpoint_success(client, db_session: Session) -> None:
    """Ensure the endpoint marks all provided IDs as read."""

    contents = [_create_content(db_session, index) for index in range(3)]
    content_ids = [content.id for content in contents]

    response = client.post(
        "/api/content/bulk-mark-read",
        json={"content_ids": content_ids},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["marked_count"] == len(content_ids)
    assert payload["failed_ids"] == []

    stored_ids = db_session.execute(
        select(ContentReadStatus.content_id)
    ).scalars().all()
    assert sorted(stored_ids) == sorted(content_ids)


def test_bulk_mark_read_endpoint_handles_invalid_ids(client, db_session: Session) -> None:
    """Ensure the endpoint rejects invalid IDs."""

    content = _create_content(db_session, 0)

    response = client.post(
        "/api/content/bulk-mark-read",
        json={"content_ids": [content.id, 9999]},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Invalid content IDs" in detail
    assert "9999" in detail
