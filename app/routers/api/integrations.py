"""Integration endpoints for external providers (X/Twitter)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.models.user import User
from app.routers.api.models import (
    IntegrationDisconnectResponse,
    XConnectionResponse,
    XOAuthExchangeRequest,
    XOAuthStartRequest,
    XOAuthStartResponse,
)
from app.services.x_integration import (
    XConnectionView,
    disconnect_x_connection,
    exchange_x_oauth,
    get_x_connection_view,
    start_x_oauth,
)

router = APIRouter(prefix="/integrations/x", tags=["integrations"])


def _to_connection_response(view: XConnectionView) -> XConnectionResponse:
    return XConnectionResponse(
        provider=view.provider,
        connected=view.connected,
        is_active=view.is_active,
        provider_user_id=view.provider_user_id,
        provider_username=view.provider_username,
        scopes=view.scopes,
        last_synced_at=view.last_synced_at,
        last_status=view.last_status,
        last_error=view.last_error,
        twitter_username=view.twitter_username,
    )


@router.get("/connection", response_model=XConnectionResponse)
def get_x_connection(
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> XConnectionResponse:
    """Return current X connection status for the authenticated user."""
    return _to_connection_response(get_x_connection_view(db, current_user))


@router.post("/oauth/start", response_model=XOAuthStartResponse)
def start_x_oauth_flow(
    payload: XOAuthStartRequest,
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> XOAuthStartResponse:
    """Start X OAuth flow and return authorize URL."""
    try:
        authorize_url, state, scopes = start_x_oauth(
            db,
            user=current_user,
            twitter_username=payload.twitter_username,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return XOAuthStartResponse(
        authorize_url=authorize_url,
        state=state,
        scopes=scopes,
    )


@router.post("/oauth/exchange", response_model=XConnectionResponse)
def exchange_x_oauth_code(
    payload: XOAuthExchangeRequest,
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> XConnectionResponse:
    """Exchange OAuth callback code and persist X connection."""
    try:
        view = exchange_x_oauth(
            db,
            user=current_user,
            code=payload.code,
            state=payload.state,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return _to_connection_response(view)


@router.delete("/connection", response_model=IntegrationDisconnectResponse)
def disconnect_x(
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> IntegrationDisconnectResponse:
    """Disconnect the user's X integration."""
    disconnect_x_connection(db, user=current_user)
    return IntegrationDisconnectResponse()
