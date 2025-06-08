#!/usr/bin/env python3
"""
Simple test script for the Substack scraper.
Tests the scraper functionality and shows results.
"""

import sys
import os
import argparse

# Add parent directory so we can import from app
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Import after path setup
try:
    # Direct import from the file
    import importlib.util
    
    # Load substack_scraper module directly
    spec = importlib.util.spec_from_file_location(
        "substack_scraper",
        os.path.join(project_root, "app", "scraping", "substack_scraper.py")
    )
    substack_scraper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(substack_scraper)
    
    # Get the functions we need
    run_substack_scraper = substack_scraper.run_substack_scraper
    load_substack_feeds = substack_scraper.load_substack_feeds
    
    from app.models import Articles, Links
    from app.database import SessionLocal, init_db
    from scripts.process_local_articles import process_new_local_articles
    
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)
except Exception as e:
    print(f"Error loading modules: {e}")
    sys.exit(1)


def show_substack_config():
    """Display the current Substack configuration."""
    print("📋 Substack Configuration:")
    feeds = load_substack_feeds()
    if feeds:
        for i, feed in enumerate(feeds, 1):
            print(f"  {i}. {feed}")
    else:
        print("  No feeds configured or config file not found.")
    print()


def show_recent_articles(db, limit=5):
    """Display recent articles from the database."""
    articles = db.query(Articles).filter(
        Articles.local_path.isnot(None)
    ).order_by(Articles.scraped_date.desc()).limit(limit).all()
    
    if not articles:
        print("📰 No local articles found in database.")
        return
    
    print(f"📰 Recent Local Articles (last {limit}):")
    for i, article in enumerate(articles, 1):
        print(f"  {i}. {article.title[:60]}{'...' if len(article.title) > 60 else ''}")
        print(f"     URL: {article.url}")
        print(f"     Status: {article.status.value}")
        print(f"     Local Path: {article.local_path}")
        print(f"     Author: {article.author or 'Unknown'}")
        if article.short_summary:
            print(f"     Summary: {article.short_summary[:100]}{'...' if len(article.short_summary) > 100 else ''}")
        print()


def show_database_stats(db):
    """Show basic database statistics."""
    total_links = db.query(Links).count()
    total_articles = db.query(Articles).count()
    substack_links = db.query(Links).filter(Links.source == 'substack').count()
    local_articles = db.query(Articles).filter(Articles.local_path.isnot(None)).count()
    
    print("📊 Database Statistics:")
    print(f"  Total Links: {total_links}")
    print(f"  Total Articles: {total_articles}")
    print(f"  Substack Links: {substack_links}")
    print(f"  Local Articles: {local_articles}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Test Substack Scraper")
    parser.add_argument(
        "--show-config-only",
        action="store_true",
        help="Only show the current configuration without running scraper"
    )
    parser.add_argument(
        "--no-process",
        action="store_true",
        help="Skip processing local articles after scraping"
    )
    parser.add_argument(
        "--show-articles",
        type=int,
        default=5,
        help="Number of recent articles to display (default: 5)"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Substack Scraper Test")
    print("=" * 60)

    # Show configuration
    show_substack_config()

    if args.show_config_only:
        return 0

    print("Initializing database...")
    init_db()
    db = SessionLocal()

    try:
        # Show initial stats
        print("📊 Initial Database State:")
        show_database_stats(db)

        # Run the scraper
        print("🔄 Running Substack scraper...")
        run_substack_scraper()
        print("✅ Substack scraper completed.")

        # Show stats after scraping
        print("\n📊 Database State After Scraping:")
        show_database_stats(db)

        # Process local articles unless skipped
        if not args.no_process:
            print("🔄 Processing newly downloaded local articles...")
            process_new_local_articles(db)
            print("✅ Local article processing completed.")

            # Show final stats
            print("\n📊 Final Database State:")
            show_database_stats(db)

        # Show recent articles
        print()
        show_recent_articles(db, args.show_articles)

        print("=" * 60)
        print("Test completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"❌ Error running Substack scraper test: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        db.close()

    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)