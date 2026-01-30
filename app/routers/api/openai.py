"""OpenAI-related endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_current_user
from app.models.user import User
from app.routers.api.models import RealtimeTokenResponse
from app.services import openai_realtime

router = APIRouter(prefix="/openai", tags=["openai"])


@router.post(
    "/realtime/token",
    response_model=RealtimeTokenResponse,
    summary="Create OpenAI Realtime token",
)
async def create_realtime_token(
    current_user: Annotated[User, Depends(get_current_user)],
) -> RealtimeTokenResponse:
    """Create a short-lived token for OpenAI Realtime sessions."""
    _ = current_user
    try:
        token, expires_at, model = openai_realtime.create_realtime_client_secret()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return RealtimeTokenResponse(token=token, expires_at=expires_at, model=model)
