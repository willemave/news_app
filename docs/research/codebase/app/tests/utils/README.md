## Purpose
Asserts that summary-kind inference returns the right enum for different summary payload shapes.

## Test Coverage Focus
Multiple permutations of summary data (`interleaved`, `news_digest`, `long_structured`, etc.) confirm `infer_summary_kind_version` emits the correct tuple.

## Key Fixtures/Helpers
- Direct call patterns; there are no additional fixtures beyond constants from `app.constants`.
- Enum constants such as `SUMMARY_KIND_LONG_BULLETS` to keep assertions readable.

## Gaps or Brittleness
No tests for fallbacks when both kind and version are missing while `summary_type` is unknown.
Refactor: Parametrize the kind/version matrix to minimize repeated `result ==` checks.

## Refactor Opportunities
Use a data-driven table so future kinds do not require a brand-new test function.

Reviewed files: 1
