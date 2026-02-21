## Purpose
Service-level coverage for LLM model selection, summarization control, transcription helpers, and queue management used by higher layers.

## Test Coverage Focus
`test_llm_models` ensures env-based resolution, `test_llm_summarization` exercises prompt truncation/retries, `test_openai_transcription` verifies file bridging and ffmpeg guardrails, and `test_queue` asserts enqueue/dequeue/completion/retry logic.

## Key Fixtures/Helpers
- `SimpleNamespace` settings stubs and `monkeypatch` for per-test config.
- `FakeAgent`/`FakeResult` helpers that replace actual LLM agents.
- `MagicMock` queue/processing task records for the queue service.

## Gaps or Brittleness
External API clients still mocked, so real audio uploads or LLM responses are never validated.
Refactor: Share the `SimpleNamespace` settings builder across these tests to ensure consistent environment simulation.

## Refactor Opportunities
Factor out the repeated response/agent builders so new behavior (e.g., streaming errors) can be added quickly.


Reviewed files: 5
