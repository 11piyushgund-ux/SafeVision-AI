"""
SafeVision AI — Health Check Endpoint

Reports the health status of the application and its dependencies.
This is the first endpoint built — verifies the skeleton is alive.
In later phases, this will also check: DB, Redis, CV service, LLM API.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db

router = APIRouter(tags=["System"])


class DependencyStatus(BaseModel):
    """Status of an individual dependency."""
    name: str
    status: str  # "healthy" | "unhealthy" | "not_configured"
    latency_ms: float | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str  # "healthy" | "degraded" | "unhealthy"
    timestamp: str
    version: str
    environment: str
    dependencies: list[DependencyStatus]


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System Health Check",
    description="Returns the health status of the application and its dependencies.",
)
def health_check(db: Session = Depends(get_db)):
    """
    Check the health of all system dependencies.
    Returns overall status based on dependency health.
    """
    settings = get_settings()
    dependencies: list[DependencyStatus] = []

    # --- Check PostgreSQL ---
    db_status = _check_database(db)
    dependencies.append(db_status)

    # --- Check Redis (basic — will be expanded in later phases) ---
    redis_status = _check_redis(settings.redis_url)
    dependencies.append(redis_status)

    # --- Determine overall status ---
    statuses = [d.status for d in dependencies]
    if all(s == "healthy" for s in statuses):
        overall = "healthy"
    elif any(s == "unhealthy" for s in statuses):
        overall = "degraded"
    else:
        overall = "healthy"  # not_configured deps don't degrade health

    return HealthResponse(
        status=overall,
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="0.1.0",
        environment=settings.app_env,
        dependencies=dependencies,
    )


def _check_database(db: Session) -> DependencyStatus:
    """Check PostgreSQL connectivity."""
    import time
    start = time.perf_counter()
    try:
        db.execute(text("SELECT 1"))
        latency = (time.perf_counter() - start) * 1000
        return DependencyStatus(
            name="postgresql",
            status="healthy",
            latency_ms=round(latency, 2),
        )
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return DependencyStatus(
            name="postgresql",
            status="unhealthy",
            latency_ms=round(latency, 2),
            error=str(e),
        )


def _check_redis(redis_url: str) -> DependencyStatus:
    """Check Redis connectivity."""
    import time
    try:
        import redis as redis_lib
        start = time.perf_counter()
        r = redis_lib.from_url(redis_url, socket_connect_timeout=2)
        r.ping()
        latency = (time.perf_counter() - start) * 1000
        r.close()
        return DependencyStatus(
            name="redis",
            status="healthy",
            latency_ms=round(latency, 2),
        )
    except ImportError:
        return DependencyStatus(
            name="redis",
            status="not_configured",
            error="redis package not installed",
        )
    except Exception as e:
        return DependencyStatus(
            name="redis",
            status="unhealthy",
            error=str(e),
        )
