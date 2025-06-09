import pytest
import httpx # For creating mock Headers
from unittest.mock import MagicMock

from app.http_client.robust_http_client import RobustHttpClient
from app.processing_strategies.pubmed_strategy import PubMedProcessorStrategy

SAMPLE_PUBMED_PAGE_HTML_PMC_LINK = """
<html><body>
    <div class="full-text-links-list">
        <a href="https://example.com/some_other_link.html">Other Link</a>
        <a href="https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12345/">Full text at PMC</a>
    </div>
</body></html>
"""

SAMPLE_PUBMED_PAGE_HTML_FIRST_LINK = """
<html><body>
    <aside id="full-text-links">
        <h3>Full text links</h3>
        <a href="https://example.com/first_full_text.pdf">Full Text PDF</a>
        <a href="https://example.com/another.html">Another HTML</a>
    </aside>
</body></html>
"""

SAMPLE_PUBMED_PAGE_HTML_NO_LINKS = """
<html><body>
    <div class="full-text-links-list">
        <p>No full text links available.</p>
    </div>
</body></html>
"""

SAMPLE_PUBMED_PAGE_HTML_MALFORMED = """
<html><body>
    <div>This page is not what we expect.</div>
</body></html>
"""


@pytest.fixture
def mock_http_client(mocker):
    """Fixture to mock RobustHttpClient."""
    mock = MagicMock(spec=RobustHttpClient)
    return mock

@pytest.fixture
def pubmed_strategy(mock_http_client):
    """Fixture to provide an instance of PubMedProcessorStrategy with a mocked http_client."""
    return PubMedProcessorStrategy(http_client=mock_http_client)

@pytest.mark.parametrize("url, expected", [
    ("https://pubmed.ncbi.nlm.nih.gov/1234567/", True),
    ("http://pubmed.ncbi.nlm.nih.gov/9876543", True),
    ("https://pubmed.ncbi.nlm.nih.gov/1234567", True), # Without trailing slash
    ("https://www.ncbi.nlm.nih.gov/pubmed/1234567", False), # Different subdomain structure, though might be valid pubmed
    ("https://example.com/pubmed/1234567", False),
    ("https://pubmed.ncbi.nlm.nih.gov/some/other/path", False), # Not just PMID
    ("https://pubmed.ncbi.nlm.nih.gov/1234567.pdf", False), # Direct PDF link
])
def test_can_handle_url(pubmed_strategy: PubMedProcessorStrategy, url: str, expected: bool):
    """Test can_handle_url for various PubMed URL patterns."""
    assert pubmed_strategy.can_handle_url(url, None) is expected

def test_download_content(pubmed_strategy: PubMedProcessorStrategy, mock_http_client: MagicMock):
    """Test download of PubMed page HTML."""
    url = "https://pubmed.ncbi.nlm.nih.gov/1234567/"
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.text = SAMPLE_PUBMED_PAGE_HTML_PMC_LINK
    mock_response.url = url # Simulate final URL

    def mock_get_op(*args, **kwargs):
        return mock_response
    mock_http_client.get = MagicMock(side_effect=mock_get_op)
    
    content = pubmed_strategy.download_content(url)

    mock_http_client.get.assert_called_once_with(url)
    assert content == SAMPLE_PUBMED_PAGE_HTML_PMC_LINK

def test_extract_data_pmc_link_found(pubmed_strategy: PubMedProcessorStrategy):
    """Test extract_data when a PMC full-text link is found."""
    pubmed_url = "https://pubmed.ncbi.nlm.nih.gov/1234567/"
    expected_full_text_url = "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12345/"
    
    extracted_data = pubmed_strategy.extract_data(SAMPLE_PUBMED_PAGE_HTML_PMC_LINK, pubmed_url)

    assert extracted_data["content_type"] == "pubmed_delegation"
    assert extracted_data["next_url_to_process"] == expected_full_text_url
    assert extracted_data["original_pubmed_url"] == pubmed_url
    assert extracted_data["final_url_after_redirects"] == pubmed_url

def test_extract_data_first_link_used(pubmed_strategy: PubMedProcessorStrategy):
    """Test extract_data when no PMC link is found, and the first available link is used."""
    pubmed_url = "https://pubmed.ncbi.nlm.nih.gov/2345678/"
    expected_full_text_url = "https://example.com/first_full_text.pdf"
    
    extracted_data = pubmed_strategy.extract_data(SAMPLE_PUBMED_PAGE_HTML_FIRST_LINK, pubmed_url)

    assert extracted_data["content_type"] == "pubmed_delegation"
    assert extracted_data["next_url_to_process"] == expected_full_text_url
    assert extracted_data["original_pubmed_url"] == pubmed_url

def test_extract_data_no_links_found(pubmed_strategy: PubMedProcessorStrategy):
    """Test extract_data when no full-text links are found on the PubMed page."""
    pubmed_url = "https://pubmed.ncbi.nlm.nih.gov/3456789/"
    extracted_data = pubmed_strategy.extract_data(SAMPLE_PUBMED_PAGE_HTML_NO_LINKS, pubmed_url)

    assert extracted_data["content_type"] == "error_pubmed_extraction"
    assert "next_url_to_process" not in extracted_data
    assert extracted_data["title"] == f"PubMed Full-Text Link Extraction Failed for {pubmed_url.split('/')[-1]}"
    assert "Could not find a usable full-text link" in extracted_data["text_content"]

def test_extract_data_malformed_html(pubmed_strategy: PubMedProcessorStrategy):
    """Test extract_data with malformed HTML where link sections might be missing."""
    pubmed_url = "https://pubmed.ncbi.nlm.nih.gov/4567890/"
    extracted_data = pubmed_strategy.extract_data(SAMPLE_PUBMED_PAGE_HTML_MALFORMED, pubmed_url)

    assert extracted_data["content_type"] == "error_pubmed_extraction"
    assert "next_url_to_process" not in extracted_data

def test_prepare_for_llm_delegation_case(pubmed_strategy: PubMedProcessorStrategy):
    """Test prepare_for_llm when delegation is expected (should be minimal)."""
    extracted_data_delegation = {
        "next_url_to_process": "https://example.com/fulltext.pdf",
        "original_pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/123/",
        "content_type": "pubmed_delegation"
    }
    llm_input = pubmed_strategy.prepare_for_llm(extracted_data_delegation)
    assert llm_input["content_to_filter"] is None
    assert llm_input["content_to_summarize"] is None
    assert llm_input["is_pdf"] is False

def test_prepare_for_llm_failure_case(pubmed_strategy: PubMedProcessorStrategy):
    """Test prepare_for_llm when PubMed link extraction failed."""
    extracted_data_failure = {
        "title": "PubMed Extraction Failed",
        "text_content": "No link found.",
        "content_type": "error_pubmed_extraction"
    }
    llm_input = pubmed_strategy.prepare_for_llm(extracted_data_failure)
    assert llm_input["content_to_filter"] is None
    assert llm_input["content_to_summarize"] is None

def test_extract_internal_urls_placeholder(pubmed_strategy: PubMedProcessorStrategy):
    """Test the placeholder implementation of extract_internal_urls for PubMed."""
    urls = pubmed_strategy.extract_internal_urls(SAMPLE_PUBMED_PAGE_HTML_PMC_LINK, "http://example.com/pubmed123")
    assert urls == []