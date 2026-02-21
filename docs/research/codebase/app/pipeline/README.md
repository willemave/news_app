## Purpose
Hosts the sequential worker infrastructure that dequeues `ProcessingTask` rows, routes them through handlers, and reconciles database checkout/checkin semantics.

## Key Files
- `app/pipeline/checkout.py` – `CheckoutManager` that claims, releases, and stats availability of `app.models.schema.Content` rows so workers avoid conflicts.
- `app/pipeline/sequential_task_processor.py` – long-running `SequentialTaskProcessor` that builds all task handlers, listens to shutdown signals, and pumps `QueueService` tasks through `TaskDispatcher` with Langfuse tracing.
- `app/pipeline/dispatcher.py` – simple dispatcher mapping `TaskType` to `TaskHandler` implementations.
- `app/pipeline/task_models.py` – `TaskEnvelope` and `TaskResult` Pydantic models used for handler replies.
- `app/pipeline/task_context.py`, `task_handler.py`, and `worker.py` – shared context, handler protocol, and the legacy `ContentWorker` that delegates to strategies, HTTP helpers, and LLM summarizers.
- `app/pipeline/podcast_workers.py` – specialized download/transcribe helpers for podcasts (yt-dlp, Whisper, queue dispatch).

## Main Types/Interfaces
- `CheckoutManager`, `get_checkout_manager()` for transactional claiming.
- `SequentialTaskProcessor` and `TaskDispatcher` for orchestrating handler execution.
- `TaskContext` bundling queue/LLM/db dependencies, plus `TaskEnvelope`/`TaskResult` for structured handler contracts.
- `ContentWorker` with platform-specific logic (strategies, feed detection, queue jag) used by `ProcessContentHandler`.

## Dependencies & Coupling
Tightly coupled to `app.services.queue.QueueService`, `app.services.llm_summarization`, `app.services.http`, `app.services.image_generation`, and the handler modules under `app.pipeline.handlers`. Langfuse tracing and settings form part of the context.

## Refactor Opportunities
- `SequentialTaskProcessor.run` mixes signal handling, backoff, and shutdown logic; the loop could be factored into smaller helpers to ease testing.
- `ContentWorker.process_content` still handles numerous content-type-specific branches; consider delegating more to the strategy registry to reduce branching.

Reviewed files: 9
