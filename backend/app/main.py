"""
SafeVision AI — FastAPI Application Entry Point

This is the main application module. It:
- Creates and configures the FastAPI app instance
- Sets up CORS middleware
- Registers all API routers
- Configures structured logging

Run with: uvicorn app.main:app --reload
"""

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.ai_analysis import router as ai_analysis_router
from app.api.alerts import router as alerts_router
from app.api.auth import router as auth_router
from app.api.cameras import router as cameras_router
from app.api.documents import router as documents_router
from app.api.events import router as events_router
from app.api.health import router as health_router
from app.api.patterns import router as patterns_router
from app.api.stats import router as stats_router
from app.api.users import router as users_router
from app.api.video_stream import router as video_stream_router
from app.api.rules import router as rules_router
from app.api.notifications import router as notifications_router
from app.config import get_settings


def create_app() -> FastAPI:
    """
    Application factory.
    Creates and configures the FastAPI app with all middleware and routers.
    """
    settings = get_settings()

    # --- Configure structured logging ---
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            (
                structlog.dev.ConsoleRenderer()
                if not settings.is_production
                else structlog.processors.JSONRenderer()
            ),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            settings.log_level_int
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    log = structlog.get_logger()

    # --- Create FastAPI app ---
    app = FastAPI(
        title=settings.app_name,
        description=(
            "Multi-tenant industrial safety monitoring platform. "
            "Real-time CV-based detection of PPE violations, fire, smoke, "
            "and zone intrusions with automated alerting and AI insights."
        ),
        version="0.1.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )

    # --- CORS Middleware ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    # --- Register Routers ---
    # System routes (no auth required)
    app.include_router(health_router, prefix="/api")

    # Auth routes (no auth required for login itself)
    app.include_router(auth_router, prefix="/api")

    # Authenticated routes
    app.include_router(users_router, prefix="/api")

    # Phase 7B — Alert Engine
    app.include_router(alerts_router, prefix="/api")

    # Phase 8 — RAG / Knowledge Base
    app.include_router(documents_router, prefix="/api")

    # Phase 9 — AI Analysis
    app.include_router(ai_analysis_router, prefix="/api")

    # Phase 10B — Events, Cameras/Zones, Patterns, Stats
    app.include_router(events_router, prefix="/api")
    app.include_router(cameras_router, prefix="/api")
    app.include_router(patterns_router, prefix="/api")
    app.include_router(stats_router, prefix="/api")

    # Phase 11 — Real Video CV Streaming
    app.include_router(video_stream_router, prefix="/api")

    # Phase 11B — Safety Rules Config
    app.include_router(rules_router, prefix="/api")

    # Phase 15 — Notification Integration
    app.include_router(notifications_router, prefix="/api")

    # --- Startup / Shutdown Events ---
    @app.on_event("startup")
    async def on_startup():
        log.info(
            "safevision_startup",
            app_name=settings.app_name,
            environment=settings.app_env,
            debug=settings.debug,
        )

    @app.on_event("shutdown")
    async def on_shutdown():
        log.info("safevision_shutdown")

    return app


# App instance — used by uvicorn (reloaded with Phase 16 email settings)
app = create_app()

