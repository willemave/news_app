"""
Link processor worker that handles individual link processing using the checkout mechanism.
"""

from typing import Optional
from app.database import SessionLocal
from app.models import Links, LinkStatus
from app.config import logger, settings
from app.links.checkout_manager import LinkCheckoutManager
from app.processor import process_link_from_db
from app.http_client.robust_http_client import RobustHttpClient
from app.processing_strategies.factory import UrlProcessorFactory


class LinkProcessorWorker:
    """Worker that processes individual links using the checkout mechanism."""
    
    def __init__(self, instance_id: str = "1"):
        """
        Initialize the link processor worker.
        
        Args:
            instance_id: Unique identifier for this worker instance
        """
        self.instance_id = instance_id
        self.worker_id = f"link_processor_{instance_id}"
        
        # Initialize HTTP client and factory for processing
        self.http_client = RobustHttpClient(
            timeout=settings.HTTP_CLIENT_TIMEOUT,
            headers={'User-Agent': settings.HTTP_CLIENT_USER_AGENT}
        )
        self.factory = UrlProcessorFactory(self.http_client)
    
    def process_link(self, link_id: int) -> bool:
        """
        Process a single link by ID using the checkout mechanism.
        
        Args:
            link_id: ID of the link to process
            
        Returns:
            True if processing was successful, False otherwise
        """
        db = SessionLocal()
        checkout_manager = LinkCheckoutManager(db)
        
        try:
            # Attempt to checkout the link
            link = checkout_manager.checkout_link(link_id, self.worker_id, LinkStatus.new)
            
            if not link:
                logger.debug(f"Worker {self.worker_id} could not checkout link {link_id}")
                return False
            
            logger.debug(f"Worker {self.worker_id} processing link {link_id}: {link.url}")
            
            # Update status to processing
            if not checkout_manager.checkin_link(link_id, self.worker_id, LinkStatus.processing):
                logger.error(f"Worker {self.worker_id} failed to update link {link_id} to processing state")
                return False
            
            # Re-checkout the link in processing state
            link = checkout_manager.checkout_link(link_id, self.worker_id, LinkStatus.processing)
            if not link:
                logger.error(f"Worker {self.worker_id} could not re-checkout link {link_id} in processing state")
                return False
            
            # Process the link using the existing processor
            try:
                success = process_link_from_db(link, self.http_client, self.factory)
                
                if success:
                    # The process_link_from_db function already updates the link status
                    # We just need to check in with no status change
                    checkout_manager.checkin_link(link_id, self.worker_id)
                    logger.debug(f"Worker {self.worker_id} successfully processed link {link_id}")
                    return True
                else:
                    checkout_manager.checkin_link(link_id, self.worker_id, LinkStatus.failed,
                                                "Processing failed")
                    logger.warning(f"Worker {self.worker_id} failed to process link {link_id}")
                    return False
                    
            except Exception as e:
                error_msg = f"Worker {self.worker_id} encountered error processing link {link_id}: {e}"
                logger.error(error_msg, exc_info=True)
                checkout_manager.checkin_link(link_id, self.worker_id, LinkStatus.failed, error_msg)
                return False
                
        except Exception as e:
            logger.error(f"Worker {self.worker_id} encountered unexpected error with link {link_id}: {e}", 
                        exc_info=True)
            return False
        finally:
            db.close()
    
    def cleanup(self):
        """Clean up resources used by the worker."""
        if self.http_client:
            self.http_client.close()