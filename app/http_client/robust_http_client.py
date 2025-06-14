"""
This module provides a robust synchronous HTTP client.
"""
import httpx
from typing import Optional, Dict

from app.core.settings import get_settings
from app.core.logging import get_logger
from app.utils.error_logger import create_error_logger

settings = get_settings()
logger = get_logger(__name__)

# Default values, can be overridden by settings
DEFAULT_TIMEOUT = 10.0
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36)"

class RobustHttpClient:
    """
    A robust synchronous HTTP client for making GET and HEAD requests.
    It handles redirects, timeouts, and common HTTP errors.
    """
    def __init__(
        self,
        timeout: Optional[float] = None,
        headers: Optional[Dict[str, str]] = None
    ):
        """
        Initializes the RobustHttpClient.

        Args:
            timeout: Default timeout for requests in seconds.
                     Falls back to settings.HTTP_CLIENT_TIMEOUT or DEFAULT_TIMEOUT.
            headers: Default headers for requests.
                     Merges with a default User-Agent from settings or DEFAULT_USER_AGENT.
        """
        self.default_timeout = timeout or getattr(settings, 'http_timeout_seconds', DEFAULT_TIMEOUT)
        
        base_headers = {
            'User-Agent': getattr(settings, 'HTTP_CLIENT_USER_AGENT', DEFAULT_USER_AGENT)
        }
        if headers:
            base_headers.update(headers)
        self.default_headers = base_headers

        self._client: Optional[httpx.Client] = None
        self.error_logger = create_error_logger("robust_http_client")

    def _get_client(self) -> httpx.Client:
        """Initializes and returns the httpx.Client instance."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                headers=self.default_headers,
                timeout=self.default_timeout,
                follow_redirects=True  # Default to follow redirects
            )
        return self._client

    def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        stream: bool = False
    ) -> httpx.Response:
        """
        Performs a synchronous GET request.

        Args:
            url: The URL to request.
            headers: Optional headers to include in the request, overriding defaults.
            timeout: Optional timeout for this specific request, overriding default.
            stream: Whether to stream the response content.

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

        logger.info(f"Making GET request to {url} with timeout {effective_timeout}s (stream={stream})")
        try:
            if stream:
                response = client.stream('GET', url, headers=request_headers, timeout=effective_timeout)
                response.__enter__()  # Enter the context manager
            else:
                response = client.get(url, headers=request_headers, timeout=effective_timeout)
            
            response.raise_for_status()  # Raise an exception for 4XX or 5XX status codes
            logger.info(f"GET request to {url} successful, status: {response.status_code}")
            if response.history:
                logger.info(f"Request to {url} was redirected. Final URL: {response.url}")
                for i, r in enumerate(response.history):
                    logger.debug(f"Redirect {i+1}: {r.url} ({r.status_code}) -> {r.headers.get('Location')}")
            return response
        except httpx.HTTPStatusError as e:
            self.error_logger.log_http_error(
                url=url,
                response=e.response,
                error=e,
                operation="http_get",
                context={"status_code": e.response.status_code}
            )
            logger.error(f"HTTP error {e.response.status_code} for GET {url}: {e.response.text[:200]}")
            raise
        except httpx.RequestError as e:
            self.error_logger.log_http_error(
                url=url,
                error=e,
                operation="http_get"
            )
            logger.error(f"Request error for GET {url}: {e}")
            raise

    def head(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None
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
            response.raise_for_status() # Raise an exception for 4XX or 5XX status codes
            logger.info(f"HEAD request to {url} successful, status: {response.status_code}")
            if response.history:
                logger.info(f"HEAD request to {url} was redirected. Final URL: {response.url}")
                for i, r in enumerate(response.history):
                    logger.debug(f"Redirect {i+1}: {r.url} ({r.status_code}) -> {r.headers.get('Location')}")
            return response
        except httpx.HTTPStatusError as e:
            self.error_logger.log_http_error(
                url=url,
                response=e.response,
                error=e,
                operation="http_head",
                context={"status_code": e.response.status_code}
            )
            logger.error(f"HTTP error {e.response.status_code} for HEAD {url}: {e.response.text[:200]}")
            raise
        except httpx.RequestError as e:
            self.error_logger.log_http_error(
                url=url,
                error=e,
                operation="http_head"
            )
            logger.error(f"Request error for HEAD {url}: {e}")
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