"""
Link processor module that consumes URLs from the links_to_scrape queue,
downloads content, processes it with LLM, and creates Articles/Summaries.
Uses a strategy pattern for handling different URL types.
"""
# import re # No longer needed here, moved to strategies
# import requests # Replaced by httpx via RobustHttpClient
from datetime import datetime
from typing import Optional, Dict, Any
# from urllib.parse import urlparse # Moved to strategies if needed
from google.genai.errors import ClientError
# from trafilatura import bare_extraction # Moved to HtmlStrategy
# from bs4 import BeautifulSoup # Moved to PubMedStrategy

from .config import logger # Import settings for client config
from .database import SessionLocal
from .models import Articles, Links, LinkStatus, FailurePhase
from .utils.failures import record_failure
from .schemas import ArticleSummary
from . import llm

# New imports for strategy pattern
from .http_client.robust_http_client import RobustHttpClient
from .processing_strategies.factory import UrlProcessorFactory
# Individual strategies are registered in the factory, no direct import needed here unless for type hinting.
# from .processing_strategies.base_strategy import UrlProcessorStrategy


# url_preprocessor and extract_pubmed_full_text_link are removed as their logic
# is now within specific strategies (HtmlStrategy, PubMedStrategy).

# download_and_process_content is removed and its logic is replaced by the
# strategy execution flow within process_link_from_db.


def check_duplicate_url(url: str, db_session: SessionLocal) -> bool: # Added db_session parameter
    """
    Check if a URL already exists in the Articles table.
    """
    # db = SessionLocal() # Session should be managed by the caller
    try:
        existing_article = db_session.query(Articles).filter(Articles.url == url).first()
        return existing_article is not None
    finally:
        pass # db_session.close() # Caller manages session


# process_with_llm remains largely the same but expects input from strategy.prepare_for_llm()
def process_with_llm(llm_input_data: Dict[str, Any], original_url: str) -> Optional[Dict[str, Any]]:
    """
    Process content with LLM for filtering and summarization.
    
    Args:
        llm_input_data: Dictionary from strategy.prepare_for_llm()
                        e.g., {"content_to_filter": ..., "content_to_summarize": ..., "is_pdf": ...}
        original_url: The original URL being processed, for logging.
        
    Returns:
        Dictionary with LLM results, {"skipped": True, "skip_reason": str} if filtered out, or None if failed
        
    Raises:
        ClientError: If LLM returns 429 (rate limit) error
    """
    try:
        content_to_filter = llm_input_data.get("content_to_filter")
        content_to_summarize = llm_input_data.get("content_to_summarize")
        is_pdf = llm_input_data.get("is_pdf", False)
        
        if content_to_summarize is None: # Should not happen if strategy is correct
            logger.error(f"LLM processing error: 'content_to_summarize' is missing for {original_url}")
            return None

        logger.info(f"Processing content with LLM for: {original_url}")
        
        matches_preferences = True
        skip_reason = None

        if is_pdf:
            logger.info(f"Skipping text-based filtering for PDF content: {original_url}")
        elif content_to_filter:
            matches_preferences, skip_reason = llm.filter_article(content_to_filter)
        else:
            # If not PDF and no content_to_filter, assume it matches or log warning
            logger.warning(f"No content_to_filter provided for non-PDF, assuming matches: {original_url}")

        if not matches_preferences:
            logger.info(f"Article does not match preferences, marking as skipped: {original_url} - Reason: {skip_reason}")
            return {"skipped": True, "skip_reason": skip_reason}
        else:
            if skip_reason: # Log reason even if it matches (e.g. "Matches, but close call because...")
                 logger.info(f"Article matches preferences: {original_url} - Reason: {skip_reason}")
            else:
                 logger.info(f"Article matches preferences, proceeding with summarization: {original_url}")
            
        # Generate summaries
        if is_pdf:
            # content_to_summarize should be bytes for PDF
            if not isinstance(content_to_summarize, bytes):
                logger.error(f"LLM PDF analysis error: content_to_summarize is not bytes for {original_url}")
                return None
            pdf_analysis = llm.analyze_pdf(content_to_summarize)
            
            if not hasattr(pdf_analysis, 'title') or not hasattr(pdf_analysis, 'short_summary'):
                logger.error(f"Invalid PDF analysis format from LLM for {original_url}: {type(pdf_analysis)}")
                return None
                
            return {
                "title": pdf_analysis.title,  # Include extracted title
                "short_summary": pdf_analysis.short_summary,
                "detailed_summary": pdf_analysis.detailed_summary
            }
        else:
            # content_to_summarize should be string for text
            if not isinstance(content_to_summarize, str):
                logger.error(f"LLM text summarization error: content_to_summarize is not str for {original_url}")
                return None
            summary_model = llm.summarize_article(content_to_summarize)
            
            if not isinstance(summary_model, ArticleSummary):
                logger.error(f"Invalid summary format from LLM for {original_url}: {type(summary_model)}")
                return None
                
            return {
                "short_summary": summary_model.short_summary,
                "detailed_summary": summary_model.detailed_summary
            }
        
    except ClientError as e:
        if "429" in str(e) or "rate limit" in str(e).lower():
            logger.warning(f"LLM rate limit hit for {original_url}: {e}")
            raise
        else:
            logger.error(f"LLM client error for {original_url}: {e}", exc_info=True)
            return None
    except Exception as e:
        logger.error(f"Error processing content with LLM for {original_url}: {e}", exc_info=True)
        return None


def create_article_and_link_to_source(
    extracted_data: Dict[str, Any], 
    llm_results: Dict[str, Any], 
    link: Links,
    db_session: SessionLocal # Added db_session parameter
) -> bool:
    """
    Create Article record and link it to the source Link.
    'extracted_data' is the rich dictionary from the strategy.
    'llm_results' contains summaries.
    """
    # db = SessionLocal() # Session should be managed by the caller
    try:
        # Use title from LLM results if available (for PDFs), otherwise use extracted title
        title = llm_results.get("title") or extracted_data.get("title", "Untitled")
        
        article = Articles(
            title=title,
            url=extracted_data["final_url_after_redirects"], # Use final URL
            author=extracted_data.get("author"),
            publication_date=extracted_data.get("publication_date"), # Assumes already parsed if string
            scraped_date=datetime.utcnow(),
            short_summary=llm_results.get("short_summary", ""),
            detailed_summary=llm_results.get("detailed_summary", ""),
            summary_date=datetime.utcnow(),
            link_id=link.id
        )
        
        db_session.add(article)
        # db_session.commit() # Commit should be handled by the main processing loop after all updates
        
        logger.info(f"Successfully prepared article for DB: {extracted_data['final_url_after_redirects']} (source: {link.source})")
        return True
        
    except Exception as e:
        logger.error(f"Error preparing article for DB {extracted_data.get('final_url_after_redirects')}: {e}", exc_info=True)
        # db_session.rollback() # Rollback handled by main loop
        return False
    finally:
        pass # db_session.close() # Caller manages session


def update_link_status(link_id: int, status: LinkStatus, db_session: SessionLocal, error_message: Optional[str] = None) -> None: # Added db_session
    """
    Update the status of a link in the database.
    """
    # db = SessionLocal() # Session should be managed by the caller
    try:
        link_obj = db_session.query(Links).filter(Links.id == link_id).first() # Renamed to link_obj
        if link_obj:
            link_obj.status = status
            if status == LinkStatus.processed or status == LinkStatus.skipped: # Skipped is also a final state
                link_obj.processed_date = datetime.utcnow()
            if error_message:
                link_obj.error_message = error_message
            # db_session.commit() # Commit handled by main loop
            logger.info(f"Updated link {link_id} status to {status.value}")
        else:
            logger.error(f"Link {link_id} not found for status update")
    except Exception as e:
        logger.error(f"Error updating link {link_id} status: {e}", exc_info=True)
        # db_session.rollback() # Rollback handled by main loop
    finally:
        pass # db_session.close() # Caller manages session


def process_link_from_db(link: Links, http_client: RobustHttpClient, factory: UrlProcessorFactory) -> bool: # Made synchronous, added client & factory
    """
    Process a link from the database using the strategy pattern.
    This function is now synchronous.
    """
    logger.info(f"Processing link ID {link.id} from {link.source}: {link.url}")
    db = SessionLocal() # Manage session within this task execution

    try:
        update_link_status(link.id, LinkStatus.processing, db)
        db.commit() # Commit status update immediately

        # Initial duplicate check with original URL from DB
        if check_duplicate_url(link.url, db):
            logger.info(f"Original URL {link.url} (ID: {link.id}) already exists in articles, marking as processed.")
            update_link_status(link.id, LinkStatus.processed, db)
            db.commit()
            return True

        current_url_to_process = link.url
        extracted_data: Optional[Dict[str, Any]] = None
        strategy_instance = None
        
        # Loop to handle potential delegation (e.g., PubMed)
        MAX_DELEGATIONS = 3 # Prevent infinite loops
        delegation_count = 0

        while delegation_count < MAX_DELEGATIONS:
            delegation_count += 1
            strategy_instance = factory.get_strategy(current_url_to_process)

            if not strategy_instance:
                error_msg = f"No suitable processing strategy found for URL: {current_url_to_process} (original: {link.url})"
                logger.error(error_msg)
                record_failure(FailurePhase.processor, error_msg, link.id)
                update_link_status(link.id, LinkStatus.failed, db, error_msg)
                db.commit()
                return False

            logger.info(f"Using strategy: {strategy_instance.__class__.__name__} for URL: {current_url_to_process}")

            try:
                # Preprocess URL (e.g., arXiv /abs/ to /pdf/)
                # The factory might re-evaluate if preprocess_url changes URL type significantly,
                # but for now, assume current strategy handles the preprocessed URL.
                processed_url_for_download = strategy_instance.preprocess_url(current_url_to_process)
                if processed_url_for_download != current_url_to_process:
                     logger.info(f"URL preprocessed from {current_url_to_process} to {processed_url_for_download} by {strategy_instance.__class__.__name__}")
                     # If URL changed significantly (e.g. to a PDF by Arxiv preprocessor in HTML strategy),
                     # it might be better to re-run factory.get_strategy(processed_url_for_download).
                     # For now, the selected strategy proceeds. The factory's initial HEAD request helps.
                     current_url_to_process = processed_url_for_download


                content_downloaded = strategy_instance.download_content(current_url_to_process)
                
                # Pass original link.url for context if needed by extract_data
                temp_extracted_data = strategy_instance.extract_data(content_downloaded, current_url_to_process)
                temp_extracted_data["original_url_from_db"] = link.url # Ensure original URL is part of data

                if temp_extracted_data.get("content_type") == "pubmed_delegation":
                    next_url = temp_extracted_data.get("next_url_to_process")
                    if next_url:
                        logger.info(f"PubMedStrategy delegated. Original: {link.url}, PubMed page: {current_url_to_process}, Next to process: {next_url}")
                        current_url_to_process = next_url
                        # Duplicate check for the *new* target URL before continuing loop
                        if check_duplicate_url(current_url_to_process, db):
                            logger.info(f"Delegated URL {current_url_to_process} already exists in articles. Marking original link {link.url} as processed.")
                            update_link_status(link.id, LinkStatus.processed, db)
                            db.commit()
                            return True
                        continue # Loop to get strategy for next_url
                    else:
                        error_msg = f"PubMedStrategy failed to provide next_url_to_process for {current_url_to_process}"
                        logger.error(error_msg)
                        # Fall through to treat as failure of this strategy path
                        extracted_data = temp_extracted_data # Keep the error data
                        break
                
                extracted_data = temp_extracted_data
                break # Successful extraction, exit delegation loop

            except Exception as e_strat:
                error_msg = f"Strategy {strategy_instance.__class__.__name__} failed for {current_url_to_process} (original: {link.url}): {e_strat}"
                logger.error(error_msg, exc_info=True)
                record_failure(FailurePhase.processor, error_msg, link.id)
                update_link_status(link.id, LinkStatus.failed, db, error_msg)
                db.commit()
                return False
        
        if delegation_count >= MAX_DELEGATIONS:
            error_msg = f"Exceeded max delegations ({MAX_DELEGATIONS}) for link ID {link.id}, original URL {link.url}"
            logger.error(error_msg)
            record_failure(FailurePhase.processor, error_msg, link.id)
            update_link_status(link.id, LinkStatus.failed, db, error_msg)
            db.commit()
            return False

        if not extracted_data or not extracted_data.get("final_url_after_redirects"):
            error_msg = f"Failed to extract data or final_url_after_redirects missing for {link.url} using strategy {strategy_instance.__class__.__name__ if strategy_instance else 'N/A'}"
            logger.error(error_msg)
            # Check if extracted_data has a more specific error message (e.g. from PubMed failure)
            if extracted_data and extracted_data.get("content_type") == "error_pubmed_extraction":
                error_msg = extracted_data.get("text_content", error_msg)

            record_failure(FailurePhase.processor, error_msg, link.id)
            update_link_status(link.id, LinkStatus.failed, db, error_msg)
            db.commit()
            return False

        # Log internal URLs if any (for now, strategies return empty list)
        # internal_urls = strategy_instance.extract_internal_urls(content_downloaded, link.url)
        # if internal_urls:
        #     logger.info(f"Extracted internal URLs for {link.url}: {internal_urls}")


        # Additional duplicate check using the final URL from which content was fetched
        final_url_from_content = extracted_data["final_url_after_redirects"]
        if final_url_from_content != link.url and check_duplicate_url(final_url_from_content, db):
            logger.info(f"Final content URL {final_url_from_content} (from original {link.url}) already exists in articles, marking as processed.")
            update_link_status(link.id, LinkStatus.processed, db)
            db.commit()
            return True

        # Prepare data for LLM
        llm_input_data = strategy_instance.prepare_for_llm(extracted_data)
        
        # Process with LLM (may raise ClientError for 429)
        llm_results = process_with_llm(llm_input_data, link.url) # Pass original_url for logging
        
        if not llm_results:
            error_msg = f"LLM processing failed for final URL: {final_url_from_content} (original: {link.url})"
            logger.error(error_msg)
            record_failure(FailurePhase.processor, error_msg, link.id)
            update_link_status(link.id, LinkStatus.failed, db, error_msg)
            db.commit()
            return False
        
        if llm_results.get("skipped"):
            skip_reason = llm_results.get("skip_reason", "No reason provided")
            logger.info(f"Content skipped by LLM filtering: {link.url} - Reason: {skip_reason}")
            error_msg_skipped = f"FILTER_DECISION: REJECTED - Content skipped by LLM filtering: {skip_reason}"
            record_failure(FailurePhase.processor, error_msg_skipped, link.id, skip_reason=skip_reason)
            update_link_status(link.id, LinkStatus.skipped, db)
            db.commit()
            return True

        # Create article
        article_created = create_article_and_link_to_source(extracted_data, llm_results, link, db)
        if article_created:
            logger.info(f"Successfully processed link: {link.url} -> {final_url_from_content}")
            update_link_status(link.id, LinkStatus.processed, db)
            db.commit()
            return True
        else:
            error_msg = f"Failed to create article in DB for: {link.url} -> {final_url_from_content}"
            logger.error(error_msg)
            # record_failure already called by create_article if it fails internally, but good to have a fallback
            record_failure(FailurePhase.database, error_msg, link.id)
            update_link_status(link.id, LinkStatus.failed, db, error_msg)
            db.commit()
            return False

    except ClientError as e_llm_rate_limit: # Specifically for 429 from process_with_llm
        logger.warning(f"LLM rate limit hit for {link.url}, will retry: {e_llm_rate_limit}")
        update_link_status(link.id, LinkStatus.new, db) # Reset status for retry by Huey
        db.commit()
        raise # Re-raise to trigger Huey's retry mechanism
    except Exception as e_main:
        error_msg = f"Unexpected error processing link {link.url}: {e_main}"
        logger.error(error_msg, exc_info=True)
        # Ensure db session is passed to record_failure if it's available
        record_failure(FailurePhase.processor, error_msg, link.id)
        update_link_status(link.id, LinkStatus.failed, db, error_msg)
        db.commit()
        return False
    finally:
        if db: # Ensure db session is closed
            db.close()


# Example of how this might be called by a Huey task (conceptual)
# from huey import SqliteHuey
# from app.models import Links
# from app.http_client.robust_http_client import RobustHttpClient
# from app.processing_strategies.factory import UrlProcessorFactory

# huey = SqliteHuey(filename=settings.HUEY_DB_PATH)

# @huey.task()
# def process_link_task(link_id: int):
#     db = SessionLocal()
#     link = db.query(Links).filter(Links.id == link_id).first()
#     if not link:
#         logger.error(f"Link ID {link_id} not found in process_link_task.")
#         db.close()
#         return
    
#     # Initialize http_client and factory once per worker or task group if possible,
#     # or per task if they are lightweight to create/destroy.
#     # For RobustHttpClient, it's better to reuse the underlying httpx.Client.
#     # This example creates them per task for simplicity here.
#     http_client = RobustHttpClient(timeout=settings.HTTP_CLIENT_TIMEOUT, headers={'User-Agent': settings.HTTP_CLIENT_USER_AGENT})
#     factory = UrlProcessorFactory(http_client)
    
#     try:
#         process_link_from_db(link, http_client, factory)
#     finally:
#         http_client.close() # Ensure client is closed
#         db.close()

# The `process_link_from_db` is now synchronous. The caller (Huey task)
# can call it directly without needing async/await.
