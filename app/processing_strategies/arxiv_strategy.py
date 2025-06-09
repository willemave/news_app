"""
This module defines the strategy for processing arXiv web pages.
"""
import re
import io
from typing import Optional, Dict, Any, List

import httpx  # For type hinting httpx.Headers
import pdfplumber # For PDF processing

from app.http_client.robust_http_client import RobustHttpClient
from app.processing_strategies.base_strategy import UrlProcessorStrategy
from app.config import logger

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
        self.arxiv_abs_pattern = r'https://arxiv\.org/abs/(\d+\.\d+.*)'
        self.arxiv_pdf_template = r'https://arxiv.org/pdf/{paper_id}'

    def can_handle_url(self, url: str, response_headers: Optional[httpx.Headers] = None) -> bool:
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
            logger.info(f"ArxivStrategy: Converted arXiv abstract URL {url} to PDF URL {pdf_url}")
            return pdf_url
        # This case should ideally not be reached if can_handle_url was true,
        # but serves as a safeguard.
        logger.warning(f"ArxivStrategy: preprocess_url called with non-matching URL {url}, returning unchanged.")
        return url

    def download_content(self, url: str) -> bytes: # PDF content is bytes
        """
        Downloads the PDF content from the given URL.
        This method expects 'url' to be a direct link to a PDF file
        (transformed by preprocess_url if it was an abstract page).
        """
        logger.info(f"ArxivStrategy: Downloading PDF content from {url}")
        response = self.http_client.get(url)
        # RobustHttpClient handles raise_for_status
        logger.info(f"ArxivStrategy: Successfully downloaded PDF from {url}. Final URL: {response.url}")
        return response.content

    def extract_data(self, content: bytes, url: str) -> Dict[str, Any]:
        """
        Extracts text and metadata from the downloaded PDF content.
        'url' is the final URL from which the PDF was downloaded.
        """
        logger.info(f"ArxivStrategy: Extracting data from PDF content for URL: {url}")
        text_content = ""
        # Default title, attempt to update from PDF metadata
        title = "Untitled arXiv PDF Document"

        if not content:
            logger.warning(f"ArxivStrategy: No PDF content provided for extraction for URL {url}")
            return {
                "title": "Extraction Failed (No PDF Content)",
                "text_content": "",
                "content_type": "pdf",
                "final_url_after_redirects": url,
            }

        try:
            with io.BytesIO(content) as pdf_file_stream:
                with pdfplumber.open(pdf_file_stream) as pdf_doc:
                    # Attempt to extract title from PDF metadata
                    if pdf_doc.metadata and isinstance(pdf_doc.metadata, dict):
                        meta_title = pdf_doc.metadata.get('title')
                        if isinstance(meta_title, (str, bytes)):
                            if isinstance(meta_title, bytes):
                                try:
                                    title = meta_title.decode('utf-8', errors='replace')
                                except UnicodeDecodeError:
                                    # Fallback to latin-1 if utf-8 fails
                                    title = meta_title.decode('latin-1', errors='replace')
                            else:
                                title = meta_title
                        elif meta_title is not None: # Handle other types by converting to string
                            title = str(meta_title)
                    
                    extracted_pages = []
                    for page in pdf_doc.pages:
                        page_text = page.extract_text()
                        if page_text:
                            extracted_pages.append(page_text)
                    text_content = "\n".join(extracted_pages)

            if not text_content.strip():
                logger.warning(f"ArxivStrategy: pdfplumber extracted no text from PDF at {url}")
                text_content = "Content extraction from PDF yielded no text (pdfplumber)."

        except pdfplumber.exceptions.PDFSyntaxError as e:
            logger.error(f"ArxivStrategy: PDFSyntaxError while processing {url}: {e}")
            return {
                "title": title, # Use title extracted so far or default
                "text_content": f"Failed to parse PDF due to syntax error: {e}",
                "content_type": "pdf",
                "final_url_after_redirects": url,
            }
        except Exception as e:
            logger.error(f"ArxivStrategy: Unexpected error extracting PDF text for {url}: {e}", exc_info=True)
            return {
                "title": title, # Use title extracted so far or default
                "text_content": f"An unexpected error occurred during PDF text extraction: {e}",
                "content_type": "pdf",
                "final_url_after_redirects": url,
            }

        logger.info(f"ArxivStrategy: Successfully extracted data for PDF {url}. Title: '{title[:60]}...'")
        return {
            "title": title,
            "author": None,  # PDF author metadata can be unreliable; not extracted by default
            "publication_date": None,  # PDF date metadata can be unreliable
            "text_content": text_content,
            "content_type": "pdf", # Explicitly state content type
            "final_url_after_redirects": url,
        }

    def prepare_for_llm(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepares the extracted PDF data for processing by an LLM.
        """
        final_url = extracted_data.get('final_url_after_redirects', 'Unknown URL')
        logger.info(f"ArxivStrategy: Preparing PDF data for LLM for URL: {final_url}")
        text_content = extracted_data.get("text_content", "")
        
        return {
            "content_to_filter": text_content,
            "content_to_summarize": text_content,
            "is_pdf": True  # Indicate that the content is from a PDF
        }

    def extract_internal_urls(self, content: bytes, original_url: str) -> List[str]:
        """
        Extracts internal URLs. For PDFs, this is typically not applicable in the same
        way as HTML, so an empty list is returned.
        """
        logger.info(f"ArxivStrategy: extract_internal_urls called for {original_url} (PDF). Returning empty list.")
        return []