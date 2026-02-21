## Purpose
Unit tests for workers and summarization handlers, plus fixture-driven validations for pipeline-ready records.

## Test Coverage Focus
`ContentWorker` unit tests cover strategy discovery, non-retryable errors, and queue enqueues, while `SequentialTaskProcessor`, `SummarizeHandler`, and `summarization_metadata_update` ensure pipeline transitions and metadata updates remain stable. The `test_worker_with_fixtures` module double-checks the actual fixture structure.

## Key Fixtures/Helpers
- `mock_dependencies` fixture that patches `get_db`, `queue`, `strategy_registry`, and podcast workers.
- `TaskContext` builder used in `test_summarization_metadata_update`.
- The sample fixtures imported from `app/tests`.

## Gaps or Brittleness
Mocks still dominate, so the actual queue backoff/retry behavior is not exercised; only the handler logic is touched.
Refactor: Split the `mock_dependencies` fixture across more fine-grained scopes to avoid overly broad patches.

## Refactor Opportunities
Factor the common `worker.process_content` expectations into helper assertions that confirm queue enqueues and metadata updates in one place.

Reviewed files: 5
