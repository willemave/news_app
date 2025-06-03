import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock

from app.http_client.robust_http_client import RobustHttpClient
from app.config import Settings # To potentially override settings for testing

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_settings(mocker):
    """Fixture to mock app.config.settings if needed for overriding client defaults."""
    mock_settings_obj = Settings(
        HTTP_CLIENT_TIMEOUT=5.0, # Custom test timeout
        HTTP_CLIENT_USER_AGENT="TestApp/1.0"
    )
    mocker.patch('app.http_client.robust_http_client.settings', mock_settings_obj)
    return mock_settings_obj

@pytest.fixture
async def http_client(mock_settings): # Use mock_settings to ensure testable defaults
    """Fixture to provide an instance of RobustHttpClient and ensure it's closed."""
    client = RobustHttpClient(timeout=mock_settings.HTTP_CLIENT_TIMEOUT) # Use mocked timeout
    yield client
    await client.close()

@pytest.fixture
def mock_async_client(mocker):
    """Mocks the internal httpx.AsyncClient instance."""
    mock = AsyncMock(spec=httpx.AsyncClient)
    mock.is_closed = False # Simulate an open client initially
    
    # Mock the aclose method
    async def mock_aclose():
        mock.is_closed = True
    mock.aclose = MagicMock(side_effect=mock_aclose)

    mocker.patch('httpx.AsyncClient', return_value=mock)
    return mock


async def test_get_successful(http_client: RobustHttpClient, mock_async_client: MagicMock):
    """Test successful GET request."""
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value={"key": "value"})
    mock_response.text = "Success"
    mock_response.history = []
    mock_response.url = "http://example.com"
    
    async def mock_get_op(*args, **kwargs):
        return mock_response
    mock_async_client.get = MagicMock(side_effect=mock_get_op)

    # Re-initialize client to use the mocked httpx.AsyncClient
    # This is a bit tricky because RobustHttpClient initializes its client lazily.
    # We need to ensure our mock_async_client is used.
    # One way is to patch httpx.AsyncClient *before* RobustHttpClient is instantiated
    # or ensure _get_client() uses the patched version.
    # The fixture `mock_async_client` already patches `httpx.AsyncClient` globally for the test.
    
    client_instance = RobustHttpClient() # This will now use the mocked AsyncClient due to the patch

    url = "http://example.com"
    response = await client_instance.get(url)

    mock_async_client.get.assert_called_once_with(url, headers=client_instance.default_headers, timeout=client_instance.default_timeout)
    assert response.status_code == 200
    assert response.text == "Success"
    await client_instance.close()


async def test_head_successful(http_client: RobustHttpClient, mock_async_client: MagicMock):
    """Test successful HEAD request."""
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "text/html"}
    mock_response.history = []
    mock_response.url = "http://example.com"

    async def mock_head_op(*args, **kwargs):
        return mock_response
    mock_async_client.head = MagicMock(side_effect=mock_head_op)
    
    client_instance = RobustHttpClient()

    url = "http://example.com"
    response = await client_instance.head(url)

    mock_async_client.head.assert_called_once_with(url, headers=client_instance.default_headers, timeout=client_instance.default_timeout)
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "text/html"
    await client_instance.close()


async def test_get_http_error(http_client: RobustHttpClient, mock_async_client: MagicMock):
    """Test GET request that results in an HTTPStatusError."""
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 404
    mock_response.text = "Not Found"
    mock_response.request = httpx.Request("GET", "http://example.com/notfound")
    
    # Configure raise_for_status mock on the response object itself
    mock_response.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError("Not Found", request=mock_response.request, response=mock_response))

    async def mock_get_op_error(*args, **kwargs):
        return mock_response # Return the mock response that will then raise on .raise_for_status()
    mock_async_client.get = MagicMock(side_effect=mock_get_op_error)

    client_instance = RobustHttpClient()
    url = "http://example.com/notfound"

    with pytest.raises(httpx.HTTPStatusError) as excinfo:
        await client_instance.get(url)
    
    assert excinfo.value.response.status_code == 404
    mock_async_client.get.assert_called_once()
    await client_instance.close()


async def test_get_request_error(http_client: RobustHttpClient, mock_async_client: MagicMock):
    """Test GET request that results in a RequestError (e.g., network issue)."""
    mock_request = httpx.Request("GET", "http://example.com/networkissue")
    
    async def mock_get_op_req_error(*args, **kwargs):
        raise httpx.RequestError("Network error", request=mock_request)
    mock_async_client.get = MagicMock(side_effect=mock_get_op_req_error)

    client_instance = RobustHttpClient()
    url = "http://example.com/networkissue"

    with pytest.raises(httpx.RequestError):
        await client_instance.get(url)
    
    mock_async_client.get.assert_called_once()
    await client_instance.close()


async def test_client_closure(mock_async_client: MagicMock):
    """Test that the underlying httpx.AsyncClient is closed."""
    # Need to instantiate RobustHttpClient for its _get_client to be called
    client = RobustHttpClient()
    # Call a method to ensure the client is initialized
    try:
        await client.get("http://example.com") 
    except: # We don't care about the outcome of get, just that _get_client was called
        pass

    await client.close()
    # Assert that the mock's aclose was called
    mock_async_client.aclose.assert_called_once()
    assert client._client is None # Check internal state if accessible, or rely on mock_aclose


async def test_get_with_redirect(http_client: RobustHttpClient, mock_async_client: MagicMock):
    """Test GET request with redirects."""
    original_url = "http://example.com/redirect"
    final_url = "http://example.com/final"

    history_response1 = AsyncMock(spec=httpx.Response)
    history_response1.status_code = 301
    history_response1.url = original_url
    history_response1.headers = {'Location': 'http://example.com/intermediate'}

    history_response2 = AsyncMock(spec=httpx.Response)
    history_response2.status_code = 302
    history_response2.url = 'http://example.com/intermediate'
    history_response2.headers = {'Location': final_url}
    
    final_mock_response = AsyncMock(spec=httpx.Response)
    final_mock_response.status_code = 200
    final_mock_response.text = "Final Content"
    final_mock_response.url = final_url # httpx.AsyncClient(follow_redirects=True) updates response.url
    final_mock_response.history = [history_response1, history_response2]

    async def mock_get_redirect(*args, **kwargs):
        # The actual httpx.AsyncClient handles redirects internally when follow_redirects=True.
        # So, the mock for client.get() should just return the *final* response.
        # The `response.history` attribute is populated by the real client.
        return final_mock_response
        
    mock_async_client.get = MagicMock(side_effect=mock_get_redirect)
    
    client_instance = RobustHttpClient()
    response = await client_instance.get(original_url)

    mock_async_client.get.assert_called_once_with(original_url, headers=client_instance.default_headers, timeout=client_instance.default_timeout)
    assert response.status_code == 200
    assert response.url == final_url
    assert len(response.history) == 2
    assert response.history[0].url == original_url
    assert response.history[1].url == 'http://example.com/intermediate'
    await client_instance.close()

async def test_custom_headers_and_timeout(http_client: RobustHttpClient, mock_async_client: MagicMock):
    """Test providing custom headers and timeout to a GET request."""
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.text = "Customized"
    mock_response.history = []
    mock_response.url = "http://example.com/custom"

    async def mock_get_custom(*args, **kwargs):
        # Check that custom headers and timeout are passed to the underlying client
        assert kwargs['headers']['X-Custom-Header'] == 'TestValue'
        assert kwargs['timeout'] == 2.5
        return mock_response
    mock_async_client.get = MagicMock(side_effect=mock_get_custom)

    client_instance = RobustHttpClient()
    url = "http://example.com/custom"
    custom_headers = {"X-Custom-Header": "TestValue"}
    custom_timeout = 2.5

    response = await client_instance.get(url, headers=custom_headers, timeout=custom_timeout)

    # The assertion is within mock_get_custom for this test
    mock_async_client.get.assert_called_once() 
    assert response.status_code == 200
    await client_instance.close()