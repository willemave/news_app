"""
Full ingestion pipeline script (triggered by cron or manual run).
This script runs both steps of the ingestion pipeline:
1. Daily ingest - fetches new articles and adds them to the database
2. Article processing - processes articles, scrapes content, and generates summaries
"""
import sys
import time
from daily_ingest import run_daily_ingest
from process_articles import process_articles

def run_full_pipeline(process_batch_size=20, delay_seconds=5):
    """
    Run the full ingestion pipeline: fetch new articles and then process them.
    
    Args:
        process_batch_size: Number of articles to process in this run
        delay_seconds: Delay between ingestion and processing steps
    """
    print("=== Starting Full Ingestion Pipeline ===")
    
    # Step 1: Run daily ingest to fetch new articles
    print("\n== Step 1: Daily Ingest ==")
    run_daily_ingest()
    
    # Optional delay between steps
    if delay_seconds > 0:
        print(f"\nWaiting {delay_seconds} seconds before processing...")
        time.sleep(delay_seconds)
    
    # Step 2: Process articles
    print("\n== Step 2: Article Processing ==")
    processed, approved, errors = process_articles(batch_size=process_batch_size)
    
    # Summary
    print("\n=== Pipeline Summary ===")
    print(f"Articles processed: {processed}")
    print(f"Articles approved: {approved}")
    print(f"Errors encountered: {errors}")
    print("=== Pipeline Complete ===")
    
    return processed, approved, errors

if __name__ == "__main__":
    # Get batch size from command line if provided
    batch_size = 20
    if len(sys.argv) > 1:
        try:
            batch_size = int(sys.argv[1])
        except ValueError:
            print(f"Invalid batch size: {sys.argv[1]}. Using default: 20")
    
    run_full_pipeline(process_batch_size=batch_size) 