"""Unit tests for robust synchronous HTTP client behavior."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest

from app.http_client.robust_http_client import RobustHttpClient


@pytest.fixture(autouse=True)
def mock_settings(mocker):
    """Patch global settings used by RobustHttpClient defaults."""
    settings_obj = SimpleNamespace(
        http_timeout_seconds=5.0,
        HTTP_CLIENT_USER_AGENT="TestClient/1.0",
    )
    mocker.patch("app.http_client.robust_http_client.settings", settings_obj)
    return settings_obj


@pytest.fixture
def mock_httpx_client(mocker):
    """Patch internal httpx.Client constructor and return a mock instance."""
    client = MagicMock(spec=httpx.Client)
    client.is_closed = False

    def _close() -> None:
        client.is_closed = True

    client.close.side_effect = _close
    mocker.patch("app.http_client.robust_http_client.httpx.Client", return_value=client)
    return client


def _mock_response(status_code: int = 200, text: str = "OK") -> MagicMock:
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.text = text
    response.history = []
    response.url = "https://example.com/final"
    response.headers = {}
    response.raise_for_status.return_value = None
    return response


def test_get_successful_uses_defaults(mock_settings, mock_httpx_client):
    """GET should use merged default headers and default timeout/redirect settings."""
    response = _mock_response()
    mock_httpx_client.get.return_value = response

    client = RobustHttpClient()
    result = client.get("https://example.com")

    assert result is response
    mock_httpx_client.get.assert_called_once_with(
        "https://example.com",
        headers={"User-Agent": "TestClient/1.0"},
        timeout=5.0,
        follow_redirects=True,
    )
    client.close()


def test_get_allows_custom_timeout_headers_and_redirects(mock_httpx_client):
    """Per-request overrides should be passed through to httpx.Client.get."""
    response = _mock_response(text="custom")
    mock_httpx_client.get.return_value = response

    client = RobustHttpClient(timeout=10.0, headers={"X-Base": "1"})
    result = client.get(
        "https://example.com/custom",
        headers={"X-Request": "2"},
        timeout=2.5,
        follow_redirects=False,
    )

    assert result.text == "custom"
    mock_httpx_client.get.assert_called_once_with(
        "https://example.com/custom",
        headers={"User-Agent": "TestClient/1.0", "X-Base": "1", "X-Request": "2"},
        timeout=2.5,
        follow_redirects=False,
    )
    client.close()


def test_get_stream_mode_enters_stream_context(mock_httpx_client):
    """Stream mode should invoke httpx stream context and return streamed response."""
    stream_response = MagicMock()
    stream_response.status_code = 200
    stream_response.history = []
    stream_response.url = "https://example.com/stream"
    stream_response.raise_for_status.return_value = None
    mock_httpx_client.stream.return_value = stream_response

    client = RobustHttpClient()
    result = client.get("https://example.com/stream", stream=True)

    assert result is stream_response
    stream_response.__enter__.assert_called_once_with()
    mock_httpx_client.stream.assert_called_once_with(
        "GET",
        "https://example.com/stream",
        headers=client.default_headers,
        timeout=client.default_timeout,
        follow_redirects=True,
    )
    client.close()


def test_get_http_status_error_is_raised(mock_httpx_client):
    """4xx/5xx status errors should bubble up as HTTPStatusError."""
    response = _mock_response(status_code=404, text="Not Found")
    request = httpx.Request("GET", "https://example.com/missing")
    response.request = request
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Not Found",
        request=request,
        response=response,
    )
    mock_httpx_client.get.return_value = response

    client = RobustHttpClient()
    with pytest.raises(httpx.HTTPStatusError):
        client.get("https://example.com/missing")
    client.close()


def test_get_retries_hostname_mismatch_by_removing_www(mock_httpx_client):
    """SSL hostname mismatch should retry using host variant without `www.`."""
    request = httpx.Request("GET", "https://www.example.com/path")
    ssl_error = httpx.RequestError(
        "certificate verify failed: Hostname mismatch",
        request=request,
    )
    retry_response = _mock_response()
    mock_httpx_client.get.side_effect = [ssl_error, retry_response]

    client = RobustHttpClient()
    result = client.get("https://www.example.com/path")

    assert result is retry_response
    assert mock_httpx_client.get.call_count == 2
    first_call_url = mock_httpx_client.get.call_args_list[0].args[0]
    second_call_url = mock_httpx_client.get.call_args_list[1].args[0]
    assert first_call_url == "https://www.example.com/path"
    assert second_call_url == "https://example.com/path"
    client.close()


def test_head_successful_uses_default_headers(mock_httpx_client):
    """HEAD should use the same header policy as GET."""
    response = _mock_response()
    mock_httpx_client.head.return_value = response

    client = RobustHttpClient()
    result = client.head("https://example.com/head")

    assert result is response
    mock_httpx_client.head.assert_called_once_with(
        "https://example.com/head",
        headers=client.default_headers,
        timeout=client.default_timeout,
    )
    client.close()


def test_head_retries_hostname_mismatch_using_head(mock_httpx_client):
    """HEAD hostname mismatch retry should call head() again on host variant."""
    request = httpx.Request("HEAD", "https://example.com/path")
    ssl_error = httpx.RequestError(
        "certificate verify failed: Hostname mismatch",
        request=request,
    )
    retry_response = _mock_response()
    mock_httpx_client.head.side_effect = [ssl_error, retry_response]

    client = RobustHttpClient()
    result = client.head("https://example.com/path")

    assert result is retry_response
    assert mock_httpx_client.head.call_count == 2
    first_call_url = mock_httpx_client.head.call_args_list[0].args[0]
    second_call_url = mock_httpx_client.head.call_args_list[1].args[0]
    assert first_call_url == "https://example.com/path"
    assert second_call_url == "https://www.example.com/path"
    client.close()


def test_close_closes_underlying_httpx_client(mock_httpx_client):
    """close() should close and reset underlying client reference."""
    client = RobustHttpClient()
    client.get("https://example.com")

    client.close()

    mock_httpx_client.close.assert_called_once_with()
    assert client._client is None
