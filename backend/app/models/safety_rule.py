"""
SafeVision AI — Safety Rule Model

Configurable safety rules that define what constitutes a violation.
Rules are org-scoped and optionally zone-scoped.

The `parameters` JSONB field is the key design decision:
thresholds and required PPE are configurable per-rule, not hardcoded constants.

Example parameters:
{
    "confidence_threshold": 0.75,
    "required_ppe": ["helmet", "safety_vest"],
    "min_violation_duration_seconds": 3,
    "cooldown_seconds": 60,
    "max_persons_in_zone": 5,
    "recommendation_template": "Workers in {zone_name} must wear {ppe_list}."
}
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RuleType(str, enum.Enum):
    """Type of safety rule."""
    PPE_VIOLATION = "ppe_violation"
    EXCLUSION_ZONE = "exclusion_zone"
    FIRE_SMOKE = "fire_smoke"
    OVERCROWDING = "overcrowding"
    CUSTOM = "custom"


class RuleSeverity(str, enum.Enum):
    """Default severity when this rule triggers an alert."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class RuleStatus(str, enum.Enum):
    """Rule lifecycle status."""
    ACTIVE = "active"
    DISABLED = "disabled"


class SafetyRule(Base):
    __tablename__ = "safety_rules"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    zone_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("zones.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_type: Mapped[str] = mapped_column(
        SAEnum(RuleType, name="rule_type", create_constraint=True),
        nullable=False,
    )
    severity: Mapped[str] = mapped_column(
        SAEnum(RuleSeverity, name="rule_severity", create_constraint=True),
        default=RuleSeverity.MEDIUM,
        nullable=False,
    )
    # THE KEY FIELD: all thresholds, PPE requirements, and recommendation
    # templates are stored here — never hardcoded in code.
    parameters: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="Rule-specific config: confidence_threshold, required_ppe, cooldown, etc.",
    )
    status: Mapped[str] = mapped_column(
        SAEnum(RuleStatus, name="rule_status", create_constraint=True),
        default=RuleStatus.ACTIVE,
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
    organization = relationship("Organization", backref="safety_rules")
    zone = relationship("Zone", back_populates="safety_rules")
    alerts = relationship("Alert", back_populates="rule")

    def __repr__(self) -> str:
        return f"<SafetyRule(id={self.id}, name={self.name}, type={self.rule_type})>"
