from app.models.schema import Content, ContentStatusEntry


def test_submission_creates_content_status(client, db_session, test_user):
    payload = {
        "url": "https://example.com/article-1",
        "content_type": "article",
        "title": "Example",
    }
    resp = client.post("/api/content/submit", json=payload)
    assert resp.status_code in (200, 201)

    content = db_session.query(Content).filter_by(url=payload["url"]).first()
    assert content is not None

    status_row = (
        db_session.query(ContentStatusEntry)
        .filter_by(user_id=test_user.id, content_id=content.id)
        .first()
    )
    assert status_row is not None
    assert status_row.status == "inbox"
