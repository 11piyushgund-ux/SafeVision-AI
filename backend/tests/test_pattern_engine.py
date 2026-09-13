"""
SafeVision AI — PatternEngine & Recurring Patterns Tests (Phase 13)

Comprehensive automated tests covering:
1. Dynamic database-driven assertions (COUNT, MIN, MAX, daily trend frequency).
2. Legacy seed pattern reconciliation (P13-003A: mark DISMISSED, no deletion).
3. Strict pattern status lifecycle & preservation (no inferred auto-resolution for inactivity).
4. Authoritative daily trend source consistency.
5. Recurrence threshold enforcement (count >= 2).
6. Multi-tenant isolation.
7. API GET /api/patterns contract and serialization.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.main import app
from app.middleware.auth import get_current_user
from app.models.camera import Camera, CameraStatus
from app.models.event import Event, EventType
from app.models.organization import Organization
from app.models.pattern import Pattern, PatternStatus, PatternType
from app.models.role import Permission, Role
from app.models.site import Site
from app.models.user import User, UserStatus
from app.models.zone import Zone, ZoneType
from app.schemas.pattern_schema import DailyTrendItem, PatternResponse
from app.services.pattern_engine import (
    EVENT_TYPE_TO_PATTERN_TYPE,
    RECURRENCE_THRESHOLD,
    PatternEngine,
    _get_utc_date_str,
)


@pytest.fixture
def db_session():
    """Provide a transactional DB session for tests."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_org_environment(db_session: Session):
    """Set up isolated test organization, site, zone, camera, role, and user."""
    org_id = f"test-org-{uuid.uuid4().hex[:8]}"
    site_id = f"test-site-{uuid.uuid4().hex[:8]}"
    zone_id = f"test-zone-{uuid.uuid4().hex[:8]}"
    cam_id = f"test-cam-{uuid.uuid4().hex[:8]}"
    role_id = f"test-role-{uuid.uuid4().hex[:8]}"
    user_id = f"test-user-{uuid.uuid4().hex[:8]}"

    org = Organization(id=org_id, name=f"Test Safety Corp {org_id}", slug=f"slug-{org_id}")
    role = Role(id=role_id, org_id=org_id, name="Admin")
    perm = Permission(id=str(uuid.uuid4()), role_id=role_id, perm_name="patterns.view")
    site = Site(id=site_id, org_id=org_id, name="Test Plant 1")
    zone = Zone(id=zone_id, site_id=site_id, org_id=org_id, name="Test Welding Bay", zone_type=ZoneType.GENERAL)
    camera = Camera(
        id=cam_id,
        site_id=site_id,
        org_id=org_id,
        zone_id=zone_id,
        name="Test Camera 1",
        status=CameraStatus.ONLINE,
    )
    user = User(
        id=user_id,
        org_id=org_id,
        email=f"tester-{uuid.uuid4().hex[:6]}@example.com",
        name="Pattern Tester",
        role_id=role_id,
        status=UserStatus.ACTIVE,
        pwd_hash="mock-password-hash",
    )

    db_session.add_all([org, role, perm, site, zone, camera, user])
    db_session.commit()

    return {
        "org_id": org_id,
        "site_id": site_id,
        "zone_id": zone_id,
        "cam_id": cam_id,
        "user": user,
    }


def test_pattern_engine_dynamic_database_assertions(db_session: Session, test_org_environment):
    """
    Test that pattern metrics strictly match dynamic database aggregates:
    - pattern.occurrence_count == COUNT(matching real events)
    - pattern.first_detected_at == MIN(matching event timestamps)
    - pattern.last_detected_at == MAX(matching event timestamps)
    - daily_trend == actual grouped event counts by day
    """
    org_id = test_org_environment["org_id"]
    cam_id = test_org_environment["cam_id"]
    zone_id = test_org_environment["zone_id"]

    # Insert events across multiple UTC days
    base_time = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
    events_to_create = [
        Event(
            id=str(uuid.uuid4()),
            org_id=org_id,
            camera_id=cam_id,
            event_type=EventType.FIRE_SMOKE,
            timestamp=base_time,
            confidence=0.82,
        ),
        Event(
            id=str(uuid.uuid4()),
            org_id=org_id,
            camera_id=cam_id,
            event_type=EventType.FIRE_SMOKE,
            timestamp=base_time + timedelta(hours=2),
            confidence=0.88,
        ),
        Event(
            id=str(uuid.uuid4()),
            org_id=org_id,
            camera_id=cam_id,
            event_type=EventType.FIRE_SMOKE,
            timestamp=base_time + timedelta(days=1, hours=3),
            confidence=0.90,
        ),
        Event(
            id=str(uuid.uuid4()),
            org_id=org_id,
            camera_id=cam_id,
            event_type=EventType.FIRE_SMOKE,
            timestamp=base_time + timedelta(days=2, hours=4),
            confidence=0.94,
        ),
    ]
    db_session.add_all(events_to_create)
    db_session.commit()

    # Query dynamic ground truth directly from events table
    db_events = (
        db_session.query(Event)
        .filter(Event.org_id == org_id, Event.event_type == EventType.FIRE_SMOKE)
        .all()
    )
    expected_count = len(db_events)
    expected_first = min(e.timestamp for e in db_events)
    expected_last = max(e.timestamp for e in db_events)

    expected_daily = defaultdict(int)
    for e in db_events:
        expected_daily[_get_utc_date_str(e.timestamp)] += 1
    expected_daily_trend = [{"date": d, "occurrences": expected_daily[d]} for d in sorted(expected_daily.keys())]

    # Run PatternEngine synchronization
    patterns = PatternEngine.sync_patterns(db_session, org_id)
    fire_patterns = [p for p in patterns if p.pattern_type == PatternType.TREND and p.zone_id == zone_id]

    assert len(fire_patterns) == 1, "Exactly one recurring fire/smoke trend pattern should be created"
    p = fire_patterns[0]

    # Dynamic assertions
    assert p.occurrence_count == expected_count
    assert p.first_detected_at == expected_first
    assert p.last_detected_at == expected_last
    assert p.pattern_data is not None
    assert p.pattern_data.get("daily_trend") == expected_daily_trend
    assert p.status == PatternStatus.ACTIVE


def test_reconcile_legacy_seed_patterns_marks_dismissed_no_deletion(db_session: Session, test_org_environment):
    """
    Test P13-003A: Legacy Pattern records with zero backing events are safely marked
    DISMISSED and never deleted.
    """
    org_id = test_org_environment["org_id"]
    zone_id = test_org_environment["zone_id"]

    # Insert a synthetic seed pattern with no backing real events
    seed_pattern = Pattern(
        id=str(uuid.uuid4()),
        org_id=org_id,
        zone_id=zone_id,
        pattern_type=PatternType.SPATIAL,
        title="Stale Seed Pattern with No Events",
        description="Legacy synthetic finding",
        occurrence_count=19,
        confidence_score=0.91,
        pattern_data={"seed_origin": "legacy_import"},
        status=PatternStatus.ACTIVE,
        first_detected_at=datetime(2026, 7, 15, tzinfo=timezone.utc),
        last_detected_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
    )
    db_session.add(seed_pattern)
    db_session.commit()

    # Verify initial state
    assert seed_pattern.status == PatternStatus.ACTIVE

    # Run reconciliation
    reconciled_count = PatternEngine.reconcile_legacy_seed_patterns(db_session, org_id)
    assert reconciled_count >= 1

    # Reload from database
    db_session.expire_all()
    reloaded = db_session.query(Pattern).filter(Pattern.id == seed_pattern.id).first()

    assert reloaded is not None, "Legacy seed pattern must NEVER be deleted"
    assert reloaded.status == PatternStatus.DISMISSED, "Legacy seed pattern must be marked DISMISSED"
    assert reloaded.pattern_data.get("reconciled") is True
    assert "zero backing events" in reloaded.pattern_data.get("reconciliation_reason", "")


def test_pattern_status_no_inferred_resolution_for_inactivity(db_session: Session, test_org_environment):
    """
    Test Correction 1: An active pattern is NOT automatically marked RESOLVED
    merely because events stopped occurring for 14+ days.
    """
    org_id = test_org_environment["org_id"]
    cam_id = test_org_environment["cam_id"]
    zone_id = test_org_environment["zone_id"]

    # Events from 30 days ago
    old_time = datetime.now(timezone.utc) - timedelta(days=30)
    e1 = Event(
        id=str(uuid.uuid4()),
        org_id=org_id,
        camera_id=cam_id,
        event_type=EventType.ZONE_INTRUSION,
        timestamp=old_time,
        confidence=0.85,
    )
    e2 = Event(
        id=str(uuid.uuid4()),
        org_id=org_id,
        camera_id=cam_id,
        event_type=EventType.ZONE_INTRUSION,
        timestamp=old_time + timedelta(hours=1),
        confidence=0.87,
    )
    db_session.add_all([e1, e2])
    db_session.commit()

    patterns = PatternEngine.sync_patterns(db_session, org_id)
    intrusion_patterns = [p for p in patterns if p.pattern_type == PatternType.SPATIAL and p.zone_id == zone_id]

    assert len(intrusion_patterns) == 1
    p = intrusion_patterns[0]
    # Inactivity must NEVER resolve a pattern
    assert p.status == PatternStatus.ACTIVE


def test_pattern_status_preserves_explicit_resolved_and_dismissed(db_session: Session, test_org_environment):
    """
    Test Correction 1: Explicitly RESOLVED or DISMISSED patterns must preserve
    their status across synchronization cycles and not revert to ACTIVE.
    """
    org_id = test_org_environment["org_id"]
    cam_id = test_org_environment["cam_id"]
    zone_id = test_org_environment["zone_id"]

    events = [
        Event(
            id=str(uuid.uuid4()),
            org_id=org_id,
            camera_id=cam_id,
            event_type=EventType.PPE_DETECTION,
            timestamp=datetime.now(timezone.utc) - timedelta(hours=2),
            confidence=0.89,
        ),
        Event(
            id=str(uuid.uuid4()),
            org_id=org_id,
            camera_id=cam_id,
            event_type=EventType.PPE_DETECTION,
            timestamp=datetime.now(timezone.utc) - timedelta(hours=1),
            confidence=0.91,
        ),
    ]
    db_session.add_all(events)
    db_session.commit()

    patterns = PatternEngine.sync_patterns(db_session, org_id)
    ppe_pattern = [p for p in patterns if p.pattern_type == PatternType.TEMPORAL and p.zone_id == zone_id][0]
    assert ppe_pattern.status == PatternStatus.ACTIVE

    # Explicitly resolve by human operator
    ppe_pattern.status = PatternStatus.RESOLVED
    db_session.commit()

    # Re-sync
    patterns_after = PatternEngine.sync_patterns(db_session, org_id)
    ppe_pattern_after = [p for p in patterns_after if p.id == ppe_pattern.id][0]

    assert ppe_pattern_after.status == PatternStatus.RESOLVED, "Resolved status must be preserved across syncs"


def test_recurrence_threshold_filtering(db_session: Session, test_org_environment):
    """
    Test that isolated incidents with count < 2 are ignored and do NOT produce patterns.
    """
    org_id = test_org_environment["org_id"]
    cam_id = test_org_environment["cam_id"]
    zone_id = test_org_environment["zone_id"]

    # Single isolated event
    single_event = Event(
        id=str(uuid.uuid4()),
        org_id=org_id,
        camera_id=cam_id,
        event_type=EventType.FIRE_SMOKE,
        timestamp=datetime.now(timezone.utc),
        confidence=0.95,
    )
    db_session.add(single_event)
    db_session.commit()

    patterns = PatternEngine.sync_patterns(db_session, org_id)
    matching = [p for p in patterns if p.pattern_type == PatternType.TREND and p.zone_id == zone_id]
    assert len(matching) == 0, "Single event must not meet recurrence threshold"


def test_tenant_isolation(db_session: Session, test_org_environment):
    """
    Test that events in Organization A do not leak or produce patterns in Organization B.
    """
    org_a = test_org_environment["org_id"]
    cam_a = test_org_environment["cam_id"]

    org_b = f"org-b-{uuid.uuid4().hex[:8]}"
    db_session.add(Organization(id=org_b, name=f"Org B {org_b}", slug=f"slug-b-{org_b}"))
    db_session.commit()

    # Add 2 events to Org A
    now = datetime.now(timezone.utc)
    db_session.add_all([
        Event(id=str(uuid.uuid4()), org_id=org_a, camera_id=cam_a, event_type=EventType.FIRE_SMOKE, timestamp=now, confidence=0.8),
        Event(id=str(uuid.uuid4()), org_id=org_a, camera_id=cam_a, event_type=EventType.FIRE_SMOKE, timestamp=now + timedelta(minutes=5), confidence=0.85),
    ])
    db_session.commit()

    # Sync Org B
    pats_b = PatternEngine.sync_patterns(db_session, org_b)
    assert len(pats_b) == 0, "Org B must have 0 patterns"


def test_api_get_patterns_contract_and_authoritative_daily_trend(test_org_environment):
    """
    Test GET /api/patterns endpoint:
    - Returns 200 with authenticated user
    - Returns PatternListResponse
    - Top-level daily_trend matches pattern_data["daily_trend"] identically
    - Filters by pattern_type and status
    """
    user = test_org_environment["user"]

    def override_get_current_user():
        return user

    app.dependency_overrides[get_current_user] = override_get_current_user
    client = TestClient(app)

    try:
        response = client.get("/api/patterns")
        assert response.status_code == 200
        payload = response.json()

        assert "data" in payload
        assert "total" in payload
        assert "page" in payload
        assert "size" in payload

        for item in payload["data"]:
            if item.get("daily_trend"):
                # Verify schema format
                for trend in item["daily_trend"]:
                    assert "date" in trend
                    assert "occurrences" in trend
                    assert isinstance(trend["occurrences"], int)

                # Authoritative derivation check (Correction 4)
                data_trend = (item.get("pattern_data") or {}).get("daily_trend")
                assert item["daily_trend"] == data_trend, "Top-level daily_trend must match pattern_data['daily_trend']"

        # Test filtering
        filter_res = client.get("/api/patterns?status=active")
        assert filter_res.status_code == 200
        for p in filter_res.json()["data"]:
            assert p["status"] == "active"

    finally:
        app.dependency_overrides.pop(get_current_user, None)
