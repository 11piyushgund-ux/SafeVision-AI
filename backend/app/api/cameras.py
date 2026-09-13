"""
SafeVision AI — Cameras & Zones API Routes (Phase 10B)

Endpoints:
  GET /api/cameras — List cameras (org-scoped)
  GET /api/zones   — List zones with polygon/ROI data (org-scoped)

All endpoints:
  - Require authentication (JWT Bearer)
  - Enforce tenant isolation (org_id from authenticated user)
  - Return standard HTTP error codes
"""

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.camera import Camera
from app.models.user import User
from app.models.zone import Zone
from app.schemas.camera_schema import CameraResponse, ZoneResponse

router = APIRouter(tags=["Cameras & Zones"])
log = structlog.get_logger()


@router.get(
    "/cameras",
    response_model=list[CameraResponse],
    summary="List Cameras",
    description="List all cameras in the current organization.",
)
def list_cameras(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List cameras for the authenticated user's organization."""
    cameras = (
        db.query(Camera)
        .filter(Camera.org_id == current_user.org_id)
        .order_by(Camera.name)
        .all()
    )

    # Build zone name lookup
    zone_ids = {c.zone_id for c in cameras if c.zone_id}
    zone_map: dict[str, str] = {}
    if zone_ids:
        zones = db.query(Zone.id, Zone.name).filter(Zone.id.in_(zone_ids)).all()
        zone_map = {z.id: z.name for z in zones}

    data = []
    for c in cameras:
        data.append(
            CameraResponse(
                id=c.id,
                name=c.name,
                description=c.description,
                status=c.status.value if hasattr(c.status, "value") else str(c.status),
                stream_url=c.stream_url,
                stream_type=c.stream_type,
                resolution_width=c.resolution_width,
                resolution_height=c.resolution_height,
                fps=c.fps,
                last_frame_at=c.last_frame_at,
                created_at=c.created_at,
                updated_at=c.updated_at,
                site_id=c.site_id,
                zone_id=c.zone_id,
                zone_name=zone_map.get(c.zone_id) if c.zone_id else None,
            )
        )

    log.info("cameras_listed", org_id=current_user.org_id, count=len(data))
    return data


@router.get(
    "/zones",
    response_model=list[ZoneResponse],
    summary="List Zones",
    description=(
        "List all zones in the current organization, including ROI polygon "
        "coordinates and required PPE configuration."
    ),
)
def list_zones(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List zones for the authenticated user's organization.

    Each zone includes:
    - polygon: ROI boundary as [[x,y], ...] in normalized 0.0-1.0 coordinates
    - required_ppe: list of PPE class names required in this zone
    - zone_type: determines which rule engine evaluator applies
    """
    zones = (
        db.query(Zone)
        .filter(Zone.org_id == current_user.org_id)
        .order_by(Zone.name)
        .all()
    )

    data = []
    for z in zones:
        data.append(
            ZoneResponse(
                id=z.id,
                name=z.name,
                description=z.description,
                zone_type=z.zone_type.value if hasattr(z.zone_type, "value") else str(z.zone_type),
                status=z.status.value if hasattr(z.status, "value") else str(z.status),
                polygon=z.polygon,
                required_ppe=z.required_ppe,
                site_id=z.site_id,
                created_at=z.created_at,
                updated_at=z.updated_at,
            )
        )

    log.info("zones_listed", org_id=current_user.org_id, count=len(data))
    return data
