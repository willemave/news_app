"""
Article processing script (triggered by cron or admin).
This script is responsible for:
1. Fetching unprocessed articles from the database
2. Scraping their content
3. Applying LLM filtering
4. Generating summaries for approved articles
5. Updating article status
"""
import datetime
from sqlalchemy.orm import Session
from app.database import SessionLocal, init_db
from app.models import Articles, ArticleStatus, CronLogs
from app.processor import download_and_process_content
from app.llm import filter_article, summarize_article

def process_articles(batch_size=10):
    """
    Process a batch of new articles that have been added to the database.
    
    Args:
        batch_size: Number of articles to process in one run
    
    Returns:
        tuple: (processed_count, approved_count, error_count)
    """
    db = SessionLocal()
    init_db()
    
    # Create a log entry
    cron_log = CronLogs()
    db.add(cron_log)
    db.commit()
    db.refresh(cron_log)
    
    # Get articles with status "new"
    new_articles = db.query(Articles).filter(
        Articles.status == ArticleStatus.new
    ).limit(batch_size).all()
    
    if not new_articles:
        print("No new articles to process")
        return (0, 0, 0)
    
    processed_count = 0
    approved_count = 0
    errors = []
    
    for article in new_articles:
        try:
            # Scrape article content
            data = download_and_process_content(article.url)
            if not data or not data.get("content"):
                article.status = ArticleStatus.failed
                db.commit()
                errors.append(f"Failed to scrape {article.url}")
                continue
                
            # Update article with scraped data
            article.title = data.get("title") or article.title
            article.author = data.get("author")
            article.publication_date = data.get("publication_date") or article.publication_date
            article.status = ArticleStatus.scraped
            db.commit()
            
            processed_count += 1
            
            # Apply LLM filtering
            if filter_article(data.get("content")):
                # Generate summaries for approved articles
                summaries = summarize_article(data.get("content"))
                
                # Handle both dict and tuple return formats
                if isinstance(summaries, dict):
                    short_summary = summaries.get("short", "")
                    detailed_summary = summaries.get("detailed", "")
                else:
                    # Fallback for tuple format
                    short_summary = summaries[0] if len(summaries) > 0 else ""
                    detailed_summary = summaries[1] if len(summaries) > 1 else ""
                
                # Update article with summary data
                article.short_summary = short_summary
                article.detailed_summary = detailed_summary
                article.summary_date = datetime.datetime.utcnow()
                article.status = ArticleStatus.approved
                db.commit()
                
                approved_count += 1
            else:
                # Article didn't pass the filter
                article.status = ArticleStatus.processed
                db.commit()
                
        except Exception as e:
            errors.append(f"Error processing {article.url}: {str(e)}")
            article.status = ArticleStatus.failed
            db.commit()
    
    # Update log
    cron_log.links_fetched = len(new_articles)
    cron_log.successful_scrapes = processed_count
    if errors:
        cron_log.errors = str(errors)
    db.commit()
    db.close()
    
    print(f"Processing complete: {processed_count} articles processed, {approved_count} approved, {len(errors)} errors")
    return (processed_count, approved_count, len(errors))

if __name__ == "__main__":
    process_articles()
