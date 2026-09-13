"""
SafeVision AI — Risk Assessment Schemas

Pydantic models for the deterministic Risk Engine output.

RiskFactor: A single scored input factor with weight and explanation.
RiskAssessment: The complete risk evaluation result.

These schemas are the contract between:
  - Phase 7A Risk Engine (producer)
  - Future Alert Engine (consumer)
  - Future AI/LLM reasoning layers (consumer)
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RiskFactor(BaseModel):
    """Single contributing factor in the risk calculation."""

    name: str = Field(
        ..., description="Factor name: event_type, zone_criticality, confidence, recurrence",
    )
    raw_value: str | float | int | None = Field(
        default=None, description="Original input value before normalization",
    )
    score: float = Field(
        ..., ge=0.0, le=1.0, description="Normalized factor score [0.0, 1.0]",
    )
    weight: float = Field(
        ..., ge=0.0, le=1.0, description="Weight of this factor in the final score",
    )
    weighted_score: float = Field(
        ..., description="score × weight — contribution to final risk_score",
    )
    explanation: str = Field(
        ..., description="Human-readable explanation of this factor's contribution",
    )


class RiskAssessment(BaseModel):
    """
    Complete deterministic risk assessment result.

    Produced by RiskEngine.assess() for a single safety event.
    Contains the numeric score, categorical level, all contributing
    factors with explanations, and a full human-readable summary.
    """

    risk_score: float = Field(
        ..., ge=0.0, le=1.0, description="Overall risk score [0.0, 1.0]",
    )
    risk_level: str = Field(
        ..., description="Risk level from AlertSeverity: critical, high, medium, low, info",
    )
    factors: list[RiskFactor] = Field(
        default_factory=list, description="Individual contributing factors",
    )
    explanation: str = Field(
        ..., description="Human-readable risk summary",
    )
    event_id: str | None = Field(
        default=None, description="Source event ID",
    )
    event_type: str = Field(
        ..., description="Event type that was assessed",
    )
    camera_id: str | None = Field(
        default=None, description="Source camera ID",
    )
    org_id: str = Field(
        ..., description="Organization ID (tenant)",
    )
    assessed_at: datetime = Field(
        ..., description="Timestamp when this assessment was computed",
    )
