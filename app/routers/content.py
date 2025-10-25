import secrets
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.core.deps import require_admin
from app.domain.converters import content_to_domain
from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content
from app.services import favorites, read_status
from app.templates import templates

router = APIRouter()

SESSION_COOKIE_NAME = "news_app_session"
SESSION_COOKIE_MAX_AGE = 365 * 24 * 60 * 60  # 1 year


def get_or_create_session_id(
    request: Request,
    response: Response,
    session_id: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> str:
    """Get existing session ID or create a new one."""
    print(f"[SESSION] Request path: {request.url.path}")
    print(f"[SESSION] Request cookies: {request.cookies}")
    print(f"[SESSION] Incoming session_id from cookie: {session_id}")
    if not session_id:
        session_id = secrets.token_urlsafe(32)
        print(f"[SESSION] Creating new session_id: {session_id}")
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session_id,
            max_age=SESSION_COOKIE_MAX_AGE,
            httponly=True,
            samesite="lax",
            secure=False,  # Set to True in production with HTTPS
            path="/",
        )
        print(f"[SESSION] Cookie set with key={SESSION_COOKIE_NAME}, value={session_id}")
    else:
        print(f"[SESSION] Using existing session_id: {session_id}")
    return session_id


SessionDep = Annotated[str, Depends(get_or_create_session_id)]


@router.get("/", response_class=HTMLResponse)
async def list_content(
    request: Request,
    db: Annotated[Session, Depends(get_db_session)],
    _: None = Depends(require_admin),
    content_type: str | None = None,
    date: str | None = None,
    read_filter: str = "unread",
):
    """List content with optional filters."""
    # Get available dates for the dropdown
    summarized_clause = (
        Content.content_metadata["summary"].is_not(None)
        & (Content.content_metadata["summary"] != "null")
    )
    completed_news_clause = and_(
        Content.content_type == ContentType.NEWS.value,
        Content.status == ContentStatus.COMPLETED.value,
    )

    available_dates_query = (
        db.query(func.date(Content.created_at).label("date"))
        .filter(or_(summarized_clause, completed_news_clause))
        .filter((Content.classification != "skip") | (Content.classification.is_(None)))
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
    query = query.filter((Content.classification != "skip") | (Content.classification.is_(None)))

    # Only show content that has been summarized
    query = query.filter(or_(summarized_clause, completed_news_clause))

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
    
    # Get read content IDs
    print("DEBUG: Getting read content")
    read_content_ids = read_status.get_read_content_ids(db)
    print(f"DEBUG: Found {len(read_content_ids)} read items: {read_content_ids}")
    
    # Get favorite content IDs
    favorite_content_ids = favorites.get_favorite_content_ids(db)
    
    # Filter based on read status if needed
    if read_filter == "unread":
        contents = [c for c in contents if c.id not in read_content_ids]
    elif read_filter == "read":
        contents = [c for c in contents if c.id in read_content_ids]
    # If read_filter is "all", don't filter

    # Convert to domain objects, skipping invalid ones
    domain_contents = []
    for c in contents:
        try:
            domain_content = content_to_domain(c)
            domain_contents.append(domain_content)
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
            "selected_read_filter": read_filter,
            "read_content_ids": read_content_ids,
            "favorite_content_ids": favorite_content_ids,
        },
    )


@router.get("/content/{content_id}", response_class=HTMLResponse)
async def content_detail(
    request: Request,
    content_id: int,
    db: Annotated[Session, Depends(get_db_session)],
    _: None = Depends(require_admin),
):
    """Get detailed view of a specific content item."""
    content = db.query(Content).filter(Content.id == content_id).first()

    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Mark content as read (no session needed)
    print(f"DEBUG: Marking content {content_id} as read")
    result = read_status.mark_content_as_read(db, content_id)
    print(f"DEBUG: Mark as read result: {result}")
    if result:
        print(f"DEBUG: Successfully marked content {content_id} as read at {result.read_at}")

    # Convert to domain object
    domain_content = content_to_domain(content)
    
    # Check if content is favorited
    is_favorited = favorites.is_content_favorited(db, content_id)

    return templates.TemplateResponse(
        "content_detail.html", 
        {
            "request": request, 
            "content": domain_content,
            "is_favorited": is_favorited,
        }
    )


@router.get("/favorites", response_class=HTMLResponse)
async def favorites_list(
    request: Request,
    db: Annotated[Session, Depends(get_db_session)],
    _: None = Depends(require_admin),
    read_filter: str = "all",
):
    """List favorited content."""
    # Get favorited content IDs
    favorite_content_ids = favorites.get_favorite_content_ids(db)
    
    # Query favorited content
    if favorite_content_ids:
        query = db.query(Content).filter(Content.id.in_(favorite_content_ids))

        # Filter out "skip" classification articles
        query = query.filter((Content.classification != "skip") | (Content.classification.is_(None)))

        # Order by most recent first
        contents = query.order_by(Content.created_at.desc()).all()
    else:
        contents = []
    
    # Get read content IDs
    read_content_ids = read_status.get_read_content_ids(db)
    
    # Filter based on read status if needed
    if read_filter == "unread":
        contents = [c for c in contents if c.id not in read_content_ids]
    elif read_filter == "read":
        contents = [c for c in contents if c.id in read_content_ids]
    
    # Convert to domain objects
    domain_contents = []
    for c in contents:
        try:
            domain_content = content_to_domain(c)
            domain_contents.append(domain_content)
        except Exception as e:
            print(f"Skipping content {c.id} due to validation error: {e}")
            continue
    
    # Get content types for filter
    content_types = [ct.value for ct in ContentType]
    
    return templates.TemplateResponse(
        "favorites.html",
        {
            "request": request,
            "contents": domain_contents,
            "content_types": content_types,
            "selected_read_filter": read_filter,
            "read_content_ids": read_content_ids,
            "favorite_content_ids": favorite_content_ids,
        },
    )


@router.get("/content/{content_id}/json", response_class=JSONResponse)
async def content_json(
    content_id: int,
    db: Annotated[Session, Depends(get_db_session)],
    _: None = Depends(require_admin),
):
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
