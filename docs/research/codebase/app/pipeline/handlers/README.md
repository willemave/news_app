## Purpose
Houses the `TaskHandler` implementations that encapsulate each queued processing phase (scrape → analyze → process → summarize → generate image, etc.) so the sequential processor can keep a stable dispatch map.

## Key Files
- `analyze_url.py`, `scrape.py` – initial ingestion handlers that classify URLs, detect feeds, subscribe users, and enqueue downstream tasks.
- `process_content.py`, `download_audio.py`, `transcribe.py` – workers that invoke `ContentWorker`, podcast download helpers, Whisper, and strategy-based content extraction.
- `summarize.py`, `generate_image.py`, `fetch_discussion.py` – handlers that call LLM summarizers, image generation services, and discussion crawlers respectively.
- `discover_feeds.py`, `onboarding_discover.py`, `dig_deeper.py`, `sync_integration.py` – specialized flows tied to discovery lanes, onboarding, dig-deeper chats, and integration synchronization.

## Main Types/Interfaces
Each module exposes a class with `task_type: TaskType` and `handle(self, task, context) -> TaskResult`, following the `TaskHandler` protocol defined in `app/pipeline/task_handler.py`.

## Dependencies & Coupling
Handlers tear down business logic via `app.services.*` (queue, http, llm, feed detection, image generation, etc.), `app.pipeline.worker.ContentWorker`, and database models (e.g., `app.models.schema.Content`). `TaskContext` and Langfuse tracing are threaded into every handler call.

## Refactor Opportunities
Error handling and logging are repeated across handlers, especially around missing `content_id`; consolidating that validation plus a shared retry policy would reduce duplication. Some handlers (e.g., `analyze_url`) are still very large—splitting flows like `TwitterShareFlow` into service helpers would make the files easier to reason about.

Reviewed files: 13
