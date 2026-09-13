"""
SafeVision AI — User API Routes

All endpoints are org-scoped: users can only see/manage users in their own org.
org_id comes from the authenticated user's session, never from query params.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user, require_permission
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import UserCreate, UserListResponse, UserResponse
from app.services.auth_service import hash_password

router = APIRouter(prefix="/users", tags=["Users"])
log = structlog.get_logger()


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Current User Profile",
    description="Get the authenticated user's own profile.",
)
def get_me(
    current_user: User = Depends(get_current_user),
):
    """Return the current authenticated user's profile."""
    return UserResponse.from_user(current_user)


@router.get(
    "",
    response_model=UserListResponse,
    summary="List Users",
    description="List all users in the current organization. Requires users.view permission.",
)
def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=100, description="Page size"),
    current_user: User = Depends(require_permission("users.view")),
    db: Session = Depends(get_db),
):
    """
    List users in the authenticated user's organization.
    org_id is resolved server-side — no client-supplied org filtering.
    """
    org_id = current_user.org_id

    # Count total
    total = db.query(User).filter(User.org_id == org_id).count()

    # Paginate
    offset = (page - 1) * size
    users = (
        db.query(User)
        .filter(User.org_id == org_id)
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(size)
        .all()
    )

    return UserListResponse(
        data=[UserResponse.from_user(u) for u in users],
        total=total,
        page=page,
        size=size,
    )


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create User",
    description="Create a new user in the current organization. Requires users.manage permission.",
)
def create_user(
    request: UserCreate,
    current_user: User = Depends(require_permission("users.manage")),
    db: Session = Depends(get_db),
):
    """
    Create a new user in the authenticated user's organization.

    - The new user is ALWAYS created in the same org as the admin creating them.
    - The role_id must belong to the same org (prevent cross-org role assignment).
    - Email must be unique globally.
    """
    org_id = current_user.org_id

    # Verify email uniqueness
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Verify the role belongs to the same org
    role = db.query(Role).filter(
        Role.id == request.role_id,
        Role.org_id == org_id,
    ).first()
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role_id for this organization",
        )

    # Create user
    new_user = User(
        org_id=org_id,
        email=request.email,
        name=request.name,
        pwd_hash=hash_password(request.password),
        role_id=request.role_id,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    log.info(
        "user_created",
        created_by=current_user.id,
        new_user_id=new_user.id,
        org_id=org_id,
    )

    return UserResponse.from_user(new_user)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get User",
    description="Get a specific user's profile. Requires users.view permission.",
)
def get_user(
    user_id: str,
    current_user: User = Depends(require_permission("users.view")),
    db: Session = Depends(get_db),
):
    """
    Get a user by ID — ONLY if they belong to the same organization.
    This is the IDOR prevention: always filter by org_id.
    """
    org_id = current_user.org_id

    user = db.query(User).filter(
        User.id == user_id,
        User.org_id == org_id,  # IDOR prevention: always scope by org
    ).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse.from_user(user)
