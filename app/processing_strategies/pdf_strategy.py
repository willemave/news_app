"""
This module defines the strategy for processing PDF documents.
Simplified to only handle PDFs as bytes and pass them directly to the LLM.
"""
import httpx # For type hinting httpx.Headers
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

from app.http_client.robust_http_client import RobustHttpClient
from app.processing_strategies.base_strategy import UrlProcessorStrategy
from app.config import logger

class PdfProcessorStrategy(UrlProcessorStrategy):
    """
    Strategy for processing PDF documents.
    Downloads PDF content and passes bytes directly to the LLM for processing.
    No text extraction is performed - the LLM handles the PDF bytes directly.
    """
    def __init__(self, http_client: RobustHttpClient):
        super().__init__(http_client)

    def can_handle_url(self, url: str, response_headers: Optional[httpx.Headers] = None) -> bool:
        """
        Determines if this strategy can handle the given URL.
        Checks for 'application/pdf' in Content-Type or if URL ends with '.pdf'.
        """
        if response_headers:
            content_type = response_headers.get('content-type', '').lower()
            if 'application/pdf' in content_type:
                logger.debug(f"PdfStrategy can handle {url} based on Content-Type: {content_type}")
                return True
        
        # Fallback: check URL pattern if no headers
        if url.lower().endswith('.pdf'):
            logger.debug(f"PdfStrategy can handle {url} based on .pdf extension.")
            return True
        
        # Check for arXiv PDF URLs specifically, as they might not end with .pdf but are PDFs
        if "arxiv.org/pdf/" in url.lower():
            logger.debug(f"PdfStrategy can handle arXiv PDF URL: {url}")
            return True

        logger.debug(f"PdfStrategy cannot handle {url} based on current checks.")
        return False

    def download_content(self, url: str) -> bytes:
        """
        Downloads PDF content from the given URL.
        """
        logger.info(f"PdfStrategy: Downloading PDF content from {url}")
        response = self.http_client.get(url)
        # response.raise_for_status() is handled by RobustHttpClient
        logger.info(f"PdfStrategy: eessfully downloaded PDF from {url}. Final URL: {response.url}")
        return response.content # Returns PDF as bytes

    def extract_data(self, content: bytes, url: str) -> Dict[str, Any]:
        """
        Extracts basic metadata from PDF content.
        No text extraction is performed - the LLM will handle the PDF bytes directly.
        """
        logger.info(f"PdfStrategy: Preparing PDF data for URL: {url}")
        
        if not content:
            logger.warning(f"PdfStrategy: No PDF content provided for {url}")
            return {
                "title": "Extraction Failed (No PDF Content)",
                "content_type": "pdf",
                "final_url_after_redirects": url,
                "pdf_bytes": None,
            }

        # Use filename from URL as a fallback title
        parsed_url = urlparse(url)
        filename = parsed_url.path.split('/')[-1] or "PDF Document"
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"

        logger.info(f"PdfStrategy: Successfully prepared PDF data for {url}. Title: {filename}")
        return {
            "title": filename,
            "author": None,
            "publication_date": None,
            "text_content": None,  # No text extraction - LLM handles PDF bytes
            "content_type": "pdf",
            "final_url_after_redirects": url,
            "pdf_bytes": content,  # Store raw PDF bytes for LLM processing
        }

    def prepare_for_llm(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepares PDF data for LLM processing.
        Passes raw PDF bytes directly to the LLM for text extraction and summarization.
        """
        final_url = extracted_data.get('final_url_after_redirects', 'Unknown URL')
        logger.info(f"PdfStrategy: Preparing PDF data for LLM for URL: {final_url}")
        
        pdf_bytes = extracted_data.get("pdf_bytes")
        if not pdf_bytes:
            logger.error(f"PdfStrategy: No pdf_bytes found in extracted_data for {final_url}")
            return {
                "content_to_filter": None,  # PDFs skip text-based filtering
                "content_to_summarize": b"",  # Empty bytes as fallback
                "is_pdf": True
            }
            
        return {
            "content_to_filter": None,  # PDFs skip text-based filtering
            "content_to_summarize": pdf_bytes,  # Pass raw PDF bytes to LLM
            "is_pdf": True
        }

    def extract_internal_urls(self, content: bytes, original_url: str) -> List[str]:
        """
        Extracting URLs from PDF content is complex and not implemented for now.
        Returns an empty list.
        """
        logger.info(f"PdfStrategy: extract_internal_urls called for {original_url}. (Not implemented for PDF - returning empty list)")
        return []