## Purpose
Validates `app.models.metadata` Pydantic schemas to prevent drift in structured summary constraints.

## Test Coverage Focus
`StructuredSummary`, `ArticleMetadata`, and `PodcastMetadata` are exercised for boundary cases: minimum bullet counts, quote size, topic lists, invalid `content_type`, and metadata type requirements.

## Key Fixtures/Helpers
- `SummaryBulletPoint`, `ContentQuote` builders.
- `datetime.now(UTC)` to prove date fields accept timezone-aware values.
- `pytest.raises` around `ValidationError` to assert failure paths.

## Gaps or Brittleness
Does not cover new schema additions such as `NewsSummary` customization or transcript-specific fields.
Refactor: Parameterize repeated `with pytest.raises(ValidationError)` blocks to document the failure reason inside the helper.

## Refactor Opportunities
Wrap repeated invalid payload generations in a data-driven table so new schema rules are easy to add.

Reviewed files: 2
