## Purpose
Encapsulates a synchronous, resilient HTTP client used across scrapers and processing strategies, handling retries, redirects, and SSL edge cases.

## Key Files
- `app/http_client/robust_http_client.py` – `RobustHttpClient` that keeps an `httpx.Client` alive, logs requests, retries hostname variants on SSL hostname-mismatch errors, and wraps GET/HEAD with structured logging.
- `app/http_client/__init__.py` – package marker.

## Main Types/Interfaces
- `RobustHttpClient` with `get`, `head`, and `close` methods and internal retry logic for `_maybe_retry_hostname_mismatch`.

## Dependencies & Coupling
Wraps `httpx.Client` and pulls configuration from `app.core.settings`; used by `app.processing_strategies` and other download helpers needing consistent headers/timeouts.

## Refactor Opportunities
The client logs and manages retry logic inline; consider splitting the hostname-variant retry into a helper so non-GET callers (e.g., streaming video processors) can reuse it without duplicating `httpx` setup.

Reviewed files: 2
