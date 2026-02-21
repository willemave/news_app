## Purpose
Provides SQLAlchemy query helpers for content visibility, read/favorite flags, and search filters that avoid repeating correlated subqueries across routers.

## Key Files
- `app/repositories/content_repository.py` – builds `VisibilityContext`, applies inbox/read filters, and exposes SQLite FTS helpers and `apply_visibility_filters()` for list APIs.

## Main Types/Interfaces
- `VisibilityContext` dataclass with correlated `exists` subqueries for `is_in_inbox`, `is_read`, and `is_favorited`.
- Utility functions (`apply_visibility_filters`, `apply_read_filter`, `get_visible_content_query`, `build_fts_match_query`, `sqlite_fts_available`, `apply_sqlite_fts_filter`).

## Dependencies & Coupling
Depends on `app.models.schema.*` and SQLAlchemy core APIs; used by routers (e.g., `api/content_list`) to keep per-user visibility consistent.

## Refactor Opportunities
Expose a builder that returns both the base query and the correlated joins in one object rather than reusing standalone helpers; this would improve readability when combining multiple filters.

Reviewed files: 1
