## Purpose
Tests for the suite of unified scrapers (HN, podcast, Substack, Techmeme) that keep feeds aligned before pipeline ingestion.

## Test Coverage Focus
Each scraper test module validates corner cases like duplicate URLs, encoding overrides, limit enforcement, audio extraction, and aggregator normalization against real metadata dictionaries.

## Key Fixtures/Helpers
- `feedparser`/`MagicMock` entries for feed data.
- `mock_db_session`, `mock_queue_service`, and `PodcastUnifiedScraper` patches.
- `pytest.mark.parametrize` for repeated limit and status checks.

## Gaps or Brittleness
No live HTTP requests or Playwright interactions; the tests trust the feedparser output remains structured.
Refactor: Centralize the stub feed entries so new scraper tests reuse the same `feedparser` DSL.

## Refactor Opportunities
Create helper functions that wrap the `feedparser` mocks and return canonical entries to reduce duplication.

Reviewed files: 6
