"""
This module defines the strategy for processing standard HTML web pages using crawl4ai.
"""

import asyncio
import contextlib
import re
from typing import Any

import httpx  # For type hinting httpx.Headers
import nest_asyncio
from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CacheMode,
    CrawlerRunConfig,
    DefaultMarkdownGenerator,
    LLMConfig,
    LLMContentFilter,
)
from dateutil import parser as date_parser  # For parsing dates from metadata

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.http_client.robust_http_client import RobustHttpClient
from app.processing_strategies.base_strategy import UrlProcessorStrategy
from app.utils.error_logger import create_error_logger

logger = get_logger(__name__)

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()


class HtmlProcessorStrategy(UrlProcessorStrategy):
    """
    Strategy for processing standard HTML web pages.
    It downloads HTML content using crawl4ai with LLM-based content extraction,
    and prepares it for further processing.
    """

    def __init__(self, http_client: RobustHttpClient):
        super().__init__(http_client)
        self.error_logger = create_error_logger("html_strategy")
        self.settings = get_settings()

    def _detect_source(self, url: str) -> str:
        """Detect the source type from URL."""
        if "pubmed.ncbi.nlm.nih.gov" in url or "pmc.ncbi.nlm.nih.gov" in url:
            return "PubMed"
        elif "arxiv.org" in url:
            return "Arxiv"
        else:
            return "web"

    def preprocess_url(self, url: str) -> str:
        """
        Preprocess URLs to ensure we get the full content.
        - Transform PubMed URLs to PMC full-text URLs
        - Transform ArXiv abstract URLs to PDF URLs
        """
        # Handle PubMed URLs - transform to PMC full-text if available
        pubmed_match = re.match(r"https?://pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", url)
        if pubmed_match:
            pmid = pubmed_match.group(1)
            pmc_url = f"https://pmc.ncbi.nlm.nih.gov/articles/pmid/{pmid}/"
            logger.debug(f"HtmlStrategy: Transforming PubMed URL {url} to PMC URL {pmc_url}")
            return pmc_url

        # Handle ArXiv URLs - transform abstract to PDF
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
        For crawl4ai, we'll use the extract_data method directly since it handles downloading.
        This method remains for compatibility with the base class.
        """
        logger.info(f"HtmlStrategy: download_content called for {url}")
        # We'll actually download in extract_data using crawl4ai
        return url  # Return the URL itself as a placeholder

    def _get_extraction_instruction(self, source: str) -> str:
        """Get source-specific extraction instructions for the LLM."""
        base_instruction = """
        Focus on extracting the core educational and informational content.
        Include:
        - Main article content
        - Key concepts and explanations
        - Important facts and findings
        - Code examples if present
        - Essential technical details
        
        Exclude:
        - Navigation elements
        - Sidebars and advertisements
        - Footer content
        - Cookie notices
        - Social media links
        
        Extract metadata if available:
        - Title
        - Author(s)
        - Publication date
        
        Format the output as clean markdown with proper headers and structure.
        """

        if source == "PubMed":
            return (
                base_instruction
                + """
            
            For PubMed/PMC articles, also include:
            - Abstract
            - Introduction
            - Methods
            - Results
            - Discussion
            - Conclusions
            - References (main ones)
            """
            )
        elif source == "Arxiv":
            return (
                base_instruction
                + """
            
            For ArXiv papers, also include:
            - Abstract
            - All sections of the paper
            - Mathematical formulas (in LaTeX format if possible)
            - Algorithms and pseudocode
            - Experimental results
            """
            )
        else:
            return base_instruction

    async def _extract_with_crawl4ai(self, url: str) -> dict[str, Any]:
        """Extract content using crawl4ai with LLM filtering."""
        source = self._detect_source(url)

        # Configure browser
        browser_config = BrowserConfig(headless=True, viewport_width=1280, viewport_height=720)

        # Configure LLM for content filtering
        llm_config = LLMConfig(
            provider="gemini/gemini-2.5-flash-preview-05-20", api_token="env:GOOGLE_API_KEY"
        )

        # Initialize LLM filter with specific instruction
        content_filter = LLMContentFilter(
            llm_config=llm_config,
            instruction=self._get_extraction_instruction(source),
            chunk_token_threshold=2000,  # Increased to reduce chunks
            verbose=True,
        )

        # Configure markdown generator
        markdown_generator = DefaultMarkdownGenerator(
            content_filter=content_filter, options={"ignore_links": True}
        )

        # Configure crawler run
        run_config = CrawlerRunConfig(
            markdown_generator=markdown_generator,
            cache_mode=CacheMode.BYPASS,
            wait_for="body",
            delay_before_return_html=2.0,  # Wait for dynamic content
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=run_config)

            if result.success:
                # Handle the new markdown format
                content = ""
                if hasattr(result, 'markdown') and result.markdown:
                    if hasattr(result.markdown, 'raw_markdown'):
                        content = result.markdown.raw_markdown
                    else:
                        content = str(result.markdown)
                
                return {
                    "success": True,
                    "content": content,
                    "title": result.metadata.get("title") if result.metadata else None,
                    "final_url": result.url,
                }
            else:
                return {"success": False, "error": result.error_message or "Unknown error"}

    def extract_data(self, content: str, url: str) -> dict[str, Any]:
        """
        Extracts data from HTML content using crawl4ai with LLM-based extraction.
        'content' parameter is ignored as crawl4ai handles downloading.
        'url' here is the final URL after any preprocessing.
        """
        logger.info(f"HtmlStrategy: Extracting data from {url}")

        # Detect source for metadata
        source = self._detect_source(url)

        try:
            # With nest_asyncio, we can safely run async code
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're already in an event loop, use it
                result = loop.run_until_complete(self._extract_with_crawl4ai(url))
            else:
                # No running loop, use asyncio.run
                result = asyncio.run(self._extract_with_crawl4ai(url))

            if not result["success"]:
                raise Exception(
                    f"Crawl4ai extraction failed: {result.get('error', 'Unknown error')}"
                )

            # Extract metadata from content if not provided
            extracted_text = result["content"]
            title = result.get("title", "Untitled")
            author = None
            publication_date = None

            # Try to extract metadata from the content
            if extracted_text:
                # Simple pattern matching for common metadata patterns
                # Author patterns
                author_patterns = [
                    r"(?:Author|By|Written by)[:\s]+([^\n]+)",
                    r"<meta[^>]+name=[\"']author[\"'][^>]+content=[\"']([^\"']+)[\"']",
                ]
                for pattern in author_patterns:
                    match = re.search(pattern, extracted_text, re.IGNORECASE)
                    if match:
                        author = match.group(1).strip()
                        break

                # Date patterns
                date_patterns = [
                    r"(?:Published|Date|Posted)[:\s]+([^\n]+\d{4}[^\n]*)",
                    r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
                    r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})",
                ]
                for pattern in date_patterns:
                    match = re.search(pattern, extracted_text, re.IGNORECASE)
                    if match:
                        date_str = match.group(1).strip()
                        with contextlib.suppress(date_parser.ParserError, ValueError):
                            publication_date = date_parser.parse(date_str)
                        if publication_date:
                            break

            logger.info(
                f"HtmlStrategy: Successfully extracted data for {url}. "
                f"Title: {title[:50]}... Source: {source}"
            )

            return {
                "title": title,
                "author": author,
                "publication_date": publication_date,
                "text_content": extracted_text,
                "content_type": "html",
                "source": source,  # New field
                "final_url_after_redirects": result.get("final_url", url),
            }

        except Exception as e:
            error_msg = f"Content extraction failed for {url}: {str(e)}"
            self.error_logger.log_processing_error(
                item_id=url,
                error=e,
                operation="html_content_extraction",
                context={
                    "url": url,
                    "strategy": "html",
                    "source": source,
                    "method": "crawl4ai",
                },
            )
            logger.error(f"HtmlStrategy: {error_msg}")

            return {
                "title": "Extraction Failed",
                "text_content": "",
                "content_type": "html",
                "source": source,
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
        logger.info(
            f"HtmlStrategy: extract_internal_urls called for {original_url}. "
            "(Placeholder - returning empty list)"
        )
        return []

