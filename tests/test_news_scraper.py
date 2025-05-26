import pytest
from unittest.mock import patch, MagicMock
from app.scraping.news_scraper import scrape_news

def test_scrape_news_success():
    """
    Test that scraping news returns expected fields when NewsPlease succeeds.
    """
    mock_article = MagicMock()
    mock_article.title = "Mock Title"
    mock_article.authors = ["Author One"]
    mock_article.date_publish = "2024-01-10"
    mock_article.maintext = "Some main text content"

    with patch("app.scraping.news_scraper.NewsPlease.from_url", return_value=mock_article) as mock_method:
        url = "http://example.com/news/article"
        result = scrape_news(url)
        mock_method.assert_called_once_with(url)
        assert result["title"] == "Mock Title"
        assert result["author"] == "Author One"
        assert result["publication_date"] == "2024-01-10"
        assert result["content"] == "Some main text content"

def test_scrape_news_failure():
    """
    Test that scraping news returns None and logs the error when an exception occurs.
    """
    with patch("app.scraping.news_scraper.NewsPlease.from_url", side_effect=Exception("Test exception")):
        url = "http://example.com/failingnews"
        result = scrape_news(url)
        assert result is None