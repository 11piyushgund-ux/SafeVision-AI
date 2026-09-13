"""
SafeVision AI — Test Configuration & Fixtures

Shared pytest fixtures for all tests. Provides:
- A test FastAPI client (no real DB needed for unit tests)
- Database session overrides for integration tests
- Helper factories for creating test data
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    """
    FastAPI test client.
    Uses the real app instance but does NOT hit a real database
    unless explicitly configured for integration tests.

    For unit tests: override the get_db dependency in individual tests.
    For integration tests: a test database will be configured in Phase 3+.
    """
    with TestClient(app) as c:
        yield c
