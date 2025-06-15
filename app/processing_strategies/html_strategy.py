"""
This module defines the strategy for processing standard HTML web pages.
"""

import contextlib
from typing import Any

import html2text
import httpx  # For type hinting httpx.Headers
from dateutil import parser as date_parser  # For parsing dates from metadata
from firecrawl import FirecrawlApp
from trafilatura import extract

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.http_client.robust_http_client import RobustHttpClient
from app.processing_strategies.base_strategy import UrlProcessorStrategy
from app.utils.error_logger import create_error_logger

logger = get_logger(__name__)


class HtmlProcessorStrategy(UrlProcessorStrategy):
    """
    Strategy for processing standard HTML web pages.
    It downloads HTML content, extracts data using Trafilatura,
    and prepares it for LLM processing.
    """

    def __init__(self, http_client: RobustHttpClient):
        super().__init__(http_client)
        self.error_logger = create_error_logger("html_strategy")

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

    def can_handle_url(self, url: str, response_headers: httpx.Headers | None = None) -> bool:
        """
        Determines if this strategy can handle the given URL.
        Checks for 'text/html' in Content-Type or common HTML file extensions.
        """
        if response_headers:
            content_type = response_headers.get("content-type", "").lower()
            if "text/html" in content_type:
                logger.debug(f"HtmlStrategy can handle {url} based on Content-Type: {content_type}")
                return True

        # Fallback: check URL pattern if no headers (e.g. direct call without HEAD)
        # This is a loose check and might need refinement.
        # For now, assume if it's not clearly PDF or another specific type, it might be HTML.
        # The factory should prioritize more specific strategies first.
        if not url.lower().endswith((".pdf", ".xml", ".json", ".txt")) and url.lower().startswith(
            ("http://", "https://")
        ):
            # ArXiv PDF URLs are handled by ArxivStrategy or PdfStrategy.
            # This check ensures HtmlStrategy doesn't mistakenly claim them.
            if "arxiv.org/pdf/" in url.lower():
                logger.debug(
                    f"HtmlStrategy: URL {url} appears to be an arXiv PDF, "
                    "deferring to other strategies."
                )
                return False
            logger.debug(
                f"HtmlStrategy attempting to handle {url} based on URL pattern "
                "(not PDF/XML/JSON/TXT)."
            )
            return True  # A bit of a catch-all if no other strategy matches

        logger.debug(f"HtmlStrategy cannot handle {url} based on current checks.")
        return False

    def download_content(self, url: str) -> str:
        """
        Downloads HTML content from the given URL.
        """
        logger.info(f"HtmlStrategy: Downloading HTML content from {url}")
        response = self.http_client.get(url)
        # response.raise_for_status() is handled by RobustHttpClient
        logger.info(
            f"HtmlStrategy: Successfully downloaded HTML from {url}. Final URL: {response.url}"
        )
        return response.text  # Returns HTML as string

    def extract_data(self, content: str, url: str) -> dict[str, Any]:
        """
        Extracts data from HTML content using Trafilatura with fallback methods.
        'url' here is the final URL after any redirects from download_content.
        """
        logger.info(f"HtmlStrategy: Extracting data from HTML content for URL: {url}")

        # First attempt: Use trafilatura with enhanced options
        text_content = extract(
            filecontent=content,
            url=url,
            with_metadata=True,
            include_links=False,
            include_formatting=False,
            output_format="json",
            favor_recall=True,  # Favor recall over precision
            no_fallback=False,  # Enable fallback extraction
        )

        title = None
        author = None
        publication_date_str = None
        publication_date = None
        extracted_text = None

        if text_content:
            # Parse JSON output to extract metadata
            import json

            try:
                extracted_data = json.loads(text_content)
                title = extracted_data.get("title", "Untitled")
                author = extracted_data.get("author")
                extracted_text = extracted_data.get("text", "")
                publication_date_str = extracted_data.get("date")
            except (json.JSONDecodeError, AttributeError):
                logger.warning(f"Failed to parse Trafilatura JSON output for {url}")
                extracted_text = text_content

        # Fallback 1: Try html2text if Trafilatura fails
        if not extracted_text:
            logger.info(f"HtmlStrategy: Trafilatura failed, trying html2text for {url}")
            h = html2text.HTML2Text()
            h.ignore_links = True
            h.ignore_images = True
            h.ignore_emphasis = True
            h.body_width = 0  # Don't wrap lines

            try:
                extracted_text = h.handle(content)
                title = "Untitled (html2text)"
                logger.info(f"HtmlStrategy: html2text successfully extracted content for {url}")
            except Exception as e:
                logger.warning(f"HtmlStrategy: html2text failed for {url}: {str(e)}")
                extracted_text = None

        # Fallback 2: Try Firecrawl if html2text also fails
        settings = get_settings()
        if not extracted_text and settings.firecrawl_api_key:
            logger.info(f"HtmlStrategy: Trying Firecrawl for {url}")
            try:
                app = FirecrawlApp(api_key=settings.firecrawl_api_key)
                scrape_result = app.scrape_url(url, params={"formats": ["markdown", "html"]})

                if scrape_result and "markdown" in scrape_result:
                    extracted_text = scrape_result["markdown"]
                    title = scrape_result.get("metadata", {}).get("title", "Untitled (Firecrawl)")
                    author = scrape_result.get("metadata", {}).get("author", author)
                    logger.info(f"HtmlStrategy: Firecrawl successfully extracted content for {url}")
            except Exception as e:
                logger.warning(f"HtmlStrategy: Firecrawl failed for {url}: {str(e)}")

        # If all methods fail, return error response
        if not extracted_text:
            error_msg = f"All extraction methods failed for {url}"
            error = Exception(error_msg)
            self.error_logger.log_processing_error(
                item_id=url,
                error=error,
                operation="html_content_extraction",
                context={
                    "url": url,
                    "strategy": "html",
                    "methods_tried": ["trafilatura", "html2text", "firecrawl"],
                },
            )
            logger.error(f"HtmlStrategy: {error_msg}")
            return {
                "title": "Extraction Failed",
                "text_content": "",
                "content_type": "html",
                "final_url_after_redirects": url,
            }

        # Parse publication date if available
        if publication_date_str:
            with contextlib.suppress(date_parser.ParserError, ValueError):
                publication_date = date_parser.parse(publication_date_str)

        # Safely handle None title for logging
        title_preview = title[:50] if title else "None"
        logger.info(
            f"HtmlStrategy: Successfully extracted data for {url}. Title: {title_preview}..."
        )
        return {
            "title": title or "Untitled",
            "author": author,
            "publication_date": publication_date,
            "text_content": extracted_text,
            "content_type": "html",
            "final_url_after_redirects": url,
        }

    def prepare_for_llm(self, extracted_data: dict[str, Any]) -> dict[str, Any]:
        """
        Prepares extracted HTML data for LLM processing.
        """
        logger.info(
            f"HtmlStrategy: Preparing data for LLM for URL: "
            f"{extracted_data.get('final_url_after_redirects')}"
        )
        text_content = extracted_data.get("text_content", "")

        # Construct a meaningful input for filtering and summarization
        # This might include title and some metadata if helpful for the LLM
        # For now, primarily using the main text content.

        # Based on app.llm.py, filter_article and summarize_article take the content string.
        return {
            "content_to_filter": text_content,
            "content_to_summarize": text_content,
            "is_pdf": False,
        }

    def extract_internal_urls(self, content: str, original_url: str) -> list[str]:
        """
        Extracts internal URLs from HTML content for logging.
        This is a basic implementation; more sophisticated parsing might be needed.
        """
        # This is a placeholder. A more robust implementation would use BeautifulSoup
        # or a regex designed for URLs, and properly resolve relative URLs.
        # For now, returning empty as per "logging related links" and default.
        # If actual extraction is needed, this would be more complex.
        logger.info(
            f"HtmlStrategy: extract_internal_urls called for {original_url}. "
            "(Placeholder - returning empty list)"
        )
        return []
