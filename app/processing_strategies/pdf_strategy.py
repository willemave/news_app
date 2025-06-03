"""
This module defines the strategy for processing PDF documents.
"""
import base64
import httpx # For type hinting httpx.Headers
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

from app.http_client.robust_http_client import RobustHttpClient
from app.processing_strategies.base_strategy import UrlProcessorStrategy
from app.config import logger

class PdfProcessorStrategy(UrlProcessorStrategy):
    """
    Strategy for processing PDF documents.
    It downloads PDF content, extracts basic metadata (like filename as title),
    and prepares it (as bytes) for LLM processing.
    """
    def __init__(self, http_client: RobustHttpClient):
        super().__init__(http_client)

    async def can_handle_url(self, url: str, response_headers: Optional[httpx.Headers] = None) -> bool:
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

    async def download_content(self, url: str) -> bytes:
        """
        Downloads PDF content from the given URL.
        """
        logger.info(f"PdfStrategy: Downloading PDF content from {url}")
        response = await self.http_client.get(url)
        # response.raise_for_status() is handled by RobustHttpClient
        logger.info(f"PdfStrategy: Successfully downloaded PDF from {url}. Final URL: {response.url}")
        return response.content # Returns PDF as bytes

    async def extract_data(self, content: bytes, url: str) -> Dict[str, Any]:
        """
        Extracts data from PDF content.
        'url' here is the final URL after any redirects from download_content.
        For PDFs, the primary "content" for the LLM is the PDF bytes themselves.
        Text extraction could be done here (e.g. with PyPDF2) if needed before LLM,
        but current app.llm.summarize_pdf takes bytes.
        """
        logger.info(f"PdfStrategy: Extracting data from PDF content for URL: {url}")
        
        if not content:
            logger.warning(f"PdfStrategy: No PDF content to extract for {url}")
            return {
                "title": "Extraction Failed (No PDF Content)",
                "binary_content_b64": None,
                "content_type": "pdf",
                "final_url_after_redirects": url,
            }

        # Use filename from URL as a fallback title
        parsed_url = urlparse(url)
        filename = parsed_url.path.split('/')[-1] or "PDF Document"
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf" # Ensure it looks like a PDF filename

        pdf_content_base64 = base64.b64encode(content).decode('utf-8')

        logger.info(f"PdfStrategy: Successfully prepared PDF data for {url}. Title: {filename}")
        return {
            "title": filename,
            "author": None, # PDF metadata extraction is more complex, skip for now
            "publication_date": None, # Skip for now
            "text_content": None, # Raw text extraction not done here, LLM handles bytes
            "binary_content_b64": pdf_content_base64, # LLM might prefer raw bytes
            "raw_bytes": content, # Provide raw bytes as well, LLM function can choose
            "content_type": "pdf",
            "final_url_after_redirects": url,
            # "original_url_from_db" will be added by the main processor
        }

    async def prepare_for_llm(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepares extracted PDF data for LLM processing.
        The primary content is the PDF itself (bytes).
        """
        logger.info(f"PdfStrategy: Preparing PDF data for LLM for URL: {extracted_data.get('final_url_after_redirects')}")
        
        # app.llm.summarize_pdf expects raw PDF bytes.
        # app.llm.filter_article expects text. PDFs currently bypass direct text filtering in processor.py
        # If filtering is desired for PDFs based on text, text extraction would need to happen first.
        # For now, aligning with existing llm.py which summarizes PDF bytes directly.
        
        raw_bytes = extracted_data.get("raw_bytes")
        if not raw_bytes:
            logger.error(f"PdfStrategy: No raw_bytes found in extracted_data for LLM preparation for {extracted_data.get('final_url_after_redirects')}")
            # This case should ideally not happen if download and extract_data worked.
            # Return a structure that indicates an issue or use placeholder.
            return {
                "content_to_filter": None, # PDFs might skip text-based filtering
                "content_to_summarize": b"", # Empty bytes
                "is_pdf": True
            }
            
        return {
            "content_to_filter": None, # PDFs might skip text-based filtering in the current setup
            "content_to_summarize": raw_bytes, # Pass raw bytes to llm.summarize_pdf
            "is_pdf": True
        }

    async def extract_internal_urls(self, content: bytes, original_url: str) -> List[str]:
        """
        Extracting URLs from PDF content is complex and not implemented for now.
        Returns an empty list.
        """
        logger.info(f"PdfStrategy: extract_internal_urls called for {original_url}. (Not implemented for PDF - returning empty list)")
        return []