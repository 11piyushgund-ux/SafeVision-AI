"""
SafeVision AI — Role & Permission Models

Roles are scoped per organization (each org can have its own role set).
Permissions are granular flags attached to roles.
The Permission Matrix from the spec is enforced as actual DB records.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Unique role name per organization
    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_role_org_name"),
    )

    # Relationships
    organization = relationship("Organization", back_populates="roles")
    permissions = relationship("Permission", back_populates="role", cascade="all, delete-orphan", lazy="joined")
    users = relationship("User", back_populates="role", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, name={self.name}, org_id={self.org_id})>"

    def has_permission(self, perm_name: str) -> bool:
        """Check if this role has a specific permission."""
        return any(p.perm_name == perm_name for p in self.permissions)


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    role_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    perm_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # One permission entry per role — no duplicate perms on same role
    __table_args__ = (
        UniqueConstraint("role_id", "perm_name", name="uq_permission_role_perm"),
    )

    # Relationships
    role = relationship("Role", back_populates="permissions")

    def __repr__(self) -> str:
        return f"<Permission(role_id={self.role_id}, perm_name={self.perm_name})>"
