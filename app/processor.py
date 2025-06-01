"""
Link processor module that consumes URLs from the links_to_scrape queue,
downloads content, processes it with LLM, and creates Articles/Summaries.
"""
import base64
import re
import requests
from datetime import datetime
from typing import Optional, Dict, Any
from urllib.parse import urljoin, urlparse
from google.genai.errors import ClientError
from trafilatura import fetch_url, bare_extraction
from bs4 import BeautifulSoup

from .config import settings, logger
from .database import SessionLocal
from .models import Articles, Links, LinkStatus, FailurePhase
from .utils.failures import record_failure
from .schemas import ArticleSummary
from . import llm


def url_preprocessor(url: str) -> str:
    """
    Preprocess URLs to handle specific site heuristics.
    
    Args:
        url: Original URL
        
    Returns:
        Processed URL that may be different from the original
    """
    logger.info(f"Preprocessing URL: {url}")
    
    # Handle arXiv URLs: convert /abs/ to /pdf/
    arxiv_pattern = r'https://arxiv\.org/abs/(\d+\.\d+)'
    arxiv_match = re.match(arxiv_pattern, url)
    if arxiv_match:
        paper_id = arxiv_match.group(1)
        pdf_url = f"https://arxiv.org/pdf/{paper_id}"
        logger.info(f"Converted arXiv URL from {url} to {pdf_url}")
        return pdf_url
    
    # Handle PubMed URLs: extract full text links
    if 'pubmed.ncbi.nlm.nih.gov' in url:
        try:
            full_text_url = extract_pubmed_full_text_link(url)
            if full_text_url:
                logger.info(f"Extracted PubMed full text URL: {full_text_url}")
                return full_text_url
            else:
                logger.warning(f"Could not extract full text link from PubMed URL: {url}")
        except Exception as e:
            logger.error(f"Error processing PubMed URL {url}: {e}")
    
    return url


def extract_pubmed_full_text_link(pubmed_url: str) -> Optional[str]:
    """
    Extract the first available full text link from a PubMed article page.
    
    Args:
        pubmed_url: PubMed article URL
        
    Returns:
        Full text URL if found, None otherwise
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(pubmed_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for full text links section
        full_text_section = soup.find('div', {'class': 'full-text-links-list'})
        if not full_text_section:
            # Alternative selector for full text links
            full_text_section = soup.find('div', string=re.compile(r'Full.*text.*links', re.IGNORECASE))
            if full_text_section:
                full_text_section = full_text_section.find_parent('div')
        
        if full_text_section:
            # Find the first link in the full text section
            links = full_text_section.find_all('a', href=True)
            for link in links:
                href = link.get('href')
                if href and (href.startswith('http') or href.startswith('//')):
                    # Convert relative URLs to absolute
                    if href.startswith('//'):
                        href = 'https:' + href
                    elif href.startswith('/'):
                        href = 'https://pubmed.ncbi.nlm.nih.gov' + href
                    
                    # Prioritize PMC links
                    if 'pmc' in href.lower():
                        return href
                    
            # If no PMC link found, return the first available link
            if links:
                href = links[0].get('href')
                if href.startswith('//'):
                    href = 'https:' + href
                elif href.startswith('/'):
                    href = 'https://pubmed.ncbi.nlm.nih.gov' + href
                return href
        
        return None
        
    except Exception as e:
        logger.error(f"Error extracting full text link from {pubmed_url}: {e}")
        return None


def check_duplicate_url(url: str) -> bool:
    """
    Check if a URL already exists in the database.
    
    Args:
        url: URL to check
        
    Returns:
        True if URL exists, False otherwise
    """
    db = SessionLocal()
    try:
        existing_article = db.query(Articles).filter(Articles.url == url).first()
        return existing_article is not None
    finally:
        db.close()


def download_and_process_content(url: str) -> Optional[Dict[str, Any]]:
    """
    Download content from URL and return processed data.
    
    Args:
        url: URL to download and process
        
    Returns:
        Dictionary with processed content or None if failed
    """
    try:
        # Preprocess URL for specific site heuristics
        processed_url = url_preprocessor(url)
        logger.info(f"Downloading content from: {processed_url}")
        
        # First, make a HEAD request to check content type
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        try:
            head_response = requests.head(processed_url, headers=headers, timeout=10, allow_redirects=True)
            content_type = head_response.headers.get('content-type', '').lower()
        except Exception as e:
            logger.warning(f"HEAD request failed for {processed_url}: {e}. Proceeding with content detection.")
            content_type = ''
        
        # Handle PDF content
        if 'application/pdf' in content_type:
            logger.info(f"Detected PDF content for: {processed_url}")
            # Use requests for PDF content to get binary data
            response = requests.get(processed_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Encode PDF content as base64 for LLM processing
            pdf_content = base64.b64encode(response.content).decode('utf-8')
            return {
                "url": url,  # Keep original URL for tracking
                "title": urlparse(processed_url).path.split('/')[-1] or "PDF Document",
                "author": None,
                "publication_date": None,
                "content": pdf_content,
                "is_pdf": True
            }
        
        # For HTML/text content, use trafilatura's fetch_url
        downloaded_html = fetch_url(processed_url)
        
        if not downloaded_html:
            logger.warning(f"Failed to fetch content from {processed_url}")
            return None
        
        # Extract content and metadata using trafilatura
        extracted_data = bare_extraction(
            filecontent=downloaded_html,
            url=processed_url,
            with_metadata=True,
            include_links=True,
            include_formatting=True
        )
        
        if not extracted_data:
            logger.warning(f"Trafilatura failed to extract content from {processed_url}")
            return None
        
        # Extract metadata from trafilatura result
        title = extracted_data.title or "Untitled"
        author = extracted_data.author
        content = extracted_data.text or ""

        logger.info(f"Sample content {content[0:100]}")
        
        # Handle publication date
        publication_date = None
        if extracted_data.date:
            try:
                from dateutil import parser
                publication_date = parser.parse(extracted_data.date)
            except Exception:
                pass
        
        # Validate content length
        if len(content) < 100:
            logger.warning(f"Content too short for {url}. Length: {len(content)}")
            return None
            
        return {
            "url": url,
            "title": title or "Untitled",
            "author": author,
            "publication_date": publication_date,
            "content": content,
            "is_pdf": False
        }
        
    except requests.RequestException as e:
        error_msg = f"HTTP error downloading content from {processed_url}: {e}"
        logger.error(error_msg, exc_info=True)
        return None
    except Exception as e:
        error_msg = f"Error downloading content from {processed_url}: {e}"
        logger.error(error_msg, exc_info=True)
        return None


def process_with_llm(content_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Process content with LLM for filtering and summarization.
    
    Args:
        content_data: Dictionary with content information
        
    Returns:
        Dictionary with LLM results, {"skipped": True, "skip_reason": str} if filtered out, or None if failed
        
    Raises:
        ClientError: If LLM returns 429 (rate limit) error
    """
    try:
        content = content_data["content"]
        is_pdf = content_data.get("is_pdf", False)
        
        logger.info(f"Processing content with LLM for: {content_data['url']}")
        
        # First, filter the article to see if it matches preferences
        if is_pdf:
            # For PDFs, we'll skip filtering and proceed directly to summarization
            # since filtering PDFs requires different handling
            logger.info("Skipping filtering for PDF content")
            matches_preferences = True
            skip_reason = None
        else:
            matches_preferences, skip_reason = llm.filter_article(content)
            
        if not matches_preferences:
            logger.info(f"Article does not match preferences, marking as skipped: {content_data['url']} - Reason: {skip_reason}")
            return {"skipped": True, "skip_reason": skip_reason}
        else:
            logger.info(f"Article matches preferences, proceeding with summarization: {content_data['url']} - Reason: {skip_reason}")
            
        # Generate summaries
        if is_pdf:
            # Decode base64 string back to bytes for LLM processing
            pdf_bytes = base64.b64decode(content)
            summary = llm.summarize_pdf(pdf_bytes)
        else:
            summary = llm.summarize_article(content)
            
        # Validate summary is ArticleSummary instance
        if not isinstance(summary, ArticleSummary):
            logger.error(f"Invalid summary format for {content_data['url']}: {type(summary)}")
            return None
            
        return {
            "short_summary": summary.short_summary,
            "detailed_summary": summary.detailed_summary
        }
        
    except ClientError as e:
        # Check if this is a 429 rate limit error
        if "429" in str(e) or "rate limit" in str(e).lower():
            logger.warning(f"LLM rate limit hit for {content_data['url']}: {e}")
            raise  # Re-raise to trigger retry logic
        else:
            logger.error(f"LLM client error for {content_data['url']}: {e}", exc_info=True)
            return None
    except Exception as e:
        logger.error(f"Error processing content with LLM for {content_data['url']}: {e}", exc_info=True)
        return None


def create_article_and_link_to_source(content_data: Dict[str, Any], llm_data: Dict[str, Any], link: Links) -> bool:
    """
    Create Article record with embedded summary data and link it to the source Link.
    
    Args:
        content_data: Dictionary with content information
        llm_data: Dictionary with LLM processing results
        link: Link object that was processed
        
    Returns:
        True if successful, False otherwise
    """
    db = SessionLocal()
    try:
        # Create Article record with embedded summary data (no raw_content)
        article = Articles(
            title=content_data.get("title", ""),
            url=content_data["url"],
            author=content_data.get("author"),
            publication_date=content_data.get("publication_date"),
            scraped_date=datetime.utcnow(),
            short_summary=llm_data.get("short_summary", ""),
            detailed_summary=llm_data.get("detailed_summary", ""),
            summary_date=datetime.utcnow(),
            link_id=link.id
        )
        
        db.add(article)
        db.commit()
        
        logger.info(f"Successfully created article with summary for: {content_data['url']} (source: {link.source})")
        return True
        
    except Exception as e:
        logger.error(f"Error creating article for {content_data['url']}: {e}", exc_info=True)
        db.rollback()
        return False
        
    finally:
        db.close()


def update_link_status(link_id: int, status: LinkStatus, error_message: str = None) -> None:
    """
    Update the status of a link in the database.
    
    Args:
        link_id: ID of the link to update
        status: New status for the link
        error_message: Optional error message if status is failed
    """
    db = SessionLocal()
    try:
        link = db.query(Links).filter(Links.id == link_id).first()
        if link:
            link.status = status
            if status == LinkStatus.processed:
                link.processed_date = datetime.utcnow()
            if error_message:
                link.error_message = error_message
            db.commit()
            logger.info(f"Updated link {link_id} status to {status.value}")
        else:
            logger.error(f"Link {link_id} not found for status update")
    except Exception as e:
        logger.error(f"Error updating link {link_id} status: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


def process_link_from_db(link: Links) -> bool:
    """
    Process a link from the database: download, filter, summarize, and store.
    
    Args:
        link: Link object from database
        
    Returns:
        True if successful, False otherwise
        
    Raises:
        ClientError: If LLM returns 429 (rate limit) error
    """
    logger.info(f"Processing link from {link.source}: {link.url}")
    
    # Update status to processing
    update_link_status(link.id, LinkStatus.processing)
    
    try:
        # Check for duplicates in Articles table
        if check_duplicate_url(link.url):
            logger.info(f"URL already exists in articles, marking as processed: {link.url}")
            update_link_status(link.id, LinkStatus.processed)
            return True
        
        # Download and process content
        content_data = download_and_process_content(link.url)
        if not content_data:
            error_msg = f"Failed to download content for: {link.url}"
            logger.warning(error_msg)
            record_failure(FailurePhase.processor, error_msg, link.id)
            update_link_status(link.id, LinkStatus.failed, error_msg)
            return False
        
        # Process with LLM (may raise ClientError for 429)
        llm_data = process_with_llm(content_data)
        if not llm_data:
            error_msg = f"LLM processing failed for: {link.url}"
            logger.error(error_msg)
            record_failure(FailurePhase.processor, error_msg, link.id)
            update_link_status(link.id, LinkStatus.failed, error_msg)
            return False
        
        # Check if content was skipped by LLM filtering
        if llm_data.get("skipped"):
            skip_reason = llm_data.get("skip_reason", "No reason provided")
            logger.info(f"Content skipped by LLM filtering: {link.url} - Reason: {skip_reason}")
            # Record the skip as a "failure" with the skip reason for tracking
            # Concatenate filter decision to the beginning of error_msg
            error_msg = f"FILTER_DECISION: REJECTED - Content skipped by LLM filtering: {skip_reason}"
            record_failure(FailurePhase.processor, error_msg, link.id, skip_reason)
            update_link_status(link.id, LinkStatus.skipped)
            return True  # This is a successful processing, just skipped
        
        # Create article and link to source
        success = create_article_and_link_to_source(content_data, llm_data, link)
        if success:
            logger.info(f"Successfully processed link: {link.url}")
            update_link_status(link.id, LinkStatus.processed)
        else:
            error_msg = f"Failed to create article for: {link.url}"
            logger.error(error_msg)
            record_failure(FailurePhase.processor, error_msg, link.id)
            update_link_status(link.id, LinkStatus.failed, error_msg)
        
        return success
        
    except ClientError as e:
        # Check if this is a 429 rate limit error
        if "429" in str(e) or "rate limit" in str(e).lower():
            logger.warning(f"LLM rate limit hit for {link.url}, will retry: {e}")
            # Reset status to new for retry
            update_link_status(link.id, LinkStatus.new)
            raise  # Re-raise to trigger retry logic
        else:
            error_msg = f"LLM client error: {e}"
            logger.error(f"LLM client error for {link.url}: {e}", exc_info=True)
            record_failure(FailurePhase.processor, error_msg, link.id)
            update_link_status(link.id, LinkStatus.failed, error_msg)
            return False
    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        logger.error(f"Error processing link {link.url}: {e}", exc_info=True)
        record_failure(FailurePhase.processor, error_msg, link.id)
        update_link_status(link.id, LinkStatus.failed, error_msg)
        return False


