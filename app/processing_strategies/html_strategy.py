"""
This module defines the strategy for processing standard HTML web pages.
"""
import httpx # For type hinting httpx.Headers
from typing import Optional, Dict, Any, List
from trafilatura import bare_extraction
from dateutil import parser as date_parser # For parsing dates from metadata

from app.http_client.robust_http_client import RobustHttpClient
from app.processing_strategies.base_strategy import UrlProcessorStrategy
from app.config import logger

class HtmlProcessorStrategy(UrlProcessorStrategy):
    """
    Strategy for processing standard HTML web pages.
    It downloads HTML content, extracts data using Trafilatura,
    and prepares it for LLM processing.
    """
    def __init__(self, http_client: RobustHttpClient):
        super().__init__(http_client)

    def preprocess_url(self, url: str) -> str:
        """
        Currently, HTML strategy does not perform any preprocessing on the URL.
        This method is kept for consistency with the base class.
        If specific HTML URL transformations are needed in the future,
        they can be implemented here.
        """
        if "arxiv.org/abs/" in url:
            logger.debug(f"HtmlStrategy: Transforming arXiv URL {url}")
            return url.replace("/abs/", "/pdf/")
        logger.debug(f"HtmlStrategy: preprocess_url called for {url}, no transformation applied.")
        return url

    def can_handle_url(self, url: str, response_headers: Optional[httpx.Headers] = None) -> bool:
        """
        Determines if this strategy can handle the given URL.
        Checks for 'text/html' in Content-Type or common HTML file extensions.
        """
        if response_headers:
            content_type = response_headers.get('content-type', '').lower()
            if 'text/html' in content_type:
                logger.debug(f"HtmlStrategy can handle {url} based on Content-Type: {content_type}")
                return True
        
        # Fallback: check URL pattern if no headers (e.g. direct call without HEAD)
        # This is a loose check and might need refinement.
        # For now, assume if it's not clearly PDF or another specific type, it might be HTML.
        # The factory should prioritize more specific strategies first.
        if not url.lower().endswith(('.pdf', '.xml', '.json', '.txt')) and url.lower().startswith(('http://', 'https://')):
            # ArXiv PDF URLs are handled by ArxivStrategy or PdfStrategy.
            # This check ensures HtmlStrategy doesn't mistakenly claim them if already processed to PDF form.
            if "arxiv.org/pdf/" in url.lower():
                logger.debug(f"HtmlStrategy: URL {url} appears to be an arXiv PDF, deferring to other strategies.")
                return False
            logger.debug(f"HtmlStrategy attempting to handle {url} based on URL pattern (not PDF/XML/JSON/TXT).")
            return True # A bit of a catch-all if no other strategy matches

        logger.debug(f"HtmlStrategy cannot handle {url} based on current checks.")
        return False

    def download_content(self, url: str) -> str:
        """
        Downloads HTML content from the given URL.
        """
        logger.info(f"HtmlStrategy: Downloading HTML content from {url}")
        response = self.http_client.get(url)
        # response.raise_for_status() is handled by RobustHttpClient
        logger.info(f"HtmlStrategy: Successfully downloaded HTML from {url}. Final URL: {response.url}")
        return response.text # Returns HTML as string

    def extract_data(self, content: str, url: str) -> Dict[str, Any]:
        """
        Extracts data from HTML content using Trafilatura.
        'url' here is the final URL after any redirects from download_content.
        """
        logger.info(f"HtmlStrategy: Extracting data from HTML content for URL: {url}")
        if not content:
            logger.warning(f"HtmlStrategy: No content to extract for {url}")
            return {
                "title": "Extraction Failed (No Content)",
                "text_content": "",
                "content_type": "html",
                "final_url_after_redirects": url,
            }

        extracted_data_trafilatura = bare_extraction(
            filecontent=content,
            url=url, # Provide URL for better context to Trafilatura
            with_metadata=True,
            include_links=False, # As per plan, internal URLs handled by extract_internal_urls
            include_formatting=False # Simpler text for LLM
        )

        if not extracted_data_trafilatura:
            logger.warning(f"HtmlStrategy: Trafilatura failed to extract content from {url}")
            return {
                "title": "Extraction Failed (Trafilatura)",
                "text_content": "",
                "content_type": "html",
                "final_url_after_redirects": url,
            }

        title = extracted_data_trafilatura.get("title", "Untitled")
        author = extracted_data_trafilatura.get("author")
        text_content = extracted_data_trafilatura.get("text", "")
        
        publication_date_str = extracted_data_trafilatura.get("date")
        publication_date = None
        if publication_date_str:
            try:
                publication_date = date_parser.parse(publication_date_str).strftime('%Y-%m-%d')
            except (date_parser.ParserError, ValueError) as e:
                logger.warning(f"HtmlStrategy: Could not parse date '{publication_date_str}' for {url}: {e}")
        
        if len(text_content) < 100: # Arbitrary threshold for meaningful content
            logger.warning(f"HtmlStrategy: Content too short after extraction for {url}. Length: {len(text_content)}")
            # Potentially return less or mark as low quality

        logger.info(f"HtmlStrategy: Successfully extracted data for {url}. Title: {title[:50]}...")
        return {
            "title": title or "Untitled",
            "author": author,
            "publication_date": publication_date,
            "text_content": text_content,
            "content_type": "html",
            "final_url_after_redirects": url,
            # "original_url_from_db" will be added by the main processor
        }

    def prepare_for_llm(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepares extracted HTML data for LLM processing.
        """
        logger.info(f"HtmlStrategy: Preparing data for LLM for URL: {extracted_data.get('final_url_after_redirects')}")
        text_content = extracted_data.get("text_content", "")
        
        # Construct a meaningful input for filtering and summarization
        # This might include title and some metadata if helpful for the LLM
        # For now, primarily using the main text content.
        
        # Based on app.llm.py, filter_article and summarize_article take the content string.
        return {
            "content_to_filter": text_content,
            "content_to_summarize": text_content,
            "is_pdf": False
        }

    def extract_internal_urls(self, content: str, original_url: str) -> List[str]:
        """
        Extracts internal URLs from HTML content for logging.
        This is a basic implementation; more sophisticated parsing might be needed.
        """
        # This is a placeholder. A more robust implementation would use BeautifulSoup
        # or a regex designed for URLs, and properly resolve relative URLs.
        # For now, returning empty as per "logging related links" and default.
        # If actual extraction is needed, this would be more complex.
        logger.info(f"HtmlStrategy: extract_internal_urls called for {original_url}. (Placeholder - returning empty list)")
        return []