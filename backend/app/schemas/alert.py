"""
SafeVision AI — Alert Pydantic Schemas (Phase 7B)

Request/response contracts for the Alert API.

Uses the existing Alert/AlertState SQLAlchemy models and AlertSeverity/AlertStatus enums.
Does NOT duplicate database models.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# ==============================================================================
# Request Schemas
# ==============================================================================

class AlertTransitionRequest(BaseModel):
    """Request to transition an alert to a new lifecycle status.

    PATCH /api/alerts/{alert_id}/status
    """

    status: str = Field(
        ..., description="Target status: acknowledged, escalated, resolved",
    )
    reason: str | None = Field(
        default=None, description="Optional reason for the transition",
    )


# ==============================================================================
# Response Schemas
# ==============================================================================

class AlertStateResponse(BaseModel):
    """Single lifecycle audit record."""

    id: str
    from_status: str | None
    to_status: str
    changed_by: str | None
    reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertResponse(BaseModel):
    """Single alert response."""

    id: str
    event_id: str | None
    rule_id: str | None
    org_id: str
    title: str
    description: str | None
    severity: str
    status: str
    assigned_to: str | None
    evidence_path: str | None
    metadata_json: dict | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class AlertDetailResponse(AlertResponse):
    """Alert response with lifecycle audit trail."""

    states: list[AlertStateResponse] = Field(default_factory=list)


class AlertListResponse(BaseModel):
    """Paginated alert list response."""

    data: list[AlertResponse]
    total: int
    page: int
    size: int
