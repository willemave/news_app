from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.pipeline.worker import WorkerPool
from app.pipeline.checkout import get_checkout_manager
from app.services.queue import get_queue_service
from app.domain.content import ContentType

router = APIRouter(prefix="/admin", tags=["admin"])

@router.post("/workers/start")
async def start_workers(
    background_tasks: BackgroundTasks,
    content_type: Optional[ContentType] = None,
    max_items: Optional[int] = None,
    max_workers: int = 5
):
    """Start worker pool in background."""
    pool = WorkerPool(max_workers=max_workers)
    
    background_tasks.add_task(
        pool.run_workers,
        content_type=content_type,
        max_items=max_items
    )
    
    return {
        "message": "Worker pool started",
        "max_workers": max_workers,
        "content_type": content_type.value if content_type else "all",
        "max_items": max_items
    }

@router.post("/maintenance/run")
async def run_maintenance(background_tasks: BackgroundTasks):
    """Run maintenance tasks."""
    pool = WorkerPool()
    background_tasks.add_task(pool.run_maintenance)
    
    return {"message": "Maintenance tasks started"}

@router.get("/stats/checkout")
async def get_checkout_stats():
    """Get checkout statistics."""
    checkout_manager = get_checkout_manager()
    return checkout_manager.get_checkout_stats()

@router.get("/stats/queue")
async def get_queue_stats():
    """Get queue statistics."""
    queue_service = get_queue_service()
    return queue_service.get_queue_stats()

@router.post("/checkouts/release")
async def release_stale_checkouts():
    """Manually release stale checkouts."""
    checkout_manager = get_checkout_manager()
    released = checkout_manager.release_stale_checkouts()
    
    return {"message": f"Released {released} stale checkouts"}