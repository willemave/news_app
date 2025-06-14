from typing import Optional, Dict, Any, Union
from contextlib import asynccontextmanager
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from app.core.settings import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

class HttpService:
    """Async HTTP client with retry logic."""
    
    def __init__(self):
        self.timeout = httpx.Timeout(
            timeout=settings.http_timeout_seconds,
            connect=10.0
        )
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; NewsAggregator/1.0)'
        }
    
    @asynccontextmanager
    async def get_client(self):
        """Get an async HTTP client."""
        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers=self.headers
        ) as client:
            yield client
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError))
    )
    async def fetch(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None
    ) -> httpx.Response:
        """
        Fetch a URL with retry logic.
        
        Args:
            url: URL to fetch
            headers: Additional headers
            
        Returns:
            httpx.Response object
        """
        async with self.get_client() as client:
            logger.debug(f"Fetching URL: {url}")
            
            request_headers = self.headers.copy()
            if headers:
                request_headers.update(headers)
            
            response = await client.get(url, headers=request_headers)
            response.raise_for_status()
            
            logger.debug(f"Successfully fetched {url}: {response.status_code}")
            return response
    
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