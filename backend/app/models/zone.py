"""
SafeVision AI — Zone Model

A monitored area within a site. Zones define:
- A polygon boundary (JSON array of [x,y] points in normalized coordinates)
- Required PPE for that zone (JSON list of PPE class names)
- Zone type (exclusion zone, PPE required zone, etc.)

Zones are the spatial unit for safety rules — rules can be scoped to a zone.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ZoneType(str, enum.Enum):
    """Type of monitored zone."""
    PPE_REQUIRED = "ppe_required"
    EXCLUSION = "exclusion"
    SPEED_LIMIT = "speed_limit"
    FIRE_WATCH = "fire_watch"
    GENERAL = "general"


class ZoneStatus(str, enum.Enum):
    """Zone operational status."""
    ACTIVE = "active"
    INACTIVE = "inactive"


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    site_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Direct org_id for fast filtering without joining through site
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    zone_type: Mapped[str] = mapped_column(
        SAEnum(ZoneType, name="zone_type", create_constraint=True),
        default=ZoneType.GENERAL,
        nullable=False,
    )
    # Polygon boundary: JSON array of [x, y] points in normalized camera coordinates (0.0-1.0)
    # Stored directly as: [[0.1, 0.2], [0.8, 0.2], [0.8, 0.9], [0.1, 0.9]]
    # NOT a wrapper object — the array IS the value of this column.
    polygon: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Required PPE for this zone: JSON list of PPE class names from the CV model
    # Stored directly as: ["helmet", "safety_vest", "goggles"]
    # NOT a wrapper object — the list IS the value of this column.
    required_ppe: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    status: Mapped[str] = mapped_column(
        SAEnum(ZoneStatus, name="zone_status", create_constraint=True),
        default=ZoneStatus.ACTIVE,
        nullable=False,
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

    # Relationships
    site = relationship("Site", back_populates="zones")
    organization = relationship("Organization", backref="zones")
    cameras = relationship("Camera", back_populates="zone")
    safety_rules = relationship("SafetyRule", back_populates="zone")

    def __repr__(self) -> str:
        return f"<Zone(id={self.id}, name={self.name}, type={self.zone_type})>"
