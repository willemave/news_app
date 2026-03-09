"""Search backend abstractions for repository queries."""

from __future__ import annotations

from typing import Protocol

from sqlalchemy.orm import Session


class SearchBackend(Protocol):
    """Interface for DB-backed content search strategies."""

    def supports_full_text(self) -> bool:
        """Return whether backend uses native full-text support."""

    def apply_search(self, query, query_text: str, context: dict | None = None):
        """Apply search filtering to a SQLAlchemy query."""


def get_search_backend(db: Session) -> SearchBackend:
    """Return a search backend for the current session dialect."""
    if db.get_bind().dialect.name == "sqlite":
        from app.infrastructure.db.search.sqlite_search_backend import SQLiteSearchBackend

        return SQLiteSearchBackend(db)

    from app.infrastructure.db.search.generic_search_backend import GenericSearchBackend

    return GenericSearchBackend()
