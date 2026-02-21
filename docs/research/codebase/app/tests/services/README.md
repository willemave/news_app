## Purpose
Gives service-layer logic a safety net: admin conversational agent, eval runner, analyzer, feed detection/discovery, queue, voice, onboarding, and LLM helpers all live here.

## Test Coverage Focus
Modules from `admin_conversational_agent` through `voice_session_manager` along with onboarding heuristics, feed detection/discovery, instruction links, and queue services are covered via targeted unit tests and `monkeypatch` spells.

## Key Fixtures/Helpers
- `db_session`, `test_user`, and `Content` seeds used in knowledge search, admin, and feed tests.
- `monkeypatch` to stub LLM agents/responses (`FakeAgent`, `DummyStrategy`, etc.).
- Service-specific helpers such as `build_dig_deeper_prompt`, `run_admin_eval` inputs, and `QueueService` mocks.

## Gaps or Brittleness
Almost every test mocks external LLMs, HTTP clients, or queue services, so real HTTP, queue timing, and voice streaming behavior aren’t validated.
Refactor: Introduce shared helper factories for fake LLM responses or `TaskContext` builders that multiple services reuse.

## Refactor Opportunities
Group the repeated `monkeypatch.setattr` calls for session retries and LLM results into fixtures/utilities to avoid drift when agents change.

Reviewed files: 41
