## Purpose
Unit tests for the pipeline handlers/workers that run inside the task queue.

## Test Coverage Focus
Handlers for fetching discussions, processing content, analyzing URLs, routing summarization, syncing integrations, and task dispatch/retry are all covered via targeted scenarios plus the `SequentialTaskProcessor`/`TaskDispatcher` units.

## Key Fixtures/Helpers
- `db_session` plus `test_user` to seed content rows.
- `TaskEnvelope`/`TaskContext` builders that feed mocks into handlers.
- `monkeypatch` to stub registry/lookups, especially for `AnalyzedUrlHandler`, `SummarizeHandler`, and worker queues.

## Gaps or Brittleness
Most tests mock the queue/LLM services, so the actual flow through `QueueService` isn’t exercised, and only selective content types (news/podcast) are fuzzed.

## Refactor Opportunities
Centralize the context+task builder used in almost every handler test to avoid repeating the `TaskContext` construction logic.

Reviewed files: 11
