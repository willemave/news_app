"""
Daily ingestion script (triggered by cron or admin).
This script is responsible for:
1. Fetching new links from Raindrop.io & RSS feeds
2. Adding new articles to the database with status "new"

The actual processing (scraping, filtering, and summarization) 
is handled by a separate processing script.
"""
import datetime
from sqlalchemy.orm import Session
from app.database import SessionLocal, init_db
from app.models import Articles, CronLogs, ArticleStatus
from app.scraping.raindrop import fetch_new_raindrops
from app.scraping.rss import fetch_rss_links

def run_daily_ingest():
    """
    Main function to fetch new links and add them to the database.
    """
    db = SessionLocal()
    init_db()

    # Create a log entry
    cron_log = CronLogs()
    db.add(cron_log)
    db.commit()
    db.refresh(cron_log)

    # Get last_run_date from the last CronLog
    # For simplicity, we'll use 24 hours ago as default
    last_run_date = datetime.datetime.utcnow() - datetime.timedelta(hours=24)

    # Fetch links from different sources
    # 1) Fetch from Raindrop.io
    raindrop_links = fetch_new_raindrops(last_run_date)
    
    # 2) Fetch from RSS feeds
    feed_urls = ["https://some-rss-feed.com/rss", "https://other-feed.com/feed"]
    rss_links = fetch_rss_links(feed_urls, last_run_date)

    # Combine all links
    all_links = raindrop_links + rss_links
    cron_log.links_fetched = len(all_links)
    db.commit()

    # Track added articles
    added_articles = 0
    errors = []

    # Process each link
    for item in all_links:
        url = item.get("url")
        if not url:
            continue
            
        # Check if article already exists
        existing = db.query(Articles).filter(Articles.url == url).first()
        if existing:
            # Skip if already in database
            continue

        try:
            # Add new article to database with status "new"
            new_article = Articles(
                url=url,
                title=item.get("title"),  # Use title if provided by the source
                publication_date=item.get("publication_date"),  # Use date if provided by the source
                status=ArticleStatus.new
            )
            db.add(new_article)
            db.commit()
            added_articles += 1
        except Exception as e:
            errors.append(f"Failed to add {url}: {str(e)}")

    # Update log
    cron_log.successful_scrapes = added_articles  # Reusing the field for added articles count
    if errors:
        cron_log.errors = str(errors)
    db.commit()
    db.close()
    
    print(f"Daily ingest complete: {added_articles} new articles added out of {len(all_links)} fetched links")

if __name__ == "__main__":
    run_daily_ingest()
