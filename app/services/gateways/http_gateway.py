"""Unified HTTP gateway for service and workflow orchestration."""

from __future__ import annotations

import httpx

from app.http_client.robust_http_client import RobustHttpClient
from app.services.http import HttpService, get_http_service


class HttpGateway:
    """Facade over project HTTP clients with stable method signatures."""

    def __init__(
        self,
        http_service: HttpService | None = None,
        robust_client: RobustHttpClient | None = None,
    ) -> None:
        self._http_service = http_service or get_http_service()
        self._robust_client = robust_client or RobustHttpClient()

    def fetch_content(
        self,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> tuple[str | bytes, dict[str, str]]:
        """Fetch URL content and response headers."""
        return self._http_service.fetch_content(url, headers=headers)

    def fetch(self, url: str, headers: dict[str, str] | None = None) -> httpx.Response:
        """Perform GET request with retry semantics."""
        return self._http_service.fetch(url, headers=headers)

    def head(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        allow_statuses: set[int] | None = None,
    ) -> httpx.Response:
        """Perform HEAD request with retry semantics."""
        return self._http_service.head(url, headers=headers, allow_statuses=allow_statuses)

    def robust_get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        follow_redirects: bool = True,
    ) -> httpx.Response:
        """Execute GET using hostname-mismatch tolerant robust client."""
        return self._robust_client.get(
            url,
            headers=headers,
            timeout=timeout,
            follow_redirects=follow_redirects,
        )

    def robust_head(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        """Execute HEAD using hostname-mismatch tolerant robust client."""
        return self._robust_client.head(url, headers=headers, timeout=timeout)

    def close(self) -> None:
        """Release robust client resources."""
        self._robust_client.close()


_http_gateway: HttpGateway | None = None


def get_http_gateway() -> HttpGateway:
    """Return a cached HTTP gateway."""
    global _http_gateway
    if _http_gateway is None:
        _http_gateway = HttpGateway()
    return _http_gateway
