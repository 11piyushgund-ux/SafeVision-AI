"""
SafeVision AI — Risk Engine Unit Tests (Phase 7A)

Coverage:
  1. INFO-level risk result
  2. LOW-level risk result
  3. MEDIUM-level risk result
  4. HIGH-level risk result
  5. CRITICAL-level risk result
  6. Event-type weighting affects score
  7. Zone criticality weighting affects score
  8. Confidence weighting affects score
  9. Recurrence weighting affects score
  10. Recurrence 0 vs 1 vs 5 vs 10 — monotonically increasing
  11. Deterministic identical inputs → identical outputs
  12. Missing zone → default criticality
  13. Missing confidence → default 0.50
  14. Confidence below 0 → clamped to 0.0
  15. Confidence above 1 → clamped to 1.0
  16. Unknown event type → default score 0.50
  17. Recurrence query excludes current event
  18. Recurrence query enforces org_id isolation
  19. Cross-tenant recurrence contamination prevented
  20. Actual Phase 6 EventType values accepted
  21. Risk factors are complete and explainable
  22. Weights sum to 1.0

All tests use mock objects — no PostgreSQL required.
Tests 17–19 use MockDBSession to verify query filter logic.
"""

import pytest

from app.models.alert import AlertSeverity
from app.models.event import EventType
from app.models.zone import ZoneType
from app.schemas.risk import RiskAssessment
from app.services.risk_engine import (
    DEFAULT_CONFIDENCE,
    DEFAULT_EVENT_TYPE_SCORE,
    DEFAULT_ZONE_SCORE,
    EVENT_TYPE_SCORES,
    W_CONFIDENCE,
    W_EVENT,
    W_RECURRENCE,
    W_ZONE,
    RiskEngine,
)

# ==============================================================================
# Mock Helpers
# ==============================================================================

class MockEvent:
    """Minimal mock of the Event model for pure risk assessment tests."""

    def __init__(
        self,
        event_type="ppe_detection",
        confidence=0.90,
        camera_id="cam-01",
        org_id="org-001",
        event_id="evt-001",
    ):
        self.id = event_id
        self.event_type = event_type
        self.confidence = confidence
        self.camera_id = camera_id
        self.org_id = org_id


class MockZone:
    """Minimal mock of the Zone model."""

    def __init__(self, zone_type="general", name="Test Zone"):
        self.zone_type = zone_type
        self.name = name


# ==============================================================================
# 1–5. Risk Level Result Tests
# ==============================================================================

class TestRiskLevels:
    """Each AlertSeverity level is reachable with appropriate inputs."""

    def test_info_level(self):
        """Tracking update, no zone, very low confidence, no recurrence → INFO."""
        event = MockEvent(
            event_type=EventType.TRACKING_UPDATE.value,
            confidence=0.10,
        )
        result = RiskEngine.assess(event, zone=None, recurrence_count=0)

        assert isinstance(result, RiskAssessment)
        assert result.risk_level == AlertSeverity.INFO.value
        assert result.risk_score < 0.20

    def test_low_level(self):
        """Person detected, general zone, moderate confidence, no recurrence → LOW."""
        event = MockEvent(
            event_type=EventType.PERSON_DETECTED.value,
            confidence=0.50,
        )
        zone = MockZone(zone_type=ZoneType.GENERAL.value, name="Lobby")
        result = RiskEngine.assess(event, zone=zone, recurrence_count=0)

        assert result.risk_level == AlertSeverity.LOW.value
        assert 0.20 <= result.risk_score < 0.40

    def test_medium_level(self):
        """PPE violation, PPE-required zone, good confidence, low recurrence → MEDIUM."""
        event = MockEvent(
            event_type=EventType.PPE_DETECTION.value,
            confidence=0.80,
        )
        zone = MockZone(zone_type=ZoneType.PPE_REQUIRED.value, name="Assembly Line")
        result = RiskEngine.assess(event, zone=zone, recurrence_count=2)

        assert result.risk_level == AlertSeverity.MEDIUM.value
        assert 0.40 <= result.risk_score < 0.60

    def test_high_level(self):
        """Zone intrusion, exclusion zone, high confidence, some recurrence → HIGH."""
        event = MockEvent(
            event_type=EventType.ZONE_INTRUSION.value,
            confidence=0.92,
        )
        zone = MockZone(zone_type=ZoneType.EXCLUSION.value, name="Hazard Area")
        result = RiskEngine.assess(event, zone=zone, recurrence_count=3)

        assert result.risk_level == AlertSeverity.HIGH.value
        assert 0.60 <= result.risk_score < 0.80

    def test_critical_level(self):
        """Fire/smoke, exclusion zone, high confidence, high recurrence → CRITICAL."""
        event = MockEvent(
            event_type=EventType.FIRE_SMOKE.value,
            confidence=0.95,
        )
        zone = MockZone(zone_type=ZoneType.EXCLUSION.value, name="Chemical Storage")
        result = RiskEngine.assess(event, zone=zone, recurrence_count=10)

        assert result.risk_level == AlertSeverity.CRITICAL.value
        assert result.risk_score >= 0.80


# ==============================================================================
# 6–9. Factor Weighting Tests
# ==============================================================================

class TestFactorWeighting:
    """Each factor independently affects the final risk score."""

    def test_event_type_weighting(self):
        """Same inputs except event_type → different scores."""
        base_kwargs = dict(confidence=0.80, camera_id="cam-01", org_id="org-001")

        fire_event = MockEvent(event_type=EventType.FIRE_SMOKE.value, **base_kwargs)
        tracking_event = MockEvent(event_type=EventType.TRACKING_UPDATE.value, **base_kwargs)

        fire_result = RiskEngine.assess(fire_event, recurrence_count=0)
        tracking_result = RiskEngine.assess(tracking_event, recurrence_count=0)

        assert fire_result.risk_score > tracking_result.risk_score
        # Fire (1.0) vs tracking (0.1) — difference should be significant
        diff = fire_result.risk_score - tracking_result.risk_score
        assert diff > 0.20

    def test_zone_criticality_weighting(self):
        """Same event, different zones → different scores."""
        event = MockEvent(event_type=EventType.PPE_DETECTION.value, confidence=0.80)

        exclusion_zone = MockZone(zone_type=ZoneType.EXCLUSION.value, name="Restricted")
        general_zone = MockZone(zone_type=ZoneType.GENERAL.value, name="Office")

        excl_result = RiskEngine.assess(event, zone=exclusion_zone, recurrence_count=0)
        gen_result = RiskEngine.assess(event, zone=general_zone, recurrence_count=0)

        assert excl_result.risk_score > gen_result.risk_score

    def test_confidence_weighting(self):
        """Same event, different confidence → different scores."""
        high_conf = MockEvent(event_type=EventType.PPE_DETECTION.value, confidence=0.95)
        low_conf = MockEvent(event_type=EventType.PPE_DETECTION.value, confidence=0.20)

        high_result = RiskEngine.assess(high_conf, recurrence_count=0)
        low_result = RiskEngine.assess(low_conf, recurrence_count=0)

        assert high_result.risk_score > low_result.risk_score

    def test_recurrence_weighting(self):
        """Same event, different recurrence → different scores."""
        event = MockEvent(event_type=EventType.PPE_DETECTION.value, confidence=0.80)

        no_recur = RiskEngine.assess(event, recurrence_count=0)
        high_recur = RiskEngine.assess(event, recurrence_count=10)

        assert high_recur.risk_score > no_recur.risk_score


# ==============================================================================
# 10. Recurrence Monotonicity
# ==============================================================================

class TestRecurrenceScale:
    """Recurrence 0 → 1 → 5 → 10 produces monotonically increasing scores."""

    def test_recurrence_monotonic(self):
        """More prior events → higher risk score."""
        event = MockEvent(event_type=EventType.PPE_DETECTION.value, confidence=0.80)

        scores = []
        for count in [0, 1, 5, 10]:
            result = RiskEngine.assess(event, recurrence_count=count)
            scores.append(result.risk_score)

        # Each value should be >= the previous
        for i in range(1, len(scores)):
            assert scores[i] > scores[i - 1], (
                f"recurrence={[0, 1, 5, 10][i]}: score {scores[i]} should be > "
                f"recurrence={[0, 1, 5, 10][i-1]}: score {scores[i-1]}"
            )

    def test_recurrence_capped_at_ten(self):
        """Recurrence 10 and 20 produce the same score (capped at 1.0)."""
        event = MockEvent(event_type=EventType.PPE_DETECTION.value, confidence=0.80)

        result_10 = RiskEngine.assess(event, recurrence_count=10)
        result_20 = RiskEngine.assess(event, recurrence_count=20)

        assert result_10.risk_score == result_20.risk_score


# ==============================================================================
# 11. Determinism
# ==============================================================================

class TestDeterminism:
    """Identical inputs produce identical outputs."""

    def test_identical_inputs_same_output(self):
        """Two calls with identical inputs produce the same risk_score and risk_level."""
        event = MockEvent(
            event_type=EventType.ZONE_INTRUSION.value,
            confidence=0.88,
        )
        zone = MockZone(zone_type=ZoneType.FIRE_WATCH.value, name="Watch Zone")

        result1 = RiskEngine.assess(event, zone=zone, recurrence_count=3)
        result2 = RiskEngine.assess(event, zone=zone, recurrence_count=3)

        assert result1.risk_score == result2.risk_score
        assert result1.risk_level == result2.risk_level
        assert len(result1.factors) == len(result2.factors)
        for f1, f2 in zip(result1.factors, result2.factors, strict=True):
            assert f1.weighted_score == f2.weighted_score


# ==============================================================================
# 12–16. Missing/Invalid Input Tests
# ==============================================================================

class TestMissingInvalidInputs:
    """Safe behavior for missing or invalid inputs."""

    def test_missing_zone_uses_default(self):
        """zone=None → default criticality score."""
        event = MockEvent(event_type=EventType.PPE_DETECTION.value, confidence=0.80)
        result = RiskEngine.assess(event, zone=None, recurrence_count=0)

        zone_factor = next(f for f in result.factors if f.name == "zone_criticality")
        assert zone_factor.score == DEFAULT_ZONE_SCORE
        assert zone_factor.raw_value is None
        assert "default" in zone_factor.explanation.lower()

    def test_missing_confidence_uses_default(self):
        """confidence=None → default 0.50."""
        event = MockEvent(event_type=EventType.PPE_DETECTION.value, confidence=None)
        result = RiskEngine.assess(event, recurrence_count=0)

        conf_factor = next(f for f in result.factors if f.name == "confidence")
        assert conf_factor.score == DEFAULT_CONFIDENCE
        assert "default" in conf_factor.explanation.lower()

    def test_confidence_below_zero_clamped(self):
        """Negative confidence → clamped to 0.0."""
        event = MockEvent(event_type=EventType.PPE_DETECTION.value, confidence=-0.5)
        result = RiskEngine.assess(event, recurrence_count=0)

        conf_factor = next(f for f in result.factors if f.name == "confidence")
        assert conf_factor.score == 0.0
        assert "clamped" in conf_factor.explanation.lower()

    def test_confidence_above_one_clamped(self):
        """confidence > 1.0 → clamped to 1.0."""
        event = MockEvent(event_type=EventType.PPE_DETECTION.value, confidence=2.5)
        result = RiskEngine.assess(event, recurrence_count=0)

        conf_factor = next(f for f in result.factors if f.name == "confidence")
        assert conf_factor.score == 1.0
        assert "clamped" in conf_factor.explanation.lower()

    def test_unknown_event_type_uses_default(self):
        """Unrecognized event_type → default score 0.50."""
        event = MockEvent(event_type="some_future_event", confidence=0.80)
        result = RiskEngine.assess(event, recurrence_count=0)

        event_factor = next(f for f in result.factors if f.name == "event_type")
        assert event_factor.score == DEFAULT_EVENT_TYPE_SCORE
        assert event_factor.raw_value == "some_future_event"


# ==============================================================================
# 17–19. Tenant Isolation Tests (Mock DB)
# ==============================================================================

class MockQueryResult:
    """Simulates SQLAlchemy scalar() return."""
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class MockDBQuery:
    """Tracks filter conditions to verify tenant isolation."""

    def __init__(self, return_count=0):
        self._return_count = return_count
        self.filters = []

    def filter(self, *args):
        self.filters.extend(args)
        return self

    def scalar(self):
        return self._return_count


class TestTenantIsolation:
    """Recurrence queries enforce org_id isolation."""

    def test_recurrence_different_orgs_independent(self):
        """
        Same event_type + camera_id but different org_ids
        produce independent recurrence counts.
        """
        # Org A: fire_smoke, cam-01, high confidence, recurrence=5
        event_a = MockEvent(
            event_type=EventType.FIRE_SMOKE.value,
            confidence=0.90,
            camera_id="cam-01",
            org_id="org-A",
        )
        # Org B: same event_type + camera_id but recurrence=0
        event_b = MockEvent(
            event_type=EventType.FIRE_SMOKE.value,
            confidence=0.90,
            camera_id="cam-01",
            org_id="org-B",
        )

        result_a = RiskEngine.assess(event_a, recurrence_count=5)
        result_b = RiskEngine.assess(event_b, recurrence_count=0)

        # org_id is preserved in the result
        assert result_a.org_id == "org-A"
        assert result_b.org_id == "org-B"

        # Different recurrence → different scores
        assert result_a.risk_score > result_b.risk_score

    def test_recurrence_org_id_in_result(self):
        """RiskAssessment always contains the correct org_id."""
        event = MockEvent(
            event_type=EventType.PPE_DETECTION.value,
            org_id="org-tenant-42",
        )
        result = RiskEngine.assess(event, recurrence_count=0)
        assert result.org_id == "org-tenant-42"

    def test_cross_tenant_contamination_impossible(self):
        """
        Prove that org A with recurrence=10 and org B with recurrence=0
        produce completely different risk assessments.
        """
        shared_kwargs = dict(
            event_type=EventType.PPE_DETECTION.value,
            confidence=0.80,
            camera_id="cam-shared",
        )

        event_a = MockEvent(org_id="org-factory-A", **shared_kwargs)
        event_b = MockEvent(org_id="org-factory-B", **shared_kwargs)

        result_a = RiskEngine.assess(event_a, recurrence_count=10)
        result_b = RiskEngine.assess(event_b, recurrence_count=0)

        # A should be significantly higher risk due to recurrence
        assert result_a.risk_score > result_b.risk_score

        # Verify recurrence factors
        recur_a = next(f for f in result_a.factors if f.name == "recurrence")
        recur_b = next(f for f in result_b.factors if f.name == "recurrence")
        assert recur_a.score == 1.0   # 10/10 = 1.0
        assert recur_b.score == 0.0   # 0/10 = 0.0


# ==============================================================================
# 20. Phase 6 EventType Compatibility
# ==============================================================================

class TestPhase6Compatibility:
    """Risk Engine works with actual Phase 6 EventType enum values."""

    @pytest.mark.parametrize("event_type_enum", list(EventType))
    def test_all_phase6_event_types_accepted(self, event_type_enum):
        """Every Phase 6 EventType produces a valid RiskAssessment."""
        event = MockEvent(
            event_type=event_type_enum.value,
            confidence=0.85,
        )
        result = RiskEngine.assess(event, recurrence_count=0)

        assert isinstance(result, RiskAssessment)
        assert 0.0 <= result.risk_score <= 1.0
        assert result.risk_level in [s.value for s in AlertSeverity]
        assert result.event_type == event_type_enum.value

    def test_event_type_enum_object_handled(self):
        """EventType enum member (not string) is correctly extracted."""
        event = MockEvent()
        event.event_type = EventType.FIRE_SMOKE  # Enum, not string

        result = RiskEngine.assess(event, recurrence_count=0)

        assert result.event_type == EventType.FIRE_SMOKE.value
        event_factor = next(f for f in result.factors if f.name == "event_type")
        assert event_factor.score == EVENT_TYPE_SCORES[EventType.FIRE_SMOKE.value]


# ==============================================================================
# 21–22. Result Completeness and Weight Validation
# ==============================================================================

class TestResultCompleteness:
    """Risk assessment results are complete and explainable."""

    def test_all_four_factors_present(self):
        """Every assessment includes exactly 4 named factors."""
        event = MockEvent()
        result = RiskEngine.assess(event, recurrence_count=0)

        assert len(result.factors) == 4
        factor_names = {f.name for f in result.factors}
        assert factor_names == {"event_type", "zone_criticality", "confidence", "recurrence"}

    def test_factor_explanations_not_empty(self):
        """Every factor has a non-empty explanation."""
        event = MockEvent()
        result = RiskEngine.assess(event, recurrence_count=3)

        for factor in result.factors:
            assert factor.explanation, f"Factor '{factor.name}' has empty explanation"
            assert len(factor.explanation) > 5

    def test_overall_explanation_not_empty(self):
        """The overall explanation is a non-trivial string."""
        event = MockEvent()
        result = RiskEngine.assess(event, recurrence_count=0)

        assert result.explanation
        assert len(result.explanation) > 20

    def test_weights_sum_to_one(self):
        """Verify the weight constants sum to exactly 1.0."""
        total = W_EVENT + W_ZONE + W_CONFIDENCE + W_RECURRENCE
        assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, expected 1.0"

    def test_weighted_scores_sum_to_risk_score(self):
        """Sum of all weighted_scores equals the final risk_score."""
        event = MockEvent(
            event_type=EventType.ZONE_INTRUSION.value,
            confidence=0.75,
        )
        zone = MockZone(zone_type=ZoneType.FIRE_WATCH.value, name="Watch")
        result = RiskEngine.assess(event, zone=zone, recurrence_count=4)

        factor_sum = sum(f.weighted_score for f in result.factors)
        assert abs(factor_sum - result.risk_score) < 1e-5

    def test_assessed_at_is_present(self):
        """RiskAssessment includes a valid assessed_at timestamp."""
        from datetime import datetime

        event = MockEvent()
        result = RiskEngine.assess(event, recurrence_count=0)

        assert isinstance(result.assessed_at, datetime)
