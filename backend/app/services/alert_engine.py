"""
SafeVision AI — Alert Engine (Phase 7B)

Responsibilities:
  1. Create alerts from RiskAssessments (risk → alert boundary)
  2. Enforce valid lifecycle transitions
  3. Record every transition in alert_states (audit trail)
  4. Enforce tenant isolation (org_id)
  5. Provide atomic status + audit updates

Does NOT:
  - Recalculate risk (uses Phase 7A RiskAssessment as-is)
  - Send notifications (future phase)
  - Invoke LLM/RAG (future phase)
  - Modify frontend (separate phase)

Lifecycle:
  NEW → ACKNOWLEDGED → ESCALATED → RESOLVED
  Plus: ACKNOWLEDGED → RESOLVED (direct resolve shortcut)
        NEW → ESCALATED (emergency escalation)
  All other transitions are rejected with HTTP 409.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy.orm import Session

from app.models.alert import Alert, AlertSeverity, AlertState, AlertStatus
from app.models.event import Event
from app.schemas.risk import RiskAssessment

log = structlog.get_logger()


# ==============================================================================
# Valid Lifecycle Transitions
# ==============================================================================

# Explicit set of allowed (from_status → to_status) transitions.
# Any transition NOT in this set is rejected.
VALID_TRANSITIONS: dict[AlertStatus, set[AlertStatus]] = {
    AlertStatus.NEW: {
        AlertStatus.ACKNOWLEDGED,
        AlertStatus.ESCALATED,       # Emergency escalation shortcut
    },
    AlertStatus.ACKNOWLEDGED: {
        AlertStatus.ESCALATED,
        AlertStatus.RESOLVED,        # Direct resolve shortcut
    },
    AlertStatus.ESCALATED: {
        AlertStatus.RESOLVED,
    },
    # Terminal states — no outgoing transitions
    AlertStatus.RESOLVED: set(),
    AlertStatus.CLOSED: set(),
    AlertStatus.FALSE_POSITIVE: set(),
    AlertStatus.INVESTIGATING: {
        AlertStatus.ESCALATED,
        AlertStatus.RESOLVED,
    },
}


# Map lifecycle transitions to required permissions
TRANSITION_PERMISSIONS: dict[AlertStatus, str] = {
    AlertStatus.ACKNOWLEDGED: "alerts.acknowledge",
    AlertStatus.ESCALATED: "alerts.escalate",
    AlertStatus.RESOLVED: "alerts.resolve",
}


# ==============================================================================
# Alert Engine
# ==============================================================================

class AlertEngine:
    """
    Alert creation and lifecycle management engine.

    Stateless — all state is persisted in PostgreSQL via the Session.
    """

    # ------------------------------------------------------------------
    # Alert Creation
    # ------------------------------------------------------------------

    @staticmethod
    def create_alert_from_risk(
        risk: RiskAssessment,
        db: Session,
        event: Event | None = None,
        rule_id: str | None = None,
        title: str | None = None,
        description: str | None = None,
        created_by_user_id: str | None = None,
    ) -> Alert:
        """
        Create a new alert from a RiskAssessment.

        Uses the risk level as alert severity. Links to the originating event.
        Creates the initial audit trail (→ NEW).

        Args:
            risk: Phase 7A RiskAssessment result.
            db: SQLAlchemy session (transaction handled by caller).
            event: Optional Event ORM object (for relationship link).
            rule_id: Optional safety rule ID that triggered this.
            title: Alert title. Auto-generated if None.
            description: Alert description. Auto-generated if None.
            created_by_user_id: User ID who triggered creation (None for system).

        Returns:
            The newly created Alert ORM object (flushed, not committed).
        """
        # Map risk_level string to AlertSeverity enum
        severity = _risk_level_to_severity(risk.risk_level)

        # Auto-generate title/description from risk context
        if title is None:
            title = _generate_title(risk)
        if description is None:
            description = risk.explanation

        alert_id = str(uuid.uuid4())

        # Synchronize evidence_path from event if available
        evidence_path = None
        if event and hasattr(event, "evidence_path") and event.evidence_path:
            evidence_path = event.evidence_path
        elif risk.event_id:
            ev = db.query(Event).filter(Event.id == risk.event_id).first()
            if ev and ev.evidence_path:
                evidence_path = ev.evidence_path

        alert = Alert(
            id=alert_id,
            event_id=risk.event_id,
            rule_id=rule_id,
            org_id=risk.org_id,
            title=title,
            description=description,
            severity=severity,
            status=AlertStatus.NEW,
            evidence_path=evidence_path,
            metadata_json={
                "risk_score": risk.risk_score,
                "risk_level": risk.risk_level,
                "event_type": risk.event_type,
                "camera_id": risk.camera_id,
                "factors": [f.model_dump() for f in risk.factors],
            },
        )
        db.add(alert)
        db.flush()  # Get the ID assigned

        # Create initial audit state (None → NEW)
        initial_state = AlertState(
            id=str(uuid.uuid4()),
            alert_id=alert_id,
            from_status=None,
            to_status=AlertStatus.NEW.value,
            changed_by=created_by_user_id,
            reason="Alert created from risk assessment",
            metadata_json={"risk_score": risk.risk_score},
        )
        db.add(initial_state)
        db.flush()

        log.info(
            "alert_created",
            alert_id=alert_id,
            severity=severity.value,
            event_id=risk.event_id,
            org_id=risk.org_id,
            risk_score=risk.risk_score,
        )

        return alert

    # ------------------------------------------------------------------
    # Lifecycle Transitions
    # ------------------------------------------------------------------

    @staticmethod
    def transition(
        alert: Alert,
        to_status: AlertStatus,
        user_id: str,
        db: Session,
        reason: str | None = None,
    ) -> AlertState:
        """
        Transition an alert to a new lifecycle status.

        ATOMIC: Alert status update + audit row are flushed together.
        Caller is responsible for commit/rollback.

        Args:
            alert: The Alert ORM object to transition.
            to_status: Target AlertStatus.
            user_id: Acting user's ID (for audit).
            db: SQLAlchemy session.
            reason: Optional transition reason.

        Returns:
            The new AlertState audit record.

        Raises:
            InvalidTransitionError: If the transition is not allowed.
        """
        from_status = AlertStatus(alert.status) if isinstance(alert.status, str) else alert.status

        # Validate transition
        allowed = VALID_TRANSITIONS.get(from_status, set())
        if to_status not in allowed:
            raise InvalidTransitionError(
                from_status=from_status.value,
                to_status=to_status.value,
            )

        # Update alert status
        alert.status = to_status
        alert.updated_at = datetime.now(timezone.utc)

        if to_status == AlertStatus.RESOLVED:
            alert.resolved_at = datetime.now(timezone.utc)

        # Create audit record
        state = AlertState(
            id=str(uuid.uuid4()),
            alert_id=alert.id,
            from_status=from_status.value,
            to_status=to_status.value,
            changed_by=user_id,
            reason=reason,
        )
        db.add(state)
        db.flush()

        log.info(
            "alert_transitioned",
            alert_id=alert.id,
            from_status=from_status.value,
            to_status=to_status.value,
            changed_by=user_id,
        )

        return state

    # ------------------------------------------------------------------
    # Query Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def get_alert(db: Session, alert_id: str, org_id: str) -> Alert | None:
        """
        Fetch an alert by ID, scoped by org_id for tenant isolation.

        Returns None if the alert doesn't exist OR belongs to a different org.
        """
        return db.query(Alert).filter(
            Alert.id == alert_id,
            Alert.org_id == org_id,  # TENANT ISOLATION
        ).first()

    @staticmethod
    def list_alerts(
        db: Session,
        org_id: str,
        page: int = 1,
        size: int = 50,
        severity: str | None = None,
        status: str | None = None,
    ) -> tuple[list[Alert], int]:
        """
        List alerts for an organization with optional filters and pagination.

        Returns (alerts_list, total_count).
        """
        query = db.query(Alert).filter(Alert.org_id == org_id)

        if severity is not None:
            query = query.filter(Alert.severity == severity)
        if status is not None:
            query = query.filter(Alert.status == status)

        total = query.count()
        offset = (page - 1) * size
        alerts = (
            query
            .order_by(Alert.created_at.desc())
            .offset(offset)
            .limit(size)
            .all()
        )

        return alerts, total

    @staticmethod
    def get_required_permission(to_status: AlertStatus) -> str | None:
        """Return the permission name required for a transition to to_status."""
        return TRANSITION_PERMISSIONS.get(to_status)


# ==============================================================================
# Exceptions
# ==============================================================================

class InvalidTransitionError(Exception):
    """Raised when an alert lifecycle transition is not allowed."""

    def __init__(self, from_status: str, to_status: str):
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(
            f"Invalid transition: {from_status} → {to_status}",
        )


# ==============================================================================
# Internal Helpers
# ==============================================================================

_EVENT_TYPE_LABELS: dict[str, str] = {
    "ppe_detection": "PPE Violation",
    "fire_smoke": "Fire/Smoke",
    "zone_intrusion": "Zone Intrusion",
    "person_detected": "Person Detected",
    "tracking_update": "Tracking Update",
}


def _generate_title(risk: RiskAssessment) -> str:
    """Auto-generate a human-readable alert title from risk context."""
    event_label = _EVENT_TYPE_LABELS.get(risk.event_type, risk.event_type)
    level = risk.risk_level.upper()
    return f"{level}: {event_label} Detected"


def _risk_level_to_severity(risk_level: str) -> AlertSeverity:
    """Map a risk_level string to an AlertSeverity enum."""
    try:
        return AlertSeverity(risk_level)
    except ValueError:
        log.warning("unknown_risk_level", risk_level=risk_level)
        return AlertSeverity.MEDIUM
