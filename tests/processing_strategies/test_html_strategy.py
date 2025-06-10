import pytest
import httpx # For creating mock Headers
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

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


@pytest.fixture
def mock_http_client():
    """Fixture to mock RobustHttpClient."""
    return MagicMock(spec=RobustHttpClient)

@pytest.fixture
def html_strategy(mock_http_client):
    """Fixture to provide an instance of HtmlProcessorStrategy with a mocked http_client."""
    return HtmlProcessorStrategy(http_client=mock_http_client)

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
    headers = httpx.Headers({'Content-Type': 'text/html; charset=utf-f'})
    assert html_strategy.can_handle_url("http://example.com", headers) is True

def test_can_handle_url_other_content_type(html_strategy: HtmlProcessorStrategy):
    """Test can_handle_url with non-HTML content type."""
    headers = httpx.Headers({'Content-Type': 'application/pdf'})
    assert html_strategy.can_handle_url("http://example.com/doc.pdf", headers) is False

def test_can_handle_url_no_headers_html_pattern(html_strategy: HtmlProcessorStrategy):
    """Test can_handle_url with a typical HTML URL pattern when no headers are provided."""
    assert html_strategy.can_handle_url("http://example.com/article.html", None) is True
    assert html_strategy.can_handle_url("http://example.com/some/path", None) is True # General path

def test_can_handle_url_no_headers_other_pattern(html_strategy: HtmlProcessorStrategy):
    """Test can_handle_url with non-HTML URL patterns when no headers are provided."""
    assert html_strategy.can_handle_url("http://example.com/doc.pdf", None) is False
    assert html_strategy.can_handle_url("http://example.com/data.xml", None) is False
    # Test that preprocessed arXiv PDF URL is not handled by HTML strategy
    assert html_strategy.can_handle_url("https://arxiv.org/pdf/1234.5678", None) is False


def test_download_content(html_strategy: HtmlProcessorStrategy, mock_http_client: MagicMock):
    """Test HTML content download."""
    url = "http://example.com/article.html"
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.text = SAMPLE_HTML_CONTENT
    mock_response.url = url # Simulate final URL after potential redirects

    mock_http_client.get.return_value = mock_response

    content = html_strategy.download_content(url)

    mock_http_client.get.assert_called_once_with(url)
    assert content == SAMPLE_HTML_CONTENT

def test_extract_data_successful_and_returns_datetime(html_strategy: HtmlProcessorStrategy):
    """Test successful data extraction and that publication_date is a datetime object."""
    url = "http://example.com/article.html"
    mock_trafilatura_output = json.dumps({
        "title": "Test Article Title",
        "author": "John Doe",
        "date": "2023-01-15",
        "text": "This is the main content of the article. It's very informative."
    })

    with patch('app.processing_strategies.html_strategy.extract') as mock_extract:
        mock_extract.return_value = mock_trafilatura_output
        
        extracted_data = html_strategy.extract_data(SAMPLE_HTML_CONTENT, url)

        mock_extract.assert_called_once_with(
            filecontent=SAMPLE_HTML_CONTENT,
            url=url,
            with_metadata=True,
            include_links=False,
            include_formatting=False,
            output_format='json'
        )
        assert extracted_data["title"] == "Test Article Title"
        assert extracted_data["author"] == "John Doe"
        assert isinstance(extracted_data["publication_date"], datetime)
        assert extracted_data["publication_date"].year == 2023
        assert extracted_data["publication_date"].month == 1
        assert extracted_data["publication_date"].day == 15
        assert extracted_data["text_content"] == "This is the main content of the article. It's very informative."
        assert extracted_data["content_type"] == "html"
        assert extracted_data["final_url_after_redirects"] == url

def test_extract_data_trafilatura_fails(html_strategy: HtmlProcessorStrategy):
    """Test data extraction when Trafilatura fails to extract content."""
    url = "http://example.com/empty_article.html"
    empty_html_content = "<html><body></body></html>"
    with patch('app.processing_strategies.html_strategy.extract') as mock_extract:
        mock_extract.return_value = None # Simulate Trafilatura failure
        
        extracted_data = html_strategy.extract_data(empty_html_content, url)
        
        assert extracted_data["title"] == "Extraction Failed"
        assert extracted_data["text_content"] == ""
        assert extracted_data["content_type"] == "html"

def test_prepare_for_llm(html_strategy: HtmlProcessorStrategy):
    """Test preparation of extracted data for LLM processing."""
    extracted_data = {
        "title": "Test Article Title",
        "author": "John Doe",
        "publication_date": "2023-01-15",
        "text_content": "This is the main content.",
        "content_type": "html",
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