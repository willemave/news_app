import re
from abc import ABC, abstractmethod
from urllib.parse import urljoin, urlparse

from app.core.logging import get_logger
from app.models.metadata import ProcessingResult

logger = get_logger(__name__)


class ProcessingStrategy(ABC):
    """Base class for all content processing strategies."""

    @abstractmethod
    def can_handle(self, url: str, headers: dict[str, str] | None = None) -> bool:
        """Check if this strategy can handle the given URL."""
        pass

    @abstractmethod
    async def process(self, url: str, content: str | None = None) -> ProcessingResult:
        """Process the content and return results."""
        pass

    def extract_internal_links(self, content: str, base_url: str) -> list[str]:
        """Extract internal links from content. Override if needed."""
        # Default implementation for HTML content
        if not content:
            return []

        links = []
        # Simple regex for href links (override for better parsing)
        href_pattern = re.compile(r'href=[\'"]?([^\'" >]+)', re.IGNORECASE)

        for match in href_pattern.finditer(content):
            link = match.group(1)
            # Convert relative to absolute URLs
            absolute_url = urljoin(base_url, link)

            # Only keep links from same domain
            if urlparse(absolute_url).netloc == urlparse(base_url).netloc:
                links.append(absolute_url)

        return list(set(links))  # Remove duplicates

    def preprocess_url(self, url: str) -> str:
        """Preprocess URL before fetching. Override if needed."""
        return url.strip()

    @staticmethod
    def is_pdf_url(url: str) -> bool:
        """Check if URL likely points to a PDF."""
        return url.lower().endswith(".pdf") or "/pdf/" in url.lower()

    @staticmethod
    def is_media_content(headers: dict[str, str] | None) -> bool:
        """Check if content type indicates media (image, video, audio)."""
        if not headers:
            return False

        content_type = headers.get("content-type", "").lower()
        media_types = ["image/", "video/", "audio/"]

        return any(media in content_type for media in media_types)
