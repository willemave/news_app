#!/usr/bin/env python3
"""
Test script for the podcast pipeline.
Tests RSS scraping, downloading, transcription, and summarization.
"""

import sys
import os
import asyncio

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scraping.podcast_rss_scraper import run_podcast_scraper
from app.processing.podcast_processor import PodcastProcessor
from app.queue import drain_queue
from app.database import SessionLocal
from app.models import Podcasts, PodcastStatus
from app.config import logger

def test_rss_scraping(debug=False):
    """Test podcast RSS scraping."""
    print("\n=== Testing Podcast RSS Scraping ===")
    
    try:
        # Get initial count
        db = SessionLocal()
        initial_count = db.query(Podcasts).count()
        db.close()
        
        print(f"Initial podcast count: {initial_count}")
        
        if debug:
            print("\n--- DEBUG MODE: Testing individual feeds ---")
            from app.scraping.podcast_rss_scraper import PodcastRSSScraper
            import feedparser
            
            # Test the problematic feed specifically
            scraper = PodcastRSSScraper(debug=True)
            
            # Test "Honestly with Bari Weiss" feed specifically
            test_feed = {
                'name': 'Honestly with Bari Weiss',
                'url': 'https://feeds.megaphone.fm/rsv2347142881',
                'limit': 3
            }
            
            print(f"\nTesting feed: {test_feed['name']}")
            print(f"URL: {test_feed['url']}")
            
            try:
                parsed_feed = feedparser.parse(test_feed['url'])
                print(f"Feed parsed successfully. Bozo: {parsed_feed.bozo}")
                print(f"Total entries: {len(parsed_feed.entries)}")
                
                if len(parsed_feed.entries) > 0:
                    print(f"\nFirst entry details:")
                    entry = parsed_feed.entries[0]
                    print(f"  Title: {entry.get('title', 'No Title')}")
                    print(f"  Link: {entry.get('link', 'No Link')}")
                    print(f"  Available keys: {list(entry.keys())}")
                    
                    if hasattr(entry, 'links'):
                        print(f"  Links found: {len(entry.links)}")
                        for i, link_item in enumerate(entry.links):
                            print(f"    Link {i}: href='{link_item.get('href')}', type='{link_item.get('type')}', rel='{link_item.get('rel')}'")
                    
                    if hasattr(entry, 'enclosures'):
                        print(f"  Enclosures found: {len(entry.enclosures)}")
                        for i, enclosure in enumerate(entry.enclosures):
                            print(f"    Enclosure {i}: href='{enclosure.href}', type='{enclosure.type}'")
                
            except Exception as feed_error:
                print(f"Error testing feed: {feed_error}")
            
            print("\n--- Running full scraper with debug ---")
        
        # Run scraper with debug if requested
        run_podcast_scraper(debug=debug)
        
        # Get new count
        db = SessionLocal()
        new_count = db.query(Podcasts).count()
        new_podcasts = db.query(Podcasts).filter(Podcasts.status == PodcastStatus.new).count()
        db.close()
        
        print(f"New podcast count: {new_count}")
        print(f"New podcasts to process: {new_podcasts}")
        
        if new_count > initial_count:
            print("✅ RSS scraping successful - new podcasts found")
        else:
            print("ℹ️  RSS scraping complete - no new podcasts (may be expected)")
            
        return True
        
    except Exception as e:
        print(f"❌ RSS scraping failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_podcast_processing(max_podcasts=10):
    """Test the full podcast processing pipeline with a limited number of podcasts."""
    print(f"\n=== Testing Full Podcast Processing Pipeline (max {max_podcasts} podcasts) ===")
    
    try:
        from app.database import SessionLocal
        from app.models import Podcasts, PodcastStatus
        from app.processing.podcast_processor import PodcastProcessor
        
        # Initialize processor
        processor = PodcastProcessor()
        
        # Get initial stats
        print("Getting initial podcast statistics...")
        initial_stats = processor.get_podcast_stats()
        print(f"Initial stats: {initial_stats}")
        
        # Limit the number of new podcasts to process
        db = SessionLocal()
        try:
            new_podcasts = db.query(Podcasts).filter(Podcasts.status == PodcastStatus.new).limit(max_podcasts).all()
            
            if not new_podcasts:
                print("No new podcasts to process")
                return True
                
            print(f"Found {len(new_podcasts)} new podcasts to process")
            for podcast in new_podcasts:
                print(f"  - {podcast.title[:60]}...")
            
        finally:
            db.close()
        
        # Process all pending podcasts through the full pipeline
        print("\nStarting full pipeline processing...")
        print("This will queue tasks for download → transcription → summarization")
        
        # Process all pending podcasts at each stage
        results = processor.process_all_pending_podcasts()
        print(f"Pipeline queuing results: {results}")
        
        # Drain the queue to process all tasks
        print("\nDraining queue to process all tasks...")
        print("This may take several minutes for transcription and summarization...")
        drain_queue()
        
        # Get final stats
        print("\nGetting final podcast statistics...")
        final_stats = processor.get_podcast_stats()
        print(f"Final stats: {final_stats}")
        
        # Show progress made
        print("\n=== Pipeline Progress Summary ===")
        for status in PodcastStatus:
            initial_count = initial_stats.get(status.value, 0)
            final_count = final_stats.get(status.value, 0)
            change = final_count - initial_count
            if change != 0:
                print(f"{status.value}: {initial_count} → {final_count} ({change:+d})")
        
        # Check if we have any completed podcasts
        summarized_count = final_stats.get('summarized', 0)
        if summarized_count > 0:
            print(f"\n✅ Successfully completed {summarized_count} podcasts through full pipeline")
            
            # Show a sample of completed podcasts
            db = SessionLocal()
            try:
                completed_podcasts = db.query(Podcasts).filter(
                    Podcasts.status == PodcastStatus.summarized
                ).limit(3).all()
                
                print("\nSample completed podcasts:")
                for podcast in completed_podcasts:
                    print(f"  📻 {podcast.title}")
                    print(f"     Feed: {podcast.podcast_feed_name}")
                    if podcast.short_summary:
                        print(f"     Summary: {podcast.short_summary[:100]}...")
                    print()
            finally:
                db.close()
        else:
            print("\n⚠️  No podcasts completed the full pipeline")
        
        return True
        
    except Exception as e:
        print(f"❌ Podcast processing failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_individual_podcast():
    """Test processing a single podcast through the full pipeline."""
    print("\n=== Testing Individual Podcast Full Pipeline ===")
    
    try:
        db = SessionLocal()
        
        # Find a podcast to test with
        podcast = db.query(Podcasts).filter(Podcasts.status == PodcastStatus.new).first()
        
        if not podcast:
            print("ℹ️  No new podcasts available for individual testing")
            db.close()
            return True
        
        print(f"Testing with podcast: {podcast.title}")
        print(f"Feed: {podcast.podcast_feed_name}")
        print(f"URL: {podcast.enclosure_url}")
        
        db.close()
        
        # Queue the initial download task - the pipeline will automatically progress
        from app.queue import download_podcast_task
        print("\n🚀 Starting full pipeline by queuing download task...")
        print("The queue system will automatically progress: download → transcribe → summarize")
        
        download_podcast_task(podcast.id)
        
        # Drain the queue to process all tasks in the pipeline
        print("\nDraining queue to process full pipeline...")
        print("This will process download, transcription, and summarization sequentially...")
        drain_queue()
        
        # Check final status and show progress
        db = SessionLocal()
        try:
            updated_podcast = db.query(Podcasts).filter(Podcasts.id == podcast.id).first()
            
            print(f"\n=== Pipeline Results ===")
            print(f"Final status: {updated_podcast.status}")
            
            if updated_podcast.status == PodcastStatus.downloaded:
                print("✅ Download completed")
                print("⚠️  Pipeline stopped at download stage")
                if updated_podcast.error_message:
                    print(f"Error: {updated_podcast.error_message}")
                    
            elif updated_podcast.status == PodcastStatus.transcribed:
                print("✅ Download completed")
                print("✅ Transcription completed")
                print("⚠️  Pipeline stopped at transcription stage")
                if updated_podcast.error_message:
                    print(f"Error: {updated_podcast.error_message}")
                    
            elif updated_podcast.status == PodcastStatus.summarized:
                print("✅ Download completed")
                print("✅ Transcription completed")
                print("✅ Summarization completed")
                print("🎉 Full pipeline successful!")
                
                if updated_podcast.file_path:
                    print(f"Audio file: {updated_podcast.file_path}")
                if updated_podcast.transcribed_text_path:
                    print(f"Transcript: {updated_podcast.transcribed_text_path}")
                if updated_podcast.short_summary:
                    print(f"Short summary: {updated_podcast.short_summary[:150]}...")
                if updated_podcast.detailed_summary:
                    print(f"Detailed summary: {updated_podcast.detailed_summary[:200]}...")
                    
            elif updated_podcast.status == PodcastStatus.failed:
                print("❌ Pipeline failed")
                if updated_podcast.error_message:
                    print(f"Error: {updated_podcast.error_message}")
            else:
                print(f"⚠️  Unexpected status: {updated_podcast.status}")
                
        finally:
            db.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Individual podcast test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all podcast pipeline tests."""
    print("🎙️  Starting Podcast Pipeline Tests")
    
    # Check for debug mode
    debug_mode = '--debug' in sys.argv
    if debug_mode:
        print("🐛 DEBUG MODE ENABLED")
    
    # Configurable number of podcasts to test
    MAX_PODCASTS = 10
    
    tests = [
        ("RSS Scraping", lambda: test_rss_scraping(debug=debug_mode)),
        ("Pipeline Processing", lambda: test_podcast_processing(MAX_PODCASTS)),
        ("Individual Podcast", test_individual_podcast),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Running: {test_name}")
        print('='*50)
        
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ Test {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print(f"\n{'='*50}")
    print("TEST SUMMARY")
    print('='*50)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name}: {status}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)