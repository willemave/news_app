## Purpose
Verifies the helper properties on ORM/data models that surface curated summaries to the UI.

## Test Coverage Focus
`test_content_short_summary` checks the fallback logic, and the other modules validate structured summaries for bullet-heavy, editorial narrative, and news-specific summaries.

## Key Fixtures/Helpers
- `ContentData`/`Content` builders with synthetic metadata.
- `_build_points` helper to generate repeated bullet-quote pairs in `test_long_bullets_summary.py`.
- Shared constants from `app.models.metadata` for statuses and categories.

## Gaps or Brittleness
No dynamic validation of `ContentData.topics` or integration with presenter helpers, so the properties are only validated in isolation.

## Refactor Opportunities
Group the structured-summary builders into fixtures so assertions about quotes/bullet points can be reused across tests.

Reviewed files: 4
