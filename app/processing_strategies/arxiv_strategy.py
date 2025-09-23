"""
This module defines the strategy for processing arXiv web pages.
Simplified to pass PDF bytes directly to the LLM without any local processing.
"""

import re
from typing import Any
from urllib.parse import urlparse

import httpx  # For type hinting httpx.Headers

from app.core.logging import get_logger
from app.http_client.robust_http_client import RobustHttpClient
from app.processing_strategies.base_strategy import UrlProcessorStrategy

logger = get_logger(__name__)


class ArxivProcessorStrategy(UrlProcessorStrategy):
    """
    Strategy for processing arXiv abstract pages.
    It identifies URLs like 'https://arxiv.org/abs/...' and transforms them
    to their corresponding PDF URLs (e.g., 'https://arxiv.org/pdf/...'),
    then downloads and extracts content from the PDF.
    """

    def __init__(self, http_client: RobustHttpClient):
        super().__init__(http_client)
        # Pattern to match arXiv abstract URLs, including potential version numbers
        self.arxiv_abs_pattern = r"https://arxiv\.org/abs/(\d+\.\d+.*)"
        self.arxiv_pdf_template = r"https://arxiv.org/pdf/{paper_id}"

    def can_handle_url(self, url: str, response_headers: httpx.Headers | None = None) -> bool:
        """
        Determines if this strategy can handle the given URL, specifically looking for
        arXiv abstract page patterns.
        """
        is_arxiv_abs = bool(re.match(self.arxiv_abs_pattern, url))
        if is_arxiv_abs:
            logger.debug(f"ArxivStrategy can handle URL (is arXiv abstract): {url}")
            return True
        logger.debug(f"ArxivStrategy cannot handle URL: {url}")
        return False

    def preprocess_url(self, url: str) -> str:
        """
        Transforms an arXiv abstract URL (e.g., /abs/...) to its PDF version (e.g., /pdf/...).
        If the URL doesn't match the arXiv abstract pattern, it's returned unchanged.
        """
        match = re.match(self.arxiv_abs_pattern, url)
        if match:
            paper_id = match.group(1)
            pdf_url = self.arxiv_pdf_template.format(paper_id=paper_id)
            logger.info(
                "ArxivStrategy: Converted arXiv abstract URL %s to PDF URL %s",
                url,
                pdf_url,
            )
            return pdf_url
        # This case should ideally not be reached if can_handle_url was true,
        # but serves as a safeguard.
        logger.warning(
            "ArxivStrategy: preprocess_url called with non-matching URL %s; returning unchanged.",
            url,
        )
        return url

    def download_content(self, url: str) -> bytes:  # PDF content is bytes
        """
        Downloads the PDF content from the given URL.
        This method expects 'url' to be a direct link to a PDF file
        (transformed by preprocess_url if it was an abstract page).
        """
        logger.info(f"ArxivStrategy: Downloading PDF content from {url}")
        response = self.http_client.get(url)
        # RobustHttpClient handles raise_for_status
        logger.info(
            f"ArxivStrategy: Successfully downloaded PDF from {url}. Final URL: {response.url}"
        )
        return response.content

    def extract_data(self, content: bytes, url: str) -> dict[str, Any]:
        """
        Prepares PDF data for LLM processing.
        No local text extraction - the LLM will handle everything from the PDF bytes.
        """
        logger.info(
            "ArxivStrategy: Preparing PDF data for LLM processing for URL: %s", url
        )

        if not content:
            logger.warning(f"ArxivStrategy: No PDF content provided for {url}")
            return {
                "title": "Extraction Failed (No PDF Content)",
                "text_content": None,
                "content_type": "pdf",
                "final_url_after_redirects": url,
                "pdf_bytes": None,
            }

        # Use filename from URL as a fallback title - LLM will extract the real title
        parsed_url = urlparse(url)
        filename = parsed_url.path.split("/")[-1] or "ArXiv PDF Document"
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"

        logger.info(
            "ArxivStrategy: Successfully prepared PDF data for %s. Fallback title: %s",
            url,
            filename,
        )
        return {
            "title": filename,  # Fallback title - LLM will extract the real title
            "author": None,
            "publication_date": None,
            "text_content": None,  # No text extraction - LLM handles PDF bytes
            "content_type": "pdf",
            "final_url_after_redirects": url,
            "pdf_bytes": content,  # Store raw PDF bytes for LLM processing
        }

    def prepare_for_llm(self, extracted_data: dict[str, Any]) -> dict[str, Any]:
        """
        Prepares PDF data for LLM processing.
        Passes raw PDF bytes directly to the LLM for title extraction and summarization.
        """
        final_url = extracted_data.get("final_url_after_redirects", "Unknown URL")
        logger.info("ArxivStrategy: Preparing PDF data for LLM for URL: %s", final_url)
        pdf_bytes = extracted_data.get("pdf_bytes")

        if pdf_bytes is None:
            logger.error(
                "ArxivStrategy: PDF bytes not found in extracted_data for %s", final_url
            )
            return {
                "content_to_filter": None,  # PDFs skip text-based filtering
                "content_to_summarize": b"",  # Empty bytes as fallback
                "is_pdf": True,
            }

        return {
            "content_to_filter": None,  # PDFs skip text-based filtering
            "content_to_summarize": pdf_bytes,  # Pass raw PDF bytes to LLM
            "is_pdf": True,
        }

    def extract_internal_urls(self, content: bytes, original_url: str) -> list[str]:
        """
        Extracts internal URLs. For PDFs, this is typically not applicable in the same
        way as HTML, so an empty list is returned.
        """
        logger.info(
            "ArxivStrategy: extract_internal_urls called for %s (PDF). Returning empty list.",
            original_url,
        )
        return []
