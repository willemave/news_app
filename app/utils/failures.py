"""
Failure logging utilities for recording errors during scraping and processing.
"""
from typing import Optional
from ..database import SessionLocal
from ..models import FailureLogs, FailurePhase
from ..config import logger


def record_failure(phase: FailurePhase, msg: str, link_id: Optional[int] = None) -> None:
    """
    Record a failure in the failure_logs table.
    
    Args:
        phase: The phase where the failure occurred (scraper or processor)
        msg: Error message describing the failure
        link_id: Optional link ID if the failure is associated with a specific link
    """
    db = SessionLocal()
    try:
        failure_log = FailureLogs(
            link_id=link_id,
            phase=phase,
            error_msg=msg
        )
        db.add(failure_log)
        db.commit()
        
        logger.info(f"Recorded {phase.value} failure: {msg[:100]}{'...' if len(msg) > 100 else ''}")
        
    except Exception as e:
        logger.error(f"Failed to record failure log: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()