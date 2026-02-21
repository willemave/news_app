## Purpose
Top-level entry point that re-exports the fixtures from `app/tests` so external suites can reuse them without importing deep paths.

## Test Coverage Focus
`tests/conftest.py` simply prepends the app directory to `sys.path` and re-exports the shared fixtures from `app/tests/conftest.py`.

## Key Fixtures/Helpers
- The re-exported fixture list (`content_samples`, `sample_article_long`, etc.).
- No additional helpers beyond path surgery.

## Gaps or Brittleness
No tests live directly under `tests/`, so this folder’s observation is purely infrastructural.
Refactor: Remove the redundant `sys.path` insert if the project adopts a proper editable install.

## Refactor Opportunities
Document this bridging layer so maintainers know it only exists to expose shared fixtures to legacy paths.

Reviewed files: 1
