## Purpose
Contains the API router implementations that power the public `/api` surface for chats, submissions, content actions, discovery, voice, integrations, and telemetry.

## Key Files
- `chat.py`/`chat_models.py` – chat endpoints plus streaming WebSocket models used by the dig-deeper experience.
- `content_list.py`, `content_detail.py`, `content_actions.py`, `favorites.py`, `read_status.py` – REST endpoints for presenting articles/podcasts, updating flags, and toggling favorites/read state.
- `submission.py` – `/api/content/submit` handler that validates `SubmitContentRequest` and enqueues the ingestion task.
- `discovery.py`, `integrations.py`, `scraper_configs.py`, `stats.py` – endpoints that expose discovery plans, integration syncs, scraper dashboards, and system metrics.
- `openai.py`, `voice.py`, `voice_models.py` – wrappers/mappers around OpenAI auth and ElevenLabs or Langfuse configuration checks requested by the clients.
- `models.py` – shared Pydantic response models, e.g., `ContentSummaryResponse`, `DetectedFeed`, and `VoiceHealthResponse`.

## Main Types/Interfaces
- `APIRouter` instances with dependency-injected services (`TaskQueue`, `presenters`, `QueueService`, etc.).
- `ContentSummaryResponse`, `VoiceModelResponse`, and chat response models defined in this package drive the HTTP contracts.

## Dependencies & Coupling
Routers rely on `app.services` for queueing, `app.repositories`/`app.presenters` for visibility flags, and `app.utils` for URLs/dates. They also share models defined here for uniform responses and include higher-level routers from `app/routers/api_content`.

## Refactor Opportunities
Some endpoints still manually duplicate pagination or visibility filters; extracting shared helpers (or reusing `VisibilityContext` builders inside this package) would reduce duplication. Consider splitting long modules (e.g., `content_actions.py` and `chat.py`) when the API surface grows further.

Reviewed files: 19
