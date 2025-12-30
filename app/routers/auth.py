"""Authentication endpoints."""

import secrets
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.core.deps import ADMIN_SESSION_COOKIE, get_current_user
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_admin_password,
    verify_apple_token,
    verify_token,
)
from app.core.settings import get_settings
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

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# PRODUCTION WARNING - IN-MEMORY SESSION STORAGE:
# This in-memory set stores admin session tokens. This has critical limitations:
#
# PROBLEMS WITH CURRENT IMPLEMENTATION:
# 1. Sessions lost on application restart - all admins logged out
# 2. Does not work with multiple server instances - sessions only valid on one server
# 3. No session expiry mechanism - sessions live forever until server restart
# 4. No ability to revoke sessions or view active sessions
# 5. Memory leak potential if sessions accumulate
#
# BEFORE PRODUCTION DEPLOYMENT - MUST FIX:
# Option 1: Redis (recommended for distributed systems)
#   - Use Redis with TTL for automatic expiry
#   - Works across multiple server instances
#   - Fast session validation
#
# Option 2: Database sessions
#   - Store sessions in database with expiry timestamp
#   - Works across server instances
#   - Can track login history and revoke sessions
#
# This implementation is suitable ONLY for single-instance development/MVP.
admin_sessions = set()


@router.post("/apple", response_model=TokenResponse)
def apple_signin(
    request: AppleSignInRequest, db: Annotated[Session, Depends(get_db_session)]
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
    logger.info("=== Apple Sign In Request Started ===")
    logger.info(f"Request data - email: {request.email}, full_name: {request.full_name}")
    logger.debug(f"ID token (first 20 chars): {request.id_token[:20]}...")

    # Verify Apple identity token
    try:
        logger.info("Verifying Apple ID token...")
        apple_claims = verify_apple_token(request.id_token)
        logger.info(f"Apple token verified successfully. Claims: {apple_claims}")

        apple_id = apple_claims.get("sub")
        logger.info(f"Extracted Apple ID: {apple_id}")

        if not apple_id:
            logger.error("Apple token missing 'sub' claim")
            raise ValueError("Missing subject in token")

    except (ValueError, Exception) as e:
        logger.error(f"Apple token verification failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid Apple token: {str(e)}"
        ) from e

    # Extract email from token if not provided or empty
    email = request.email
    if not email or email.strip() == "":
        email = apple_claims.get("email")
        logger.info(f"Email not in request, extracted from token: {email}")
    else:
        logger.info(f"Using email from request: {email}")

    if not email:
        logger.error("No email found in request or Apple token")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is required but not found in request or Apple token",
        )

    # Extract full_name from token if not provided or empty
    full_name = request.full_name
    if not full_name or full_name.strip() == "":
        # Apple sometimes provides name in the token
        token_name = apple_claims.get("name")
        if token_name:
            # Token name might be a dict like {"firstName": "John", "lastName": "Doe"}
            if isinstance(token_name, dict):
                first = token_name.get("firstName", "")
                last = token_name.get("lastName", "")
                full_name = f"{first} {last}".strip()
            else:
                full_name = token_name
            logger.info(f"Full name extracted from token: {full_name}")
        else:
            full_name = None
            logger.info("No full name provided in request or token")
    else:
        logger.info(f"Using full name from request: {full_name}")

    # Check if user already exists
    logger.info(f"Checking if user exists with apple_id: {apple_id}")
    user = db.query(User).filter(User.apple_id == apple_id).first()

    if user is None:
        logger.info(f"User not found. Creating new user with email: {email}")
        # Create new user
        user = User(
            apple_id=apple_id,
            email=email,
            full_name=full_name if full_name else None,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"New user created with ID: {user.id}")
    else:
        logger.info(f"Existing user found with ID: {user.id}")

    # Generate tokens
    logger.info("Generating access and refresh tokens...")
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    logger.info("Tokens generated successfully")

    logger.info(f"=== Apple Sign In Successful for user {user.id} ===")

    # Log OpenAI key status for debugging voice dictation
    if settings.openai_api_key:
        logger.info(
            f"🔑 [Auth] Sending OpenAI API key to client (length: {len(settings.openai_api_key)})"
        )
    else:
        logger.warning("⚠️ [Auth] No OpenAI API key configured - voice dictation unavailable")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.from_orm(user),
        openai_api_key=settings.openai_api_key,
    )


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh_token(
    request: RefreshTokenRequest, db: Annotated[Session, Depends(get_db_session)]
) -> AccessTokenResponse:
    """
    Refresh access token using refresh token.

    Implements refresh token rotation for enhanced security:
    - Issues new access token (30 min expiry)
    - Issues new refresh token (90 day expiry)
    - Old refresh token is invalidated (client should discard)

    This ensures active users stay logged in indefinitely while
    maintaining security through token rotation.

    Args:
        request: Refresh token request
        db: Database session

    Returns:
        New access token and new refresh token

    Raises:
        HTTPException: 401 if refresh token is invalid
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
    )

    try:
        payload = verify_token(request.refresh_token)
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")

        if user_id is None or token_type != "refresh":
            raise credentials_exception

    except jwt.InvalidTokenError:
        raise credentials_exception from None

    # Verify user exists and is active
    user = db.query(User).filter(User.id == int(user_id)).first()

    if user is None or not user.is_active:
        raise credentials_exception

    # Generate new access token AND new refresh token (token rotation)
    access_token = create_access_token(user.id)
    new_refresh_token = create_refresh_token(user.id)

    logger.info(f"Token refresh successful for user {user.id}")

    # Log OpenAI key status for debugging voice dictation
    if settings.openai_api_key:
        key_len = len(settings.openai_api_key)
        logger.info(f"🔑 [Refresh] Sending OpenAI API key to client (length: {key_len})")
    else:
        logger.warning("⚠️ [Refresh] No OpenAI API key - voice dictation unavailable")

    return AccessTokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        openai_api_key=settings.openai_api_key,
    )


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    """
    Get current authenticated user information.

    Args:
        current_user: Current authenticated user from JWT token

    Returns:
        Current user information

    Raises:
        HTTPException: 401 if token is invalid
    """
    return UserResponse.from_orm(current_user)


@router.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request) -> HTMLResponse:
    """
    Render admin login page.

    Args:
        request: FastAPI request object

    Returns:
        HTML login page
    """
    return templates.TemplateResponse("admin_login.html", {"request": request})


@router.post("/admin/login", response_model=AdminLoginResponse)
def admin_login(request: AdminLoginRequest, response: Response) -> AdminLoginResponse:
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
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin password"
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
        samesite="lax",
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
