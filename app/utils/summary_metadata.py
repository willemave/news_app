"""Utilities for inferring summary metadata."""

from __future__ import annotations

from typing import Any

from app.constants import (
    SUMMARY_KIND_LONG_BULLETS,
    SUMMARY_KIND_LONG_EDITORIAL_NARRATIVE,
    SUMMARY_KIND_LONG_INTERLEAVED,
    SUMMARY_KIND_LONG_STRUCTURED,
    SUMMARY_KIND_SHORT_NEWS_DIGEST,
    SUMMARY_VERSION_V1,
    SUMMARY_VERSION_V2,
)


def infer_summary_kind_version(
    content_type: str,
    summary: dict[str, Any],
    summary_kind: str | None,
    summary_version: int | None,
) -> tuple[str, int] | None:
    """Infer missing summary_kind/summary_version values from legacy payloads."""
    if summary_kind and summary_version:
        return summary_kind, summary_version

    if summary_kind and not summary_version:
        if summary_kind == SUMMARY_KIND_LONG_INTERLEAVED:
            if "key_points" in summary:
                return summary_kind, SUMMARY_VERSION_V2
            return summary_kind, SUMMARY_VERSION_V1
        if summary_kind in {
            SUMMARY_KIND_LONG_STRUCTURED,
            SUMMARY_KIND_LONG_BULLETS,
            SUMMARY_KIND_LONG_EDITORIAL_NARRATIVE,
            SUMMARY_KIND_SHORT_NEWS_DIGEST,
        }:
            return summary_kind, SUMMARY_VERSION_V1

    if content_type == "news":
        return SUMMARY_KIND_SHORT_NEWS_DIGEST, SUMMARY_VERSION_V1

    summary_type = summary.get("summary_type")
    if summary_type == "interleaved":
        return SUMMARY_KIND_LONG_INTERLEAVED, SUMMARY_VERSION_V1
    if summary_type == "news_digest":
        return SUMMARY_KIND_SHORT_NEWS_DIGEST, SUMMARY_VERSION_V1

    if "key_points" in summary and "topics" in summary:
        return SUMMARY_KIND_LONG_INTERLEAVED, SUMMARY_VERSION_V2
    if "insights" in summary:
        return SUMMARY_KIND_LONG_INTERLEAVED, SUMMARY_VERSION_V1
    if "points" in summary:
        return SUMMARY_KIND_LONG_BULLETS, SUMMARY_VERSION_V1
    if "editorial_narrative" in summary and "key_points" in summary:
        return SUMMARY_KIND_LONG_EDITORIAL_NARRATIVE, SUMMARY_VERSION_V1
    if "bullet_points" in summary or "overview" in summary:
        return SUMMARY_KIND_LONG_STRUCTURED, SUMMARY_VERSION_V1

    return None
