"""Tests for content router with read status functionality."""
from sqlalchemy.orm import Session

from app.models.schema import Content, ContentReadStatus


def test_content_list_with_read_filter(
    client,
    db_session: Session
):
    """Test content list with read/unread filtering."""
    # Create test content
    for i in range(3):
        content = Content(
            content_type="article",
            url=f"https://example.com/article{i}",
            title=f"Test Article {i}",
            status="completed",
            content_metadata={
                "summary": {
                    "title": f"Test Article {i}",
                    "overview": f"This is a comprehensive test summary for article {i} that contains detailed information about the content to meet the minimum length requirement.",
                    "bullet_points": [
                        {
                            "text": f"Key point {i}.1: Important information about topic {i}",
                            "category": "key_finding"
                        },
                        {
                            "text": f"Key point {i}.2: Additional details about the subject matter",
                            "category": "key_finding"
                        },
                        {
                            "text": f"Key point {i}.3: Broader implications for topic {i}",
                            "category": "conclusion"
                        },
                    ],
                    "quotes": [],
                    "topics": ["Testing", f"Topic{i}"],
                    "summarization_date": "2025-01-04T12:00:00Z"
                }
            },
        )
        db_session.add(content)
    db_session.commit()
    
    # Get initial list - should show all as unread
    response = client.get("/")
    assert response.status_code == 200
    assert "Test Article 0" in response.text
    assert "Test Article 1" in response.text
    assert "Test Article 2" in response.text
    
    # Mark first article as read by visiting it
    response = client.get("/content/1")
    assert response.status_code == 200
    
    # Get session cookie
    session_cookie = None
    for cookie in response.cookies:
        if cookie == "news_app_session":
            session_cookie = response.cookies[cookie]
            break
    
    # Now check unread filter (default)
    response = client.get("/", cookies={"news_app_session": session_cookie})
    assert response.status_code == 200
    assert "Test Article 0" not in response.text  # Article 1 was read
    assert "Test Article 1" in response.text
    assert "Test Article 2" in response.text
    
    # Check all filter
    response = client.get("/?read_filter=all", cookies={"news_app_session": session_cookie})
    assert response.status_code == 200
    assert "Test Article 0" in response.text
    assert "Test Article 1" in response.text
    assert "Test Article 2" in response.text
    assert "(read)" in response.text  # Should show read indicator
    
    # Check read only filter
    response = client.get("/?read_filter=read", cookies={"news_app_session": session_cookie})
    assert response.status_code == 200
    assert "Test Article 0" in response.text  # Only read article
    assert "Test Article 1" not in response.text
    assert "Test Article 2" not in response.text


def test_content_detail_marks_as_read(
    client,
    db_session: Session
):
    """Test that viewing content detail marks it as read."""
    # Create test content
    content = Content(
        content_type="article",
        url="https://example.com/test",
        title="Test Article",
        status="completed",
        content_metadata={
                "summary": {
                    "title": "Test Article",
                    "overview": "This is a comprehensive test summary that contains detailed information about the content to meet the minimum length requirement for validation.",
                    "bullet_points": [
                        {
                            "text": "Key point 1: Important information about the topic",
                            "category": "key_finding"
                        },
                        {
                            "text": "Key point 2: Supporting evidence for the topic",
                            "category": "analysis"
                        },
                        {
                            "text": "Key point 3: Why this matters for readers",
                            "category": "conclusion"
                        },
                    ],
                    "quotes": [],
                    "topics": ["Testing"],
                    "summarization_date": "2025-01-04T12:00:00Z"
                }
        },
    )
    db_session.add(content)
    db_session.commit()
    db_session.refresh(content)
    
    # Initially no read status
    read_status = db_session.query(ContentReadStatus).first()
    assert read_status is None
    
    # Visit content detail
    response = client.get(f"/content/{content.id}")
    assert response.status_code == 200
    assert "Test Article" in response.text
    
    # Check that read status was created
    read_status = db_session.query(ContentReadStatus).first()
    assert read_status is not None
    assert read_status.content_id == content.id
    assert read_status.session_id is not None


def test_session_persistence(
    client,
    db_session: Session
):
    """Test that session cookies persist across requests."""
    # Create test content
    content = Content(
        content_type="article",
        url="https://example.com/test",
        title="Test Article",
        status="completed",
        content_metadata={
                "summary": {
                    "title": "Test Article",
                    "overview": "This is a comprehensive test summary that contains detailed information about the content to meet the minimum length requirement for validation.",
                    "bullet_points": [
                        {
                            "text": "Key point 1: Important information about the topic",
                            "category": "key_finding"
                        },
                        {
                            "text": "Key point 2: Supporting evidence for the topic",
                            "category": "analysis"
                        },
                        {
                            "text": "Key point 3: Why this matters for readers",
                            "category": "conclusion"
                        },
                    ],
                    "quotes": [],
                    "topics": ["Testing"],
                    "summarization_date": "2025-01-04T12:00:00Z"
                }
        },
    )
    db_session.add(content)
    db_session.commit()
    db_session.refresh(content)
    
    # First request should create session
    response1 = client.get("/")
    session_cookie1 = response1.cookies.get("news_app_session")
    assert session_cookie1 is not None
    
    # Second request with same cookie should not create new session
    response2 = client.get("/", cookies={"news_app_session": session_cookie1})
    session_cookie2 = response2.cookies.get("news_app_session")
    assert session_cookie2 is None  # No new cookie set
    
    # Mark content as read
    response3 = client.get(f"/content/{content.id}", cookies={"news_app_session": session_cookie1})
    assert response3.status_code == 200
    
    # Verify read status persists
    response4 = client.get("/?read_filter=read", cookies={"news_app_session": session_cookie1})
    assert "Test Article" in response4.text


def test_news_content_rendering(client, db_session: Session):
    """Ensure news content displays aggregated items."""
    news_content = Content(
        content_type="news",
        url="https://example.com/news",
        title="Morning Digest",
        status="completed",
        is_aggregate=True,
        content_metadata={
            "platform": "twitter",
            "source": "twitter.com",
            "article": {
                "url": "https://example.com/news/primary",
                "title": "Primary Story",
            },
            "items": [
                {
                    "title": "Launch announcement",
                    "url": "https://twitter.com/example/status/1",
                    "summary": "Key highlight",
                }
            ],
            "rendered_markdown": "- [Launch announcement](https://twitter.com/example/status/1)",
            "excerpt": "1 updates curated from twitter",
        },
    )

    db_session.add(news_content)
    db_session.commit()
    db_session.refresh(news_content)

    list_response = client.get("/")
    assert list_response.status_code == 200
    assert "Morning Digest" in list_response.text
    assert "Launch announcement" in list_response.text

    detail_response = client.get(f"/content/{news_content.id}")
    assert detail_response.status_code == 200
    assert "News Items" in detail_response.text
    assert "Launch announcement" in detail_response.text


def test_unprocessed_news_excluded_from_list(client, db_session: Session):
    """News items without summaries should remain hidden until summarization completes."""

    pending_news = Content(
        content_type="news",
        url="https://www.techmeme.com/cluster/pending",
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
                "url": "https://www.techmeme.com/cluster/pending",
            },
        },
    )

    completed_news = Content(
        content_type="news",
        url="https://www.techmeme.com/cluster/processed",
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
                "url": "https://www.techmeme.com/cluster/processed",
            },
            "summary": {
                "title": "Processed Digest",
                "article_url": "https://processed.com/story",
                "key_points": [
                    "Headline takeaway",
                    "Secondary insight",
                ],
                "summary": "Short overview of the processed item.",
                "classification": "to_read",
                "summarization_date": "2025-09-23T00:00:00Z",
            },
        },
    )

    db_session.add_all([pending_news, completed_news])
    db_session.commit()

    response = client.get("/?content_type=news&read_filter=all")
    assert response.status_code == 200
    page = response.text

    assert "Processed Digest" in page
    assert "Pending Article" not in page
    assert "Pending Cluster" not in page
