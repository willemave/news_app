"""Dialect-aware search backends for repository queries."""

from __future__ import annotations

import re
from typing import Protocol

from sqlalchemy import String, cast, column, func, or_, table, text
from sqlalchemy.orm import Session

from app.models.schema import Content


class SearchBackend(Protocol):
    """Interface for DB-backed content search strategies."""

    def supports_full_text(self) -> bool:
        """Return whether backend uses native full-text support."""

    def apply_search(self, query, query_text: str, context: dict | None = None):
        """Apply search filtering to a SQLAlchemy query."""


def build_fts_match_query(raw_query: str) -> str | None:
    """Build a safe SQLite FTS query from user input."""
    tokens = re.findall(r"[A-Za-z0-9_]+", raw_query.lower())
    if not tokens:
        return None
    return " ".join(f"{token}*" for token in tokens)


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


def get_search_backend(db: Session) -> SearchBackend:
    """Return a search backend for the current session dialect."""
    if db.get_bind().dialect.name == "sqlite":
        return SQLiteSearchBackend(db)
    return GenericSearchBackend()
