"""
SafeVision AI — Patterns API Routes (Phase 10B)

Endpoints:
  GET /api/patterns — List patterns (org-scoped, paginated, filterable)

All endpoints:
  - Require authentication (JWT Bearer)
  - Enforce tenant isolation (org_id from authenticated user)
  - Return standard HTTP error codes
"""

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.pattern import Pattern
from app.models.user import User
from app.models.zone import Zone
from app.schemas.pattern_schema import DailyTrendItem, PatternListResponse, PatternResponse
from app.services.pattern_engine import PatternEngine

router = APIRouter(prefix="/patterns", tags=["Patterns"])
log = structlog.get_logger()


@router.get(
    "",
    response_model=PatternListResponse,
    summary="List Patterns",
    description="List detected recurring patterns in the current organization.",
)
def list_patterns(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=100, description="Page size"),
    pattern_type: str | None = Query(None, description="Filter by pattern type"),
    pattern_status: str | None = Query(None, alias="status", description="Filter by status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List patterns for the authenticated user's organization."""
    # Synchronize patterns from real events and reconcile legacy seed records
    PatternEngine.sync_patterns(db, current_user.org_id)

    query = db.query(Pattern).filter(Pattern.org_id == current_user.org_id)

    if pattern_type and pattern_type != "all":
        query = query.filter(Pattern.pattern_type == pattern_type)
    if pattern_status and pattern_status != "all":
        query = query.filter(Pattern.status == pattern_status)

    total = query.count()
    patterns = (
        query.order_by(Pattern.last_detected_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )

    # Build zone name lookup
    zone_ids = {p.zone_id for p in patterns if p.zone_id}
    zone_map: dict[str, str] = {}
    if zone_ids:
        zones = db.query(Zone.id, Zone.name).filter(Zone.id.in_(zone_ids)).all()
        zone_map = {z.id: z.name for z in zones}

    data = []
    for p in patterns:
        daily_trend_raw = (
            (p.pattern_data or {}).get("daily_trend")
            if isinstance(p.pattern_data, dict)
            else None
        )
        daily_trend = (
            [DailyTrendItem(**item) for item in daily_trend_raw]
            if daily_trend_raw
            else None
        )

        data.append(
            PatternResponse(
                id=p.id,
                org_id=p.org_id,
                zone_id=p.zone_id,
                rule_id=p.rule_id,
                pattern_type=p.pattern_type.value if hasattr(p.pattern_type, "value") else str(p.pattern_type),
                title=p.title,
                description=p.description,
                occurrence_count=p.occurrence_count,
                confidence_score=p.confidence_score,
                pattern_data=p.pattern_data,
                status=p.status.value if hasattr(p.status, "value") else str(p.status),
                first_detected_at=p.first_detected_at,
                last_detected_at=p.last_detected_at,
                created_at=p.created_at,
                zone_name=zone_map.get(p.zone_id) if p.zone_id else None,
                daily_trend=daily_trend,
            )
        )

    log.info(
        "patterns_listed",
        org_id=current_user.org_id,
        total=total,
        page=page,
    )
    return PatternListResponse(data=data, total=total, page=page, size=size)
