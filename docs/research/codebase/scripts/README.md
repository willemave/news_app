Purpose
- Collection of shell and Python helpers that orchestrate server/workers/scrapers lifecycles, intake pipelines, diagnostics, and data reshaping for the Newsly backend.
- Scripts are the touchpoint for bootstrapping user inboxes, seeding and diagnosing feeds, and driving ad-hoc maintenance without touching FastAPI entrypoints directly.

Key Files
- `scripts/run_scrapers.py`, `scripts/run_feed_discovery.py`, `scripts/run_workers.py`, `scripts/start_server.sh` execute the hourly scraping, weekly discovery, background processing, and HTTP server runbooks referenced by cron, supervisor, and Docker images.
- Management helpers such as `scripts/bootstrap_user_feeds.sh`, `scripts/add_user_scraper_config.py`, `scripts/reset_content_processing.py`, and `scripts/queue_control.py` operate directly on `app` models to align user inboxes and queues.
- Diagnostics + data utilities (`scripts/dump_database.py`, `scripts/dump_system_stats.py`, `scripts/analyze_errors.py`, `scripts/error_analysis_prompt.md`, `scripts/diagnose_youtube.py`) provide quick introspection and reporting for support incidents.
- Dev/infra scripts (`scripts/dev.sh`, `scripts/install_uv_env.sh`, `scripts/setup_uv_env.sh`, `scripts/check_and_run_migrations.sh`, `scripts/sync_db_from_remote.sh`, `scripts/view_remote_errors.sh`, `scripts/update-docs-from-commit.sh`) streamline local prep, migrations, and remote troubleshooting.

Main Interfaces/Behaviors
- Each script is a CLI entrypoint invoked manually, via scheduler, or by supervisor; most expect to run inside the project’s `.venv` (activated in start scripts and Dockerfiles) and rely on `app/core/settings` for `.env`-driven configuration.
- Scraper + worker orchestration scripts emit structured stats (`--show-stats`, `--stats-interval`) and return service-relevant exit codes so supervisors can restart automatically; many share a `scripts/**.py` pattern of `if __name__ == '__main__':` runners that load services from `app/services`.
- Maintenance helpers work directly with SQLAlchemy sessions (`app/core/db`) or rely on `uv` (for dependency locking) while referencing `config/` feeds, `alembic.ini`, and `scripts/QUICK_REFERENCE.md` for documented workflows.

Dependencies & Coupling
- Depend on the `app` package (FastAPI app, DB models, services), so any refactor in `app/models` or `app/services/feed_detection.py` must keep the scripts’ import paths working.
- Coupled to `config/*.yml` for feed/source definitions, to `alembic.ini` for migration checks, to `static/` assets only when generating infographics or thumbnails, and to Docker entrypoints (`scripts/` are copied into every service image).
- Some scripts drive infrastructure (e.g., `scripts/run_scrapers.py` used by `crontab` and `Dockerfile.scrapers`, `scripts/start_workers.sh` used by supervisors), so scheduling logic there must stay aligned with root cron/supervisor declarations.

Refactor Opportunities
- Many scripts parse flags and host constants manually; shared option parsing helpers or a tiny `scripts/common.py` could enforce consistent logging/exit handling and cut repeated boilerplate (e.g., `ssh` options, `--queue` validation, `--dry-run`).
- Split helper scripts (diagnostics vs ingestion) into clearer namespaces or expose them through a dispatcher so that new maintainers do not need to memorize dozens of filenames.
- Add lightweight docstrings or CLI `--help` text guided by `scripts/QUICK_REFERENCE.md` to keep usage predictable when migrating to new infra (e.g., `scripts/run_workers.py` vs. `scripts/start_workers.sh`).

Reviewed files: 64
