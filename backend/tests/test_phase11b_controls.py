"""
SafeVision AI — Phase 11B Controls Unit Tests

Tests for:
1. GET /api/rules/controls
2. PUT /api/rules/controls/detection-filter
3. PUT /api/rules/controls/restricted-area
4. Role permissions / RBAC (Viewer cannot update, Owner/Admin can)
"""

import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.main import app
from app.models.organization import Organization
from app.models.role import Role, Permission
from app.models.user import User, UserStatus
from app.models.safety_rule import SafetyRule, RuleType, RuleStatus
from app.services.auth_service import create_access_token

NOW = datetime.now(timezone.utc)

ORG_ID = "t11b00a0-0000-0000-0000-000000000001"
ADMIN_ROLE_ID = "t11b00a0-0000-0000-0000-000000000002"
VIEWER_ROLE_ID = "t11b00a0-0000-0000-0000-000000000003"
ADMIN_USER_ID = "t11b00a0-0000-0000-0000-000000000004"
VIEWER_USER_ID = "t11b00a0-0000-0000-0000-000000000005"


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="module")
def setup_data(db: Session):
    org = db.query(Organization).filter(Organization.id == ORG_ID).first()
    if not org:
        org = Organization(id=ORG_ID, name="Phase 11B Org", slug="p11b-org")
        db.add(org)

    admin_role = db.query(Role).filter(Role.id == ADMIN_ROLE_ID).first()
    if not admin_role:
        admin_role = Role(id=ADMIN_ROLE_ID, org_id=ORG_ID, name="admin")
        db.add(admin_role)

    viewer_role = db.query(Role).filter(Role.id == VIEWER_ROLE_ID).first()
    if not viewer_role:
        viewer_role = Role(id=VIEWER_ROLE_ID, org_id=ORG_ID, name="viewer")
        db.add(viewer_role)

    admin_user = db.query(User).filter(User.id == ADMIN_USER_ID).first()
    if not admin_user:
        admin_user = User(
            id=ADMIN_USER_ID,
            org_id=ORG_ID,
            role_id=ADMIN_ROLE_ID,
            email="admin@phase11b.test",
            name="Admin User",
            pwd_hash="dummy",
            status=UserStatus.ACTIVE,
        )
        db.add(admin_user)

    viewer_user = db.query(User).filter(User.id == VIEWER_USER_ID).first()
    if not viewer_user:
        viewer_user = User(
            id=VIEWER_USER_ID,
            org_id=ORG_ID,
            role_id=VIEWER_ROLE_ID,
            email="viewer@phase11b.test",
            name="Viewer User",
            pwd_hash="dummy",
            status=UserStatus.ACTIVE,
        )
        db.add(viewer_user)

    db.commit()


@pytest.fixture(scope="module")
def admin_headers(db: Session, setup_data):
    token = create_access_token(
        user_id=ADMIN_USER_ID,
        org_id=ORG_ID,
        role_name="admin",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def viewer_headers(db: Session, setup_data):
    token = create_access_token(
        user_id=VIEWER_USER_ID,
        org_id=ORG_ID,
        role_name="viewer",
    )
    return {"Authorization": f"Bearer {token}"}


def test_get_controls_initial(admin_headers):
    client = TestClient(app)
    response = client.get("/api/rules/controls", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "ignored_classes" in data
    assert "restricted_area_enabled" in data


def test_update_detection_filter(admin_headers):
    client = TestClient(app)
    payload = {"ignored_classes": ["helmet", "safety_vest"]}
    response = client.put(
        "/api/rules/controls/detection-filter",
        json=payload,
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "helmet" in data["ignored_classes"]
    assert "safety_vest" in data["ignored_classes"]


def test_update_restricted_area(admin_headers):
    client = TestClient(app)
    payload = {"enabled": True}
    response = client.put(
        "/api/rules/controls/restricted-area",
        json=payload,
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["restricted_area_enabled"] is True

    # Now disable it
    payload = {"enabled": False}
    response = client.put(
        "/api/rules/controls/restricted-area",
        json=payload,
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["restricted_area_enabled"] is False


def test_viewer_cannot_update_controls(viewer_headers):
    client = TestClient(app)
    payload = {"ignored_classes": ["person"]}
    response = client.put(
        "/api/rules/controls/detection-filter",
        json=payload,
        headers=viewer_headers,
    )
    assert response.status_code == 403
