Purpose
- Centralized feed/source definitions that power automatic scraper registration, import helpers, and script-driven ingestion for Newsly.

Key Files
- `config/atom.yml` (plus `atom.example.yml`) lists Atom feed URLs and limits used by `scripts/import_config_feeds.py` and `scripts/run_scrapers.py` when building `UserScraperConfig` entries.
- `config/podcasts.yml`, `config/substack.yml`, `config/reddit.yml`, and `config/twitter.yml` enumerate subscription targets and limits; `scripts/add_user_scraper_config.py` reuses these lists for onboarding flows and the deployment sync process can rehydrate them for fresh installs.
- `config/techmeme.yml` and `config/youtube.yml` contain richer metadata (e.g., `limit`, `include_related`, YouTube client options) that feed into `app/services/feed_detection.py` and scraper helpers that know how to parse each source format.

Main Interfaces/Behaviors
- YAML files follow a simple structure (`feeds: [{name, url, limit, ...}]` or `feed: {url, limit}`) and are read by scripts/helpers that iterate over `config/*.yml`, dedupe based on `feed_url`, and create scraper configs via `app.services.scraper_configs`.
- The YouTube config declares both client-global settings (`cookies_path`, `po_token_provider`, `throttle_seconds`) and channel-specific inclusions, so the ingestion service micro-tunes `yt-dlp` behavior on a per-run basis.

Dependencies & Coupling
- Scripts such as `scripts/import_config_feeds.py` expect these YAMLs to exist and use `yaml.safe_load`; removing entries requires coordinating with user configs stored in the database and feed detection code because duplicates are filtered by URL.
- `app/services/content_analyzer.py` and `app/services/feed_detection.py` rely on the same `config/*.yml` for default sources, so any restructuring must keep the YAML reader compatible with `FeedConfig` definitions (e.g., rename keys carefully).
- Example `.yml` files (`*.example.yml`) serve as templates for copying secrets and do not get ingested but keep naming consistent for onboarding docs.

Refactor Opportunities
- Introduce a shared loader that enforces the allowed keys across feed types (and optionally validates `limit` ranges) before scripts attempt to convert data into `UserScraperConfig` records.
- Move recurring values (like limit defaults, `include_related`, throttling) into code-level defaults so the YAML files can stay concise and duplication stays low when the same limit applies to dozens of feeds.

Reviewed files: 11
