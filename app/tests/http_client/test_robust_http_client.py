"""Tests for RobustHttpClient hostname retry behavior."""

import httpx

from app.http_client.robust_http_client import RobustHttpClient


class _StubClient:
    def __init__(self, response: httpx.Response):
        self._response = response

    def get(self, url: str, headers: dict[str, str], timeout: float) -> httpx.Response:
        return self._response


def test_hostname_mismatch_retry_uses_variant():
    """Hostname mismatch triggers retry with non-www host."""
    client = RobustHttpClient()
    retry_url = "https://vpri.org/some/path"
    response = httpx.Response(200, request=httpx.Request("GET", retry_url))

    def _stub_get_client():
        return _StubClient(response)

    client._get_client = _stub_get_client  # type: ignore[method-assign]

    retry_response = client._maybe_retry_hostname_mismatch(
        url="https://www.vpri.org/some/path",
        error_message="CERTIFICATE_VERIFY_FAILED: Hostname mismatch",
        headers={},
        timeout=5.0,
        stream=False,
    )

    assert retry_response is not None
    assert str(retry_response.request.url) == retry_url
