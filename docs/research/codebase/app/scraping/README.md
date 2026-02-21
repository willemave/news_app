## Purpose
Implements the legacy scraping flows (RSS, social feeds, podcasts, news aggregators) that seed `ProcessingTask` rows for further enrichment.

## Key Files
- `runner.py` – coordinates scraper runs, tracks stats, and writes `ScraperStats` data.
- `base.py`, `rss_helpers.py` – shared helpers for HTTP fetching, normalization, and feed source heuristics.
- Platform-specific scrapers (`atom_unified.py`, `hackernews_unified.py`, `podcast_unified.py`, `reddit_unified.py`, `substack_unified.py`, `techmeme_unified.py`, `twitter_unified.py`, `youtube_unified.py`) that harvest items and map them to `ProcessingTask` entries.

## Main Types/Interfaces
- `ScraperStats` dataclass for run metrics and `runner` utilities that invoke each unified scraper.
- Each scraper exposes a `run()`-like entry point that emits normalized content entries and uses `app.services.queue.QueueService` to enqueue tasks.

## Dependencies & Coupling
Scrapers depend on `httpx`, `feedparser`, `app.services.queue`, and sometimes `app.services.*` helpers; they use the shared RSS helpers for feed resolution and rely on `app.models.scraper_runs.ScraperStats` for telemetry.

## Refactor Opportunities
The unified scrapers have platform-specific logic inline and share little infrastructure; collapsing them into a shared `BaseScraper` with configurable parsers could simplify onboarding new sources. The runner could also expose more metrics (errors per platform) to improve dashboard visibility.

Reviewed files: 12
