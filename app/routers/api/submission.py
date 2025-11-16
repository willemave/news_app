"""Endpoint for one-off user submissions."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.models.user import User
from app.routers.api.models import ContentSubmissionResponse, SubmitContentRequest
from app.services.content_submission import submit_user_content

router = APIRouter()


@router.post(
    "/submit",
    response_model=ContentSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a one-off URL for processing",
    description="Submit article or podcast URLs for processing. Only http/https URLs are accepted.",
)
async def submit_content(
    payload: SubmitContentRequest,
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ContentSubmissionResponse:
    """Create or reuse content for a user-submitted URL and enqueue processing."""
    try:
        result = submit_user_content(db, payload, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    status_code = status.HTTP_200_OK if result.already_exists else status.HTTP_201_CREATED
    return JSONResponse(status_code=status_code, content=result.model_dump(mode="json"))

