Purpose
- Houses the minimal Python package marker and documents the system-level cron jobs that keep scraping, backup, and discovery tasks running automatically.

Key Files
- `cron/__init__.py` exists solely to mark the `cron` namespace for Python tooling.
- Root `crontab` (installed on the RackNerd host according to this repo) defines the jobs for database backups, hourly scrapers, and weekly feed discovery runs.

Main Interfaces/Behaviors
- System cron executes `/opt/news_app/scripts/backup_database.sh`, `scripts/run_scrapers.py`, and `scripts/run_feed_discovery.py` according to the schedule in `crontab`; each cron line cd’s to the app directory and appends output to `/var/log/news_app/` for long-term visibility.

Dependencies & Coupling
- Cron lines rely on the repository’s scripts (copied into Docker images and referenced by supervisor) as well as the project `.venv` present at `/opt/news_app/.venv` so Python dependencies match local dev versions.
- The backup job depends on `scripts/backup_database.sh`, which in turn needs the database path defined by `app/core/settings`, while the scraper/discovery jobs read config entries from `config/*.yml`.

Refactor Opportunities
- Consider templating the cron schedule or describing a `/etc/cron.d/news_app` deployment manifest so scheduling can be updated alongside Docker images instead of editing `crontab` manually.
- Document how to regenerate the log shipping path or add environment validation so cron jobs fail fast if `.venv` or the target scripts are missing.

Reviewed files: 1
