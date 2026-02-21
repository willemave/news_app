## Purpose
Contains the domain services that orchestrate LLM analysis, queue management, image generation, feed detection, submissions, and integrations—the bulk of the business logic called from routers and pipeline handlers.

## Key Files
- `content_analyzer.py` – LLM-based URL analyzer with trafilatura/`httpx` fetching, platform detection, and instruction link extraction.
- `content_submission.py` – submission workflow helpers that normalize URLs, deduplicate existing content, and enqueue queue tasks.
- `queue.py` – `TaskType`/`TaskQueue` enums plus the database-backed `QueueService` for enqueuing/dequeuing `ProcessingTask` records.
- `feed_detection.py` and `feed_discovery.py` – detect RSS/Atom feeds and orchestrate discovery directions.
- `image_generation.py` – AI image/thumbnail creation and persistence hooks invoked after summaries complete.
- `llm_summarization.py`, `llm_agents.py`, `llm_models.py`, `llm_prompts.py` – wrappers around the shared summarizer, prompt management, and agent orchestration.
- `langfuse_tracing.py` – Langfuse client initialization plus context manager helpers shared by the HTTP middleware and task processor.
- `discussion_fetcher.py`, `favorites.py`, `content_interactions.py`, `instruction_links.py`, `prompt_debug_report.py` – support routines for user interactions, favorites, and debugging data.

## Main Types/Interfaces
- `QueueService` and `TaskType`/`TaskQueue` drive worker orchestration.
- `ContentSummarizer` (from `llm_summarization`) and the Langfuse `langfuse_trace_context` wrap LLM calls with tracing metadata.
- Image helper classes provide `generate_image_payload` semantics tied into `app.services.image_generation`.

## Dependencies & Coupling
Heavy dependency on HTTP clients (`httpx`), LLM SDKs (OpenAI, Anthropic, Exa, Langfuse, ElevenLabs), the database via `app.core.db`, and cross-module configuration from `app.core.settings`. Services also import `app.utils` helpers for URLs, dates, and summaries.

## Refactor Opportunities
Many services instantiate their own LLM clients and prompt builders; consider centralizing LLM client creation to avoid inconsistent retries/timeout settings. Also, a clear boundary between request-facing services and worker-only services would help prevent accidental coupling (e.g., `content_submission` currently reuses queue logic meant for workers).

Reviewed files: 44
