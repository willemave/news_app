import pytest
import httpx # For creating mock Headers
import base64
from unittest.mock import MagicMock

from app.http_client.robust_http_client import RobustHttpClient
from app.processing_strategies.pdf_strategy import PdfProcessorStrategy

# Sample PDF content (minimal valid PDF structure for testing purposes)
# This is a very simple, tiny, valid PDF.
SAMPLE_PDF_BYTES = b"%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 3 3]>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000058 00000 n\n0000000111 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n149\n%%EOF"

@pytest.fixture
def mock_http_client(mocker):
    """Fixture to mock RobustHttpClient."""
    mock = MagicMock(spec=RobustHttpClient)
    return mock

@pytest.fixture
def pdf_strategy(mock_http_client):
    """Fixture to provide an instance of PdfProcessorStrategy with a mocked http_client."""
    return PdfProcessorStrategy(http_client=mock_http_client)

def test_can_handle_url_pdf_content_type(pdf_strategy: PdfProcessorStrategy):
    """Test can_handle_url with 'application/pdf' content type."""
    headers = httpx.Headers({'Content-Type': 'application/pdf'})
    assert pdf_strategy.can_handle_url("http://example.com/document.pdf", headers) is True

def test_can_handle_url_pdf_extension(pdf_strategy: PdfProcessorStrategy):
    """Test can_handle_url with '.pdf' extension and no headers."""
    assert pdf_strategy.can_handle_url("http://example.com/document.pdf", None) is True

def test_can_handle_url_arxiv_pdf_link(pdf_strategy: PdfProcessorStrategy):
    """Test can_handle_url with an arXiv PDF link."""
    assert pdf_strategy.can_handle_url("https://arxiv.org/pdf/1234.5678", None) is True
    # Test with .pdf at the end as well
    assert pdf_strategy.can_handle_url("https://arxiv.org/pdf/1234.5678.pdf", None) is True


def test_can_handle_url_non_pdf(pdf_strategy: PdfProcessorStrategy):
    """Test can_handle_url with non-PDF content type and extension."""
    headers = httpx.Headers({'Content-Type': 'text/html'})
    assert pdf_strategy.can_handle_url("http://example.com/page.html", headers) is False
    assert pdf_strategy.can_handle_url("http://example.com/page.html", None) is False
    assert pdf_strategy.can_handle_url("http://example.com/document.doc", None) is False


def test_download_content(pdf_strategy: PdfProcessorStrategy, mock_http_client: MagicMock):
    """Test PDF content download."""
    url = "http://example.com/document.pdf"
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.content = SAMPLE_PDF_BYTES
    mock_response.url = url # Simulate final URL

    def mock_get_op(*args, **kwargs):
        return mock_response
    mock_http_client.get = MagicMock(side_effect=mock_get_op)
    
    content = pdf_strategy.download_content(url)

    mock_http_client.get.assert_called_once_with(url)
    assert content == SAMPLE_PDF_BYTES

@pytest.mark.asyncio
async def test_extract_data_successful(pdf_strategy: PdfProcessorStrategy):
    """Test successful data extraction from PDF content."""
    url = "http://example.com/mydoc.pdf"
    extracted_data = await pdf_strategy.extract_data(SAMPLE_PDF_BYTES, url)

    assert extracted_data["title"] == "mydoc.pdf"
    assert extracted_data["author"] is None
    assert extracted_data["publication_date"] is None
    assert extracted_data["text_content"] is None
    assert extracted_data["binary_content_b64"] == base64.b64encode(SAMPLE_PDF_BYTES).decode('utf-8')
    assert extracted_data["raw_bytes"] == SAMPLE_PDF_BYTES
    assert extracted_data["content_type"] == "pdf"
    assert extracted_data["final_url_after_redirects"] == url

@pytest.mark.asyncio
async def test_extract_data_no_content(pdf_strategy: PdfProcessorStrategy):
    """Test data extraction when no PDF content is provided."""
    url = "http://example.com/empty.pdf"
    extracted_data = await pdf_strategy.extract_data(b"", url) # Empty bytes content
    
    assert extracted_data["title"] == "Extraction Failed (No PDF Content)"
    assert extracted_data["binary_content_b64"] is None
    assert extracted_data["content_type"] == "pdf"

@pytest.mark.asyncio
async def test_extract_data_url_filename_parsing(pdf_strategy: PdfProcessorStrategy):
    """Test filename parsing from URL for title."""
    url1 = "http://example.com/path/to/another_document.pdf"
    data1 = await pdf_strategy.extract_data(SAMPLE_PDF_BYTES, url1)
    assert data1["title"] == "another_document.pdf"

    url2 = "http://example.com/simple" # No extension
    data2 = await pdf_strategy.extract_data(SAMPLE_PDF_BYTES, url2)
    assert data2["title"] == "simple.pdf" # .pdf should be appended

    url3 = "http://example.com/" # Root path
    data3 = await pdf_strategy.extract_data(SAMPLE_PDF_BYTES, url3)
    assert data3["title"] == "PDF Document.pdf" # Default title + .pdf

def test_prepare_for_llm(pdf_strategy: PdfProcessorStrategy):
    """Test preparation of extracted PDF data for LLM processing."""
    extracted_data = {
        "title": "mydoc.pdf",
        "raw_bytes": SAMPLE_PDF_BYTES,
        "content_type": "pdf",
        "final_url_after_redirects": "http://example.com/mydoc.pdf",
    }
    llm_input = pdf_strategy.prepare_for_llm(extracted_data)

    assert llm_input["content_to_filter"] is None # PDFs skip text filtering in current setup
    assert llm_input["content_to_summarize"] == SAMPLE_PDF_BYTES
    assert llm_input["is_pdf"] is True

def test_prepare_for_llm_no_raw_bytes(pdf_strategy: PdfProcessorStrategy):
    """Test LLM prep when raw_bytes are missing (should indicate error)."""
    extracted_data = {
        "title": "error.pdf",
        "raw_bytes": None, # Simulate missing bytes
        "content_type": "pdf",
        "final_url_after_redirects": "http://example.com/error.pdf",
    }
    llm_input = pdf_strategy.prepare_for_llm(extracted_data)
    assert llm_input["content_to_summarize"] == b"" # Should be empty bytes or handle error
    assert llm_input["is_pdf"] is True


def test_extract_internal_urls_placeholder(pdf_strategy: PdfProcessorStrategy):
    """Test the placeholder implementation of extract_internal_urls for PDF."""
    urls = pdf_strategy.extract_internal_urls(SAMPLE_PDF_BYTES, "http://example.com/doc.pdf")
    assert urls == []