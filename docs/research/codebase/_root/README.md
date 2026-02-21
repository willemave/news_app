Purpose
- High-level entrypoint for the infrastructure artifacts rooted at the repository base (Dockerfiles, supervisor, scheduler, and build configs) so operators understand how the container images and host services glue together.

Key Files
- `Dockerfile.server`, `Dockerfile.workers`, and `Dockerfile.scrapers` share a two-stage build that installs Python 3.13 via `uv`, copies `app`, `scripts`, `config`, `alembic`, `static`, and `templates`, and expose service-specific defaults (`SERVICE_TYPE`, healthchecks, cron bootstrap for scrapers).
- `supervisor.conf` declares the programs run on the RackNerd host (server plus worker queues) and documents the cron-style scrapers/discovery scheduling the container-based setup delegates elsewhere.
- `crontab` defines the host jobs to backup the database daily, run scrapers hourly, and trigger feed discovery weekly; each job cdes to `/opt/news_app` and appends to `/var/log/news_app`.
- `alembic.ini` configures the shared Alembic instance (script location, logging, `sqlalchemy.url` from `DATABASE_URL`) used by the `alembic` package copied into every image.
- `index.html` is a static Sequoia Capital RSS dump that seems to serve as a reference sample feed; it is included verbatim under the repo root (likely for testing ingestion or documentation).
- `package.json` plus `tailwind.config.js` define the Tailwind CLI dev setup used to build `static/css/app.css` from `static/css/styles.css`, ensuring the templates under `templates/` have their styles compiled with the same content glob.

Main Interfaces/Behaviors
- Dockerfiles rely on `scripts/start_server.sh`, `scripts/run_workers.py`, `scripts/run_scrapers.py`, and `scripts/run_feed_discovery.py` to bring the application online; the server/workers images expose a `CMD` that launches the appropriate shell script or Python module.
- Supervisor uses the final Docker image artifacts (or host script copies) and monitors each queue with `pgrep` healthchecks; cron lines on the host run `scripts/run_scrapers.py` and `scripts/run_feed_discovery.py` while `scripts/backup_database.sh` handles daily backups.
- Tailwind builds happen via `npm run dev` during local development but the compiled CSS is included in the Docker build context so the runtime does not require Node.

Dependencies & Coupling
- The Dockerfiles depend on `uv.lock`, `pyproject.toml`, `scripts/`, `config/`, `alembic/`, `static/`, and `templates/` being in place; any renaming or restructuring there has to be mirrored inside the `COPY` commands and healthcheck expectations.
- `supervisor.conf` and `crontab` assume the application is installed at `/opt/news_app` with a `.venv` environment; they reference scripts and log paths that must match what the installers create.
- `tailwind.config.js` scans `templates/**/*.html`, so moving templates out of that tree invalidates the CSS build; `package.json`+`static/css/styles.css` are referenced by `scripts/start_server.sh` only indirectly (static assets are served from FastAPI).

Refactor Opportunities
- Consolidate the overlapping base steps of the three Dockerfiles into shared build stages or a new `Dockerfile.base` so installing dependencies, copying directories, and setting env vars happens in one place.
- Document why `index.html` is present at the repo root (if it is a sample feed) or relocate it to a `samples/` directory so the root layout matches the rest of the documented structure.
- Capture cron/supervisor expectations inside this doc or a `deployment/` README so anyone updating `crontab` knows to mirror those updates in `Dockerfile.scrapers` and `supervisor.conf`.

Reviewed files: 9
