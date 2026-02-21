## Purpose
Exposes the FastAPI routing layer for the admin UI, authentication, logging, and content-focused endpoints, delegating most heavy lifting to `app.routers.api` submodules.

## Key Files
- `app/routers/admin.py` – admin dashboard router (WebSocket, task/queue status, admin agent flows) plus integration with `app.services.{admin_conversational_agent,onboarding,admin_eval}`.
- `app/routers/auth.py` – authentication endpoints (Apple Sign In, admin login, token refresh) wired to `app.services.openai_llm` and JWT helpers.
- `app/routers/logs.py` – middleware-exposed log streaming endpoints for the admin UI and log viewers.
- `app/routers/api_content.py` – shared `/api/content` router that orchestrates listings, favorites, read status, etc., referencing presenters and repositories.
- `app/routers/admin_conversational_models.py` – Pydantic response model for admin readiness checks.

## Main Types/Interfaces
- `APIRouter` instances that include endpoints for frontend views, WebSocket notifications, and aggregated metadata.
- Integration with `AdminAuthRequired` (redirect) and `require_admin` dependencies for the dashboard.

## Dependencies & Coupling
Routers depend on services in `app.services.*`, repositories, presenters, and the `app.templates` package; they also include the API routers from `app.routers.api`. `admin.py` heavily couples to background task models and queue dashboards.

## Refactor Opportunities
`admin.py` continues to be large—splitting WebSocket handling, queue dashboards, and agent orchestration into helper modules would improve maintainability, especially as more admin features are added.

Reviewed files: 6
