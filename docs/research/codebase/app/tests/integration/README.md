## Purpose
Integration smoke tests that prove FastAPI guards and conversion endpoints work with the real dependency graph.

## Test Coverage Focus
`test_auth_protected_endpoints` hits guarded APIs, `test_convert_workflow` exercises content conversion plus favorites, and `test_user_data_isolation` ensures favorites/read status are scoped per user.

## Key Fixtures/Helpers
- `client`/`TestClient` hitting `/api/...` endpoints.
- `db_session` plus `Content`/`User` rows for HTTP payloads.
- `create_access_token` to prove auth flows and `app.dependency_overrides` for user context.

## Gaps or Brittleness
Focuses on the happy path; it does not cover error scenarios (e.g., invalid content IDs) or async worker progress.

## Refactor Opportunities
Share a helper that installs the dependency overrides once per test to avoid repeating the try/finally pattern around `app.dependency_overrides.clear()`.

Reviewed files: 4
