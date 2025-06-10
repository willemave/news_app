"""
Pipeline orchestrator for podcast processing.
Coordinates workers and manages the state machine-driven pipeline.
"""

import time
import threading
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.database import SessionLocal
from app.models import Podcasts, PodcastStatus
from app.config import logger
from app.podcast.checkout_manager import CheckoutManager
from app.podcast.podcast_downloader import PodcastDownloader
from app.podcast.podcast_converter import PodcastConverter
from app.podcast.podcast_summarizer import PodcastSummarizer
from app.constants import (
    DEFAULT_POLLING_INTERVAL_SECONDS,
    DEFAULT_DOWNLOADER_CONCURRENCY,
    DEFAULT_TRANSCRIBER_CONCURRENCY,
    DEFAULT_SUMMARIZER_CONCURRENCY
)


class PipelineOrchestrator:
    """Orchestrates the podcast processing pipeline."""
    
    def __init__(self, 
                 downloader_concurrency: int = DEFAULT_DOWNLOADER_CONCURRENCY,
                 transcriber_concurrency: int = DEFAULT_TRANSCRIBER_CONCURRENCY,
                 summarizer_concurrency: int = DEFAULT_SUMMARIZER_CONCURRENCY,
                 polling_interval: int = DEFAULT_POLLING_INTERVAL_SECONDS):
        """
        Initialize the pipeline orchestrator.
        
        Args:
            downloader_concurrency: Number of concurrent download workers
            transcriber_concurrency: Number of concurrent transcription workers
            summarizer_concurrency: Number of concurrent summarization workers
            polling_interval: Polling interval in seconds
        """
        self.downloader_concurrency = downloader_concurrency
        self.transcriber_concurrency = transcriber_concurrency
        self.summarizer_concurrency = summarizer_concurrency
        self.polling_interval = polling_interval
        
        # Worker instances
        self.downloaders = [PodcastDownloader(instance_id=str(i+1)) for i in range(downloader_concurrency)]
        self.transcribers = [PodcastConverter(instance_id=str(i+1)) for i in range(transcriber_concurrency)]
        self.summarizers = [PodcastSummarizer(instance_id=str(i+1)) for i in range(summarizer_concurrency)]
        
        # Control flags
        self.running = False
        self.shutdown_event = threading.Event()
        
        # Statistics
        self.stats = {
            'cycles_completed': 0,
            'total_processed': 0,
            'downloads_completed': 0,
            'transcriptions_completed': 0,
            'summarizations_completed': 0,
            'errors': 0
        }
        
        # Don't override signal handlers - let parent handle them
        # signal.signal(signal.SIGINT, self._signal_handler)
        # signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown()
    
    def find_available_podcasts(self, state: PodcastStatus, limit: int = 10) -> List[Podcasts]:
        """
        Find podcasts available for processing in the given state.
        
        Args:
            state: Podcast state to search for
            limit: Maximum number of podcasts to return
            
        Returns:
            List of available podcast objects
        """
        db = SessionLocal()
        checkout_manager = CheckoutManager(db)
        
        try:
            return checkout_manager.find_available_podcasts(state, limit)
        finally:
            db.close()
    
    def dispatch_download_workers(self) -> Dict[str, int]:
        """
        Dispatch download workers to process available podcasts.
        
        Returns:
            Dictionary with processing statistics
        """
        available_podcasts = self.find_available_podcasts(PodcastStatus.new, self.downloader_concurrency * 2)
        
        if not available_podcasts:
            return {"downloaded": 0, "failed": 0, "total": 0}
        
        downloaded = 0
        failed = 0
        
        # Use ThreadPoolExecutor for concurrent downloads
        with ThreadPoolExecutor(max_workers=self.downloader_concurrency) as executor:
            # Submit download tasks
            future_to_podcast = {}
            for i, podcast in enumerate(available_podcasts[:self.downloader_concurrency]):
                downloader = self.downloaders[i % len(self.downloaders)]
                future = executor.submit(downloader.download_podcast, podcast.id)
                future_to_podcast[future] = podcast
            
            # Collect results
            for future in as_completed(future_to_podcast):
                podcast = future_to_podcast[future]
                try:
                    success = future.result()
                    if success:
                        downloaded += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(f"Download worker exception for podcast {podcast.id}: {e}")
                    failed += 1
        
        if downloaded > 0 or failed > 0:
            logger.info(f"Download dispatch complete: {downloaded} downloaded, {failed} failed")
        
        return {"downloaded": downloaded, "failed": failed, "total": downloaded + failed}
    
    def dispatch_transcribe_workers(self) -> Dict[str, int]:
        """
        Dispatch transcription workers to process available podcasts.
        
        Returns:
            Dictionary with processing statistics
        """
        available_podcasts = self.find_available_podcasts(PodcastStatus.downloaded, self.transcriber_concurrency * 2)
        
        if not available_podcasts:
            return {"transcribed": 0, "failed": 0, "total": 0}
        
        transcribed = 0
        failed = 0
        
        # Use ThreadPoolExecutor for concurrent transcriptions
        with ThreadPoolExecutor(max_workers=self.transcriber_concurrency) as executor:
            # Submit transcription tasks
            future_to_podcast = {}
            for i, podcast in enumerate(available_podcasts[:self.transcriber_concurrency]):
                transcriber = self.transcribers[i % len(self.transcribers)]
                future = executor.submit(transcriber.transcribe_podcast, podcast.id)
                future_to_podcast[future] = podcast
            
            # Collect results
            for future in as_completed(future_to_podcast):
                podcast = future_to_podcast[future]
                try:
                    success = future.result()
                    if success:
                        transcribed += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(f"Transcription worker exception for podcast {podcast.id}: {e}")
                    failed += 1
        
        if transcribed > 0 or failed > 0:
            logger.info(f"Transcription dispatch complete: {transcribed} transcribed, {failed} failed")
        
        return {"transcribed": transcribed, "failed": failed, "total": transcribed + failed}
    
    def dispatch_summarize_workers(self) -> Dict[str, int]:
        """
        Dispatch summarization workers to process available podcasts.
        
        Returns:
            Dictionary with processing statistics
        """
        available_podcasts = self.find_available_podcasts(PodcastStatus.transcribed, self.summarizer_concurrency * 2)
        
        if not available_podcasts:
            return {"summarized": 0, "failed": 0, "total": 0}
        
        summarized = 0
        failed = 0
        
        # Use ThreadPoolExecutor for concurrent summarizations
        with ThreadPoolExecutor(max_workers=self.summarizer_concurrency) as executor:
            # Submit summarization tasks
            future_to_podcast = {}
            for i, podcast in enumerate(available_podcasts[:self.summarizer_concurrency]):
                summarizer = self.summarizers[i % len(self.summarizers)]
                future = executor.submit(summarizer.summarize_podcast, podcast.id)
                future_to_podcast[future] = podcast
            
            # Collect results
            for future in as_completed(future_to_podcast):
                podcast = future_to_podcast[future]
                try:
                    success = future.result()
                    if success:
                        summarized += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(f"Summarization worker exception for podcast {podcast.id}: {e}")
                    failed += 1
        
        if summarized > 0 or failed > 0:
            logger.info(f"Summarization dispatch complete: {summarized} summarized, {failed} failed")
        
        return {"summarized": summarized, "failed": failed, "total": summarized + failed}
    
    def release_stale_checkouts(self) -> int:
        """
        Release stale checkouts across all workers.
        
        Returns:
            Number of stale checkouts released
        """
        db = SessionLocal()
        checkout_manager = CheckoutManager(db)
        
        try:
            return checkout_manager.release_stale_checkouts()
        finally:
            db.close()
    
    def run_single_cycle(self) -> Dict[str, Dict[str, int]]:
        """
        Run a single processing cycle.
        
        Returns:
            Dictionary with cycle statistics
        """
        cycle_stats = {
            'downloads': {"downloaded": 0, "failed": 0, "total": 0},
            'transcriptions': {"transcribed": 0, "failed": 0, "total": 0},
            'summarizations': {"summarized": 0, "failed": 0, "total": 0},
            'stale_checkouts_released': 0
        }
        
        try:
            # Release stale checkouts first
            cycle_stats['stale_checkouts_released'] = self.release_stale_checkouts()
            
            # Dispatch workers for each stage
            cycle_stats['downloads'] = self.dispatch_download_workers()
            cycle_stats['transcriptions'] = self.dispatch_transcribe_workers()
            cycle_stats['summarizations'] = self.dispatch_summarize_workers()
            
            # Update statistics
            self.stats['cycles_completed'] += 1
            self.stats['downloads_completed'] += cycle_stats['downloads']['downloaded']
            self.stats['transcriptions_completed'] += cycle_stats['transcriptions']['transcribed']
            self.stats['summarizations_completed'] += cycle_stats['summarizations']['summarized']
            self.stats['total_processed'] += (
                cycle_stats['downloads']['downloaded'] + 
                cycle_stats['transcriptions']['transcribed'] + 
                cycle_stats['summarizations']['summarized']
            )
            self.stats['errors'] += (
                cycle_stats['downloads']['failed'] + 
                cycle_stats['transcriptions']['failed'] + 
                cycle_stats['summarizations']['failed']
            )
            
        except Exception as e:
            logger.error(f"Error in processing cycle: {e}", exc_info=True)
            self.stats['errors'] += 1
        
        return cycle_stats
    
    def run(self) -> None:
        """
        Run the pipeline orchestrator continuously.
        """
        self.running = True
        logger.info("Pipeline orchestrator starting...")
        logger.info(f"Worker configuration: {self.downloader_concurrency} downloaders, "
                   f"{self.transcriber_concurrency} transcribers, {self.summarizer_concurrency} summarizers")
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
                total_work = (
                    cycle_stats['downloads']['total'] + 
                    cycle_stats['transcriptions']['total'] + 
                    cycle_stats['summarizations']['total']
                )
                
                if total_work > 0 or cycle_stats['stale_checkouts_released'] > 0:
                    logger.info(f"Cycle {self.stats['cycles_completed']} complete: "
                               f"downloads={cycle_stats['downloads']}, "
                               f"transcriptions={cycle_stats['transcriptions']}, "
                               f"summarizations={cycle_stats['summarizations']}, "
                               f"stale_released={cycle_stats['stale_checkouts_released']}")
                
                # Wait for next cycle
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
            logger.error(f"Unexpected error in pipeline orchestrator: {e}", exc_info=True)
        finally:
            self.running = False
            logger.info("Pipeline orchestrator stopped")
            self.log_final_stats()
    
    def shutdown(self) -> None:
        """
        Initiate graceful shutdown of the orchestrator.
        """
        logger.info("Shutting down pipeline orchestrator...")
        self.running = False
        self.shutdown_event.set()
    
    def get_status(self) -> Dict:
        """
        Get current pipeline status.
        
        Returns:
            Dictionary with pipeline status information
        """
        db = SessionLocal()
        checkout_manager = CheckoutManager(db)
        
        try:
            checkout_status = checkout_manager.get_checkout_status()
            
            return {
                'running': self.running,
                'worker_config': {
                    'downloaders': self.downloader_concurrency,
                    'transcribers': self.transcriber_concurrency,
                    'summarizers': self.summarizer_concurrency
                },
                'polling_interval': self.polling_interval,
                'statistics': self.stats.copy(),
                'checkout_status': checkout_status
            }
        finally:
            db.close()
    
    def log_final_stats(self) -> None:
        """Log final statistics on shutdown."""
        logger.info("=== Pipeline Orchestrator Final Statistics ===")
        logger.info(f"Cycles completed: {self.stats['cycles_completed']}")
        logger.info(f"Total podcasts processed: {self.stats['total_processed']}")
        logger.info(f"Downloads completed: {self.stats['downloads_completed']}")
        logger.info(f"Transcriptions completed: {self.stats['transcriptions_completed']}")
        logger.info(f"Summarizations completed: {self.stats['summarizations_completed']}")
        logger.info(f"Total errors: {self.stats['errors']}")
        logger.info("===============================================")