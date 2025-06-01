"""
Failure logging utilities for recording errors during scraping and processing.
"""
from typing import Optional
from ..database import SessionLocal
from ..models import FailureLogs, FailurePhase
from ..config import logger


def record_failure(phase: FailurePhase, msg: str, link_id: Optional[int] = None, skip_reason: Optional[str] = None) -> None:
    """
    Record a failure in the failure_logs table.
    
    Args:
        phase: The phase where the failure occurred (scraper or processor)
        msg: Error message describing the failure
        link_id: Optional link ID if the failure is associated with a specific link
        skip_reason: Optional reason for skipping when applicable
    """
    db = SessionLocal()
    try:
        failure_log = FailureLogs(
            link_id=link_id,
            phase=phase,
            error_msg=msg,
            skip_reason=skip_reason
        )
        db.add(failure_log)
        db.commit()
        
        log_msg = f"Recorded {phase.value} failure: {msg[:100]}{'...' if len(msg) > 100 else ''}"
        if skip_reason:
            log_msg += f" (skip reason: {skip_reason[:50]}{'...' if len(skip_reason) > 50 else ''})"
        logger.info(log_msg)
        
    except Exception as e:
        logger.error(f"Failed to record failure log: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()