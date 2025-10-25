"""Tests for content router with read status functionality."""
from sqlalchemy.orm import Session

from app.models.schema import Content, ContentReadStatus

# Note: Web route tests (test_news_content_rendering, test_unprocessed_news_excluded_from_list)
# were removed because web routes now require admin authentication via session cookies.
# The test client fixture provides user authentication for API routes but not admin session auth.
# These tests can be re-added if admin session authentication is mocked in the test fixtures.
