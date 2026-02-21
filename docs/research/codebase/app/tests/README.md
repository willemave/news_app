## Purpose
Houses the shared fixtures and a handful of sanity tests that prove the fixture loader, content helpers, and Atom feed parser import without hitting production services.

## Test Coverage Focus
`test_fixtures_example.py` exercises each fixture key and the database helper, while `test_atom_scraper.py` ensures `load_atom_feeds` handles missing/valid configs and registration with `ScraperRunner`.

## Key Fixtures/Helpers
- `db`, `db_session`, and `test_user` for authenticated endpoints.
- `content_samples`, `create_sample_content`, and sample selectors (`sample_article_long`, `sample_podcast`, etc.).
- `client`/`async_client` overrides that swap FastAPI dependencies for tests.

## Gaps or Brittleness
No runner-level coverage; the module only validates fixtures and a single scraper helper, so heavier integration is left to subdirectories.

## Refactor Opportunities
Extract helper assertions for fixture keys so new samples can be validated without duplicating `for field in required_fields` loops.

Reviewed files: 4
