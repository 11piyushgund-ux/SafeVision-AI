"""
SafeVision AI — Notifications API Routes (Phase 15)

Endpoints:
  GET  /api/notifications                — list org-scoped notifications (paginated)
  GET  /api/notifications/{id}           — single notification detail
  GET  /api/notifications/settings       — get org notification settings
  POST /api/notifications/settings       — save org notification settings

All endpoints:
  - Require authentication (JWT Bearer)
  - Enforce tenant isolation (org_id from authenticated user — never from request body)
  - Require notifications.view or notifications.manage permission as appropriate
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user, require_permission
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification_schema import (
    NotificationListResponse,
    NotificationResponse,
    OrgNotificationSettingsResponse,
    OrgNotificationSettingsUpdate,
)
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])
log = structlog.get_logger()


# ==============================================================================
# GET /api/notifications/settings — Read Org Notification Settings
# ==============================================================================

@router.get(
    "/settings",
    response_model=OrgNotificationSettingsResponse,
    summary="Get Org Notification Settings",
    description=(
        "Get the notification settings for the current organization. "
        "Requires notifications.view permission."
    ),
)
def get_notification_settings(
    current_user: User = Depends(require_permission("notifications.view")),
    db: Session = Depends(get_db),
):
    """Retrieve current org notification configuration."""
    settings = NotificationService.get_org_settings(db, current_user.org_id)
    if settings is None:
        # Return a sensible default when settings have never been saved
        from app.models.org_notification_settings import OrgNotificationSettings, NotificationMode
        from datetime import datetime, timezone
        # Build a synthetic response (not persisted)
        return OrgNotificationSettingsResponse(
            id="",
            org_id=current_user.org_id,
            notifications_enabled=False,
            notification_mode=NotificationMode.EMAIL.value,
            email_recipient=None,
            whatsapp_recipient=None,
            notification_recipient=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    return OrgNotificationSettingsResponse.model_validate(settings)


# ==============================================================================
# POST /api/notifications/settings — Save Org Notification Settings
# ==============================================================================

@router.post(
    "/settings",
    response_model=OrgNotificationSettingsResponse,
    summary="Save Org Notification Settings",
    description=(
        "Create or update notification settings for the current organization. "
        "Requires notifications.manage permission."
    ),
)
def save_notification_settings(
    body: OrgNotificationSettingsUpdate,
    current_user: User = Depends(require_permission("notifications.manage")),
    db: Session = Depends(get_db),
):
    """Persist notification settings for the authenticated user's organization."""
    settings = NotificationService.upsert_org_settings(
        db=db,
        org_id=current_user.org_id,
        notifications_enabled=body.notifications_enabled,
        notification_mode=body.notification_mode,
        email_recipient=body.email_recipient,
        whatsapp_recipient=body.whatsapp_recipient,
        notification_recipient=body.notification_recipient,
    )

    log.info(
        "notification_settings_updated",
        org_id=current_user.org_id,
        mode=body.notification_mode,
        enabled=body.notifications_enabled,
        updated_by=current_user.id,
    )

    return OrgNotificationSettingsResponse.model_validate(settings)


# ==============================================================================
# GET /api/notifications — List Notifications
# ==============================================================================

@router.get(
    "",
    response_model=NotificationListResponse,
    summary="List Notifications",
    description=(
        "List notifications for the current organization. "
        "Paginated and filterable. Requires notifications.view permission."
    ),
)
def list_notifications(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=100, description="Page size"),
    alert_id: str | None = Query(None, description="Filter by alert ID"),
    channel: str | None = Query(None, description="Filter by channel (email, whatsapp, ...)"),
    notification_status: str | None = Query(None, alias="status", description="Filter by status"),
    current_user: User = Depends(require_permission("notifications.view")),
    db: Session = Depends(get_db),
):
    """List notifications for the authenticated user's organization."""
    query = db.query(Notification).filter(
        Notification.org_id == current_user.org_id,  # TENANT ISOLATION
    )

    if alert_id:
        query = query.filter(Notification.alert_id == alert_id)
    if channel:
        query = query.filter(Notification.channel == channel)
    if notification_status:
        query = query.filter(Notification.status == notification_status)

    total = query.count()
    notifications = (
        query.order_by(Notification.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )

    log.info(
        "notifications_listed",
        org_id=current_user.org_id,
        total=total,
        page=page,
    )

    return NotificationListResponse(
        data=[NotificationResponse.model_validate(n) for n in notifications],
        total=total,
        page=page,
        size=size,
    )


# ==============================================================================
# GET /api/notifications/{notification_id} — Single Notification
# ==============================================================================

@router.get(
    "/{notification_id}",
    response_model=NotificationResponse,
    summary="Get Notification",
    description=(
        "Get a single notification by ID. "
        "Tenant-isolated. Requires notifications.view permission."
    ),
)
def get_notification(
    notification_id: str,
    current_user: User = Depends(require_permission("notifications.view")),
    db: Session = Depends(get_db),
):
    """Retrieve a single notification by ID — only if it belongs to the user's org."""
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.org_id == current_user.org_id,  # TENANT ISOLATION
        )
        .first()
    )
    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    return NotificationResponse.model_validate(notification)
