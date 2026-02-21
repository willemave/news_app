## Purpose
Ensures scraper config loaders and error-metric counters handle missing files gracefully.

## Test Coverage Focus
`test_config_loaders` covers Substack/Reddit/podcast config discovery, environment overrides, and warning deduplication, while metrics are asserted via `get_scraper_metrics`.

## Key Fixtures/Helpers
- `monkeypatch` + `tmp_path` to create temporary configs.
- `caplog` to verify warning deduplication.
- Custom call to `get_scraper_metrics`/`reset_scraper_metrics` to inspect counters.

## Gaps or Brittleness
No live scraping; only config parsing.
Refactor: Could export a helper that writes sample configs so new scrapers reuse the same pattern.

## Refactor Opportunities
Move the repeated env tweaks and metrics resets into fixtures so new scraper config loaders can piggyback on the same scaffolding.

Reviewed files: 6
