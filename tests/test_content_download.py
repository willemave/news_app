"""
Test content download and processing functionality.
"""
import pytest
import base64
from unittest.mock import patch, MagicMock, Mock
from requests.exceptions import RequestException

from app.processor import download_and_process_content, url_preprocessor


class TestDownloadAndProcessContent:
    """Test cases for download_and_process_content function."""

    @patch('app.processor.fetch_url')
    @patch('app.processor.bare_extraction')
    @patch('app.processor.requests.head')
    def test_download_html_content_success(self, mock_head, mock_extraction, mock_fetch):
        """Test successful HTML content download and processing."""
        # Mock HEAD request
        mock_head_response = Mock()
        mock_head_response.headers = {'content-type': 'text/html'}
        mock_head.return_value = mock_head_response
        
        # Mock fetch_url
        mock_fetch.return_value = "<html><body>Test content</body></html>"
        
        # Mock bare_extraction
        mock_extracted = Mock()
        mock_extracted.title = "Test Article"
        mock_extracted.author = "Test Author"
        mock_extracted.text = "This is test content for the article with enough length to pass validation. " * 3
        mock_extracted.date = "2024-01-01"
        mock_extraction.return_value = mock_extracted
        
        result = download_and_process_content("https://example.com/article")
        
        assert result is not None
        assert result['url'] == "https://example.com/article"
        assert result['title'] == "Test Article"
        assert result['author'] == "Test Author"
        assert result['is_pdf'] is False
        assert len(result['content']) > 100

    @patch('app.processor.requests.head')
    @patch('app.processor.requests.get')
    def test_download_pdf_content_success(self, mock_get, mock_head):
        """Test successful PDF content download and processing."""
        # Mock HEAD request for PDF
        mock_head_response = Mock()
        mock_head_response.headers = {'content-type': 'application/pdf'}
        mock_head.return_value = mock_head_response
        
        # Mock GET request for PDF content
        mock_pdf_content = b"fake pdf content"
        mock_get_response = Mock()
        mock_get_response.content = mock_pdf_content
        mock_get_response.raise_for_status = Mock()
        mock_get.return_value = mock_get_response
        
        result = download_and_process_content("https://example.com/paper.pdf")
        
        assert result is not None
        assert result['url'] == "https://example.com/paper.pdf"
        assert result['is_pdf'] is True
        assert result['content'] == base64.b64encode(mock_pdf_content).decode('utf-8')

    @patch('app.processor.fetch_url')
    def test_download_content_fetch_failure(self, mock_fetch):
        """Test handling when fetch_url returns None."""
        mock_fetch.return_value = None
        
        result = download_and_process_content("https://example.com/article")
        
        assert result is None

    @patch('app.processor.fetch_url')
    @patch('app.processor.bare_extraction')
    def test_download_content_extraction_failure(self, mock_extraction, mock_fetch):
        """Test handling when bare_extraction returns None."""
        mock_fetch.return_value = "<html><body>Test</body></html>"
        mock_extraction.return_value = None
        
        result = download_and_process_content("https://example.com/article")
        
        assert result is None

    @patch('app.processor.fetch_url')
    @patch('app.processor.bare_extraction')
    @patch('app.processor.requests.head')
    def test_download_content_too_short(self, mock_head, mock_extraction, mock_fetch):
        """Test handling when extracted content is too short."""
        # Mock HEAD request
        mock_head_response = Mock()
        mock_head_response.headers = {'content-type': 'text/html'}
        mock_head.return_value = mock_head_response
        
        mock_fetch.return_value = "<html><body>Short</body></html>"
        
        # Mock extraction with short content
        mock_extracted = Mock()
        mock_extracted.title = "Test"
        mock_extracted.author = None
        mock_extracted.text = "Short"  # Less than 100 characters
        mock_extracted.date = None
        mock_extraction.return_value = mock_extracted
        
        result = download_and_process_content("https://example.com/article")
        
        assert result is None

    @patch('app.processor.requests.head')
    def test_download_content_request_exception(self, mock_head):
        """Test handling of RequestException."""
        mock_head.side_effect = RequestException("Network error")
        
        result = download_and_process_content("https://example.com/article")
        
        assert result is None

    @patch('app.processor.url_preprocessor')
    @patch('app.processor.fetch_url')
    @patch('app.processor.bare_extraction')
    @patch('app.processor.requests.head')
    def test_download_content_uses_preprocessor(self, mock_head, mock_extraction, mock_fetch, mock_preprocessor):
        """Test that url_preprocessor is called."""
        # Setup mocks
        mock_preprocessor.return_value = "https://processed.com/article"
        mock_head_response = Mock()
        mock_head_response.headers = {'content-type': 'text/html'}
        mock_head.return_value = mock_head_response
        mock_fetch.return_value = "<html><body>Test content</body></html>"
        
        mock_extracted = Mock()
        mock_extracted.title = "Test"
        mock_extracted.author = None
        mock_extracted.text = "This is test content with enough length to pass validation checks. " * 3
        mock_extracted.date = None
        mock_extraction.return_value = mock_extracted
        
        result = download_and_process_content("https://example.com/article")
        
        mock_preprocessor.assert_called_once_with("https://example.com/article")
        assert result is not None


class TestUrlPreprocessor:
    """Test cases for url_preprocessor function."""

    def test_arxiv_url_conversion(self):
        """Test arXiv URL conversion to PDF format."""
        arxiv_url = "https://arxiv.org/abs/2504.16980"
        result = url_preprocessor(arxiv_url)
        expected = "https://arxiv.org/pdf/2504.16980"
        
        assert result == expected

    def test_arxiv_url_different_paper_id(self):
        """Test arXiv URL conversion with different paper ID."""
        arxiv_url = "https://arxiv.org/abs/1234.5678"
        result = url_preprocessor(arxiv_url)
        expected = "https://arxiv.org/pdf/1234.5678"
        
        assert result == expected

    def test_regular_url_unchanged(self):
        """Test that regular URLs remain unchanged."""
        regular_url = "https://example.com/article"
        result = url_preprocessor(regular_url)
        
        assert result == regular_url

    def test_github_url_unchanged(self):
        """Test that GitHub URLs remain unchanged."""
        github_url = "https://github.com/user/repo"
        result = url_preprocessor(github_url)
        
        assert result == github_url

    @patch('app.processor.extract_pubmed_full_text_link')
    def test_pubmed_url_with_full_text_link(self, mock_extract):
        """Test PubMed URL processing when full text link is found."""
        pubmed_url = "https://pubmed.ncbi.nlm.nih.gov/12345678"
        full_text_url = "https://pmc.ncbi.nlm.nih.gov/articles/PMC123456/"
        mock_extract.return_value = full_text_url
        
        result = url_preprocessor(pubmed_url)
        
        assert result == full_text_url
        mock_extract.assert_called_once_with(pubmed_url)

    @patch('app.processor.extract_pubmed_full_text_link')
    def test_pubmed_url_without_full_text_link(self, mock_extract):
        """Test PubMed URL processing when no full text link is found."""
        pubmed_url = "https://pubmed.ncbi.nlm.nih.gov/12345678"
        mock_extract.return_value = None
        
        result = url_preprocessor(pubmed_url)
        
        assert result == pubmed_url
        mock_extract.assert_called_once_with(pubmed_url)

    @patch('app.processor.extract_pubmed_full_text_link')
    def test_pubmed_url_extraction_exception(self, mock_extract):
        """Test PubMed URL processing when extraction raises exception."""
        pubmed_url = "https://pubmed.ncbi.nlm.nih.gov/12345678"
        mock_extract.side_effect = Exception("Network error")
        
        result = url_preprocessor(pubmed_url)
        
        assert result == pubmed_url

    @pytest.mark.parametrize("url,expected", [
        ("https://arxiv.org/abs/2024.12345", "https://arxiv.org/pdf/2024.12345"),
        ("https://arxiv.org/abs/1234.5678", "https://arxiv.org/pdf/1234.5678"),
        ("https://example.com/article", "https://example.com/article"),
        ("https://github.com/user/repo", "https://github.com/user/repo"),
        ("https://news.ycombinator.com/item?id=123", "https://news.ycombinator.com/item?id=123"),
    ])
    def test_url_preprocessing_parametrized(self, url, expected):
        """Test URL preprocessing with various inputs."""
        with patch('app.processor.extract_pubmed_full_text_link') as mock_extract:
            # Only mock for PubMed URLs
            if 'pubmed.ncbi.nlm.nih.gov' in url:
                mock_extract.return_value = None
            
            result = url_preprocessor(url)
            assert result == expected