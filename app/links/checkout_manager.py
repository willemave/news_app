"""
Checkout/checkin mechanism for link pipeline worker concurrency control.
Provides atomic operations to ensure exclusive access to link records.
"""

from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from sqlalchemy.exc import SQLAlchemyError

from app.models import Links, LinkStatus
from app.constants import DEFAULT_CHECKOUT_TIMEOUT_MINUTES
import logging

logger = logging.getLogger(__name__)


class LinkCheckoutManager:
    """Manages checkout/checkin operations for link processing."""
    
    def __init__(self, db: Session, timeout_minutes: int = DEFAULT_CHECKOUT_TIMEOUT_MINUTES):
        self.db = db
        self.timeout_minutes = timeout_minutes
    
    def checkout_link(self, link_id: int, worker_id: str, expected_state: LinkStatus) -> Optional[Links]:
        """
        Atomically checkout a link for exclusive processing.
        
        Args:
            link_id: ID of the link to checkout
            worker_id: Unique identifier of the worker requesting checkout
            expected_state: Expected current state of the link
            
        Returns:
            Link object if checkout successful, None otherwise
        """
        try:
            # Calculate timeout threshold
            timeout_threshold = datetime.utcnow() - timedelta(minutes=self.timeout_minutes)
            
            # Atomic checkout with row-level locking
            link = self.db.query(Links).filter(
                and_(
                    Links.id == link_id,
                    Links.status == expected_state,
                    or_(
                        Links.checked_out_by.is_(None),
                        Links.checked_out_at < timeout_threshold
                    )
                )
            ).with_for_update().first()
            
            if link:
                link.checked_out_by = worker_id
                link.checked_out_at = datetime.utcnow()
                self.db.commit()
                
                logger.info(f"Link {link_id} checked out by {worker_id}")
                return link
            else:
                logger.debug(f"Link {link_id} checkout failed - not available or wrong state")
                return None
                
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during checkout of link {link_id}: {e}")
            return None
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during checkout of link {link_id}: {e}")
            return None
    
    def checkin_link(self, link_id: int, worker_id: str, new_state: Optional[LinkStatus] = None, 
                    error_message: Optional[str] = None) -> bool:
        """
        Check in a link after processing, updating its state.
        
        Args:
            link_id: ID of the link to checkin
            worker_id: Worker ID that currently has the link checked out
            new_state: New state to set (if None, keeps current state)
            error_message: Error message if processing failed
            
        Returns:
            True if checkin successful, False otherwise
        """
        try:
            # Find the link that should be checked out by this worker
            link = self.db.query(Links).filter(
                and_(
                    Links.id == link_id,
                    Links.checked_out_by == worker_id
                )
            ).with_for_update().first()
            
            if not link:
                logger.error(f"Checkin failed - link {link_id} not checked out by {worker_id}")
                return False
            
            # Update state if provided
            if new_state:
                link.status = new_state
            
            # Update processed_date for final states
            if new_state in [LinkStatus.processed, LinkStatus.failed, LinkStatus.skipped]:
                link.processed_date = datetime.utcnow()
            
            # Update error message if provided
            if error_message:
                link.error_message = error_message
            
            # Clear checkout fields
            link.checked_out_by = None
            link.checked_out_at = None
            
            self.db.commit()
            
            logger.info(f"Link {link_id} checked in by {worker_id}, new state: {new_state}")
            return True
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during checkin of link {link_id}: {e}")
            return False
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during checkin of link {link_id}: {e}")
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
            stale_links = self.db.query(Links).filter(
                and_(
                    Links.checked_out_by.isnot(None),
                    Links.checked_out_at < timeout_threshold
                )
            ).with_for_update().all()
            
            count = 0
            for link in stale_links:
                logger.warning(f"Releasing stale checkout for link {link.id}, "
                             f"was checked out by {link.checked_out_by} at {link.checked_out_at}")
                
                link.checked_out_by = None
                link.checked_out_at = None
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
    
    def is_checked_out(self, link_id: int) -> bool:
        """
        Check if a link is currently checked out.
        
        Args:
            link_id: ID of the link to check
            
        Returns:
            True if link is checked out, False otherwise
        """
        try:
            timeout_threshold = datetime.utcnow() - timedelta(minutes=self.timeout_minutes)
            
            link = self.db.query(Links).filter(
                and_(
                    Links.id == link_id,
                    Links.checked_out_by.isnot(None),
                    Links.checked_out_at >= timeout_threshold
                )
            ).first()
            
            return link is not None
            
        except Exception as e:
            logger.error(f"Error checking checkout status for link {link_id}: {e}")
            return False
    
    def find_available_links(self, state: LinkStatus, limit: int = 10) -> List[Links]:
        """
        Find links available for processing in the given state.
        
        Args:
            state: Link state to search for
            limit: Maximum number of links to return
            
        Returns:
            List of available link objects
        """
        try:
            timeout_threshold = datetime.utcnow() - timedelta(minutes=self.timeout_minutes)
            
            links = self.db.query(Links).filter(
                and_(
                    Links.status == state,
                    or_(
                        Links.checked_out_by.is_(None),
                        Links.checked_out_at < timeout_threshold
                    )
                )
            ).limit(limit).all()
            
            return links
            
        except Exception as e:
            logger.error(f"Error finding available links in state {state}: {e}")
            return []
    
    def get_checkout_status(self) -> dict:
        """
        Get current checkout status for monitoring.
        
        Returns:
            Dictionary with checkout statistics
        """
        try:
            timeout_threshold = datetime.utcnow() - timedelta(minutes=self.timeout_minutes)
            
            # Count links by status
            status_counts = {}
            for status in LinkStatus:
                count = self.db.query(Links).filter(Links.status == status).count()
                status_counts[status.value] = count
            
            # Count active checkouts
            active_checkouts = self.db.query(Links).filter(
                and_(
                    Links.checked_out_by.isnot(None),
                    Links.checked_out_at >= timeout_threshold
                )
            ).count()
            
            # Count stale checkouts
            stale_checkouts = self.db.query(Links).filter(
                and_(
                    Links.checked_out_by.isnot(None),
                    Links.checked_out_at < timeout_threshold
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