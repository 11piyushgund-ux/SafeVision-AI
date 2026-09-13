"""
SafeVision AI — Events API Routes (Phase 10B)

Endpoints:
  GET /api/events — List events (org-scoped, paginated, filterable)

All endpoints:
  - Require authentication (JWT Bearer)
  - Enforce tenant isolation (org_id from authenticated user)
  - Return standard HTTP error codes
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.camera import Camera
from app.models.event import Event
from app.models.user import User
from app.models.zone import Zone
from app.schemas.event_schema import EventListResponse, EventResponse
from app.services.evidence_service import EvidenceService

router = APIRouter(prefix="/events", tags=["Events"])
log = structlog.get_logger()


@router.get(
    "",
    response_model=EventListResponse,
    summary="List Events",
    description="List detection events in the current organization. Paginated and filterable.",
)
def list_events(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=100, description="Page size"),
    event_type: str | None = Query(None, description="Filter by event type"),
    camera_id: str | None = Query(None, description="Filter by camera ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List events for the authenticated user's organization."""
    query = db.query(Event).filter(Event.org_id == current_user.org_id)

    if event_type:
        query = query.filter(Event.event_type == event_type)
    if camera_id:
        query = query.filter(Event.camera_id == camera_id)

    total = query.count()
    events = (
        query.order_by(Event.timestamp.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )

    # Build camera/zone name lookup for joined fields
    camera_ids = {e.camera_id for e in events}
    camera_map: dict[str, tuple[str, str | None]] = {}
    if camera_ids:
        cameras = (
            db.query(Camera.id, Camera.name, Camera.zone_id)
            .filter(Camera.id.in_(camera_ids))
            .all()
        )
        zone_ids = {c.zone_id for c in cameras if c.zone_id}
        zone_map: dict[str, str] = {}
        if zone_ids:
            zones = (
                db.query(Zone.id, Zone.name)
                .filter(Zone.id.in_(zone_ids))
                .all()
            )
            zone_map = {z.id: z.name for z in zones}
        for c in cameras:
            camera_map[c.id] = (c.name, zone_map.get(c.zone_id) if c.zone_id else None)

    data = []
    for e in events:
        cam_name, zone_name = camera_map.get(e.camera_id, (None, None))
        data.append(
            EventResponse(
                id=e.id,
                camera_id=e.camera_id,
                org_id=e.org_id,
                event_type=e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type),
                timestamp=e.timestamp,
                confidence=e.confidence,
                detection_data=e.detection_data,
                evidence_path=e.evidence_path,
                created_at=e.created_at,
                camera_name=cam_name,
                zone_name=zone_name,
            )
        )

    log.info(
        "events_listed",
        org_id=current_user.org_id,
        total=total,
        page=page,
        size=size,
    )
    return EventListResponse(data=data, total=total, page=page, size=size)


@router.get(
    "/{event_id}",
    response_model=EventResponse,
    summary="Get Event Detail",
    description="Get single event detail by ID including evidence_path and metadata. Authenticated and tenant-isolated.",
)
def get_event(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single event by ID for the authenticated user's organization."""
    event = (
        db.query(Event)
        .filter(Event.id == event_id, Event.org_id == current_user.org_id)
        .first()
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    cam_name, zone_name = None, None
    if event.camera_id:
        cam = db.query(Camera).filter(Camera.id == event.camera_id).first()
        if cam:
            cam_name = cam.name
            if cam.zone_id:
                zone = db.query(Zone).filter(Zone.id == cam.zone_id).first()
                if zone:
                    zone_name = zone.name

    return EventResponse(
        id=event.id,
        camera_id=event.camera_id,
        org_id=event.org_id,
        event_type=event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type),
        timestamp=event.timestamp,
        confidence=event.confidence,
        detection_data=event.detection_data,
        evidence_path=event.evidence_path,
        created_at=event.created_at,
        camera_name=cam_name,
        zone_name=zone_name,
    )


@router.get(
    "/{event_id}/evidence",
    summary="Get Event Visual Evidence",
    description="Serve the captured visual frame evidence for a specific event. Authenticated and tenant-isolated.",
)
def get_event_evidence(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Serve authenticated visual evidence for an event."""
    event = (
        db.query(Event)
        .filter(Event.id == event_id, Event.org_id == current_user.org_id)
        .first()
    )
    if not event or not event.evidence_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )

    file_path = EvidenceService.resolve_evidence_path(event.evidence_path, current_user.org_id)
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )

    return FileResponse(str(file_path), media_type="image/jpeg")
