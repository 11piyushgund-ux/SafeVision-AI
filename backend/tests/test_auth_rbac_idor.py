"""
SafeVision AI — Auth, RBAC, and IDOR Test Suite

Tests cover:
1. Authentication (login, JWT, expired tokens, wrong passwords)
2. RBAC (permission checks per role)
3. IDOR (cross-org access attempts must fail with 403/404)

Uses a real test database with two isolated organizations to prove
tenant isolation works at every level.
"""

import uuid
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.database import get_db
from app.main import app
from app.models.organization import Organization
from app.models.role import Permission, Role
from app.models.user import User
from app.services.auth_service import create_access_token, hash_password

# ==============================================================================
# Test Database Setup
# ==============================================================================

settings = get_settings()
test_engine = create_engine(settings.database_url, echo=False)
TestSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


def _override_get_db():
    """Override get_db to use the test session."""
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


# Override the DB dependency for all tests
app.dependency_overrides[get_db] = _override_get_db
client = TestClient(app)


# ==============================================================================
# Test Data Helpers
# ==============================================================================

def _create_org(db: Session, name: str, slug: str) -> Organization:
    """Create a test organization."""
    org = Organization(
        id=str(uuid.uuid4()),
        name=name,
        slug=slug,
    )
    db.add(org)
    db.flush()
    return org


def _create_role(db: Session, org_id: str, name: str, permissions: list[str]) -> Role:
    """Create a role with specific permissions."""
    role = Role(
        id=str(uuid.uuid4()),
        name=name,
        org_id=org_id,
    )
    db.add(role)
    db.flush()

    for perm_name in permissions:
        perm = Permission(
            id=str(uuid.uuid4()),
            role_id=role.id,
            perm_name=perm_name,
        )
        db.add(perm)

    db.flush()
    return role


def _create_user(
    db: Session,
    org_id: str,
    role_id: str,
    email: str,
    name: str = "Test User",
    password: str = "testpassword123",
) -> User:
    """Create a test user with hashed password."""
    user = User(
        id=str(uuid.uuid4()),
        org_id=org_id,
        email=email,
        name=name,
        pwd_hash=hash_password(password),
        role_id=role_id,
    )
    db.add(user)
    db.flush()
    return user


def _login(email: str, password: str = "testpassword123") -> str | None:
    """Login and return the access token, or None if login fails."""
    resp = client.post("/api/auth/login", json={
        "email": email,
        "password": password,
    })
    if resp.status_code == 200:
        return resp.json()["access_token"]
    return None


def _auth_header(token: str) -> dict:
    """Return the Authorization header for a given token."""
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# Fixture: Two Isolated Organizations
# Store ONLY scalar IDs/emails — never live ORM instances — to avoid
# DetachedInstanceError when the setup session closes.
# ==============================================================================

_test_data: dict = {}


def _setup_test_data():
    """Create two orgs with users at different permission levels."""
    if _test_data:
        return  # Already set up

    db = TestSession()
    try:
        # --- ORG A ---
        org_a = _create_org(db, f"Test Org A {uuid.uuid4().hex[:6]}", f"test-org-a-{uuid.uuid4().hex[:6]}")

        admin_role_a = _create_role(db, org_a.id, "Admin", [
            "users.view", "users.manage",
            "events.view", "alerts.view", "alerts.acknowledge",
            "alerts.escalate", "alerts.resolve",
            "zones.manage", "cameras.manage",
            "reports.export", "ai.view", "ai.manage",
        ])
        viewer_role_a = _create_role(db, org_a.id, "Viewer", [
            "events.view", "alerts.view", "ai.view",
        ])

        admin_a = _create_user(db, org_a.id, admin_role_a.id, f"admin-a-{uuid.uuid4().hex[:6]}@test.com", "Admin A")
        viewer_a = _create_user(db, org_a.id, viewer_role_a.id, f"viewer-a-{uuid.uuid4().hex[:6]}@test.com", "Viewer A")

        # --- ORG B ---
        org_b = _create_org(db, f"Test Org B {uuid.uuid4().hex[:6]}", f"test-org-b-{uuid.uuid4().hex[:6]}")

        admin_role_b = _create_role(db, org_b.id, "Admin", [
            "users.view", "users.manage",
            "events.view", "alerts.view", "alerts.acknowledge",
            "alerts.escalate", "alerts.resolve",
            "zones.manage", "cameras.manage",
            "reports.export", "ai.view", "ai.manage",
        ])

        admin_b = _create_user(db, org_b.id, admin_role_b.id, f"admin-b-{uuid.uuid4().hex[:6]}@test.com", "Admin B")

        db.commit()

        # Store ONLY scalar values — no ORM instances
        _test_data["org_a_id"] = org_a.id
        _test_data["org_b_id"] = org_b.id
        _test_data["admin_a_id"] = admin_a.id
        _test_data["viewer_a_id"] = viewer_a.id
        _test_data["admin_b_id"] = admin_b.id
        _test_data["admin_a_email"] = admin_a.email
        _test_data["viewer_a_email"] = viewer_a.email
        _test_data["admin_b_email"] = admin_b.email
        _test_data["viewer_role_a_id"] = viewer_role_a.id

    finally:
        db.close()


# ==============================================================================
# Auth Tests
# ==============================================================================

class TestAuth:
    """Tests for authentication (login, JWT, token validation)."""

    def setup_method(self):
        _setup_test_data()

    def test_login_success(self):
        """Valid credentials should return a JWT token."""
        resp = client.post("/api/auth/login", json={
            "email": _test_data["admin_a_email"],
            "password": "testpassword123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["email"] == _test_data["admin_a_email"]

    def test_login_wrong_password(self):
        """Wrong password should return 401 with generic message."""
        resp = client.post("/api/auth/login", json={
            "email": _test_data["admin_a_email"],
            "password": "wrongpassword",
        })
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid email or password"

    def test_login_nonexistent_email(self):
        """Nonexistent email should return 401 with the SAME generic message (no enumeration)."""
        resp = client.post("/api/auth/login", json={
            "email": "nonexistent@test.com",
            "password": "testpassword123",
        })
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid email or password"

    def test_login_returns_org_id(self):
        """Login response should include the user's org_id (server-resolved)."""
        resp = client.post("/api/auth/login", json={
            "email": _test_data["admin_a_email"],
            "password": "testpassword123",
        })
        data = resp.json()
        assert data["user"]["org_id"] == _test_data["org_a_id"]

    def test_no_token_returns_error(self):
        """Requests without a token should be rejected."""
        resp = client.get("/api/users/me")
        # HTTPBearer returns 403 when no Authorization header is present
        assert resp.status_code in (401, 403)

    def test_invalid_token_returns_401(self):
        """Invalid JWT should return 401."""
        resp = client.get("/api/users/me", headers=_auth_header("invalid.token.here"))
        assert resp.status_code == 401

    def test_expired_token_returns_401(self):
        """Expired JWT should return 401."""
        token = create_access_token(
            user_id=_test_data["admin_a_id"],
            org_id=_test_data["org_a_id"],
            role_name="Admin",
            expires_delta=timedelta(seconds=-10),  # Already expired
        )
        resp = client.get("/api/users/me", headers=_auth_header(token))
        assert resp.status_code == 401

    def test_get_me_returns_current_user(self):
        """GET /api/users/me should return the authenticated user's profile."""
        token = _login(_test_data["admin_a_email"])
        assert token is not None

        resp = client.get("/api/users/me", headers=_auth_header(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == _test_data["admin_a_email"]
        assert data["org_id"] == _test_data["org_a_id"]
        # Password hash must NEVER appear in response
        assert "pwd_hash" not in data
        assert "password" not in data


# ==============================================================================
# RBAC Tests
# ==============================================================================

class TestRBAC:
    """Tests for role-based access control (permission enforcement)."""

    def setup_method(self):
        _setup_test_data()

    def test_admin_can_list_users(self):
        """Admin (with users.view) should be able to list users."""
        token = _login(_test_data["admin_a_email"])
        resp = client.get("/api/users", headers=_auth_header(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data

    def test_viewer_cannot_list_users(self):
        """Viewer (without users.view) should get 403 on list users."""
        token = _login(_test_data["viewer_a_email"])
        resp = client.get("/api/users", headers=_auth_header(token))
        assert resp.status_code == 403
        assert "users.view" in resp.json()["detail"]

    def test_admin_can_create_user(self):
        """Admin (with users.manage) should be able to create users."""
        token = _login(_test_data["admin_a_email"])
        role_id = _test_data["viewer_role_a_id"]

        new_email = f"newuser-{uuid.uuid4().hex[:6]}@test.com"
        resp = client.post("/api/users", json={
            "email": new_email,
            "name": "New Test User",
            "password": "securepassword123",
            "role_id": role_id,
        }, headers=_auth_header(token))
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == new_email
        assert data["org_id"] == _test_data["org_a_id"]

    def test_viewer_cannot_create_user(self):
        """Viewer (without users.manage) should get 403 on create user."""
        token = _login(_test_data["viewer_a_email"])
        resp = client.post("/api/users", json={
            "email": "blocked@test.com",
            "name": "Blocked",
            "password": "password123",
            "role_id": "any-id",
        }, headers=_auth_header(token))
        assert resp.status_code == 403
        assert "users.manage" in resp.json()["detail"]

    def test_admin_can_view_specific_user(self):
        """Admin can view a user in their org by ID."""
        token = _login(_test_data["admin_a_email"])
        user_id = _test_data["viewer_a_id"]
        resp = client.get(f"/api/users/{user_id}", headers=_auth_header(token))
        assert resp.status_code == 200
        assert resp.json()["id"] == user_id


# ==============================================================================
# IDOR Tests (Cross-Organization Isolation)
# ==============================================================================

class TestIDOR:
    """
    Tests proving tenant isolation:
    - Org A admin cannot see Org B's users
    - Org B admin cannot see Org A's users
    - Cross-org user creation is impossible
    - Cross-org role assignment is impossible
    """

    def setup_method(self):
        _setup_test_data()

    def test_org_a_cannot_see_org_b_users(self):
        """Admin from Org A should get 404 when requesting Org B user by ID."""
        token_a = _login(_test_data["admin_a_email"])
        user_b_id = _test_data["admin_b_id"]

        resp = client.get(f"/api/users/{user_b_id}", headers=_auth_header(token_a))
        # Must be 404, not 200 or 403 — don't even confirm the resource exists
        assert resp.status_code == 404

    def test_org_b_cannot_see_org_a_users(self):
        """Admin from Org B should get 404 when requesting Org A user by ID."""
        token_b = _login(_test_data["admin_b_email"])
        user_a_id = _test_data["admin_a_id"]

        resp = client.get(f"/api/users/{user_a_id}", headers=_auth_header(token_b))
        assert resp.status_code == 404

    def test_org_a_user_list_only_shows_org_a(self):
        """User list from Org A should never contain Org B users."""
        token_a = _login(_test_data["admin_a_email"])
        resp = client.get("/api/users", headers=_auth_header(token_a))
        assert resp.status_code == 200

        data = resp.json()
        org_a_id = _test_data["org_a_id"]
        for user in data["data"]:
            assert user["org_id"] == org_a_id, \
                f"IDOR VIOLATION: User {user['id']} from org {user['org_id']} leaked into org {org_a_id}"

    def test_org_b_user_list_only_shows_org_b(self):
        """User list from Org B should never contain Org A users."""
        token_b = _login(_test_data["admin_b_email"])
        resp = client.get("/api/users", headers=_auth_header(token_b))
        assert resp.status_code == 200

        data = resp.json()
        org_b_id = _test_data["org_b_id"]
        for user in data["data"]:
            assert user["org_id"] == org_b_id, \
                f"IDOR VIOLATION: User {user['id']} from org {user['org_id']} leaked into org {org_b_id}"

    def test_cannot_create_user_with_cross_org_role(self):
        """
        Admin from Org A should NOT be able to assign a role from Org B
        to a new user — this would be a cross-org privilege escalation.
        """
        token_a = _login(_test_data["admin_a_email"])

        # Get a role from Org B
        db = TestSession()
        try:
            role_b = db.query(Role).filter(
                Role.org_id == _test_data["org_b_id"],
            ).first()
            role_b_id = role_b.id
        finally:
            db.close()

        resp = client.post("/api/users", json={
            "email": f"crossorg-{uuid.uuid4().hex[:6]}@test.com",
            "name": "Cross-Org Attack",
            "password": "password123",
            "role_id": role_b_id,  # Role from Org B!
        }, headers=_auth_header(token_a))

        # Must be 400 — the role doesn't belong to Org A
        assert resp.status_code == 400
        assert "Invalid role_id" in resp.json()["detail"]

    def test_token_org_mismatch_rejected(self):
        """
        A token with a forged org_id (doesn't match the user's actual org)
        should be rejected.
        """
        # Create a token with Org B's ID but for Org A's user
        forged_token = create_access_token(
            user_id=_test_data["admin_a_id"],
            org_id=_test_data["org_b_id"],  # Wrong org!
            role_name="Admin",
        )
        resp = client.get("/api/users/me", headers=_auth_header(forged_token))
        assert resp.status_code == 401
        assert "mismatch" in resp.json()["detail"].lower()

    def test_nonexistent_user_id_returns_404(self):
        """Requesting a user with a random UUID should return 404, not 500."""
        token_a = _login(_test_data["admin_a_email"])
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/users/{fake_id}", headers=_auth_header(token_a))
        assert resp.status_code == 404
