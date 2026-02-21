## Purpose
Targets the refactored API content router modules that wrap listing, detail, chat, and stats endpoints.

## Test Coverage Focus
Tests chat URL prompt composition, subscribe eligibility, discussion payloads, stats counters, and discussion lookups, with some reuse of fixtures from the root conftest.

## Key Fixtures/Helpers
- `client`, `db_session`, and `test_user` for authenticated calls.
- `create_sample_content` plus `sample_*` fixtures for content detail flows.
- Custom helper `_get_display_title` in `test_content_detail.py` to mirror the actual prompt builder.

## Gaps or Brittleness
Most tests assume the worker queue has already injected metadata; there is no coverage of API validation errors beyond the happy path.
Refactor: Parameterize enumerations like `TaskType` and test that the `stats` endpoints reject invalid filters.

## Refactor Opportunities
Parameterize repeated query sets (e.g., stats calculations) so the same data geometry can be reused when new content types are added.

Reviewed files: 6
