"""Tests for content list filtering behavior."""

from __future__ import annotations

from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content, ContentStatusEntry
from app.utils.image_paths import get_content_images_dir


def _build_summary(title: str) -> dict[str, object]:
    return {
        "title": title,
        "overview": (
            "This overview is long enough to satisfy the minimum length requirement "
            "for structured summaries."
        ),
        "bullet_points": [
            {"text": "Key point one", "category": "key_finding"},
            {"text": "Key point two", "category": "methodology"},
            {"text": "Key point three", "category": "conclusion"},
        ],
        "quotes": [],
        "topics": ["Testing"],
        "summarization_date": "2025-12-31T00:00:00Z",
    }


def _add_inbox_status(db_session, user_id: int, content_id: int) -> None:
    db_session.add(
        ContentStatusEntry(
            user_id=user_id,
            content_id=content_id,
            status="inbox",
        )
    )


def test_list_filters_articles_without_keypoints_or_image(
    client,
    db_session,
    test_user,
) -> None:
    ready_article = Content(
        url="https://example.com/ready",
        content_type=ContentType.ARTICLE.value,
        status=ContentStatus.COMPLETED.value,
        content_metadata={
            "summary": _build_summary("Ready Article"),
            "summary_kind": "long_structured",
            "summary_version": 1,
            "image_generated_at": "2025-12-31T00:00:00Z",
        },
    )
    missing_summary = Content(
        url="https://example.com/no-summary",
        content_type=ContentType.ARTICLE.value,
        status=ContentStatus.COMPLETED.value,
        content_metadata={"image_generated_at": "2025-12-31T00:00:00Z"},
    )
    missing_image = Content(
        url="https://example.com/no-image",
        content_type=ContentType.ARTICLE.value,
        status=ContentStatus.COMPLETED.value,
        content_metadata={
            "summary": _build_summary("No Image"),
            "summary_kind": "long_structured",
            "summary_version": 1,
        },
    )

    db_session.add_all([ready_article, missing_summary, missing_image])
    db_session.commit()
    db_session.refresh(ready_article)
    db_session.refresh(missing_summary)
    db_session.refresh(missing_image)

    _add_inbox_status(db_session, test_user.id, ready_article.id)
    _add_inbox_status(db_session, test_user.id, missing_summary.id)
    _add_inbox_status(db_session, test_user.id, missing_image.id)
    db_session.commit()

    images_dir = get_content_images_dir()
    images_dir.mkdir(parents=True, exist_ok=True)
    ready_image = images_dir / f"{ready_article.id}.png"
    missing_summary_image = images_dir / f"{missing_summary.id}.png"

    try:
        ready_image.write_bytes(b"fake-png")
        missing_summary_image.write_bytes(b"fake-png")

        response = client.get("/api/content/", params={"content_type": "article"})
        assert response.status_code == 200
        ids = {item["id"] for item in response.json()["contents"]}

        assert ready_article.id in ids
        assert missing_summary.id not in ids
        assert missing_image.id not in ids
    finally:
        if ready_image.exists():
            ready_image.unlink()
        if missing_summary_image.exists():
            missing_summary_image.unlink()
