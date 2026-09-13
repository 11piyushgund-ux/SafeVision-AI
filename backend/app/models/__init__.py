"""
SafeVision AI — SQLAlchemy ORM Models Package

All models are imported here so Alembic and other consumers can
access them via a single import: `from app.models import *`
"""

# Phase 3 — Auth & RBAC
from app.models.ai_insight import AiInsight, InsightStatus, InsightType  # noqa: F401
from app.models.alert import Alert, AlertSeverity, AlertState, AlertStatus  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.camera import Camera, CameraStatus  # noqa: F401

# Phase 8 — RAG Knowledge Base
from app.models.document import DocumentChunk, DocumentStatus, DocumentType, SafetyDocument  # noqa: F401

# Phase 4 — Event Pipeline
from app.models.event import Event, EventType  # noqa: F401
from app.models.notification import Notification, NotificationChannel, NotificationStatus  # noqa: F401
from app.models.organization import Organization, OrgStatus  # noqa: F401
from app.models.org_notification_settings import OrgNotificationSettings, NotificationMode  # noqa: F401

# Phase 4 — Analytics & Audit
from app.models.pattern import Pattern, PatternStatus, PatternType  # noqa: F401
from app.models.role import Permission, Role  # noqa: F401
from app.models.safety_rule import RuleSeverity, RuleStatus, RuleType, SafetyRule  # noqa: F401

# Phase 4 — Infrastructure
from app.models.site import Site, SiteStatus  # noqa: F401
from app.models.user import User, UserStatus  # noqa: F401
from app.models.zone import Zone, ZoneStatus, ZoneType  # noqa: F401
