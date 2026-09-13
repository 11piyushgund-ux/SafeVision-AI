"""
SafeVision AI — Notification Service (Phase 15)

Orchestrates the full notification lifecycle:
  1. Read OrgNotificationSettings for the alert's organization.
  2. Guard: disabled or unconfigured → skip silently.
  3. Duplicate guard: don't re-send if a notification already exists for this alert.
  4. Build message from real alert/event data (camera name, zone, event type, etc.).
  5. Create Notification row with status=PENDING.
  6. Invoke the selected provider (Email or WhatsApp).
  7. Update status → SENT or FAILED.
  8. Commit.

Failure isolation guarantee:
  dispatch() NEVER raises.  Any provider exception is caught, logged, and
  persisted as status=FAILED.  The caller's alert/event transaction is
  completely unaffected — the Alert commit has already happened before
  dispatch() is ever called.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog
from sqlalchemy.orm import Session

from app.models.camera import Camera
from app.models.notification import Notification, NotificationChannel, NotificationStatus
from app.models.org_notification_settings import NotificationMode, OrgNotificationSettings
from app.models.zone import Zone
from app.services.notifications.base_provider import ProviderError
from app.services.notifications.email_provider import EmailProvider
from app.services.notifications.whatsapp_provider import WhatsAppProvider

if TYPE_CHECKING:
    from app.models.alert import Alert
    from app.models.event import Event

log = structlog.get_logger()


# ==============================================================================
# Message Builder
# ==============================================================================

def _build_message(
    alert: "Alert",
    event: "Event | None",
    db: Session,
) -> tuple[str, str]:
    """
    Build (subject, body) from real alert/event data.

    Performs minimal DB lookups to resolve camera and zone names.
    Never uses hardcoded location names.
    """
    # --- Resolve event metadata ---
    event_type_raw = ""
    confidence_pct = ""
    camera_name = ""
    zone_name = ""
    missing_ppe_info = ""
    event_id_display = ""
    event_timestamp = ""

    # Prefer direct event object; fall back to alert metadata
    if event is not None:
        event_type_raw = (
            event.event_type.value
            if hasattr(event.event_type, "value")
            else str(event.event_type)
        )
        if event.confidence is not None:
            confidence_pct = f"{event.confidence * 100:.0f}%"
        event_id_display = event.id[:8]  # Short ID for readability
        event_timestamp = (
            event.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
            if event.timestamp
            else ""
        )

        # Resolve camera name
        if event.camera_id:
            cam = db.query(Camera).filter(Camera.id == event.camera_id).first()
            if cam:
                camera_name = cam.name
                if cam.zone_id:
                    zone = db.query(Zone).filter(Zone.id == cam.zone_id).first()
                    if zone:
                        zone_name = zone.name

        # Extract missing PPE from detection_data
        det = event.detection_data or {}
        mp = det.get("missing_ppe")
        if isinstance(mp, list) and mp:
            missing_ppe_info = ", ".join(str(p) for p in mp)

    else:
        # Fall back to alert.metadata_json when event is not passed
        meta = alert.metadata_json or {}
        event_type_raw = meta.get("event_type", "")
        event_timestamp = (
            alert.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
            if alert.created_at
            else ""
        )

    # Resolve from alert.metadata_json if event lookup didn't populate camera
    if not camera_name:
        meta = alert.metadata_json or {}
        cam_id = meta.get("camera_id")
        if cam_id:
            cam = db.query(Camera).filter(Camera.id == cam_id).first()
            if cam:
                camera_name = cam.name
                if cam.zone_id:
                    zone = db.query(Zone).filter(Zone.id == cam.zone_id).first()
                    if zone:
                        zone_name = zone.name

    # Format readable event type label
    event_label = event_type_raw.replace("_", " ").title() if event_type_raw else "Safety Event"

    # Risk metadata from alert
    meta = alert.metadata_json or {}
    risk_score = meta.get("risk_score")
    risk_level = meta.get("risk_level") or alert.severity
    risk_display = f"{risk_level.upper()}" + (
        f" ({risk_score:.2f})" if risk_score is not None else ""
    )

    # --- Build subject ---
    location_hint = f" — {zone_name or camera_name}" if (zone_name or camera_name) else ""
    subject = f"[SafeVision] {alert.severity.upper()} Alert: {event_label}{location_hint}"

    # --- Build plain-text body ---
    lines: list[str] = [
        "═══════════════════════════════════",
        "  SafeVision AI — Safety Alert",
        "═══════════════════════════════════",
        "",
        f"Alert ID   : {alert.id}",
        f"Event Type : {event_label}",
        f"Risk Level : {risk_display}",
        f"Status     : {alert.status.upper() if isinstance(alert.status, str) else alert.status}",
    ]

    if event_id_display:
        lines.append(f"Event ID   : {event_id_display}...")
    if confidence_pct:
        lines.append(f"Confidence : {confidence_pct}")
    if camera_name:
        lines.append(f"Camera     : {camera_name}")
    if zone_name:
        lines.append(f"Zone       : {zone_name}")
    if event_timestamp:
        lines.append(f"Time       : {event_timestamp}")
    if missing_ppe_info:
        lines.append(f"Missing PPE: {missing_ppe_info}")

    lines += [
        "",
        "Description:",
        alert.description or alert.title,
        "",
        "═══════════════════════════════════",
        "Please log in to SafeVision AI to",
        "review and take action on this alert.",
        "═══════════════════════════════════",
    ]

    body = "\n".join(lines)
    return subject, body


def _build_whatsapp_body(
    alert: "Alert",
    event: "Event | None",
    db: Session,
) -> str:
    """
    Build a structured, text-only WhatsApp message body.
    Format adheres strictly to the Phase 17 product specification:

    SafeVision AI — Safety Alert

    Alert ID: <full alert id>
    Event: <event type>
    Risk: <LEVEL> (<score>)
    Status: <status>
    Camera: <camera name>
    Zone: <zone name>
    Time: <UTC timestamp>

    Description:
    <description / risk explanation>

    Please log in to SafeVision AI to review and take action.
    """
    meta = alert.metadata_json or {}

    # Event label
    event_type_raw = ""
    if event is not None:
        event_type_raw = (
            event.event_type.value
            if hasattr(event.event_type, "value")
            else str(event.event_type)
        )
    else:
        event_type_raw = meta.get("event_type", "")

    event_label = event_type_raw.replace("_", " ").title() if event_type_raw else "Safety Event"

    # Risk level + score
    risk_score = meta.get("risk_score")
    risk_level = (meta.get("risk_level") or alert.severity or "UNKNOWN").upper()
    if risk_score is not None:
        try:
            risk_display = f"{risk_level} ({float(risk_score):.2f})"
        except (ValueError, TypeError):
            risk_display = f"{risk_level} ({risk_score})"
    else:
        risk_display = risk_level

    # Status
    status_val = (
        alert.status.value
        if hasattr(alert.status, "value")
        else str(alert.status or "NEW")
    ).upper()

    # Camera & Zone
    camera_name = ""
    zone_name = ""
    cam_id = (event.camera_id if event else None) or meta.get("camera_id")
    if cam_id:
        cam = db.query(Camera).filter(Camera.id == cam_id).first()
        if cam:
            camera_name = cam.name
            if cam.zone_id:
                zone = db.query(Zone).filter(Zone.id == cam.zone_id).first()
                if zone:
                    zone_name = zone.name

    if not camera_name and meta.get("camera_name"):
        camera_name = meta.get("camera_name")
    if not zone_name and meta.get("zone_name"):
        zone_name = meta.get("zone_name")

    # Timestamp
    if alert.created_at:
        timestamp_display = alert.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    elif event and event.timestamp:
        timestamp_display = event.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
    else:
        timestamp_display = "N/A"

    # Description / explanation
    description = alert.description or alert.title or "Safety event detected."

    lines = [
        "SafeVision AI — Safety Alert",
        "",
        f"Alert ID: {alert.id}",
        f"Event: {event_label}",
        f"Risk: {risk_display}",
        f"Status: {status_val}",
        f"Camera: {camera_name or 'N/A'}",
        f"Zone: {zone_name or 'N/A'}",
        f"Time: {timestamp_display}",
        "",
        "Description:",
        description,
        "",
        "Please log in to SafeVision AI to review and take action.",
    ]

    return "\n".join(lines)


# ==============================================================================
# Notification Service
# ==============================================================================

_UNSET = object()


class NotificationService:
    """
    Stateless notification dispatch service.

    Call dispatch() after an alert has been committed to the database.
    All exceptions are caught internally — dispatch() never propagates.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def dispatch(
        alert: "Alert",
        db: Session,
        event: "Event | None" = None,
    ) -> Notification | None:
        """
        Attempt to send a notification for a newly created alert.

        This method is guaranteed not to raise.  All failures are:
          1. Logged at WARNING level.
          2. Persisted as Notification.status = FAILED.
          3. Never allowed to propagate to the caller.

        Args:
            alert: The just-committed Alert ORM object.
            db:    The active SQLAlchemy session.
            event: The originating Event (optional — used for richer messages).

        Returns:
            The Notification ORM object (SENT or FAILED), or None if notifications
            are disabled / not configured for this organization.
        """
        alert_id = getattr(alert, "id", "unknown")
        org_id = getattr(alert, "org_id", "unknown")
        try:
            return NotificationService._dispatch_inner(alert=alert, db=db, event=event)
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            log.exception(
                "notification_dispatch_unexpected_failure",
                alert_id=alert_id,
                org_id=org_id,
            )
            return None

    # ------------------------------------------------------------------
    # Internal Implementation
    # ------------------------------------------------------------------

    @staticmethod
    def _dispatch_inner(
        alert: "Alert",
        db: Session,
        event: "Event | None",
    ) -> Notification | None:
        """Core dispatch logic — may raise; wrapped by dispatch()."""

        # 1. Load org notification settings
        org_settings = (
            db.query(OrgNotificationSettings)
            .filter(OrgNotificationSettings.org_id == alert.org_id)
            .first()
        )

        if org_settings is None:
            log.debug(
                "notification_skipped_no_settings",
                alert_id=alert.id,
                org_id=alert.org_id,
            )
            return None

        if not org_settings.notifications_enabled:
            log.debug(
                "notification_skipped_disabled",
                alert_id=alert.id,
                org_id=alert.org_id,
            )
            return None

        # 2. Duplicate guard — prevent sending twice for the same alert + channel
        mode_value = (
            org_settings.notification_mode.value
            if hasattr(org_settings.notification_mode, "value")
            else str(org_settings.notification_mode)
        )

        # 3. Resolve target recipient strictly by active mode (Phase 18 Dual Channel)
        target_recipient: str | None = None
        email_rec = getattr(org_settings, "email_recipient", None)
        wa_rec = getattr(org_settings, "whatsapp_recipient", None)
        legacy_rec = getattr(org_settings, "notification_recipient", None)

        if mode_value == NotificationMode.EMAIL.value:
            if isinstance(email_rec, str) and email_rec.strip() and "@" in email_rec:
                target_recipient = email_rec.strip()
            elif isinstance(legacy_rec, str) and legacy_rec.strip() and "@" in legacy_rec:
                target_recipient = legacy_rec.strip()
        elif mode_value == NotificationMode.WHATSAPP.value:
            if isinstance(wa_rec, str) and wa_rec.strip() and "@" not in wa_rec:
                target_recipient = wa_rec.strip()
            elif isinstance(legacy_rec, str) and legacy_rec.strip() and "@" not in legacy_rec:
                target_recipient = legacy_rec.strip()

        if not target_recipient:
            log.warning(
                "notification_skipped_no_recipient",
                alert_id=alert.id,
                org_id=alert.org_id,
                mode=mode_value,
            )
            return None

        existing = (
            db.query(Notification)
            .filter(
                Notification.alert_id == alert.id,
                Notification.channel == mode_value,
            )
            .first()
        )
        if existing is not None:
            log.debug(
                "notification_skipped_duplicate",
                alert_id=alert.id,
                existing_notification_id=existing.id,
                channel=mode_value,
            )
            return existing

        # 4. Determine channel enum
        channel_enum = _mode_to_channel(mode_value)

        # 5. Build message
        if mode_value == NotificationMode.WHATSAPP.value:
            body = _build_whatsapp_body(alert, event, db)
            subject = None
        else:
            subject, body = _build_message(alert, event, db)

        # 6. Create PENDING Notification record
        event_id = event.id if event is not None else alert.event_id
        notification = Notification(
            id=str(uuid.uuid4()),
            alert_id=alert.id,
            event_id=event_id,
            org_id=alert.org_id,
            recipient_address=target_recipient,
            channel=channel_enum,
            status=NotificationStatus.PENDING,
            subject=subject,
            body=body,
        )
        db.add(notification)
        db.flush()  # Obtain ID without committing

        log.info(
            "notification_pending",
            notification_id=notification.id,
            alert_id=alert.id,
            channel=mode_value,
            recipient=target_recipient,
        )

        # Resolve authoritative evidence image if present (Email only — WhatsApp is text-only)
        attachment_bytes: bytes | None = None
        attachment_filename: str | None = None
        if mode_value == NotificationMode.EMAIL.value:
            evidence_rel_path = getattr(alert, "evidence_path", None)
            if not evidence_rel_path and event is not None:
                evidence_rel_path = getattr(event, "evidence_path", None)
            if not evidence_rel_path and getattr(alert, "event_id", None):
                try:
                    from app.models.event import Event
                    ev = db.query(Event).filter(Event.id == alert.event_id).first()
                    if ev and ev.evidence_path:
                        evidence_rel_path = ev.evidence_path
                except Exception:
                    pass

            if evidence_rel_path:
                try:
                    from app.services.evidence_service import EvidenceService
                    file_path = EvidenceService.resolve_evidence_path(evidence_rel_path, alert.org_id)
                    if file_path and file_path.is_file():
                        with open(file_path, "rb") as f:
                            attachment_bytes = f.read()
                        attachment_filename = "evidence.jpg"
                        log.info(
                            "notification_evidence_attached",
                            alert_id=alert.id,
                            evidence_path=evidence_rel_path,
                            bytes_len=len(attachment_bytes),
                        )
                except Exception as e:
                    log.warning(
                        "notification_evidence_load_failed",
                        alert_id=alert.id,
                        evidence_path=evidence_rel_path,
                        error=str(e),
                    )

        # 7. Select and invoke provider
        try:
            provider = _get_provider(mode_value)
            result = provider.send(
                recipient=target_recipient,
                subject=subject,
                body=body,
                attachment_bytes=attachment_bytes,
                attachment_filename=attachment_filename,
            )

            # 7. Mark SENT
            notification.status = NotificationStatus.SENT
            notification.sent_at = datetime.now(timezone.utc)
            # Strip any accidentally included sensitive keys before storing
            notification.provider_response = _sanitize_provider_response(result)
            db.commit()

            log.info(
                "notification_sent",
                notification_id=notification.id,
                alert_id=alert.id,
                channel=mode_value,
                provider=provider.provider_name,
            )

        except ProviderError as exc:
            # 8. Mark FAILED — persist error info safely
            notification.status = NotificationStatus.FAILED
            notification.retry_count = (notification.retry_count or 0) + 1
            notification.provider_response = {
                "error": exc.reason,
                "provider": exc.provider,
                "failed_at": datetime.now(timezone.utc).isoformat(),
            }
            db.commit()

            log.warning(
                "notification_failed",
                notification_id=notification.id,
                alert_id=alert.id,
                channel=mode_value,
                reason=exc.reason,
                provider=exc.provider,
            )

        return notification

    # ------------------------------------------------------------------
    # Settings Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def get_org_settings(db: Session, org_id: str) -> OrgNotificationSettings | None:
        """Retrieve notification settings for an organization."""
        return (
            db.query(OrgNotificationSettings)
            .filter(OrgNotificationSettings.org_id == org_id)
            .first()
        )

    @staticmethod
    def upsert_org_settings(
        db: Session,
        org_id: str,
        notifications_enabled: bool,
        notification_mode: str,
        email_recipient: str | None | object = _UNSET,
        whatsapp_recipient: str | None | object = _UNSET,
        notification_recipient: str | None = None,
    ) -> OrgNotificationSettings:
        """
        Create or update notification settings for an organization.

        This is the authoritative write path used by the API endpoint.
        Maintains independent email_recipient and whatsapp_recipient while
        keeping legacy notification_recipient synchronized to the active mode.
        """
        settings = (
            db.query(OrgNotificationSettings)
            .filter(OrgNotificationSettings.org_id == org_id)
            .first()
        )

        if settings is None:
            settings = OrgNotificationSettings(
                id=str(uuid.uuid4()),
                org_id=org_id,
            )
            db.add(settings)

        settings.notifications_enabled = notifications_enabled
        # Normalize to NotificationMode enum member so SQLAlchemy persists
        # the correct lowercase value expected by the PostgreSQL enum type.
        mode_enum = NotificationMode(notification_mode.lower())
        settings.notification_mode = mode_enum  # type: ignore[assignment]

        # 1. Process Email recipient
        if email_recipient is not _UNSET:
            clean_email = email_recipient.strip() if isinstance(email_recipient, str) and email_recipient.strip() else None
            settings.email_recipient = clean_email
        elif notification_recipient and "@" in notification_recipient:
            # Fallback from legacy notification_recipient
            settings.email_recipient = notification_recipient.strip()

        # 2. Process WhatsApp recipient with normalization
        if whatsapp_recipient is not _UNSET:
            if isinstance(whatsapp_recipient, str) and whatsapp_recipient.strip():
                clean_wa = WhatsAppProvider._normalize_recipient(whatsapp_recipient.strip())
                if clean_wa.startswith("whatsapp:"):
                    clean_wa = clean_wa[len("whatsapp:"):]
                settings.whatsapp_recipient = clean_wa
            else:
                settings.whatsapp_recipient = None
        elif notification_recipient and "@" not in notification_recipient:
            # Fallback from legacy notification_recipient
            clean_wa = WhatsAppProvider._normalize_recipient(notification_recipient.strip())
            if clean_wa.startswith("whatsapp:"):
                clean_wa = clean_wa[len("whatsapp:"):]
            settings.whatsapp_recipient = clean_wa

        # 3. Synchronize legacy notification_recipient to the active mode
        if mode_enum == NotificationMode.EMAIL:
            settings.notification_recipient = getattr(settings, "email_recipient", None)
        else:
            settings.notification_recipient = getattr(settings, "whatsapp_recipient", None)

        settings.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(settings)
        return settings


# ==============================================================================
# Private Helpers
# ==============================================================================

def _mode_to_channel(mode: str) -> str:
    """Map notification_mode string to NotificationChannel enum value."""
    mapping = {
        NotificationMode.EMAIL.value: NotificationChannel.EMAIL.value,
        NotificationMode.WHATSAPP.value: NotificationChannel.WHATSAPP.value,
    }
    return mapping.get(mode, NotificationChannel.EMAIL.value)


def _get_provider(mode: str) -> "EmailProvider | WhatsAppProvider":
    """Instantiate the correct provider for the given mode."""
    if mode == NotificationMode.WHATSAPP.value:
        return WhatsAppProvider()
    if mode == NotificationMode.EMAIL.value:
        return EmailProvider()
    raise ProviderError(
        f"Unsupported notification mode: '{mode}'",
        provider="notification_service",
    )


_SENSITIVE_KEYS = frozenset({
    "auth_token", "password", "secret", "token", "api_key",
    "twilio_auth_token", "smtp_password", "authorization",
})


def _sanitize_provider_response(response: dict) -> dict:
    """
    Remove any accidentally included sensitive keys from provider_response
    before storing in the database.
    """
    return {
        k: v
        for k, v in response.items()
        if k.lower() not in _SENSITIVE_KEYS
    }
