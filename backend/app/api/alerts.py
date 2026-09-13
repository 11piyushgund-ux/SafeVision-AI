"""
SafeVision AI — Alert API Routes (Phase 7B)

Endpoints:
  GET    /api/alerts           — List alerts (org-scoped, paginated)
  GET    /api/alerts/{id}      — Get alert detail with audit trail
  PATCH  /api/alerts/{id}/status — Transition alert lifecycle

All endpoints:
  - Require authentication (JWT Bearer)
  - Enforce tenant isolation (org_id from authenticated user)
  - Enforce RBAC permissions
  - Return standard HTTP error codes
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user, require_permission
from app.models.alert import AlertStatus
from app.models.user import User
from app.schemas.alert import (
    AlertDetailResponse,
    AlertListResponse,
    AlertResponse,
    AlertStateResponse,
    AlertTransitionRequest,
)
from app.services.alert_engine import AlertEngine, InvalidTransitionError
from app.services.evidence_service import EvidenceService

router = APIRouter(prefix="/alerts", tags=["Alerts"])
log = structlog.get_logger()


# ==============================================================================
# GET /api/alerts — List Alerts
# ==============================================================================

@router.get(
    "",
    response_model=AlertListResponse,
    summary="List Alerts",
    description="List alerts in the current organization. Requires alerts.view permission.",
)
def list_alerts(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=100, description="Page size"),
    severity: str | None = Query(None, description="Filter by severity"),
    alert_status: str | None = Query(None, alias="status", description="Filter by status"),
    current_user: User = Depends(require_permission("alerts.view")),
    db: Session = Depends(get_db),
):
    """List alerts for the authenticated user's organization."""
    alerts, total = AlertEngine.list_alerts(
        db=db,
        org_id=current_user.org_id,
        page=page,
        size=size,
        severity=severity,
        status=alert_status,
    )

    return AlertListResponse(
        data=[AlertResponse.model_validate(a) for a in alerts],
        total=total,
        page=page,
        size=size,
    )


# ==============================================================================
# GET /api/alerts/{alert_id} — Get Alert Detail
# ==============================================================================

@router.get(
    "/{alert_id}",
    response_model=AlertDetailResponse,
    summary="Get Alert",
    description="Get alert detail with lifecycle audit trail. Requires alerts.view permission.",
)
def get_alert(
    alert_id: str,
    current_user: User = Depends(require_permission("alerts.view")),
    db: Session = Depends(get_db),
):
    """Get a single alert by ID — only if it belongs to the user's org."""
    alert = AlertEngine.get_alert(db, alert_id, current_user.org_id)
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    return AlertDetailResponse(
        **AlertResponse.model_validate(alert).model_dump(),
        states=[AlertStateResponse.model_validate(s) for s in alert.states],
    )


@router.get(
    "/{alert_id}/evidence",
    summary="Get Alert Visual Evidence",
    description="Serve the captured visual frame evidence for a specific alert. Authenticated and tenant-isolated.",
)
def get_alert_evidence(
    alert_id: str,
    current_user: User = Depends(require_permission("alerts.view")),
    db: Session = Depends(get_db),
):
    """Serve authenticated visual evidence for an alert."""
    alert = AlertEngine.get_alert(db, alert_id, current_user.org_id)
    if not alert or not alert.evidence_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )

    file_path = EvidenceService.resolve_evidence_path(alert.evidence_path, current_user.org_id)
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )

    return FileResponse(str(file_path), media_type="image/jpeg")


# ==============================================================================
# PATCH /api/alerts/{alert_id}/status — Lifecycle Transition
# ==============================================================================

@router.patch(
    "/{alert_id}/status",
    response_model=AlertDetailResponse,
    summary="Transition Alert Status",
    description="Transition an alert to a new lifecycle status. Requires appropriate permission.",
)
def transition_alert(
    alert_id: str,
    body: AlertTransitionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Transition an alert's lifecycle status.

    Validates:
    1. Alert exists and belongs to user's org (404 if not)
    2. Target status is valid (409 if not)
    3. Transition is allowed from current status (409 if not)
    4. User has required permission (403 if not)

    On success: updates alert, creates audit row, commits atomically.
    """
    # 1. Resolve target status
    try:
        to_status = AlertStatus(body.status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid target status: '{body.status}'",
        ) from None

    # 2. Check permission for this transition
    required_perm = AlertEngine.get_required_permission(to_status)
    if required_perm and not current_user.has_permission(required_perm):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission '{required_perm}' required",
        )

    # 3. Fetch alert (tenant-isolated)
    alert = AlertEngine.get_alert(db, alert_id, current_user.org_id)
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    # 4. Attempt transition
    try:
        AlertEngine.transition(
            alert=alert,
            to_status=to_status,
            user_id=current_user.id,
            db=db,
            reason=body.reason,
        )
        db.commit()
        db.refresh(alert)
    except InvalidTransitionError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from None

    log.info(
        "alert_status_api",
        alert_id=alert_id,
        to_status=to_status.value,
        user_id=current_user.id,
    )

    return AlertDetailResponse(
        **AlertResponse.model_validate(alert).model_dump(),
        states=[AlertStateResponse.model_validate(s) for s in alert.states],
    )
