"""SQLite search backend with optional FTS fallback."""

from __future__ import annotations

import re

from sqlalchemy import column, table, text
from sqlalchemy.orm import Session

from app.infrastructure.db.search.generic_search_backend import GenericSearchBackend
from app.models.schema import Content


def build_fts_match_query(raw_query: str) -> str | None:
    """Build a safe SQLite FTS query from user input."""
    tokens = re.findall(r"[A-Za-z0-9_]+", raw_query.lower())
    if not tokens:
        return None
    return " ".join(f"{token}*" for token in tokens)


class SQLiteSearchBackend(GenericSearchBackend):
    """SQLite search backend using FTS when available."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def supports_full_text(self) -> bool:
        """Return whether the SQLite FTS table exists."""
        result = self._db.execute(
            text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='content_fts'")
        ).first()
        return result is not None

    def apply_search(self, query, query_text: str, context: dict | None = None):
        """Apply SQLite FTS when available, otherwise use generic fallback."""
        del context
        match_query = build_fts_match_query(query_text)
        if match_query and self.supports_full_text():
            fts_table = table("content_fts", column("rowid"))
            return (
                query.join(fts_table, fts_table.c.rowid == Content.id)
                .filter(text("content_fts MATCH :match_query"))
                .params(match_query=match_query)
            )
        return super().apply_search(query, query_text)
