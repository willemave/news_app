## Purpose
Validates the core utilities that safeguard authentication, settings, and structured logging before any router or worker code runs.

## Test Coverage Focus
Covers admin password verification, FastAPI dependency guards (`get_current_user`, `require_admin`), logging helpers (redaction, JSONL payloads, filters), and settings surface (storage paths, ElevenLabs alias, PDF model validation).

## Key Fixtures/Helpers
- `monkeypatch` to swap environment variables and dependency overrides.
- `get_settings.cache_clear()` boilerplate spread across tests.
- ad-hoc helpers that build `LogRecord`s for structured payload assertions.

## Gaps or Brittleness
No coverage for `lifespan` hooks, `pydantic-settings` validation cascades beyond the named fields, or token timers in `verify_token`.

## Refactor Opportunities
Wrap repeated `get_settings.cache_clear()`/`monkeypatch.delenv` patterns into fixtures so new enums follow the same reset discipline.

Reviewed files: 9
