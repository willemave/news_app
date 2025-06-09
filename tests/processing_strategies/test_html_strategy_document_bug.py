"""
Test to reproduce the Document object bug in HtmlProcessorStrategy.
"""
import pytest
from unittest.mock import MagicMock, patch
from trafilatura.core import Document

from app.http_client.robust_http_client import RobustHttpClient
from app.processing_strategies.html_strategy import HtmlProcessorStrategy


@pytest.fixture
def mock_http_client():
    """Fixture to mock RobustHttpClient."""
    return MagicMock(spec=RobustHttpClient)


@pytest.fixture
def html_strategy(mock_http_client):
    """Fixture to provide an instance of HtmlProcessorStrategy with a mocked http_client."""
    return HtmlProcessorStrategy(http_client=mock_http_client)


def test_extract_data_trafilatura_returns_document_object_before_fix(html_strategy: HtmlProcessorStrategy):
    """
    Test that demonstrates the original bug would have occurred before the fix.
    This test verifies that we properly handle Document objects now.
    """
    url = "https://rohangautam.github.io/blog/chebyshev_gauss/"
    sample_html = "<html><body><h1>Test</h1><p>Content</p></body></html>"
    
    # Create a mock Document object that doesn't have .get() method
    mock_document = Document()
    
    with patch('app.processing_strategies.html_strategy.bare_extraction') as mock_bare_extraction:
        # Make bare_extraction return a Document object instead of a dict
        mock_bare_extraction.return_value = mock_document
        
        # After the fix, this should NOT raise an error and should return fallback data
        extracted_data = html_strategy.extract_data(sample_html, url)
        
        # Should return fallback data when Document object is returned
        assert extracted_data["title"] == "Extraction Failed (Trafilatura)"
        assert extracted_data["text_content"] == ""
        assert extracted_data["content_type"] == "html"
        assert extracted_data["final_url_after_redirects"] == url


def test_extract_data_handles_document_object_gracefully(html_strategy: HtmlProcessorStrategy):
    """
    Test that after the fix, the strategy handles Document objects gracefully.
    This test will pass after we implement the fix.
    """
    url = "https://rohangautam.github.io/blog/chebyshev_gauss/"
    sample_html = "<html><body><h1>Test Title</h1><p>Test content here.</p></body></html>"
    
    # Create a mock Document object
    mock_document = Document()
    
    with patch('app.processing_strategies.html_strategy.bare_extraction') as mock_bare_extraction:
        # Make bare_extraction return a Document object instead of a dict
        mock_bare_extraction.return_value = mock_document
        
        # After the fix, this should not raise an error and should return a fallback response
        extracted_data = html_strategy.extract_data(sample_html, url)
        
        # Should return fallback data when Document object is returned
        assert extracted_data["title"] == "Extraction Failed (Trafilatura)"
        assert extracted_data["text_content"] == ""
        assert extracted_data["content_type"] == "html"
        assert extracted_data["final_url_after_redirects"] == url