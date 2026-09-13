"""
SafeVision AI — Alert and AlertState Models

Alert: A safety violation that was triggered by a rule evaluating an event.
AlertState: REQUIRED audit trail for alert lifecycle transitions.

Alert lifecycle: NEW → ACKNOWLEDGED → INVESTIGATING → RESOLVED / ESCALATED → CLOSED
Every state transition is recorded in alert_states — this is not optional.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AlertSeverity(str, enum.Enum):
    """Alert severity level."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertStatus(str, enum.Enum):
    """Alert lifecycle status."""
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"
    FALSE_POSITIVE = "false_positive"


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    event_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    rule_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("safety_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Direct org_id for fast org-scoped queries
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(
        SAEnum(AlertSeverity, name="alert_severity", create_constraint=True),
        default=AlertSeverity.MEDIUM,
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        SAEnum(AlertStatus, name="alert_status", create_constraint=True),
        default=AlertStatus.NEW,
        nullable=False,
        index=True,
    )
    # Who is currently assigned to this alert
    assigned_to: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Evidence file path (screenshot/frame)
    evidence_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Additional context (detection details, zone info, etc.)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Relationships
    event = relationship("Event", back_populates="alerts")
    rule = relationship("SafetyRule", back_populates="alerts")
    organization = relationship("Organization", backref="alerts")
    assigned_user = relationship("User", backref="assigned_alerts", foreign_keys=[assigned_to])
    # REQUIRED: Every alert has an audit trail of state changes
    states = relationship("AlertState", back_populates="alert", cascade="all, delete-orphan",
                          order_by="AlertState.created_at")
    notifications = relationship("Notification", back_populates="alert", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Alert(id={self.id}, severity={self.severity}, status={self.status})>"


class AlertState(Base):
    """
    REQUIRED audit trail for alert lifecycle transitions.

    Every time an alert changes status, a new AlertState row is created.
    This provides a complete, immutable history of who did what and when.
    """
    __tablename__ = "alert_states"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    alert_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("alerts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[str | None] = mapped_column(
        String(50), nullable=True,  # NULL for the initial state
    )
    to_status: Mapped[str] = mapped_column(
        String(50), nullable=False,
    )
    changed_by: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,  # NULL for system-generated transitions
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Additional context for this transition
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Relationships
    alert = relationship("Alert", back_populates="states")
    user = relationship("User", backref="alert_state_changes", foreign_keys=[changed_by])

    def __repr__(self) -> str:
        return f"<AlertState(alert_id={self.alert_id}, {self.from_status} → {self.to_status})>"
