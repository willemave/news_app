from typing import Optional, Dict, Any, Union, Set
from contextlib import asynccontextmanager
import httpx
import ssl
from urllib.parse import urlparse
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_not_exception_type
)

from app.core.settings import get_settings
from app.core.logging import get_logger
from app.utils.error_logger import create_error_logger

logger = get_logger(__name__)
settings = get_settings()

# Domains with known SSL issues that should use relaxed verification
SSL_BYPASS_DOMAINS: Set[str] = {
    '0x80.pl',
    # Add other problematic domains here
}

# HTTP status codes that should never be retried
NON_RETRYABLE_STATUS_CODES: Set[int] = {
    400, 401, 403, 404, 405, 406, 407, 408, 409, 410, 411, 412, 413, 414, 415, 416, 417, 418,
    421, 422, 423, 424, 425, 426, 428, 429, 431, 451  # Client errors
}

class NonRetryableError(Exception):
    """Exception for errors that should not be retried."""
    pass

def should_bypass_ssl(url: str) -> bool:
    """Check if URL domain should bypass SSL verification."""
    try:
        domain = urlparse(url).netloc.lower()
        return any(domain.endswith(bypass_domain) for bypass_domain in SSL_BYPASS_DOMAINS)
    except Exception:
        return False

def is_ssl_error(error: Exception) -> bool:
    """Check if error is SSL-related."""
    error_str = str(error).lower()
    return any(ssl_term in error_str for ssl_term in [
        'ssl', 'certificate', 'hostname mismatch', 'cert', 'tls'
    ])

def categorize_http_error(error: httpx.HTTPStatusError) -> Exception:
    """Categorize HTTP errors into retryable vs non-retryable."""
    status_code = error.response.status_code
    
    if status_code in NON_RETRYABLE_STATUS_CODES:
        return NonRetryableError(f"Non-retryable HTTP {status_code}: {error}")
    
    # 5xx errors are generally retryable
    if 500 <= status_code < 600:
        return error
    
    # Default to non-retryable for unknown status codes
    return NonRetryableError(f"Unknown status code {status_code}: {error}")

class HttpService:
    """Async HTTP client with intelligent retry logic and SSL handling."""
    
    def __init__(self):
        self.timeout = httpx.Timeout(
            timeout=settings.http_timeout_seconds,
            connect=10.0
        )
        # Enhanced user agent to avoid bot detection
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        self.error_logger = create_error_logger("http_service")
    
    @asynccontextmanager
    async def get_client(self, url: str = None):
        """Get an async HTTP client with appropriate SSL settings."""
        # Determine SSL verification settings
        verify_ssl = True
        if url and should_bypass_ssl(url):
            verify_ssl = False
            logger.warning(f"Bypassing SSL verification for {urlparse(url).netloc}")
        
        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers=self.headers,
            verify=verify_ssl
        ) as client:
            yield client
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        retry=retry_if_not_exception_type((NonRetryableError, httpx.HTTPStatusError))
    )
    async def fetch(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None
    ) -> httpx.Response:
        """
        Fetch a URL with intelligent retry logic.
        
        Args:
            url: URL to fetch
            headers: Additional headers
            
        Returns:
            httpx.Response object
        """
        async with self.get_client(url) as client:
            logger.debug(f"Fetching URL: {url}")
            
            request_headers = self.headers.copy()
            if headers:
                request_headers.update(headers)
            
            try:
                response = await client.get(url, headers=request_headers)
                response.raise_for_status()
                
                logger.debug(f"Successfully fetched {url}: {response.status_code}")
                return response
                
            except httpx.HTTPStatusError as e:
                # Categorize HTTP errors
                categorized_error = categorize_http_error(e)
                
                # Log the error
                self.error_logger.log_http_error(
                    url=url,
                    response=e.response,
                    error=e,
                    operation="http_fetch",
                    context={"status_code": e.response.status_code}
                )
                
                # Raise categorized error (may be NonRetryableError)
                raise categorized_error
                
            except httpx.ConnectError as e:
                # Check if this is an SSL error that shouldn't be retried
                if is_ssl_error(e):
                    logger.warning(f"SSL error for {url}: {e}")
                    self.error_logger.log_http_error(
                        url=url,
                        error=e,
                        operation="http_fetch",
                        context={"error_type": "ssl_error"}
                    )
                    raise NonRetryableError(f"SSL error: {e}")
                
                # Regular connection errors can be retried
                self.error_logger.log_http_error(
                    url=url,
                    error=e,
                    operation="http_fetch",
                    context={"error_type": "connection_error"}
                )
                raise
                
            except Exception as e:
                self.error_logger.log_http_error(
                    url=url,
                    error=e,
                    operation="http_fetch"
                )
                raise
    
    async def fetch_content(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None
    ) -> tuple[Union[str, bytes], Dict[str, str]]:
        """
        Fetch content and return both content and headers.
        
        Returns:
            Tuple of (content, response_headers)
        """
        response = await self.fetch(url, headers)
        
        content_type = response.headers.get('content-type', '').lower()
        
        # Return bytes for binary content
        if 'pdf' in content_type or 'octet-stream' in content_type:
            return response.content, dict(response.headers)
        
        # Return text for everything else
        return response.text, dict(response.headers)

# Global instance
_http_service = None

def get_http_service() -> HttpService:
    """Get the global HTTP service instance."""
    global _http_service
    if _http_service is None:
        _http_service = HttpService()
    return _http_service