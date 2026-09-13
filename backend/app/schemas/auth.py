"""
SafeVision AI — Pydantic Schemas for Auth, Users, and Organizations

These define the API request/response contracts.
"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

# ==============================================================================
# Auth Schemas
# ==============================================================================

class LoginRequest(BaseModel):
    """POST /api/auth/login request body."""
    email: EmailStr
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    """POST /api/auth/login response."""
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class TokenPayload(BaseModel):
    """JWT token payload (decoded)."""
    sub: str          # user_id
    org_id: str       # organization_id (resolved server-side)
    role: str         # role name
    exp: datetime     # expiration


# ==============================================================================
# Organization Schemas
# ==============================================================================

class OrgCreate(BaseModel):
    """Request to create a new organization."""
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=255, pattern=r"^[a-z0-9\-]+$")
    description: str | None = None


class OrgResponse(BaseModel):
    """Organization response."""
    id: str
    name: str
    slug: str
    status: str
    description: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ==============================================================================
# User Schemas
# ==============================================================================

class UserCreate(BaseModel):
    """Request to create a new user (admin action)."""
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    role_id: str


class UserUpdate(BaseModel):
    """Request to update a user."""
    name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr | None = None
    role_id: str | None = None
    status: str | None = None


class UserResponse(BaseModel):
    """User response (never includes password hash)."""
    id: str
    org_id: str
    email: str
    name: str
    role_id: str
    role_name: str | None = None
    status: str
    last_login: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_user(cls, user) -> "UserResponse":
        """Build response from User ORM model, including role name."""
        return cls(
            id=user.id,
            org_id=user.org_id,
            email=user.email,
            name=user.name,
            role_id=user.role_id,
            role_name=user.role.name if user.role else None,
            status=user.status,
            last_login=user.last_login,
            created_at=user.created_at,
        )


class UserListResponse(BaseModel):
    """Paginated user list response."""
    data: list[UserResponse]
    total: int
    page: int
    size: int


# Forward reference resolution
LoginResponse.model_rebuild()
