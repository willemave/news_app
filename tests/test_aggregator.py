import pytest
from unittest.mock import patch
from app.scraping.aggregator import scrape_url

@pytest.mark.parametrize("url,method_name,return_value", [
    ("http://example.com/news/test", "scrape_news", {"title": "Test News", "content": "Some content"}),
    ("http://example.com/document.pdf", "scrape_pdf", {"title": "PDF Doc", "content": "PDF content"}),
    ("http://example.com/other", "scrape_fallback", {"title": "Fallback", "content": "Fallback content"}),
])
def test_scrape_url(url, method_name, return_value):
    """
    Test scrape_url by verifying that the correct scraper function is called
    based on the provided URL. We'll patch each relevant function in turn.
    """
    patch_path = f"app.scraping.aggregator.{method_name}"
    with patch(patch_path, return_value=return_value) as mock_func:
        result = scrape_url(url)
        mock_func.assert_called_once_with(url)
        assert result == return_value