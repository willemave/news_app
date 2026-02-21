## Purpose
Alternative coverage of `content_to_domain`/`domain_to_content`, focusing on round-trip fidelity for articles/podcasts and update scenarios.

## Test Coverage Focus
Assertions cover article/podcast conversion, metadata preservation, error message propagation, and the `domain_to_content` path that updates existing `Content` rows.

## Key Fixtures/Helpers
- `DBContent`/`ContentData` builders seeded with `HttpUrl`, statuses, and metadata.
- `datetime` instances to ensure timestamps are handled.

## Gaps or Brittleness
Only articles/podcasts are exercised; news aggregations and metadata normalization are not touched.
Refactor: Move builder boilerplate into helper functions and reuse across tests.

## Refactor Opportunities
Parameterize conversion scenarios so new content types can be added without copy/pasting entry data.

Reviewed files: 2
