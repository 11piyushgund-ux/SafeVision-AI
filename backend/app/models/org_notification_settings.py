"""
SafeVision AI — Organization Notification Settings Model (Phase 15)

One row per organization. Persists:
  - which channel is active (email | whatsapp)
  - whether notifications are enabled
  - the recipient address/number for that org

This is the tenant boundary for notification configuration.
Provider secrets (SMTP password, Twilio auth token) remain in .env / Settings —
never stored in the database.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class NotificationMode(str, enum.Enum):
    """Supported notification delivery channels."""
    EMAIL = "email"
    WHATSAPP = "whatsapp"


class OrgNotificationSettings(Base):
    """
    Organization-level notification configuration.

    One row per org (unique on org_id).
    Updated via POST /api/notifications/settings by an org admin.
    """
    __tablename__ = "org_notification_settings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,   # one settings row per org
        index=True,
    )
    notifications_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
    )
    notification_mode: Mapped[str] = mapped_column(
        SAEnum(
            NotificationMode,
            name="notification_mode",
            create_constraint=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=NotificationMode.EMAIL,
        nullable=False,
    )
    # Dedicated channel recipients (Phase 18)
    email_recipient: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
    )
    whatsapp_recipient: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
    )
    # Legacy recipient address/number — maintained for backward compatibility
    notification_recipient: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship
    organization = relationship("Organization", backref="notification_settings")

    def __repr__(self) -> str:
        return (
            f"<OrgNotificationSettings("
            f"org_id={self.org_id}, "
            f"mode={self.notification_mode}, "
            f"enabled={self.notifications_enabled})>"
        )
