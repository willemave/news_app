"""
Checkout/checkin mechanism for podcast pipeline worker concurrency control.
Provides atomic operations to ensure exclusive access to podcast records.
"""

from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from sqlalchemy.exc import SQLAlchemyError

from app.models import Podcasts, PodcastStatus
from app.constants import DEFAULT_CHECKOUT_TIMEOUT_MINUTES
import logging

logger = logging.getLogger(__name__)


class CheckoutManager:
    """Manages checkout/checkin operations for podcast processing."""
    
    def __init__(self, db: Session, timeout_minutes: int = DEFAULT_CHECKOUT_TIMEOUT_MINUTES):
        self.db = db
        self.timeout_minutes = timeout_minutes
    
    def checkout_podcast(self, podcast_id: int, worker_id: str, expected_state: PodcastStatus) -> Optional[Podcasts]:
        """
        Atomically checkout a podcast for exclusive processing.
        
        Args:
            podcast_id: ID of the podcast to checkout
            worker_id: Unique identifier of the worker requesting checkout
            expected_state: Expected current state of the podcast
            
        Returns:
            Podcast object if checkout successful, None otherwise
        """
        try:
            # Calculate timeout threshold
            timeout_threshold = datetime.utcnow() - timedelta(minutes=self.timeout_minutes)
            
            # Atomic checkout with row-level locking
            podcast = self.db.query(Podcasts).filter(
                and_(
                    Podcasts.id == podcast_id,
                    Podcasts.status == expected_state,
                    or_(
                        Podcasts.checked_out_by.is_(None),
                        Podcasts.checked_out_at < timeout_threshold
                    )
                )
            ).with_for_update().first()
            
            if podcast:
                podcast.checked_out_by = worker_id
                podcast.checked_out_at = datetime.utcnow()
                self.db.commit()
                
                logger.info(f"Podcast {podcast_id} checked out by {worker_id}")
                return podcast
            else:
                logger.debug(f"Podcast {podcast_id} checkout failed - not available or wrong state")
                return None
                
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during checkout of podcast {podcast_id}: {e}")
            return None
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during checkout of podcast {podcast_id}: {e}")
            return None
    
    def checkin_podcast(self, podcast_id: int, worker_id: str, new_state: Optional[PodcastStatus] = None, 
                       error_message: Optional[str] = None) -> bool:
        """
        Check in a podcast after processing, updating its state.
        
        Args:
            podcast_id: ID of the podcast to checkin
            worker_id: Worker ID that currently has the podcast checked out
            new_state: New state to set (if None, keeps current state)
            error_message: Error message if processing failed
            
        Returns:
            True if checkin successful, False otherwise
        """
        try:
            # Find the podcast that should be checked out by this worker
            podcast = self.db.query(Podcasts).filter(
                and_(
                    Podcasts.id == podcast_id,
                    Podcasts.checked_out_by == worker_id
                )
            ).with_for_update().first()
            
            if not podcast:
                logger.error(f"Checkin failed - podcast {podcast_id} not checked out by {worker_id}")
                return False
            
            # Update state if provided
            if new_state:
                podcast.status = new_state
            
            # Update error message if provided
            if error_message:
                podcast.error_message = error_message
            
            # Clear checkout fields
            podcast.checked_out_by = None
            podcast.checked_out_at = None
            
            self.db.commit()
            
            logger.info(f"Podcast {podcast_id} checked in by {worker_id}, new state: {new_state}")
            return True
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during checkin of podcast {podcast_id}: {e}")
            return False
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during checkin of podcast {podcast_id}: {e}")
            return False
    
    def release_stale_checkouts(self) -> int:
        """
        Release checkouts that have exceeded the timeout threshold.
        
        Returns:
            Number of stale checkouts released
        """
        try:
            timeout_threshold = datetime.utcnow() - timedelta(minutes=self.timeout_minutes)
            
            # Find stale checkouts
            stale_podcasts = self.db.query(Podcasts).filter(
                and_(
                    Podcasts.checked_out_by.isnot(None),
                    Podcasts.checked_out_at < timeout_threshold
                )
            ).with_for_update().all()
            
            count = 0
            for podcast in stale_podcasts:
                logger.warning(f"Releasing stale checkout for podcast {podcast.id}, "
                             f"was checked out by {podcast.checked_out_by} at {podcast.checked_out_at}")
                
                podcast.checked_out_by = None
                podcast.checked_out_at = None
                count += 1
            
            if count > 0:
                self.db.commit()
                logger.info(f"Released {count} stale checkouts")
            
            return count
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during stale checkout release: {e}")
            return 0
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during stale checkout release: {e}")
            return 0
    
    def is_checked_out(self, podcast_id: int) -> bool:
        """
        Check if a podcast is currently checked out.
        
        Args:
            podcast_id: ID of the podcast to check
            
        Returns:
            True if podcast is checked out, False otherwise
        """
        try:
            timeout_threshold = datetime.utcnow() - timedelta(minutes=self.timeout_minutes)
            
            podcast = self.db.query(Podcasts).filter(
                and_(
                    Podcasts.id == podcast_id,
                    Podcasts.checked_out_by.isnot(None),
                    Podcasts.checked_out_at >= timeout_threshold
                )
            ).first()
            
            return podcast is not None
            
        except Exception as e:
            logger.error(f"Error checking checkout status for podcast {podcast_id}: {e}")
            return False
    
    def find_available_podcasts(self, state: PodcastStatus, limit: int = 10) -> List[Podcasts]:
        """
        Find podcasts available for processing in the given state.
        
        Args:
            state: Podcast state to search for
            limit: Maximum number of podcasts to return
            
        Returns:
            List of available podcast objects
        """
        try:
            timeout_threshold = datetime.utcnow() - timedelta(minutes=self.timeout_minutes)
            
            podcasts = self.db.query(Podcasts).filter(
                and_(
                    Podcasts.status == state,
                    or_(
                        Podcasts.checked_out_by.is_(None),
                        Podcasts.checked_out_at < timeout_threshold
                    )
                )
            ).limit(limit).all()
            
            return podcasts
            
        except Exception as e:
            logger.error(f"Error finding available podcasts in state {state}: {e}")
            return []
    
    def get_checkout_status(self) -> dict:
        """
        Get current checkout status for monitoring.
        
        Returns:
            Dictionary with checkout statistics
        """
        try:
            timeout_threshold = datetime.utcnow() - timedelta(minutes=self.timeout_minutes)
            
            # Count podcasts by status
            status_counts = {}
            for status in PodcastStatus:
                count = self.db.query(Podcasts).filter(Podcasts.status == status).count()
                status_counts[status.value] = count
            
            # Count active checkouts
            active_checkouts = self.db.query(Podcasts).filter(
                and_(
                    Podcasts.checked_out_by.isnot(None),
                    Podcasts.checked_out_at >= timeout_threshold
                )
            ).count()
            
            # Count stale checkouts
            stale_checkouts = self.db.query(Podcasts).filter(
                and_(
                    Podcasts.checked_out_by.isnot(None),
                    Podcasts.checked_out_at < timeout_threshold
                )
            ).count()
            
            return {
                'status_counts': status_counts,
                'active_checkouts': active_checkouts,
                'stale_checkouts': stale_checkouts,
                'timeout_minutes': self.timeout_minutes
            }
            
        except Exception as e:
            logger.error(f"Error getting checkout status: {e}")
            return {}