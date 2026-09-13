"""
SafeVision AI — Alert Engine & Lifecycle Tests (Phase 7B)

Coverage:
  ALERT CREATION (1–3)
  VALID LIFECYCLE (4–7)
  INVALID LIFECYCLE (8–10)
  PERMISSIONS (11–14)
  AUDIT (15–19)
  TENANT ISOLATION (20–22)
  CONCURRENCY / INTEGRITY (23–24)

Uses real test database with two isolated organizations.
Follows existing test patterns from test_auth_rbac_idor.py.
"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.database import get_db
from app.main import app
from app.models.alert import AlertSeverity, AlertState, AlertStatus
from app.models.camera import Camera
from app.models.event import Event, EventType
from app.models.organization import Organization
from app.models.role import Permission, Role
from app.models.site import Site
from app.models.user import User
from app.schemas.risk import RiskAssessment, RiskFactor
from app.services.alert_engine import (
    AlertEngine,
    InvalidTransitionError,
)
from app.services.auth_service import create_access_token, hash_password

# ==============================================================================
# Test Database Setup (follows existing test_auth_rbac_idor.py pattern)
# ==============================================================================

settings = get_settings()
test_engine = create_engine(settings.database_url, echo=False)
TestSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


def _override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db
client = TestClient(app)


# ==============================================================================
# Test Data Helpers
# ==============================================================================

def _create_org(db: Session, name: str, slug: str) -> Organization:
    org = Organization(id=str(uuid.uuid4()), name=name, slug=slug)
    db.add(org)
    db.flush()
    return org


def _create_role(db: Session, org_id: str, name: str, permissions: list[str]) -> Role:
    role = Role(id=str(uuid.uuid4()), name=name, org_id=org_id)
    db.add(role)
    db.flush()
    for perm_name in permissions:
        perm = Permission(id=str(uuid.uuid4()), role_id=role.id, perm_name=perm_name)
        db.add(perm)
    db.flush()
    return role


def _create_user(
    db: Session, org_id: str, role_id: str, email: str,
    name: str = "Test User", password: str = "testpassword123",
) -> User:
    user = User(
        id=str(uuid.uuid4()), org_id=org_id, email=email,
        name=name, pwd_hash=hash_password(password), role_id=role_id,
    )
    db.add(user)
    db.flush()
    return user


def _create_site(db: Session, org_id: str) -> Site:
    """Create a test site for the given org."""
    site = Site(
        id=str(uuid.uuid4()),
        org_id=org_id,
        name=f"Test Site {uuid.uuid4().hex[:6]}",
    )
    db.add(site)
    db.flush()
    return site


def _create_camera(db: Session, org_id: str, site_id: str) -> Camera:
    """Create a test camera for the given site."""
    camera = Camera(
        id=str(uuid.uuid4()),
        site_id=site_id,
        org_id=org_id,
        name=f"Test Camera {uuid.uuid4().hex[:6]}",
    )
    db.add(camera)
    db.flush()
    return camera


def _create_event(db: Session, org_id: str, camera_id: str) -> Event:
    """Create a test event with an existing camera."""
    event = Event(
        id=str(uuid.uuid4()),
        camera_id=camera_id,
        org_id=org_id,
        event_type=EventType.PPE_DETECTION,
        confidence=0.90,
    )
    db.add(event)
    db.flush()
    return event


def _make_risk_assessment(
    event_id: str = "evt-test",
    org_id: str = "org-test",
    risk_score: float = 0.65,
    risk_level: str = "high",
    event_type: str = "ppe_detection",
) -> RiskAssessment:
    """Create a RiskAssessment for testing."""
    from datetime import datetime, timezone
    return RiskAssessment(
        risk_score=risk_score,
        risk_level=risk_level,
        factors=[
            RiskFactor(
                name="event_type", raw_value=event_type,
                score=0.65, weight=0.35, weighted_score=0.2275,
                explanation="PPE Violation",
            ),
            RiskFactor(
                name="zone_criticality", raw_value=None,
                score=0.4, weight=0.25, weighted_score=0.1,
                explanation="Default zone",
            ),
            RiskFactor(
                name="confidence", raw_value=0.9,
                score=0.9, weight=0.15, weighted_score=0.135,
                explanation="Detection confidence 0.90",
            ),
            RiskFactor(
                name="recurrence", raw_value=3,
                score=0.3, weight=0.25, weighted_score=0.075,
                explanation="3 prior events",
            ),
        ],
        explanation="Risk assessment: HIGH",
        event_id=event_id,
        event_type=event_type,
        camera_id="cam-01",
        org_id=org_id,
        assessed_at=datetime.now(timezone.utc),
    )


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _get_token(user_id: str, org_id: str, role_name: str = "Admin") -> str:
    return create_access_token(user_id=user_id, org_id=org_id, role_name=role_name)


# ==============================================================================
# Fixture: Two Isolated Organizations with alerts
# ==============================================================================

_test_data: dict = {}


def _setup_test_data():
    if _test_data:
        return

    db = TestSession()
    try:
        # --- ORG A ---
        org_a = _create_org(db, f"Alert Org A {uuid.uuid4().hex[:6]}", f"alert-a-{uuid.uuid4().hex[:6]}")

        admin_role_a = _create_role(db, org_a.id, "Admin", [
            "alerts.view", "alerts.acknowledge", "alerts.escalate", "alerts.resolve",
            "events.view", "users.view",
        ])
        viewer_role_a = _create_role(db, org_a.id, "Viewer", [
            "alerts.view", "events.view",
        ])

        admin_email = f"alert-admin-a-{uuid.uuid4().hex[:6]}@test.com"
        admin_a = _create_user(db, org_a.id, admin_role_a.id, admin_email, "Admin A")
        viewer_email = f"alert-viewer-a-{uuid.uuid4().hex[:6]}@test.com"
        viewer_a = _create_user(db, org_a.id, viewer_role_a.id, viewer_email, "Viewer A")

        site_a = _create_site(db, org_a.id)
        camera_a = _create_camera(db, org_a.id, site_a.id)
        event_a = _create_event(db, org_a.id, camera_a.id)

        # --- ORG B ---
        org_b = _create_org(db, f"Alert Org B {uuid.uuid4().hex[:6]}", f"alert-b-{uuid.uuid4().hex[:6]}")

        admin_role_b = _create_role(db, org_b.id, "Admin", [
            "alerts.view", "alerts.acknowledge", "alerts.escalate", "alerts.resolve",
        ])

        admin_b_email = f"alert-admin-b-{uuid.uuid4().hex[:6]}@test.com"
        admin_b = _create_user(db, org_b.id, admin_role_b.id, admin_b_email, "Admin B")

        site_b = _create_site(db, org_b.id)
        camera_b = _create_camera(db, org_b.id, site_b.id)
        event_b = _create_event(db, org_b.id, camera_b.id)

        db.commit()

        _test_data["org_a_id"] = org_a.id
        _test_data["org_b_id"] = org_b.id
        _test_data["admin_a_id"] = admin_a.id
        _test_data["viewer_a_id"] = viewer_a.id
        _test_data["admin_b_id"] = admin_b.id
        _test_data["event_a_id"] = event_a.id
        _test_data["event_b_id"] = event_b.id
        _test_data["admin_a_email"] = admin_a.email
        _test_data["viewer_a_email"] = viewer_a.email

    finally:
        db.close()


# ==============================================================================
# Helper: Create alert via engine for lifecycle tests
# ==============================================================================

def _create_test_alert(org_id: str, event_id: str, severity: str = "high") -> str:
    """Create an alert directly via AlertEngine and return its ID."""
    db = TestSession()
    try:
        risk = _make_risk_assessment(event_id=event_id, org_id=org_id, risk_level=severity)
        alert = AlertEngine.create_alert_from_risk(risk=risk, db=db)
        db.commit()
        return alert.id
    finally:
        db.close()


# ==============================================================================
# 1–3. Alert Creation Tests
# ==============================================================================

class TestAlertCreation:
    """Alert creation from RiskAssessment."""

    def setup_method(self):
        _setup_test_data()

    def test_risk_assessment_creates_alert(self):
        """RiskAssessment produces an alert with correct fields."""
        db = TestSession()
        try:
            org_id = _test_data["org_a_id"]
            risk = _make_risk_assessment(
                event_id=_test_data["event_a_id"],
                org_id=org_id,
                risk_level="high",
            )
            alert = AlertEngine.create_alert_from_risk(risk=risk, db=db)
            db.commit()

            assert alert.id is not None
            assert alert.org_id == org_id
            assert alert.status == AlertStatus.NEW
            assert alert.severity == AlertSeverity.HIGH
            assert alert.event_id == _test_data["event_a_id"]
            assert alert.metadata_json is not None
            assert alert.metadata_json["risk_score"] == risk.risk_score
        finally:
            db.close()

    def test_alert_preserves_event_relationship(self):
        """Alert links to the originating event."""
        db = TestSession()
        try:
            risk = _make_risk_assessment(
                event_id=_test_data["event_a_id"],
                org_id=_test_data["org_a_id"],
            )
            alert = AlertEngine.create_alert_from_risk(risk=risk, db=db)
            db.commit()

            assert alert.event_id == _test_data["event_a_id"]
        finally:
            db.close()

    def test_alert_severity_matches_risk_level(self):
        """Alert severity matches the RiskAssessment risk_level."""
        db = TestSession()
        try:
            for risk_level, expected_severity in [
                ("critical", AlertSeverity.CRITICAL),
                ("high", AlertSeverity.HIGH),
                ("medium", AlertSeverity.MEDIUM),
                ("low", AlertSeverity.LOW),
                ("info", AlertSeverity.INFO),
            ]:
                risk = _make_risk_assessment(
                    event_id=_test_data["event_a_id"],
                    org_id=_test_data["org_a_id"],
                    risk_level=risk_level,
                )
                alert = AlertEngine.create_alert_from_risk(risk=risk, db=db)
                db.flush()
                assert alert.severity == expected_severity, (
                    f"risk_level={risk_level} should map to {expected_severity}"
                )
            db.commit()
        finally:
            db.close()


# ==============================================================================
# 4–7. Valid Lifecycle Tests
# ==============================================================================

class TestValidLifecycle:
    """Valid lifecycle transitions succeed and create audit rows."""

    def setup_method(self):
        _setup_test_data()

    def test_new_to_acknowledged(self):
        """NEW → ACKNOWLEDGED succeeds."""
        alert_id = _create_test_alert(_test_data["org_a_id"], _test_data["event_a_id"])
        token = _get_token(_test_data["admin_a_id"], _test_data["org_a_id"])

        resp = client.patch(
            f"/api/alerts/{alert_id}/status",
            json={"status": "acknowledged"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "acknowledged"

    def test_acknowledged_to_escalated(self):
        """ACKNOWLEDGED → ESCALATED succeeds."""
        alert_id = _create_test_alert(_test_data["org_a_id"], _test_data["event_a_id"])
        token = _get_token(_test_data["admin_a_id"], _test_data["org_a_id"])

        # First: NEW → ACKNOWLEDGED
        client.patch(
            f"/api/alerts/{alert_id}/status",
            json={"status": "acknowledged"},
            headers=_auth_header(token),
        )
        # Then: ACKNOWLEDGED → ESCALATED
        resp = client.patch(
            f"/api/alerts/{alert_id}/status",
            json={"status": "escalated"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "escalated"

    def test_escalated_to_resolved(self):
        """ESCALATED → RESOLVED succeeds."""
        alert_id = _create_test_alert(_test_data["org_a_id"], _test_data["event_a_id"])
        token = _get_token(_test_data["admin_a_id"], _test_data["org_a_id"])

        # NEW → ACKNOWLEDGED → ESCALATED
        client.patch(f"/api/alerts/{alert_id}/status", json={"status": "acknowledged"}, headers=_auth_header(token))
        client.patch(f"/api/alerts/{alert_id}/status", json={"status": "escalated"}, headers=_auth_header(token))

        resp = client.patch(
            f"/api/alerts/{alert_id}/status",
            json={"status": "resolved"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"

    def test_full_lifecycle_end_to_end(self):
        """Complete lifecycle: NEW → ACKNOWLEDGED → ESCALATED → RESOLVED."""
        alert_id = _create_test_alert(_test_data["org_a_id"], _test_data["event_a_id"])
        token = _get_token(_test_data["admin_a_id"], _test_data["org_a_id"])

        for target_status in ["acknowledged", "escalated", "resolved"]:
            resp = client.patch(
                f"/api/alerts/{alert_id}/status",
                json={"status": target_status},
                headers=_auth_header(token),
            )
            assert resp.status_code == 200, f"Failed on {target_status}: {resp.json()}"
            assert resp.json()["status"] == target_status

        # Final state has 4 audit entries: NEW + 3 transitions
        assert len(resp.json()["states"]) == 4


# ==============================================================================
# 8–10. Invalid Lifecycle Tests
# ==============================================================================

class TestInvalidLifecycle:
    """Invalid transitions are rejected with HTTP 409."""

    def setup_method(self):
        _setup_test_data()

    def test_new_to_resolved_rejected(self):
        """NEW → RESOLVED returns HTTP 409."""
        alert_id = _create_test_alert(_test_data["org_a_id"], _test_data["event_a_id"])
        token = _get_token(_test_data["admin_a_id"], _test_data["org_a_id"])

        resp = client.patch(
            f"/api/alerts/{alert_id}/status",
            json={"status": "resolved"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 409

    def test_invalid_transition_no_status_change(self):
        """Invalid transition does NOT change the alert status."""
        alert_id = _create_test_alert(_test_data["org_a_id"], _test_data["event_a_id"])
        token = _get_token(_test_data["admin_a_id"], _test_data["org_a_id"])

        client.patch(
            f"/api/alerts/{alert_id}/status",
            json={"status": "resolved"},
            headers=_auth_header(token),
        )

        # Get current state — should still be NEW
        resp = client.get(
            f"/api/alerts/{alert_id}",
            headers=_auth_header(token),
        )
        assert resp.json()["status"] == "new"

    def test_invalid_transition_no_audit_row(self):
        """Invalid transition does NOT create an audit row."""
        alert_id = _create_test_alert(_test_data["org_a_id"], _test_data["event_a_id"])
        token = _get_token(_test_data["admin_a_id"], _test_data["org_a_id"])

        # Get baseline audit count
        resp = client.get(f"/api/alerts/{alert_id}", headers=_auth_header(token))
        baseline_states = len(resp.json()["states"])

        # Attempt invalid transition
        client.patch(
            f"/api/alerts/{alert_id}/status",
            json={"status": "resolved"},
            headers=_auth_header(token),
        )

        # Audit count unchanged
        resp = client.get(f"/api/alerts/{alert_id}", headers=_auth_header(token))
        assert len(resp.json()["states"]) == baseline_states


# ==============================================================================
# 11–14. Permission Tests
# ==============================================================================

class TestPermissions:
    """RBAC enforcement on lifecycle transitions."""

    def setup_method(self):
        _setup_test_data()

    def test_authorized_user_can_transition(self):
        """Admin with alerts.acknowledge can acknowledge."""
        alert_id = _create_test_alert(_test_data["org_a_id"], _test_data["event_a_id"])
        token = _get_token(_test_data["admin_a_id"], _test_data["org_a_id"])

        resp = client.patch(
            f"/api/alerts/{alert_id}/status",
            json={"status": "acknowledged"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 200

    def test_viewer_cannot_acknowledge(self):
        """Viewer without alerts.acknowledge gets 403."""
        alert_id = _create_test_alert(_test_data["org_a_id"], _test_data["event_a_id"])
        token = _get_token(_test_data["viewer_a_id"], _test_data["org_a_id"], role_name="Viewer")

        resp = client.patch(
            f"/api/alerts/{alert_id}/status",
            json={"status": "acknowledged"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 403

    def test_permission_denial_no_status_change(self):
        """Permission denial does NOT change alert status."""
        alert_id = _create_test_alert(_test_data["org_a_id"], _test_data["event_a_id"])
        viewer_token = _get_token(_test_data["viewer_a_id"], _test_data["org_a_id"], role_name="Viewer")
        admin_token = _get_token(_test_data["admin_a_id"], _test_data["org_a_id"])

        # Viewer tries and fails
        client.patch(
            f"/api/alerts/{alert_id}/status",
            json={"status": "acknowledged"},
            headers=_auth_header(viewer_token),
        )

        # Still NEW
        resp = client.get(f"/api/alerts/{alert_id}", headers=_auth_header(admin_token))
        assert resp.json()["status"] == "new"

    def test_permission_denial_no_audit_row(self):
        """Permission denial does NOT create an audit row."""
        alert_id = _create_test_alert(_test_data["org_a_id"], _test_data["event_a_id"])
        viewer_token = _get_token(_test_data["viewer_a_id"], _test_data["org_a_id"], role_name="Viewer")
        admin_token = _get_token(_test_data["admin_a_id"], _test_data["org_a_id"])

        resp = client.get(f"/api/alerts/{alert_id}", headers=_auth_header(admin_token))
        baseline_states = len(resp.json()["states"])

        # Viewer tries and fails
        client.patch(
            f"/api/alerts/{alert_id}/status",
            json={"status": "acknowledged"},
            headers=_auth_header(viewer_token),
        )

        resp = client.get(f"/api/alerts/{alert_id}", headers=_auth_header(admin_token))
        assert len(resp.json()["states"]) == baseline_states


# ==============================================================================
# 15–19. Audit Trail Tests
# ==============================================================================

class TestAuditTrail:
    """Every lifecycle transition is recorded in alert_states."""

    def setup_method(self):
        _setup_test_data()

    def test_transition_creates_one_audit_row(self):
        """A valid transition creates exactly one new alert_states record."""
        alert_id = _create_test_alert(_test_data["org_a_id"], _test_data["event_a_id"])
        token = _get_token(_test_data["admin_a_id"], _test_data["org_a_id"])

        resp = client.get(f"/api/alerts/{alert_id}", headers=_auth_header(token))
        baseline = len(resp.json()["states"])

        client.patch(
            f"/api/alerts/{alert_id}/status",
            json={"status": "acknowledged"},
            headers=_auth_header(token),
        )

        resp = client.get(f"/api/alerts/{alert_id}", headers=_auth_header(token))
        assert len(resp.json()["states"]) == baseline + 1

    def test_audit_stores_previous_status(self):
        """Audit record has correct from_status."""
        alert_id = _create_test_alert(_test_data["org_a_id"], _test_data["event_a_id"])
        token = _get_token(_test_data["admin_a_id"], _test_data["org_a_id"])

        client.patch(
            f"/api/alerts/{alert_id}/status",
            json={"status": "acknowledged"},
            headers=_auth_header(token),
        )

        resp = client.get(f"/api/alerts/{alert_id}", headers=_auth_header(token))
        states = resp.json()["states"]
        transition = states[-1]  # Last state entry
        assert transition["from_status"] == "new"

    def test_audit_stores_new_status(self):
        """Audit record has correct to_status."""
        alert_id = _create_test_alert(_test_data["org_a_id"], _test_data["event_a_id"])
        token = _get_token(_test_data["admin_a_id"], _test_data["org_a_id"])

        client.patch(
            f"/api/alerts/{alert_id}/status",
            json={"status": "acknowledged"},
            headers=_auth_header(token),
        )

        resp = client.get(f"/api/alerts/{alert_id}", headers=_auth_header(token))
        transition = resp.json()["states"][-1]
        assert transition["to_status"] == "acknowledged"

    def test_audit_stores_acting_user(self):
        """Audit record has the user who performed the transition."""
        alert_id = _create_test_alert(_test_data["org_a_id"], _test_data["event_a_id"])
        token = _get_token(_test_data["admin_a_id"], _test_data["org_a_id"])

        client.patch(
            f"/api/alerts/{alert_id}/status",
            json={"status": "acknowledged"},
            headers=_auth_header(token),
        )

        resp = client.get(f"/api/alerts/{alert_id}", headers=_auth_header(token))
        transition = resp.json()["states"][-1]
        assert transition["changed_by"] == _test_data["admin_a_id"]

    def test_audit_stores_timestamp(self):
        """Audit record has a valid created_at timestamp."""
        alert_id = _create_test_alert(_test_data["org_a_id"], _test_data["event_a_id"])
        token = _get_token(_test_data["admin_a_id"], _test_data["org_a_id"])

        client.patch(
            f"/api/alerts/{alert_id}/status",
            json={"status": "acknowledged"},
            headers=_auth_header(token),
        )

        resp = client.get(f"/api/alerts/{alert_id}", headers=_auth_header(token))
        transition = resp.json()["states"][-1]
        assert transition["created_at"] is not None


# ==============================================================================
# 20–22. Tenant Isolation Tests
# ==============================================================================

class TestTenantIsolation:
    """Organization A cannot access Organization B's alerts."""

    def setup_method(self):
        _setup_test_data()

    def test_cross_org_transition_rejected(self):
        """Org A admin cannot transition Org B alert."""
        # Create alert in Org B
        alert_id = _create_test_alert(_test_data["org_b_id"], _test_data["event_b_id"])
        # Use Org A token
        token_a = _get_token(_test_data["admin_a_id"], _test_data["org_a_id"])

        resp = client.patch(
            f"/api/alerts/{alert_id}/status",
            json={"status": "acknowledged"},
            headers=_auth_header(token_a),
        )
        assert resp.status_code == 404

    def test_cross_org_get_rejected(self):
        """Org A admin cannot GET Org B alert."""
        alert_id = _create_test_alert(_test_data["org_b_id"], _test_data["event_b_id"])
        token_a = _get_token(_test_data["admin_a_id"], _test_data["org_a_id"])

        resp = client.get(
            f"/api/alerts/{alert_id}",
            headers=_auth_header(token_a),
        )
        assert resp.status_code == 404

    def test_cross_org_no_audit_created(self):
        """Cross-tenant attempt does NOT create audit rows."""
        alert_id = _create_test_alert(_test_data["org_b_id"], _test_data["event_b_id"])
        token_a = _get_token(_test_data["admin_a_id"], _test_data["org_a_id"])
        token_b = _get_token(_test_data["admin_b_id"], _test_data["org_b_id"])

        # Get baseline from org B
        resp = client.get(f"/api/alerts/{alert_id}", headers=_auth_header(token_b))
        baseline_states = len(resp.json()["states"])

        # Org A attempts transition
        client.patch(
            f"/api/alerts/{alert_id}/status",
            json={"status": "acknowledged"},
            headers=_auth_header(token_a),
        )

        # Audit count unchanged from org B perspective
        resp = client.get(f"/api/alerts/{alert_id}", headers=_auth_header(token_b))
        assert len(resp.json()["states"]) == baseline_states


# ==============================================================================
# 23–24. Concurrency / Integrity Tests
# ==============================================================================

class TestIntegrity:
    """Transaction atomicity and consistent database state."""

    def setup_method(self):
        _setup_test_data()

    def test_failed_transition_consistent_state(self):
        """Failed transition (409) leaves alert unchanged."""
        alert_id = _create_test_alert(_test_data["org_a_id"], _test_data["event_a_id"])
        token = _get_token(_test_data["admin_a_id"], _test_data["org_a_id"])

        # Invalid: NEW → RESOLVED
        resp = client.patch(
            f"/api/alerts/{alert_id}/status",
            json={"status": "resolved"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 409

        # Alert still perfectly valid
        resp = client.get(f"/api/alerts/{alert_id}", headers=_auth_header(token))
        assert resp.status_code == 200
        assert resp.json()["status"] == "new"

    def test_audit_and_status_atomic(self):
        """A successful transition has both the status and audit row."""
        alert_id = _create_test_alert(_test_data["org_a_id"], _test_data["event_a_id"])
        token = _get_token(_test_data["admin_a_id"], _test_data["org_a_id"])

        resp = client.patch(
            f"/api/alerts/{alert_id}/status",
            json={"status": "acknowledged"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 200

        data = resp.json()
        # Status is updated
        assert data["status"] == "acknowledged"
        # Audit row is present — latest entry matches
        latest_state = data["states"][-1]
        assert latest_state["from_status"] == "new"
        assert latest_state["to_status"] == "acknowledged"
        assert latest_state["changed_by"] == _test_data["admin_a_id"]


# ==============================================================================
# Additional: Alert Engine Unit Tests (no HTTP)
# ==============================================================================

class TestAlertEngineUnit:
    """Direct AlertEngine service tests (no HTTP)."""

    def setup_method(self):
        _setup_test_data()

    def test_invalid_transition_error_raised(self):
        """InvalidTransitionError is raised for disallowed transitions."""
        db = TestSession()
        try:
            risk = _make_risk_assessment(
                event_id=_test_data["event_a_id"],
                org_id=_test_data["org_a_id"],
            )
            alert = AlertEngine.create_alert_from_risk(risk=risk, db=db)
            db.commit()

            try:
                AlertEngine.transition(
                    alert=alert,
                    to_status=AlertStatus.RESOLVED,
                    user_id=_test_data["admin_a_id"],
                    db=db,
                )
                msg = "Should have raised InvalidTransitionError"
                raise AssertionError(msg)
            except InvalidTransitionError as e:
                assert e.from_status == "new"
                assert e.to_status == "resolved"
                db.rollback()
        finally:
            db.close()

    def test_initial_state_created(self):
        """Alert creation also creates an initial AlertState (→ NEW)."""
        db = TestSession()
        try:
            risk = _make_risk_assessment(
                event_id=_test_data["event_a_id"],
                org_id=_test_data["org_a_id"],
            )
            alert = AlertEngine.create_alert_from_risk(risk=risk, db=db)
            db.commit()

            states = db.query(AlertState).filter(
                AlertState.alert_id == alert.id,
            ).all()

            assert len(states) == 1
            assert states[0].from_status is None
            assert states[0].to_status == "new"
        finally:
            db.close()

    def test_get_alert_tenant_isolated(self):
        """AlertEngine.get_alert enforces org_id filter."""
        db = TestSession()
        try:
            risk = _make_risk_assessment(
                event_id=_test_data["event_a_id"],
                org_id=_test_data["org_a_id"],
            )
            alert = AlertEngine.create_alert_from_risk(risk=risk, db=db)
            db.commit()

            # Correct org → found
            found = AlertEngine.get_alert(db, alert.id, _test_data["org_a_id"])
            assert found is not None

            # Wrong org → None
            not_found = AlertEngine.get_alert(db, alert.id, _test_data["org_b_id"])
            assert not_found is None
        finally:
            db.close()

    def test_resolved_sets_resolved_at(self):
        """Resolving an alert sets resolved_at timestamp."""
        db = TestSession()
        try:
            risk = _make_risk_assessment(
                event_id=_test_data["event_a_id"],
                org_id=_test_data["org_a_id"],
            )
            alert = AlertEngine.create_alert_from_risk(risk=risk, db=db)
            db.commit()

            assert alert.resolved_at is None

            # NEW → ACKNOWLEDGED
            AlertEngine.transition(alert, AlertStatus.ACKNOWLEDGED, _test_data["admin_a_id"], db)
            # ACKNOWLEDGED → RESOLVED
            AlertEngine.transition(alert, AlertStatus.RESOLVED, _test_data["admin_a_id"], db)
            db.commit()

            assert alert.resolved_at is not None
        finally:
            db.close()
