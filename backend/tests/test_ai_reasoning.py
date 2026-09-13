"""
SafeVision AI — AI Reasoning Tests (Phase 9)

Tests use MOCKED LLM providers — no real external API calls.

Coverage:
  PROVIDER INTERFACE (1–4)
  PROVIDER SUCCESS/FAILURE (5–8)
  FALLBACK BEHAVIOR (7–8 continued)
  TIMEOUT/MALFORMED (9–10)
  STRUCTURED OUTPUT (11)
  RAG INTEGRATION (12–13)
  TENANT ISOLATION (14)
  AUTHORIZATION (15)
  API SUCCESS/FAILURE (16–17)
  MISSING API KEY (18)
  INVALID PROVIDER CONFIG (19)
  MODEL SWITCHING (20)
"""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.database import get_db
from app.main import app
from app.models.organization import Organization
from app.models.role import Permission, Role
from app.models.user import User
from app.schemas.ai_analysis import AIAnalysisResult
from app.services.auth_service import create_access_token, hash_password
from app.services.llm import LLMProvider, LLMRequest, LLMResponse
from app.services.llm.agents import (
    EmergencyResponseAgent,
    InvestigationAgent,
    PredictiveSafetyAgent,
    SafetyPolicyAgent,
)
from app.services.llm.gemini_provider import GeminiProvider
from app.services.llm.ollama_provider import OllamaProvider
from app.services.llm.orchestrator import AIOrchestrator
from app.services.llm.prompts import (
    SAFETY_SYSTEM_PROMPT,
    build_analysis_prompt,
    build_risk_context,
)
from app.services.llm.provider_factory import (
    ProviderError,
    generate_with_fallback,
    get_provider,
)

# ==============================================================================
# Test Database Setup
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
# Test Data Helpers
# ==============================================================================

_test_data: dict = {}


def _create_org(db: Session, name: str, slug: str) -> Organization:
    org = Organization(id=str(uuid.uuid4()), name=name, slug=slug)
    db.add(org)
    db.flush()
    return org


def _create_role(db: Session, org_id: str, name: str, perms: list[str]) -> Role:
    role = Role(id=str(uuid.uuid4()), name=name, org_id=org_id)
    db.add(role)
    db.flush()
    for p in perms:
        db.add(Permission(id=str(uuid.uuid4()), role_id=role.id, perm_name=p))
    db.flush()
    return role


def _create_user(db: Session, org_id: str, role_id: str, email: str) -> User:
    user = User(
        id=str(uuid.uuid4()), org_id=org_id, email=email,
        name="Test User", pwd_hash=hash_password("testpass123"),
        role_id=role_id,
    )
    db.add(user)
    db.flush()
    return user


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _get_token(user_id: str, org_id: str, role_name: str = "Admin") -> str:
    return create_access_token(user_id=user_id, org_id=org_id, role_name=role_name)


def _setup_test_data():
    if _test_data:
        return
    db = TestSession()
    try:
        uid = uuid.uuid4().hex[:6]
        org_a = _create_org(db, f"AI Org A {uid}", f"ai-a-{uid}")
        admin_role = _create_role(db, org_a.id, "Admin", [
            "ai.view", "ai.manage", "events.view",
        ])
        viewer_role = _create_role(db, org_a.id, "Viewer", [
            "events.view",
        ])
        admin = _create_user(db, org_a.id, admin_role.id, f"ai-admin-{uid}@test.com")
        viewer = _create_user(db, org_a.id, viewer_role.id, f"ai-viewer-{uid}@test.com")

        uid_b = uuid.uuid4().hex[:6]
        org_b = _create_org(db, f"AI Org B {uid_b}", f"ai-b-{uid_b}")
        admin_role_b = _create_role(db, org_b.id, "Admin", ["ai.view", "ai.manage"])
        admin_b = _create_user(db, org_b.id, admin_role_b.id, f"ai-admin-b-{uid_b}@test.com")

        db.commit()
        _test_data["org_a_id"] = org_a.id
        _test_data["org_b_id"] = org_b.id
        _test_data["admin_a_id"] = admin.id
        _test_data["viewer_a_id"] = viewer.id
        _test_data["admin_b_id"] = admin_b.id
    finally:
        db.close()


# ==============================================================================
# Mock LLM Response
# ==============================================================================

MOCK_LLM_JSON = json.dumps({
    "summary": "PPE violation detected on manufacturing floor.",
    "risk_explanation": "High risk due to missing hard hat in active zone.",
    "contributing_factors": ["Missing hard hat", "Active manufacturing zone"],
    "safety_policy_guidance": "Per PPE Policy Section 1: Hard hats required.",
    "historical_context": "3 similar events in the last 7 days.",
    "recommended_actions": [
        "Issue immediate verbal warning",
        "Provide replacement hard hat",
        "Schedule PPE compliance refresher",
    ],
})

MOCK_RISK_ASSESSMENT = {
    "risk_score": 0.75,
    "risk_level": "high",
    "factors": [
        {"name": "event_type", "score": 0.8, "explanation": "PPE violation"},
        {"name": "zone_criticality", "score": 0.7, "explanation": "Active zone"},
    ],
    "explanation": "High risk PPE violation in active manufacturing zone.",
}


# ==============================================================================
# 1–4. Provider Interface Tests
# ==============================================================================

class TestProviderInterface:
    """LLM provider interface and factory tests."""

    def test_gemini_provider_implements_interface(self):
        """GeminiProvider implements LLMProvider."""
        provider = GeminiProvider()
        assert isinstance(provider, LLMProvider)
        assert provider.name == "gemini"
        assert isinstance(provider.model_name, str)

    def test_ollama_provider_implements_interface(self):
        """OllamaProvider implements LLMProvider."""
        provider = OllamaProvider()
        assert isinstance(provider, LLMProvider)
        assert provider.name == "ollama"
        assert isinstance(provider.model_name, str)

    def test_provider_switching_via_config(self):
        """get_provider() returns correct provider by name."""
        gemini = get_provider("gemini")
        assert gemini.name == "gemini"

        ollama = get_provider("ollama")
        assert ollama.name == "ollama"

    def test_invalid_provider_raises_error(self):
        """Unknown provider name raises ProviderError."""
        with pytest.raises(ProviderError, match="Unknown LLM provider"):
            get_provider("nonexistent")


# ==============================================================================
# 5–8. Provider Success / Failure / Fallback Tests
# ==============================================================================

class TestProviderBehavior:
    """Provider success, failure, and fallback tests."""

    def test_primary_provider_success(self):
        """Successful primary provider returns content."""
        mock_response = LLMResponse(
            content=MOCK_LLM_JSON,
            provider="gemini",
            model="gemini-2.0-flash",
            success=True,
        )
        with patch(
            "app.services.llm.provider_factory.get_provider",
        ) as mock_get:
            mock_provider = MagicMock(spec=LLMProvider)
            mock_provider.generate.return_value = mock_response
            mock_get.return_value = mock_provider

            request = LLMRequest(
                system_prompt="test", user_prompt="test",
            )
            result = generate_with_fallback(request)
            assert result.success
            assert result.content == MOCK_LLM_JSON

    def test_primary_provider_failure_no_fallback(self):
        """Failed primary with primary_only mode returns error."""
        mock_response = LLMResponse(
            content="", provider="gemini", model="gemini-2.0-flash",
            success=False, error="API error",
        )
        settings = get_settings()
        original_mode = settings.llm_mode
        settings.llm_mode = "primary_only"
        try:
            with patch(
                "app.services.llm.provider_factory.get_provider",
            ) as mock_get:
                mock_provider = MagicMock(spec=LLMProvider)
                mock_provider.generate.return_value = mock_response
                mock_get.return_value = mock_provider

                request = LLMRequest(system_prompt="t", user_prompt="t")
                result = generate_with_fallback(request)
                assert not result.success
                assert "API error" in result.error
        finally:
            settings.llm_mode = original_mode

    def test_fallback_to_ollama_on_gemini_failure(self):
        """Fallback mode tries secondary when primary fails."""
        fail_response = LLMResponse(
            content="", provider="gemini", model="gemini-2.0-flash",
            success=False, error="Gemini down",
        )
        ok_response = LLMResponse(
            content=MOCK_LLM_JSON, provider="ollama",
            model="qwen2.5:7b", success=True,
        )

        settings = get_settings()
        original_mode = settings.llm_mode
        settings.llm_mode = "fallback"
        try:
            call_count = 0

            def mock_get(name=None):
                nonlocal call_count
                call_count += 1
                mock_prov = MagicMock(spec=LLMProvider)
                if call_count == 1:
                    mock_prov.generate.return_value = fail_response
                else:
                    mock_prov.generate.return_value = ok_response
                return mock_prov

            with patch(
                "app.services.llm.provider_factory.get_provider",
                side_effect=mock_get,
            ):
                request = LLMRequest(system_prompt="t", user_prompt="t")
                result = generate_with_fallback(request)
                assert result.success
                assert result.provider == "ollama"
        finally:
            settings.llm_mode = original_mode

    def test_fallback_both_fail(self):
        """Both providers failing returns error with primary context."""
        fail1 = LLMResponse(
            content="", provider="gemini", model="gemini-2.0-flash",
            success=False, error="Gemini down",
        )
        fail2 = LLMResponse(
            content="", provider="ollama", model="qwen2.5",
            success=False, error="Ollama down",
        )

        settings = get_settings()
        original_mode = settings.llm_mode
        settings.llm_mode = "fallback"
        try:
            call_count = 0

            def mock_get(name=None):
                nonlocal call_count
                call_count += 1
                mock_prov = MagicMock(spec=LLMProvider)
                if call_count == 1:
                    mock_prov.generate.return_value = fail1
                else:
                    mock_prov.generate.return_value = fail2
                return mock_prov

            with patch(
                "app.services.llm.provider_factory.get_provider",
                side_effect=mock_get,
            ):
                request = LLMRequest(system_prompt="t", user_prompt="t")
                result = generate_with_fallback(request)
                assert not result.success
                assert "primary_error" in result.metadata
        finally:
            settings.llm_mode = original_mode


# ==============================================================================
# 9–10. Timeout / Malformed Response Tests
# ==============================================================================

class TestErrorHandling:
    """Timeout and malformed response handling."""

    def test_timeout_handling(self):
        """Provider timeout returns controlled error."""
        provider = OllamaProvider()
        # Patch httpx to simulate timeout
        with patch("app.services.llm.ollama_provider.httpx.Client") as mock_client:
            import httpx
            mock_client.return_value.__enter__ = MagicMock()
            mock_client.return_value.__enter__.return_value.post.side_effect = (
                httpx.TimeoutException("Timed out")
            )
            mock_client.return_value.__exit__ = MagicMock(return_value=False)

            request = LLMRequest(system_prompt="t", user_prompt="t")
            result = provider.generate(request)
            assert not result.success
            assert "timed out" in result.error.lower()

    def test_malformed_json_response(self):
        """Malformed LLM JSON is handled safely."""
        result = AIOrchestrator._parse_response(
            raw_content="this is not json at all",
            provider="test",
            model="test-model",
        )
        assert isinstance(result, dict)
        assert result.get("success") is False
        assert "JSON" in result.get("error", "")


# ==============================================================================
# 11. Structured Output Validation
# ==============================================================================

class TestStructuredOutput:
    """Structured output validation tests."""

    def test_valid_json_parsed_to_result(self):
        """Valid JSON is parsed into AIAnalysisResult."""
        result = AIOrchestrator._parse_response(
            raw_content=MOCK_LLM_JSON,
            provider="gemini",
            model="gemini-2.0-flash",
        )
        assert isinstance(result, AIAnalysisResult)
        assert result.summary == "PPE violation detected on manufacturing floor."
        assert result.provider == "gemini"
        assert len(result.recommended_actions) == 3

    def test_json_in_code_fence_extracted(self):
        """JSON wrapped in markdown code fences is extracted."""
        fenced = f"```json\n{MOCK_LLM_JSON}\n```"
        result = AIOrchestrator._parse_response(
            raw_content=fenced,
            provider="ollama",
            model="qwen",
        )
        assert isinstance(result, AIAnalysisResult)
        assert result.provider == "ollama"

    def test_partial_json_uses_defaults(self):
        """Partial JSON gets default values for missing fields."""
        partial = json.dumps({
            "summary": "Partial analysis",
            "risk_explanation": "Limited info",
        })
        result = AIOrchestrator._parse_response(
            raw_content=partial,
            provider="gemini",
            model="gemini-2.0-flash",
        )
        assert isinstance(result, AIAnalysisResult)
        assert result.contributing_factors == []
        assert result.recommended_actions == []


# ==============================================================================
# 12–13. RAG Integration + RiskAssessment Consumption
# ==============================================================================

class TestRAGAndRiskIntegration:
    """RAG context and RiskAssessment consumption tests."""

    def test_rag_context_passed_to_prompt(self):
        """RAG chunks are formatted into the analysis prompt."""
        chunks = [
            {
                "content": "Hard hats are required in all zones.",
                "score": 0.9,
                "metadata": {"document_title": "PPE Policy"},
            },
        ]
        context = SafetyPolicyAgent.build_context("ppe_detection", chunks)
        assert "Hard hats are required" in context
        assert "PPE Policy" in context

    def test_risk_assessment_consumed_without_recalculation(self):
        """RiskAssessment is used as-is, not recalculated."""
        risk_context = build_risk_context(MOCK_RISK_ASSESSMENT)
        assert "0.75" in risk_context
        assert "high" in risk_context.lower()
        assert "do not override" in risk_context.lower()


# ==============================================================================
# 14–15. Tenant Isolation + Authorization
# ==============================================================================

class TestTenantAndAuth:
    """Tenant isolation and authorization tests."""

    def setup_method(self):
        _setup_test_data()

    def test_tenant_isolation_in_analysis(self):
        """Analysis request uses the authenticated user's org_id."""
        token = _get_token(
            _test_data["admin_a_id"], _test_data["org_a_id"],
        )

        mock_result = AIAnalysisResult(
            summary="Test",
            risk_explanation="Test",
            contributing_factors=[],
            safety_policy_guidance="None",
            historical_context="None",
            recommended_actions=[],
            provider="mock",
            model="mock",
            generated_at=datetime.now(timezone.utc),
        )

        with patch.object(
            AIOrchestrator, "analyze", return_value=mock_result,
        ) as mock_analyze:
            resp = client.post(
                "/api/ai/analyze",
                json={
                    "event_type": "ppe_detection",
                    "risk_score": 0.5,
                    "risk_level": "medium",
                },
                headers=_auth_header(token),
            )
            assert resp.status_code == 200
            # Verify org_id was passed correctly
            call_args = mock_analyze.call_args
            assert call_args.kwargs["org_id"] == _test_data["org_a_id"]

    def test_no_ai_view_permission_denied(self):
        """User without ai.view permission cannot access AI analysis."""
        token = _get_token(
            _test_data["viewer_a_id"],
            _test_data["org_a_id"],
            role_name="Viewer",
        )
        resp = client.post(
            "/api/ai/analyze",
            json={
                "event_type": "ppe_detection",
                "risk_score": 0.5,
                "risk_level": "medium",
            },
            headers=_auth_header(token),
        )
        assert resp.status_code == 403


# ==============================================================================
# 16–17. API Success / Failure Tests
# ==============================================================================

class TestAnalysisAPI:
    """API endpoint integration tests (mocked LLM)."""

    def setup_method(self):
        _setup_test_data()

    def test_api_success(self):
        """POST /api/ai/analyze returns structured analysis."""
        token = _get_token(
            _test_data["admin_a_id"], _test_data["org_a_id"],
        )

        mock_result = AIAnalysisResult(
            summary="PPE violation detected.",
            risk_explanation="High risk in active zone.",
            contributing_factors=["Missing hard hat"],
            safety_policy_guidance="Hard hats required.",
            historical_context="3 prior events.",
            recommended_actions=["Issue warning"],
            provider="gemini",
            model="gemini-2.0-flash",
            generated_at=datetime.now(timezone.utc),
        )

        with patch.object(
            AIOrchestrator, "analyze", return_value=mock_result,
        ):
            resp = client.post(
                "/api/ai/analyze",
                json={
                    "event_type": "ppe_detection",
                    "risk_score": 0.75,
                    "risk_level": "high",
                    "risk_explanation": "High risk",
                    "risk_factors": [],
                    "user_query": "What should I do?",
                },
                headers=_auth_header(token),
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["analysis"]["summary"] == "PPE violation detected."
            assert data["provider"] == "gemini"

    def test_api_failure_returns_error(self):
        """Failed LLM returns error in response."""
        token = _get_token(
            _test_data["admin_a_id"], _test_data["org_a_id"],
        )

        with patch.object(
            AIOrchestrator, "analyze",
            return_value={
                "success": False,
                "error": "Provider unavailable",
                "provider": "gemini",
                "model": "gemini-2.0-flash",
            },
        ):
            resp = client.post(
                "/api/ai/analyze",
                json={
                    "event_type": "ppe_detection",
                    "risk_score": 0.5,
                    "risk_level": "medium",
                },
                headers=_auth_header(token),
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is False
            assert "unavailable" in data["error"].lower()


# ==============================================================================
# 18–19. Missing API Key / Invalid Config Tests
# ==============================================================================

class TestConfigValidation:
    """Configuration validation tests."""

    def test_missing_gemini_api_key_handled(self):
        """Gemini provider with no API key returns controlled error."""
        provider = GeminiProvider()
        settings = get_settings()
        original_key = settings.gemini_api_key
        settings.gemini_api_key = None
        try:
            request = LLMRequest(system_prompt="t", user_prompt="t")
            result = provider.generate(request)
            assert not result.success
            assert "not configured" in result.error.lower()
        finally:
            settings.gemini_api_key = original_key

    def test_invalid_provider_config_handled(self):
        """Invalid provider name is handled gracefully."""
        settings = get_settings()
        original = settings.llm_primary_provider
        settings.llm_primary_provider = "nonexistent"
        try:
            request = LLMRequest(system_prompt="t", user_prompt="t")
            result = generate_with_fallback(request)
            assert not result.success
            assert "Unknown" in result.error
        finally:
            settings.llm_primary_provider = original


# ==============================================================================
# 20. Model Switching Tests
# ==============================================================================

class TestModelSwitching:
    """Model switching via configuration."""

    def test_gemini_model_from_config(self):
        """GeminiProvider reads model name from config."""
        settings = get_settings()
        original = settings.gemini_model
        settings.gemini_model = "gemini-pro-custom"
        try:
            provider = GeminiProvider()
            assert provider.model_name == "gemini-pro-custom"
        finally:
            settings.gemini_model = original

    def test_ollama_model_from_config(self):
        """OllamaProvider reads model name from config."""
        settings = get_settings()
        original = settings.ollama_model
        settings.ollama_model = "llama3:8b"
        try:
            provider = OllamaProvider()
            assert provider.model_name == "llama3:8b"
        finally:
            settings.ollama_model = original


# ==============================================================================
# Agent Context Building Tests
# ==============================================================================

class TestAgentContextBuilding:
    """Agent context building and prompt template tests."""

    def test_system_prompt_contains_rules(self):
        """System prompt contains safety analysis rules."""
        assert "ADVISORY" in SAFETY_SYSTEM_PROMPT
        assert "do NOT override" in SAFETY_SYSTEM_PROMPT.lower() or \
               "Do NOT" in SAFETY_SYSTEM_PROMPT
        assert "JSON" in SAFETY_SYSTEM_PROMPT

    def test_event_context_built(self):
        """InvestigationAgent builds event context."""
        ctx = InvestigationAgent.build_context(
            "ppe_detection", {"violation": "missing_hardhat"},
            camera_id="cam-1", zone_name="Zone A",
        )
        assert "ppe_detection" in ctx
        assert "cam-1" in ctx
        assert "Zone A" in ctx

    def test_emergency_context_for_critical(self):
        """EmergencyResponseAgent adds urgency for critical events."""
        ctx = EmergencyResponseAgent.build_context(
            "fire_smoke", "critical", MOCK_RISK_ASSESSMENT,
        )
        assert "EMERGENCY" in ctx
        assert "URGENT" in ctx

    def test_no_emergency_for_low_risk(self):
        """EmergencyResponseAgent no urgency for low risk."""
        low_risk = {**MOCK_RISK_ASSESSMENT, "risk_level": "low"}
        ctx = EmergencyResponseAgent.build_context(
            "ppe_detection", "low", low_risk,
        )
        assert "EMERGENCY" not in ctx

    def test_predictive_agent_recurring_pattern(self):
        """PredictiveSafetyAgent flags recurring patterns."""
        ctx = PredictiveSafetyAgent.build_context(recurrence_count=5)
        assert "RECURRING PATTERN" in ctx
        assert "5" in ctx

    def test_complete_prompt_assembled(self):
        """build_analysis_prompt assembles all sections."""
        prompt = build_analysis_prompt(
            event_context="EVENT: test",
            risk_context="RISK: high",
            rag_context="RAG: policy docs",
            historical_context="HISTORY: 3 events",
            user_query="What should I do?",
        )
        assert "EVENT: test" in prompt
        assert "RISK: high" in prompt
        assert "RAG: policy docs" in prompt
        assert "HISTORY: 3 events" in prompt
        assert "What should I do?" in prompt

    def test_providers_endpoint(self):
        """GET /api/ai/providers returns provider list."""
        _setup_test_data()
        token = _get_token(
            _test_data["admin_a_id"], _test_data["org_a_id"],
        )
        resp = client.get(
            "/api/ai/providers",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "active_provider" in data
        assert len(data["providers"]) == 3
        provider_names = [p["name"] for p in data["providers"]]
        assert "openrouter" in provider_names
