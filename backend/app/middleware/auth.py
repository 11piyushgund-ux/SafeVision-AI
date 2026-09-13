"""
SafeVision AI — Authentication & Authorization Dependencies

These FastAPI dependencies enforce auth, tenant context, and permissions
on every endpoint that uses them. The org_id is ALWAYS resolved server-side
from the authenticated user's JWT — never from a client-supplied parameter.

Usage:
    @router.get("/resource")
    def list_resources(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        # current_user.org_id is the trust boundary
        ...

    @router.post("/admin-action")
    def admin_action(
        current_user: User = Depends(require_permission("users.manage")),
    ):
        ...
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserStatus
from app.services.auth_service import decode_access_token

# Bearer token extractor
_bearer_scheme = HTTPBearer(auto_error=True)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Extract and validate the JWT from the Authorization header.
    Load the full User from the database (including role + permissions).

    This is the core trust boundary:
    - The org_id comes from the USER RECORD in the DB, not from the token alone
    - If the user is suspended/deactivated, reject immediately
    - If the user's org doesn't match the token, something is wrong — reject

    Returns the User ORM object with .role and .role.permissions loaded.
    """
    token = credentials.credentials

    # Decode JWT
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Load user from DB (with role + permissions eagerly loaded)
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check user status
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active",
        )

    # Verify org_id in token matches the user's actual org
    # (defense against token tampering or stale tokens after org change)
    token_org_id = payload.get("org_id")
    if token_org_id != user.org_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token organization mismatch",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_current_org_id(
    current_user: User = Depends(get_current_user),
) -> str:
    """
    Resolve the current organization ID from the authenticated user.

    This is the ONLY way to get org_id for data queries.
    Never accept org_id from query params or request body as a trust boundary.
    """
    return current_user.org_id


def require_permission(perm_name: str):
    """
    Factory for a permission-checking dependency.

    Usage:
        @router.post("/action")
        def action(user: User = Depends(require_permission("alerts.acknowledge"))):
            ...

    Returns a dependency function that:
    1. Authenticates the user (via get_current_user)
    2. Checks if their role has the required permission
    3. Raises 403 if not
    """

    def _check_permission(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if not current_user.has_permission(perm_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{perm_name}' required",
            )
        return current_user

    return _check_permission
