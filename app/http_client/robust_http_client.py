"""
This module provides a robust synchronous HTTP client.
"""

from urllib.parse import urlparse, urlunparse

import httpx

from app.core.logging import get_logger
from app.core.settings import get_settings

settings = get_settings()
logger = get_logger(__name__)

# Default values, can be overridden by settings
DEFAULT_TIMEOUT = 10.0
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36)"
)


class RobustHttpClient:
    """
    A robust synchronous HTTP client for making GET and HEAD requests.
    It handles redirects, timeouts, and common HTTP errors.
    """

    def __init__(self, timeout: float | None = None, headers: dict[str, str] | None = None):
        """
        Initializes the RobustHttpClient.

        Args:
            timeout: Default timeout for requests in seconds.
                     Falls back to settings.HTTP_CLIENT_TIMEOUT or DEFAULT_TIMEOUT.
            headers: Default headers for requests.
                     Merges with a default User-Agent from settings or DEFAULT_USER_AGENT.
        """
        self.default_timeout = timeout or getattr(settings, "http_timeout_seconds", DEFAULT_TIMEOUT)

        base_headers = {
            "User-Agent": getattr(settings, "HTTP_CLIENT_USER_AGENT", DEFAULT_USER_AGENT)
        }
        if headers:
            base_headers.update(headers)
        self.default_headers = base_headers

        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        """Initializes and returns the httpx.Client instance."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                headers=self.default_headers,
                timeout=self.default_timeout,
                follow_redirects=True,  # Default to follow redirects
            )
        return self._client

    def _build_host_variant(self, url: str, host: str) -> str:
        parsed = urlparse(url)
        return urlunparse(parsed._replace(netloc=host))

    def _maybe_retry_hostname_mismatch(
        self,
        url: str,
        error_message: str,
        headers: dict[str, str],
        timeout: float,
        method: str,
        stream: bool,
        follow_redirects: bool = True,
    ) -> httpx.Response | None:
        message = error_message.lower()
        if (
            "certificate verify failed" not in message
            and "certificate_verify_failed" not in message
        ) or "hostname mismatch" not in message:
            return None
        parsed = urlparse(url)
        host = parsed.netloc
        if not host:
            return None
        variant = None
        if host.startswith("www."):
            variant = host[4:]
        elif "." in host:
            variant = f"www.{host}"
        if not variant or variant == host:
            return None
        retry_url = self._build_host_variant(url, variant)
        logger.warning(
            "Retrying request with host variant due to SSL hostname mismatch: %s -> %s",
            url,
            retry_url,
            extra={
                "component": "robust_http_client",
                "operation": "host_variant_retry",
                "context_data": {"url": url, "retry_url": retry_url},
            },
        )
        client = self._get_client()
        if method == "HEAD":
            response = client.head(
                retry_url,
                headers=headers,
                timeout=timeout,
                follow_redirects=follow_redirects,
            )
        elif stream:
            response = client.stream(
                "GET",
                retry_url,
                headers=headers,
                timeout=timeout,
                follow_redirects=follow_redirects,
            )
            response.__enter__()
        else:
            response = client.get(
                retry_url,
                headers=headers,
                timeout=timeout,
                follow_redirects=follow_redirects,
            )
        response.raise_for_status()
        return response

    def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        stream: bool = False,
        follow_redirects: bool = True,
    ) -> httpx.Response:
        """
        Performs a synchronous GET request.

        Args:
            url: The URL to request.
            headers: Optional headers to include in the request, overriding defaults.
            timeout: Optional timeout for this specific request, overriding default.
            stream: Whether to stream the response content.
            follow_redirects: Whether this request should follow redirects.

        Returns:
            An httpx.Response object.

        Raises:
            httpx.HTTPStatusError: For 4xx or 5xx responses.
            httpx.RequestError: For other network-related errors.
        """
        client = self._get_client()
        request_headers = self.default_headers.copy()
        if headers:
            request_headers.update(headers)

        effective_timeout = timeout if timeout is not None else self.default_timeout

        logger.info(
            f"Making GET request to {url} with timeout {effective_timeout}s (stream={stream})"
        )
        try:
            if stream:
                response = client.stream(
                    "GET",
                    url,
                    headers=request_headers,
                    timeout=effective_timeout,
                    follow_redirects=follow_redirects,
                )
                response.__enter__()  # Enter the context manager
            else:
                response = client.get(
                    url,
                    headers=request_headers,
                    timeout=effective_timeout,
                    follow_redirects=follow_redirects,
                )

            response.raise_for_status()  # Raise an exception for 4XX or 5XX status codes
            logger.info(f"GET request to {url} successful, status: {response.status_code}")
            if response.history:
                logger.info(f"Request to {url} was redirected. Final URL: {response.url}")
                for index, redirect_response in enumerate(response.history, start=1):
                    location_header = redirect_response.headers.get("Location")
                    logger.debug(
                        "Redirect %s: %s (%s) -> %s",
                        index,
                        redirect_response.url,
                        redirect_response.status_code,
                        location_header,
                    )
            return response
        except httpx.HTTPStatusError as e:
            logger.error(
                "HTTP error %s for GET %s: %s",
                e.response.status_code,
                url,
                e.response.text[:200],
                extra={
                    "component": "robust_http_client",
                    "operation": "http_get",
                    "context_data": {"url": url, "status_code": e.response.status_code},
                },
            )
            raise
        except httpx.RequestError as e:
            if "certificate verify failed" in str(e).lower():
                try:
                    retry_response = self._maybe_retry_hostname_mismatch(
                        url=url,
                        error_message=str(e),
                        headers=request_headers,
                        timeout=effective_timeout,
                        method="GET",
                        stream=stream,
                        follow_redirects=follow_redirects,
                    )
                    if retry_response is not None:
                        return retry_response
                except Exception as retry_exc:  # noqa: BLE001
                    logger.exception(
                        "Host variant retry failed for GET %s: %s",
                        url,
                        retry_exc,
                        extra={
                            "component": "robust_http_client",
                            "operation": "http_get",
                            "context_data": {"url": url, "retry_error": str(retry_exc)},
                        },
                    )
            logger.exception(
                "Request error for GET %s: %s",
                url,
                e,
                extra={
                    "component": "robust_http_client",
                    "operation": "http_get",
                    "context_data": {"url": url},
                },
            )
            raise

    def head(
        self, url: str, headers: dict[str, str] | None = None, timeout: float | None = None
    ) -> httpx.Response:
        """
        Performs a synchronous HEAD request.

        Args:
            url: The URL to request.
            headers: Optional headers to include in the request, overriding defaults.
            timeout: Optional timeout for this specific request, overriding default.

        Returns:
            An httpx.Response object.

        Raises:
            httpx.HTTPStatusError: For 4xx or 5xx responses.
            httpx.RequestError: For other network-related errors.
        """
        client = self._get_client()
        request_headers = self.default_headers.copy()
        if headers:
            request_headers.update(headers)

        effective_timeout = timeout if timeout is not None else self.default_timeout

        logger.info(f"Making HEAD request to {url} with timeout {effective_timeout}s")
        try:
            response = client.head(url, headers=request_headers, timeout=effective_timeout)
            response.raise_for_status()  # Raise an exception for 4XX or 5XX status codes
            logger.info(f"HEAD request to {url} successful, status: {response.status_code}")
            if response.history:
                logger.info(f"HEAD request to {url} was redirected. Final URL: {response.url}")
                for index, redirect_response in enumerate(response.history, start=1):
                    location_header = redirect_response.headers.get("Location")
                    logger.debug(
                        "Redirect %s: %s (%s) -> %s",
                        index,
                        redirect_response.url,
                        redirect_response.status_code,
                        location_header,
                    )
            return response
        except httpx.HTTPStatusError as e:
            logger.error(
                "HTTP error %s for HEAD %s: %s",
                e.response.status_code,
                url,
                e.response.text[:200],
                extra={
                    "component": "robust_http_client",
                    "operation": "http_head",
                    "context_data": {"url": url, "status_code": e.response.status_code},
                },
            )
            raise
        except httpx.RequestError as e:
            if "certificate verify failed" in str(e).lower():
                try:
                    retry_response = self._maybe_retry_hostname_mismatch(
                        url=url,
                        error_message=str(e),
                        headers=request_headers,
                        timeout=effective_timeout,
                        method="HEAD",
                        stream=False,
                    )
                    if retry_response is not None:
                        return retry_response
                except Exception as retry_exc:  # noqa: BLE001
                    logger.exception(
                        "Host variant retry failed for HEAD %s: %s",
                        url,
                        retry_exc,
                        extra={
                            "component": "robust_http_client",
                            "operation": "http_head",
                            "context_data": {"url": url, "retry_error": str(retry_exc)},
                        },
                    )
            logger.exception(
                "Request error for HEAD %s: %s",
                url,
                e,
                extra={
                    "component": "robust_http_client",
                    "operation": "http_head",
                    "context_data": {"url": url},
                },
            )
            raise

    def close(self) -> None:
        """
        Closes the underlying httpx.Client.
        Should be called when the client is no longer needed, e.g., at application shutdown.
        """
        if self._client and not self._client.is_closed:
            logger.info("Closing RobustHttpClient")
            self._client.close()
            self._client = None
        else:
            logger.info("RobustHttpClient already closed or not initialized.")


# Example usage (for testing or demonstration, typically not here)
# def main():
#     http_client = RobustHttpClient()
#     try:
#         # response = http_client.get("https://httpbin.org/get")
#         # print(response.json())
#         # response_head = http_client.head("https://httpbin.org/status/200")
#         # print(response_head.headers)
#         response_redirect = http_client.get("https://httpbin.org/redirect/2")
#         print(f"Final URL after redirects: {response_redirect.url}")
#         print(f"Content: {response_redirect.text[:100]}")
#
#     except httpx.HTTPStatusError as e:
#         print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
#     except httpx.RequestError as e:
#         print(f"Request Error: {e}")
#     finally:
#         http_client.close()

# if __name__ == "__main__":
#     main()
