"""
SafeVision AI — AI Analysis API Routes (Phase 9)

Endpoints:
  POST /api/ai/analyze              — Request AI safety analysis
  POST /api/ai/analyze-event/{id}   — Analyze a real persisted event
  GET  /api/ai/insights             — List persisted AI insights (paginated)
  GET  /api/ai/providers            — List available LLM providers + health

All endpoints require authentication and enforce tenant isolation.
API keys are never exposed in responses.
"""

from datetime import datetime, timedelta, timezone
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user, require_permission
from app.models.ai_insight import AiInsight, InsightType
from app.models.camera import Camera
from app.models.event import Event
from app.models.pattern import Pattern, PatternStatus
from app.models.user import User
from app.models.zone import Zone
from app.schemas.ai_analysis import (
    AIAnalysisRequest,
    AIAnalysisResponse,
    AIAnalysisResult,
    AiInsightListResponse,
    AiInsightResponse,
)
from app.services.evidence_service import EvidenceService
from app.services.llm.orchestrator import AIOrchestrator
from app.services.llm.provider_factory import ProviderError, get_provider
from app.services.risk_engine import RiskEngine

router = APIRouter(tags=["AI Analysis"])
log = structlog.get_logger()


# ==============================================================================
# POST /api/ai/analyze — AI Safety Analysis
# ==============================================================================

@router.post(
    "/ai/analyze",
    response_model=AIAnalysisResponse,
    summary="AI Safety Analysis",
    description="Request AI-powered safety event analysis. Requires ai.view permission.",
)
def analyze_safety_event(
    body: AIAnalysisRequest,
    current_user: User = Depends(require_permission("ai.view")),
    db: Session = Depends(get_db),
):
    """
    Run AI safety analysis on a safety event.

    Uses the configured LLM provider to analyze the event with:
    - deterministic risk assessment (consumed as-is)
    - RAG-retrieved safety policy context (org-scoped)
    - historical event context

    Returns a validated structured analysis result.
    """
    risk_assessment = {
        "risk_score": body.risk_score,
        "risk_level": body.risk_level,
        "factors": body.risk_factors,
        "explanation": body.risk_explanation,
    }

    result = AIOrchestrator.analyze(
        org_id=current_user.org_id,
        event_type=body.event_type,
        risk_assessment=risk_assessment,
        event_details=body.event_details,
        camera_id=body.camera_id,
        zone_name=body.zone_name,
        recurrence_count=body.recurrence_count,
        user_query=body.user_query,
        use_rag=body.use_rag,
        rag_top_k=body.rag_top_k,
    )

    if isinstance(result, AIAnalysisResult):
        # Persist to AiInsight table
        created_insight_id: str | None = None
        try:
            meta = result.provider_metadata or {}
            fallback_used = meta.get("fallback_used", False)
            fallback_reason = meta.get("fallback_reason")
            attempted_provider = meta.get("attempted_provider")
            llm_meta = {
                "provider": result.provider,
                "model": result.model,
                "multimodal": False,
                "fallback_used": fallback_used,
            }
            if fallback_reason is not None:
                llm_meta["fallback_reason"] = fallback_reason
            if attempted_provider is not None:
                llm_meta["attempted_provider"] = attempted_provider

            insight = AiInsight(
                org_id=current_user.org_id,
                insight_type=InsightType.SAFETY_ANALYSIS,
                title=result.summary[:500],
                content=result.model_dump_json(),
                query=body.user_query or body.event_type,
                source_context={
                    "event_id": body.event_id,
                    "event_type": body.event_type,
                    "risk_level": body.risk_level,
                },
                llm_metadata=llm_meta,
            )
            db.add(insight)
            db.commit()
            created_insight_id = insight.id
        except Exception as e:
            db.rollback()
            log.warning("insight_persistence_failed", error=str(e))

        return AIAnalysisResponse(
            success=True,
            analysis=result,
            provider=result.provider,
            model=result.model,
            insight_id=created_insight_id,
        )

    # Error case
    error_msg = result.get("error", "Analysis failed")

    # Sanitize error for client — never expose internal details
    safe_error = error_msg
    if "api_key" in error_msg.lower() or "key" in error_msg.lower():
        safe_error = "LLM provider not configured"

    return AIAnalysisResponse(
        success=False,
        error=safe_error,
        provider=result.get("provider"),
        model=result.get("model"),
    )


def _require_ai_permission(current_user: User = Depends(get_current_user)) -> User:
    if not (current_user.has_permission("ai.view") or current_user.has_permission("ai.analyze")):
        raise HTTPException(
            status_code=403,
            detail="Permission 'ai.view' or 'ai.analyze' required",
        )
    return current_user


# ==============================================================================
# POST /api/ai/analyze-event/{event_id} — Real Event AI Analysis
# ==============================================================================

@router.post(
    "/ai/analyze-event/{event_id}",
    response_model=AIAnalysisResponse,
    summary="Analyze Event with AI",
    description="Run AI safety analysis directly on a real persisted Safety Event using its deterministic risk assessment.",
)
def analyze_real_event(
    event_id: str,
    current_user: User = Depends(_require_ai_permission),
    db: Session = Depends(get_db),
):
    """
    Directly analyze an existing Safety Event.
    Resolves real deterministic RiskAssessment from the event row or RiskEngine.
    Enforces tenant isolation and passes authentic risk scores to AIOrchestrator.
    """
    event = (
        db.query(Event)
        .filter(Event.id == event_id, Event.org_id == current_user.org_id)
        .first()
    )
    if not event:
        raise HTTPException(
            status_code=404,
            detail=f"Safety Event {event_id} not found in your organization",
        )

    # 1. Resolve authentic RiskAssessment (never synthesized or estimated)
    risk_data = None
    if event.detection_data and "risk_assessment" in event.detection_data:
        risk_data = event.detection_data["risk_assessment"]
    else:
        # Compute on-the-fly via real RiskEngine
        risk_obj = RiskEngine.assess_with_db(event=event, db=db, lookback_hours=24)
        risk_data = {
            "risk_score": risk_obj.risk_score,
            "risk_level": risk_obj.risk_level,
            "factors": [f.model_dump() for f in risk_obj.factors],
            "explanation": risk_obj.explanation,
        }

    # 2. Resolve zone name if available
    zone_name = None
    camera = db.query(Camera).filter(Camera.id == event.camera_id).first()
    if camera and camera.zone_id:
        zone = db.query(Zone).filter(Zone.id == camera.zone_id).first()
        if zone:
            zone_name = zone.name

    event_type_str = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)

    # 3. Query historical context (Phase 14e: 30-day lookback, same org + event_type, exclude current)
    lookback_start = datetime.now(timezone.utc) - timedelta(days=30)

    recurrence_count = (
        db.query(func.count(Event.id))
        .filter(
            Event.org_id == current_user.org_id,
            Event.event_type == event.event_type,
            Event.id != event.id,
            Event.timestamp >= lookback_start,
        )
        .scalar()
    ) or 0

    recent_event_rows = (
        db.query(Event)
        .filter(
            Event.org_id == current_user.org_id,
            Event.event_type == event.event_type,
            Event.id != event.id,
            Event.timestamp >= lookback_start,
        )
        .order_by(Event.timestamp.desc())
        .limit(5)
        .all()
    )

    recent_events = [
        {
            "event_type": (e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type)),
            "created_at": e.timestamp.isoformat() if e.timestamp else "unknown",
            "severity": (e.detection_data or {}).get("risk_assessment", {}).get("risk_level", "unknown"),
            "camera_id": e.camera_id,
        }
        for e in recent_event_rows
    ]

    # Query active pattern for this event type and org (Phase 14e)
    pattern_summary = None
    try:
        patterns = (
            db.query(Pattern)
            .filter(
                Pattern.org_id == current_user.org_id,
                Pattern.status == PatternStatus.ACTIVE,
            )
            .order_by(Pattern.last_detected_at.desc())
            .all()
        )
        for p in patterns:
            p_data = p.pattern_data or {}
            if p_data.get("event_type") == event_type_str:
                pattern_summary = {
                    "occurrence_count": p.occurrence_count,
                    "confidence_score": p.confidence_score,
                    "first_detected_at": p.first_detected_at.isoformat() if p.first_detected_at else "",
                    "last_detected_at": p.last_detected_at.isoformat() if p.last_detected_at else "",
                    "title": p.title,
                }
                break
    except Exception as e:
        log.warning("pattern_query_failed", error=str(e))

    # 4. Load evidence image for multimodal analysis (Phase 14, non-fatal)
    evidence_image: bytes | None = None
    if event.evidence_path:
        try:
            resolved = EvidenceService.resolve_evidence_path(
                evidence_path=event.evidence_path,
                org_id=current_user.org_id,
            )
            if resolved and resolved.is_file():
                evidence_image = resolved.read_bytes()
                log.info(
                    "evidence_image_loaded",
                    event_id=event_id,
                    bytes=len(evidence_image),
                )
        except Exception as e:
            log.warning("evidence_image_load_failed", event_id=event_id, error=str(e))
            # Continue with text-only analysis

    # 5. Call AI Orchestrator with authentic risk assessment + evidence + history
    result = AIOrchestrator.analyze(
        org_id=current_user.org_id,
        event_type=event_type_str,
        risk_assessment={
            "risk_score": risk_data["risk_score"],
            "risk_level": risk_data["risk_level"],
            "factors": risk_data.get("factors", []),
            "explanation": risk_data.get("explanation", ""),
        },
        event_details=event.detection_data or {},
        camera_id=event.camera_id,
        zone_name=zone_name,
        recurrence_count=recurrence_count,
        recent_events=recent_events,
        pattern_summary=pattern_summary,
        use_rag=True,
        rag_top_k=5,
        evidence_image=evidence_image,
    )

    if isinstance(result, AIAnalysisResult):
        created_insight_id: str | None = None
        try:
            meta = result.provider_metadata or {}
            fallback_used = meta.get("fallback_used", False)
            fallback_reason = meta.get("fallback_reason")
            attempted_provider = meta.get("attempted_provider")
            is_multimodal = (evidence_image is not None) and not fallback_used

            llm_metadata = {
                "provider": result.provider,
                "model": result.model,
                "multimodal": is_multimodal,
                "fallback_used": fallback_used,
            }
            if fallback_reason is not None:
                llm_metadata["fallback_reason"] = fallback_reason
            if attempted_provider is not None:
                llm_metadata["attempted_provider"] = attempted_provider

            insight = AiInsight(
                org_id=current_user.org_id,
                insight_type=InsightType.SAFETY_ANALYSIS,
                title=result.summary[:500],
                content=result.model_dump_json(),
                query=f"Analysis of {event_type_str}",
                source_context={
                    "event_id": event.id,
                    "event_type": event_type_str,
                    "risk_level": risk_data["risk_level"],
                    "risk_score": risk_data["risk_score"],
                    "evidence_path": event.evidence_path,
                },
                llm_metadata=llm_metadata,
            )
            db.add(insight)
            db.commit()
            created_insight_id = insight.id
        except Exception as e:
            db.rollback()
            log.warning("insight_persistence_failed", error=str(e))

        return AIAnalysisResponse(
            success=True,
            analysis=result,
            provider=result.provider,
            model=result.model,
            insight_id=created_insight_id,
        )


    error_msg = result.get("error", "Analysis failed")
    safe_error = error_msg
    if "api_key" in error_msg.lower() or "key" in error_msg.lower():
        safe_error = "LLM provider not configured"

    return AIAnalysisResponse(
        success=False,
        error=safe_error,
        provider=result.get("provider"),
        model=result.get("model"),
    )


# ==============================================================================
# GET /api/ai/insights — List Persisted AI Insights
# ==============================================================================

@router.get(
    "/ai/insights",
    response_model=AiInsightListResponse,
    summary="List AI Insights",
    description="Paginated list of persisted AI safety insights. Excludes mock/test records.",
)
def list_insights(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Page size"),
    sort: str = Query("newest", description="Sort order: newest, oldest, highest_risk"),
    current_user: User = Depends(_require_ai_permission),
    db: Session = Depends(get_db),
):
    """Return paginated AI insights for the current tenant.

    - Enforces org_id tenant isolation.
    - Excludes mock/test insights (provider='mock').
    - org_id is NOT included in the response.
    """
    base_q = (
        db.query(AiInsight)
        .filter(AiInsight.org_id == current_user.org_id)
        .filter(
            ~AiInsight.llm_metadata["provider"].astext.in_(["mock"])
        )
    )

    total = base_q.count()

    # Sort
    if sort == "oldest":
        base_q = base_q.order_by(AiInsight.created_at.asc())
    elif sort == "highest_risk":
        # Sort by risk_score descending (stored in source_context JSONB)
        from sqlalchemy import Float, cast
        base_q = (
            db.query(AiInsight)
            .filter(AiInsight.org_id == current_user.org_id)
            .filter(
                ~AiInsight.llm_metadata["provider"].astext.in_(["mock"])
            )
            .order_by(
                cast(
                    AiInsight.source_context["risk_score"].astext,
                    Float,
                ).desc().nullslast()
            )
        )
    else:  # newest (default)
        base_q = base_q.order_by(AiInsight.created_at.desc())

    offset = (page - 1) * size
    rows = base_q.offset(offset).limit(size).all()

    data = [
        AiInsightResponse(
            id=row.id,
            insight_type=row.insight_type.value if hasattr(row.insight_type, "value") else str(row.insight_type),
            title=row.title,
            content=row.content,
            query=row.query,
            source_context=row.source_context,
            llm_metadata=row.llm_metadata,
            status=row.status.value if hasattr(row.status, "value") else str(row.status),
            created_at=row.created_at,
        )
        for row in rows
    ]

    return AiInsightListResponse(
        data=data,
        total=total,
        page=page,
        size=size,
    )


# ==============================================================================
# GET /api/ai/providers — List LLM Providers
# ==============================================================================

@router.get(
    "/ai/providers",
    summary="List LLM Providers",
    description="List available LLM providers and their health status.",
)
def list_providers(
    current_user: User = Depends(_require_ai_permission),
):
    """List available LLM providers and their configuration status."""
    from app.config import get_settings

    settings = get_settings()

    providers = []
    for name in ["gemini", "ollama", "openrouter"]:
        try:
            provider = get_provider(name)
            healthy = provider.health_check()
            providers.append({
                "name": name,
                "model": provider.model_name,
                "available": healthy,
                "is_primary": name == settings.llm_primary_provider,
                "is_fallback": name == settings.llm_fallback_provider,
            })
        except ProviderError:
            providers.append({
                "name": name,
                "model": "unknown",
                "available": False,
                "is_primary": False,
                "is_fallback": False,
            })

    return {
        "active_provider": settings.llm_provider,
        "mode": settings.llm_mode,
        "providers": providers,
    }

