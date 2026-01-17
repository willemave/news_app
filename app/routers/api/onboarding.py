"""Onboarding endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.models.user import User
from app.routers.api.models import (
    OnboardingCompleteRequest,
    OnboardingCompleteResponse,
    OnboardingFastDiscoverRequest,
    OnboardingFastDiscoverResponse,
    OnboardingProfileRequest,
    OnboardingProfileResponse,
    OnboardingTutorialResponse,
)
from app.services.onboarding import (
    build_onboarding_profile,
    complete_onboarding,
    fast_discover,
    mark_tutorial_complete,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post(
    "/profile",
    response_model=OnboardingProfileResponse,
    summary="Build onboarding profile",
)
async def build_profile(
    payload: OnboardingProfileRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> OnboardingProfileResponse:
    """Build onboarding profile summary."""
    _ = current_user
    return build_onboarding_profile(payload)


@router.post(
    "/fast-discover",
    response_model=OnboardingFastDiscoverResponse,
    summary="Fast onboarding discovery",
)
async def run_fast_discover(
    payload: OnboardingFastDiscoverRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> OnboardingFastDiscoverResponse:
    """Return fast discovery suggestions for onboarding."""
    _ = current_user
    return fast_discover(payload)


@router.post(
    "/complete",
    response_model=OnboardingCompleteResponse,
    summary="Complete onboarding",
)
async def complete_onboarding_flow(
    payload: OnboardingCompleteRequest,
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> OnboardingCompleteResponse:
    """Persist onboarding selections and queue crawlers."""
    return complete_onboarding(db, current_user.id, payload)


@router.post(
    "/tutorial-complete",
    response_model=OnboardingTutorialResponse,
    summary="Mark onboarding tutorial complete",
)
async def tutorial_complete(
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> OnboardingTutorialResponse:
    """Mark tutorial completion flag for current user."""
    if not mark_tutorial_complete(db, current_user.id):
        raise HTTPException(status_code=404, detail="User not found")
    return OnboardingTutorialResponse(has_completed_new_user_tutorial=True)
