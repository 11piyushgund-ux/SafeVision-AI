"""
SafeVision AI — Dashboard Statistics API Route (Phase 10B)

Endpoints:
  GET /api/stats/summary — Aggregated counts for the dashboard

All endpoints:
  - Require authentication (JWT Bearer)
  - Enforce tenant isolation (org_id from authenticated user)
"""

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.alert import Alert, AlertStatus
from app.models.camera import Camera, CameraStatus
from app.models.event import Event
from app.models.user import User
from app.models.zone import Zone, ZoneStatus
from app.schemas.stats_schema import DashboardSummary

router = APIRouter(prefix="/stats", tags=["Statistics"])
log = structlog.get_logger()


@router.get(
    "/summary",
    response_model=DashboardSummary,
    summary="Dashboard Summary",
    description="Aggregated counts for the dashboard header and stats cards.",
)
def get_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return aggregated counts for the authenticated user's organization."""
    org_id = current_user.org_id

    total_alerts = db.query(func.count(Alert.id)).filter(Alert.org_id == org_id).scalar() or 0
    new_alerts = (
        db.query(func.count(Alert.id))
        .filter(Alert.org_id == org_id, Alert.status == AlertStatus.NEW)
        .scalar() or 0
    )
    acknowledged_alerts = (
        db.query(func.count(Alert.id))
        .filter(Alert.org_id == org_id, Alert.status == AlertStatus.ACKNOWLEDGED)
        .scalar() or 0
    )
    total_events = db.query(func.count(Event.id)).filter(Event.org_id == org_id).scalar() or 0
    total_cameras = db.query(func.count(Camera.id)).filter(Camera.org_id == org_id).scalar() or 0
    online_cameras = (
        db.query(func.count(Camera.id))
        .filter(Camera.org_id == org_id, Camera.status == CameraStatus.ONLINE)
        .scalar() or 0
    )
    total_zones = db.query(func.count(Zone.id)).filter(Zone.org_id == org_id).scalar() or 0
    active_zones = (
        db.query(func.count(Zone.id))
        .filter(Zone.org_id == org_id, Zone.status == ZoneStatus.ACTIVE)
        .scalar() or 0
    )

    log.info("stats_summary", org_id=org_id)
    return DashboardSummary(
        total_alerts=total_alerts,
        new_alerts=new_alerts,
        acknowledged_alerts=acknowledged_alerts,
        total_events=total_events,
        total_cameras=total_cameras,
        online_cameras=online_cameras,
        total_zones=total_zones,
        active_zones=active_zones,
    )
