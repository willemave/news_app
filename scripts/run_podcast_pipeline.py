#!/usr/bin/env python3
"""
Production podcast pipeline runner.
Runs the complete podcast pipeline based on podcasts.yml configuration
using the new state machine architecture with checkout/checkin mechanism.
"""

import sys
import os
import signal
import argparse
import logging
from datetime import datetime
from typing import Dict

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scraping.podcast_rss_scraper import run_podcast_scraper
from app.podcast.pipeline_orchestrator import PipelineOrchestrator
from app.podcast.checkout_manager import CheckoutManager
from app.database import SessionLocal
from app.models import Podcasts, PodcastStatus
from app.config import logger, setup_logging


class PodcastPipelineRunner:
    """
    Orchestrates the complete podcast pipeline using state machine architecture.
    """
    
    def __init__(self, config_path: str = 'config/podcasts.yml'):
        self.config_path = config_path
        self.orchestrator = None
        self.start_time = datetime.now()
        self.initial_stats = {}
        self.shutdown_requested = False
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_requested = True
        if self.orchestrator:
            self.orchestrator.shutdown()
        # Exit immediately for SIGINT (Ctrl+C)
        if signum == signal.SIGINT:
            logger.info("SIGINT received, forcing exit...")
            import sys
            sys.exit(130)

    def run_pipeline(self) -> Dict[str, any]:
        """
        Run the complete podcast pipeline using state machine architecture.
        
        Returns:
            Dictionary with pipeline execution results
        """
        logger.info("🎙️  Starting Podcast Pipeline Runner (State Machine)")
        logger.info(f"Configuration: {self.config_path}")
        logger.info(f"Start time: {self.start_time}")
        
        try:
            # Get initial statistics
            self.initial_stats = self._get_podcast_stats()
            logger.info(f"Initial podcast statistics: {self.initial_stats}")
            
            # Phase 1: RSS Scraping
            logger.info("\n" + "="*60)
            logger.info("PHASE 1: RSS SCRAPING")
            logger.info("="*60)
            
            scraping_result = self._run_rss_scraping()
            if not scraping_result['success']:
                logger.error("RSS scraping failed, aborting pipeline")
                return self._create_failure_result("RSS scraping failed")
            
            # Phase 2: State Machine Pipeline Processing
            logger.info("\n" + "="*60)
            logger.info("PHASE 2: STATE MACHINE PIPELINE PROCESSING")
            logger.info("="*60)
            
            processing_result = self._run_state_machine_processing()
            
            # Final statistics and summary
            final_stats = self._get_podcast_stats()
            summary = self._generate_pipeline_summary(final_stats)
            
            logger.info("\n" + "="*60)
            logger.info("PIPELINE EXECUTION COMPLETE")
            logger.info("="*60)
            logger.info(summary['message'])
            
            return {
                'success': True,
                'phases': {
                    'scraping': scraping_result,
                    'processing': processing_result
                },
                'initial_stats': self.initial_stats,
                'final_stats': final_stats,
                'summary': summary,
                'execution_time': (datetime.now() - self.start_time).total_seconds()
            }
            
        except KeyboardInterrupt:
            logger.info("Pipeline interrupted by user")
            return self._create_failure_result("Pipeline interrupted by user")
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}", exc_info=True)
            return self._create_failure_result(f"Pipeline execution failed: {e}")
        finally:
            if self.orchestrator:
                self.orchestrator.shutdown()

    def _run_rss_scraping(self) -> Dict[str, any]:
        """Run RSS scraping phase."""
        try:
            initial_count = self._get_podcast_count()
            logger.info(f"Starting RSS scraping with {initial_count} existing podcasts")
            
            # Run scraper synchronously
            run_podcast_scraper(debug=self.debug)
            
            new_count = self._get_podcast_count()
            new_podcasts = new_count - initial_count
            
            logger.info(f"RSS scraping complete: {new_podcasts} new podcasts discovered")
            
            return {
                'success': True,
                'initial_count': initial_count,
                'final_count': new_count,
                'new_podcasts': new_podcasts
            }
            
        except Exception as e:
            logger.error(f"RSS scraping failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    def _run_state_machine_processing(self) -> Dict[str, any]:
        """Run state machine pipeline processing."""
        try:
            logger.info("Starting state machine pipeline orchestrator")
            
            # Initialize orchestrator
            self.orchestrator = PipelineOrchestrator()
            
            # Get initial work available
            initial_work = self._count_available_work()
            logger.info(f"Available work: {initial_work}")
            
            if sum(initial_work.values()) == 0:
                logger.info("No work available for processing")
                return {
                    'success': True,
                    'message': 'No work available',
                    'cycles_completed': 0
                }
            
            # Run the orchestrator
            logger.info("Starting pipeline orchestrator...")
            
            # Check for shutdown before starting
            if self.shutdown_requested:
                logger.info("Shutdown requested before orchestrator start")
                return {
                    'success': True,
                    'message': 'Shutdown requested',
                    'cycles_completed': 0
                }
            
            self.orchestrator.run()
            
            # Get final statistics
            final_stats = self.orchestrator.get_status()
            
            logger.info(f"Pipeline orchestrator completed: {final_stats['statistics']['cycles_completed']} cycles")
            logger.info(f"Total processed: {final_stats['statistics']['total_processed']}")
            
            return {
                'success': True,
                'statistics': final_stats['statistics'],
                'checkout_status': final_stats['checkout_status']
            }
            
        except Exception as e:
            logger.error(f"State machine processing failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    def _count_available_work(self) -> Dict[str, int]:
        """Count available work for each processing stage."""
        db = SessionLocal()
        checkout_manager = CheckoutManager(db)
        
        try:
            available_work = {}
            for status in [PodcastStatus.new, PodcastStatus.downloaded, PodcastStatus.transcribed]:
                available_podcasts = checkout_manager.find_available_podcasts(status, limit=100)
                available_work[status.value] = len(available_podcasts)
            
            return available_work
        finally:
            db.close()

    def _get_podcast_count(self) -> int:
        """Get total podcast count."""
        db = SessionLocal()
        try:
            return db.query(Podcasts).count()
        finally:
            db.close()

    def _get_podcast_stats(self) -> Dict[str, int]:
        """Get podcast statistics by status."""
        db = SessionLocal()
        try:
            stats = {}
            for status in PodcastStatus:
                count = db.query(Podcasts).filter(Podcasts.status == status).count()
                stats[status.value] = count
            return stats
        finally:
            db.close()

    def _generate_pipeline_summary(self, final_stats: Dict[str, int]) -> Dict[str, any]:
        """Generate pipeline execution summary."""
        # Calculate changes
        changes = {}
        for status in PodcastStatus:
            initial = self.initial_stats.get(status.value, 0)
            final = final_stats.get(status.value, 0)
            changes[status.value] = final - initial

        # Generate summary message
        total_processed = changes.get('summarized', 0)
        total_failed = changes.get('failed', 0)
        execution_time = (datetime.now() - self.start_time).total_seconds()
        
        if total_processed > 0:
            message = f"✅ Pipeline completed successfully! {total_processed} podcasts fully processed"
            if total_failed > 0:
                message += f" ({total_failed} failed)"
            message += f" in {execution_time:.1f}s"
        elif total_failed > 0:
            message = f"⚠️  Pipeline completed with {total_failed} failures in {execution_time:.1f}s"
        else:
            message = f"ℹ️  Pipeline completed with no new processing in {execution_time:.1f}s"

        return {
            'message': message,
            'changes': changes,
            'execution_time': execution_time,
            'total_processed': total_processed,
            'total_failed': total_failed
        }

    def _create_failure_result(self, error_message: str) -> Dict[str, any]:
        """Create failure result dictionary."""
        execution_time = (datetime.now() - self.start_time).total_seconds()
        return {
            'success': False,
            'error': error_message,
            'execution_time': execution_time,
            'initial_stats': self.initial_stats
        }


def main():
    """Main entry point for the podcast pipeline runner."""
    parser = argparse.ArgumentParser(description="Podcast Pipeline Runner")
    parser.add_argument(
        "--config",
        type=str,
        default="config/podcasts.yml",
        help="Path to the podcast configuration file"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    args = parser.parse_args()

    # Setup logging
    if args.debug:
        setup_logging(logging.DEBUG)
    else:
        setup_logging(logging.INFO)

    # Initialize and run pipeline
    runner = PodcastPipelineRunner(config_path=args.config)
    
    try:
        result = runner.run_pipeline()
        
        # Print final summary
        print("\n" + "="*60)
        print("PODCAST PIPELINE EXECUTION SUMMARY")
        print("="*60)
        
        if result['success']:
            print("✅ Status: SUCCESS")
            if 'summary' in result:
                print(f"📊 Result: {result['summary']['message']}")
                print(f"⏱️  Execution time: {result['execution_time']:.1f} seconds")
                
                # Show detailed changes
                if 'changes' in result['summary']:
                    print("\n📈 Status Changes:")
                    for status, change in result['summary']['changes'].items():
                        if change != 0:
                            print(f"   {status}: {change:+d}")
            
            return 0
        else:
            print("❌ Status: FAILED")
            print(f"💥 Error: {result.get('error', 'Unknown error')}")
            print(f"⏱️  Execution time: {result.get('execution_time', 0):.1f} seconds")
            return 1
            
    except KeyboardInterrupt:
        print("\n⚠️  Pipeline interrupted by user")
        return 130
    except Exception as e:
        print(f"\n💥 Pipeline crashed: {e}")
        logger.error(f"Pipeline crashed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    # Run the main function
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.warning("\nInterrupted by user")
        sys.exit(130)