## Purpose
Exercises the processing pipeline end to end with real content fixtures and the rewritten search router on an in-memory DB.

## Test Coverage Focus
`test_pipeline_integration.py` enqueues tasks, mocks HTTP/LLM/strategy dependencies, and validates `Content` status updates, while `test_search_api.py` mounts `api_content` into a FastAPI instance and validates query filters/validation.

## Key Fixtures/Helpers
- `setup_test_db` used to seed/clean `Content`/`ProcessingTask`.
- FastAPI `TestClient` plus dependency overrides for `get_readonly_db_session`/`get_current_user`.
- `QueueService`, `TaskEnvelope`, and mocking of HTTP/LLM services in the sequential processor.

## Gaps or Brittleness
Search integration focuses on `news`/`article` keywords; the pipeline tests still rely on monkeypatched resources.

## Refactor Opportunities
Extract the mocked HTTP/LLM registry into named fixtures to make the integration workflow easier to extend.

Reviewed files: 3
