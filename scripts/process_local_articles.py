#!/usr/bin/env python3
"""
Processes articles that have been downloaded locally and are waiting for summarization.
This script looks for articles with status 'new' and a valid 'local_path'.
"""

import os
import sys
from trafilatura import extract
from sqlalchemy.orm import Session

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import Articles, ArticleStatus
from app.llm import summarize_article
from app.config import logger

def process_new_local_articles(db: Session):
    """
    Queries for new local articles, summarizes them, and updates their status.
    """
    articles_to_process = db.query(Articles).filter(
        Articles.status == ArticleStatus.new,
        Articles.local_path.isnot(None)
    ).all()

    if not articles_to_process:
        logger.info("No new local articles to process.")
        return

    logger.info(f"Found {len(articles_to_process)} new local articles to process.")

    for article in articles_to_process:
        logger.info(f"Processing article ID: {article.id} from {article.local_path}")
        
        try:
            with open(article.local_path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            # Extract main content from HTML
            main_content = extract(html_content, include_comments=False, include_tables=False)

            if not main_content:
                logger.warning(f"Could not extract content from {article.local_path}. Marking as failed.")
                article.status = ArticleStatus.failed
                db.commit()
                continue

            # Summarize with LLM
            summary_data = summarize_article(main_content)
            if summary_data:
                article.short_summary = summary_data.short_summary
                article.detailed_summary = summary_data.detailed_summary
                article.status = ArticleStatus.processed
                logger.info(f"Successfully processed and summarized article ID: {article.id}")
            else:
                logger.error(f"LLM summarization failed for article ID: {article.id}")
                article.status = ArticleStatus.failed

            db.commit()

        except FileNotFoundError:
            logger.error(f"File not found for article ID: {article.id} at {article.local_path}. Marking as failed.")
            article.status = ArticleStatus.failed
            db.commit()
        except Exception as e:
            logger.error(f"An unexpected error occurred while processing article ID {article.id}: {e}", exc_info=True)
            article.status = ArticleStatus.failed
            db.rollback()

def main():
    """Main function to run the local article processor."""
    db = SessionLocal()
    try:
        process_new_local_articles(db)
    finally:
        db.close()

if __name__ == "__main__":
    logger.info("Starting local article processing script...")
    main()
    logger.info("Local article processing script finished.")