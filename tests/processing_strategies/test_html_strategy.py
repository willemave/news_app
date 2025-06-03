import pytest
import httpx # For creating mock Headers
from unittest.mock import AsyncMock, MagicMock, patch

from app.http_client.robust_http_client import RobustHttpClient
from app.processing_strategies.html_strategy import HtmlProcessorStrategy

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio

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


@pytest.fixture
def mock_http_client(mocker):
    """Fixture to mock RobustHttpClient."""
    mock = AsyncMock(spec=RobustHttpClient)
    return mock

@pytest.fixture
def html_strategy(mock_http_client):
    """Fixture to provide an instance of HtmlProcessorStrategy with a mocked http_client."""
    return HtmlProcessorStrategy(http_client=mock_http_client)

async def test_preprocess_url_arxiv(html_strategy: HtmlProcessorStrategy):
    """Test arXiv URL preprocessing."""
    arxiv_abs_url = "https://arxiv.org/abs/1234.5678"
    expected_pdf_url = "https://arxiv.org/pdf/1234.5678"
    processed_url = await html_strategy.preprocess_url(arxiv_abs_url)
    assert processed_url == expected_pdf_url

    non_arxiv_url = "http://example.com/page.html"
    processed_non_arxiv_url = await html_strategy.preprocess_url(non_arxiv_url)
    assert processed_non_arxiv_url == non_arxiv_url

async def test_can_handle_url_html_content_type(html_strategy: HtmlProcessorStrategy):
    """Test can_handle_url with 'text/html' content type."""
    headers = httpx.Headers({'Content-Type': 'text/html; charset=utf-f'})
    assert await html_strategy.can_handle_url("http://example.com", headers) is True

async def test_can_handle_url_other_content_type(html_strategy: HtmlProcessorStrategy):
    """Test can_handle_url with non-HTML content type."""
    headers = httpx.Headers({'Content-Type': 'application/pdf'})
    assert await html_strategy.can_handle_url("http://example.com/doc.pdf", headers) is False

async def test_can_handle_url_no_headers_html_pattern(html_strategy: HtmlProcessorStrategy):
    """Test can_handle_url with a typical HTML URL pattern when no headers are provided."""
    assert await html_strategy.can_handle_url("http://example.com/article.html", None) is True
    assert await html_strategy.can_handle_url("http://example.com/some/path", None) is True # General path

async def test_can_handle_url_no_headers_other_pattern(html_strategy: HtmlProcessorStrategy):
    """Test can_handle_url with non-HTML URL patterns when no headers are provided."""
    assert await html_strategy.can_handle_url("http://example.com/doc.pdf", None) is False
    assert await html_strategy.can_handle_url("http://example.com/data.xml", None) is False
    # Test that preprocessed arXiv PDF URL is not handled by HTML strategy
    assert await html_strategy.can_handle_url("https://arxiv.org/pdf/1234.5678", None) is False


async def test_download_content(html_strategy: HtmlProcessorStrategy, mock_http_client: MagicMock):
    """Test HTML content download."""
    url = "http://example.com/article.html"
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.text = SAMPLE_HTML_CONTENT
    mock_response.url = url # Simulate final URL after potential redirects

    async def mock_get_op(*args, **kwargs):
        return mock_response
    mock_http_client.get = MagicMock(side_effect=mock_get_op)

    content = await html_strategy.download_content(url)

    mock_http_client.get.assert_called_once_with(url)
    assert content == SAMPLE_HTML_CONTENT

async def test_extract_data_successful(html_strategy: HtmlProcessorStrategy):
    """Test successful data extraction from HTML content."""
    url = "http://example.com/article.html"
    # Mock trafilatura.bare_extraction
    with patch('app.processing_strategies.html_strategy.bare_extraction') as mock_bare_extraction:
        mock_bare_extraction.return_value = {
            "title": "Test Article Title",
            "author": "John Doe",
            "date": "2023-01-15",
            "text": "This is the main content of the article. It's very informative."
        }
        
        extracted_data = await html_strategy.extract_data(SAMPLE_HTML_CONTENT, url)

        mock_bare_extraction.assert_called_once_with(
            filecontent=SAMPLE_HTML_CONTENT,
            url=url,
            with_metadata=True,
            include_links=False,
            include_formatting=False
        )
        assert extracted_data["title"] == "Test Article Title"
        assert extracted_data["author"] == "John Doe"
        assert extracted_data["publication_date"] == "2023-01-15"
        assert extracted_data["text_content"] == "This is the main content of the article. It's very informative."
        assert extracted_data["content_type"] == "html"
        assert extracted_data["final_url_after_redirects"] == url

async def test_extract_data_trafilatura_fails(html_strategy: HtmlProcessorStrategy):
    """Test data extraction when Trafilatura fails to extract content."""
    url = "http://example.com/empty_article.html"
    empty_html_content = "<html><body></body></html>"
    with patch('app.processing_strategies.html_strategy.bare_extraction') as mock_bare_extraction:
        mock_bare_extraction.return_value = None # Simulate Trafilatura failure
        
        extracted_data = await html_strategy.extract_data(empty_html_content, url)
        
        assert extracted_data["title"] == "Extraction Failed (Trafilatura)"
        assert extracted_data["text_content"] == ""
        assert extracted_data["content_type"] == "html"

async def test_extract_data_no_content(html_strategy: HtmlProcessorStrategy):
    """Test data extraction when no content is provided."""
    url = "http://example.com/no_content_page.html"
    extracted_data = await html_strategy.extract_data("", url) # Empty string content
    assert extracted_data["title"] == "Extraction Failed (No Content)"
    assert extracted_data["text_content"] == ""

async def test_prepare_for_llm(html_strategy: HtmlProcessorStrategy):
    """Test preparation of extracted data for LLM processing."""
    extracted_data = {
        "title": "Test Article Title",
        "author": "John Doe",
        "publication_date": "2023-01-15",
        "text_content": "This is the main content.",
        "content_type": "html",
        "final_url_after_redirects": "http://example.com/article.html",
    }
    llm_input = await html_strategy.prepare_for_llm(extracted_data)

    assert llm_input["content_to_filter"] == "This is the main content."
    assert llm_input["content_to_summarize"] == "This is the main content."
    assert llm_input["is_pdf"] is False

async def test_extract_internal_urls_placeholder(html_strategy: HtmlProcessorStrategy):
    """Test the placeholder implementation of extract_internal_urls."""
    # As per current implementation, it's a placeholder returning an empty list.
    urls = await html_strategy.extract_internal_urls(SAMPLE_HTML_CONTENT, "http://example.com")
    assert urls == []