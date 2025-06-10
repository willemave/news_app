"""
Pipeline orchestrator for link processing.
Coordinates workers and manages the state machine-driven pipeline.
"""

import time
import threading
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy import func
from app.database import SessionLocal
from app.models import Links, LinkStatus
from app.config import logger
from app.links.checkout_manager import LinkCheckoutManager
from app.links.link_processor import LinkProcessorWorker
from app.constants import (
    DEFAULT_POLLING_INTERVAL_SECONDS,
    DEFAULT_DOWNLOADER_CONCURRENCY
)


class LinkPipelineOrchestrator:
    """Orchestrates the link processing pipeline."""
    
    def __init__(self, 
                 processor_concurrency: int = DEFAULT_DOWNLOADER_CONCURRENCY,
                 polling_interval: int = DEFAULT_POLLING_INTERVAL_SECONDS):
        """
        Initialize the pipeline orchestrator.
        
        Args:
            processor_concurrency: Number of concurrent processor workers
            polling_interval: Polling interval in seconds
        """
        self.processor_concurrency = processor_concurrency
        self.polling_interval = polling_interval
        
        # Worker instances
        self.processors = [LinkProcessorWorker(instance_id=str(i+1)) for i in range(processor_concurrency)]
        
        # Control flags
        self.running = False
        self.shutdown_event = threading.Event()
        
        # Statistics
        self.stats = {
            'cycles_completed': 0,
            'total_processed': 0,
            'links_processed': 0,
            'links_failed': 0,
            'links_skipped': 0,
            'errors': 0
        }
    
    def find_available_links(self, state: LinkStatus, limit: int = 10) -> List[Links]:
        """
        Find links available for processing in the given state.
        
        Args:
            state: Link state to search for
            limit: Maximum number of links to return
            
        Returns:
            List of available link objects
        """
        db = SessionLocal()
        checkout_manager = LinkCheckoutManager(db)
        
        try:
            return checkout_manager.find_available_links(state, limit)
        finally:
            db.close()
    
    def dispatch_processor_workers(self) -> Dict[str, int]:
        """
        Dispatch processor workers to process available links.
        
        Returns:
            Dictionary with processing statistics
        """
        available_links = self.find_available_links(LinkStatus.new, self.processor_concurrency * 2)
        
        if not available_links:
            return {"processed": 0, "failed": 0, "skipped": 0, "total": 0}
        
        processed = 0
        failed = 0
        skipped = 0
        
        # Use ThreadPoolExecutor for concurrent processing
        with ThreadPoolExecutor(max_workers=self.processor_concurrency) as executor:
            # Submit processing tasks
            future_to_link = {}
            for i, link in enumerate(available_links[:self.processor_concurrency]):
                processor = self.processors[i % len(self.processors)]
                future = executor.submit(processor.process_link, link.id)
                future_to_link[future] = link
            
            # Collect results
            for future in as_completed(future_to_link):
                link = future_to_link[future]
                try:
                    success = future.result()
                    if success:
                        # Check final status to determine if processed or skipped
                        db = SessionLocal()
                        try:
                            updated_link = db.query(Links).filter(Links.id == link.id).first()
                            if updated_link and updated_link.status == LinkStatus.skipped:
                                skipped += 1
                            else:
                                processed += 1
                        finally:
                            db.close()
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(f"Processor worker exception for link {link.id}: {e}")
                    failed += 1
        
        if processed > 0 or failed > 0 or skipped > 0:
            logger.debug(f"Processing dispatch complete: {processed} processed, {skipped} skipped, {failed} failed")
        
        return {"processed": processed, "failed": failed, "skipped": skipped, "total": processed + failed + skipped}
    
    def release_stale_checkouts(self) -> int:
        """
        Release stale checkouts across all workers.
        
        Returns:
            Number of stale checkouts released
        """
        db = SessionLocal()
        checkout_manager = LinkCheckoutManager(db)
        
        try:
            return checkout_manager.release_stale_checkouts()
        finally:
            db.close()
    
    def log_link_status_summary(self) -> None:
        """Logs the summary of link statuses."""
        db = SessionLocal()
        try:
            summary = (
                db.query(Links.status, func.count(Links.id))
                .filter(Links.checked_out_by.is_(None))
                .group_by(Links.status)
                .all()
            )
            if summary:
                logger.debug("--- Link Status Summary (available) ---")
                for status, count in summary:
                    logger.debug(f"{status.name}|{count}")
                logger.debug("------------------------------------")
        except Exception as e:
            logger.error(f"Could not retrieve link status summary: {e}")
        finally:
            db.close()

    def run_single_cycle(self) -> Dict[str, Dict[str, int]]:
        """
        Run a single processing cycle.
        
        Returns:
            Dictionary with cycle statistics
        """
        self.log_link_status_summary()

        cycle_stats = {
            'processing': {"processed": 0, "failed": 0, "skipped": 0, "total": 0},
            'stale_checkouts_released': 0
        }
        
        try:
            # Release stale checkouts first
            cycle_stats['stale_checkouts_released'] = self.release_stale_checkouts()
            
            # Dispatch workers for processing
            cycle_stats['processing'] = self.dispatch_processor_workers()
            
            # Update statistics
            self.stats['cycles_completed'] += 1
            self.stats['links_processed'] += cycle_stats['processing']['processed']
            self.stats['links_failed'] += cycle_stats['processing']['failed']
            self.stats['links_skipped'] += cycle_stats['processing']['skipped']
            self.stats['total_processed'] += cycle_stats['processing']['total']
            self.stats['errors'] += cycle_stats['processing']['failed']
            
        except Exception as e:
            logger.error(f"Error in processing cycle: {e}", exc_info=True)
            self.stats['errors'] += 1
        
        return cycle_stats
    
    def run(self) -> None:
        """
        Run the pipeline orchestrator continuously until no more work is available.
        """
        self.running = True
        logger.info("Link pipeline orchestrator starting...")
        logger.info(f"Worker configuration: {self.processor_concurrency} processors")
        logger.info(f"Polling interval: {self.polling_interval} seconds")
        
        try:
            while self.running and not self.shutdown_event.is_set():
                cycle_start = time.time()
                
                # Check for shutdown before starting cycle
                if self.shutdown_event.is_set():
                    logger.info("Shutdown event detected, stopping cycle")
                    break
                
                # Run processing cycle
                cycle_stats = self.run_single_cycle()
                
                # Log cycle summary if any work was done
                total_work = cycle_stats['processing']['total']
                
                if total_work > 0 or cycle_stats['stale_checkouts_released'] > 0:
                    logger.debug(f"Cycle {self.stats['cycles_completed']} complete: "
                               f"processing={cycle_stats['processing']}, "
                               f"stale_released={cycle_stats['stale_checkouts_released']}")
                
                # If no work was done, we're finished
                if total_work == 0 and cycle_stats['stale_checkouts_released'] == 0:
                    logger.info("No more work available, pipeline complete")
                    break
                
                # Wait for next cycle if there might be more work
                cycle_duration = time.time() - cycle_start
                sleep_time = max(0, self.polling_interval - cycle_duration)
                
                if sleep_time > 0:
                    # Use shorter intervals to check for shutdown more frequently
                    remaining_time = sleep_time
                    while remaining_time > 0 and not self.shutdown_event.is_set():
                        sleep_interval = min(0.1, remaining_time)  # Check every 100ms
                        self.shutdown_event.wait(sleep_interval)
                        remaining_time -= sleep_interval
                
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down...")
        except Exception as e:
            logger.error(f"Unexpected error in link pipeline orchestrator: {e}", exc_info=True)
        finally:
            self.running = False
            logger.info("Link pipeline orchestrator stopped")
            self.log_final_stats()
            self.cleanup()
    
    def shutdown(self) -> None:
        """
        Initiate graceful shutdown of the orchestrator.
        """
        logger.info("Shutting down link pipeline orchestrator...")
        self.running = False
        self.shutdown_event.set()
    
    def cleanup(self) -> None:
        """
        Clean up resources used by the orchestrator.
        """
        for processor in self.processors:
            processor.cleanup()
    
    def get_status(self) -> Dict:
        """
        Get current pipeline status.
        
        Returns:
            Dictionary with pipeline status information
        """
        db = SessionLocal()
        checkout_manager = LinkCheckoutManager(db)
        
        try:
            checkout_status = checkout_manager.get_checkout_status()
            
            return {
                'running': self.running,
                'worker_config': {
                    'processors': self.processor_concurrency
                },
                'polling_interval': self.polling_interval,
                'statistics': self.stats.copy(),
                'checkout_status': checkout_status
            }
        finally:
            db.close()
    
    def log_final_stats(self) -> None:
        """Log final statistics on shutdown."""
        logger.info("=== Link Pipeline Orchestrator Final Statistics ===")
        logger.info(f"Cycles completed: {self.stats['cycles_completed']}")
        logger.info(f"Total links processed: {self.stats['total_processed']}")
        logger.info(f"Links successfully processed: {self.stats['links_processed']}")
        logger.info(f"Links skipped: {self.stats['links_skipped']}")
        logger.info(f"Links failed: {self.stats['links_failed']}")
        logger.info(f"Total errors: {self.stats['errors']}")
        logger.info("=====================================================")