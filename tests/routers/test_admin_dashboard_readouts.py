"""Tests for expanded admin dashboard readouts."""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.deps import require_admin
from app.main import app
from app.models.schema import Content, EventLog, OnboardingDiscoveryRun, ProcessingTask
from app.models.user import User


def test_admin_dashboard_shows_operational_readouts(client, db_session, test_user) -> None:
    """Dashboard should render queue, scraper, and user lifecycle readout sections."""

    def override_require_admin():
        return test_user

    app.dependency_overrides[require_admin] = override_require_admin
    try:
        now = datetime.now(UTC)

        other_user = User(
            apple_id="test_apple_other",
            email="other@example.com",
            full_name="Other User",
            is_active=False,
        )
        db_session.add(other_user)
        db_session.flush()

        db_session.add(
            Content(
                content_type="article",
                url="https://example.com/missing-summary",
                title="Missing Summary",
                source="test",
                status="failed",
                error_message="summary generation failed",
                content_metadata={},
            )
        )

        db_session.add_all(
            [
                ProcessingTask(
                    task_type="analyze_url",
                    queue_name="content",
                    status="pending",
                    created_at=now,
                ),
                ProcessingTask(
                    task_type="onboarding_discover",
                    queue_name="onboarding",
                    status="processing",
                    created_at=now,
                ),
                ProcessingTask(
                    task_type="summarize",
                    queue_name="content",
                    status="failed",
                    created_at=now,
                    completed_at=now,
                    error_message="Timeout while calling model",
                ),
            ]
        )

        db_session.add_all(
            [
                EventLog(
                    event_type="scraper_run",
                    event_name="all",
                    status="started",
                    data={},
                    created_at=now,
                ),
                EventLog(
                    event_type="scraper_stats",
                    event_name="hackernews",
                    status="completed",
                    data={"scraped": 12, "saved": 8, "duplicates": 2, "errors": 1},
                    created_at=now,
                ),
                EventLog(
                    event_type="scraper_error",
                    event_name="reddit",
                    status="failed",
                    data={"error": "boom"},
                    created_at=now,
                ),
                EventLog(
                    event_type="queue_watchdog_run",
                    event_name="queue_recovery",
                    status="completed",
                    data={
                        "total_touched": 3,
                        "moved_transcribe": 1,
                        "requeued_transcribe": 1,
                        "requeued_process_content": 1,
                    },
                    created_at=now,
                ),
                EventLog(
                    event_type="queue_watchdog_action",
                    event_name="move_transcribe",
                    status="completed",
                    data={"touched_count": 1},
                    created_at=now,
                ),
                EventLog(
                    event_type="queue_watchdog_alert",
                    event_name="slack",
                    status="sent",
                    data={"total_touched": 3},
                    created_at=now,
                ),
            ]
        )

        db_session.add_all(
            [
                OnboardingDiscoveryRun(
                    user_id=test_user.id,
                    status="completed",
                    topic_summary="AI news",
                    inferred_topics=["ai"],
                    lane_summary="done",
                    created_at=now,
                    completed_at=now,
                ),
                OnboardingDiscoveryRun(
                    user_id=other_user.id,
                    status="failed",
                    topic_summary="security",
                    inferred_topics=["security"],
                    lane_summary="failed",
                    created_at=now,
                ),
            ]
        )
        db_session.commit()

        response = client.get("/admin/")
        assert response.status_code == 200
        body = response.text

        assert "Queue Status" in body
        assert "Task Phases" in body
        assert "Recent Failures (24h)" in body
        assert "Scraper Health (24h)" in body
        assert "Queue Watchdog (24h)" in body
        assert "User Lifecycle" in body

        assert "onboarding" in body
        assert "hackernews" in body
        assert "reddit" in body
        assert "Tutorial Done" in body
    finally:
        app.dependency_overrides.pop(require_admin, None)
