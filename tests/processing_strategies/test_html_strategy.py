import asyncio
import pytest
import httpx  # For creating mock Headers
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.http_client.robust_http_client import RobustHttpClient
from app.processing_strategies.html_strategy import HtmlProcessorStrategy

SAMPLE_HTML_CONTENT = """
<html>
<head><title>Test Article Title</title></head>
<body>
    <h1>Main Heading</h1>
    <p>This is the main content of the article. It's very informative.</p>
    <p>Author: John Doe</p>
    <p>Date: 2023-01-15</p>
    <a href="/related_link">Related</a>
</body>
</html>
"""

SAMPLE_ARXIV_HTML_CONTENT = """
<html><head><title>ArXiv Page</title></head><body>Abstract page, not PDF.</body></html>
"""

SAMPLE_EXTRACTED_MARKDOWN = """
# Test Article Title

This is the main content of the article. It's very informative.

Author: John Doe
Date: 2023-01-15
"""


@pytest.fixture
def mock_http_client():
    """Fixture to mock RobustHttpClient."""
    return MagicMock(spec=RobustHttpClient)

@pytest.fixture
def html_strategy(mock_http_client):
    """Fixture to provide an instance of HtmlProcessorStrategy with a mocked http_client."""
    return HtmlProcessorStrategy(http_client=mock_http_client)

def test_detect_source(html_strategy: HtmlProcessorStrategy):
    """Test source detection from URLs."""
    assert html_strategy._detect_source("https://pubmed.ncbi.nlm.nih.gov/12345") == "PubMed"
    assert html_strategy._detect_source("https://pmc.ncbi.nlm.nih.gov/articles/PMC12345") == "PubMed"
    assert html_strategy._detect_source("https://arxiv.org/abs/1234.5678") == "Arxiv"
    assert html_strategy._detect_source("https://arxiv.org/pdf/1234.5678") == "Arxiv"
    assert html_strategy._detect_source("https://example.com/article") == "web"

def test_preprocess_url_pubmed(html_strategy: HtmlProcessorStrategy):
    """Test PubMed URL preprocessing to PMC."""
    pubmed_url = "https://pubmed.ncbi.nlm.nih.gov/12345"
    expected_pmc_url = "https://pmc.ncbi.nlm.nih.gov/articles/pmid/12345/"
    processed_url = html_strategy.preprocess_url(pubmed_url)
    assert processed_url == expected_pmc_url

def test_preprocess_url_arxiv(html_strategy: HtmlProcessorStrategy):
    """Test arXiv URL preprocessing."""
    arxiv_abs_url = "https://arxiv.org/abs/1234.5678"
    expected_pdf_url = "https://arxiv.org/pdf/1234.5678"
    processed_url = html_strategy.preprocess_url(arxiv_abs_url)
    assert processed_url == expected_pdf_url

    non_arxiv_url = "http://example.com/page.html"
    processed_non_arxiv_url = html_strategy.preprocess_url(non_arxiv_url)
    assert processed_non_arxiv_url == non_arxiv_url

def test_can_handle_url_html_content_type(html_strategy: HtmlProcessorStrategy):
    """Test can_handle_url with 'text/html' content type."""
    headers = httpx.Headers({'Content-Type': 'text/html; charset=utf-8'})
    assert html_strategy.can_handle_url("http://example.com", headers) is True

def test_can_handle_url_other_content_type(html_strategy: HtmlProcessorStrategy):
    """Test can_handle_url with non-HTML content type."""
    headers = httpx.Headers({'Content-Type': 'application/pdf'})
    assert html_strategy.can_handle_url("http://example.com/doc.pdf", headers) is False

def test_can_handle_url_no_headers_html_pattern(html_strategy: HtmlProcessorStrategy):
    """Test can_handle_url with a typical HTML URL pattern when no headers are provided."""
    assert html_strategy.can_handle_url("http://example.com/article.html", None) is True
    assert html_strategy.can_handle_url("http://example.com/some/path", None) is True  # General path

def test_can_handle_url_no_headers_other_pattern(html_strategy: HtmlProcessorStrategy):
    """Test can_handle_url with non-HTML URL patterns when no headers are provided."""
    assert html_strategy.can_handle_url("http://example.com/doc.pdf", None) is False
    assert html_strategy.can_handle_url("http://example.com/data.xml", None) is False
    # Test that preprocessed arXiv PDF URL is not handled by HTML strategy
    assert html_strategy.can_handle_url("https://arxiv.org/pdf/1234.5678", None) is False

def test_download_content(html_strategy: HtmlProcessorStrategy):
    """Test HTML content download - now just returns URL for crawl4ai."""
    url = "http://example.com/article.html"
    content = html_strategy.download_content(url)
    # In the new implementation, download_content just returns the URL
    assert content == url

@pytest.mark.asyncio
async def test_extract_with_crawl4ai_successful(html_strategy: HtmlProcessorStrategy):
    """Test successful extraction with crawl4ai."""
    url = "http://example.com/article.html"
    
    # Mock the crawler and its result
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.markdown_v2 = MagicMock(raw_markdown=SAMPLE_EXTRACTED_MARKDOWN)
    mock_result.metadata = {"title": "Test Article Title"}
    mock_result.url = url
    
    mock_crawler = AsyncMock()
    mock_crawler.arun = AsyncMock(return_value=mock_result)
    mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
    mock_crawler.__aexit__ = AsyncMock(return_value=None)
    
    with patch('app.processing_strategies.html_strategy.AsyncWebCrawler', return_value=mock_crawler):
        result = await html_strategy._extract_with_crawl4ai(url)
        
        assert result["success"] is True
        assert result["content"] == SAMPLE_EXTRACTED_MARKDOWN
        assert result["title"] == "Test Article Title"
        assert result["final_url"] == url

@pytest.mark.asyncio
async def test_extract_with_crawl4ai_failure(html_strategy: HtmlProcessorStrategy):
    """Test failed extraction with crawl4ai."""
    url = "http://example.com/article.html"
    
    # Mock the crawler and its result
    mock_result = MagicMock()
    mock_result.success = False
    mock_result.error_message = "Failed to fetch content"
    
    mock_crawler = AsyncMock()
    mock_crawler.arun = AsyncMock(return_value=mock_result)
    mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
    mock_crawler.__aexit__ = AsyncMock(return_value=None)
    
    with patch('app.processing_strategies.html_strategy.AsyncWebCrawler', return_value=mock_crawler):
        result = await html_strategy._extract_with_crawl4ai(url)
        
        assert result["success"] is False
        assert result["error"] == "Failed to fetch content"

def test_extract_data_successful(html_strategy: HtmlProcessorStrategy):
    """Test successful data extraction with crawl4ai."""
    url = "http://example.com/article.html"
    
    # Mock the async extraction result
    mock_extract_result = {
        "success": True,
        "content": SAMPLE_EXTRACTED_MARKDOWN,
        "title": "Test Article Title",
        "final_url": url
    }
    
    # Create a coroutine that returns the mock result
    async def mock_async_extract(url):
        return mock_extract_result
    
    with patch.object(html_strategy, '_extract_with_crawl4ai', side_effect=mock_async_extract):
        extracted_data = html_strategy.extract_data(SAMPLE_HTML_CONTENT, url)
        
        assert extracted_data["title"] == "Test Article Title"
        assert "John Doe" in extracted_data["text_content"]
        assert extracted_data["content_type"] == "html"
        assert extracted_data["source"] == "web"
        assert extracted_data["final_url_after_redirects"] == url

def test_extract_data_with_metadata_extraction(html_strategy: HtmlProcessorStrategy):
    """Test data extraction with metadata parsing."""
    url = "http://example.com/article.html"
    
    content_with_metadata = """
    # Test Article Title
    
    Author: Jane Smith
    Published: 2023-12-25
    
    This is the article content.
    """
    
    mock_extract_result = {
        "success": True,
        "content": content_with_metadata,
        "title": "Test Article Title",
        "final_url": url
    }
    
    # Create a coroutine that returns the mock result
    async def mock_async_extract(url):
        return mock_extract_result
    
    with patch.object(html_strategy, '_extract_with_crawl4ai', side_effect=mock_async_extract):
        extracted_data = html_strategy.extract_data("", url)
        
        assert extracted_data["author"] == "Jane Smith"
        assert extracted_data["publication_date"] is not None
        assert extracted_data["publication_date"].year == 2023
        assert extracted_data["publication_date"].month == 12
        assert extracted_data["publication_date"].day == 25

def test_extract_data_pubmed_source(html_strategy: HtmlProcessorStrategy):
    """Test data extraction for PubMed URLs."""
    url = "https://pmc.ncbi.nlm.nih.gov/articles/pmid/12345/"
    
    mock_extract_result = {
        "success": True,
        "content": "PubMed article content",
        "title": "PubMed Article",
        "final_url": url
    }
    
    # Create a coroutine that returns the mock result
    async def mock_async_extract(url):
        return mock_extract_result
    
    with patch.object(html_strategy, '_extract_with_crawl4ai', side_effect=mock_async_extract):
        extracted_data = html_strategy.extract_data("", url)
        
        assert extracted_data["source"] == "PubMed"

def test_extract_data_arxiv_source(html_strategy: HtmlProcessorStrategy):
    """Test data extraction for ArXiv URLs."""
    url = "https://arxiv.org/pdf/1234.5678"
    
    mock_extract_result = {
        "success": True,
        "content": "ArXiv paper content",
        "title": "ArXiv Paper",
        "final_url": url
    }
    
    # Create a coroutine that returns the mock result
    async def mock_async_extract(url):
        return mock_extract_result
    
    with patch.object(html_strategy, '_extract_with_crawl4ai', side_effect=mock_async_extract):
        extracted_data = html_strategy.extract_data("", url)
        
        assert extracted_data["source"] == "Arxiv"

def test_extract_data_failure(html_strategy: HtmlProcessorStrategy):
    """Test data extraction when crawl4ai fails."""
    url = "http://example.com/article.html"
    
    mock_extract_result = {
        "success": False,
        "error": "Network error"
    }
    
    # Create a coroutine that returns the mock result
    async def mock_async_extract(url):
        return mock_extract_result
    
    with patch.object(html_strategy, '_extract_with_crawl4ai', side_effect=mock_async_extract):
        extracted_data = html_strategy.extract_data("", url)
        
        assert extracted_data["title"] == "Extraction Failed"
        assert extracted_data["text_content"] == ""
        assert extracted_data["content_type"] == "html"
        assert extracted_data["source"] == "web"

def test_prepare_for_llm(html_strategy: HtmlProcessorStrategy):
    """Test preparation of extracted data for LLM processing."""
    extracted_data = {
        "title": "Test Article Title",
        "author": "John Doe",
        "publication_date": "2023-01-15",
        "text_content": "This is the main content.",
        "content_type": "html",
        "source": "web",
        "final_url_after_redirects": "http://example.com/article.html",
    }
    llm_input = html_strategy.prepare_for_llm(extracted_data)

    assert llm_input["content_to_filter"] == "This is the main content."
    assert llm_input["content_to_summarize"] == "This is the main content."
    assert llm_input["is_pdf"] is False

def test_extract_internal_urls_placeholder(html_strategy: HtmlProcessorStrategy):
    """Test the placeholder implementation of extract_internal_urls."""
    # As per current implementation, it's a placeholder returning an empty list.
    urls = html_strategy.extract_internal_urls(SAMPLE_HTML_CONTENT, "http://example.com")
    assert urls == []

def test_get_extraction_instruction(html_strategy: HtmlProcessorStrategy):
    """Test extraction instruction generation for different sources."""
    web_instruction = html_strategy._get_extraction_instruction("web")
    assert "Focus on extracting the core educational" in web_instruction
    assert "PubMed" not in web_instruction
    
    pubmed_instruction = html_strategy._get_extraction_instruction("PubMed")
    assert "Abstract" in pubmed_instruction
    assert "Methods" in pubmed_instruction
    assert "Results" in pubmed_instruction
    
    arxiv_instruction = html_strategy._get_extraction_instruction("Arxiv")
    assert "Mathematical formulas" in arxiv_instruction
    assert "Algorithms" in arxiv_instruction