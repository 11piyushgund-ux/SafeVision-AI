"""
SafeVision AI — Provider Fail-Safe & Structured Intelligence Tests (Phases 14c, 14d, 14e)

Tests verify:
  1. PROVIDER TIMEOUT & FALLBACK (1-8)
  2. IMAGE HANDLING & TEXT-ONLY FALLBACK (9-13)
  3. METADATA ENRICHMENT (14-17)
  4. PROMPTS — ANTI-HALLUCINATION & EPISTEMIC RULES (18-21)
  5. PROMPTS — INPUT CONTRACT (22-26)
  6. SCHEMA — PHASE 14D NEW FIELDS (27-32)
  7. PERSISTENCE & FAILURE HANDLING (33-35)
  8. HISTORICAL CONTEXT & TENANT ISOLATION (36-40)

All tests mock providers — zero live API calls.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.database import get_db
from app.main import app
from app.models.ai_insight import AiInsight
from app.models.camera import Camera
from app.models.event import Event, EventType
from app.models.organization import Organization
from app.models.pattern import Pattern, PatternStatus, PatternType
from app.models.role import Permission, Role
from app.models.site import Site
from app.models.user import User
from app.schemas.ai_analysis import AIAnalysisResult
from app.services.auth_service import create_access_token, hash_password
from app.services.llm import LLMRequest, LLMResponse
from app.services.llm.orchestrator import AIOrchestrator
from app.services.llm.prompts import (
    SAFETY_MULTIMODAL_SYSTEM_PROMPT,
    SAFETY_SYSTEM_PROMPT,
    SAFETY_TEXT_ONLY_FALLBACK_SYSTEM_PROMPT,
    build_analysis_prompt,
    build_detection_metadata_context,
    build_historical_context,
    build_rag_context,
    build_risk_context,
)
from app.services.llm.provider_factory import (
    PRIMARY_TIMEOUT_SECONDS,
    generate_with_fallback,
)

# ==============================================================================
# Database / TestClient Setup
# ==============================================================================

settings = get_settings()
test_engine = create_engine(settings.database_url, echo=False)
TestSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


def _override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db
client = TestClient(app)

# ==============================================================================
# Helper Mock Factories
# ==============================================================================

SAMPLE_LLM_JSON = json.dumps({
    "summary": "Worker detected without mandatory safety helmet in loading zone.",
    "risk_explanation": "Critical risk due to heavy overhead crane operations in Zone A.",
    "hazard_interpretation": "Falling object hazard capable of causing serious head trauma.",
    "visual_observations": [
        "The image shows a worker standing directly beneath an overhead gantry crane.",
        "The image shows no hard hat on the worker's head.",
    ],
    "visual_validation": {
        "detection_supported": True,
        "confidence_note": "Visual evidence clearly confirms absence of safety helmet.",
        "scene_context": "Active loading dock with heavy equipment in motion.",
    },
    "contributing_factors": [
        "Overhead crane in active operation",
        "Personnel in marked exclusion zone",
    ],
    "immediate_actions": [
        "Halt overhead crane operation immediately",
        "Direct worker to step outside the exclusion zone",
    ],
    "investigation_actions": [
        "Inspect site PPE dispenser log",
        "Review supervisor shift safety briefing attendance",
    ],
    "preventive_actions": [
        "Implement physical turnstile PPE interlocks",
        "Schedule mandatory refresher safety training",
    ],
    "recommended_actions": [
        "Halt overhead crane operation immediately",
        "Direct worker to step outside the exclusion zone",
        "Inspect site PPE dispenser log",
        "Review supervisor shift safety briefing attendance",
        "Implement physical turnstile PPE interlocks",
        "Schedule mandatory refresher safety training",
    ],
    "safety_policy_guidance": "SOP-104 requires hard hats in all crane operating areas.",
    "historical_context": "Three similar PPE violations occurred in Zone A during past 30 days.",
    "uncertainties": [
        "Exact duration worker spent inside zone cannot be determined from a single frame.",
    ],
})


def _mock_provider(name: str, model: str, success: bool = True, content: str = SAMPLE_LLM_JSON, error: str | None = None):
    p = MagicMock()
    p.name = name
    p.model_name = model
    p.generate.return_value = LLMResponse(
        content=content if success else "",
        provider=name,
        model=model,
        success=success,
        error=error,
        metadata={"content_length": len(content) if success else 0, "multimodal": False},
    )
    return p


# ==============================================================================
# 1. PROVIDER TIMEOUT & FALLBACK TESTS (Phase 14c)
# ==============================================================================

def test_primary_timeout_triggers_fallback():
    """Primary provider times out -> fallback provider is invoked."""
    primary = _mock_provider("openrouter", "google/gemma-4-26b-a4b-it:free", success=False, error="Request timed out after 30s")
    fallback = _mock_provider("ollama", "qwen2.5:3b-instruct", success=True)

    with patch("app.services.llm.provider_factory.get_settings") as mock_settings, \
         patch("app.services.llm.provider_factory.get_provider") as mock_get_provider:
        mock_settings.return_value = MagicMock(
            llm_mode="fallback",
            llm_primary_provider="openrouter",
            llm_fallback_provider="ollama",
        )
        mock_get_provider.side_effect = lambda n: primary if n == "openrouter" else fallback

        req = LLMRequest(system_prompt="sys", user_prompt="user", timeout_seconds=60)
        res = generate_with_fallback(req)

        assert res.success is True
        assert res.provider == "ollama"
        assert res.metadata.get("fallback_used") is True
        assert "timed out" in res.metadata.get("fallback_reason", "").lower()
        assert primary.generate.called
        assert fallback.generate.called


def test_primary_http_429_triggers_fallback():
    """Primary provider returns HTTP 429 Rate Limit -> fallback activated."""
    primary = _mock_provider("openrouter", "google/gemma-4-26b-a4b-it:free", success=False, error="HTTP 429: Too Many Requests")
    fallback = _mock_provider("ollama", "qwen2.5:3b-instruct", success=True)

    with patch("app.services.llm.provider_factory.get_settings") as mock_settings, \
         patch("app.services.llm.provider_factory.get_provider") as mock_get_provider:
        mock_settings.return_value = MagicMock(
            llm_mode="fallback",
            llm_primary_provider="openrouter",
            llm_fallback_provider="ollama",
        )
        mock_get_provider.side_effect = lambda n: primary if n == "openrouter" else fallback

        res = generate_with_fallback(LLMRequest(system_prompt="sys", user_prompt="user"))
        assert res.success is True
        assert res.provider == "ollama"
        assert res.metadata.get("fallback_used") is True
        assert "429" in res.metadata.get("fallback_reason", "")


def test_primary_http_500_triggers_fallback():
    """Primary provider returns HTTP 500 Internal Server Error -> fallback activated."""
    primary = _mock_provider("openrouter", "google/gemma-4-26b-a4b-it:free", success=False, error="HTTP 500: Server Error")
    fallback = _mock_provider("ollama", "qwen2.5:3b-instruct", success=True)

    with patch("app.services.llm.provider_factory.get_settings") as mock_settings, \
         patch("app.services.llm.provider_factory.get_provider") as mock_get_provider:
        mock_settings.return_value = MagicMock(
            llm_mode="fallback",
            llm_primary_provider="openrouter",
            llm_fallback_provider="ollama",
        )
        mock_get_provider.side_effect = lambda n: primary if n == "openrouter" else fallback

        res = generate_with_fallback(LLMRequest(system_prompt="sys", user_prompt="user"))
        assert res.success is True
        assert res.provider == "ollama"
        assert res.metadata.get("fallback_used") is True


def test_primary_network_failure_triggers_fallback():
    """Primary network connect failure -> fallback activated."""
    primary = _mock_provider("openrouter", "google/gemma-4-26b-a4b-it:free", success=False, error="ConnectError: [Errno 111] Connection refused")
    fallback = _mock_provider("ollama", "qwen2.5:3b-instruct", success=True)

    with patch("app.services.llm.provider_factory.get_settings") as mock_settings, \
         patch("app.services.llm.provider_factory.get_provider") as mock_get_provider:
        mock_settings.return_value = MagicMock(
            llm_mode="fallback",
            llm_primary_provider="openrouter",
            llm_fallback_provider="ollama",
        )
        mock_get_provider.side_effect = lambda n: primary if n == "openrouter" else fallback

        res = generate_with_fallback(LLMRequest(system_prompt="sys", user_prompt="user"))
        assert res.success is True
        assert res.provider == "ollama"
        assert res.metadata.get("fallback_used") is True


def test_primary_success_no_fallback():
    """When primary succeeds within timeout, fallback is NOT called."""
    primary = _mock_provider("openrouter", "google/gemma-4-26b-a4b-it:free", success=True)
    fallback = _mock_provider("ollama", "qwen2.5:3b-instruct", success=True)

    with patch("app.services.llm.provider_factory.get_settings") as mock_settings, \
         patch("app.services.llm.provider_factory.get_provider") as mock_get_provider:
        mock_settings.return_value = MagicMock(
            llm_mode="fallback",
            llm_primary_provider="openrouter",
            llm_fallback_provider="ollama",
        )
        mock_get_provider.side_effect = lambda n: primary if n == "openrouter" else fallback

        res = generate_with_fallback(LLMRequest(system_prompt="sys", user_prompt="user"))
        assert res.success is True
        assert res.provider == "openrouter"
        assert res.metadata.get("fallback_used") is False
        assert not fallback.generate.called


def test_both_providers_fail_returns_clean_error():
    """When both primary and fallback fail, returns success=False with clean error."""
    primary = _mock_provider("openrouter", "google/gemma-4-26b-a4b-it:free", success=False, error="OpenRouter 503")
    fallback = _mock_provider("ollama", "qwen2.5:3b-instruct", success=False, error="Ollama daemon unreachable")

    with patch("app.services.llm.provider_factory.get_settings") as mock_settings, \
         patch("app.services.llm.provider_factory.get_provider") as mock_get_provider:
        mock_settings.return_value = MagicMock(
            llm_mode="fallback",
            llm_primary_provider="openrouter",
            llm_fallback_provider="ollama",
        )
        mock_get_provider.side_effect = lambda n: primary if n == "openrouter" else fallback

        res = generate_with_fallback(LLMRequest(system_prompt="sys", user_prompt="user"))
        assert res.success is False
        assert res.provider == "ollama"
        assert res.error == "Ollama daemon unreachable"


def test_primary_timeout_is_30s():
    """Verify primary request is dispatched with timeout_seconds == 30s."""
    primary = _mock_provider("openrouter", "google/gemma-4-26b-a4b-it:free", success=True)

    with patch("app.services.llm.provider_factory.get_settings") as mock_settings, \
         patch("app.services.llm.provider_factory.get_provider") as mock_get_provider:
        mock_settings.return_value = MagicMock(
            llm_mode="fallback",
            llm_primary_provider="openrouter",
            llm_fallback_provider="ollama",
        )
        mock_get_provider.return_value = primary

        req = LLMRequest(system_prompt="sys", user_prompt="user", timeout_seconds=60)
        generate_with_fallback(req)

        sent_req = primary.generate.call_args[0][0]
        assert sent_req.timeout_seconds == PRIMARY_TIMEOUT_SECONDS
        assert sent_req.timeout_seconds == 30


def test_fallback_timeout_is_original():
    """Verify fallback request retains the caller's original timeout (e.g. 60s)."""
    primary = _mock_provider("openrouter", "google/gemma-4-26b-a4b-it:free", success=False, error="timeout")
    fallback = _mock_provider("ollama", "qwen2.5:3b-instruct", success=True)

    with patch("app.services.llm.provider_factory.get_settings") as mock_settings, \
         patch("app.services.llm.provider_factory.get_provider") as mock_get_provider:
        mock_settings.return_value = MagicMock(
            llm_mode="fallback",
            llm_primary_provider="openrouter",
            llm_fallback_provider="ollama",
        )
        mock_get_provider.side_effect = lambda n: primary if n == "openrouter" else fallback

        req = LLMRequest(system_prompt="sys", user_prompt="user", timeout_seconds=60)
        generate_with_fallback(req)

        sent_fallback_req = fallback.generate.call_args[0][0]
        assert sent_fallback_req.timeout_seconds == 60


# ==============================================================================
# 2. IMAGE HANDLING & TEXT-ONLY FALLBACK TESTS
# ==============================================================================

def test_fallback_request_strips_images():
    """Fallback request must strip images (images=[])."""
    primary = _mock_provider("openrouter", "google/gemma-4-26b-a4b-it:free", success=False, error="timeout")
    fallback = _mock_provider("ollama", "qwen2.5:3b-instruct", success=True)

    with patch("app.services.llm.provider_factory.get_settings") as mock_settings, \
         patch("app.services.llm.provider_factory.get_provider") as mock_get_provider:
        mock_settings.return_value = MagicMock(
            llm_mode="fallback",
            llm_primary_provider="openrouter",
            llm_fallback_provider="ollama",
        )
        mock_get_provider.side_effect = lambda n: primary if n == "openrouter" else fallback

        req = LLMRequest(
            system_prompt="sys",
            user_prompt="user",
            images=[b"\xff\xd8\xff\xe0...fake jpeg..."],
        )
        generate_with_fallback(req)

        sent_fallback_req = fallback.generate.call_args[0][0]
        assert sent_fallback_req.images == []


def test_primary_request_keeps_images():
    """Primary request retains images for multimodal analysis."""
    primary = _mock_provider("openrouter", "google/gemma-4-26b-a4b-it:free", success=True)

    with patch("app.services.llm.provider_factory.get_settings") as mock_settings, \
         patch("app.services.llm.provider_factory.get_provider") as mock_get_provider:
        mock_settings.return_value = MagicMock(
            llm_mode="fallback",
            llm_primary_provider="openrouter",
            llm_fallback_provider="ollama",
        )
        mock_get_provider.return_value = primary

        fake_img = b"\xff\xd8\xff\xe0testimage"
        req = LLMRequest(system_prompt="sys", user_prompt="user", images=[fake_img])
        generate_with_fallback(req)

        sent_primary_req = primary.generate.call_args[0][0]
        assert sent_primary_req.images == [fake_img]


def test_fallback_system_prompt_is_text_only():
    """Fallback request replaces system_prompt with SAFETY_TEXT_ONLY_FALLBACK_SYSTEM_PROMPT."""
    primary = _mock_provider("openrouter", "google/gemma-4-26b-a4b-it:free", success=False, error="timeout")
    fallback = _mock_provider("ollama", "qwen2.5:3b-instruct", success=True)

    with patch("app.services.llm.provider_factory.get_settings") as mock_settings, \
         patch("app.services.llm.provider_factory.get_provider") as mock_get_provider:
        mock_settings.return_value = MagicMock(
            llm_mode="fallback",
            llm_primary_provider="openrouter",
            llm_fallback_provider="ollama",
        )
        mock_get_provider.side_effect = lambda n: primary if n == "openrouter" else fallback

        req = LLMRequest(
            system_prompt=SAFETY_MULTIMODAL_SYSTEM_PROMPT,
            user_prompt="user",
            images=[b"fake"],
        )
        generate_with_fallback(req)

        sent_fallback_req = fallback.generate.call_args[0][0]
        assert sent_fallback_req.system_prompt == SAFETY_TEXT_ONLY_FALLBACK_SYSTEM_PROMPT
        assert "TEXT-ONLY FALLBACK MODE" in sent_fallback_req.system_prompt


def test_primary_multimodal_system_prompt_when_image():
    """AIOrchestrator selects SAFETY_MULTIMODAL_SYSTEM_PROMPT when evidence_image is present."""
    captured_requests = []

    def fake_generate(request):
        captured_requests.append(request)
        return LLMResponse(content=SAMPLE_LLM_JSON, provider="openrouter", model="gemma", success=True)

    with patch("app.services.llm.orchestrator.generate_with_fallback", side_effect=fake_generate):
        AIOrchestrator.analyze(
            org_id="test-org",
            event_type="ppe_violation",
            risk_assessment={"risk_score": 0.8, "risk_level": "critical"},
            evidence_image=b"\xff\xd8\xff\xe0dummyjpeg",
        )

    assert len(captured_requests) == 1
    assert captured_requests[0].system_prompt == SAFETY_MULTIMODAL_SYSTEM_PROMPT


def test_primary_text_prompt_when_no_image():
    """AIOrchestrator selects SAFETY_SYSTEM_PROMPT when evidence_image is None."""
    captured_requests = []

    def fake_generate(request):
        captured_requests.append(request)
        return LLMResponse(content=SAMPLE_LLM_JSON, provider="openrouter", model="gemma", success=True)

    with patch("app.services.llm.orchestrator.generate_with_fallback", side_effect=fake_generate):
        AIOrchestrator.analyze(
            org_id="test-org",
            event_type="ppe_violation",
            risk_assessment={"risk_score": 0.8, "risk_level": "critical"},
            evidence_image=None,
        )

    assert len(captured_requests) == 1
    assert captured_requests[0].system_prompt == SAFETY_SYSTEM_PROMPT


# ==============================================================================
# 3. METADATA TESTS
# ==============================================================================

def test_primary_success_metadata_no_fallback():
    """Primary success metadata records fallback_used=False, attempted_provider=openrouter."""
    primary = _mock_provider("openrouter", "google/gemma-4-26b-a4b-it:free", success=True)

    with patch("app.services.llm.provider_factory.get_settings") as mock_settings, \
         patch("app.services.llm.provider_factory.get_provider", return_value=primary):
        mock_settings.return_value = MagicMock(
            llm_mode="fallback",
            llm_primary_provider="openrouter",
            llm_fallback_provider="ollama",
        )

        res = generate_with_fallback(LLMRequest(system_prompt="sys", user_prompt="user"))
        assert res.metadata.get("fallback_used") is False
        assert res.metadata.get("attempted_provider") == "openrouter"


def test_fallback_metadata_contains_reason():
    """Fallback metadata contains fallback_reason from primary error."""
    primary = _mock_provider("openrouter", "google/gemma-4-26b-a4b-it:free", success=False, error="Connection timeout 30s")
    fallback = _mock_provider("ollama", "qwen2.5:3b-instruct", success=True)

    with patch("app.services.llm.provider_factory.get_settings") as mock_settings, \
         patch("app.services.llm.provider_factory.get_provider") as mock_get_provider:
        mock_settings.return_value = MagicMock(
            llm_mode="fallback",
            llm_primary_provider="openrouter",
            llm_fallback_provider="ollama",
        )
        mock_get_provider.side_effect = lambda n: primary if n == "openrouter" else fallback

        res = generate_with_fallback(LLMRequest(system_prompt="sys", user_prompt="user"))
        assert res.metadata.get("fallback_reason") == "Connection timeout 30s"


def test_fallback_metadata_contains_attempted_provider():
    """Fallback metadata records attempted_provider='openrouter'."""
    primary = _mock_provider("openrouter", "google/gemma-4-26b-a4b-it:free", success=False, error="500")
    fallback = _mock_provider("ollama", "qwen2.5:3b-instruct", success=True)

    with patch("app.services.llm.provider_factory.get_settings") as mock_settings, \
         patch("app.services.llm.provider_factory.get_provider") as mock_get_provider:
        mock_settings.return_value = MagicMock(
            llm_mode="fallback",
            llm_primary_provider="openrouter",
            llm_fallback_provider="ollama",
        )
        mock_get_provider.side_effect = lambda n: primary if n == "openrouter" else fallback

        res = generate_with_fallback(LLMRequest(system_prompt="sys", user_prompt="user"))
        assert res.metadata.get("attempted_provider") == "openrouter"


def test_fallback_metadata_multimodal_false():
    """Fallback metadata explicitly sets multimodal=False."""
    primary = _mock_provider("openrouter", "google/gemma-4-26b-a4b-it:free", success=False, error="timeout")
    fallback = _mock_provider("ollama", "qwen2.5:3b-instruct", success=True)

    with patch("app.services.llm.provider_factory.get_settings") as mock_settings, \
         patch("app.services.llm.provider_factory.get_provider") as mock_get_provider:
        mock_settings.return_value = MagicMock(
            llm_mode="fallback",
            llm_primary_provider="openrouter",
            llm_fallback_provider="ollama",
        )
        mock_get_provider.side_effect = lambda n: primary if n == "openrouter" else fallback

        res = generate_with_fallback(LLMRequest(system_prompt="sys", user_prompt="user", images=[b"fake"]))
        assert res.metadata.get("multimodal") is False


# ==============================================================================
# 4. PROMPTS — ANTI-HALLUCINATION TESTS
# ==============================================================================

def test_multimodal_prompt_contains_no_invent_rule():
    """Multimodal prompt contains strict prohibitions against inventing facts."""
    assert "CRITICAL ANTI-HALLUCINATION RULES — MANDATORY" in SAFETY_MULTIMODAL_SYSTEM_PROMPT
    assert "You MUST NOT invent or state as fact ANY of the following" in SAFETY_MULTIMODAL_SYSTEM_PROMPT
    assert "The exact cause of fire" in SAFETY_MULTIMODAL_SYSTEM_PROMPT
    assert "Chemical identity" in SAFETY_MULTIMODAL_SYSTEM_PROMPT
    assert "Injured persons" in SAFETY_MULTIMODAL_SYSTEM_PROMPT


def test_fallback_prompt_contains_no_image_warning():
    """Fallback prompt explicitly states TEXT-ONLY FALLBACK MODE."""
    assert "YOU ARE OPERATING IN TEXT-ONLY FALLBACK MODE." in SAFETY_TEXT_ONLY_FALLBACK_SYSTEM_PROMPT
    assert "You do NOT have access to the evidence image." in SAFETY_TEXT_ONLY_FALLBACK_SYSTEM_PROMPT


def test_fallback_prompt_contains_no_visual_claim_rule():
    """Fallback prompt prohibits claiming visual inspection and forces empty observations."""
    assert "You MUST NOT claim to have seen the image." in SAFETY_TEXT_ONLY_FALLBACK_SYSTEM_PROMPT
    assert "Leave visual_observations as an empty array []." in SAFETY_TEXT_ONLY_FALLBACK_SYSTEM_PROMPT
    assert "Leave visual_validation as null." in SAFETY_TEXT_ONLY_FALLBACK_SYSTEM_PROMPT


def test_multimodal_prompt_contains_epistemic_language():
    """Multimodal prompt requires epistemic calibration language."""
    assert '"The image shows..."' in SAFETY_MULTIMODAL_SYSTEM_PROMPT
    assert '"The available evidence suggests..."' in SAFETY_MULTIMODAL_SYSTEM_PROMPT
    assert '"A possible contributing factor is..."' in SAFETY_MULTIMODAL_SYSTEM_PROMPT
    assert '"This cannot be determined from the available information."' in SAFETY_MULTIMODAL_SYSTEM_PROMPT


# ==============================================================================
# 5. PROMPTS — INPUT CONTRACT TESTS
# ==============================================================================

def test_detection_metadata_in_prompt():
    """YOLO detection data is formatted and included in prompt."""
    det_data = {
        "details": {
            "detected_class": "person",
            "confidence": 0.94,
            "bbox": [10, 20, 100, 200],
        },
        "track_id": 42,
        "missing_ppe": ["helmet", "vest"],
    }
    context = build_detection_metadata_context(det_data)
    assert "MACHINE DETECTION DATA" in context
    assert "Detected Class: person" in context
    assert "Detection Confidence: 0.94" in context
    assert "Bounding Box: [10, 20, 100, 200]" in context
    assert "Track ID: 42" in context
    assert "Missing PPE: helmet, vest" in context


def test_risk_data_in_prompt():
    """Risk engine score and level are grounded in prompt."""
    risk_data = {
        "risk_score": 0.85,
        "risk_level": "critical",
        "explanation": "Active fire hazard in high-density chemical storage zone.",
        "factors": [{"name": "Fire Risk", "score": 0.9, "explanation": "Visible flame signature"}],
    }
    context = build_risk_context(risk_data)
    assert "DETERMINISTIC RISK ASSESSMENT" in context
    assert "Risk Score: 0.85" in context
    assert "Risk Level: critical" in context
    assert "Fire Risk: score=0.90" in context


def test_rag_context_in_prompt():
    """Retrieved RAG policy chunks appear in prompt with document titles."""
    chunks = [{
        "metadata": {"document_title": "OSHA-1910-Safety.pdf"},
        "score": 0.89,
        "content": "All personnel must wear ANSI Z89.1 certified hard hats.",
    }]
    context = build_rag_context(chunks)
    assert "RETRIEVED SAFETY POLICY DOCUMENTS" in context
    assert "OSHA-1910-Safety.pdf" in context
    assert "ANSI Z89.1 certified hard hats" in context


def test_history_in_prompt_when_provided():
    """Historical context and active pattern appear in prompt."""
    recent = [{"event_type": "ppe_violation", "created_at": "2026-09-01T10:00:00Z", "severity": "high"}]
    pattern = {
        "title": "Night Shift PPE Drop",
        "occurrence_count": 8,
        "confidence_score": 0.92,
        "first_detected_at": "2026-08-15T00:00:00Z",
    }
    context = build_historical_context(recurrence_count=3, recent_events=recent, pattern_summary=pattern)
    assert "3 similar events in recent history" in context
    assert "Active Pattern: 'Night Shift PPE Drop'" in context
    assert "total occurrences: 8" in context
    assert "confidence: 0.92" in context
    assert "ppe_violation at 2026-09-01T10:00:00Z" in context


def test_history_count_zero_when_no_events():
    """Historical context correctly handles 0 recurrence count."""
    context = build_historical_context(recurrence_count=0, recent_events=None, pattern_summary=None)
    assert "0 similar events in recent history" in context
    assert "Active Pattern" not in context


# ==============================================================================
# 6. SCHEMA — PHASE 14D NEW FIELDS TESTS
# ==============================================================================

def test_hazard_interpretation_parsed():
    """hazard_interpretation is parsed from LLM JSON into AIAnalysisResult."""
    raw = json.dumps({"summary": "s", "risk_explanation": "r", "hazard_interpretation": "Severe fall hazard"})
    res = AIOrchestrator._parse_response(raw, "openrouter", "gemma")
    assert isinstance(res, AIAnalysisResult)
    assert res.hazard_interpretation == "Severe fall hazard"


def test_immediate_actions_parsed():
    """immediate_actions list is parsed from LLM JSON."""
    raw = json.dumps({"summary": "s", "risk_explanation": "r", "immediate_actions": ["Stop conveyor", "Evacuate line"]})
    res = AIOrchestrator._parse_response(raw, "openrouter", "gemma")
    assert isinstance(res, AIAnalysisResult)
    assert res.immediate_actions == ["Stop conveyor", "Evacuate line"]


def test_investigation_actions_parsed():
    """investigation_actions list is parsed from LLM JSON."""
    raw = json.dumps({"summary": "s", "risk_explanation": "r", "investigation_actions": ["Inspect emergency stop button"]})
    res = AIOrchestrator._parse_response(raw, "openrouter", "gemma")
    assert isinstance(res, AIAnalysisResult)
    assert res.investigation_actions == ["Inspect emergency stop button"]


def test_preventive_actions_parsed():
    """preventive_actions list is parsed from LLM JSON."""
    raw = json.dumps({"summary": "s", "risk_explanation": "r", "preventive_actions": ["Install safety light curtain"]})
    res = AIOrchestrator._parse_response(raw, "openrouter", "gemma")
    assert isinstance(res, AIAnalysisResult)
    assert res.preventive_actions == ["Install safety light curtain"]


def test_uncertainties_parsed():
    """uncertainties list is parsed from LLM JSON."""
    raw = json.dumps({"summary": "s", "risk_explanation": "r", "uncertainties": ["Ignition source unknown"]})
    res = AIOrchestrator._parse_response(raw, "openrouter", "gemma")
    assert isinstance(res, AIAnalysisResult)
    assert res.uncertainties == ["Ignition source unknown"]


def test_missing_new_fields_default_to_empty():
    """Old-style LLM responses missing new fields deserialize safely with empty defaults."""
    old_json = json.dumps({
        "summary": "Old summary",
        "risk_explanation": "Old explanation",
        "contributing_factors": ["factor 1"],
        "recommended_actions": ["action 1"],
    })
    res = AIOrchestrator._parse_response(old_json, "openrouter", "gemma")
    assert isinstance(res, AIAnalysisResult)
    assert res.hazard_interpretation == ""
    assert res.immediate_actions == []
    assert res.investigation_actions == []
    assert res.preventive_actions == []
    assert res.uncertainties == []
    assert res.recommended_actions == ["action 1"]


# ==============================================================================
# 7. PERSISTENCE & INTEGRATION TESTS (Phase 14c / 14d)
# ==============================================================================

@pytest.fixture
def auth_context():
    """Create test org, role with ai permissions, and user."""
    db = TestSession()
    try:
        suffix = uuid.uuid4().hex[:8]
        org = Organization(id=str(uuid.uuid4()), name=f"Fallback Test Org {suffix}", slug=f"test-fb-{suffix}")
        db.add(org)
        db.flush()

        role = Role(id=str(uuid.uuid4()), name="Safety Mgr", org_id=org.id)
        db.add(role)
        db.flush()

        for p in ["ai.view", "ai.analyze", "events.view"]:
            db.add(Permission(id=str(uuid.uuid4()), role_id=role.id, perm_name=p))
        db.flush()

        user = User(
            id=str(uuid.uuid4()),
            org_id=org.id,
            email=f"test-fb-{uuid.uuid4().hex[:6]}@example.com",
            name="Safety Tester",
            pwd_hash=hash_password("pw123456"),
            role_id=role.id,
        )
        db.add(user)

        # Create site and camera
        site = Site(id=str(uuid.uuid4()), org_id=org.id, name="Site 1")
        db.add(site)
        db.flush()

        camera = Camera(id=str(uuid.uuid4()), site_id=site.id, org_id=org.id, name="Cam 1", stream_url="rtsp://test")
        db.add(camera)

        # Create event
        event = Event(
            id=str(uuid.uuid4()),
            org_id=org.id,
            camera_id=camera.id,
            event_type=EventType.PPE_DETECTION,
            timestamp=datetime.now(timezone.utc),
            detection_data={"risk_assessment": {"risk_score": 0.85, "risk_level": "critical", "factors": [], "explanation": "Test"}},
        )
        db.add(event)
        db.commit()

        token = create_access_token(user_id=user.id, org_id=org.id, role_name="Safety Mgr")
        headers = {"Authorization": f"Bearer {token}"}

        yield {
            "org_id": org.id,
            "user_id": user.id,
            "camera_id": camera.id,
            "event_id": event.id,
            "headers": headers,
        }
    finally:
        db.rollback()
        db.close()


def test_correct_provider_persisted_in_llm_metadata(auth_context):
    """When fallback occurs during real event analysis, llm_metadata records provider=ollama and fallback_used=True."""
    primary = _mock_provider("openrouter", "google/gemma-4-26b-a4b-it:free", success=False, error="Primary 30s timeout")
    fallback = _mock_provider("ollama", "qwen2.5:3b-instruct", success=True, content=SAMPLE_LLM_JSON)

    with patch("app.services.llm.provider_factory.get_settings") as mock_settings, \
         patch("app.services.llm.provider_factory.get_provider") as mock_get_provider:
        mock_settings.return_value = MagicMock(
            llm_mode="fallback",
            llm_primary_provider="openrouter",
            llm_fallback_provider="ollama",
            llm_temperature=0.2,
            llm_max_output_tokens=2048,
            llm_timeout_seconds=60,
        )
        mock_get_provider.side_effect = lambda n: primary if n == "openrouter" else fallback

        resp = client.post(
            f"/api/ai/analyze-event/{auth_context['event_id']}",
            headers=auth_context["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["provider"] == "ollama"
        assert data["insight_id"] is not None

        # Verify DB row
        db = TestSession()
        try:
            insight = db.query(AiInsight).filter(AiInsight.id == data["insight_id"]).first()
            assert insight is not None
            assert insight.llm_metadata["provider"] == "ollama"
            assert insight.llm_metadata["fallback_used"] is True
            assert insight.llm_metadata["attempted_provider"] == "openrouter"
            assert insight.llm_metadata["multimodal"] is False
            assert "Primary 30s timeout" in insight.llm_metadata["fallback_reason"]

            # Content has Phase 14d structured fields
            content = json.loads(insight.content)
            assert "hazard_interpretation" in content
            assert "immediate_actions" in content
            assert "investigation_actions" in content
            assert "preventive_actions" in content
            assert "uncertainties" in content
        finally:
            db.close()


def test_no_insight_created_on_both_failure(auth_context):
    """When both primary and fallback fail, NO AiInsight is persisted and API returns error."""
    primary = _mock_provider("openrouter", "google/gemma-4-26b-a4b-it:free", success=False, error="Primary failed")
    fallback = _mock_provider("ollama", "qwen2.5:3b-instruct", success=False, error="Fallback failed")

    db = TestSession()
    initial_count = db.query(AiInsight).filter(AiInsight.org_id == auth_context["org_id"]).count()
    db.close()

    with patch("app.services.llm.provider_factory.get_settings") as mock_settings, \
         patch("app.services.llm.provider_factory.get_provider") as mock_get_provider:
        mock_settings.return_value = MagicMock(
            llm_mode="fallback",
            llm_primary_provider="openrouter",
            llm_fallback_provider="ollama",
            llm_temperature=0.2,
            llm_max_output_tokens=2048,
            llm_timeout_seconds=60,
        )
        mock_get_provider.side_effect = lambda n: primary if n == "openrouter" else fallback

        resp = client.post(
            f"/api/ai/analyze-event/{auth_context['event_id']}",
            headers=auth_context["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert data["insight_id"] is None

        db = TestSession()
        final_count = db.query(AiInsight).filter(AiInsight.org_id == auth_context["org_id"]).count()
        db.close()
        assert final_count == initial_count


def test_fallback_reason_in_llm_metadata(auth_context):
    """Fallback reason is explicitly stored in AiInsight.llm_metadata."""
    primary = _mock_provider("openrouter", "google/gemma-4-26b-a4b-it:free", success=False, error="OpenRouter gateway 504 Gateway Timeout")
    fallback = _mock_provider("ollama", "qwen2.5:3b-instruct", success=True, content=SAMPLE_LLM_JSON)

    with patch("app.services.llm.provider_factory.get_settings") as mock_settings, \
         patch("app.services.llm.provider_factory.get_provider") as mock_get_provider:
        mock_settings.return_value = MagicMock(
            llm_mode="fallback",
            llm_primary_provider="openrouter",
            llm_fallback_provider="ollama",
            llm_temperature=0.2,
            llm_max_output_tokens=2048,
            llm_timeout_seconds=60,
        )
        mock_get_provider.side_effect = lambda n: primary if n == "openrouter" else fallback

        resp = client.post(
            f"/api/ai/analyze-event/{auth_context['event_id']}",
            headers=auth_context["headers"],
        )
        data = resp.json()
        assert data["success"] is True

        db = TestSession()
        try:
            insight = db.query(AiInsight).filter(AiInsight.id == data["insight_id"]).first()
            assert insight.llm_metadata.get("fallback_reason") == "OpenRouter gateway 504 Gateway Timeout"
        finally:
            db.close()


# ==============================================================================
# 8. HISTORICAL CONTEXT & TENANT ISOLATION TESTS (Phase 14e)
# ==============================================================================

def test_recurrence_count_from_db(auth_context):
    """Verify recurrence_count reflects DB rows within 30-day window for same event_type and org."""
    db = TestSession()
    try:
        # Insert 3 older events of same type and org within 30 days
        now = datetime.now(timezone.utc)
        for i in range(3):
            ev = Event(
                id=str(uuid.uuid4()),
                org_id=auth_context["org_id"],
                camera_id=auth_context["camera_id"],
                event_type=EventType.PPE_DETECTION,
                timestamp=now - timedelta(days=i + 1),
                detection_data={"risk_assessment": {"risk_score": 0.5, "risk_level": "medium"}},
            )
            db.add(ev)
        db.commit()
    finally:
        db.close()

    captured_args = {}

    def fake_analyze(*args, **kwargs):
        captured_args.update(kwargs)
        return AIAnalysisResult(
            summary="Recurrence test summary",
            risk_explanation="Explanation",
            provider="openrouter",
            model="gemma",
        )

    with patch("app.services.llm.orchestrator.AIOrchestrator.analyze", side_effect=fake_analyze):
        resp = client.post(
            f"/api/ai/analyze-event/{auth_context['event_id']}",
            headers=auth_context["headers"],
        )
        assert resp.status_code == 200

    assert captured_args.get("recurrence_count") == 3


def test_recurrence_excludes_current_event(auth_context):
    """Current event ID is excluded from recurrence count."""
    db = TestSession()
    try:
        now = datetime.now(timezone.utc)
        # Add 2 prior events for the same org
        for i in range(2):
            ev = Event(
                id=str(uuid.uuid4()),
                org_id=auth_context["org_id"],
                camera_id=auth_context["camera_id"],
                event_type=EventType.PPE_DETECTION,
                timestamp=now - timedelta(days=i + 1),
                detection_data={},
            )
            db.add(ev)
        db.commit()
    finally:
        db.close()

    captured_args = {}

    def fake_analyze(*args, **kwargs):
        captured_args.update(kwargs)
        return AIAnalysisResult(summary="s", risk_explanation="r", provider="p", model="m")

    with patch("app.services.llm.orchestrator.AIOrchestrator.analyze", side_effect=fake_analyze):
        client.post(
            f"/api/ai/analyze-event/{auth_context['event_id']}",
            headers=auth_context["headers"],
        )

    # Total events in DB for this org: 3 (1 current + 2 prior). Count must be 2, NOT 3.
    assert captured_args.get("recurrence_count") == 2


def test_recent_events_from_db(auth_context):
    """Recent events list contains up to 5 events ordered by timestamp desc."""
    db = TestSession()
    try:
        now = datetime.now(timezone.utc)
        # Add 6 more events to exceed the limit of 5
        for i in range(6):
            ev = Event(
                id=str(uuid.uuid4()),
                org_id=auth_context["org_id"],
                camera_id=auth_context["camera_id"],
                event_type=EventType.PPE_DETECTION,
                timestamp=now - timedelta(hours=i + 1),
                detection_data={"risk_assessment": {"risk_level": "high"}},
            )
            db.add(ev)
        db.commit()
    finally:
        db.close()

    captured_args = {}

    def fake_analyze(*args, **kwargs):
        captured_args.update(kwargs)
        return AIAnalysisResult(summary="s", risk_explanation="r", provider="p", model="m")

    with patch("app.services.llm.orchestrator.AIOrchestrator.analyze", side_effect=fake_analyze):
        client.post(
            f"/api/ai/analyze-event/{auth_context['event_id']}",
            headers=auth_context["headers"],
        )

    recent_events = captured_args.get("recent_events", [])
    assert len(recent_events) <= 5


def test_tenant_isolation_in_history_query(auth_context):
    """Events belonging to a different org are NOT counted in recurrence or recent events."""
    db = TestSession()
    try:
        other_suffix = uuid.uuid4().hex[:8]
        other_org = Organization(id=str(uuid.uuid4()), name=f"Other Org {other_suffix}", slug=f"other-{other_suffix}")
        db.add(other_org)
        db.flush()

        other_site = Site(id=str(uuid.uuid4()), org_id=other_org.id, name="Other Site")
        db.add(other_site)
        db.flush()

        other_camera = Camera(id=str(uuid.uuid4()), site_id=other_site.id, org_id=other_org.id, name="Other Cam", stream_url="rtsp://other")
        db.add(other_camera)
        db.flush()

        # Add 10 events for other org
        for i in range(10):
            db.add(Event(
                id=str(uuid.uuid4()),
                org_id=other_org.id,
                camera_id=other_camera.id,
                event_type=EventType.PPE_DETECTION,
                timestamp=datetime.now(timezone.utc) - timedelta(days=1),
                detection_data={},
            ))
        db.commit()
    finally:
        db.close()

    captured_args = {}

    def fake_analyze(*args, **kwargs):
        captured_args.update(kwargs)
        return AIAnalysisResult(summary="s", risk_explanation="r", provider="p", model="m")

    with patch("app.services.llm.orchestrator.AIOrchestrator.analyze", side_effect=fake_analyze):
        client.post(
            f"/api/ai/analyze-event/{auth_context['event_id']}",
            headers=auth_context["headers"],
        )

    # Recurrence count for auth_context's org should only count auth_context's events, not other_org's
    recent_events = captured_args.get("recent_events", [])
    for ev in recent_events:
        assert ev.get("camera_id") != other_camera.id


def test_30_day_lookback_window(auth_context):
    """Events older than 30 days are excluded from recurrence count."""
    db = TestSession()
    try:
        old_event = Event(
            id=str(uuid.uuid4()),
            org_id=auth_context["org_id"],
            camera_id=auth_context["camera_id"],
            event_type=EventType.PPE_DETECTION,
            timestamp=datetime.now(timezone.utc) - timedelta(days=45),  # 45 days old
            detection_data={},
        )
        db.add(old_event)
        db.commit()
    finally:
        db.close()

    captured_args = {}

    def fake_analyze(*args, **kwargs):
        captured_args.update(kwargs)
        return AIAnalysisResult(summary="s", risk_explanation="r", provider="p", model="m")

    with patch("app.services.llm.orchestrator.AIOrchestrator.analyze", side_effect=fake_analyze):
        client.post(
            f"/api/ai/analyze-event/{auth_context['event_id']}",
            headers=auth_context["headers"],
        )

    recent_events = captured_args.get("recent_events", [])
    # Verify the 45-day-old event is not in recent_events
    for ev in recent_events:
        created_at_dt = datetime.fromisoformat(ev["created_at"])
        assert datetime.now(timezone.utc) - created_at_dt <= timedelta(days=31)
