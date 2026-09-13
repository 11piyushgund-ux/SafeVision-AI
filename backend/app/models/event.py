"""
SafeVision AI — Event Model

A detection event from the CV pipeline. Each event represents a frame-level
detection result: what was seen, where, by which camera, with what confidence.

Events are the raw data that safety rules evaluate to generate alerts.
High-volume table — indexed for fast time-range queries.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EventType(str, enum.Enum):
    """Type of detection event."""
    PPE_DETECTION = "ppe_detection"
    FIRE_SMOKE = "fire_smoke"
    ZONE_INTRUSION = "zone_intrusion"
    PERSON_DETECTED = "person_detected"
    TRACKING_UPDATE = "tracking_update"


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    camera_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("cameras.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Direct org_id for fast org-scoped queries without joining camera→site→org
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        SAEnum(EventType, name="event_type", create_constraint=True),
        nullable=False,
        index=True,
    )
    # Timestamp when the frame was captured (not when it was processed)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    # Detection confidence (0.0 - 1.0)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Detection details — what was detected, bounding boxes, class names, etc.
    # Example: {
    #   "detections": [
    #     {"class": "person", "confidence": 0.95, "bbox": [100, 200, 300, 400], "track_id": 7},
    #     {"class": "helmet", "confidence": 0.88, "bbox": [110, 190, 180, 230]}
    #   ],
    #   "frame_number": 1234,
    #   "model": "ppe_v1"
    # }
    detection_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Evidence file path (screenshot/frame for this event)
    evidence_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    camera = relationship("Camera", back_populates="events")
    organization = relationship("Organization", backref="events")
    alerts = relationship("Alert", back_populates="event")

    def __repr__(self) -> str:
        return f"<Event(id={self.id}, type={self.event_type}, camera_id={self.camera_id})>"
