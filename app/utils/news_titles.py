"""Helpers for canonical news-item titles stored in raw metadata."""

from __future__ import annotations

from typing import Any

from app.utils.title_utils import (
    clean_title,
    get_section_title,
    mapping,
    resolve_display_title,
    resolve_title_candidate,
)

_UNSET = object()


def _clean_related_titles(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    titles: list[str] = []
    seen: set[str] = set()
    for raw in value:
        cleaned = clean_title(raw)
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        titles.append(cleaned)
    return titles


def get_news_article_title(raw_metadata: Any) -> str | None:
    """Return the canonical original/source title for one news item."""
    return get_section_title(raw_metadata, "article")


def get_news_summary_title(raw_metadata: Any) -> str | None:
    """Return the canonical enriched/generated title for one news item."""
    return get_section_title(raw_metadata, "summary")


def get_news_cluster_related_titles(raw_metadata: Any) -> list[str]:
    """Return cleaned related titles stored in cluster metadata."""
    cluster = mapping(mapping(raw_metadata).get("cluster"))
    return _clean_related_titles(cluster.get("related_titles"))


def _news_title_candidates(raw_metadata: Any) -> tuple[str | None, ...]:
    related_titles = get_news_cluster_related_titles(raw_metadata)
    return (
        get_news_summary_title(raw_metadata),
        *related_titles[:1],
        get_news_article_title(raw_metadata),
    )


def resolve_news_display_title(
    raw_metadata: Any,
    *,
    summary_text: str | None = None,
    fallback: str = "Untitled",
) -> str:
    """Resolve the best display title for one news item."""
    return resolve_display_title(
        *_news_title_candidates(raw_metadata),
        summary_text=summary_text,
        fallback=fallback,
    )


def resolve_news_summary_title(
    raw_metadata: Any,
    *,
    summary_text: str | None = None,
) -> str | None:
    """Resolve the best summary/display title candidate for one news item."""
    return resolve_title_candidate(
        *_news_title_candidates(raw_metadata),
        summary_text=summary_text,
    )


def _set_nested_title(raw_metadata: Any, section_name: str, title: Any) -> dict[str, Any]:
    updated = mapping(raw_metadata)
    section = mapping(updated.get(section_name))
    cleaned = clean_title(title)
    if cleaned:
        section["title"] = cleaned
    else:
        section.pop("title", None)
    if section:
        updated[section_name] = section
    elif section_name in updated:
        updated.pop(section_name, None)
    return updated


def set_news_article_title(raw_metadata: Any, title: Any) -> dict[str, Any]:
    """Write one canonical original/source title into raw metadata."""
    return _set_nested_title(raw_metadata, "article", title)


def set_news_summary_title(raw_metadata: Any, title: Any) -> dict[str, Any]:
    """Write one canonical enriched/generated title into raw metadata."""
    return _set_nested_title(raw_metadata, "summary", title)


def merge_news_metadata(existing: Any, incoming: Any) -> dict[str, Any]:
    """Merge news-item metadata while preserving nested title sections."""
    merged = mapping(existing)
    for key, value in mapping(incoming).items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = {**mapping(merged.get(key)), **mapping(value)}
            continue
        merged[key] = value
    return merged


def normalize_news_metadata_titles(
    raw_metadata: Any,
    *,
    article_title: Any = _UNSET,
    summary_title: Any = _UNSET,
) -> dict[str, Any]:
    """Normalize stored metadata titles and optionally overwrite them with explicit values."""
    updated = mapping(raw_metadata)
    updated = set_news_article_title(updated, get_news_article_title(updated))
    updated = set_news_summary_title(updated, get_news_summary_title(updated))
    if article_title is not _UNSET:
        updated = set_news_article_title(updated, article_title)
    if summary_title is not _UNSET:
        updated = set_news_summary_title(updated, summary_title)
    return updated
