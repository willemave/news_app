import feedparser
import datetime
import time

def fetch_rss_links(feed_urls, last_run_date: datetime.datetime):
    """
    Given a list of RSS feed URLs, fetch new items since 'last_run_date'.
    Return a list of objects/dicts with 'url', 'title', 'published', etc.
    """
    new_items = []

    for url in feed_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                # Each entry typically has "published_parsed" as a time.struct_time
                published_parsed = entry.get("published_parsed")
                if published_parsed is None:
                    # Some feeds may have different date fields, e.g. updated_parsed
                    published_parsed = entry.get("updated_parsed")

                if published_parsed:
                    published_dt = datetime.datetime.fromtimestamp(time.mktime(published_parsed))

                    # Make sure the datetime is timezone-aware
                    if published_dt.tzinfo is None:
                        published_dt = published_dt.replace(tzinfo=datetime.timezone.utc)

                    # Compare with last_run_date
                    if published_dt > last_run_date:
                        new_items.append({
                            "url": entry.link,
                            "title": getattr(entry, "title", "No Title"),
                            "published": published_dt
                        })

        except Exception as e:
            print(f"Error fetching RSS feed {url}: {e}")

    return new_items