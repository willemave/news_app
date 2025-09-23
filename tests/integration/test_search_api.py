import os
from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import get_db_session
from app.models.schema import Base, Content

# Import router and models without importing app.main (avoids env/settings side effects)
from app.routers import api_content


@pytest.fixture(scope="module")
def test_app() -> Generator[FastAPI]:
    # Set a safe DATABASE_URL for any code that might read it (defensive)
    os.environ.setdefault("DATABASE_URL", "sqlite://")

    app = FastAPI()
    app.include_router(api_content.router, prefix="/api/content")
    yield app


@pytest.fixture(scope="module")
def db_session() -> Generator[Session]:
    # In-memory SQLite shared across the module
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="module")
def client(test_app: FastAPI, db_session: Session) -> Generator[TestClient]:
    # Override DB dependency for router endpoints
    def _get_db_session_override() -> Session:
        return db_session

    test_app.dependency_overrides[get_db_session] = _get_db_session_override
    with TestClient(test_app) as c:
        yield c


def seed_content(db: Session):
    items = [
        Content(
            content_type="article",
            url="https://example.com/ai-article",
            title="Understanding AI in 2025",
            source="Tech Blog",
            platform="substack",
            content_metadata={
                "summary": {
                    "title": "Understanding AI in 2025",
                    "overview": "Deep dive into artificial intelligence",
                }
            },
        ),
        Content(
            content_type="podcast",
            url="https://example.com/podcast-ep1",
            title="Tech Talk Episode 1",
            source="Tech Podcast",
            platform="youtube",
            content_metadata={
                "transcript": "Today we discuss machine learning and AI systems",
                "summary": {
                    "title": "Tech Talk Episode 1",
                    "overview": "Discussion about machine learning",
                },
            },
        ),
        # Skipped item should not appear in results
        Content(
            content_type="article",
            url="https://example.com/skip-me",
            title="Skip This",
            source="Misc",
            classification="skip",
            content_metadata={
                "summary": {"title": "Skip This", "overview": "Not relevant"}
            },
        ),
    ]
    for it in items:
        db.add(it)
    db.commit()


class TestSearchAPI:
    def test_search_basic(self, client: TestClient, db_session: Session):
        seed_content(db_session)
        r = client.get("/api/content/search", params={"q": "AI"})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        # Ensure 'skip' item isn't present
        for c in data["contents"]:
            assert c["title"] != "Skip This"

    def test_search_type_filter(self, client: TestClient):
        r = client.get("/api/content/search", params={"q": "tech", "type": "article"})
        assert r.status_code == 200
        data = r.json()
        for c in data["contents"]:
            assert c["content_type"] == "article"

    def test_search_pagination(self, client: TestClient):
        r = client.get("/api/content/search", params={"q": "tech", "limit": 1, "offset": 0})
        assert r.status_code == 200
        data = r.json()
        assert len(data["contents"]) <= 1

    def test_search_validation(self, client: TestClient):
        # Too short
        r = client.get("/api/content/search", params={"q": "a"})
        assert r.status_code == 422
        # Invalid type
        r = client.get("/api/content/search", params={"q": "ai", "type": "video"})
        assert r.status_code == 422
