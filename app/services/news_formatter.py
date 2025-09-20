"""Utilities for rendering news content into markdown."""

from __future__ import annotations

from typing import Any, Iterable


def _format_metric_value(label: str, value: Any) -> str | None:
    """Convert a metric value into readable text."""
    if value in (None, "", 0):
        return None
    return f"{label}: {value}"


def render_news_markdown(
    items: Iterable[dict[str, Any]], *, heading: str | None = None
) -> str:
    """Render a collection of news items into markdown bullet list."""

    safe_items = list(items)
    if not safe_items:
        return ""

    lines: list[str] = []

    if heading:
        lines.append(f"### {heading}")
        lines.append("")

    for item in safe_items:
        title = item.get("title") or item.get("url") or "Untitled"
        url = item.get("url") or ""
        line = f"- [{title}]({url})" if url else f"- {title}"

        lines.append(line)

        summary = item.get("summary")
        if summary:
            lines.append(f"  {summary.strip()}")

        metadata = item.get("metadata") or {}
        metrics = [
            _format_metric_value("Score", metadata.get("score")),
            _format_metric_value("Comments", metadata.get("comments")),
            _format_metric_value("Likes", metadata.get("likes")),
            _format_metric_value("Retweets", metadata.get("retweets")),
            _format_metric_value("Replies", metadata.get("replies")),
        ]
        metrics = [m for m in metrics if m]
        if metrics:
            lines.append(f"  _{' • '.join(metrics)}_")

        comments_url = item.get("comments_url")
        if comments_url:
            lines.append(f"  [Discussion]({comments_url})")

        lines.append("")

    return "\n".join(lines).strip()

