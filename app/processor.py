"""
Link processor module that consumes URLs from the links_to_scrape queue,
downloads content, processes it with LLM, and creates Articles/Summaries.
"""
import base64
import requests
from datetime import datetime
from typing import Optional, Dict, Any
from urllib.parse import urljoin, urlparse
from google.genai.errors import ClientError
from trafilatura import fetch_url, bare_extraction

from .config import settings, logger
from .database import SessionLocal
from .models import Articles, Summaries, ArticleStatus
from . import llm


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
        logger.info(f"Downloading content from: {url}")
        
        # Set up headers to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Make HTTP request
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Check content type
        content_type = response.headers.get('content-type', '').lower()
        
        # Handle PDF content
        if 'application/pdf' in content_type:
            logger.info(f"Detected PDF content for: {url}")
            # Encode PDF content as base64 for LLM processing
            pdf_content = base64.b64encode(response.content).decode('utf-8')
            return {
                "url": url,
                "title": urlparse(url).path.split('/')[-1] or "PDF Document",
                "author": None,
                "publication_date": None,
                "content": pdf_content,
                "is_pdf": True
            }
        
        # Extract content and metadata using trafilatura
        downloaded_html = response.text
        extracted_data = bare_extraction(
            downloaded_html, 
            url=url, 
            output_format='markdown', 
            with_metadata=True, 
            include_links=True, 
            include_formatting=True, 
            date_extraction_params={'original_date': True}
        )
        
        if not extracted_data:
            logger.warning(f"Trafilatura failed to extract content from {url}")
            return None
        
        # Extract metadata from trafilatura result
        title = extracted_data.title or "Untitled"
        author = extracted_data.author
        content = extracted_data.text or ""
        
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
        logger.error(f"HTTP error downloading content from {url}: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Error downloading content from {url}: {e}", exc_info=True)
        return None


def process_with_llm(content_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Process content with LLM for filtering and summarization.
    
    Args:
        content_data: Dictionary with content information
        
    Returns:
        Dictionary with LLM results or None if failed
        
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
        else:
            matches_preferences = llm.filter_article(content)
            
        if not matches_preferences:
            logger.info(f"Article does not match preferences: {content_data['url']}")
            return None
            
        # Generate summaries
        if is_pdf:
            summaries = llm.summarize_pdf(content)
        else:
            summaries = llm.summarize_article(content)
            
        # Validate summary format
        if not isinstance(summaries, dict):
            logger.error(f"Invalid summary format for {content_data['url']}: {type(summaries)}")
            return None
            
        return {
            "short_summary": summaries.get("short", ""),
            "detailed_summary": summaries.get("detailed", ""),
            "keywords": summaries.get("keywords", [])
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


def create_article_and_summary(content_data: Dict[str, Any], llm_data: Dict[str, Any], source: str) -> bool:
    """
    Create Article and Summary records in the database.
    
    Args:
        content_data: Dictionary with content information
        llm_data: Dictionary with LLM processing results
        source: Source of the link
        
    Returns:
        True if successful, False otherwise
    """
    db = SessionLocal()
    try:
        # Create Article record (without raw_content)
        article = Articles(
            title=content_data.get("title", ""),
            url=content_data["url"],
            author=content_data.get("author"),
            publication_date=content_data.get("publication_date"),
            scraped_date=datetime.utcnow(),
            status=ArticleStatus.processed
        )
        
        db.add(article)
        db.flush()  # Get the article ID
        
        # Create Summary record
        summary = Summaries(
            article_id=article.id,
            short_summary=llm_data.get("short_summary", ""),
            detailed_summary=llm_data.get("detailed_summary", ""),
            summary_date=datetime.utcnow()
        )
        
        db.add(summary)
        db.commit()
        
        logger.info(f"Successfully created article and summary for: {content_data['url']} (source: {source})")
        return True
        
    except Exception as e:
        logger.error(f"Error creating article and summary for {content_data['url']}: {e}", exc_info=True)
        db.rollback()
        return False
        
    finally:
        db.close()


def process_single_link(url: str, source: str = "unknown") -> bool:
    """
    Process a single link: download, filter, summarize, and store.
    
    Args:
        url: URL to process
        source: Source of the link
        
    Returns:
        True if successful, False otherwise
        
    Raises:
        ClientError: If LLM returns 429 (rate limit) error
    """
    logger.info(f"Processing link from {source}: {url}")
    
    # Check for duplicates
    if check_duplicate_url(url):
        logger.info(f"URL already exists in database, skipping: {url}")
        return True  # Consider this successful since we don't need to reprocess
    
    # Download and process content
    content_data = download_and_process_content(url)
    if not content_data:
        logger.warning(f"Failed to download content for: {url}")
        return False
    
    # Process with LLM (may raise ClientError for 429)
    llm_data = process_with_llm(content_data)
    if not llm_data:
        logger.info(f"Content filtered out or LLM processing failed for: {url}")
        return False
    
    # Create article and summary
    success = create_article_and_summary(content_data, llm_data, source)
    if success:
        logger.info(f"Successfully processed link: {url}")
    else:
        logger.error(f"Failed to create article/summary for: {url}")
    
    return success
