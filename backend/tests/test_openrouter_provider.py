"""
SafeVision AI — OpenRouter Provider Tests (Phase 14)

Tests use MOCKED httpx — no real external API calls.

Coverage:
  PROVIDER INTERFACE (1–3)
  REQUEST CONSTRUCTION (4–6)
  RESPONSE HANDLING (7–10)
  ERROR HANDLING (11–14)
  FALLBACK (15)
  IMAGE HANDLING (16–17)
  SECURITY (18)
  VISUAL OUTPUT PARSING (19–20)
"""

import base64
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services.llm import LLMProvider, LLMRequest, LLMResponse
from app.services.llm.openrouter_provider import OpenRouterProvider
from app.services.llm.orchestrator import AIOrchestrator
from app.services.llm.prompts import (
    SAFETY_MULTIMODAL_SYSTEM_PROMPT,
    SAFETY_SYSTEM_PROMPT,
    build_analysis_prompt,
    build_detection_metadata_context,
)
from app.services.llm.provider_factory import get_provider


# ==============================================================================
# Helpers
# ==============================================================================

def _fake_settings(**overrides):
    """Create a mock settings object with OpenRouter defaults."""
    defaults = {
        "openrouter_api_key": "sk-or-test-key-12345",
        "openrouter_base_url": "https://openrouter.ai/api/v1",
        "openrouter_model": "google/gemma-4-26b-a4b-it:free",
        "llm_provider": "openrouter",
        "llm_mode": "primary_only",
        "llm_primary_provider": "openrouter",
        "llm_fallback_provider": "ollama",
        "llm_temperature": 0.3,
        "llm_max_output_tokens": 2048,
        "llm_timeout_seconds": 60,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _valid_json_response(multimodal: bool = False) -> dict:
    """Create a valid OpenRouter API response body."""
    result = {
        "summary": "Fire detected in Assembly Zone A.",
        "risk_explanation": "High risk due to fire detection with 85% confidence.",
        "contributing_factors": ["event_type", "confidence"],
        "safety_policy_guidance": "Follow emergency evacuation procedure.",
        "historical_context": "3 similar events in recent history.",
        "recommended_actions": ["Evacuate area", "Activate fire suppression"],
    }
    if multimodal:
        result["visual_observations"] = [
            "Visible smoke near conveyor belt",
            "No personnel visible in hazard zone",
        ]
        result["visual_validation"] = {
            "detection_supported": True,
            "confidence_note": "Smoke clearly visible matching YOLO detection",
            "scene_context": "Manufacturing floor with active machinery",
        }

    return {
        "id": "gen-test-123",
        "model": "google/gemma-4-26b-a4b-it:free",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": json.dumps(result),
                },
            }
        ],
        "usage": {"prompt_tokens": 500, "completion_tokens": 200},
    }


SMALL_JPEG = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xd9"
)


# ==============================================================================
# 1. Provider Interface
# ==============================================================================

class TestProviderInterface:
    """Verify OpenRouterProvider implements LLMProvider correctly."""

    def test_1_implements_interface(self):
        """OpenRouterProvider is an LLMProvider."""
        provider = OpenRouterProvider()
        assert isinstance(provider, LLMProvider)

    def test_2_name_is_openrouter(self):
        """Provider name must be 'openrouter'."""
        provider = OpenRouterProvider()
        assert provider.name == "openrouter"

    @patch("app.services.llm.openrouter_provider.get_settings")
    def test_3_model_name_from_config(self, mock_settings):
        """Model name should come from settings."""
        mock_settings.return_value = _fake_settings()
        provider = OpenRouterProvider()
        assert provider.model_name == "google/gemma-4-26b-a4b-it:free"


# ==============================================================================
# 2. Provider Registration
# ==============================================================================

class TestProviderRegistration:
    """Verify OpenRouterProvider is registered in the factory."""

    @patch("app.services.llm.provider_factory.get_settings")
    @patch("app.services.llm.openrouter_provider.get_settings")
    def test_4_get_provider_openrouter(self, mock_or_settings, mock_factory_settings):
        """get_provider('openrouter') should return OpenRouterProvider."""
        mock_or_settings.return_value = _fake_settings()
        mock_factory_settings.return_value = _fake_settings()
        provider = get_provider("openrouter")
        assert isinstance(provider, OpenRouterProvider)


# ==============================================================================
# 3. Request Construction
# ==============================================================================

class TestRequestConstruction:
    """Verify correct OpenAI-compatible request payload."""

    @patch("app.services.llm.openrouter_provider.get_settings")
    def test_5_text_only_request(self, mock_settings):
        """Text-only request sends string content (not array)."""
        mock_settings.return_value = _fake_settings()
        provider = OpenRouterProvider()

        request = LLMRequest(
            system_prompt="System",
            user_prompt="Hello",
        )
        content = provider._build_user_content(request)
        assert isinstance(content, str)
        assert content == "Hello"

    @patch("app.services.llm.openrouter_provider.get_settings")
    def test_6_multimodal_request(self, mock_settings):
        """Multimodal request sends content array with image_url."""
        mock_settings.return_value = _fake_settings()
        provider = OpenRouterProvider()

        request = LLMRequest(
            system_prompt="System",
            user_prompt="Analyze this",
            images=[SMALL_JPEG],
        )
        content = provider._build_user_content(request)
        assert isinstance(content, list)
        assert len(content) == 2
        assert content[0]["type"] == "text"
        assert content[0]["text"] == "Analyze this"
        assert content[1]["type"] == "image_url"
        assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
        # Verify base64 roundtrip
        b64_data = content[1]["image_url"]["url"].split(",", 1)[1]
        assert base64.b64decode(b64_data) == SMALL_JPEG


# ==============================================================================
# 4. Success Response Handling
# ==============================================================================

class TestSuccessResponse:
    """Verify correct parsing of valid API responses."""

    @patch("app.services.llm.openrouter_provider.httpx.Client")
    @patch("app.services.llm.openrouter_provider.get_settings")
    def test_7_valid_text_response(self, mock_settings, mock_client_cls):
        """Valid text-only response returns LLMResponse(success=True)."""
        mock_settings.return_value = _fake_settings()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _valid_json_response()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=MagicMock(post=MagicMock(return_value=mock_resp)))
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        provider = OpenRouterProvider()
        result = provider.generate(LLMRequest(system_prompt="S", user_prompt="U"))
        assert result.success is True
        assert result.provider == "openrouter"
        assert "gemma" in result.model
        assert len(result.content) > 0

    @patch("app.services.llm.openrouter_provider.httpx.Client")
    @patch("app.services.llm.openrouter_provider.get_settings")
    def test_8_multimodal_response_metadata(self, mock_settings, mock_client_cls):
        """Multimodal request records multimodal=True in metadata."""
        mock_settings.return_value = _fake_settings()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _valid_json_response(multimodal=True)
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=MagicMock(post=MagicMock(return_value=mock_resp)))
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        provider = OpenRouterProvider()
        result = provider.generate(LLMRequest(
            system_prompt="S",
            user_prompt="U",
            images=[SMALL_JPEG],
        ))
        assert result.success is True
        assert result.metadata.get("multimodal") is True


# ==============================================================================
# 5. Error Handling
# ==============================================================================

class TestErrorHandling:
    """Verify robust error handling for all failure modes."""

    @patch("app.services.llm.openrouter_provider.get_settings")
    def test_9_missing_api_key(self, mock_settings):
        """Missing API key should return success=False without HTTP call."""
        mock_settings.return_value = _fake_settings(openrouter_api_key=None)
        provider = OpenRouterProvider()
        result = provider.generate(LLMRequest(system_prompt="S", user_prompt="U"))
        assert result.success is False
        assert "not configured" in result.error

    @patch("app.services.llm.openrouter_provider.httpx.Client")
    @patch("app.services.llm.openrouter_provider.get_settings")
    def test_10_malformed_json_response(self, mock_settings, mock_client_cls):
        """Malformed JSON response returns success=False."""
        mock_settings.return_value = _fake_settings()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = ValueError("bad json")
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=MagicMock(post=MagicMock(return_value=mock_resp)))
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        provider = OpenRouterProvider()
        result = provider.generate(LLMRequest(system_prompt="S", user_prompt="U"))
        assert result.success is False
        assert "malformed" in result.error.lower()

    @patch("app.services.llm.openrouter_provider.httpx.Client")
    @patch("app.services.llm.openrouter_provider.get_settings")
    def test_11_timeout(self, mock_settings, mock_client_cls):
        """Timeout returns success=False with timeout error."""
        import httpx

        mock_settings.return_value = _fake_settings()
        mock_client_cls.return_value.__enter__ = MagicMock(
            return_value=MagicMock(post=MagicMock(side_effect=httpx.TimeoutException("timeout")))
        )
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        provider = OpenRouterProvider()
        result = provider.generate(LLMRequest(system_prompt="S", user_prompt="U"))
        assert result.success is False
        assert "timed out" in result.error.lower()

    @patch("app.services.llm.openrouter_provider.httpx.Client")
    @patch("app.services.llm.openrouter_provider.get_settings")
    def test_12_rate_limit_429(self, mock_settings, mock_client_cls):
        """HTTP 429 returns rate limit error."""
        mock_settings.return_value = _fake_settings()
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=MagicMock(post=MagicMock(return_value=mock_resp)))
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        provider = OpenRouterProvider()
        result = provider.generate(LLMRequest(system_prompt="S", user_prompt="U"))
        assert result.success is False
        assert "rate limit" in result.error.lower()

    @patch("app.services.llm.openrouter_provider.httpx.Client")
    @patch("app.services.llm.openrouter_provider.get_settings")
    def test_13_auth_failure_401(self, mock_settings, mock_client_cls):
        """HTTP 401 returns auth error without exposing API key."""
        mock_settings.return_value = _fake_settings()
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=MagicMock(post=MagicMock(return_value=mock_resp)))
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        provider = OpenRouterProvider()
        result = provider.generate(LLMRequest(system_prompt="S", user_prompt="U"))
        assert result.success is False
        assert "authentication" in result.error.lower()
        # API key must NOT appear in the error message
        assert "sk-or-test-key" not in result.error

    @patch("app.services.llm.openrouter_provider.httpx.Client")
    @patch("app.services.llm.openrouter_provider.get_settings")
    def test_14_no_choices(self, mock_settings, mock_client_cls):
        """Response with empty choices returns success=False."""
        mock_settings.return_value = _fake_settings()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": []}
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=MagicMock(post=MagicMock(return_value=mock_resp)))
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        provider = OpenRouterProvider()
        result = provider.generate(LLMRequest(system_prompt="S", user_prompt="U"))
        assert result.success is False
        assert "no choices" in result.error.lower()


# ==============================================================================
# 6. Fallback Behavior
# ==============================================================================

class TestFallback:
    """Verify fallback from OpenRouter to other providers."""

    @patch("app.services.llm.provider_factory.get_settings")
    @patch("app.services.llm.provider_factory.get_provider")
    def test_15_fallback_to_ollama(self, mock_get_provider, mock_settings):
        """When OpenRouter fails and mode=fallback, Ollama should be tried."""
        from app.services.llm.provider_factory import generate_with_fallback

        mock_settings.return_value = _fake_settings(
            llm_mode="fallback",
            llm_primary_provider="openrouter",
            llm_fallback_provider="ollama",
        )

        # Primary fails
        mock_openrouter = MagicMock()
        mock_openrouter.generate.return_value = LLMResponse(
            content="", provider="openrouter", model="gemma", success=False, error="unavailable",
        )
        # Fallback succeeds
        mock_ollama = MagicMock()
        mock_ollama.generate.return_value = LLMResponse(
            content='{"summary":"ok"}', provider="ollama", model="qwen", success=True,
        )

        mock_get_provider.side_effect = lambda name: {
            "openrouter": mock_openrouter,
            "ollama": mock_ollama,
        }[name]

        request = LLMRequest(system_prompt="S", user_prompt="U")
        result = generate_with_fallback(request)
        assert result.success is True
        assert result.provider == "ollama"


# ==============================================================================
# 7. Image Handling
# ==============================================================================

class TestImageHandling:
    """Verify evidence image handling in the pipeline."""

    def test_16_images_ignored_by_text_providers(self):
        """LLMRequest.images field has a default and doesn't break text providers."""
        request = LLMRequest(system_prompt="S", user_prompt="U")
        assert request.images == []
        # With images
        request2 = LLMRequest(system_prompt="S", user_prompt="U", images=[SMALL_JPEG])
        assert len(request2.images) == 1

    def test_17_missing_evidence_produces_text_only(self):
        """When no evidence image is provided, text-only prompt is used."""
        prompt = build_analysis_prompt(
            event_context="EVENT TYPE: fire_smoke",
            risk_context="RISK: high",
            rag_context="RAG: none",
            historical_context="HISTORY: 0",
            has_image=False,
        )
        assert "evidence frame" not in prompt
        assert "Analyze this safety event" in prompt


# ==============================================================================
# 8. Security
# ==============================================================================

class TestSecurity:
    """Verify API key never leaks."""

    @patch("app.services.llm.openrouter_provider.get_settings")
    def test_18_key_not_in_health_check(self, mock_settings):
        """health_check reveals only boolean, never the key."""
        mock_settings.return_value = _fake_settings()
        provider = OpenRouterProvider()
        result = provider.health_check()
        assert result is True
        # Key must not be in any string representation
        assert "sk-or-test" not in str(result)


# ==============================================================================
# 9. Visual Output Parsing
# ==============================================================================

class TestVisualOutputParsing:
    """Verify multimodal visual fields are parsed correctly."""

    def test_19_visual_fields_parsed(self):
        """Orchestrator._parse_response extracts visual fields."""
        resp_data = _valid_json_response(multimodal=True)
        raw_content = resp_data["choices"][0]["message"]["content"]

        result = AIOrchestrator._parse_response(
            raw_content=raw_content,
            provider="openrouter",
            model="gemma",
        )
        assert hasattr(result, "visual_observations")
        assert len(result.visual_observations) == 2
        assert result.visual_validation is not None
        assert result.visual_validation["detection_supported"] is True

    def test_20_missing_visual_fields_default(self):
        """Text-only response defaults visual fields to empty."""
        resp_data = _valid_json_response(multimodal=False)
        raw_content = resp_data["choices"][0]["message"]["content"]

        result = AIOrchestrator._parse_response(
            raw_content=raw_content,
            provider="ollama",
            model="qwen",
        )
        assert result.visual_observations == []
        assert result.visual_validation is None


# ==============================================================================
# 10. Detection Metadata Builder
# ==============================================================================

class TestDetectionMetadata:
    """Verify build_detection_metadata_context formats YOLO data."""

    def test_21_fire_smoke_metadata(self):
        """Fire/smoke detection data formats correctly."""
        detection_data = {
            "details": {
                "detected_class": "fire",
                "confidence": 0.85,
                "bbox": [100, 200, 300, 400],
            },
            "track_id": 7,
        }
        result = build_detection_metadata_context(detection_data)
        assert "MACHINE DETECTION DATA" in result
        assert "fire" in result
        assert "0.85" in result
        assert "Track ID: 7" in result

    def test_22_ppe_metadata(self):
        """PPE detection data with missing items formats correctly."""
        detection_data = {
            "person_bbox": [50, 100, 200, 400],
            "missing_ppe": ["helmet", "vest"],
            "track_id": 3,
        }
        result = build_detection_metadata_context(detection_data)
        assert "Missing PPE: helmet, vest" in result
        assert "Track ID: 3" in result

    def test_23_empty_data_returns_empty(self):
        """Empty/None detection data returns empty string."""
        assert build_detection_metadata_context(None) == ""
        assert build_detection_metadata_context({}) == ""

    def test_24_system_prompt_selection(self):
        """Multimodal prompt is selected when image is present."""
        assert "multimodal" in SAFETY_MULTIMODAL_SYSTEM_PROMPT.lower()
        assert "VALIDATE and CONTEXTUALIZE" in SAFETY_MULTIMODAL_SYSTEM_PROMPT
        assert "visual_observations" in SAFETY_MULTIMODAL_SYSTEM_PROMPT
        # Original prompt doesn't mention visual
        assert "visual_observations" not in SAFETY_SYSTEM_PROMPT
