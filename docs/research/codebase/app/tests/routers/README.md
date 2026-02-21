## Purpose
Exposes admin, API, and voice endpoints to confirm authentication, admin tooling, and websocket flows behave as expected.

## Test Coverage Focus
Includes admin conversational access redirects/health, dashboard status readouts, evaluators, onboarding lane preview, voice websocket flows (general and dictate-summary), plus admin router health.

## Key Fixtures/Helpers
- `client`/`TestClient` with `test_user`.
- `monkeypatch` overrides for `require_admin`, `build_health_flags`, `VoiceConversationOrchestrator`, etc.
- Cookies/auth tokens via `auth.admin_sessions` and `create_access_token` for TLS-protected routes.

## Gaps or Brittleness
Some dashboard tests are still skipped because `AsyncResponseStream` misfires, and most voice router tests mock the orchestrator rather than issuing real audio frames.

## Refactor Opportunities
Extract shared helpers for installing/removing the `require_admin` override and for streaming websocket events to reduce noise in each test file.

Reviewed files: 28
