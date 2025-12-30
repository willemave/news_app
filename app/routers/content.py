import secrets
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.core.deps import require_admin
from app.core.logging import get_logger
from app.domain.converters import content_to_domain
from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content
from app.models.user import User
from app.services import favorites, read_status
from app.templates import templates

logger = get_logger(__name__)

router = APIRouter()

SESSION_COOKIE_NAME = "news_app_session"
SESSION_COOKIE_MAX_AGE = 365 * 24 * 60 * 60  # 1 year


def get_or_create_session_id(
    request: Request,
    response: Response,
    session_id: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> str:
    """Get existing session ID or create a new one."""
    logger.debug(
        "[SESSION] Request path: %s",
        request.url.path,
        extra={
            "component": "session",
            "operation": "get_or_create_session_id",
            "context_data": {"path": request.url.path},
        },
    )
    logger.debug(
        "[SESSION] Request cookies: %s",
        request.cookies,
        extra={
            "component": "session",
            "operation": "get_or_create_session_id",
            "context_data": {"cookies": request.cookies},
        },
    )
    logger.debug(
        "[SESSION] Incoming session_id from cookie: %s",
        session_id,
        extra={
            "component": "session",
            "operation": "get_or_create_session_id",
            "context_data": {"session_id": session_id},
        },
    )
    if not session_id:
        session_id = secrets.token_urlsafe(32)
        logger.info(
            "[SESSION] Creating new session_id",
            extra={
                "component": "session",
                "operation": "get_or_create_session_id",
                "context_data": {"session_id": session_id},
            },
        )
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session_id,
            max_age=SESSION_COOKIE_MAX_AGE,
            httponly=True,
            samesite="lax",
            secure=False,  # Set to True in production with HTTPS
            path="/",
        )
        logger.debug(
            "[SESSION] Cookie set with key=%s",
            SESSION_COOKIE_NAME,
            extra={
                "component": "session",
                "operation": "get_or_create_session_id",
                "context_data": {"session_id": session_id},
            },
        )
    else:
        logger.debug(
            "[SESSION] Using existing session_id: %s",
            session_id,
            extra={
                "component": "session",
                "operation": "get_or_create_session_id",
                "context_data": {"session_id": session_id},
            },
        )
    return session_id


SessionDep = Annotated[str, Depends(get_or_create_session_id)]


@router.get("/", response_class=HTMLResponse)
async def list_content(
    request: Request,
    db: Annotated[Session, Depends(get_db_session)],
    admin_user: Annotated[User, Depends(require_admin)],
    content_type: str | None = None,
    date: str | None = None,
    read_filter: str = "unread",
):
    """List content with optional filters."""
    # Get available dates for the dropdown
    summarized_clause = Content.content_metadata["summary"].is_not(None) & (
        Content.content_metadata["summary"] != "null"
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
    logger.debug(
        "Getting read content",
        extra={
            "component": "content",
            "operation": "list_content",
            "context_data": {"user_id": admin_user.id},
        },
    )
    read_content_ids = read_status.get_read_content_ids(db, admin_user.id)
    logger.debug(
        "Found %s read items",
        len(read_content_ids),
        extra={
            "component": "content",
            "operation": "list_content",
            "context_data": {"read_count": len(read_content_ids), "user_id": admin_user.id},
        },
    )

    # Get favorite content IDs
    favorite_content_ids = favorites.get_favorite_content_ids(db, admin_user.id)

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
            logger.warning(
                "Skipping content %s due to validation error: %s",
                c.id,
                e,
                extra={
                    "component": "content",
                    "operation": "list_content",
                    "item_id": c.id,
                    "context_data": {"content_id": c.id},
                },
            )
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
    admin_user: Annotated[User, Depends(require_admin)],
):
    """Get detailed view of a specific content item."""
    content = db.query(Content).filter(Content.id == content_id).first()

    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Mark content as read
    logger.debug(
        "Marking content %s as read",
        content_id,
        extra={
            "component": "content",
            "operation": "mark_content_read",
            "item_id": content_id,
            "context_data": {"content_id": content_id, "user_id": admin_user.id},
        },
    )
    result = read_status.mark_content_as_read(db, content_id, admin_user.id)
    logger.debug(
        "Mark as read result: %s",
        result,
        extra={
            "component": "content",
            "operation": "mark_content_read",
            "item_id": content_id,
            "context_data": {"content_id": content_id, "user_id": admin_user.id},
        },
    )
    if result:
        logger.info(
            "Successfully marked content %s as read",
            content_id,
            extra={
                "component": "content",
                "operation": "mark_content_read",
                "item_id": content_id,
                "context_data": {
                    "content_id": content_id,
                    "user_id": admin_user.id,
                    "read_at": result.read_at,
                },
            },
        )

    # Convert to domain object
    domain_content = content_to_domain(content)

    # Check if content is favorited
    is_favorited = favorites.is_content_favorited(db, content_id, admin_user.id)

    return templates.TemplateResponse(
        "content_detail.html",
        {
            "request": request,
            "content": domain_content,
            "is_favorited": is_favorited,
        },
    )


@router.get("/favorites", response_class=HTMLResponse)
async def favorites_list(
    request: Request,
    db: Annotated[Session, Depends(get_db_session)],
    admin_user: Annotated[User, Depends(require_admin)],
    read_filter: str = "all",
):
    """List favorited content."""
    # Get favorited content IDs
    favorite_content_ids = favorites.get_favorite_content_ids(db, admin_user.id)

    # Query favorited content
    if favorite_content_ids:
        query = db.query(Content).filter(Content.id.in_(favorite_content_ids))

        # Filter out "skip" classification articles
        query = query.filter(
            (Content.classification != "skip") | (Content.classification.is_(None))
        )

        # Order by most recent first
        contents = query.order_by(Content.created_at.desc()).all()
    else:
        contents = []

    # Get read content IDs
    read_content_ids = read_status.get_read_content_ids(db, admin_user.id)

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
            logger.warning(
                "Skipping content %s due to validation error: %s",
                c.id,
                e,
                extra={
                    "component": "content",
                    "operation": "list_content_mobile",
                    "item_id": c.id,
                    "context_data": {"content_id": c.id},
                },
            )
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
    admin_user: Annotated[User, Depends(require_admin)],  # noqa: ARG001
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
