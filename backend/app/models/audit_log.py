"""
SafeVision AI — Audit Log Model

Immutable audit trail for all significant user actions in the system.
Every create/update/delete and security-relevant action is logged here.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,  # NULL for system-generated actions
        index=True,
    )
    # Action performed: "user.created", "alert.acknowledged", "rule.updated", etc.
    action: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # Resource type: "user", "alert", "safety_rule", "camera", etc.
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # Resource ID (the specific record that was acted upon)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # Human-readable description
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Before/after state for update operations
    changes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Request metadata (IP address, user agent, etc.)
    request_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Relationships
    organization = relationship("Organization", backref="audit_logs")
    user = relationship("User", backref="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog(action={self.action}, resource={self.resource_type}/{self.resource_id})>"
