"""User-scoped content statistics endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.core.db import get_readonly_db_session
from app.core.deps import get_current_user
from app.core.timing import timed
from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content, ContentStatusEntry
from app.models.user import User
from app.repositories.content_repository import apply_visibility_filters, build_visibility_context
from app.routers.api.models import ProcessingCountResponse, UnreadCountsResponse

router = APIRouter(prefix="/stats")


@router.get(
    "/unread-counts",
    response_model=UnreadCountsResponse,
    summary="Get unread content counts by type",
    description="Get the total count of unread items for each content type.",
)
def get_unread_counts(
    db: Annotated[Session, Depends(get_readonly_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UnreadCountsResponse:
    """Get unread counts for each content type.

    Optimized to use NOT EXISTS instead of NOT IN for much better performance
    with large read lists (30x faster: ~20ms vs ~650ms).
    """
    context = build_visibility_context(current_user.id)

    with timed("query unread_counts"):
        count_query = db.query(Content.content_type, func.count(Content.id))
        count_query = apply_visibility_filters(count_query, context)
        count_query = count_query.filter(~context.is_read).group_by(Content.content_type)
        results = count_query.all()

    counts = {"article": 0, "podcast": 0, "news": 0}
    for content_type, count in results:
        if content_type in counts:
            counts[content_type] = count

    return UnreadCountsResponse(
        article=counts["article"], podcast=counts["podcast"], news=counts["news"]
    )


@router.get(
    "/processing-count",
    response_model=ProcessingCountResponse,
    summary="Get long-form processing count",
    description=(
        "Return the number of long-form content items currently pending or processing "
        "for the authenticated user (articles, podcasts, and YouTube)."
    ),
)
def get_processing_count(
    db: Annotated[Session, Depends(get_readonly_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProcessingCountResponse:
    """Return the number of long-form content items pending or processing for the user."""
    long_form_types = {ContentType.ARTICLE.value, ContentType.PODCAST.value}
    processing_statuses = {ContentStatus.PENDING.value, ContentStatus.PROCESSING.value}

    with timed("query processing_count"):
        count_query = (
            db.query(func.count(Content.id))
            .join(ContentStatusEntry, ContentStatusEntry.content_id == Content.id)
            .filter(ContentStatusEntry.user_id == current_user.id)
            .filter(ContentStatusEntry.status == "inbox")
            .filter(Content.status.in_(processing_statuses))
            .filter(
                or_(
                    Content.content_type.in_(long_form_types),
                    and_(
                        Content.platform == "youtube",
                        Content.content_type != ContentType.NEWS.value,
                    ),
                )
            )
        )
        processing_count = count_query.scalar() or 0

    return ProcessingCountResponse(processing_count=processing_count)
