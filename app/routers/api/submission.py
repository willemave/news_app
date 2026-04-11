"""Endpoint for one-off user submissions."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import String, and_, cast, or_
from sqlalchemy.orm import Session

from app.commands import submit_content as submit_content_command
from app.core.db import get_db_session, get_readonly_db_session
from app.core.deps import get_current_user
from app.core.logging import get_logger
from app.models.api.common import (
    SubmissionStatusListResponse,
    SubmissionStatusResponse,
)
from app.models.content_submission import ContentSubmissionResponse, SubmitContentRequest
from app.models.metadata import ContentStatus, ContentType
from app.models.pagination import PaginationMetadata
from app.models.schema import Content
from app.models.user import User
from app.utils.pagination import PaginationCursor

router = APIRouter()
logger = get_logger(__name__)


@router.post(
    "/submit",
    response_model=ContentSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_200_OK: {
            "model": ContentSubmissionResponse,
            "description": "Existing content matched and reused",
        }
    },
    summary="Submit a one-off URL for processing",
    description="Submit article or podcast URLs for processing. Only http/https URLs are accepted.",
)
async def submit_content(
    payload: SubmitContentRequest,
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ContentSubmissionResponse | JSONResponse:
    """Create or reuse content for a user-submitted URL and enqueue processing."""
    try:
        result = submit_content_command.execute(
            db,
            payload=payload,
            current_user=current_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    status_code = status.HTTP_200_OK if result.already_exists else status.HTTP_201_CREATED
    return JSONResponse(status_code=status_code, content=result.model_dump(mode="json"))


@router.get(
    "/submissions/list",
    response_model=SubmissionStatusListResponse,
    summary="List user-submitted content still processing or failed",
    description=(
        "Returns self-submitted content items that are not yet completed, including "
        "processing, failed, and skipped statuses."
    ),
)
async def list_submission_statuses(
    db: Annotated[Session, Depends(get_readonly_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    cursor: str | None = Query(None, description="Pagination cursor for next page"),
    limit: int = Query(
        25,
        ge=1,
        le=100,
        description="Number of items per page (max 100)",
    ),
) -> SubmissionStatusListResponse:
    """List status information for the current user's submissions."""
    user_id = current_user.id
    if user_id is None:
        raise ValueError("Authenticated user is missing an id")
    last_id = None
    last_created_at = None
    if cursor:
        try:
            cursor_data = PaginationCursor.decode_cursor(cursor)
            last_id = cursor_data["last_id"]
            last_created_at = cursor_data["last_created_at"]
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    status_filter = [
        ContentStatus.NEW.value,
        ContentStatus.PENDING.value,
        ContentStatus.PROCESSING.value,
        ContentStatus.FAILED.value,
        ContentStatus.SKIPPED.value,
    ]

    submitter_filter = cast(Content.content_metadata["submitted_by_user_id"], String) == str(
        user_id
    )

    query = (
        db.query(Content)
        .filter(submitter_filter)
        .filter(Content.status.in_(status_filter))
        .order_by(Content.created_at.desc(), Content.id.desc())
    )

    if last_id and last_created_at:
        query = query.filter(
            or_(
                Content.created_at < last_created_at,
                and_(Content.created_at == last_created_at, Content.id < last_id),
            )
        )

    contents = query.limit(limit + 1).all()

    has_more = len(contents) > limit
    if has_more:
        contents = contents[:limit]

    submissions: list[SubmissionStatusResponse] = []
    for content in contents:
        try:
            metadata = content.content_metadata or {}
            raw_content_type = content.content_type
            raw_status = content.status
            if raw_content_type is None or raw_status is None:
                raise ValueError("Submission row is missing required fields")
            submissions.append(
                SubmissionStatusResponse(
                    id=_require_content_id(content.id),
                    content_type=ContentType(raw_content_type),
                    url=str(content.url),
                    source_url=content.source_url,
                    title=content.title,
                    status=ContentStatus(raw_status),
                    error_message=content.error_message,
                    created_at=content.created_at.isoformat() if content.created_at else "",
                    processed_at=content.processed_at.isoformat() if content.processed_at else None,
                    submitted_via=metadata.get("submitted_via"),
                    is_self_submission=True,
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Skipping submission %s due to validation error: %s",
                content.id,
                exc,
                extra={
                    "component": "submission_status",
                    "operation": "list_submissions",
                    "item_id": content.id,
                    "context_data": {"content_id": content.id},
                },
            )
            continue

    next_cursor = None
    if has_more and contents:
        last_item = contents[-1]
        if last_item.created_at is None:
            raise ValueError("Submission row is missing created_at")
        next_cursor = PaginationCursor.encode_cursor(
            last_id=_require_content_id(last_item.id),
            last_created_at=last_item.created_at,
            filters={},
        )

    return SubmissionStatusListResponse(
        submissions=submissions,
        meta=PaginationMetadata(
            next_cursor=next_cursor,
            has_more=has_more,
            page_size=len(submissions),
            total=len(submissions),
        ),
    )


def _require_content_id(content_id: int | None) -> int:
    if content_id is None:
        raise ValueError("Content is missing an id")
    return content_id
