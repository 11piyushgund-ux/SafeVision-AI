"""
SafeVision AI — Camera & Zone Response Schemas

Pydantic models for the Cameras and Zones API responses.
Source of truth: app/models/camera.py, app/models/zone.py
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CameraResponse(BaseModel):
    """Single camera record returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    status: str
    stream_url: str | None = None
    stream_type: str | None = None
    resolution_width: int | None = None
    resolution_height: int | None = None
    fps: int | None = None
    last_frame_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    # Joined fields
    site_id: str
    zone_id: str | None = None
    zone_name: str | None = None


class ZoneResponse(BaseModel):
    """
    Single zone record returned by the API.

    Includes the real ROI polygon coordinates and required PPE list
    from the Zone model. The polygon is stored as a JSON array of
    [x, y] points in normalized camera coordinates (0.0-1.0).
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    zone_type: str
    status: str
    # ROI polygon boundary: [[x1,y1], [x2,y2], ...] in normalized 0.0-1.0 coordinates
    # This is the exact same format consumed by point_in_polygon() in the rule engine
    polygon: list[list[float]] | None = None
    # Required PPE class names for this zone (e.g. ["helmet", "safety_vest"])
    required_ppe: list[str] | None = None
    site_id: str
    created_at: datetime
    updated_at: datetime
