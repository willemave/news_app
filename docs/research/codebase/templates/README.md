Purpose
-------
- Captures the Jinja2 layer that renders every admin UI, log viewer, and article experience. The set includes the shared `base.html` layout plus admin-specific diagnostics (`admin_dashboard`, `admin_errors`, `admin_eval_summaries`, `admin_conversational`, `admin_onboarding_lane_preview`), logging helpers (`logs_list`, `log_detail`), and public content pages (`articles`, `detailed_article`).

Key Templates/Assets
--------------------
- `base.html`: the sticky header/nav layout, mobile navigation, global `<link>`/`<script>` includes, and the `static_version` cache buster; every other template extends this file.
- Admin tooling: `admin_dashboard.html`, `admin_errors.html`, `admin_eval_summaries.html`, `admin_conversational.html`, `admin_onboarding_lane_preview.html`. They share Tailwind cards/tables, `details` sections, and inline scripts for fetch/run interactions.
- Logging surfaces: `logs_list.html` enumerates structured and error logs, while `log_detail.html` renders raw files inside a `<pre>` for download.
- Public content: `articles.html` lists scraped summaries with date filtering, and `detailed_article.html` styles metadata, summary markdown, and source links for each article entry.

Coupling to Backend
-------------------
- Each template expects context from FastAPI routers: counts/statistics for dashboard cards, filtered datasets for article lists, JSON responses for evaluation runs/onboarding previews, and paginated log entries for the log views.
- Inline scripts and forms target FastAPI endpoints (e.g., `/admin/onboarding/lane-preview`, `/admin/logs/<file>/download`, `/auth/admin/login`, `/admin/errors/reset`), so the templates are tightly coupled to the routing paths, payload shapes, and `static_version` provided by the backend.

Risks/UX-Maintainability Concerns
---------------------------------
- The admin templates duplicate similar blocks (e.g., `details` wrappers, table headers, summary cards) instead of factoring them into macros, so updates in one place easily diverge from others.
- A lot of interactivity is wired inline (embedded `<script>` tags) rather than through a shared JS module, which increases the chance of stale DOM references when the layout evolves.
- Because most pages extend `base.html`, any change to the navigation or shared assets immediately impacts every admin screen; regressions can be hard to isolate without clearer segmentation or tests.

Refactor Opportunities
--------------------
- Introduce Jinja macros/partials for repeated patterns (summary card rows, toggle sections, filter groups) so the templates stay DRY and easier to reason about.
- Move inline JavaScript into the `static/js` folder and surface configuration via `data-` attributes on the templates; this would centralize behavior and allow better unit testing.
- Consider extracting the article listings and log tables into reusable components (e.g., `articles_list.html`, `log_table.html`) that can be included with different data to avoid large monolithic templates.

Reviewed files: 11
