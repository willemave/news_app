## Purpose
Verifies the `RobustHttpClient` helper’s hostname-mismatch retry logic in isolation.

## Test Coverage Focus
`test_robust_http_client.py` fakes `_get_client` and asserts `_maybe_retry_hostname_mismatch` retries from `www.` to bare host paths and returns the stub response.

## Key Fixtures/Helpers
- `_StubClient` returning a canned `httpx.Response`.
- Direct assignment of `_get_client` to avoid the real pool.
- `httpx.Response` objects with populated `history`/`url` fields used in assertions.

## Gaps or Brittleness
No coverage for actual TLS errors, redirects, or `HEAD` requests; only the specific hostname fallback branch is exercised.

## Refactor Opportunities
Wrap the repeated stub setup in a fixture or helper so future branches (timeouts, retries) can be added without repeating client patching.

Reviewed files: 1
