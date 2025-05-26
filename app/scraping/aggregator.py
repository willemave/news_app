import requests

from .news_scraper import scrape_news
from .pdf_scraper import scrape_pdf
from .fallback_scraper import scrape_fallback

def scrape_url(url: str):
    """
    Decide which scraper to call based on the URL or its content type.
    Return a dict with {title, author, publication_date, content}.
    """
    # Try to get content type via HEAD request. If that fails, default to an empty string.
    try:
        head_resp = requests.head(url, allow_redirects=True, timeout=5)
        content_type = head_resp.headers.get("Content-Type", "").lower()
    except Exception:
        content_type = ""

    # If the content type indicates a PDF or if the URL ends with ".pdf", use the PDF scraper
    if "pdf" in content_type or url.lower().endswith(".pdf"):
        data = scrape_pdf(url)
        if data:
            return data

    # If the URL looks like news or the site is otherwise recognized as a news site, try the news scraper
    if "news" in url.lower():
        data = scrape_news(url)
        if data:
            return data

    # Otherwise, fall back to a generic scraper
    return scrape_fallback(url)