Purpose
- Remote deployment utilities that sync the Newsly repo (code, assets, envs) to the RackNerd host and keep supervisor-managed processes aligned.

Key Files
- `push_app.sh` handles `rsync` sync + ownership, optional `uv` env install, supervisor restarts, and post-sync validation via remote `supervisorctl` probes.
- `push_envs.sh` is a lightweight helper that mirrors `.env.racknerd` to `.env` on the remote machine, keeping permissions tight and offloading sudo work to the remote host.

Main Interfaces/Behaviors
- Both scripts expose CLI flags for host/dir/owner/port plus extra behaviors (`--install`, `--restart-supervisor`, `--no-delete`, `--env-only`, `--force-env`) and rely on SSH control sockets to minimize connection churn.
- `push_app.sh` also runs remote validation after the sync (the `validate_supervisor_state` function) and can trigger automatic `uv sync` and `scripts/check_and_run_migrations.sh`; `push_envs.sh` focuses solely on transferring secrets files via `rsync` followed by `sudo cp` on the remote node.

Dependencies & Coupling
- Depend on `rsync`, `ssh`, and remote `supervisorctl`/`sudo` being available; the set of supervisor programs (e.g., `news_app_server`, `news_app_workers_*`) must match `supervisor.conf` and Dockerfile service expectations.
- Coupled to local `.venv`, `uv.lock`, and `.env.racknerd`; both scripts expect the repo to live under `/opt/news_app` on the remote side and default to user `newsapp` for ownership.

Refactor Opportunities
- Several SSH/rsync option groupings are reimplemented in both scripts; a shared helper (Bash library or small Python helper) could centralize repeated validation/option parsing logic and reduce divergence.
- Logging could standardize summary output (e.g., success/failure codes for each stage) to make automated deploy pipelines easier to parse and to satisfy `logger.error` conventions in the rest of the codebase.

Reviewed files: 2
