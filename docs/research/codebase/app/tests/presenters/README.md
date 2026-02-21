## Purpose
Keeps presenter helpers honest by checking primary topic selection and top-comment extraction in the API responses.

## Test Coverage Focus
`build_content_summary_response` is exercised for topic fallbacks (news uses platform, blank topic -> null) and for metadata-derived `top_comment` filtering.

## Key Fixtures/Helpers
- `_make_domain_mock`/`_make_content_row` that craft minimal `ContentData` + ORM stubs.
- Magic mocks for metadata to test `primary_topic` heuristics.

## Gaps or Brittleness
Does not cover every branch in `build_content_summary_response`, such as `structured_summary` vs. `summary` payloads for long-form content.

## Refactor Opportunities
Parametrize the domain mock to cover more combinations rather than manual helper tweaks inside each test.

Reviewed files: 2
