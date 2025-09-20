#!/usr/bin/env python3
"""Quick utility to exercise the YouTube unified scraper."""

import argparse
import os
import sys

from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.logging import setup_logging  # noqa: E402
from app.scraping.youtube_unified import (  # noqa: E402
    YouTubeChannelConfig,
    YouTubeUnifiedScraper,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dry-run the YouTube scraper against a single channel")
    parser.add_argument("--url", required=False, help="Channel, playlist, or handle URL")
    parser.add_argument("--channel-id", required=False, help="Channel ID if URL is omitted")
    parser.add_argument("--name", required=True, help="Friendly channel name")
    parser.add_argument("--limit", type=int, default=3, help="Maximum number of videos to fetch")
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=30,
        help="Skip videos older than this many days (set 0 to disable)",
    )
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Persist results to the database instead of dry-run",
    )
    parser.add_argument(
        "--language",
        default="en",
        help="Optional transcript language hint",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    log_level = "DEBUG" if args.debug else "INFO"
    setup_logging(level=log_level)

    channel_config = YouTubeChannelConfig(
        name=args.name,
        url=args.url,
        channel_id=args.channel_id,
        limit=args.limit,
        max_age_days=None if args.max_age_days == 0 else args.max_age_days,
        language=args.language,
    )

    scraper = YouTubeUnifiedScraper(channels=[channel_config])

    if args.persist:
        stats = scraper.run_with_stats()
        print(
            f"Saved {stats.saved} items (duplicates: {stats.duplicates}, errors: {stats.errors})"
        )
        return 0

    items = scraper.scrape()
    print(f"Fetched {len(items)} items (dry run)")
    for item in items:
        metadata = item.get("metadata", {})
        print("-", item["title"])
        print("  URL:", item["url"])
        print("  Published:", metadata.get("publication_date"))
        print("  Duration:", metadata.get("duration_seconds"))
        print("  View count:", metadata.get("view_count"))

    return 0


if __name__ == "__main__":
    sys.exit(main())
