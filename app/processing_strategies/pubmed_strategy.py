"""
This module defines the strategy for processing PubMed article pages.
Its primary role is to extract the full-text link and delegate further processing.
"""
import httpx # For type hinting httpx.Headers
import re
from typing import Optional, Dict, Any, List
from bs4 import BeautifulSoup

from app.http_client.robust_http_client import RobustHttpClient
from app.processing_strategies.base_strategy import UrlProcessorStrategy
from app.core.logging import get_logger

logger = get_logger(__name__)

class PubMedProcessorStrategy(UrlProcessorStrategy):
    """
    Strategy for processing PubMed article pages.
    It downloads the PubMed page, extracts the link to the full-text article,
    and then signals for delegation to another strategy (HTML or PDF)
    to process the actual full-text content.
    """
    def __init__(self, http_client: RobustHttpClient):
        super().__init__(http_client)

    def can_handle_url(self, url: str, response_headers: Optional[httpx.Headers] = None) -> bool:
        """
        Determines if this strategy can handle the given URL.
        Checks if the URL is a PubMed article page.
        """
        # Check if it's a PubMed abstract/article page, not a direct PDF or other content link from PubMed.
        # Example: https://pubmed.ncbi.nlm.nih.gov/1234567/
        if 'pubmed.ncbi.nlm.nih.gov' in url.lower() and not url.lower().endswith(('.pdf', '.html', '.htm')):
            # A more specific regex could be used if needed, e.g., to match /<PMID>/
            if re.search(r'pubmed\.ncbi\.nlm\.nih\.gov/\d+/?$', url.lower()):
                logger.debug(f"PubMedStrategy can handle PubMed article page: {url}")
                return True
        logger.debug(f"PubMedStrategy cannot handle URL: {url} (not a typical PubMed article page URL)")
        return False

    def download_content(self, url: str) -> str:
        """
        Downloads the HTML content of the PubMed article page.
        """
        logger.info(f"PubMedStrategy: Downloading PubMed page HTML from {url}")
        response = self.http_client.get(url)
        # response.raise_for_status() is handled by RobustHttpClient
        logger.info(f"PubMedStrategy: Successfully downloaded PubMed page HTML from {url}. Final URL: {response.url}")
        return response.text

    def _extract_full_text_link_from_html(self, pubmed_page_html: str, pubmed_url: str) -> Optional[str]:
        """
        Helper to extract the full text link from PubMed page HTML.
        This logic is similar to the one previously in processor.py.
        """
        try:
            soup = BeautifulSoup(pubmed_page_html, 'html.parser')
            
            # Look for full text links section (multiple selectors for robustness)
            full_text_section = soup.find('div', {'class': 'full-text-links-list'})
            if not full_text_section:
                full_text_section = soup.find('aside', {'id': 'full-text-links'})
            if not full_text_section:
                 # Try finding by heading text then parent
                heading = soup.find(['h3', 'h4', 'strong'], string=re.compile(r'Full.*text.*links', re.IGNORECASE))
                if heading:
                    full_text_section = heading.find_parent('div') # Common parent

            if full_text_section:
                links = full_text_section.find_all('a', href=True)
                
                # Prioritize PMC links
                pmc_link = None
                first_link = None

                for link_tag in links:
                    href = link_tag.get('href')
                    if not href:
                        continue

                    # Resolve relative URLs
                    if href.startswith('//'):
                        href = 'https:' + href
                    elif href.startswith('/'):
                        # Ensure base is correct for pubmed or ncbi domain
                        base_domain = "https://www.ncbi.nlm.nih.gov" if "ncbi.nlm.nih.gov" in pubmed_url else "https://pubmed.ncbi.nlm.nih.gov"
                        href = base_domain + href
                    
                    if not first_link: # Keep track of the very first valid link
                        first_link = href

                    if 'pmc' in href.lower() and ('article' in href.lower() or href.endswith(".pdf")):
                        pmc_link = href
                        logger.info(f"PubMedStrategy: Found PMC link: {pmc_link}")
                        return pmc_link # Prioritize and return immediately
                
                if first_link: # If no PMC link, return the first one found
                    logger.info(f"PubMedStrategy: No PMC link found, returning first available link: {first_link}")
                    return first_link
            
            logger.warning(f"PubMedStrategy: Could not find 'full-text-links' section or any links within it for {pubmed_url}")
            return None
            
        except Exception as e:
            logger.error(f"PubMedStrategy: Error parsing PubMed HTML for full text link from {pubmed_url}: {e}", exc_info=True)
            return None

    def extract_data(self, content: str, url: str) -> Dict[str, Any]:
        """
        Extracts the full-text link from the PubMed page HTML.
        Returns a special dictionary indicating the next URL to process.
        'url' here is the final URL of the PubMed page itself.
        """
        logger.info(f"PubMedStrategy: Extracting full-text link from PubMed page: {url}")
        
        full_text_url = self._extract_full_text_link_from_html(content, url)

        if full_text_url:
            logger.info(f"PubMedStrategy: Extracted full-text URL '{full_text_url}' from PubMed page {url}. Delegating processing.")
            return {
                "next_url_to_process": full_text_url,
                "original_pubmed_url": url, # The URL of the PubMed page itself
                "content_type": "pubmed_delegation", # Special type to signal delegation
                "final_url_after_redirects": url, # For this strategy, it's the pubmed page URL
            }
        else:
            logger.warning(f"PubMedStrategy: Could not extract any full-text link from {url}. Cannot delegate.")
            # This is an extraction failure for this strategy.
            return {
                "title": f"PubMed Full-Text Link Extraction Failed for {url.split('/')[-1]}",
                "text_content": "Could not find a usable full-text link on the PubMed page.",
                "content_type": "error_pubmed_extraction", # Special error type
                "final_url_after_redirects": url,
            }

    def prepare_for_llm(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        This method should not be called directly if delegation occurs.
        If called (e.g., due to an extraction failure), it indicates no LLM processing.
        """
        logger.info(f"PubMedStrategy: prepare_for_llm called. Data: {extracted_data}")
        # If 'next_url_to_process' is present, this strategy's job is done.
        # If not, it means extraction failed, so no LLM processing for this step.
        return { # Indicates no content for LLM from this PubMed *page* itself
            "content_to_filter": None,
            "content_to_summarize": None,
            "is_pdf": False # Irrelevant as we are delegating or failed
        }

    def extract_internal_urls(self, content: str, original_url: str) -> List[str]:
        """
        Extracts internal URLs from the PubMed page for logging.
        Could log other links found on the PubMed page if desired.
        """
        # Placeholder, similar to HtmlStrategy.
        # Could parse 'content' (PubMed page HTML) for other links if needed.
        logger.info(f"PubMedStrategy: extract_internal_urls called for {original_url}. (Placeholder - returning empty list)")
        return []