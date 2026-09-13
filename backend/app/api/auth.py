"""
SafeVision AI — Auth API Routes

POST /api/auth/login — Authenticate a user and return a JWT.
"""

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserStatus
from app.schemas.auth import LoginRequest, LoginResponse, UserResponse
from app.services.auth_service import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])
log = structlog.get_logger()


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="User Login",
    description="Authenticate with email and password. Returns a JWT access token.",
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Authenticate a user.

    1. Look up user by email
    2. Verify password against bcrypt hash
    3. Check user status (must be active)
    4. Issue JWT with org_id from the user record (server-side resolution)
    5. Update last_login timestamp
    """
    # Find user by email
    user = db.query(User).filter(User.email == request.email).first()

    if user is None:
        log.warning("login_failed", reason="user_not_found", email=request.email)
        # Use generic error to prevent email enumeration
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Verify password
    if not verify_password(request.password, user.pwd_hash):
        log.warning("login_failed", reason="wrong_password", user_id=user.id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Check user status
    if user.status != UserStatus.ACTIVE:
        log.warning("login_failed", reason="inactive_account", user_id=user.id, status=user.status)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active",
        )

    # Create JWT — org_id comes from the user record, never from the request
    role_name = user.role.name if user.role else "unknown"
    token = create_access_token(
        user_id=user.id,
        org_id=user.org_id,
        role_name=role_name,
    )

    # Update last_login
    user.last_login = datetime.now(timezone.utc)
    db.commit()

    log.info("login_success", user_id=user.id, org_id=user.org_id, role=role_name)

    return LoginResponse(
        access_token=token,
        user=UserResponse.from_user(user),
    )
