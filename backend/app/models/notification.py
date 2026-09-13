"""
SafeVision AI — Notification Model (Phase 15)

Tracks all notifications sent for alerts (email, WhatsApp, in-app, webhook).
Records delivery status for audit and retry logic.

Delivery lifecycle: PENDING → SENT → (DELIVERED via future webhook) | FAILED | RETRYING

Tenant isolation: every row carries org_id — all queries must filter by org_id.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class NotificationChannel(str, enum.Enum):
    """Delivery channel for notifications."""
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    IN_APP = "in_app"
    WEBHOOK = "webhook"
    SMS = "sms"


class NotificationStatus(str, enum.Enum):
    """Delivery status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    alert_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("alerts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Direct link to the originating safety event (for context without joining alert→event)
    event_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Who this notification was sent to
    recipient_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    recipient_address: Mapped[str | None] = mapped_column(
        String(500), nullable=True,  # email address, phone number, webhook URL
    )
    channel: Mapped[str] = mapped_column(
        SAEnum(
            NotificationChannel,
            name="notification_channel",
            create_constraint=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        SAEnum(
            NotificationStatus,
            name="notification_status",
            create_constraint=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=NotificationStatus.PENDING,
        nullable=False,
    )
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Provider response (message ID, error details, etc.)
    provider_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    retry_count: Mapped[int] = mapped_column(default=0, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    # Set only when confirmed delivery receipt is received (e.g. Twilio status callback)
    # Leave NULL for MVP — SMTP has no reliable delivery confirmation
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    alert = relationship("Alert", back_populates="notifications")
    organization = relationship("Organization", backref="notifications")
    recipient = relationship("User", backref="notifications", foreign_keys=[recipient_user_id])
    event = relationship("Event", backref="notifications", foreign_keys=[event_id])

    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, channel={self.channel}, status={self.status})>"
