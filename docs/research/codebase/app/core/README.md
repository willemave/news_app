## Purpose
Provides the foundational services for configuration, database session management, structured logging, and lightweight timing helpers consumed by every other layer.

## Key Files
- `app/core/settings.py` – Pydantic `BaseSettings` model wired to `.env`, exposes JWT, worker, external API, and storage path defaults plus validators that allow SQLite or Postgres.
- `app/core/db.py` – SQLAlchemy `Base`, engine/session lifecycle, helper contexts (`get_db`, `get_readonly_db_session`, `run_migrations`), and connection-pool logging.
- `app/core/logging.py` – structured logger setup with JSONL error/structured handlers, redaction utilities, and console formatter aware of the standard `component`/`operation` extras.
- `app/core/security.py` – JWT helper functions (`create_access_token`, `verify_token`) and a placeholder Apple token verifier that currently skips signature validation with a prominent TODO.
- `app/core/deps.py` – FastAPI dependencies (`get_current_user`, `require_admin`) that stash `AdminAuthRequired` to redirect admins.
- `app/core/timing.py` – simple context manager that emits level-adjusted timing logs for measured operations.

## Main Types/Interfaces
- `Settings`: centralized configuration with lots of descriptive fields, field validators, and alias-based overrides for some API keys.
- `Checkout` of DB sessions: `get_db`, `get_db_session`, and `get_readonly_db_session` all wrap SQLAlchemy sessions with commit/rollback guarantees.
- Structured logging helpers and formatters used by `setup_logging`.

## Dependencies & Coupling
Depends heavily on SQLAlchemy, Pydantic/Pydantic Settings, and the standard library (`jwt`, `dotenv`, `subprocess`) and exposes hooks consumed by `app.main`, routers, and services; `get_settings` is used everywhere.

## Refactor Opportunities
- `get_db`, `get_db_session`, and `get_readonly_db_session` duplicate boilerplate; a shared context manager/factory in one place would simplify maintenance.
- `verify_apple_token` explicitly skips signature verification, so it should either be expanded now or clearly gated behind a feature flag before production.

Reviewed files: 7
