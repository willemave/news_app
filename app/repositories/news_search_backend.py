"""Portable search backend for news-item queries."""

from __future__ import annotations

import re
from typing import Protocol

from sqlalchemy import String, and_, cast, func, literal, literal_column, or_

from app.models.schema import NewsItem


class NewsSearchBackend(Protocol):
    """Interface for DB-backed news-item search strategies."""

    def supports_full_text(self) -> bool:
        """Return whether backend uses native full-text support."""

    def apply_search(self, query, query_text: str, context: dict | None = None):
        """Apply search filtering to a SQLAlchemy query."""


def _summary_title_expr():
    return func.coalesce(cast(NewsItem.raw_metadata["summary"]["title"].as_string(), String), "")


def _article_title_expr():
    return func.coalesce(cast(NewsItem.raw_metadata["article"]["title"].as_string(), String), "")


def _cluster_titles_expr():
    return func.coalesce(
        cast(NewsItem.raw_metadata["cluster"]["related_titles"].as_string(), String),
        "",
    )


def _summary_text_expr():
    return func.coalesce(cast(NewsItem.summary_text, String), "")


def _source_label_expr():
    return func.coalesce(cast(NewsItem.source_label, String), "")


def _article_domain_expr():
    return func.coalesce(cast(NewsItem.article_domain, String), "")


def _provenance_text_expr():
    return (
        _source_label_expr()
        + literal(" ")
        + _article_domain_expr()
        + literal(" ")
        + _cluster_titles_expr()
    )


class PostgresNewsSearchBackend:
    """PostgreSQL full-text search backend for visible news-item lookups."""

    def supports_full_text(self) -> bool:
        return True

    def _search_document(self):
        summary_title_vector = func.setweight(
            func.to_tsvector("english", _summary_title_expr()),
            literal_column("'A'"),
        )
        article_title_vector = func.setweight(
            func.to_tsvector("english", _article_title_expr()),
            literal_column("'B'"),
        )
        summary_text_vector = func.setweight(
            func.to_tsvector("english", _summary_text_expr()),
            literal_column("'C'"),
        )
        provenance_vector = func.setweight(
            func.to_tsvector("english", _provenance_text_expr()),
            literal_column("'D'"),
        )
        return (
            summary_title_vector.op("||")(article_title_vector)
            .op("||")(summary_text_vector)
            .op("||")(provenance_vector)
        )

    def apply_search(self, query, query_text: str, context: dict | None = None):
        search_context = context if context is not None else {}
        normalized = " ".join(query_text.split()).strip()
        if not normalized:
            return query

        search_document = self._search_document()
        search_query = func.websearch_to_tsquery("english", normalized)
        search_rank = func.ts_rank_cd(search_document, search_query)
        summary_title_match = _summary_title_expr().bool_op("OPERATOR(public.%)")(normalized)
        article_title_match = _article_title_expr().bool_op("OPERATOR(public.%)")(normalized)
        trigram_rank = func.greatest(
            func.public.word_similarity(normalized, _summary_title_expr()),
            func.public.word_similarity(normalized, _article_title_expr()),
            func.public.word_similarity(normalized, _source_label_expr()),
            func.public.word_similarity(normalized, _article_domain_expr()),
            func.public.word_similarity(normalized, _cluster_titles_expr()),
        )
        combined_filter = or_(
            search_document.op("@@")(search_query),
            summary_title_match,
            article_title_match,
            trigram_rank >= 0.5,
        )
        search_context["rank_expr"] = func.greatest(search_rank, trigram_rank * 0.25)
        return query.filter(combined_filter)


class GenericNewsSearchBackend:
    """Portable fallback backend for SQLite and other non-Postgres tests."""

    def supports_full_text(self) -> bool:
        return False

    def apply_search(self, query, query_text: str, context: dict | None = None):
        del context
        tokens = [
            token for token in re.findall(r"[a-z0-9]+", query_text.lower()) if len(token) >= 3
        ]
        if not tokens:
            return query

        token_filters = [
            or_(
                func.lower(_summary_title_expr()).like(f"%{token}%"),
                func.lower(_article_title_expr()).like(f"%{token}%"),
                func.lower(_summary_text_expr()).like(f"%{token}%"),
                func.lower(_source_label_expr()).like(f"%{token}%"),
                func.lower(_article_domain_expr()).like(f"%{token}%"),
                func.lower(_cluster_titles_expr()).like(f"%{token}%"),
            )
            for token in tokens
        ]
        return query.filter(and_(*token_filters))


def get_news_search_backend(db) -> NewsSearchBackend:
    """Return the best available DB-backed news-item search backend."""
    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        return PostgresNewsSearchBackend()
    return GenericNewsSearchBackend()
