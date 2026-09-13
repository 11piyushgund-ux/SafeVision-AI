"""
SafeVision AI — Local Development Seed Data

Creates a test user, organization, roles, sites, zones (with real polygons),
cameras, events, alerts, safety rules, and patterns for manual UI testing.

IDEMPOTENT: Safe to run multiple times — uses get-or-create pattern.
FOR LOCAL DEVELOPMENT ONLY — not for production.

Usage:
    cd backend
    python -m scripts.seed_dev_data
"""

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure the backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.camera import Camera, CameraStatus
from app.models.event import Event, EventType
from app.models.organization import OrgStatus, Organization
from app.models.pattern import Pattern, PatternStatus, PatternType
from app.models.role import Permission, Role
from app.models.safety_rule import RuleSeverity, RuleStatus, RuleType, SafetyRule
from app.models.site import Site, SiteStatus
from app.models.user import User, UserStatus
from app.models.zone import Zone, ZoneStatus, ZoneType
from app.services.auth_service import hash_password

# ============================================================================
# Fixed IDs for idempotency
# ============================================================================
ORG_ID = "d0000000-0000-0000-0000-000000000001"
ROLE_ID = "d0000000-0000-0000-0000-000000000002"
USER_ID = "d0000000-0000-0000-0000-000000000003"
SITE_ID = "d0000000-0000-0000-0000-000000000004"

ZONE_IDS = [
    "d0000000-0000-0000-0000-000000000010",
    "d0000000-0000-0000-0000-000000000011",
    "d0000000-0000-0000-0000-000000000012",
]
CAMERA_IDS = [
    "d0000000-0000-0000-0000-000000000020",
    "d0000000-0000-0000-0000-000000000021",
    "d0000000-0000-0000-0000-000000000022",
]
RULE_IDS = [
    "d0000000-0000-0000-0000-000000000030",
    "d0000000-0000-0000-0000-000000000031",
    "d0000000-0000-0000-0000-000000000032",
]
EVENT_IDS = [f"d0000000-0000-0000-0000-0000000001{i:02d}" for i in range(15)]
ALERT_IDS = [f"d0000000-0000-0000-0000-0000000002{i:02d}" for i in range(5)]
PATTERN_IDS = [
    "d0000000-0000-0000-0000-000000000040",
    "d0000000-0000-0000-0000-000000000041",
    "d0000000-0000-0000-0000-000000000042",
]

# All permissions the admin role should have
ALL_PERMISSIONS = [
    "alerts.view", "alerts.acknowledge", "alerts.escalate",
    "alerts.resolve", "alerts.close",
    "documents.view", "documents.upload", "documents.delete",
    "events.view",
    "users.view", "users.manage",
    "ai.analyze",
    "cameras.view",
    "zones.view",
    "patterns.view",
    "settings.view", "settings.manage",
    "notifications.view", "notifications.manage",
]

NOW = datetime.now(timezone.utc)


def get_or_create(db: Session, model, defaults: dict, **kwargs):
    """Get existing record or create new one. Returns (instance, created)."""
    instance = db.query(model).filter_by(**kwargs).first()
    if instance:
        return instance, False
    instance = model(**kwargs, **defaults)
    db.add(instance)
    db.flush()
    return instance, True


def seed(db: Session):
    """Seed all development data."""
    print("=" * 60)
    print("SafeVision AI — Development Seed Data")
    print("=" * 60)

    # ---- Organization ----
    org, created = get_or_create(
        db, Organization, id=ORG_ID,
        defaults={
            "name": "SafeVision Demo Corp",
            "slug": "safevision-demo",
            "status": OrgStatus.ACTIVE,
            "description": "Development/testing organization",
        },
    )
    print(f"  Organization: {'CREATED' if created else 'EXISTS'} — {org.name}")

    # ---- Role ----
    role, created = get_or_create(
        db, Role, id=ROLE_ID,
        defaults={
            "name": "Admin",
            "description": "Full access role for development testing",
            "org_id": ORG_ID,
        },
    )
    print(f"  Role: {'CREATED' if created else 'EXISTS'} — {role.name}")

    # ---- Permissions ----
    existing_perms = {p.perm_name for p in db.query(Permission).filter_by(role_id=ROLE_ID).all()}
    perms_added = 0
    for perm_name in ALL_PERMISSIONS:
        if perm_name not in existing_perms:
            db.add(Permission(id=str(uuid.uuid4()), role_id=ROLE_ID, perm_name=perm_name))
            perms_added += 1
    if perms_added:
        db.flush()
    print(f"  Permissions: {perms_added} added ({len(ALL_PERMISSIONS)} total)")

    # ---- User ----
    user, created = get_or_create(
        db, User, id=USER_ID,
        defaults={
            "org_id": ORG_ID,
            "email": "testmail@gmail.com",
            "name": "Test Admin",
            "pwd_hash": hash_password("test@1234"),
            "role_id": ROLE_ID,
            "status": UserStatus.ACTIVE,
        },
    )
    print(f"  User: {'CREATED' if created else 'EXISTS'} — {user.email}")

    # ---- Site ----
    site, created = get_or_create(
        db, Site, id=SITE_ID,
        defaults={
            "org_id": ORG_ID,
            "name": "Main Manufacturing Plant",
            "address": "123 Industrial Avenue, Manufacturing District",
            "status": SiteStatus.ACTIVE,
        },
    )
    print(f"  Site: {'CREATED' if created else 'EXISTS'} — {site.name}")

    # ---- Zones (with real polygon data) ----
    zones_data = [
        {
            "id": ZONE_IDS[0],
            "name": "Assembly Zone A",
            "description": "Primary assembly line — restricted zone with PPE requirements",
            "zone_type": ZoneType.EXCLUSION,
            "polygon": [[0.05, 0.10], [0.45, 0.10], [0.45, 0.85], [0.05, 0.85]],
            "required_ppe": ["helmet", "safety_vest"],
        },
        {
            "id": ZONE_IDS[1],
            "name": "Packaging Area",
            "description": "Packaging and dispatch area — PPE required zone",
            "zone_type": ZoneType.PPE_REQUIRED,
            "polygon": [[0.50, 0.05], [0.95, 0.05], [0.95, 0.50], [0.50, 0.50]],
            "required_ppe": ["helmet", "safety_vest", "goggles"],
        },
        {
            "id": ZONE_IDS[2],
            "name": "Electrical Room",
            "description": "High-voltage electrical equipment — fire watch zone",
            "zone_type": ZoneType.FIRE_WATCH,
            "polygon": [[0.55, 0.55], [0.90, 0.55], [0.90, 0.95], [0.55, 0.95]],
            "required_ppe": ["helmet"],
        },
    ]
    for zd in zones_data:
        zone, created = get_or_create(
            db, Zone, id=zd["id"],
            defaults={
                "site_id": SITE_ID,
                "org_id": ORG_ID,
                "name": zd["name"],
                "description": zd["description"],
                "zone_type": zd["zone_type"],
                "polygon": zd["polygon"],
                "required_ppe": zd["required_ppe"],
                "status": ZoneStatus.ACTIVE,
            },
        )
        print(f"  Zone: {'CREATED' if created else 'EXISTS'} — {zone.name} ({zd['zone_type'].value})")

    # ---- Cameras ----
    cameras_data = [
        {"id": CAMERA_IDS[0], "name": "CAM-001 Assembly", "zone_id": ZONE_IDS[0], "status": CameraStatus.ONLINE},
        {"id": CAMERA_IDS[1], "name": "CAM-002 Packaging", "zone_id": ZONE_IDS[1], "status": CameraStatus.ONLINE},
        {"id": CAMERA_IDS[2], "name": "CAM-003 Electrical", "zone_id": ZONE_IDS[2], "status": CameraStatus.OFFLINE},
    ]
    for cd in cameras_data:
        cam, created = get_or_create(
            db, Camera, id=cd["id"],
            defaults={
                "site_id": SITE_ID,
                "org_id": ORG_ID,
                "zone_id": cd["zone_id"],
                "name": cd["name"],
                "status": cd["status"],
                "stream_type": "rtsp",
            },
        )
        print(f"  Camera: {'CREATED' if created else 'EXISTS'} — {cam.name} ({cd['status'].value})")

    # ---- Safety Rules ----
    rules_data = [
        {
            "id": RULE_IDS[0],
            "name": "Assembly Zone A — Exclusion Zone Rule",
            "rule_type": RuleType.EXCLUSION_ZONE,
            "severity": RuleSeverity.HIGH,
            "zone_id": ZONE_IDS[0],
            "parameters": {"confidence_threshold": 0.6},
        },
        {
            "id": RULE_IDS[1],
            "name": "Packaging Area — PPE Compliance Rule",
            "rule_type": RuleType.PPE_VIOLATION,
            "severity": RuleSeverity.MEDIUM,
            "zone_id": ZONE_IDS[1],
            "parameters": {"confidence_threshold": 0.5, "required_ppe": ["helmet", "safety_vest", "goggles"]},
        },
        {
            "id": RULE_IDS[2],
            "name": "Global Fire & Smoke Detection Rule",
            "rule_type": RuleType.FIRE_SMOKE,
            "severity": RuleSeverity.CRITICAL,
            "zone_id": None,
            "parameters": {
                "confidence_threshold": 0.50,
                "min_persistence_frames": 2,
                "cooldown_seconds": 60,
                "frame_gap": 15,
            },
        },
    ]
    for rd in rules_data:
        rule, created = get_or_create(
            db, SafetyRule, id=rd["id"],
            defaults={
                "org_id": ORG_ID,
                "zone_id": rd["zone_id"],
                "name": rd["name"],
                "rule_type": rd["rule_type"],
                "severity": rd["severity"],
                "parameters": rd["parameters"],
                "status": RuleStatus.ACTIVE,
            },
        )
        if not created and rd["rule_type"] == RuleType.FIRE_SMOKE:
            rule.parameters = rd["parameters"]
            db.commit()
        print(f"  Rule: {'CREATED' if created else 'EXISTS'} — {rule.name}")

    # ---- Events ----
    events_data = [
        (EventType.PPE_DETECTION, CAMERA_IDS[1], 0.92, 0),
        (EventType.PPE_DETECTION, CAMERA_IDS[1], 0.88, 1),
        (EventType.ZONE_INTRUSION, CAMERA_IDS[0], 0.95, 2),
        (EventType.FIRE_SMOKE, CAMERA_IDS[2], 0.78, 3),
        (EventType.PPE_DETECTION, CAMERA_IDS[1], 0.91, 4),
        (EventType.PERSON_DETECTED, CAMERA_IDS[0], 0.97, 5),
        (EventType.ZONE_INTRUSION, CAMERA_IDS[0], 0.89, 6),
        (EventType.PPE_DETECTION, CAMERA_IDS[0], 0.85, 7),
        (EventType.FIRE_SMOKE, CAMERA_IDS[2], 0.82, 8),
        (EventType.TRACKING_UPDATE, CAMERA_IDS[0], 0.99, 9),
        (EventType.PPE_DETECTION, CAMERA_IDS[1], 0.93, 10),
        (EventType.ZONE_INTRUSION, CAMERA_IDS[0], 0.87, 11),
        (EventType.PERSON_DETECTED, CAMERA_IDS[1], 0.96, 12),
        (EventType.PPE_DETECTION, CAMERA_IDS[0], 0.90, 13),
        (EventType.FIRE_SMOKE, CAMERA_IDS[2], 0.75, 14),
    ]
    events_created = 0
    for event_type, camera_id, confidence, offset_hours in events_data:
        eid = EVENT_IDS[offset_hours]
        ev, created = get_or_create(
            db, Event, id=eid,
            defaults={
                "camera_id": camera_id,
                "org_id": ORG_ID,
                "event_type": event_type,
                "timestamp": NOW - timedelta(hours=offset_hours, minutes=offset_hours * 7),
                "confidence": confidence,
                "detection_data": {
                    "detections": [
                        {"class": event_type.value, "confidence": confidence, "bbox": [100, 200, 300, 400]}
                    ],
                },
            },
        )
        if created:
            events_created += 1
    print(f"  Events: {events_created} created ({len(events_data)} total)")

    # ---- Alerts ----
    alerts_data = [
        {
            "id": ALERT_IDS[0],
            "event_id": EVENT_IDS[2],
            "rule_id": RULE_IDS[0],
            "title": "Restricted Zone Entry — Assembly Zone A",
            "description": "Unauthorized person detected inside restricted Assembly Zone A.",
            "severity": AlertSeverity.HIGH,
            "status": AlertStatus.NEW,
        },
        {
            "id": ALERT_IDS[1],
            "event_id": EVENT_IDS[0],
            "rule_id": RULE_IDS[1],
            "title": "PPE Non-Compliance — Packaging Area",
            "description": "Worker in Packaging Area missing required safety goggles.",
            "severity": AlertSeverity.MEDIUM,
            "status": AlertStatus.ACKNOWLEDGED,
        },
        {
            "id": ALERT_IDS[2],
            "event_id": EVENT_IDS[3],
            "rule_id": None,
            "title": "Fire/Smoke Detection — Electrical Room",
            "description": "Potential fire or smoke detected near high-voltage equipment.",
            "severity": AlertSeverity.CRITICAL,
            "status": AlertStatus.NEW,
        },
        {
            "id": ALERT_IDS[3],
            "event_id": EVENT_IDS[6],
            "rule_id": RULE_IDS[0],
            "title": "Repeated Zone Intrusion — Assembly Zone A",
            "description": "Second zone intrusion detected within 1 hour.",
            "severity": AlertSeverity.HIGH,
            "status": AlertStatus.INVESTIGATING,
        },
        {
            "id": ALERT_IDS[4],
            "event_id": EVENT_IDS[4],
            "rule_id": RULE_IDS[1],
            "title": "PPE Non-Compliance — Packaging Area",
            "description": "Worker missing helmet in Packaging Area.",
            "severity": AlertSeverity.MEDIUM,
            "status": AlertStatus.RESOLVED,
        },
    ]
    alerts_created = 0
    for ad in alerts_data:
        alert, created = get_or_create(
            db, Alert, id=ad["id"],
            defaults={
                "org_id": ORG_ID,
                "event_id": ad["event_id"],
                "rule_id": ad["rule_id"],
                "title": ad["title"],
                "description": ad["description"],
                "severity": ad["severity"],
                "status": ad["status"],
                "metadata_json": {"zone": "Assembly Zone A"},
            },
        )
        if created:
            alerts_created += 1
    print(f"  Alerts: {alerts_created} created ({len(alerts_data)} total)")

    # ---- Patterns ----
    patterns_data = [
        {
            "id": PATTERN_IDS[0],
            "pattern_type": PatternType.TEMPORAL,
            "title": "PPE violations spike during shift change (06:00–07:00)",
            "description": "PPE non-compliance events are 3x more frequent during morning shift change in Packaging Area.",
            "zone_id": ZONE_IDS[1],
            "occurrence_count": 23,
            "confidence_score": 0.87,
            "pattern_data": {
                "peak_hours": ["06:00", "07:00"],
                "affected_zone": "Packaging Area",
                "trend": "increasing",
            },
        },
        {
            "id": PATTERN_IDS[1],
            "pattern_type": PatternType.SPATIAL,
            "title": "Repeated zone intrusions near Assembly Zone A north entrance",
            "description": "70% of zone intrusion events occur at the north entrance of Assembly Zone A.",
            "zone_id": ZONE_IDS[0],
            "occurrence_count": 15,
            "confidence_score": 0.92,
            "pattern_data": {
                "hotspot": "north entrance",
                "affected_zone": "Assembly Zone A",
                "trend": "stable",
            },
        },
        {
            "id": PATTERN_IDS[2],
            "pattern_type": PatternType.TREND,
            "title": "Fire/smoke false positives declining in Electrical Room",
            "description": "After sensor recalibration, fire/smoke false positive rate dropped from 40% to 12%.",
            "zone_id": ZONE_IDS[2],
            "occurrence_count": 8,
            "confidence_score": 0.78,
            "pattern_data": {
                "false_positive_rate_before": 0.40,
                "false_positive_rate_after": 0.12,
                "trend": "decreasing",
            },
        },
    ]
    patterns_created = 0
    for pd_item in patterns_data:
        pat, created = get_or_create(
            db, Pattern, id=pd_item["id"],
            defaults={
                "org_id": ORG_ID,
                "zone_id": pd_item["zone_id"],
                "pattern_type": pd_item["pattern_type"],
                "title": pd_item["title"],
                "description": pd_item["description"],
                "occurrence_count": pd_item["occurrence_count"],
                "confidence_score": pd_item["confidence_score"],
                "pattern_data": pd_item["pattern_data"],
                "status": PatternStatus.ACTIVE,
                "first_detected_at": NOW - timedelta(days=14),
                "last_detected_at": NOW - timedelta(hours=3),
            },
        )
        if created:
            patterns_created += 1
    print(f"  Patterns: {patterns_created} created ({len(patterns_data)} total)")

    db.commit()
    print()
    print("=" * 60)
    print("[OK] Seed complete!")
    print()
    print("Test account:")
    print("  Email:    testmail@gmail.com")
    print("  Password: test@1234")
    print("  Role:     Admin (full access)")
    print("  Org:      SafeVision Demo Corp")
    print("=" * 60)


if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed(db)
    except Exception as e:
        db.rollback()
        print(f"\n[FAILED] Seed failed: {e}")
        raise
    finally:
        db.close()
