Purpose
- Houses every generated or hand-tuned revision that incrementally evolves the schema (tables, indexes, chat tables, feed discovery state, analytics, etc.).

Key Files
- Timestamped revisions such as `20260221_01_add_user_integration_tables.py`, `20260215_02_add_analytics_interactions_table.py`, `20260204_01_backfill_summary_kind_version.py`, and hash-prefixed migrations (`031228d342949_create_users_table.py`, `add_content_favorites_table.py`) describe the shape of each step.
- Earlier migrations like `001_initial_schema.py` set up base tables while recent ones expand the content discovery stack and FTS indices (e.g., `20250920_02_add_news_content_type.py`, `9b2a6f9e5c1d_add_content_fts_search.py`).

Main Interfaces/Behaviors
- Alembic imports the `versions` modules when running commands like `upgrade head` or during autogenerate; each file exposes `upgrade()` and `downgrade()` functions that manipulate metadata via SQLAlchemy (usually `op.create_table`, `op.add_column`, etc.).
- Revision filenames follow either date-based or hash-based prefixes, so migrations are usually ordered chronologically and represent discrete feature pushes (e.g., analytics, feed discovery tokens, onboarding flags).

Dependencies & Coupling
- Each file references the Alembic `op` object plus SQLAlchemy `sa` types; they are implicitly coupled to `app/models/schema.py` because they must reflect the actual ORM models.
- Deployment scripts and CI depend on this directory being copied into runtime containers so migrations can run after code syncs; removing or renaming files can break the ordered `heads` chain.

Refactor Opportunities
- Most migrations are packed into a single module; adding a high-level changelog table or README to say which release introduced which revision would help reviewers.
- Consider standardizing naming (e.g., always `YYYYMMDD_<summary>` instead of mixing `hash_` and `date_`) for clearer history and easier `grep` when tracing a specific change.

Reviewed files: 35
