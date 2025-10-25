"""Authentication endpoints."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_apple_token,
)
from app.models.user import AppleSignInRequest, TokenResponse, User, UserResponse

router = APIRouter()


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
