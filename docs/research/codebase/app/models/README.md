## Purpose
Defines the database tables plus the Pydantic schemas that describe content submissions, discovery runs, and user/auth payloads used across the FastAPI routers and services.

## Key Files
- `app/models/schema.py` – SQLAlchemy `Content`, `ProcessingTask`, `ContentDiscussion`, and `ContentReadStatus` tables; includes metadata validation hooks and short-summary helpers.
- `app/models/metadata.py` – rich `ContentType`/`ContentStatus` enums plus reusable summary structures (`InterleavedSummary`, `InterleavedSummaryV2`, bullet models, quotes, etc.) used by content processors.
- `app/models/user.py` – `User` table plus Pydantic schemas for authentication (tokens, admin login, profile updates).
- `app/models/content_submission.py` – request/response schemas for the `/api/content/submit` workflow.
- `app/models/feed_discovery.py` – plan/candidate models for discovery flows.
- `app/models/pagination.py` – standardized cursor/metadata responses.
- `app/models/scraper_runs.py` – `ScraperStats` dataclass used in scraping dashboards.

## Main Types/Interfaces
- SQLAlchemy models with `get_validated_metadata()` and custom validators to route metadata through Pydantic.
- Metadata enums (`ContentType`, `ContentStatus`, `ContentClassification`) with accompanying Pydantic summary structures.
- API schema models (`SubmitContentRequest`, `ContentSubmissionResponse`, `Admin`/`User` tokens, discovery lanes, pagination cursors).

## Dependencies & Coupling
Models rely on SQLAlchemy for persistence, Pydantic/Pydantic Settings for schema enforcement, and helper utilities under `app.utils` (date, summary extraction). Routers and services import these models directly for payload validation.

## Refactor Opportunities
`schema.Content` tries to validate metadata during every set which adds complexity; consider moving metadata validation out of the SQLAlchemy event hooks into a dedicated transformation layer. Also, richer reuse between `feed_discovery` and other schema modules could reduce duplication in field descriptions.

Reviewed files: 8
