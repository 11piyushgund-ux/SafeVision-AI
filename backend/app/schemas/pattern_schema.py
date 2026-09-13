"""
SafeVision AI — Pattern Response Schemas

Pydantic models for the Patterns API responses.
Source of truth: app/models/pattern.py
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DailyTrendItem(BaseModel):
    """Single date count representation for daily trend frequency."""

    date: str  # YYYY-MM-DD
    occurrences: int


class PatternResponse(BaseModel):
    """Single pattern record returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    zone_id: str | None = None
    rule_id: str | None = None
    pattern_type: str
    title: str
    description: str | None = None
    occurrence_count: int
    confidence_score: float | None = None
    pattern_data: dict | None = None
    status: str
    first_detected_at: datetime
    last_detected_at: datetime
    created_at: datetime

    # Joined and derived fields
    zone_name: str | None = None
    daily_trend: list[DailyTrendItem] | None = None


class PatternListResponse(BaseModel):
    """Paginated list of patterns."""

    data: list[PatternResponse]
    total: int
    page: int
    size: int
