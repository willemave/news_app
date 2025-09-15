#!/usr/bin/env python3
"""
Build an LLM prompt from unliked articles over the last N days to guide
classification into "to_read" or "skip". By default, provides SKIP examples
from unliked items. Optionally include TO_READ examples from favorites.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

# Local app imports
from app.core.db import get_db_session
from app.models.schema import Content, ContentUnlikes, ContentFavorites
from app.domain.converters import content_to_domain


def fetch_unliked_articles(db: Session, days: int, limit: int | None) -> list[Content]:
    since = datetime.utcnow() - timedelta(days=days)
    q = (
        db.query(Content)
        .join(ContentUnlikes, Content.id == ContentUnlikes.content_id)
        .filter(Content.content_type == "article")
        .filter(Content.created_at >= since)
        .order_by(Content.created_at.desc())
    )
    if limit:
        q = q.limit(limit)
    return q.all()


def fetch_favorited_articles(db: Session, days: int, limit: int | None) -> list[Content]:
    since = datetime.utcnow() - timedelta(days=days)
    q = (
        db.query(Content)
        .join(ContentFavorites, Content.id == ContentFavorites.content_id)
        .filter(Content.content_type == "article")
        .filter(Content.created_at >= since)
        .order_by(Content.created_at.desc())
    )
    if limit:
        q = q.limit(limit)
    return q.all()


def example_block(domain: Any, label: str) -> str:
    # Build a compact but information-rich example block for the LLM
    parts = [
        f"label: {label}",
        f"title: {domain.display_title}",
    ]
    if domain.source:
        parts.append(f"source: {domain.source}")
    if getattr(domain, "platform", None):
        parts.append(f"platform: {domain.platform}")
    if domain.publication_date:
        parts.append(f"published: {domain.publication_date.isoformat()}")
    if domain.short_summary:
        parts.append(f"short_summary: {domain.short_summary}")
    elif domain.summary:
        parts.append(f"summary: {domain.summary[:800]}")
    # Topics / bullet points if present
    if domain.topics:
        topics = ", ".join(domain.topics[:6])
        parts.append(f"topics: {topics}")
    if domain.bullet_points:
        pts = "; ".join((bp.get("text", "") for bp in domain.bullet_points[:6]))
        parts.append(f"bullets: {pts}")
    return "\n".join(parts)


def build_prompt(db: Session, days: int, limit: int | None, include_favorites: bool) -> str:
    unliked = fetch_unliked_articles(db, days, limit)
    favs = fetch_favorited_articles(db, days, limit) if include_favorites else []

    # Convert to domain
    unliked_domains = []
    for c in unliked:
        try:
            unliked_domains.append(content_to_domain(c))
        except Exception:
            continue

    fav_domains = []
    for c in favs:
        try:
            fav_domains.append(content_to_domain(c))
        except Exception:
            continue

    lines: list[str] = []
    lines.append("# Classification Prompt: to_read vs skip")
    lines.append("")
    lines.append(
        "Your task is to classify incoming articles into either `to_read` or `skip`.\n"
        "Use the labeled examples below to calibrate. Consider source quality, topic relevance,\n"
        "duplication, and content depth. Prefer succinct, informative, novel content as `to_read`;\n"
        "clickbait, low-signal, repetitive, or out-of-scope content as `skip`."
    )
    lines.append("")
    lines.append(f"Time window: last {days} days")
    lines.append("")

    # SKIP examples
    lines.append("## Examples: SKIP (from unliked)")
    if not unliked_domains:
        lines.append("(none in window)")
    for i, d in enumerate(unliked_domains, 1):
        lines.append(f"### Skip Example {i}")
        lines.append("```yaml")
        lines.append(example_block(d, "skip"))
        lines.append("```")
        lines.append("")

    # TO_READ examples (optional)
    if include_favorites:
        lines.append("## Examples: TO_READ (from favorites)")
        if not fav_domains:
            lines.append("(none in window)")
        for i, d in enumerate(fav_domains, 1):
            lines.append(f"### ToRead Example {i}")
            lines.append("```yaml")
            lines.append(example_block(d, "to_read"))
            lines.append("```")
            lines.append("")

    # Instruction
    lines.append("## Instruction")
    lines.append(
        "Given a new article (title/source/summary/topics), respond with a single token: `to_read` or `skip`.\n"
        "No explanation, just the classification."
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate LLM prompt from unliked articles")
    parser.add_argument("--days", type=int, default=7, help="Lookback window in days (default: 7)")
    parser.add_argument("--limit", type=int, default=50, help="Max examples per set (default: 50)")
    parser.add_argument("--include-favorites", action="store_true", help="Also include favorites as TO_READ examples")
    parser.add_argument("--output", type=Path, help="Write prompt to this file (default: stdout)")
    args = parser.parse_args()

    # DB session
    # Use dependency function to get configured session factory
    db: Session = get_db_session()
    try:
        prompt = build_prompt(db, days=args.days, limit=args.limit, include_favorites=args.include_favorites)
    finally:
        try:
            db.close()
        except Exception:
            pass

    if args.output:
        args.output.write_text(prompt, encoding="utf-8")
        print(f"Wrote prompt to {args.output}")
    else:
        print(prompt)


if __name__ == "__main__":
    main()

