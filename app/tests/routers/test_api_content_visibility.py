"""Tests for API content visibility rules."""
from sqlalchemy.orm import Session

from app.models.schema import Content


def _news_summary_payload(title: str) -> dict[str, object]:
    return {
        "title": title,
        "article_url": "https://processed.com/story",
        "key_points": [
            "Headline takeaway",
            "Secondary insight",
        ],
        "summary": "Short overview of the processed item.",
        "classification": "to_read",
        "summarization_date": "2025-09-23T00:00:00Z",
    }


def test_api_excludes_unprocessed_news(client, db_session: Session):
    """Unprocessed news items should not appear in the API feed."""
    pending_news = Content(
        content_type="news",
        url="https://example.com/pending",
        title="Pending Cluster",
        status="new",
        content_metadata={
            "platform": "techmeme",
            "source": "example.com",
            "article": {
                "url": "https://example.com/pending",
                "title": "Pending Article",
            },
            "aggregator": {
                "name": "Techmeme",
            },
            "discussion_url": "https://www.techmeme.com/cluster/pending",
        },
    )

    completed_news = Content(
        content_type="news",
        url="https://processed.com/story",
        title="Processed Cluster",
        status="completed",
        content_metadata={
            "platform": "techmeme",
            "source": "processed.com",
            "article": {
                "url": "https://processed.com/story",
                "title": "Processed Article",
            },
            "aggregator": {
                "name": "Techmeme",
            },
            "discussion_url": "https://www.techmeme.com/cluster/processed",
            "summary": _news_summary_payload("Processed Digest"),
        },
    )

    db_session.add_all([pending_news, completed_news])
    db_session.commit()
    db_session.refresh(completed_news)

    response = client.get("/api/content/?content_type=news&read_filter=unread")
    assert response.status_code == 200

    payload = response.json()
    ids = [item["id"] for item in payload["contents"]]

    assert completed_news.id in ids
    assert pending_news.id not in ids
    assert payload["meta"]["total"] == len(payload["contents"]) == 1
