import pytest
import httpx # For creating mock Headers
from unittest.mock import MagicMock, patch

from app.http_client.robust_http_client import RobustHttpClient
from app.processing_strategies.factory import UrlProcessorFactory
from app.processing_strategies.html_strategy import HtmlProcessorStrategy
from app.processing_strategies.pdf_strategy import PdfProcessorStrategy
from app.processing_strategies.pubmed_strategy import PubMedProcessorStrategy
from app.processing_strategies.base_strategy import UrlProcessorStrategy # For type hinting

@pytest.fixture
def mock_http_client(mocker):
    """Fixture to mock RobustHttpClient."""
    mock = MagicMock(spec=RobustHttpClient)
    # Mock the head method specifically for factory tests
    mock.head = MagicMock(return_value=MagicMock(spec=httpx.Response, headers=httpx.Headers()))
    return mock

@pytest.fixture
def factory(mock_http_client):
    """Fixture to provide an instance of UrlProcessorFactory with a mocked http_client."""
    return UrlProcessorFactory(http_client=mock_http_client)


@pytest.fixture
def factory_with_mocked_strategies(
    mock_http_client,
    mock_pubmed_strategy_class, # Class mock, instance mock
    mock_pdf_strategy_class,
    mock_html_strategy_class
):
    """
    Provides a UrlProcessorFactory instance where the _strategies list
    is populated with the mocked strategy *classes*.
    """
    factory_instance = UrlProcessorFactory(http_client=mock_http_client)
    # Clear default strategies that might have been registered with real classes
    factory_instance._strategies = []
    
    # Register the mocked strategy classes in the desired order
    # This uses the factory's own registration logic, which logs __name__
    factory_instance.register_strategy(mock_pubmed_strategy_class[0]) # The class mock
    factory_instance.register_strategy(mock_pdf_strategy_class[0])    # The class mock
    factory_instance.register_strategy(mock_html_strategy_class[0])    # The class mock
    
    return factory_instance


# Mock concrete strategy classes to control their can_handle_url behavior
@pytest.fixture
def mock_html_strategy_class(mocker):
    mock = MagicMock(spec=HtmlProcessorStrategy) # Use MagicMock for class mock
    mock.__name__ = "MockHtmlProcessorStrategy" # Add __name__ attribute
    instance_mock = MagicMock(spec=HtmlProcessorStrategy) # Mock for instances
    instance_mock.can_handle_url = MagicMock(return_value=False)
    mock.return_value = instance_mock # When class is called, return instance_mock
    mocker.patch('app.processing_strategies.factory.HtmlProcessorStrategy', mock)
    return mock, instance_mock # Return both class mock and instance mock for assertions

@pytest.fixture
def mock_pdf_strategy_class(mocker):
    mock = MagicMock(spec=PdfProcessorStrategy)
    mock.__name__ = "MockPdfProcessorStrategy" # Add __name__ attribute
    instance_mock = MagicMock(spec=PdfProcessorStrategy)
    instance_mock.can_handle_url = MagicMock(return_value=False)
    mock.return_value = instance_mock
    mocker.patch('app.processing_strategies.factory.PdfProcessorStrategy', mock)
    return mock, instance_mock

@pytest.fixture
def mock_pubmed_strategy_class(mocker):
    mock = MagicMock(spec=PubMedProcessorStrategy)
    mock.__name__ = "MockPubMedProcessorStrategy" # Add __name__ attribute
    instance_mock = MagicMock(spec=PubMedProcessorStrategy)
    instance_mock.can_handle_url = MagicMock(return_value=False)
    mock.return_value = instance_mock
    mocker.patch('app.processing_strategies.factory.PubMedProcessorStrategy', mock)
    return mock, instance_mock


def test_get_strategy_selects_pubmed(
    factory_with_mocked_strategies: UrlProcessorFactory, # Use the new fixture
    mock_http_client: MagicMock,
    mock_pubmed_strategy_class
):
    """Test that PubMedStrategy is selected for a PubMed URL."""
    _, pubmed_instance_mock = mock_pubmed_strategy_class
    pubmed_instance_mock.can_handle_url = MagicMock(return_value=True) # This instance will say yes

    url = "https://pubmed.ncbi.nlm.nih.gov/1234567/"
    strategy = factory_with_mocked_strategies.get_strategy(url) # Use the new fixture

    assert isinstance(strategy, MagicMock) # Should be our mocked instance
    assert strategy == pubmed_instance_mock
    # Check can_handle_url was called on the instance (via the temp instance in factory)
    # The factory creates a temp instance first for URL check without HEAD.
    # Then, if it matches, it creates the *actual* instance to return.
    # So, can_handle_url on the *returned* instance's class mock's return_value (which is instance_mock)
    pubmed_instance_mock.can_handle_url.assert_any_call(url, response_headers=None)


def test_get_strategy_selects_pdf_by_content_type(
    factory_with_mocked_strategies: UrlProcessorFactory,  # Use the new fixture
    mock_http_client: MagicMock,
    mock_pdf_strategy_class,
    mock_pubmed_strategy_class, # Added fixture
    mock_html_strategy_class    # Added fixture
):
    """Test that PdfStrategy is selected based on Content-Type from HEAD request."""
    _mock_pubmed_cls, pubmed_instance_mock = mock_pubmed_strategy_class
    _mock_pdf_cls, pdf_instance_mock = mock_pdf_strategy_class
    _mock_html_cls, html_instance_mock = mock_html_strategy_class

    # Ensure other strategies say NO
    pubmed_instance_mock.can_handle_url = MagicMock(return_value=False)
    html_instance_mock.can_handle_url = MagicMock(return_value=False)

    def pdf_can_handle_logic(url_param, response_headers=None):
        # PDF strategy should say NO on URL-only check for this test case
        if response_headers is None and url_param == "http://example.com/document":
            return False
        # PDF strategy should say YES if headers indicate PDF
        if response_headers and response_headers.get('Content-Type') == 'application/pdf':
            return True
        return False
    pdf_instance_mock.can_handle_url = MagicMock(side_effect=pdf_can_handle_logic)

    url = "http://example.com/document" # URL doesn't end in .pdf
    mock_head_response = MagicMock(spec=httpx.Response)
    mock_head_response.headers = httpx.Headers({'Content-Type': 'application/pdf'})
    mock_head_response.url = url
    mock_http_client.head = MagicMock(return_value=mock_head_response)

    strategy = factory_with_mocked_strategies.get_strategy(url) # Use the new fixture
    
    assert isinstance(strategy, MagicMock)
    assert strategy == pdf_instance_mock
    mock_http_client.head.assert_called_once_with(url)
    pdf_instance_mock.can_handle_url.assert_called_with(url, response_headers=mock_head_response.headers)


def test_get_strategy_selects_html_by_content_type(
    factory_with_mocked_strategies: UrlProcessorFactory, # Use the new fixture
    mock_http_client: MagicMock,
    mock_html_strategy_class,
    mock_pubmed_strategy_class, # Added fixture
    mock_pdf_strategy_class     # Added fixture
):
    """Test that HtmlStrategy is selected based on Content-Type."""
    _mock_pubmed_cls, pubmed_instance_mock = mock_pubmed_strategy_class
    _mock_pdf_cls, pdf_instance_mock = mock_pdf_strategy_class
    _mock_html_cls, html_instance_mock = mock_html_strategy_class

    # Ensure other strategies say NO
    pubmed_instance_mock.can_handle_url = MagicMock(return_value=False)
    pdf_instance_mock.can_handle_url = MagicMock(return_value=False)
    
    def html_can_handle_logic(url_param, response_headers=None):
        # HTML strategy should say NO on URL-only check for this test case
        if response_headers is None and url_param == "http://example.com/page":
            return False
        # HTML strategy should say YES if headers indicate HTML
        if response_headers and response_headers.get('Content-Type') == 'text/html':
            return True
        return False
    html_instance_mock.can_handle_url = MagicMock(side_effect=html_can_handle_logic)

    url = "http://example.com/page"
    mock_head_response = MagicMock(spec=httpx.Response)
    mock_head_response.headers = httpx.Headers({'Content-Type': 'text/html'})
    mock_head_response.url = url
    mock_http_client.head = MagicMock(return_value=mock_head_response)

    strategy = factory_with_mocked_strategies.get_strategy(url) # Use the new fixture

    assert isinstance(strategy, MagicMock)
    assert strategy == html_instance_mock
    mock_http_client.head.assert_called_once_with(url)
    html_instance_mock.can_handle_url.assert_called_with(url, response_headers=mock_head_response.headers)

def test_get_strategy_selects_html_as_fallback(
    factory_with_mocked_strategies: UrlProcessorFactory, # Use the new fixture
    mock_http_client: MagicMock,
    mock_html_strategy_class,
    mock_pdf_strategy_class, # Ensure other strategies say no
    mock_pubmed_strategy_class
):
    """Test that HtmlStrategy is selected as a fallback if others don't match."""
    _mock_html_cls, html_instance_mock = mock_html_strategy_class
    _mock_pdf_cls, pdf_instance_mock = mock_pdf_strategy_class
    _mock_pubmed_cls, pubmed_instance_mock = mock_pubmed_strategy_class

    # Ensure PubMed and PDF strategies always say NO for this test
    # This forces the factory to make a HEAD request.
    def always_false_can_handle(url_param, response_headers=None):
        return False
    pubmed_instance_mock.can_handle_url = MagicMock(side_effect=always_false_can_handle)
    pdf_instance_mock.can_handle_url = MagicMock(side_effect=always_false_can_handle)
    
    # HTML strategy says yes, but only when called with headers (after HEAD)
    def html_fallback_logic(url_param, response_headers=None):
        if response_headers is not None and url_param == "http://example.com/unknown_type": # Called after HEAD
            return True
        return False # URL-only check should fail
    html_instance_mock.can_handle_url = MagicMock(side_effect=html_fallback_logic)

    url = "http://example.com/unknown_type"
    mock_head_response = MagicMock(spec=httpx.Response)
    # Simulate a generic content type or HEAD failure leading to no headers
    mock_head_response.headers = httpx.Headers({'Content-Type': 'application/octet-stream'}) 
    mock_head_response.url = url
    mock_http_client.head = MagicMock(return_value=mock_head_response)
    
    strategy = factory_with_mocked_strategies.get_strategy(url) # Use the new fixture

    assert isinstance(strategy, MagicMock)
    assert strategy == html_instance_mock
    mock_http_client.head.assert_called_once_with(url)
    # Ensure all strategies were checked
    pubmed_instance_mock.can_handle_url.assert_any_call(url, response_headers=None) # URL check
    pdf_instance_mock.can_handle_url.assert_any_call(url, response_headers=mock_head_response.headers) # HEAD check
    html_instance_mock.can_handle_url.assert_any_call(url, response_headers=mock_head_response.headers) # HEAD check


def test_get_strategy_no_strategy_found(
    factory_with_mocked_strategies: UrlProcessorFactory, # Use the new fixture
    mock_http_client: MagicMock,
    mock_html_strategy_class,
    mock_pdf_strategy_class,
    mock_pubmed_strategy_class
):
    """Test that None is returned if no strategy can handle the URL."""
    _, html_instance_mock = mock_html_strategy_class
    _, pdf_instance_mock = mock_pdf_strategy_class
    _, pubmed_instance_mock = mock_pubmed_strategy_class

    # All strategies say no
    html_instance_mock.can_handle_url = MagicMock(return_value=False)
    pdf_instance_mock.can_handle_url = MagicMock(return_value=False)
    pubmed_instance_mock.can_handle_url = MagicMock(return_value=False)

    url = "ftp://example.com/somefile.dat" # A URL no default strategy handles
    mock_http_client.head = MagicMock(side_effect=httpx.UnsupportedProtocol("FTP not supported"))

    strategy = factory_with_mocked_strategies.get_strategy(url) # Use the new fixture
    assert strategy is None
    mock_http_client.head.assert_called_once_with(url)


def test_get_strategy_head_request_fails(
    factory_with_mocked_strategies: UrlProcessorFactory, # Use the new fixture
    mock_http_client: MagicMock,
    mock_html_strategy_class, # Assume HTML might handle it as fallback
    mock_pubmed_strategy_class, # Added
    mock_pdf_strategy_class     # Added
):
    """Test strategy selection when HEAD request fails but a strategy can handle without headers."""
    _mock_pubmed_cls, pubmed_instance_mock = mock_pubmed_strategy_class
    _mock_pdf_cls, pdf_instance_mock = mock_pdf_strategy_class
    _mock_html_cls, html_instance_mock = mock_html_strategy_class
    
    # Ensure PubMed and PDF strategies always say NO during URL-only check
    def always_false_for_url_check(url_param, response_headers=None):
        if response_headers is None: # URL-only check
            return False
        return False # Default for other cases
    
    pubmed_instance_mock.can_handle_url = MagicMock(side_effect=always_false_for_url_check)
    pdf_instance_mock.can_handle_url = MagicMock(side_effect=always_false_for_url_check)

    # HTML strategy:
    # - Should say NO on the first pass (URL pattern check, response_headers=None)
    # - Should say YES on the second pass (after HEAD fail, response_headers=None)
    def html_can_handle_after_head_fail(url_param, response_headers=None):
        # This mock will be called twice by the factory for this URL.
        # 1. URL pattern check (response_headers=None)
        # 2. After HEAD fails (response_headers=None again)
        if url_param == "http://example.com/fallback_url" and response_headers is None:
            # If it's the second time it's called for this URL with no headers, it means HEAD failed.
            if html_instance_mock.can_handle_url.call_count > 1: # call_count is 1-based
                return True
        return False
    html_instance_mock.can_handle_url = MagicMock(side_effect=html_can_handle_after_head_fail)

    url = "http://example.com/fallback_url"
    mock_http_client.head = MagicMock(side_effect=httpx.RequestError("Network error during HEAD"))

    strategy = factory_with_mocked_strategies.get_strategy(url) # Use the new fixture

    assert isinstance(strategy, MagicMock)
    assert strategy == html_instance_mock
    mock_http_client.head.assert_called_once_with(url)
    # It should have been called twice: once with headers=None (URL check), once with headers=None (after HEAD fail)
    html_instance_mock.can_handle_url.assert_any_call(url, response_headers=None)


def test_factory_registration(mock_http_client: MagicMock):
    """Test custom strategy registration."""
    factory_instance = UrlProcessorFactory(http_client=mock_http_client)
    
    # Create a dummy strategy class for testing registration
    class DummyStrategy(UrlProcessorStrategy):
        def can_handle_url(self, url: str, response_headers: httpx.Headers | None = None) -> bool: return "dummy_url" in url
        def download_content(self, url: str): return "dummy_content"
        def extract_data(self, content, url: str): return {"text_content": content}
        def prepare_for_llm(self, extracted_data): return extracted_data

    factory_instance.register_strategy(DummyStrategy)
    
    # Check if DummyStrategy is called for its specific URL
    mock_dummy_instance = MagicMock(spec=DummyStrategy)
    mock_dummy_instance.can_handle_url = MagicMock(return_value=True)

    # Need to patch the DummyStrategy inside the factory's list or how it's called
    # This is simpler if we check the type of the returned strategy
    
    # Temporarily mock the __init__ of DummyStrategy to control instance creation
    with patch.object(DummyStrategy, '__init__', return_value=None) as mock_dummy_init:
        # Mock the can_handle_url on the prototype (class) if that's how it's checked first
        # Or ensure the instance returned by DummyStrategy() has can_handle_url mocked
        # For this test, let's assume the factory instantiates then calls can_handle_url
        
        # To properly test this, we'd need to mock the instantiation of DummyStrategy
        # when the factory iterates. A simpler check:
        
        # Re-initialize factory to clear default strategies for this specific test
        factory_instance_for_reg_test = UrlProcessorFactory(http_client=mock_http_client)
        factory_instance_for_reg_test._strategies = [] # Clear defaults
        factory_instance_for_reg_test.register_strategy(DummyStrategy)

        strategy_returned = factory_instance_for_reg_test.get_strategy("http://example.com/dummy_url")
        assert isinstance(strategy_returned, DummyStrategy)

        strategy_not_found = factory_instance_for_reg_test.get_strategy("http://example.com/other_url")
        assert strategy_not_found is None