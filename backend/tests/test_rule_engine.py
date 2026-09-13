"""
SafeVision AI — Safety Rule Engine Unit Tests (Phase 5, Opus Review)

Comprehensive coverage:
1. Geometry utilities (centroid, point-in-polygon, bbox containment)
2. PPE association — track_id primary + spatial bbox fallback
3. PPE violation detection (missing items per track_id, all 5 Phase 1 classes)
4. Restricted-zone incursion (convex, concave, outside, boundary, degenerate)
5. Compliant scenario (all requirements met, zero violations)
6. Configurable thresholds from safety_rules.parameters (zero hardcoding)
7. Rule PPE override → zone fallback chain
8. Multi-person frames — no PPE cross-leak
9. Malformed / edge case inputs
10. Inactive rules skipped
"""

import pytest

from app.models.safety_rule import RuleSeverity, RuleStatus, RuleType
from app.models.zone import ZoneType
from app.schemas.detection import DetectionItem, DetectionPayload
from app.services.geometry import bbox_contains, calculate_centroid, point_in_polygon
from app.services.rule_engine import SafetyRuleEngine

# ==============================================================================
# Helper Mock Objects for Rules & Zones
# ==============================================================================

class MockRule:
    def __init__(
        self,
        id: str = "rule-001",
        name: str = "Test Rule",
        rule_type: RuleType = RuleType.PPE_VIOLATION,
        severity: RuleSeverity = RuleSeverity.HIGH,
        status: RuleStatus = RuleStatus.ACTIVE,
        parameters: dict | None = None,
        zone_id: str | None = None,
    ):
        self.id = id
        self.name = name
        self.rule_type = rule_type
        self.severity = severity
        self.status = status
        self.parameters = parameters or {}
        self.zone_id = zone_id


class MockZone:
    def __init__(
        self,
        id: str = "zone-001",
        name: str = "Test Zone",
        zone_type: ZoneType = ZoneType.PPE_REQUIRED,
        polygon: list[list[float]] | None = None,
        required_ppe: list[str] | None = None,
    ):
        self.id = id
        self.name = name
        self.zone_type = zone_type
        self.polygon = polygon or []
        self.required_ppe = required_ppe or []


# ==============================================================================
# 1. Geometry Utility Tests
# ==============================================================================

class TestGeometryUtilities:
    """Tests for core spatial algorithms."""

    def test_calculate_centroid_standard(self):
        """Bounding box [x1, y1, x2, y2] centroid calculation."""
        cx, cy = calculate_centroid([100.0, 200.0, 300.0, 400.0])
        assert cx == 200.0
        assert cy == 300.0

    def test_calculate_centroid_normalized(self):
        """Normalized coordinate bounding box [0.1, 0.2, 0.5, 0.8]."""
        cx, cy = calculate_centroid([0.1, 0.2, 0.5, 0.8])
        assert pytest.approx(cx) == 0.3
        assert pytest.approx(cy) == 0.5

    def test_calculate_centroid_invalid(self):
        """Invalid bbox with fewer than 4 coordinates raises ValueError."""
        with pytest.raises(ValueError, match="Invalid bbox format"):
            calculate_centroid([10.0, 20.0])

    def test_point_in_polygon_square_inside(self):
        polygon = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
        assert point_in_polygon((5.0, 5.0), polygon) is True

    def test_point_in_polygon_square_outside(self):
        polygon = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
        assert point_in_polygon((15.0, 5.0), polygon) is False
        assert point_in_polygon((-2.0, 5.0), polygon) is False

    def test_point_in_polygon_concave_l_shape(self):
        """L-shaped concave polygon: 10x10 square with top-right 5x5 cut out."""
        l_poly = [
            [0.0, 0.0], [10.0, 0.0], [10.0, 5.0],
            [5.0, 5.0], [5.0, 10.0], [0.0, 10.0],
        ]
        assert point_in_polygon((7.0, 2.0), l_poly) is True   # Bottom arm
        assert point_in_polygon((2.0, 7.0), l_poly) is True   # Left arm
        assert point_in_polygon((7.0, 7.0), l_poly) is False  # Cut-out corner

    def test_point_in_polygon_degenerate(self):
        """Polygon with fewer than 3 vertices returns False."""
        assert point_in_polygon((1.0, 1.0), [[0.0, 0.0], [1.0, 1.0]]) is False
        assert point_in_polygon((1.0, 1.0), []) is False

    def test_point_in_polygon_triangle(self):
        """Triangle polygon: minimal valid polygon."""
        tri = [[0.0, 0.0], [10.0, 0.0], [5.0, 10.0]]
        assert point_in_polygon((5.0, 3.0), tri) is True
        assert point_in_polygon((0.0, 10.0), tri) is False

    def test_bbox_contains_inside(self):
        """PPE centroid inside person bbox → True."""
        person_bbox = [100.0, 100.0, 300.0, 400.0]
        ppe_bbox = [150.0, 110.0, 250.0, 180.0]  # Centroid (200, 145) inside
        assert bbox_contains(person_bbox, ppe_bbox) is True

    def test_bbox_contains_outside(self):
        """PPE centroid outside person bbox → False."""
        person_bbox = [100.0, 100.0, 200.0, 200.0]
        ppe_bbox = [300.0, 300.0, 400.0, 400.0]  # Centroid (350, 350) outside
        assert bbox_contains(person_bbox, ppe_bbox) is False

    def test_bbox_contains_malformed(self):
        """Malformed bboxes (None, too short) → False, no crash."""
        assert bbox_contains(None, [1, 2, 3, 4]) is False
        assert bbox_contains([1, 2], [1, 2, 3, 4]) is False
        assert bbox_contains([1, 2, 3, 4], None) is False
        assert bbox_contains([1, 2, 3, 4], [1]) is False


# ==============================================================================
# 2. PPE Association Tests — CRITICAL
# ==============================================================================

class TestPPEAssociation:
    """Verify PPE items are associated with the correct person only."""

    def test_track_id_association_no_cross_leak(self):
        """
        Two people with different PPE: prove PPE does NOT leak between them.
        Worker A (track 1): has helmet only → missing safety_vest
        Worker B (track 2): has safety_vest only → missing helmet
        """
        payload = DetectionPayload(
            camera_id="cam-01",
            detections=[
                DetectionItem(class_name="person", confidence=0.95, bbox=[100, 100, 200, 400], track_id=1),
                DetectionItem(class_name="helmet", confidence=0.90, bbox=[120, 100, 180, 160], track_id=1),
                DetectionItem(class_name="person", confidence=0.93, bbox=[400, 100, 500, 400], track_id=2),
                DetectionItem(class_name="safety_vest", confidence=0.88, bbox=[410, 200, 490, 350], track_id=2),
            ],
        )

        rule = MockRule(
            rule_type=RuleType.PPE_VIOLATION,
            parameters={"required_ppe": ["helmet", "safety_vest"]},
        )

        result = SafetyRuleEngine.evaluate_frame(payload, rules=[rule])
        assert len(result.violations) == 2

        v_by_track = {v.track_id: v for v in result.violations}
        # Worker A has helmet, missing vest
        assert v_by_track[1].detected_ppe == ["helmet"]
        assert v_by_track[1].missing_ppe == ["safety_vest"]
        # Worker B has vest, missing helmet
        assert v_by_track[2].detected_ppe == ["safety_vest"]
        assert v_by_track[2].missing_ppe == ["helmet"]

    def test_spatial_fallback_untracked_ppe(self):
        """
        PPE detection without track_id is assigned to person whose bbox
        contains the PPE centroid (spatial fallback).
        """
        payload = DetectionPayload(
            camera_id="cam-01",
            detections=[
                # Tracked person
                DetectionItem(class_name="person", confidence=0.95, bbox=[100, 100, 300, 400], track_id=10),
                # Untracked helmet — centroid (175, 120) is inside person bbox
                DetectionItem(class_name="helmet", confidence=0.92, bbox=[150, 100, 200, 140], track_id=None),
            ],
        )

        rule = MockRule(
            rule_type=RuleType.PPE_VIOLATION,
            parameters={"required_ppe": ["helmet", "safety_vest"]},
        )

        result = SafetyRuleEngine.evaluate_frame(payload, rules=[rule])
        assert len(result.violations) == 1
        # Helmet was associated spatially — only vest is missing
        assert result.violations[0].missing_ppe == ["safety_vest"]
        assert result.violations[0].detected_ppe == ["helmet"]

    def test_spatial_fallback_ppe_outside_all_persons(self):
        """
        Untracked PPE whose centroid falls outside all person bboxes
        is discarded — never creates phantom associations.
        """
        payload = DetectionPayload(
            camera_id="cam-01",
            detections=[
                DetectionItem(class_name="person", confidence=0.95, bbox=[100, 100, 200, 200], track_id=5),
                # PPE centroid (450, 450) is outside person bbox
                DetectionItem(class_name="helmet", confidence=0.92, bbox=[400, 400, 500, 500], track_id=None),
            ],
        )

        rule = MockRule(
            rule_type=RuleType.PPE_VIOLATION,
            parameters={"required_ppe": ["helmet"]},
        )

        result = SafetyRuleEngine.evaluate_frame(payload, rules=[rule])
        assert len(result.violations) == 1
        assert result.violations[0].missing_ppe == ["helmet"]

    def test_untracked_person_ignored(self):
        """Person detection without track_id is ignored — no violation generated."""
        payload = DetectionPayload(
            camera_id="cam-01",
            detections=[
                DetectionItem(class_name="person", confidence=0.95, bbox=[100, 100, 200, 200], track_id=None),
            ],
        )
        rule = MockRule(
            rule_type=RuleType.PPE_VIOLATION,
            parameters={"required_ppe": ["helmet"]},
        )

        result = SafetyRuleEngine.evaluate_frame(payload, rules=[rule])
        assert len(result.violations) == 0
        assert result.total_persons_detected == 0


# ==============================================================================
# 3. PPE Violation Tests — All Phase 1 Class Names
# ==============================================================================

class TestPPEViolations:
    """PPE violation detection with exact Phase 1 CV model class names."""

    def test_ppe_violation_missing_items(self):
        """
        Track 17 has person + helmet, but missing safety_vest and goggles.
        """
        payload = DetectionPayload(
            camera_id="cam-south-01",
            detections=[
                DetectionItem(class_name="person", confidence=0.95, bbox=[100, 100, 200, 300], track_id=17),
                DetectionItem(class_name="helmet", confidence=0.92, bbox=[120, 100, 180, 150], track_id=17),
            ],
        )
        rule = MockRule(
            id="rule-ppe-01",
            name="Mandatory PPE Construction",
            rule_type=RuleType.PPE_VIOLATION,
            severity=RuleSeverity.HIGH,
            parameters={
                "confidence_threshold": 0.60,
                "required_ppe": ["helmet", "safety_vest", "goggles"],
            },
        )

        result = SafetyRuleEngine.evaluate_frame(payload, rules=[rule])
        assert len(result.violations) == 1
        v = result.violations[0]
        assert v.rule_type == RuleType.PPE_VIOLATION.value
        assert v.track_id == 17
        assert v.severity == RuleSeverity.HIGH.value
        assert v.missing_ppe == ["goggles", "safety_vest"]
        assert v.detected_ppe == ["helmet"]
        assert v.person_centroid == (150.0, 200.0)
        assert 17 not in result.compliant_track_ids

    def test_all_five_phase1_ppe_classes(self):
        """
        Validate all 5 Phase 1 PPE classes: helmet, gloves, goggles,
        safety_shoes, safety_vest. Worker has gloves + goggles only.
        """
        all_five = ["helmet", "gloves", "goggles", "safety_shoes", "safety_vest"]

        payload = DetectionPayload(
            camera_id="cam-full-ppe",
            detections=[
                DetectionItem(class_name="person", confidence=0.97, bbox=[50, 50, 200, 400], track_id=7),
                DetectionItem(class_name="gloves", confidence=0.89, track_id=7),
                DetectionItem(class_name="goggles", confidence=0.91, track_id=7),
            ],
        )

        rule = MockRule(
            rule_type=RuleType.PPE_VIOLATION,
            parameters={"required_ppe": all_five, "confidence_threshold": 0.50},
        )

        result = SafetyRuleEngine.evaluate_frame(payload, rules=[rule])
        assert len(result.violations) == 1
        assert result.violations[0].missing_ppe == ["helmet", "safety_shoes", "safety_vest"]
        assert result.violations[0].detected_ppe == ["gloves", "goggles"]

    def test_ppe_rule_overrides_zone_required_ppe(self):
        """Rule parameters required_ppe overrides zone.required_ppe."""
        payload = DetectionPayload(
            camera_id="cam-01",
            detections=[
                DetectionItem(class_name="person", confidence=0.90, bbox=[50, 50, 150, 250], track_id="A"),
            ],
        )
        zone = MockZone(
            id="zone-1",
            required_ppe=["helmet", "safety_vest", "goggles"],  # Zone says 3 items
        )
        rule = MockRule(
            rule_type=RuleType.PPE_VIOLATION,
            parameters={"required_ppe": ["helmet"]},  # Rule overrides to 1 item
            zone_id=zone.id,
        )

        result = SafetyRuleEngine.evaluate_frame(payload, rules=[rule], zone=zone)
        assert len(result.violations) == 1
        # Only helmet is required (rule overrides zone), not vest/goggles
        assert result.violations[0].missing_ppe == ["helmet"]

    def test_ppe_zone_fallback_when_rule_has_no_required_ppe(self):
        """Rule without required_ppe falls back to zone.required_ppe."""
        payload = DetectionPayload(
            camera_id="cam-01",
            detections=[
                DetectionItem(class_name="person", confidence=0.90, bbox=[50, 50, 150, 250], track_id="B"),
            ],
        )
        zone = MockZone(
            id="zone-heavy-machinery",
            required_ppe=["helmet", "safety_vest"],
        )
        rule = MockRule(
            rule_type=RuleType.PPE_VIOLATION,
            parameters={"confidence_threshold": 0.50},  # No required_ppe in rule
            zone_id=zone.id,
        )

        result = SafetyRuleEngine.evaluate_frame(payload, rules=[rule], zone=zone)
        assert len(result.violations) == 1
        assert result.violations[0].missing_ppe == ["helmet", "safety_vest"]
        assert result.violations[0].zone_id == "zone-heavy-machinery"

    def test_unknown_class_name_ignored(self):
        """Unknown class names (not person, not known PPE) are silently ignored."""
        payload = DetectionPayload(
            camera_id="cam-01",
            detections=[
                DetectionItem(class_name="person", confidence=0.95, bbox=[100, 100, 200, 300], track_id=1),
                DetectionItem(class_name="forklift", confidence=0.99, bbox=[300, 300, 500, 500], track_id=1),
            ],
        )
        rule = MockRule(
            rule_type=RuleType.PPE_VIOLATION,
            parameters={"required_ppe": ["helmet"]},
        )
        result = SafetyRuleEngine.evaluate_frame(payload, rules=[rule])
        assert len(result.violations) == 1
        assert result.violations[0].missing_ppe == ["helmet"]
        # "forklift" was not counted as PPE
        assert result.violations[0].detected_ppe == []


# ==============================================================================
# 4. Restricted Zone Incursion Tests
# ==============================================================================

class TestRestrictedZoneIncursion:
    """Restricted zone centroid-in-polygon checks."""

    def test_restricted_zone_incursion_detected(self):
        """Centroid (350, 400) inside polygon → violation."""
        restricted_poly = [
            [200.0, 200.0], [600.0, 200.0],
            [600.0, 600.0], [200.0, 600.0],
        ]
        payload = DetectionPayload(
            camera_id="cam-restricted-01",
            detections=[
                DetectionItem(class_name="person", confidence=0.94, bbox=[300, 300, 400, 500], track_id=42),
            ],
        )
        rule = MockRule(
            id="rule-excl-01",
            name="Danger Zone No Entry",
            rule_type=RuleType.EXCLUSION_ZONE,
            severity=RuleSeverity.CRITICAL,
            parameters={"confidence_threshold": 0.70, "polygon": restricted_poly},
        )

        result = SafetyRuleEngine.evaluate_frame(payload, rules=[rule])
        assert len(result.violations) == 1
        v = result.violations[0]
        assert v.rule_type == RuleType.EXCLUSION_ZONE.value
        assert v.track_id == 42
        assert v.severity == RuleSeverity.CRITICAL.value
        assert v.person_centroid == (350.0, 400.0)

    def test_restricted_zone_person_outside_no_violation(self):
        """Centroid (550, 550) outside polygon → no violation."""
        restricted_poly = [
            [0.0, 0.0], [100.0, 0.0], [100.0, 100.0], [0.0, 100.0],
        ]
        payload = DetectionPayload(
            camera_id="cam-restricted-01",
            detections=[
                DetectionItem(class_name="person", confidence=0.91, bbox=[500, 500, 600, 600], track_id=99),
            ],
        )
        rule = MockRule(
            rule_type=RuleType.EXCLUSION_ZONE,
            parameters={"polygon": restricted_poly},
        )
        result = SafetyRuleEngine.evaluate_frame(payload, rules=[rule])
        assert len(result.violations) == 0
        assert 99 in result.compliant_track_ids

    def test_exclusion_zone_polygon_from_zone_fallback(self):
        """Rule without polygon in parameters falls back to zone.polygon."""
        zone = MockZone(
            id="zone-hazard",
            name="Hazard Zone",
            zone_type=ZoneType.EXCLUSION,
            polygon=[[0.0, 0.0], [500.0, 0.0], [500.0, 500.0], [0.0, 500.0]],
        )
        payload = DetectionPayload(
            camera_id="cam-01",
            detections=[
                # Centroid (250, 250) inside zone polygon
                DetectionItem(class_name="person", confidence=0.93, bbox=[200, 200, 300, 300], track_id=50),
            ],
        )
        rule = MockRule(
            rule_type=RuleType.EXCLUSION_ZONE,
            # No polygon in parameters → falls back to zone.polygon
            parameters={"confidence_threshold": 0.50},
        )
        result = SafetyRuleEngine.evaluate_frame(payload, rules=[rule], zone=zone)
        assert len(result.violations) == 1
        assert result.violations[0].person_centroid == (250.0, 250.0)

    def test_degenerate_polygon_no_violation(self):
        """Polygon with <3 vertices → no violations, no crash."""
        payload = DetectionPayload(
            camera_id="cam-01",
            detections=[
                DetectionItem(class_name="person", confidence=0.95, bbox=[10, 10, 20, 20], track_id=1),
            ],
        )
        rule = MockRule(
            rule_type=RuleType.EXCLUSION_ZONE,
            parameters={"polygon": [[0.0, 0.0], [10.0, 10.0]]},  # 2 points
        )
        result = SafetyRuleEngine.evaluate_frame(payload, rules=[rule])
        assert len(result.violations) == 0

    def test_person_no_bbox_skipped(self):
        """Person detection with no bbox is silently skipped for zone check."""
        restricted_poly = [[0, 0], [100, 0], [100, 100], [0, 100]]
        payload = DetectionPayload(
            camera_id="cam-01",
            detections=[
                DetectionItem(class_name="person", confidence=0.95, bbox=None, track_id=1),
            ],
        )
        rule = MockRule(
            rule_type=RuleType.EXCLUSION_ZONE,
            parameters={"polygon": restricted_poly},
        )
        result = SafetyRuleEngine.evaluate_frame(payload, rules=[rule])
        assert len(result.violations) == 0


# ==============================================================================
# 5. Compliant Scenario
# ==============================================================================

class TestCompliantScenario:
    """All requirements met, no violation."""

    def test_fully_compliant_worker(self):
        """Track 88 has all required PPE and is outside the exclusion zone."""
        exclusion_polygon = [
            [0.0, 0.0], [200.0, 0.0], [200.0, 200.0], [0.0, 200.0],
        ]
        payload = DetectionPayload(
            camera_id="cam-warehouse-main",
            detections=[
                DetectionItem(class_name="person", confidence=0.96, bbox=[450, 450, 550, 650], track_id=88),
                DetectionItem(class_name="helmet", confidence=0.88, bbox=[470, 450, 530, 500], track_id=88),
                DetectionItem(class_name="safety_vest", confidence=0.92, bbox=[460, 500, 540, 600], track_id=88),
            ],
        )
        ppe_rule = MockRule(
            id="rule-ppe",
            rule_type=RuleType.PPE_VIOLATION,
            parameters={"required_ppe": ["helmet", "safety_vest"], "confidence_threshold": 0.65},
        )
        zone_rule = MockRule(
            id="rule-zone",
            rule_type=RuleType.EXCLUSION_ZONE,
            parameters={"polygon": exclusion_polygon},
        )

        result = SafetyRuleEngine.evaluate_frame(payload, rules=[ppe_rule, zone_rule])
        assert len(result.violations) == 0
        assert result.total_persons_detected == 1
        assert result.compliant_track_ids == [88]
        assert result.rules_evaluated_count == 2


# ==============================================================================
# 6. Configurable Thresholds
# ==============================================================================

class TestConfigurableParameters:
    """All thresholds from safety_rules.parameters — zero hardcoding."""

    def test_ppe_confidence_threshold_rejection(self):
        """PPE confidence 0.65 < rule threshold 0.80 → treated as missing."""
        payload = DetectionPayload(
            camera_id="cam-01",
            detections=[
                DetectionItem(class_name="person", confidence=0.95, bbox=[100, 100, 200, 300], track_id=1),
                DetectionItem(class_name="helmet", confidence=0.65, bbox=[120, 100, 180, 150], track_id=1),
            ],
        )
        strict_rule = MockRule(
            rule_type=RuleType.PPE_VIOLATION,
            parameters={"required_ppe": ["helmet"], "confidence_threshold": 0.80},
        )
        result = SafetyRuleEngine.evaluate_frame(payload, rules=[strict_rule])
        assert len(result.violations) == 1
        assert "helmet" in result.violations[0].missing_ppe

    def test_ppe_confidence_threshold_acceptance(self):
        """PPE confidence 0.65 >= rule threshold 0.50 → accepted, no violation."""
        payload = DetectionPayload(
            camera_id="cam-01",
            detections=[
                DetectionItem(class_name="person", confidence=0.95, bbox=[100, 100, 200, 300], track_id=1),
                DetectionItem(class_name="helmet", confidence=0.65, bbox=[120, 100, 180, 150], track_id=1),
            ],
        )
        lenient_rule = MockRule(
            rule_type=RuleType.PPE_VIOLATION,
            parameters={"required_ppe": ["helmet"], "confidence_threshold": 0.50},
        )
        result = SafetyRuleEngine.evaluate_frame(payload, rules=[lenient_rule])
        assert len(result.violations) == 0
        assert 1 in result.compliant_track_ids

    def test_custom_recommendation_template(self):
        """Custom message template from parameters is rendered properly."""
        payload = DetectionPayload(
            camera_id="cam-01",
            detections=[
                DetectionItem(class_name="person", confidence=0.95, bbox=[10, 10, 50, 100], track_id="T100"),
            ],
        )
        rule = MockRule(
            rule_type=RuleType.PPE_VIOLATION,
            parameters={
                "required_ppe": ["safety_vest"],
                "recommendation_template": "CRITICAL: Worker {track_id} missing {missing_ppe}",
            },
        )
        result = SafetyRuleEngine.evaluate_frame(payload, rules=[rule])
        assert len(result.violations) == 1
        assert result.violations[0].message == "CRITICAL: Worker T100 missing safety_vest"

    def test_person_confidence_threshold_separate(self):
        """person_confidence_threshold gates person detections independently."""
        payload = DetectionPayload(
            camera_id="cam-01",
            detections=[
                # Person confidence 0.55 — below person threshold of 0.70
                DetectionItem(class_name="person", confidence=0.55, bbox=[100, 100, 200, 300], track_id=1),
                DetectionItem(class_name="helmet", confidence=0.90, track_id=1),
            ],
        )
        rule = MockRule(
            rule_type=RuleType.PPE_VIOLATION,
            parameters={
                "required_ppe": ["helmet"],
                "confidence_threshold": 0.50,
                "person_confidence_threshold": 0.70,
            },
        )
        result = SafetyRuleEngine.evaluate_frame(payload, rules=[rule])
        # Person rejected by person_confidence_threshold — no violation
        assert len(result.violations) == 0


# ==============================================================================
# 7. Multi-Person Mixed Frame & Edge Cases
# ==============================================================================

class TestMixedFrameEvaluation:
    """Complex multi-person frame evaluation."""

    def test_multi_person_mixed_compliance(self):
        """
        Frame with 3 workers:
        - Worker 1: Fully compliant (has helmet + vest, outside zone)
        - Worker 2: Missing vest
        - Worker 3: Inside restricted zone (has all PPE though)
        """
        restricted_polygon = [[0.0, 0.0], [300.0, 0.0], [300.0, 300.0], [0.0, 300.0]]

        payload = DetectionPayload(
            camera_id="cam-yard",
            detections=[
                DetectionItem(class_name="person", confidence=0.95, bbox=[450, 450, 550, 550], track_id=1),
                DetectionItem(class_name="helmet", confidence=0.90, track_id=1),
                DetectionItem(class_name="safety_vest", confidence=0.90, track_id=1),

                DetectionItem(class_name="person", confidence=0.92, bbox=[550, 550, 650, 650], track_id=2),
                DetectionItem(class_name="helmet", confidence=0.88, track_id=2),

                DetectionItem(class_name="person", confidence=0.96, bbox=[100, 100, 200, 200], track_id=3),
                DetectionItem(class_name="helmet", confidence=0.91, track_id=3),
                DetectionItem(class_name="safety_vest", confidence=0.91, track_id=3),
            ],
        )

        ppe_rule = MockRule(id="ppe-rule", rule_type=RuleType.PPE_VIOLATION,
                            parameters={"required_ppe": ["helmet", "safety_vest"]})
        zone_rule = MockRule(id="zone-rule", rule_type=RuleType.EXCLUSION_ZONE,
                             parameters={"polygon": restricted_polygon})

        result = SafetyRuleEngine.evaluate_frame(payload, rules=[ppe_rule, zone_rule])

        assert len(result.violations) == 2
        violated_tracks = {v.track_id for v in result.violations}
        assert violated_tracks == {2, 3}  # Worker 2: PPE, Worker 3: zone
        assert result.compliant_track_ids == [1]
        assert result.total_persons_detected == 3

    def test_empty_payload(self):
        """Empty detections → 0 violations, 0 persons."""
        payload = DetectionPayload(camera_id="cam-empty", detections=[])
        rule = MockRule(rule_type=RuleType.PPE_VIOLATION, parameters={"required_ppe": ["helmet"]})

        result = SafetyRuleEngine.evaluate_frame(payload, rules=[rule])
        assert len(result.violations) == 0
        assert result.total_persons_detected == 0

    def test_inactive_rule_skipped(self):
        """Rules with status=DISABLED are skipped entirely."""
        payload = DetectionPayload(
            camera_id="cam-01",
            detections=[
                DetectionItem(class_name="person", confidence=0.95, bbox=[100, 100, 200, 200], track_id=1),
            ],
        )
        disabled_rule = MockRule(
            status=RuleStatus.DISABLED,
            rule_type=RuleType.PPE_VIOLATION,
            parameters={"required_ppe": ["helmet"]},
        )
        result = SafetyRuleEngine.evaluate_frame(payload, rules=[disabled_rule])
        assert len(result.violations) == 0
        assert result.rules_evaluated_count == 0

    def test_no_rules_with_ppe_zone(self):
        """Zone-only evaluation when no explicit rules provided."""
        zone = MockZone(
            id="zone-ppe",
            name="PPE Zone",
            zone_type=ZoneType.PPE_REQUIRED,
            required_ppe=["helmet"],
        )
        payload = DetectionPayload(
            camera_id="cam-01",
            detections=[
                DetectionItem(class_name="person", confidence=0.95, bbox=[100, 100, 200, 200], track_id=1),
            ],
        )
        result = SafetyRuleEngine.evaluate_frame(payload, rules=[], zone=zone)
        assert len(result.violations) == 1
        assert result.violations[0].missing_ppe == ["helmet"]

    def test_case_insensitive_class_names(self):
        """PPE class names are matched case-insensitively."""
        payload = DetectionPayload(
            camera_id="cam-01",
            detections=[
                DetectionItem(class_name="Person", confidence=0.95, bbox=[100, 100, 200, 300], track_id=1),
                DetectionItem(class_name="Helmet", confidence=0.92, track_id=1),
                DetectionItem(class_name="SAFETY_VEST", confidence=0.90, track_id=1),
            ],
        )
        rule = MockRule(
            rule_type=RuleType.PPE_VIOLATION,
            parameters={"required_ppe": ["helmet", "safety_vest"]},
        )
        result = SafetyRuleEngine.evaluate_frame(payload, rules=[rule])
        assert len(result.violations) == 0
        assert 1 in result.compliant_track_ids
