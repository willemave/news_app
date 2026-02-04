"""Helpers for extracting summary text from metadata payloads."""

from typing import Any


def extract_short_summary(summary: dict[str, Any] | str | None) -> str | None:
    """Extract short summary text from a summary payload."""
    if summary is None:
        return None
    if isinstance(summary, str):
        return summary
    if not isinstance(summary, dict):
        return None

    overview = summary.get("overview")
    if overview:
        return overview

    if summary.get("summary_type") == "interleaved":
        hook = summary.get("hook") or summary.get("takeaway")
        if hook:
            return hook

    if summary.get("summary_type") == "news_digest":
        return summary.get("summary") or summary.get("overview")

    points = summary.get("points")
    if isinstance(points, list) and points:
        first_point = points[0] if isinstance(points[0], dict) else None
        if first_point and first_point.get("text"):
            return first_point.get("text")

    if summary.get("summary"):
        return summary.get("summary")

    hook = summary.get("hook") or summary.get("takeaway")
    if hook:
        return hook

    return None


def extract_summary_text(summary: dict[str, Any] | str | None) -> str | None:
    """Extract summary text from a summary payload."""
    return extract_short_summary(summary)
