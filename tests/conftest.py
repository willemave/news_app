"""Test configuration and fixtures."""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.schema import Base, Content
from app.models.user import User


@pytest.fixture
def db():
    """Create test database session (for authentication tests)."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_db():
    """Create a test database."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(test_db):
    """Create a test database session."""
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_user(db_session):
    """Create a test user for authentication."""
    user = User(
        apple_id="test_apple_id_12345",
        email="test@example.com",
        full_name="Test User",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def client(db_session, test_user):
    """Create a test client with database and auth overrides."""
    from app.core.db import get_db_session, get_readonly_db_session
    from app.core.deps import get_current_user

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_current_user():
        return test_user

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_readonly_db_session] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def async_client(db_session, test_user):
    """Create an async test client with database and auth overrides."""
    from app.core.db import get_db_session, get_readonly_db_session
    from app.core.deps import get_current_user

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_current_user():
        return test_user

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_readonly_db_session] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    ac = AsyncClient(app=app, base_url="http://test")
    yield ac

    app.dependency_overrides.clear()


# Content fixtures
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(fixture_name: str) -> Dict[str, Any]:
    """Load a fixture from the fixtures directory.

    Args:
        fixture_name: Name of the fixture file (without .json extension)

    Returns:
        Parsed JSON data from the fixture file
    """
    fixture_path = FIXTURES_DIR / f"{fixture_name}.json"
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def content_samples() -> Dict[str, Dict[str, Any]]:
    """Load all content samples from fixtures.

    Returns:
        Dictionary with keys:
        - article_long_form: Long-form article with full summary
        - article_short_technical: Short technical article
        - podcast_interview: Podcast episode with transcript and summary
        - raw_content_unprocessed: Unprocessed article (status='new')
        - podcast_raw_transcript: Podcast with transcript but no summary
    """
    return load_fixture("content_samples")


@pytest.fixture
def sample_article_long(content_samples: Dict[str, Any]) -> Dict[str, Any]:
    """Get a long-form article sample."""
    return content_samples["article_long_form"]


@pytest.fixture
def sample_article_short(content_samples: Dict[str, Any]) -> Dict[str, Any]:
    """Get a short technical article sample."""
    return content_samples["article_short_technical"]


@pytest.fixture
def sample_podcast(content_samples: Dict[str, Any]) -> Dict[str, Any]:
    """Get a podcast episode sample with full processing."""
    return content_samples["podcast_interview"]


@pytest.fixture
def sample_unprocessed_article(content_samples: Dict[str, Any]) -> Dict[str, Any]:
    """Get an unprocessed article (for testing processing pipeline)."""
    return content_samples["raw_content_unprocessed"]


@pytest.fixture
def sample_unprocessed_podcast(content_samples: Dict[str, Any]) -> Dict[str, Any]:
    """Get a podcast with transcript but no summary (for testing summarization)."""
    return content_samples["podcast_raw_transcript"]


def _parse_datetime(date_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO format date string to datetime object.

    Args:
        date_str: ISO format date string (e.g., "2025-06-21T15:51:43")

    Returns:
        datetime object or None if date_str is None
    """
    if not date_str:
        return None

    try:
        # Try parsing with microseconds
        return datetime.fromisoformat(date_str)
    except ValueError:
        # Try parsing without microseconds
        try:
            return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            # Try parsing date only
            return datetime.strptime(date_str, "%Y-%m-%d")


def create_content_from_fixture(fixture_data: Dict[str, Any]) -> Content:
    """Create a Content model instance from fixture data.

    Args:
        fixture_data: Dictionary containing content data from fixture

    Returns:
        Content model instance ready to be added to database
    """
    return Content(
        id=fixture_data.get("id"),
        content_type=fixture_data["content_type"],
        url=fixture_data["url"],
        title=fixture_data["title"],
        source=fixture_data["source"],
        status=fixture_data["status"],
        platform=fixture_data.get("platform"),
        classification=fixture_data.get("classification"),
        publication_date=_parse_datetime(fixture_data.get("publication_date")),
        content_metadata=fixture_data.get("content_metadata", {}),
    )


@pytest.fixture
def create_sample_content(db_session):
    """Factory fixture to create content from samples in the database.

    Usage:
        content = create_sample_content(sample_article_long)
    """
    def _create(fixture_data: Dict[str, Any]) -> Content:
        content = create_content_from_fixture(fixture_data)
        db_session.add(content)
        db_session.commit()
        db_session.refresh(content)
        return content

    return _create
