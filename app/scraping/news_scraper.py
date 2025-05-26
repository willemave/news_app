from newsplease import NewsPlease

def scrape_news(url: str):
    """
    Uses news-please to scrape a news article.
    Returns a dict with title, author, publication_date, and content.
    """
    try:
        article = NewsPlease.from_url(url)
        # If the article is successfully parsed, it will have the attributes we need.
        return {
            "title": article.title,
            "author": article.authors[0] if article.authors else None,
            "publication_date": article.date_publish,
            "content": article.maintext
        }
    except Exception as e:
        print(f"News scraper failed for {url}: {e}")
        return None