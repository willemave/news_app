## Purpose
Houses the FastAPI entry point, shared constants, and template helpers that glue together the HTTP surface with the rest of the application.

## Key Files
- `app/main.py` – configures FastAPI (lifespan, middleware, exception handlers), mounts static assets, and includes every router plus Langfuse tracing hooks.
- `app/constants.py` – centralized, type-annotated defaults for models, workers, polling, and summary metadata plus a helper that builds worker IDs.
- `app/templates.py` – configures Jinja2 templates, exposes the cache-busting static version, and registers the `markdown` filter used by the admin UI.
- `app/__init__.py` – package marker ensuring Python treats `app` as a module.

## Main Types/Interfaces
- `FastAPI` application instance with lifespan that initializes logging, Langfuse, and the database.
- Exception handlers for Pydantic validation and admin auth that convert payloads into JSON responses or redirects.
- HTTP middleware that annotates responses with `X-Response-Time` and logs via the structured logger.

## Dependencies & Coupling
Depends on `app.core.*` for settings, logging, DB lifecycles, and security, and wires in every router module plus `app.services.langfuse_tracing`; also mounts `StaticFiles` directories for `/static`.

## Refactor Opportunities
The `main` module still mixes middleware, exception serialization, and router wiring; consider splitting middleware/validation logging helpers into smaller modules so `app/main.py` only composes the pieces.

Reviewed files: 4
