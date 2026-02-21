Purpose
- Centralized database migration tooling for the Newsly schema; tracks schema drift via Alembic while sharing the same settings/kernel as the REST service.

Key Files
- `alembic/env.py` resolves `DATABASE_URL` through `app.core.settings.get_settings()`, wires `Base.metadata` from `app.models.schema`, and implements the standard offline/online contexts that `python -m alembic upgrade head` relies upon.
- `alembic/script.py.mako` is the revision template used by `alembic revision` if the team ever needs custom boilerplate beyond the default template.
- `alembic/README` documents the fact that the project sticks to a single-database setup, while `scripts/check_and_run_migrations.sh` adds validation around migrations in deployment and CI.
- `alembic/versions/` houses every timestamped migration that alters materialized views, tables, indexes, and triggers; the naming pattern uses a mix of hashes and dates for traceability.

Main Interfaces/Behaviors
- Migrations are invoked through Alembic CLI commands (`python -m alembic current`, `heads`, `upgrade head`), with `env.py` ensuring the active `.env` settings (or alembic.ini fallback) drive the target database.
- `scripts/check_and_run_migrations.sh` is the operational wrapper that activates `.venv`, validates settings via `get_settings()`, then runs the same Alembic commands so deployments never miss pending heads.

Dependencies & Coupling
- Strongly coupled to `app.models.schema.Base`, so schema changes there must be reflected by new `alembic/versions` scripts.
- Depends on `app/core/settings` for connection URLs, Pydantic validation, and `.env` loading, as well as `alembic.ini` to describe script locations and logging.
- Deployment tooling (`scripts/deploy/push_app.sh`) and Docker entrypoints copy `alembic.ini` and the `alembic/` package so migrations can run inside containers or on the host.

Refactor Opportunities
- The fallback logic in `env.py` mixes exception handling and string scanning; it could be clearer by settling on a single source of truth for `sqlalchemy.url` (e.g., always deriving from settings and keeping alembic.ini light).
- Tests or lint checks for new migrations could be added by scripting a `python -m alembic check`-style command inside `scripts/check_and_run_migrations.sh` so reviewers do not forget to run `upgrade head` locally.

Reviewed files: 38
