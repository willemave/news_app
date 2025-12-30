#!/usr/bin/env python3
"""
Audit script to verify podcast and Substack content in database.
Fetches recent episodes/posts from feeds and cross-checks against DB.
"""

import asyncio
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import feedparser
import httpx
import yaml


def normalize_url_for_comparison(url: str) -> str:
    """Normalize URL by removing tracking parameters for comparison.

    Some RSS feeds (like art19.com) add tracking parameters that differ
    based on the HTTP client used (e.g., rss_browser). This function
    removes those parameters to enable matching.
    """
    if not url:
        return url

    parsed = urlparse(url)

    # Remove tracking query parameters
    if parsed.query:
        params = parse_qs(parsed.query)
        # Remove known tracking parameters
        params.pop("rss_browser", None)

        # Rebuild query string
        query = urlencode(params, doseq=True) if params else ""

        # Rebuild URL
        return urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment)
        )

    return url


def load_yaml_config(config_path: Path) -> dict[str, Any]:
    """Load YAML configuration file."""
    with open(config_path) as f:
        return yaml.safe_load(f)


async def fetch_feed(url: str, client: httpx.AsyncClient) -> feedparser.FeedParserDict:
    """Fetch and parse RSS feed."""
    try:
        response = await client.get(url, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        return feedparser.parse(response.text)
    except Exception as e:
        print(f"Error fetching feed {url}: {e}")
        return feedparser.FeedParserDict()


def get_db_connection(db_path: str) -> sqlite3.Connection:
    """Create database connection."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def check_url_in_db(
    conn: sqlite3.Connection, url: str, audio_url: str = None
) -> dict[str, Any] | None:
    """Check if URL exists in database and return its status.

    For podcasts, checks both the entry URL and the audio URL in metadata.
    Uses normalized URLs for comparison to handle tracking parameters.
    """
    cursor = conn.cursor()

    # Normalize URLs for comparison
    normalized_url = normalize_url_for_comparison(url) if url else None
    normalized_audio_url = normalize_url_for_comparison(audio_url) if audio_url else None

    # Try direct URL match first
    if normalized_url:
        cursor.execute(
            """
            SELECT
                c.id,
                c.url,
                c.title,
                c.content_type,
                c.status,
                c.source,
                c.classification,
                c.created_at,
                c.processed_at,
                c.publication_date,
                c.error_message,
                c.retry_count,
                c.content_metadata,
                (SELECT COUNT(*) FROM content_favorites WHERE content_id = c.id) as favorite_count,
                (SELECT GROUP_CONCAT(task_type || ':' || status)
                 FROM processing_tasks
                 WHERE content_id = c.id) as processing_tasks
            FROM contents c
            WHERE c.url = ?
            """,
            (normalized_url,),
        )
        row = cursor.fetchone()
        if row:
            return dict(row)

        # Also try matching by comparing base URLs (without query params)
        # This handles cases where tracking params differ
        cursor.execute(
            """
            SELECT
                c.id,
                c.url,
                c.title,
                c.content_type,
                c.status,
                c.source,
                c.classification,
                c.created_at,
                c.processed_at,
                c.publication_date,
                c.error_message,
                c.retry_count,
                c.content_metadata,
                (SELECT COUNT(*) FROM content_favorites WHERE content_id = c.id) as favorite_count,
                (SELECT GROUP_CONCAT(task_type || ':' || status)
                 FROM processing_tasks
                 WHERE content_id = c.id) as processing_tasks
            FROM contents c
            WHERE SUBSTR(c.url, 1, INSTR(c.url || '?', '?') - 1)
                = SUBSTR(? || '?', 1, INSTR(? || '?', '?') - 1)
            """,
            (normalized_url, normalized_url),
        )
        row = cursor.fetchone()
        if row:
            return dict(row)

    # For podcasts, also check if the audio URL matches
    if normalized_audio_url:
        cursor.execute(
            """
            SELECT
                c.id,
                c.url,
                c.title,
                c.content_type,
                c.status,
                c.source,
                c.classification,
                c.created_at,
                c.processed_at,
                c.publication_date,
                c.error_message,
                c.retry_count,
                c.content_metadata,
                (SELECT COUNT(*) FROM content_favorites WHERE content_id = c.id) as favorite_count,
                (SELECT GROUP_CONCAT(task_type || ':' || status)
                 FROM processing_tasks
                 WHERE content_id = c.id) as processing_tasks
            FROM contents c
            WHERE c.content_type = 'podcast'
            AND (
                json_extract(c.content_metadata, '$.audio_url') = ?
                OR SUBSTR(json_extract(c.content_metadata, '$.audio_url'), 1,
                    INSTR(json_extract(c.content_metadata, '$.audio_url') || '?', '?') - 1) =
                    SUBSTR(? || '?', 1, INSTR(? || '?', '?') - 1)
            )
            """,
            (normalized_audio_url, normalized_audio_url, normalized_audio_url),
        )
        row = cursor.fetchone()
        if row:
            return dict(row)

    return None


async def audit_podcasts(config_path: Path, db_conn: sqlite3.Connection) -> dict[str, Any]:
    """Audit podcast feeds."""
    config = load_yaml_config(config_path)
    results = {}

    async with httpx.AsyncClient() as client:
        for feed_config in config.get("feeds", []):
            feed_name = feed_config["name"]
            feed_url = feed_config["url"]
            limit = min(feed_config.get("limit", 10), 10)  # Max 10 for this audit

            print(f"Auditing podcast: {feed_name}")

            feed = await fetch_feed(feed_url, client)

            if not feed.entries:
                results[feed_name] = {
                    "feed_url": feed_url,
                    "error": "No entries found in feed",
                    "episodes": [],
                }
                continue

            episodes = []
            for entry in feed.entries[:limit]:
                # Get the entry link (web page URL)
                entry_link = entry.get("link")

                # For podcasts, we look for the enclosure URL (audio file)
                audio_url = None
                if hasattr(entry, "enclosures") and entry.enclosures:
                    audio_url = entry.enclosures[0].get("href")

                # Some feeds use different structures
                if not audio_url and hasattr(entry, "links"):
                    for link in entry.links:
                        if link.get("type", "").startswith("audio/"):
                            audio_url = link.get("href")
                            break

                # Check database using both entry link and audio URL
                db_status = None
                if entry_link:
                    db_status = check_url_in_db(db_conn, entry_link, audio_url)
                elif audio_url:
                    # Fallback if no entry link
                    db_status = check_url_in_db(db_conn, audio_url, audio_url)

                episode_info = {
                    "title": entry.get("title", "No title"),
                    "entry_link": entry_link,
                    "audio_url": audio_url,
                    "published": entry.get("published", "Unknown"),
                    "in_database": db_status is not None,
                    "db_info": db_status,
                }
                episodes.append(episode_info)

            results[feed_name] = {
                "feed_url": feed_url,
                "total_episodes_checked": len(episodes),
                "episodes_in_db": sum(1 for e in episodes if e["in_database"]),
                "episodes": episodes,
            }

    return results


async def audit_substacks(config_path: Path, db_conn: sqlite3.Connection) -> dict[str, Any]:
    """Audit Substack feeds."""
    config = load_yaml_config(config_path)
    results = {}

    async with httpx.AsyncClient() as client:
        for feed_config in config.get("feeds", []):
            feed_name = feed_config["name"]
            feed_url = feed_config["url"]
            limit = min(feed_config.get("limit", 10), 10)  # Max 10 for this audit

            print(f"Auditing Substack: {feed_name}")

            feed = await fetch_feed(feed_url, client)

            if not feed.entries:
                results[feed_name] = {
                    "feed_url": feed_url,
                    "error": "No entries found in feed",
                    "posts": [],
                }
                continue

            posts = []
            for entry in feed.entries[:limit]:
                post_url = entry.get("link")
                db_status = check_url_in_db(db_conn, post_url) if post_url else None

                post_info = {
                    "title": entry.get("title", "No title"),
                    "url": post_url,
                    "published": entry.get("published", "Unknown"),
                    "in_database": db_status is not None,
                    "db_info": db_status,
                }
                posts.append(post_info)

            results[feed_name] = {
                "feed_url": feed_url,
                "total_posts_checked": len(posts),
                "posts_in_db": sum(1 for p in posts if p["in_database"]),
                "posts": posts,
            }

    return results


def generate_report(podcast_results: dict[str, Any], substack_results: dict[str, Any]) -> str:
    """Generate a comprehensive audit report."""
    report_lines = []

    report_lines.append("=" * 80)
    report_lines.append("CONTENT AUDIT REPORT")
    report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("=" * 80)
    report_lines.append("")

    # Podcast Summary
    report_lines.append("PODCAST FEEDS SUMMARY")
    report_lines.append("-" * 80)
    total_podcast_episodes = 0
    total_podcast_in_db = 0

    for feed_name, data in podcast_results.items():
        if "error" in data:
            report_lines.append(f"❌ {feed_name}: {data['error']}")
        else:
            total_checked = data["total_episodes_checked"]
            in_db = data["episodes_in_db"]
            total_podcast_episodes += total_checked
            total_podcast_in_db += in_db
            coverage = (in_db / total_checked * 100) if total_checked > 0 else 0
            status = "✅" if coverage == 100 else "⚠️" if coverage > 0 else "❌"
            report_lines.append(
                f"{status} {feed_name}: {in_db}/{total_checked} episodes in DB ({coverage:.1f}%)"
            )

    report_lines.append("")
    overall_podcast_coverage = (
        (total_podcast_in_db / total_podcast_episodes * 100) if total_podcast_episodes > 0 else 0
    )
    report_lines.append(
        f"TOTAL PODCASTS: {total_podcast_in_db}/{total_podcast_episodes} "
        f"episodes in DB ({overall_podcast_coverage:.1f}%)"
    )
    report_lines.append("")

    # Substack Summary
    report_lines.append("SUBSTACK FEEDS SUMMARY")
    report_lines.append("-" * 80)
    total_substack_posts = 0
    total_substack_in_db = 0

    for feed_name, data in substack_results.items():
        if "error" in data:
            report_lines.append(f"❌ {feed_name}: {data['error']}")
        else:
            total_checked = data["total_posts_checked"]
            in_db = data["posts_in_db"]
            total_substack_posts += total_checked
            total_substack_in_db += in_db
            coverage = (in_db / total_checked * 100) if total_checked > 0 else 0
            status = "✅" if coverage == 100 else "⚠️" if coverage > 0 else "❌"
            report_lines.append(
                f"{status} {feed_name}: {in_db}/{total_checked} posts in DB ({coverage:.1f}%)"
            )

    report_lines.append("")
    overall_substack_coverage = (
        (total_substack_in_db / total_substack_posts * 100) if total_substack_posts > 0 else 0
    )
    report_lines.append(
        f"TOTAL SUBSTACKS: {total_substack_in_db}/{total_substack_posts} "
        f"posts in DB ({overall_substack_coverage:.1f}%)"
    )
    report_lines.append("")

    # Detailed Podcast Report
    report_lines.append("=" * 80)
    report_lines.append("DETAILED PODCAST REPORT")
    report_lines.append("=" * 80)

    for feed_name, data in podcast_results.items():
        report_lines.append("")
        report_lines.append(f"📻 {feed_name}")
        report_lines.append(f"   Feed URL: {data['feed_url']}")

        if "error" in data:
            report_lines.append(f"   Error: {data['error']}")
            continue

        report_lines.append(
            f"   Coverage: {data['episodes_in_db']}/{data['total_episodes_checked']}"
        )
        report_lines.append("")

        for episode in data["episodes"]:
            status = "✅" if episode["in_database"] else "❌"
            report_lines.append(f"   {status} {episode['title']}")
            if episode.get("entry_link"):
                report_lines.append(f"      Entry URL: {episode['entry_link']}")
            if episode.get("audio_url"):
                report_lines.append(f"      Audio URL: {episode['audio_url']}")
            report_lines.append(f"      Published: {episode['published']}")

            if episode["in_database"] and episode["db_info"]:
                db = episode["db_info"]
                report_lines.append(f"      DB Status: {db.get('status', 'unknown')}")
                report_lines.append(f"      Content Type: {db.get('content_type', 'unknown')}")
                if db.get("source"):
                    report_lines.append(f"      Source: {db['source']}")
                if db.get("classification"):
                    report_lines.append(f"      Classification: {db['classification']}")
                if db.get("created_at"):
                    report_lines.append(f"      Created: {db['created_at']}")
                if db.get("processed_at"):
                    report_lines.append(f"      Processed: {db['processed_at']}")
                if db.get("processing_tasks"):
                    report_lines.append(f"      Tasks: {db['processing_tasks']}")
                if db.get("error_message"):
                    report_lines.append(f"      ⚠️ Error: {db['error_message'][:100]}")
                if db.get("retry_count", 0) > 0:
                    report_lines.append(f"      Retries: {db['retry_count']}")
                if db.get("favorite_count", 0) > 0:
                    report_lines.append(f"      ⭐ Favorited ({db['favorite_count']} times)")
            else:
                report_lines.append("      ⚠️  NOT IN DATABASE")

            report_lines.append("")

    # Detailed Substack Report
    report_lines.append("=" * 80)
    report_lines.append("DETAILED SUBSTACK REPORT")
    report_lines.append("=" * 80)

    for feed_name, data in substack_results.items():
        report_lines.append("")
        report_lines.append(f"📝 {feed_name}")
        report_lines.append(f"   Feed URL: {data['feed_url']}")

        if "error" in data:
            report_lines.append(f"   Error: {data['error']}")
            continue

        report_lines.append(f"   Coverage: {data['posts_in_db']}/{data['total_posts_checked']}")
        report_lines.append("")

        for post in data["posts"]:
            status = "✅" if post["in_database"] else "❌"
            report_lines.append(f"   {status} {post['title']}")
            report_lines.append(f"      URL: {post['url']}")
            report_lines.append(f"      Published: {post['published']}")

            if post["in_database"] and post["db_info"]:
                db = post["db_info"]
                report_lines.append(f"      DB Status: {db.get('status', 'unknown')}")
                report_lines.append(f"      Content Type: {db.get('content_type', 'unknown')}")
                if db.get("source"):
                    report_lines.append(f"      Source: {db['source']}")
                if db.get("classification"):
                    report_lines.append(f"      Classification: {db['classification']}")
                if db.get("created_at"):
                    report_lines.append(f"      Created: {db['created_at']}")
                if db.get("processed_at"):
                    report_lines.append(f"      Processed: {db['processed_at']}")
                if db.get("processing_tasks"):
                    report_lines.append(f"      Tasks: {db['processing_tasks']}")
                if db.get("error_message"):
                    report_lines.append(f"      ⚠️ Error: {db['error_message'][:100]}")
                if db.get("retry_count", 0) > 0:
                    report_lines.append(f"      Retries: {db['retry_count']}")
                if db.get("favorite_count", 0) > 0:
                    report_lines.append(f"      ⭐ Favorited ({db['favorite_count']} times)")
            else:
                report_lines.append("      ⚠️  NOT IN DATABASE")

            report_lines.append("")

    report_lines.append("=" * 80)
    report_lines.append("END OF REPORT")
    report_lines.append("=" * 80)

    return "\n".join(report_lines)


async def main():
    """Main audit function."""
    # Paths
    base_path = Path(__file__).parent.parent
    podcast_config = base_path / "config" / "podcasts.yml"
    substack_config = base_path / "config" / "substack.yml"
    db_path = base_path / "news_app.db"

    # Database connection
    db_conn = get_db_connection(str(db_path))

    try:
        # Audit podcasts
        print("Starting podcast audit...")
        podcast_results = await audit_podcasts(podcast_config, db_conn)

        # Audit substacks
        print("\nStarting Substack audit...")
        substack_results = await audit_substacks(substack_config, db_conn)

        # Generate report
        print("\nGenerating report...")
        report = generate_report(podcast_results, substack_results)

        # Save report
        report_path = (
            base_path / "logs" / f"audit_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(report_path, "w") as f:
            f.write(report)

        print(f"\n✅ Report saved to: {report_path}")
        print("\n" + report)

    finally:
        db_conn.close()


if __name__ == "__main__":
    asyncio.run(main())
