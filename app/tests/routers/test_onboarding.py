from __future__ import annotations

from app.models.schema import UserScraperConfig
from app.services.queue import TaskType


def test_onboarding_complete_creates_configs(client, db_session, monkeypatch, test_user):
    calls: list[tuple[str, dict]] = []

    def fake_enqueue(self, task_type, content_id=None, payload=None):
        calls.append((task_type.value, payload or {}))
        return 42

    monkeypatch.setattr("app.services.onboarding.QueueService.enqueue", fake_enqueue)

    response = client.post(
        "/api/onboarding/complete",
        json={
            "selected_sources": [
                {
                    "suggestion_type": "substack",
                    "title": "Example Substack",
                    "feed_url": "https://example.substack.com/feed",
                },
                {
                    "suggestion_type": "podcast_rss",
                    "title": "Example Podcast",
                    "feed_url": "https://example.com/podcast/rss.xml",
                },
            ],
            "selected_subreddits": ["MachineLearning"],
            "profile_summary": "AI researcher and writer",
            "inferred_topics": ["AI", "ML"],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert data["task_id"] == 42

    configs = (
        db_session.query(UserScraperConfig)
        .filter(UserScraperConfig.user_id == test_user.id)
        .all()
    )
    assert len(configs) == 3
    assert any(config.scraper_type == "substack" for config in configs)
    assert any(config.scraper_type == "podcast_rss" for config in configs)
    assert any(config.scraper_type == "reddit" for config in configs)

    assert any(call[0] == TaskType.SCRAPE.value for call in calls)
    assert any(call[0] == TaskType.ONBOARDING_DISCOVER.value for call in calls)


def test_onboarding_tutorial_complete(client, db_session, test_user):
    response = client.post("/api/onboarding/tutorial-complete")
    assert response.status_code == 200
    assert response.json()["has_completed_new_user_tutorial"] is True

    db_session.refresh(test_user)
    assert test_user.has_completed_new_user_tutorial is True


def test_onboarding_fast_discover_defaults(client):
    response = client.post(
        "/api/onboarding/fast-discover",
        json={"profile_summary": "AI engineer", "inferred_topics": ["AI", "ML"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert "recommended_substacks" in data
    assert "recommended_pods" in data
    assert "recommended_subreddits" in data


def test_onboarding_profile_requires_interests(client, monkeypatch):
    def fake_build_profile(_payload):
        return {
            "profile_summary": "Summary",
            "inferred_topics": ["AI"],
            "candidate_sources": [],
        }

    monkeypatch.setattr("app.routers.api.onboarding.build_onboarding_profile", fake_build_profile)

    response = client.post(
        "/api/onboarding/profile",
        json={"first_name": "Ada", "interest_topics": []},
    )
    assert response.status_code == 422


def test_onboarding_parse_voice(client, monkeypatch):
    from types import SimpleNamespace

    def fake_get_basic_agent(_model, output_cls, _system_prompt):
        class FakeAgent:
            def run_sync(self, _prompt, model_settings=None):
                return SimpleNamespace(
                    data=output_cls(
                        first_name="Ada",
                        interest_topics=["AI", "AI", " climate tech "],
                        confidence=0.92,
                    )
                )

        return FakeAgent()

    monkeypatch.setattr("app.services.onboarding.get_basic_agent", fake_get_basic_agent)

    response = client.post(
        "/api/onboarding/parse-voice",
        json={"transcript": "I'm Ada and I like AI and climate tech."},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["first_name"] == "Ada"
    assert data["interest_topics"] == ["AI", "climate tech"]
    assert data["missing_fields"] == []
