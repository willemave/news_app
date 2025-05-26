import pytest
import requests_mock
from app.scraping.fallback_scraper import scrape_fallback

def test_scrape_fallback_success():
    """
    Test successful fallback scrape with mock HTML content.
    """
    test_html = """
    <html>
      <head><title>Test Page</title></head>
      <body>
        <header>Header content</header>
        <p>Main paragraph.</p>
        <footer>Footer content</footer>
      </body>
    </html>
    """
    url = "http://example.com"
    with requests_mock.Mocker() as m:
        m.get(url, text=test_html, status_code=200)
        result = scrape_fallback(url)
        assert result is not None
        assert result["title"] == "Test Page"
        # It should remove header/footer text but for this naive approach, we only remove the tags
        # The final text is in 'content' with script/style/etc. removed.
        assert "Header content" not in result["content"]  # Because the tag is explicitly removed
        assert "Footer content" not in result["content"]
        assert "Main paragraph." in result["content"]

def test_scrape_fallback_http_error():
    """
    Test fallback scraper handling of 404 or other HTTP errors.
    """
    url = "http://example.com/404"
    with requests_mock.Mocker() as m:
        m.get(url, status_code=404)
        result = scrape_fallback(url)
        # The function logs an error and returns None
        assert result is None