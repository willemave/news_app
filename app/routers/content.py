from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.domain.converters import content_to_domain
from app.models.metadata import ContentType
from app.models.schema import Content
from app.templates import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def list_content(
    request: Request,
    content_type: str | None = None,
    date: str | None = None,
    db: Session = Depends(get_db_session),
):
    """List content with optional filters."""
    # Get available dates for the dropdown
    available_dates_query = (
        db.query(func.date(Content.created_at).label("date"))
        .filter(Content.content_metadata["summary"] != None)
        .filter((Content.classification != "skip") | (Content.classification == None))
        .distinct()
        .order_by(func.date(Content.created_at).desc())
    )

    available_dates = []
    for row in available_dates_query.all():
        if row.date:
            if isinstance(row.date, str):
                available_dates.append(row.date)
            else:
                available_dates.append(row.date.strftime("%Y-%m-%d"))

    # Query content
    query = db.query(Content)

    # Filter out "skip" classification articles
    query = query.filter((Content.classification != "skip") | (Content.classification == None))
    
    # Only show content that has been summarized
    query = query.filter(Content.content_metadata["summary"] != None)

    # Apply content type filter
    if content_type and content_type != "all":
        query = query.filter(Content.content_type == content_type)

    # Apply date filter
    if date:
        try:
            filter_date = datetime.strptime(date, "%Y-%m-%d").date()
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

    return templates.TemplateResponse(
        "content_list.html",
        {
            "request": request,
            "contents": domain_contents,
            "content_types": content_types,
            "selected_type": content_type,
            "selected_date": date,
            "available_dates": available_dates,
        },
    )


@router.get("/content/{content_id}", response_class=HTMLResponse)
async def content_detail(request: Request, content_id: int, db: Session = Depends(get_db_session)):
    """Get detailed view of a specific content item."""
    content = db.query(Content).filter(Content.id == content_id).first()

    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Convert to domain object
    domain_content = content_to_domain(content)

    return templates.TemplateResponse(
        "content_detail.html", {"request": request, "content": domain_content}
    )


@router.get("/content/{content_id}/json", response_class=JSONResponse)
async def content_json(content_id: int, db: Session = Depends(get_db_session)):
    """Get content item with metadata as JSON."""
    content = db.query(Content).filter(Content.id == content_id).first()

    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Return the entire content model and metadata
    return {
        "id": content.id,
        "content_type": content.content_type,
        "url": content.url,
        "title": content.title,
        "source": content.source,
        "status": content.status,
        "error_message": content.error_message,
        "retry_count": content.retry_count,
        "checked_out_by": content.checked_out_by,
        "checked_out_at": content.checked_out_at.isoformat() if content.checked_out_at else None,
        "content_metadata": content.content_metadata,
        "created_at": content.created_at.isoformat() if content.created_at else None,
        "updated_at": content.updated_at.isoformat() if content.updated_at else None,
        "processed_at": content.processed_at.isoformat() if content.processed_at else None,
    }
