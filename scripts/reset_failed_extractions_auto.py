"""
Script to reset failed article extractions for reprocessing (non-interactive).

This script finds all articles with "Extraction Failed" titles and resets their status
to allow the pipeline to reprocess them.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.settings import get_settings
from app.models.schema import Content
from app.models.metadata import ContentStatus
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

def reset_failed_extractions(auto_confirm=True):
    """Reset all articles that failed extraction back to 'new' status."""
    
    # Create database connection
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    
    with Session() as session:
        try:
            # Find all content with "Extraction Failed" title
            failed_content = session.query(Content).filter(
                Content.title == "Extraction Failed"
            ).all()
            
            logger.info(f"Found {len(failed_content)} articles with failed extraction")
            
            if not failed_content:
                print("No failed extractions found.")
                return
            
            # Show URLs that will be reset
            print(f"\nFound {len(failed_content)} failed extractions:")
            for content in failed_content[:10]:  # Show first 10
                print(f"  - {content.url}")
            if len(failed_content) > 10:
                print(f"  ... and {len(failed_content) - 10} more")
            
            if not auto_confirm:
                return
            
            print("\nResetting articles...")
            
            # Reset each failed article
            reset_count = 0
            for content in failed_content:
                # Reset status and clear error fields
                content.status = ContentStatus.NEW
                content.error_message = None
                content.retry_count = 0
                content.checked_out_by = None
                content.checked_out_at = None
                content.processed_at = None
                
                # Clear the failed title
                content.title = None
                
                # Clear any partial metadata
                if content.content_metadata:
                    # Keep the URL but clear extracted data
                    metadata_keys_to_remove = ['title', 'text_content', 'content']
                    for key in metadata_keys_to_remove:
                        if key in content.content_metadata:
                            del content.content_metadata[key]
                
                reset_count += 1
            
            # Commit the changes
            session.commit()
            logger.info(f"Successfully reset {reset_count} failed articles")
            print(f"\n✓ Reset {reset_count} articles to 'new' status for reprocessing")
            
            # Also reset articles that might be stuck in processing
            stuck_processing = session.query(Content).filter(
                Content.status == ContentStatus.PROCESSING,
                Content.checked_out_by.isnot(None)
            ).all()
            
            if stuck_processing:
                print(f"\nFound {len(stuck_processing)} articles stuck in 'processing' status.")
                print("Resetting stuck articles...")
                
                for content in stuck_processing:
                    content.status = ContentStatus.NEW
                    content.checked_out_by = None
                    content.checked_out_at = None
                
                session.commit()
                print(f"✓ Reset {len(stuck_processing)} stuck articles")
                reset_count += len(stuck_processing)
            
            return reset_count
            
        except Exception as e:
            logger.error(f"Error resetting failed extractions: {e}")
            print(f"\n✗ Error: {e}")
            session.rollback()
            raise

def show_statistics():
    """Show current content processing statistics."""
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    
    with Session() as session:
        # Get counts by status
        stats_query = text("""
            SELECT status, COUNT(*) as count 
            FROM contents 
            WHERE content_type = 'article'
            GROUP BY status
            ORDER BY count DESC
        """)
        
        results = session.execute(stats_query).fetchall()
        
        print("\nCurrent article processing statistics:")
        print("-" * 40)
        total = 0
        for status, count in results:
            print(f"{status:12} : {count:6} articles")
            total += count
        print("-" * 40)
        print(f"{'TOTAL':12} : {total:6} articles")
        
        # Check failed extractions specifically
        failed_extractions = session.query(Content).filter(
            Content.title == "Extraction Failed"
        ).count()
        
        if failed_extractions > 0:
            print(f"\n⚠️  {failed_extractions} articles have 'Extraction Failed' title")

if __name__ == "__main__":
    print("Article Extraction Reset Tool (Auto)")
    print("=" * 40)
    
    # Show current statistics
    show_statistics()
    
    # Reset failed extractions automatically
    print("\n")
    total_reset = reset_failed_extractions(auto_confirm=True)
    
    # Show updated statistics
    if total_reset and total_reset > 0:
        print("\nUpdated statistics:")
        show_statistics()
    
    print("\n✅ Done!")