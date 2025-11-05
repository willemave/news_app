"""
ARCHIVED FROM app/api/content.py
This file contains reference code for content API endpoints that can be reused in the new router structure.
"""

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.domain.content import ContentData, ContentStatus, ContentType
from app.domain.converters import content_to_domain
from app.models.schema import Content
from app.pipeline.worker import get_worker

router = APIRouter(prefix="/content", tags=["content"])


@router.get("/", response_model=list[ContentData])
async def list_content(
    content_type: ContentType | None = None,
    status: ContentStatus | None = None,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db_session),
):
    """List content with optional filters."""
    query = db.query(Content)

    if content_type:
        query = query.filter(Content.content_type == content_type.value)

    if status:
        query = query.filter(Content.status == status.value)

    # Order by most recent first
    query = query.order_by(Content.created_at.desc())

    # Apply pagination
    content_list = query.offset(offset).limit(limit).all()

    return [content_to_domain(c) for c in content_list]


@router.get("/{content_id}", response_model=ContentData)
async def get_content(content_id: int, db: Session = Depends(get_db_session)):
    """Get a specific content item."""
    content = db.query(Content).filter(Content.id == content_id).first()

    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    return content_to_domain(content)


@router.post("/add")
async def add_content(url: str, content_type: ContentType, db: Session = Depends(get_db_session)):
    """Add new content to process."""
    # Check if already exists
    existing = db.query(Content).filter(Content.url == url).first()
    if existing:
        return {"message": "Content already exists", "id": existing.id}

    # Create new content
    content = Content(
        content_type=content_type.value,
        url=url,
        status=ContentStatus.NEW.value,
        content_metadata={},
    )

    db.add(content)
    db.commit()
    db.refresh(content)

    return {"message": "Content added", "id": content.id}


@router.post("/process")
async def process_content(background_tasks: BackgroundTasks, limit: int = Query(default=10, le=50)):
    """Process pending content items."""
    worker = get_worker()

    # Run processing in background
    background_tasks.add_task(worker.process_batch, limit)

    return {"message": f"Started processing up to {limit} items"}


@router.get("/stats/overview")
async def get_stats(db: Session = Depends(get_db_session)):
    """Get content statistics."""
    stats = {}

    # Count by type
    for content_type in ContentType:
        count = db.query(Content).filter(Content.content_type == content_type.value).count()
        stats[f"total_{content_type.value}s"] = count

    # Count by status
    for status in ContentStatus:
        count = db.query(Content).filter(Content.status == status.value).count()
        stats[f"status_{status.value}"] = count

    # Recent activity
    today = datetime.utcnow().date()
    stats["processed_today"] = db.query(Content).filter(Content.processed_at >= today).count()

    return stats
