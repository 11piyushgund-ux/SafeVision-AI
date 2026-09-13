"""
SafeVision AI — Phase 10B API Tests

Tests for the new Events, Cameras, Zones, Patterns, and Stats endpoints.
Covers: authentication, tenant isolation, pagination, filters, empty responses.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.main import app
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.camera import Camera, CameraStatus
from app.models.event import Event, EventType
from app.models.organization import OrgStatus, Organization
from app.models.pattern import Pattern, PatternStatus, PatternType
from app.models.role import Permission, Role
from app.models.site import Site, SiteStatus
from app.models.user import User, UserStatus
from app.models.zone import Zone, ZoneStatus, ZoneType
from app.services.auth_service import create_access_token, hash_password

# ============================================================================
# Fixtures
# ============================================================================

NOW = datetime.now(timezone.utc)

# Fixed IDs for test data (different from seed data to avoid collisions)
ORG_A_ID = "t10b00a0-0000-0000-0000-000000000001"
ORG_B_ID = "t10b00b0-0000-0000-0000-000000000001"
ROLE_A_ID = "t10b00a0-0000-0000-0000-000000000002"
ROLE_B_ID = "t10b00b0-0000-0000-0000-000000000002"
USER_A_ID = "t10b00a0-0000-0000-0000-000000000003"
USER_B_ID = "t10b00b0-0000-0000-0000-000000000003"
SITE_A_ID = "t10b00a0-0000-0000-0000-000000000004"
SITE_B_ID = "t10b00b0-0000-0000-0000-000000000004"
ZONE_A_ID = "t10b00a0-0000-0000-0000-000000000010"
ZONE_B_ID = "t10b00b0-0000-0000-0000-000000000010"
CAM_A_ID = "t10b00a0-0000-0000-0000-000000000020"
CAM_B_ID = "t10b00b0-0000-0000-0000-000000000020"
EVENT_A_ID = "t10b00a0-0000-0000-0000-000000000030"
EVENT_B_ID = "t10b00b0-0000-0000-0000-000000000030"
ALERT_A_ID = "t10b00a0-0000-0000-0000-000000000040"
PATTERN_A_ID = "t10b00a0-0000-0000-0000-000000000050"
PATTERN_B_ID = "t10b00b0-0000-0000-0000-000000000050"


@pytest.fixture(scope="module")
def db():
    """Get a real database session for integration tests."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="module", autouse=True)
def seed_test_data(db: Session):
    """Seed two organizations with isolated data for tenant isolation tests."""
    # Clean up any previous test data
    for model in [Alert, Event, Camera, Pattern, Zone, Site, Permission, User, Role, Organization]:
        db.query(model).filter(
            model.id.in_([
                ORG_A_ID, ORG_B_ID, ROLE_A_ID, ROLE_B_ID, USER_A_ID, USER_B_ID,
                SITE_A_ID, SITE_B_ID, ZONE_A_ID, ZONE_B_ID, CAM_A_ID, CAM_B_ID,
                EVENT_A_ID, EVENT_B_ID, ALERT_A_ID, PATTERN_A_ID, PATTERN_B_ID,
            ])
        ).delete(synchronize_session=False)
    # Also clean by org_id
    for model in [Alert, Event, Camera, Pattern, Zone, Site]:
        if hasattr(model, "org_id"):
            db.query(model).filter(model.org_id.in_([ORG_A_ID, ORG_B_ID])).delete(synchronize_session=False)
    db.query(User).filter(User.org_id.in_([ORG_A_ID, ORG_B_ID])).delete(synchronize_session=False)
    db.query(Permission).filter(Permission.role_id.in_([ROLE_A_ID, ROLE_B_ID])).delete(synchronize_session=False)
    db.query(Role).filter(Role.org_id.in_([ORG_A_ID, ORG_B_ID])).delete(synchronize_session=False)
    db.query(Organization).filter(Organization.id.in_([ORG_A_ID, ORG_B_ID])).delete(synchronize_session=False)
    db.commit()

    # ---- Org A ----
    db.add(Organization(id=ORG_A_ID, name="Test Org A 10B", slug="test-org-a-10b", status=OrgStatus.ACTIVE))
    db.add(Role(id=ROLE_A_ID, name="Admin", org_id=ORG_A_ID))
    db.flush()
    for perm in ["events.view", "cameras.view", "zones.view", "patterns.view", "alerts.view"]:
        db.add(Permission(id=str(uuid.uuid4()), role_id=ROLE_A_ID, perm_name=perm))
    db.add(User(
        id=USER_A_ID, org_id=ORG_A_ID, email="testa10b@test.com",
        name="User A", pwd_hash=hash_password("pass"), role_id=ROLE_A_ID, status=UserStatus.ACTIVE,
    ))
    db.add(Site(id=SITE_A_ID, org_id=ORG_A_ID, name="Site A", status=SiteStatus.ACTIVE))
    db.flush()
    db.add(Zone(
        id=ZONE_A_ID, site_id=SITE_A_ID, org_id=ORG_A_ID, name="Zone A Exclusion",
        zone_type=ZoneType.EXCLUSION, status=ZoneStatus.ACTIVE,
        polygon=[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
        required_ppe=["helmet", "safety_vest"],
    ))
    db.flush()
    db.add(Camera(
        id=CAM_A_ID, site_id=SITE_A_ID, org_id=ORG_A_ID, zone_id=ZONE_A_ID,
        name="Cam A", status=CameraStatus.ONLINE,
    ))
    db.flush()
    db.add(Event(
        id=EVENT_A_ID, camera_id=CAM_A_ID, org_id=ORG_A_ID,
        event_type=EventType.ZONE_INTRUSION, timestamp=NOW, confidence=0.95,
    ))
    db.add(Alert(
        id=ALERT_A_ID, org_id=ORG_A_ID, event_id=EVENT_A_ID,
        title="Test Alert A", severity=AlertSeverity.HIGH, status=AlertStatus.NEW,
    ))
    db.add(Pattern(
        id=PATTERN_A_ID, org_id=ORG_A_ID, zone_id=ZONE_A_ID,
        pattern_type=PatternType.SPATIAL, title="Pattern A",
        occurrence_count=10, confidence_score=0.9, status=PatternStatus.ACTIVE,
        first_detected_at=NOW - timedelta(days=7), last_detected_at=NOW,
    ))
    db.flush()

    # ---- Org B ----
    db.add(Organization(id=ORG_B_ID, name="Test Org B 10B", slug="test-org-b-10b", status=OrgStatus.ACTIVE))
    db.add(Role(id=ROLE_B_ID, name="Admin", org_id=ORG_B_ID))
    db.flush()
    for perm in ["events.view", "cameras.view", "zones.view", "patterns.view", "alerts.view"]:
        db.add(Permission(id=str(uuid.uuid4()), role_id=ROLE_B_ID, perm_name=perm))
    db.add(User(
        id=USER_B_ID, org_id=ORG_B_ID, email="testb10b@test.com",
        name="User B", pwd_hash=hash_password("pass"), role_id=ROLE_B_ID, status=UserStatus.ACTIVE,
    ))
    db.add(Site(id=SITE_B_ID, org_id=ORG_B_ID, name="Site B", status=SiteStatus.ACTIVE))
    db.flush()
    db.add(Zone(
        id=ZONE_B_ID, site_id=SITE_B_ID, org_id=ORG_B_ID, name="Zone B PPE",
        zone_type=ZoneType.PPE_REQUIRED, status=ZoneStatus.ACTIVE,
        polygon=[[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]],
        required_ppe=["goggles"],
    ))
    db.flush()
    db.add(Camera(
        id=CAM_B_ID, site_id=SITE_B_ID, org_id=ORG_B_ID, zone_id=ZONE_B_ID,
        name="Cam B", status=CameraStatus.OFFLINE,
    ))
    db.flush()
    db.add(Event(
        id=EVENT_B_ID, camera_id=CAM_B_ID, org_id=ORG_B_ID,
        event_type=EventType.PPE_DETECTION, timestamp=NOW, confidence=0.88,
    ))
    db.add(Pattern(
        id=PATTERN_B_ID, org_id=ORG_B_ID, zone_id=ZONE_B_ID,
        pattern_type=PatternType.TEMPORAL, title="Pattern B",
        occurrence_count=5, confidence_score=0.7, status=PatternStatus.ACTIVE,
        first_detected_at=NOW - timedelta(days=3), last_detected_at=NOW,
    ))
    db.commit()

    yield

    # Cleanup
    for model in [Alert, Event, Camera, Pattern, Zone, Site, Permission, User, Role, Organization]:
        db.query(model).filter(
            model.id.in_([
                ORG_A_ID, ORG_B_ID, ROLE_A_ID, ROLE_B_ID, USER_A_ID, USER_B_ID,
                SITE_A_ID, SITE_B_ID, ZONE_A_ID, ZONE_B_ID, CAM_A_ID, CAM_B_ID,
                EVENT_A_ID, EVENT_B_ID, ALERT_A_ID, PATTERN_A_ID, PATTERN_B_ID,
            ])
        ).delete(synchronize_session=False)
    for model in [Alert, Event, Camera, Pattern, Zone, Site]:
        if hasattr(model, "org_id"):
            db.query(model).filter(model.org_id.in_([ORG_A_ID, ORG_B_ID])).delete(synchronize_session=False)
    db.query(User).filter(User.org_id.in_([ORG_A_ID, ORG_B_ID])).delete(synchronize_session=False)
    db.query(Permission).filter(Permission.role_id.in_([ROLE_A_ID, ROLE_B_ID])).delete(synchronize_session=False)
    db.query(Role).filter(Role.org_id.in_([ORG_A_ID, ORG_B_ID])).delete(synchronize_session=False)
    db.query(Organization).filter(Organization.id.in_([ORG_A_ID, ORG_B_ID])).delete(synchronize_session=False)
    db.commit()


def _token_a():
    return create_access_token(USER_A_ID, ORG_A_ID, "Admin")


def _token_b():
    return create_access_token(USER_B_ID, ORG_B_ID, "Admin")


def _auth_header(token: str):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ============================================================================
# Events API Tests
# ============================================================================

class TestEventsAPI:
    def test_list_events_authenticated(self, client):
        resp = client.get("/api/events", headers=_auth_header(_token_a()))
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        assert data["total"] >= 1
        assert all(e["org_id"] == ORG_A_ID for e in data["data"])

    def test_list_events_unauthenticated(self, client):
        resp = client.get("/api/events")
        assert resp.status_code in (401, 403)

    def test_list_events_tenant_isolated(self, client):
        resp_a = client.get("/api/events", headers=_auth_header(_token_a()))
        resp_b = client.get("/api/events", headers=_auth_header(_token_b()))
        ids_a = {e["id"] for e in resp_a.json()["data"]}
        ids_b = {e["id"] for e in resp_b.json()["data"]}
        assert ids_a & ids_b == set(), "Events must be org-isolated"

    def test_list_events_filter_by_type(self, client):
        resp = client.get("/api/events?event_type=zone_intrusion", headers=_auth_header(_token_a()))
        assert resp.status_code == 200
        for e in resp.json()["data"]:
            assert e["event_type"] == "zone_intrusion"

    def test_list_events_pagination(self, client):
        resp = client.get("/api/events?page=1&size=1", headers=_auth_header(_token_a()))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) <= 1
        assert data["page"] == 1
        assert data["size"] == 1


# ============================================================================
# Cameras API Tests
# ============================================================================

class TestCamerasAPI:
    def test_list_cameras_authenticated(self, client):
        resp = client.get("/api/cameras", headers=_auth_header(_token_a()))
        assert resp.status_code == 200
        cameras = resp.json()
        assert len(cameras) >= 1
        assert all(c["site_id"] == SITE_A_ID for c in cameras if c["id"] == CAM_A_ID)

    def test_list_cameras_unauthenticated(self, client):
        resp = client.get("/api/cameras")
        assert resp.status_code in (401, 403)

    def test_list_cameras_tenant_isolated(self, client):
        resp_a = client.get("/api/cameras", headers=_auth_header(_token_a()))
        resp_b = client.get("/api/cameras", headers=_auth_header(_token_b()))
        ids_a = {c["id"] for c in resp_a.json()}
        ids_b = {c["id"] for c in resp_b.json()}
        assert ids_a & ids_b == set(), "Cameras must be org-isolated"

    def test_camera_includes_zone_name(self, client):
        resp = client.get("/api/cameras", headers=_auth_header(_token_a()))
        cam_a = next((c for c in resp.json() if c["id"] == CAM_A_ID), None)
        assert cam_a is not None
        assert cam_a["zone_name"] == "Zone A Exclusion"


# ============================================================================
# Zones API Tests (with ROI Polygon Tenant Isolation)
# ============================================================================

class TestZonesAPI:
    def test_list_zones_authenticated(self, client):
        resp = client.get("/api/zones", headers=_auth_header(_token_a()))
        assert resp.status_code == 200
        zones = resp.json()
        assert len(zones) >= 1

    def test_list_zones_unauthenticated(self, client):
        resp = client.get("/api/zones")
        assert resp.status_code in (401, 403)

    def test_zone_list_returns_polygon_data(self, client):
        """ZoneResponse includes the real polygon coordinates."""
        resp = client.get("/api/zones", headers=_auth_header(_token_a()))
        zone_a = next((z for z in resp.json() if z["id"] == ZONE_A_ID), None)
        assert zone_a is not None
        assert zone_a["polygon"] == [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]

    def test_zone_list_org_isolated(self, client):
        """Org B cannot see Org A's zone polygon/ROI data."""
        resp_a = client.get("/api/zones", headers=_auth_header(_token_a()))
        resp_b = client.get("/api/zones", headers=_auth_header(_token_b()))
        ids_a = {z["id"] for z in resp_a.json()}
        ids_b = {z["id"] for z in resp_b.json()}
        assert ids_a & ids_b == set(), "Zones (including polygon data) must be org-isolated"

    def test_zone_polygon_format_matches_model(self, client):
        """Polygon in API response is identical to Zone.polygon in DB - no transformation."""
        resp = client.get("/api/zones", headers=_auth_header(_token_a()))
        zone_a = next((z for z in resp.json() if z["id"] == ZONE_A_ID), None)
        assert zone_a is not None
        # The polygon should be a list of [x, y] pairs with float values 0.0-1.0
        polygon = zone_a["polygon"]
        assert isinstance(polygon, list)
        assert len(polygon) == 4
        for point in polygon:
            assert isinstance(point, list)
            assert len(point) == 2
            assert all(0.0 <= v <= 1.0 for v in point)

    def test_zone_required_ppe_included(self, client):
        """ZoneResponse includes required_ppe list from Zone model."""
        resp = client.get("/api/zones", headers=_auth_header(_token_a()))
        zone_a = next((z for z in resp.json() if z["id"] == ZONE_A_ID), None)
        assert zone_a is not None
        assert zone_a["required_ppe"] == ["helmet", "safety_vest"]

    def test_zone_list_empty_for_other_org(self, client):
        """An org's user only sees their own zones."""
        resp_b = client.get("/api/zones", headers=_auth_header(_token_b()))
        zones_b = resp_b.json()
        zone_ids = {z["id"] for z in zones_b}
        assert ZONE_A_ID not in zone_ids, "Org B must not see Org A's zones"

    def test_zone_type_included(self, client):
        """ZoneResponse includes zone_type."""
        resp = client.get("/api/zones", headers=_auth_header(_token_a()))
        zone_a = next((z for z in resp.json() if z["id"] == ZONE_A_ID), None)
        assert zone_a is not None
        assert zone_a["zone_type"] == "exclusion"


# ============================================================================
# Patterns API Tests
# ============================================================================

class TestPatternsAPI:
    def test_list_patterns_authenticated(self, client):
        resp = client.get("/api/patterns", headers=_auth_header(_token_a()))
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert data["total"] >= 1

    def test_list_patterns_unauthenticated(self, client):
        resp = client.get("/api/patterns")
        assert resp.status_code in (401, 403)

    def test_list_patterns_tenant_isolated(self, client):
        resp_a = client.get("/api/patterns", headers=_auth_header(_token_a()))
        resp_b = client.get("/api/patterns", headers=_auth_header(_token_b()))
        ids_a = {p["id"] for p in resp_a.json()["data"]}
        ids_b = {p["id"] for p in resp_b.json()["data"]}
        assert ids_a & ids_b == set(), "Patterns must be org-isolated"

    def test_patterns_include_zone_name(self, client):
        resp = client.get("/api/patterns", headers=_auth_header(_token_a()))
        pattern_a = next((p for p in resp.json()["data"] if p["id"] == PATTERN_A_ID), None)
        assert pattern_a is not None
        assert pattern_a["zone_name"] == "Zone A Exclusion"

    def test_list_patterns_pagination(self, client):
        resp = client.get("/api/patterns?page=1&size=1", headers=_auth_header(_token_a()))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) <= 1


# ============================================================================
# Stats API Tests
# ============================================================================

class TestStatsAPI:
    def test_stats_summary_authenticated(self, client):
        resp = client.get("/api/stats/summary", headers=_auth_header(_token_a()))
        assert resp.status_code == 200
        data = resp.json()
        assert "total_alerts" in data
        assert "new_alerts" in data
        assert "total_events" in data
        assert "total_cameras" in data
        assert "online_cameras" in data
        assert "total_zones" in data
        assert "active_zones" in data

    def test_stats_summary_unauthenticated(self, client):
        resp = client.get("/api/stats/summary")
        assert resp.status_code in (401, 403)

    def test_stats_summary_tenant_isolated(self, client):
        resp_a = client.get("/api/stats/summary", headers=_auth_header(_token_a()))
        resp_b = client.get("/api/stats/summary", headers=_auth_header(_token_b()))
        data_a = resp_a.json()
        data_b = resp_b.json()
        # Org A has 1 alert, Org B has 0
        assert data_a["new_alerts"] >= 1
        assert data_b["new_alerts"] == 0

    def test_stats_counts_correct_for_org_a(self, client):
        resp = client.get("/api/stats/summary", headers=_auth_header(_token_a()))
        data = resp.json()
        assert data["total_cameras"] >= 1
        assert data["online_cameras"] >= 1
        assert data["total_zones"] >= 1
        assert data["active_zones"] >= 1
        assert data["total_events"] >= 1
