"""
SafeVision AI — Health Endpoint Tests

Verifies the /api/health endpoint works without any external dependencies.
This is the first test in the project — the CI skeleton runs this.
"""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app


def _mock_db_dependency():
    """
    Override get_db to return a mock session.
    The health endpoint tries to run SELECT 1 — we mock that.
    """
    mock_session = MagicMock(spec=Session)
    # Make execute() succeed (simulates healthy DB)
    mock_session.execute.return_value = None
    try:
        yield mock_session
    finally:
        pass


class TestHealthEndpoint:
    """Tests for GET /api/health."""

    def setup_method(self):
        """Override DB dependency with mock for each test."""
        app.dependency_overrides[get_db] = _mock_db_dependency
        self.client = TestClient(app)

    def teardown_method(self):
        """Remove dependency overrides after each test."""
        app.dependency_overrides.clear()

    def test_health_returns_200(self):
        """Health endpoint should always return 200, even if deps are down."""
        response = self.client.get("/api/health")
        assert response.status_code == 200

    def test_health_response_structure(self):
        """Response must contain status, timestamp, version, environment, dependencies."""
        response = self.client.get("/api/health")
        data = response.json()

        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "environment" in data
        assert "dependencies" in data
        assert isinstance(data["dependencies"], list)

    def test_health_version_matches(self):
        """Version should match the app's current version."""
        response = self.client.get("/api/health")
        data = response.json()
        assert data["version"] == "0.1.0"

    def test_health_reports_db_status(self):
        """Health should report PostgreSQL dependency status."""
        response = self.client.get("/api/health")
        data = response.json()

        dep_names = [d["name"] for d in data["dependencies"]]
        assert "postgresql" in dep_names

    def test_health_status_values(self):
        """Overall status must be one of the defined values."""
        response = self.client.get("/api/health")
        data = response.json()
        assert data["status"] in ("healthy", "degraded", "unhealthy")

    def test_health_dependency_fields(self):
        """Each dependency must have name and status fields."""
        response = self.client.get("/api/health")
        data = response.json()

        for dep in data["dependencies"]:
            assert "name" in dep
            assert "status" in dep
            assert dep["status"] in ("healthy", "unhealthy", "not_configured")
