"""
SafeVision AI — Event Response Schemas

Pydantic models for the Events API responses.
Source of truth: app/models/event.py
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EventResponse(BaseModel):
    """Single event record returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    camera_id: str
    org_id: str
    event_type: str
    timestamp: datetime
    confidence: float | None = None
    detection_data: dict | None = None
    evidence_path: str | None = None
    created_at: datetime

    # Joined fields (populated in the API layer)
    camera_name: str | None = None
    zone_name: str | None = None


class EventListResponse(BaseModel):
    """Paginated list of events."""

    data: list[EventResponse]
    total: int
    page: int
    size: int
