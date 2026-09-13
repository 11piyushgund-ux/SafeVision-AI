"""
Tests for visual_observations normalization in AIAnalysisResult and AIOrchestrator._parse_response.

Verifies:
1. List of strings (preserved unchanged)
2. List of structured dict observations (converted to readable strings)
3. Mixed string + dict observations
4. Malformed/unexpected observation values (handled safely without crashing)
"""

import json
from app.schemas.ai_analysis import AIAnalysisResult, _format_visual_observation
from app.services.llm.orchestrator import AIOrchestrator


class TestVisualObservationsNormalization:
    """Test suite for visual_observations normalization."""

    def test_1_list_of_strings_preserved(self):
        """Plain string observations pass through unchanged."""
        obs = [
            "Smoke plume originating from conveyor belt.",
            "No personnel visible in the immediate hazard zone.",
        ]
        result = AIAnalysisResult(
            summary="Test summary",
            risk_explanation="Test risk explanation",
            provider="ollama",
            model="qwen2.5:3b-instruct",
            visual_observations=obs,
        )
        assert result.visual_observations == obs

    def test_2_structured_dicts_converted_to_strings(self):
        """Structured dict observations are converted to readable strings."""
        raw_obs = [
            {"title": "Smoke Detection", "details": "Smoke is visible in the detected area."},
            {"title": "Personnel in the area", "details": "moved to a safe area."},
            {"title": "Equipment and machinery", "details": "verified safe and available."},
            {"title": "Environmental factors", "details": "assessed and addressed."},
            {"title": "Bounding Box Analysis", "details": "secure and free of hazards."},
        ]
        result = AIAnalysisResult(
            summary="Test summary",
            risk_explanation="Test risk explanation",
            provider="ollama",
            model="qwen2.5:3b-instruct",
            visual_observations=raw_obs,
        )
        assert len(result.visual_observations) == 5
        assert result.visual_observations[0] == "Smoke Detection: Smoke is visible in the detected area."
        assert result.visual_observations[1] == "Personnel in the area: moved to a safe area."
        assert result.visual_observations[2] == "Equipment and machinery: verified safe and available."
        assert result.visual_observations[3] == "Environmental factors: assessed and addressed."
        assert result.visual_observations[4] == "Bounding Box Analysis: secure and free of hazards."

    def test_3_mixed_strings_and_dicts(self):
        """Mixed list of strings and dicts are all normalized to strings."""
        raw_obs = [
            "Dense smoke plume visible on the left.",
            {"title": "Exits", "details": "Emergency exit door is unblocked."},
            {"title": "PPE Status", "description": "Worker wearing high-vis vest."},
            "Ambient lighting is adequate.",
        ]
        result = AIAnalysisResult(
            summary="Test summary",
            risk_explanation="Test risk explanation",
            provider="ollama",
            model="qwen2.5:3b-instruct",
            visual_observations=raw_obs,
        )
        assert len(result.visual_observations) == 4
        assert result.visual_observations[0] == "Dense smoke plume visible on the left."
        assert result.visual_observations[1] == "Exits: Emergency exit door is unblocked."
        assert result.visual_observations[2] == "PPE Status: Worker wearing high-vis vest."
        assert result.visual_observations[3] == "Ambient lighting is adequate."

    def test_4_malformed_and_unexpected_values(self):
        """Malformed or non-standard observation shapes are handled safely."""
        raw_obs = [
            {"title": "Fire Alarm Only"},  # title only
            {"observation": "Sparks near grinding station"},  # observation key only
            {"description": "Oil slick on concrete floor"},  # description key only
            {"location": "Section 4", "hazard": "Tripping wire"},  # generic keys
            {},  # empty dict -> omitted
            "",  # empty string -> omitted
            "   ",  # whitespace string -> omitted
            123,  # scalar integer
        ]
        result = AIAnalysisResult(
            summary="Test summary",
            risk_explanation="Test risk explanation",
            provider="ollama",
            model="qwen2.5:3b-instruct",
            visual_observations=raw_obs,
        )
        # Empty dict and empty strings are filtered out
        assert len(result.visual_observations) == 5
        assert result.visual_observations[0] == "Fire Alarm Only"
        assert result.visual_observations[1] == "Sparks near grinding station"
        assert result.visual_observations[2] == "Oil slick on concrete floor"
        assert "Tripping wire" in result.visual_observations[3]
        assert result.visual_observations[4] == "123"

    def test_5_missing_or_empty_visual_observations(self):
        """Empty or missing visual_observations defaults cleanly to empty list."""
        r1 = AIAnalysisResult(
            summary="Summary",
            risk_explanation="Risk",
            provider="ollama",
            model="qwen2.5:3b-instruct",
            visual_observations=[],
        )
        assert r1.visual_observations == []

        r2 = AIAnalysisResult(
            summary="Summary",
            risk_explanation="Risk",
            provider="ollama",
            model="qwen2.5:3b-instruct",
            visual_observations=None,
        )
        assert r2.visual_observations == []

    def test_6_orchestrator_parse_response_with_structured_dicts(self):
        """AIOrchestrator._parse_response parses LLM JSON containing dict visual_observations."""
        llm_payload = {
            "summary": "Fire/smoke event confirmed in production cell.",
            "risk_explanation": "Risk score 0.743 is HIGH.",
            "visual_observations": [
                {"title": "Smoke Detection", "details": "Smoke is visible in the detected area."},
                {"title": "Personnel in the area", "details": "moved to a safe area."},
                {"title": "Equipment and machinery", "details": "verified safe and available."},
                {"title": "Environmental factors", "details": "assessed and addressed."},
                {"title": "Bounding Box Analysis", "details": "secure and free of hazards."},
            ],
            "visual_validation": {
                "detection_supported": True,
                "confidence_note": "Smoke presence confirmed.",
            },
            "immediate_actions": [
                {
                    "title": "Evacuate Area",
                    "procedure": "Evacuate personnel immediately.",
                    "role": "Floor Supervisor",
                }
            ],
            "investigation_actions": [],
            "preventive_actions": [],
            "contributing_factors": ["High temperature", "Combustible materials"],
        }

        raw_content = json.dumps(llm_payload)
        result = AIOrchestrator._parse_response(
            raw_content=raw_content,
            provider="ollama",
            model="qwen2.5:3b-instruct",
        )

        assert isinstance(result, AIAnalysisResult)
        assert len(result.visual_observations) == 5
        assert result.visual_observations[0] == "Smoke Detection: Smoke is visible in the detected area."
        assert result.visual_observations[1] == "Personnel in the area: moved to a safe area."
        assert result.visual_observations[2] == "Equipment and machinery: verified safe and available."
        assert result.visual_observations[3] == "Environmental factors: assessed and addressed."
        assert result.visual_observations[4] == "Bounding Box Analysis: secure and free of hazards."
        assert result.visual_validation["detection_supported"] is True
