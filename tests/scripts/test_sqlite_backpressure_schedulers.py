"""Tests for SQLite backpressure behavior in cron scheduler scripts."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import scripts.run_news_digests as run_news_digests
import scripts.run_scrapers as run_scrapers


class _FakeScraperRunner:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def list_scrapers(self) -> list[str]:
        return ["HackerNews", "Reddit"]

    def run_scraper_with_stats(self, scraper_name: str) -> SimpleNamespace:
        self.calls.append(scraper_name)
        return SimpleNamespace(scraped=2, saved=1, duplicates=1, errors=0)


def test_run_scrapers_skips_when_backpressure_is_unhealthy(monkeypatch) -> None:
    """Scrapers should skip the cron run when the queue backlog is unhealthy."""
    runner = _FakeScraperRunner()
    monkeypatch.setattr(
        run_scrapers.argparse.ArgumentParser,
        "parse_args",
        lambda self: SimpleNamespace(scrapers=None, debug=False, show_stats=False),
    )
    monkeypatch.setattr(run_scrapers, "setup_logging", lambda level="INFO": None)
    monkeypatch.setattr(run_scrapers, "init_db", lambda: None)
    monkeypatch.setattr(run_scrapers, "ScraperRunner", lambda: runner)
    monkeypatch.setattr(
        run_scrapers,
        "get_queue_service",
        lambda: SimpleNamespace(
            get_backpressure_status=lambda: {
                "should_throttle": True,
                "reasons": ["content_queue_backlog"],
            }
        ),
    )

    run_scrapers.main()

    assert runner.calls == []


def test_run_scrapers_stops_after_current_scraper_when_backpressure_crosses_threshold(
    monkeypatch,
) -> None:
    """Scrapers should stop before starting the next scraper once backlog turns unhealthy."""
    runner = _FakeScraperRunner()
    backpressure_checks = iter(
        [
            {"should_throttle": False, "reasons": []},
            {"should_throttle": True, "reasons": ["process_news_item_backlog"]},
        ]
    )
    monkeypatch.setattr(
        run_scrapers.argparse.ArgumentParser,
        "parse_args",
        lambda self: SimpleNamespace(scrapers=None, debug=False, show_stats=False),
    )
    monkeypatch.setattr(run_scrapers, "setup_logging", lambda level="INFO": None)
    monkeypatch.setattr(run_scrapers, "init_db", lambda: None)
    monkeypatch.setattr(run_scrapers, "ScraperRunner", lambda: runner)
    monkeypatch.setattr(
        run_scrapers,
        "get_queue_service",
        lambda: SimpleNamespace(get_backpressure_status=lambda: next(backpressure_checks)),
    )

    run_scrapers.main()

    assert runner.calls == ["HackerNews"]


def test_run_news_digests_skips_when_backpressure_is_unhealthy(monkeypatch) -> None:
    """News digest enqueue should skip entirely when the queue backlog is unhealthy."""
    monkeypatch.setattr(
        run_news_digests,
        "_parse_args",
        lambda: SimpleNamespace(user_ids=None, now_utc=None, dry_run=False),
    )
    monkeypatch.setattr(run_news_digests, "setup_logging", lambda: None)
    monkeypatch.setattr(
        run_news_digests,
        "get_queue_service",
        lambda: SimpleNamespace(
            get_backpressure_status=lambda: {
                "should_throttle": True,
                "reasons": ["content_queue_backlog"],
            }
        ),
    )

    @contextmanager
    def _unexpected_db():
        raise AssertionError("digest scheduler should not open the database when throttled")
        yield

    monkeypatch.setattr(run_news_digests, "get_db", _unexpected_db)

    run_news_digests.main()


def test_run_news_digests_enqueues_when_backpressure_is_healthy(monkeypatch) -> None:
    """News digest enqueue should proceed normally when backlog is healthy."""
    monkeypatch.setattr(
        run_news_digests,
        "_parse_args",
        lambda: SimpleNamespace(user_ids=None, now_utc=None, dry_run=False),
    )
    monkeypatch.setattr(run_news_digests, "setup_logging", lambda: None)
    monkeypatch.setattr(
        run_news_digests,
        "get_queue_service",
        lambda: SimpleNamespace(
            get_backpressure_status=lambda: {"should_throttle": False, "reasons": []}
        ),
    )

    enqueued_user_ids: list[int] = []

    class _FakeQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def yield_per(self, _chunk_size: int):
            return iter([SimpleNamespace(id=7)])

    class _FakeDB:
        def query(self, _model):
            return _FakeQuery()

    @contextmanager
    def _fake_db():
        yield _FakeDB()

    monkeypatch.setattr(run_news_digests, "get_db", _fake_db)
    monkeypatch.setattr(
        run_news_digests,
        "get_news_digest_trigger_decision",
        lambda _db, user, now_utc: SimpleNamespace(
            should_generate=True,
            trigger_reason="scheduled",
            candidate_count=12,
            provisional_group_count=4,
        ),
    )
    monkeypatch.setattr(
        run_news_digests,
        "enqueue_news_digest_generation",
        lambda _db, user_id, trigger_reason: enqueued_user_ids.append(user_id) or 99,
    )

    run_news_digests.main()

    assert enqueued_user_ids == [7]
