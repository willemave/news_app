## Purpose
Reinforces the `RobustHttpClient` with more exhaustive coverage (HEAD, redirects, retries, headers, closures).

## Test Coverage Focus
Tests cover GET success/errors/redirects, HEAD requests, custom timeout/headers, request errors, and that the underlying `httpx.Client` is closed after use.

## Key Fixtures/Helpers
- `mock_settings` for timeout/User-Agent defaults.
- `mock_client` to patch `httpx.Client` and inspect `get`/`head` calls.
- Helpers that raise `HTTPStatusError` or `RequestError` on demand.

## Gaps or Brittleness
No coverage for streaming responses or asynchronous calls; focus stays on synchronous `get`/`head`.
Refactor: Share the repeated `_subscribe` pattern (mocking `httpx.Response` fields) via a small factory.

## Refactor Opportunities
Factor the `mock_response` builder out and reuse it across tests instead of duplicating status/header setup.

Reviewed files: 2
