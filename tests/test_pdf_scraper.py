import pytest
import os
from unittest.mock import patch, MagicMock
from app.scraping.pdf_scraper import scrape_pdf

def test_scrape_pdf_success(monkeypatch):
    """
    Test PDF scraping success by mocking environment variable and GeminiPDFProcessor methods.
    """
    # Set environment variable
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-api-key")

    mock_download = MagicMock(return_value=b"%PDF-somebinarycontent")
    mock_extract = MagicMock(return_value="Extracted PDF text")
    mock_analyze = MagicMock(return_value={
        "title": "Analyzed Title",
        "author": "Analyzed Author",
        "publication_date": "2025-01-01",
        "content": "Analyzed summary content"
    })

    with patch("app.scraping.pdf_scraper.GeminiPDFProcessor._download_pdf", mock_download), \
         patch("app.scraping.pdf_scraper.GeminiPDFProcessor._extract_text_from_pdf", mock_extract), \
         patch("app.scraping.pdf_scraper.GeminiPDFProcessor._analyze_with_gemini", mock_analyze):
        
        url = "http://example.com/somefile.pdf"
        result = scrape_pdf(url)
        assert result is not None
        assert result["title"] == "Analyzed Title"
        assert result["author"] == "Analyzed Author"
        assert result["publication_date"] == "2025-01-01"
        assert result["content"] == "Analyzed summary content"

def test_scrape_pdf_no_api_key(monkeypatch):
    """
    Test that if GOOGLE_API_KEY is not set, the scraper returns None and logs an error.
    """
    # Ensure the environment variable is absent
    if "GOOGLE_API_KEY" in os.environ:
        monkeypatch.delenv("GOOGLE_API_KEY")

    result = scrape_pdf("http://example.com/another.pdf")
    assert result is None

def test_scrape_pdf_failure(monkeypatch):
    """
    Test a failure scenario (e.g. network error or PDF parse error) leading to a None result.
    """
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-api-key")

    with patch("app.scraping.pdf_scraper.GeminiPDFProcessor._download_pdf", side_effect=Exception("Download failed")):
        result = scrape_pdf("http://example.com/broken.pdf")
        assert result is None