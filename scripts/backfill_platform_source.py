#!/usr/bin/env python3
"""
Backfill 'platform' and 'source' columns in the SQLite DB according to the rules:

- platform: scraper identifier (hackernews, reddit, substack, podcast, twitter, ...)
- source: full domain of the linked content; for reddit only, the subreddit name

Usage:
  python scripts/backfill_platform_source.py [--dry-run]

Reads DATABASE_URL from env (e.g., sqlite:////data/news_app.db) or defaults to ./news_app.db
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from urllib.parse import urlparse


def _db_path_from_env() -> str:
    url = os.getenv("DATABASE_URL", "sqlite:///./news_app.db")
    if not url.startswith("sqlite:"):
        raise SystemExit("Only sqlite DATABASE_URL is supported for this backfill script")
    # Accept forms: sqlite:///relative.db, sqlite:////abs/path.db
    m = re.match(r"sqlite:(?P<slashes>/{2,3})(?P<path>.*)", url)
    if not m:
        return "news_app.db"
    path = m.group("path")
    if not path:
        return "news_app.db"
    return path


def host_of(url: str | None) -> str:
    if not url:
        return ""
    try:
        return urlparse(url).netloc or ""
    except Exception:
        return ""


def main() -> int:
    dry = "--dry-run" in sys.argv
    db_path = _db_path_from_env()
    if not os.path.exists(db_path):
        print(f"DB not found at {db_path}")
        return 1

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    rows = cur.execute(
        "SELECT id, url, platform, source, content_metadata FROM contents"
    ).fetchall()

    updates = 0
    plat_updates = 0
    src_updates = 0

    for row in rows:
        cid = row["id"]
        url = row["url"]
        platform = row["platform"]
        source = row["source"]
        md = row["content_metadata"]
        try:
            meta = json.loads(md) if isinstance(md, str) else (md or {})
        except Exception:
            meta = {}

        new_platform = platform
        new_source = source

        # Prefer metadata platform if DB missing
        mp = meta.get("platform")
        if (not platform) and isinstance(mp, str) and mp.strip():
            new_platform = mp.strip().lower()

        # Source rule
        if (new_platform or meta.get("platform")) == "reddit":
            # subreddit from metadata or strip prefix from existing
            sub = meta.get("subreddit")
            if not sub and isinstance(source, str) and source.startswith("reddit:"):
                sub = source.split(":", 1)[-1]
            if sub:
                new_source = sub
        else:
            # Use domain of final_url if present else url
            final_url = meta.get("final_url") or meta.get("final_url_after_redirects") or url
            domain = host_of(final_url)
            if domain and domain != source:
                new_source = domain

        if new_platform != platform or new_source != source:
            if not dry:
                cur.execute(
                    "UPDATE contents SET platform = ?, source = ? WHERE id = ?",
                    (new_platform, new_source, cid),
                )
            updates += 1
            if new_platform != platform:
                plat_updates += 1
            if new_source != source:
                src_updates += 1

    if not dry:
        con.commit()
    print(f"Rows scanned: {len(rows)} | updated: {updates} (platform: {plat_updates}, source: {src_updates})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

