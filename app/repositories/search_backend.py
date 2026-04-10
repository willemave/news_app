"""Portable search backend for repository queries."""

from __future__ import annotations

from typing import Protocol

from sqlalchemy import String, cast, func, literal_column, or_

from app.models.schema import Content


class SearchBackend(Protocol):
    """Interface for DB-backed content search strategies."""

    def supports_full_text(self) -> bool:
        """Return whether backend uses native full-text support."""

    def apply_search(self, query, query_text: str, context: dict | None = None):
        """Apply search filtering to a SQLAlchemy query."""


class PostgresSearchBackend:
    """PostgreSQL full-text search backend with weighted ranking."""

    def supports_full_text(self) -> bool:
        """PostgreSQL backend uses native FTS."""
        return True

    def _search_document(self):
        """Build the weighted search document expression."""
        title_vector = func.setweight(
            func.to_tsvector("english", func.coalesce(cast(Content.title, String), "")),
            literal_column("'A'"),
        )
        source_vector = func.setweight(
            func.to_tsvector("english", func.coalesce(cast(Content.source, String), "")),
            literal_column("'B'"),
        )
        search_text_vector = func.setweight(
            func.to_tsvector("english", func.coalesce(cast(Content.search_text, String), "")),
            literal_column("'C'"),
        )
        return title_vector.op("||")(source_vector).op("||")(search_text_vector)

    def apply_search(self, query, query_text: str, context: dict | None = None):
        """Apply native PostgreSQL FTS predicates and ranking."""
        search_context = context if context is not None else {}
        normalized = " ".join(query_text.split()).strip()
        if not normalized:
            return query

        search_document = self._search_document()
        search_query = func.websearch_to_tsquery("english", normalized)
        search_rank = func.ts_rank_cd(search_document, search_query)
        title_match = Content.title.bool_op("OPERATOR(public.%)")(normalized)
        source_match = Content.source.bool_op("OPERATOR(public.%)")(normalized)
        trigram_rank = func.greatest(
            func.public.word_similarity(
                normalized,
                func.coalesce(cast(Content.title, String), ""),
            ),
            func.public.word_similarity(
                normalized,
                func.coalesce(cast(Content.source, String), ""),
            ),
        )
        combined_filter = or_(
            search_document.op("@@")(search_query),
            title_match,
            source_match,
            trigram_rank >= 0.5,
        )
        combined_rank = func.greatest(search_rank, trigram_rank * 0.25)

        search_context["rank_expr"] = combined_rank
        return query.filter(combined_filter)


def get_search_backend(db) -> SearchBackend:
    """Return the PostgreSQL-native search backend."""
    del db
    return PostgresSearchBackend()
