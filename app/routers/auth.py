"""Authentication endpoints."""
import secrets
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import ADMIN_SESSION_COOKIE
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_admin_password,
    verify_apple_token,
    verify_token,
)
from app.models.user import (
    AccessTokenResponse,
    AdminLoginRequest,
    AdminLoginResponse,
    AppleSignInRequest,
    RefreshTokenRequest,
    TokenResponse,
    User,
    UserResponse,
)

router = APIRouter()

# Simple in-memory admin sessions (for MVP)
# Production TODO: Use Redis or database for session storage
admin_sessions = set()


@router.post("/apple", response_model=TokenResponse)
def apple_signin(
    request: AppleSignInRequest,
    db: Session = Depends(get_db)
) -> TokenResponse:
    """
    Authenticate with Apple Sign In.

    Creates new user if first time, otherwise logs in existing user.

    Args:
        request: Apple Sign In request with id_token, email, and optional full_name
        db: Database session

    Returns:
        Access token, refresh token, and user data

    Raises:
        HTTPException: 401 if Apple token is invalid
    """
    # Verify Apple identity token
    try:
        apple_claims = verify_apple_token(request.id_token)
        apple_id = apple_claims.get("sub")

        if not apple_id:
            raise ValueError("Missing subject in token")

    except (ValueError, Exception) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Apple token: {str(e)}"
        )

    # Check if user already exists
    user = db.query(User).filter(User.apple_id == apple_id).first()

    if user is None:
        # Create new user
        user = User(
            apple_id=apple_id,
            email=request.email,
            full_name=request.full_name,
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Generate tokens
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.from_orm(user)
    )


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
) -> AccessTokenResponse:
    """
    Refresh access token using refresh token.

    Args:
        request: Refresh token request
        db: Database session

    Returns:
        New access token

    Raises:
        HTTPException: 401 if refresh token is invalid
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token"
    )

    try:
        payload = verify_token(request.refresh_token)
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")

        if user_id is None or token_type != "refresh":
            raise credentials_exception

    except jwt.InvalidTokenError:
        raise credentials_exception

    # Verify user exists and is active
    user = db.query(User).filter(User.id == int(user_id)).first()

    if user is None or not user.is_active:
        raise credentials_exception

    # Generate new access token
    access_token = create_access_token(user.id)

    return AccessTokenResponse(access_token=access_token)


@router.post("/admin/login", response_model=AdminLoginResponse)
def admin_login(
    request: AdminLoginRequest,
    response: Response
) -> AdminLoginResponse:
    """
    Admin login with password.

    Args:
        request: Admin login request with password
        response: FastAPI response to set cookie

    Returns:
        Success message

    Raises:
        HTTPException: 401 if password is incorrect
    """
    if not verify_admin_password(request.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin password"
        )

    # Generate session token
    session_token = secrets.token_urlsafe(32)
    admin_sessions.add(session_token)

    # Set httpOnly cookie
    response.set_cookie(
        key=ADMIN_SESSION_COOKIE,
        value=session_token,
        httponly=True,
        max_age=7 * 24 * 60 * 60,  # 7 days
        samesite="lax"
    )

    return AdminLoginResponse(message="Logged in as admin")


@router.post("/admin/logout")
def admin_logout(response: Response) -> dict:
    """
    Admin logout.

    Args:
        response: FastAPI response to delete cookie

    Returns:
        Success message
    """
    # Delete cookie
    response.delete_cookie(key=ADMIN_SESSION_COOKIE)

    return {"message": "Logged out"}
