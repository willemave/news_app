from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.db import get_db_session
from app.models.schema import Content
from app.models.metadata import ContentType
from app.domain.converters import content_to_domain
from app.templates import templates

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def list_content(
    request: Request,
    content_type: Optional[str] = None,
    date: Optional[str] = None,
    db: Session = Depends(get_db_session)
):
    """List content with optional filters."""
    # Get available dates for the dropdown
    available_dates_query = db.query(
        func.date(Content.created_at).label('date')
    ).distinct().order_by(func.date(Content.created_at).desc())
    
    available_dates = []
    for row in available_dates_query.all():
        if row.date:
            if isinstance(row.date, str):
                available_dates.append(row.date)
            else:
                available_dates.append(row.date.strftime('%Y-%m-%d'))
    
    # Query content
    query = db.query(Content)
    
    # Apply content type filter
    if content_type and content_type != "all":
        query = query.filter(Content.content_type == content_type)
    
    # Apply date filter
    if date:
        try:
            filter_date = datetime.strptime(date, '%Y-%m-%d').date()
            query = query.filter(func.date(Content.created_at) == filter_date)
        except ValueError:
            pass
    
    # Order by most recent first
    contents = query.order_by(Content.created_at.desc()).all()
    
    # Convert to domain objects, skipping invalid ones
    domain_contents = []
    for c in contents:
        try:
            domain_contents.append(content_to_domain(c))
        except Exception as e:
            # Skip content with invalid metadata
            print(f"Skipping content {c.id} due to validation error: {e}")
            continue
    
    # Get content types for filter
    content_types = [ct.value for ct in ContentType]
    
    return templates.TemplateResponse("content_list.html", {
        "request": request,
        "contents": domain_contents,
        "content_types": content_types,
        "selected_type": content_type,
        "selected_date": date,
        "available_dates": available_dates
    })

@router.get("/content/{content_id}", response_class=HTMLResponse)
async def content_detail(
    request: Request,
    content_id: int,
    db: Session = Depends(get_db_session)
):
    """Get detailed view of a specific content item."""
    content = db.query(Content).filter(Content.id == content_id).first()
    
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    
    # Convert to domain object
    domain_content = content_to_domain(content)
    
    return templates.TemplateResponse("content_detail.html", {
        "request": request,
        "content": domain_content
    })