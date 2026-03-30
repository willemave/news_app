"""Generic search backend for non-FTS databases."""

from __future__ import annotations

from sqlalchemy import String, cast, func, or_

from app.models.schema import Content


class GenericSearchBackend:
    """Portable case-insensitive LIKE search backend."""

    def supports_full_text(self) -> bool:
        """Generic backend does not use native FTS."""
        return False

    def apply_search(self, query, query_text: str, context: dict | None = None):
        """Apply portable string/JSON search predicates."""
        del context
        search = f"%{query_text.lower()}%"
        conditions = or_(
            func.lower(Content.title).like(search),
            func.lower(Content.source).like(search),
            func.lower(cast(Content.content_metadata["summary"]["title"], String)).like(search),
            func.lower(cast(Content.content_metadata["summary"]["overview"], String)).like(search),
            func.lower(cast(Content.content_metadata["summary"]["hook"], String)).like(search),
            func.lower(cast(Content.content_metadata["summary"]["takeaway"], String)).like(search),
            func.lower(cast(Content.search_text, String)).like(search),
        )
        return query.filter(conditions)
