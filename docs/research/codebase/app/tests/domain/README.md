## Purpose
Ensures the domain converter keeps news metadata, summaries, and classification in sync with the ORM models.

## Test Coverage Focus
A pair of assertions about news metadata preserve article URLs and summary metadata plus the `SUMMARY_KIND`/`VERSION` constants after conversion.

## Key Fixtures/Helpers
- `_build_news_content` helper that seeds a `Content` row with platform, source, and metadata.
- `content_to_domain` call providers used in both test paths.

## Gaps or Brittleness
Podcast/video conversions are absent, and there is no inverse test for `domain_to_content` in this folder (that lives in `tests/domain`).

## Refactor Opportunities
Parametrize `content_to_domain` assertions to cover at least two summary kinds instead of hardcoding one metadata blob.

Reviewed files: 1
