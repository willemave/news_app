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
    It downloads HTML content using crawl4ai with optimized content extraction,
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
        elif "substack.com" in url:
            return "Substack"
        elif "medium.com" in url:
            return "Medium"
        elif "chinatalk.media" in url:
            return "ChinaTalk"
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

    def _get_source_specific_config(self, source: str) -> dict[str, Any]:
        """Get source-specific configuration for crawl4ai."""
        # Base configuration
        config = {
            "word_count_threshold": 20,
            "excluded_tags": ["script", "style", "nav", "footer", "header"],
            "exclude_external_links": True,
            "remove_overlay_elements": True,
        }
        
        # Source-specific adjustments
        if source == "Substack":
            config["excluded_tags"].extend(["form", "aside"])
            config["excluded_selector"] = ".subscribe-widget, .footer-wrap, .subscription-form-wrapper"
            config["target_elements"] = [".post", ".post-content", "article"]
        elif source == "Medium":
            config["excluded_selector"] = ".metabar, .js-postActions, .js-stickyFooter"
            config["target_elements"] = ["article", ".postArticle", ".section-content"]
        elif source in ["PubMed", "PMC"]:
            # Keep more scientific content
            config["excluded_tags"] = ["script", "style", "nav", "footer"]
            config["target_elements"] = [".article", ".abstract", ".body", ".content", "main"]
            config["word_count_threshold"] = 10  # Lower threshold for scientific content
        elif source == "ChinaTalk":
            config["target_elements"] = [".post-content", ".post", "article"]
            config["excluded_selector"] = ".subscribe-widget, .comments-section"
        elif source == "Arxiv":
            # ArXiv PDFs need special handling
            config["pdf"] = True
            
        return config

    async def _extract_with_crawl4ai(self, url: str) -> dict[str, Any]:
        """Extract content using crawl4ai with optimized settings."""
        source = self._detect_source(url)
        
        # Configure browser
        browser_config = BrowserConfig(
            headless=True,
            viewport_width=1920,  # Wider viewport for better content capture
            viewport_height=1080,
            text_mode=False,  # Keep images for now, filter later if needed
            light_mode=True,  # Performance optimization
            ignore_https_errors=True,
            java_script_enabled=True,  # Need JS for many modern sites
            extra_args=["--disable-blink-features=AutomationControlled"],  # Stealth
        )
        
        # Get source-specific configuration
        source_config = self._get_source_specific_config(source)
        
        # Configure crawler run
        run_config = CrawlerRunConfig(
            # Content filtering
            word_count_threshold=source_config.get("word_count_threshold", 20),
            excluded_tags=source_config.get("excluded_tags", []),
            excluded_selector=source_config.get("excluded_selector"),
            target_elements=source_config.get("target_elements"),
            exclude_external_links=source_config.get("exclude_external_links", True),
            
            # Content processing
            process_iframes=False,
            remove_overlay_elements=source_config.get("remove_overlay_elements", True),
            remove_forms=True,  # Usually don't need forms in article content
            keep_data_attributes=False,  # Clean up HTML
            
            # Page handling
            wait_until="domcontentloaded",  # Faster than networkidle
            wait_for="body",
            delay_before_return_html=1.0,  # Reduced delay
            adjust_viewport_to_content=True,
            
            # Performance
            cache_mode=CacheMode.ENABLED,  # Use cache for repeated visits
            verbose=False,  # Less logging
            
            # Link filtering
            exclude_social_media_links=True,
            exclude_domains=["facebook.com", "twitter.com", "instagram.com", "linkedin.com"],
            
            # Special handling
            pdf=source_config.get("pdf", False),
            check_robots_txt=False,  # Speed over compliance for news aggregation
        )
        
        try:
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=run_config)
                
                if result.success:
                    # Get content
                    content = ""
                    if hasattr(result, 'markdown') and result.markdown:
                        if hasattr(result.markdown, 'raw_markdown'):
                            content = result.markdown.raw_markdown
                        elif isinstance(result.markdown, str):
                            content = result.markdown
                        else:
                            content = str(result.markdown)
                    
                    return {
                        "success": True,
                        "content": content,
                        "title": result.metadata.get("title") if result.metadata else None,
                        "final_url": result.url,
                        "cleaned_html": result.cleaned_html,
                        "links": result.links,
                        "media": result.media,
                    }
                else:
                    return {
                        "success": False,
                        "error": result.error_message or "Unknown error"
                    }
        except Exception as e:
            logger.error(f"Crawl4ai extraction error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def extract_data(self, content: str, url: str) -> dict[str, Any]:
        """
        Extracts data from HTML content using crawl4ai.
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
                    r"(?:By|Author|Written by)[:\s]+([^\n]+)",
                    r"<meta[^>]+name=[\"']author[\"'][^>]+content=[\"']([^\"']+)[\"']",
                ]
                
                # First check cleaned HTML for meta tags
                cleaned_html = result.get("cleaned_html", "")
                if cleaned_html:
                    for pattern in author_patterns[1:]:  # Meta tag patterns
                        match = re.search(pattern, cleaned_html, re.IGNORECASE)
                        if match:
                            author = match.group(1).strip()
                            break
                
                # Then check markdown content
                if not author:
                    for pattern in author_patterns[:1]:  # Text patterns
                        match = re.search(pattern, extracted_text, re.IGNORECASE)
                        if match:
                            author = match.group(1).strip()
                            # Clean up author if it contains extra content
                            if len(author) > 100:  # Likely grabbed too much
                                author = None
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
                "source": source,  # Source field for categorization
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