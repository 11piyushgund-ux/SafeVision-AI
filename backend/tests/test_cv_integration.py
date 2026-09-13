"""
SafeVision AI — CV Integration Unit Tests (Phase 6)

All tests use mocked YOLO models to avoid requiring GPU/model weights in CI.

Coverage:
1. Detection adapter: Ultralytics Results → DetectionPayload contract
2. Track ID preservation through adapter
3. Bbox coordinate preservation (original frame, not 640x640)
4. Event engine: N-frame persistence accumulation
5. Event engine: ACTIVE promotion and DB persistence
6. Event engine: duplicate suppression while ACTIVE
7. Event engine: COOLDOWN entry when violation clears
8. Event engine: violation returns during cooldown → no new event
9. Event engine: cooldown expires → new event allowed
10. Event engine: ACCUMULATING resets when condition clears early
11. Full pipeline mock: frame → inference → adapter → rules → event → DB
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.event import EventType
from app.models.safety_rule import RuleSeverity, RuleStatus, RuleType
from app.models.zone import ZoneType
from app.schemas.detection import DetectionItem, DetectionPayload
from app.services.detection_adapter import DetectionAdapter
from app.services.event_engine import EventEngine, ViolationState

# ==============================================================================
# Mock Helpers
# ==============================================================================

class MockBoxes:
    """Mock Ultralytics boxes with xyxy, conf, cls, id tensors."""
    def __init__(self, detections: list[dict]):
        self._detections = detections

    @property
    def xyxy(self):
        return [[d["bbox"][0], d["bbox"][1], d["bbox"][2], d["bbox"][3]] for d in self._detections]

    @property
    def conf(self):
        return [d["confidence"] for d in self._detections]

    @property
    def cls(self):
        return [d["cls_idx"] for d in self._detections]

    @property
    def id(self):
        ids = [d.get("track_id") for d in self._detections]
        if all(tid is None for tid in ids):
            return None
        return ids

    def __len__(self):
        return len(self._detections)


class MockResult:
    """Mock Ultralytics Result object."""
    def __init__(self, boxes: MockBoxes):
        self.boxes = boxes


class MockRule:
    def __init__(self, rule_type=RuleType.PPE_VIOLATION, parameters=None,
                 status=RuleStatus.ACTIVE, severity=RuleSeverity.HIGH,
                 id="rule-001", name="Test Rule", zone_id=None):
        self.id = id
        self.name = name
        self.rule_type = rule_type
        self.severity = severity
        self.status = status
        self.parameters = parameters or {}
        self.zone_id = zone_id


class MockZone:
    def __init__(self, id="zone-001", name="Test Zone",
                 zone_type=ZoneType.PPE_REQUIRED,
                 polygon=None, required_ppe=None):
        self.id = id
        self.name = name
        self.zone_type = zone_type
        self.polygon = polygon or []
        self.required_ppe = required_ppe or []


class MockDBSession:
    """Mock SQLAlchemy session for testing DB persistence."""
    def __init__(self):
        self.added: list = []
        self.committed = False

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed = True

    def rollback(self):
        pass


PPE_MODEL_NAMES = {
    0: "gloves", 1: "goggles", 2: "helmet",
    3: "person", 4: "safety_shoes", 5: "safety_vest",
}


# ==============================================================================
# 1. Detection Adapter Tests
# ==============================================================================

class TestDetectionAdapter:
    """Adapter converts Ultralytics Results to Phase 5 DetectionPayload."""

    def test_adapt_basic_detections(self):
        """Adapter produces correct DetectionPayload from mock results."""
        boxes = MockBoxes([
            {"bbox": [100.5, 200.3, 280.7, 450.1], "confidence": 0.97, "cls_idx": 3, "track_id": 17},
            {"bbox": [110.2, 205.0, 170.4, 250.8], "confidence": 0.93, "cls_idx": 2, "track_id": 17},
        ])
        result = MockResult(boxes)

        payload = DetectionAdapter.adapt(
            results=[result],
            camera_id="cam-001",
            model_names=PPE_MODEL_NAMES,
        )

        assert isinstance(payload, DetectionPayload)
        assert payload.camera_id == "cam-001"
        assert len(payload.detections) == 2

    def test_bbox_preserved_exactly(self):
        """Bbox coordinates are preserved as-is (original frame, not 640x640)."""
        original_bbox = [123.456, 789.012, 345.678, 901.234]
        boxes = MockBoxes([
            {"bbox": original_bbox, "confidence": 0.95, "cls_idx": 3, "track_id": 1},
        ])
        result = MockResult(boxes)

        payload = DetectionAdapter.adapt(
            results=[result], camera_id="cam-01", model_names=PPE_MODEL_NAMES,
        )

        assert payload.detections[0].bbox == pytest.approx(original_bbox)

    def test_track_id_preserved(self):
        """Track IDs from BoT-SORT are preserved through adapter."""
        boxes = MockBoxes([
            {"bbox": [10, 10, 50, 50], "confidence": 0.9, "cls_idx": 3, "track_id": 42},
            {"bbox": [60, 60, 100, 100], "confidence": 0.85, "cls_idx": 2, "track_id": 42},
        ])
        result = MockResult(boxes)

        payload = DetectionAdapter.adapt(
            results=[result], camera_id="cam-01", model_names=PPE_MODEL_NAMES,
        )

        assert payload.detections[0].track_id == 42
        assert payload.detections[1].track_id == 42

    def test_class_name_from_model_names(self):
        """Class names are mapped using model.names, not hardcoded."""
        boxes = MockBoxes([
            {"bbox": [10, 10, 50, 50], "confidence": 0.9, "cls_idx": 0, "track_id": 1},
            {"bbox": [60, 60, 100, 100], "confidence": 0.85, "cls_idx": 5, "track_id": 1},
        ])
        result = MockResult(boxes)

        payload = DetectionAdapter.adapt(
            results=[result], camera_id="cam-01", model_names=PPE_MODEL_NAMES,
        )

        assert payload.detections[0].class_name == "gloves"
        assert payload.detections[1].class_name == "safety_vest"

    def test_untracked_detections_have_none_track_id(self):
        """Detections without tracker produce track_id=None."""
        boxes = MockBoxes([
            {"bbox": [10, 10, 50, 50], "confidence": 0.9, "cls_idx": 3, "track_id": None},
        ])
        result = MockResult(boxes)

        payload = DetectionAdapter.adapt(
            results=[result], camera_id="cam-01", model_names=PPE_MODEL_NAMES,
        )

        assert payload.detections[0].track_id is None

    def test_empty_results(self):
        """Empty results produce empty payload."""
        boxes = MockBoxes([])
        result = MockResult(boxes)

        payload = DetectionAdapter.adapt(
            results=[result], camera_id="cam-01", model_names=PPE_MODEL_NAMES,
        )

        assert len(payload.detections) == 0

    def test_merge_payloads(self):
        """Merging PPE + fire/smoke payloads combines all detections."""
        ppe_payload = DetectionPayload(
            camera_id="cam-01",
            detections=[
                DetectionItem(class_name="person", confidence=0.95, bbox=[10, 10, 50, 50], track_id=1),
            ],
        )
        fire_payload = DetectionPayload(
            camera_id="cam-01",
            detections=[
                DetectionItem(class_name="fire", confidence=0.88, bbox=[200, 200, 300, 300], track_id=None),
            ],
        )

        merged = DetectionAdapter.merge_payloads(ppe_payload, fire_payload)
        assert len(merged.detections) == 2
        assert merged.camera_id == "cam-01"


# ==============================================================================
# 2. Event Engine — Temporal Persistence Tests
# ==============================================================================

class TestEventEngineAccumulation:
    """N-frame persistence and promotion logic."""

    def _make_violation_result(self, camera_id="cam-01", track_id=1,
                                rule_type="ppe_violation"):
        """Helper to create a RuleEvaluationResult with one violation."""
        from app.schemas.detection import RuleEvaluationResult, RuleViolation
        return RuleEvaluationResult(
            camera_id=camera_id,
            violations=[
                RuleViolation(
                    rule_type=rule_type,
                    severity="high",
                    camera_id=camera_id,
                    track_id=track_id,
                    missing_ppe=["helmet"],
                    message="Missing helmet",
                    details={"person_confidence": 0.95},
                ),
            ],
            total_persons_detected=1,
        )

    def _make_empty_result(self, camera_id="cam-01"):
        """Helper to create a RuleEvaluationResult with no violations."""
        from app.schemas.detection import RuleEvaluationResult
        return RuleEvaluationResult(camera_id=camera_id)

    def test_accumulation_increments(self):
        """Frame counter increments for each frame with the same violation."""
        engine = EventEngine()
        db = MockDBSession()
        rule = MockRule(parameters={"min_persistence_frames": 5})
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)

        # Frame 1
        engine.process_frame(
            self._make_violation_result(), "org-1", db, [rule], now=now,
        )
        # Frame 2
        engine.process_frame(
            self._make_violation_result(), "org-1", db, [rule],
            now=now + timedelta(seconds=1),
        )

        # Should be accumulating, not yet promoted
        key = ("cam-01", 1, "ppe_violation")
        assert key in engine._state
        assert engine._state[key].state == ViolationState.ACCUMULATING
        assert engine._state[key].frame_count == 2
        assert db.committed is False  # No event yet

    def test_promotion_at_min_persistence(self):
        """Event created exactly when frame_count reaches min_persistence_frames."""
        engine = EventEngine()
        db = MockDBSession()
        rule = MockRule(parameters={"min_persistence_frames": 3})
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)

        for i in range(3):
            events = engine.process_frame(
                self._make_violation_result(), "org-1", db, [rule],
                now=now + timedelta(seconds=i),
            )

        # Should be promoted on frame 3
        assert len(events) == 1
        key = ("cam-01", 1, "ppe_violation")
        assert engine._state[key].state == ViolationState.ACTIVE
        assert engine._state[key].event_id is not None
        assert db.committed is True

    def test_single_event_created(self):
        """Exactly one DB event is created per promotion."""
        engine = EventEngine()
        db = MockDBSession()
        rule = MockRule(parameters={"min_persistence_frames": 2})
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)

        all_events = []
        for i in range(5):  # 5 frames
            events = engine.process_frame(
                self._make_violation_result(), "org-1", db, [rule],
                now=now + timedelta(seconds=i),
            )
            all_events.extend(events)

        # Only 1 event created (at frame 2), frames 3-5 suppressed
        assert len(all_events) == 1
        assert len(db.added) == 1


# ==============================================================================
# 3. Event Engine — Duplicate Suppression Tests
# ==============================================================================

class TestEventEngineSuppression:
    """Duplicate event suppression while violation is ACTIVE."""

    def _make_violation_result(self, camera_id="cam-01", track_id=1):
        from app.schemas.detection import RuleEvaluationResult, RuleViolation
        return RuleEvaluationResult(
            camera_id=camera_id,
            violations=[
                RuleViolation(
                    rule_type="ppe_violation", severity="high",
                    camera_id=camera_id, track_id=track_id,
                    message="Missing PPE",
                    details={"person_confidence": 0.95},
                ),
            ],
            total_persons_detected=1,
        )

    def test_suppression_after_promotion(self):
        """No new events after promotion — all subsequent frames suppressed."""
        engine = EventEngine()
        db = MockDBSession()
        rule = MockRule(parameters={"min_persistence_frames": 2})
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)

        total_events = []
        for i in range(10):
            events = engine.process_frame(
                self._make_violation_result(), "org-1", db, [rule],
                now=now + timedelta(seconds=i),
            )
            total_events.extend(events)

        # Only 1 event across 10 frames
        assert len(total_events) == 1

        key = ("cam-01", 1, "ppe_violation")
        assert engine._state[key].state == ViolationState.ACTIVE
        assert engine._state[key].frame_count == 10


# ==============================================================================
# 4. Event Engine — Cooldown Tests
# ==============================================================================

class TestEventEngineCooldown:
    """Full cooldown lifecycle: ACTIVE → COOLDOWN → CLEARED."""

    def _make_violation_result(self, camera_id="cam-01", track_id=1):
        from app.schemas.detection import RuleEvaluationResult, RuleViolation
        return RuleEvaluationResult(
            camera_id=camera_id,
            violations=[
                RuleViolation(
                    rule_type="ppe_violation", severity="high",
                    camera_id=camera_id, track_id=track_id,
                    message="Missing PPE",
                    details={"person_confidence": 0.95},
                ),
            ],
            total_persons_detected=1,
        )

    def _make_empty_result(self, camera_id="cam-01"):
        from app.schemas.detection import RuleEvaluationResult
        return RuleEvaluationResult(camera_id=camera_id)

    def test_active_to_cooldown_on_clear(self):
        """Violation clears while ACTIVE → enters COOLDOWN."""
        engine = EventEngine()
        db = MockDBSession()
        rule = MockRule(parameters={"min_persistence_frames": 2, "cooldown_seconds": 60})
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)

        # Promote to ACTIVE (2 frames)
        for i in range(2):
            engine.process_frame(
                self._make_violation_result(), "org-1", db, [rule],
                now=now + timedelta(seconds=i),
            )

        key = ("cam-01", 1, "ppe_violation")
        assert engine._state[key].state == ViolationState.ACTIVE

        # Violation clears
        engine.process_frame(
            self._make_empty_result(), "org-1", db, [rule],
            now=now + timedelta(seconds=5),
        )

        assert engine._state[key].state == ViolationState.COOLDOWN
        assert engine._state[key].cooldown_until is not None

    def test_violation_returns_during_cooldown_no_new_event(self):
        """Violation returns during cooldown → back to ACTIVE, no new event."""
        engine = EventEngine()
        db = MockDBSession()
        rule = MockRule(parameters={"min_persistence_frames": 2, "cooldown_seconds": 60})
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)

        # Promote to ACTIVE
        for i in range(2):
            engine.process_frame(
                self._make_violation_result(), "org-1", db, [rule],
                now=now + timedelta(seconds=i),
            )

        original_event_id = engine._state[("cam-01", 1, "ppe_violation")].event_id

        # Clear → COOLDOWN
        engine.process_frame(
            self._make_empty_result(), "org-1", db, [rule],
            now=now + timedelta(seconds=5),
        )

        # Violation returns during cooldown (before 60s)
        events = engine.process_frame(
            self._make_violation_result(), "org-1", db, [rule],
            now=now + timedelta(seconds=10),
        )

        # No new event — same event_id, back to ACTIVE
        assert len(events) == 0
        key = ("cam-01", 1, "ppe_violation")
        assert engine._state[key].state == ViolationState.ACTIVE
        assert engine._state[key].event_id == original_event_id

    def test_cooldown_expires_new_event_allowed(self):
        """After cooldown expires, a new violation creates a new event."""
        engine = EventEngine()
        db = MockDBSession()
        rule = MockRule(parameters={"min_persistence_frames": 2, "cooldown_seconds": 30})
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)

        # Promote to ACTIVE
        for i in range(2):
            engine.process_frame(
                self._make_violation_result(), "org-1", db, [rule],
                now=now + timedelta(seconds=i),
            )

        original_event_id = engine._state[("cam-01", 1, "ppe_violation")].event_id

        # Clear → COOLDOWN
        engine.process_frame(
            self._make_empty_result(), "org-1", db, [rule],
            now=now + timedelta(seconds=5),
        )

        # Wait for cooldown to expire (>30s)
        engine.process_frame(
            self._make_empty_result(), "org-1", db, [rule],
            now=now + timedelta(seconds=40),
        )

        # State should be cleared
        key = ("cam-01", 1, "ppe_violation")
        assert key not in engine._state

        # New violation → fresh accumulation → new event
        all_events = []
        for i in range(2):
            events = engine.process_frame(
                self._make_violation_result(), "org-1", db, [rule],
                now=now + timedelta(seconds=50 + i),
            )
            all_events.extend(events)

        assert len(all_events) == 1
        assert all_events[0].id != original_event_id

    def test_accumulating_resets_on_early_clear(self):
        """Violation that clears before reaching min_persistence resets counter."""
        engine = EventEngine()
        db = MockDBSession()
        rule = MockRule(parameters={"min_persistence_frames": 5})
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)

        # 2 frames of violation
        for i in range(2):
            engine.process_frame(
                self._make_violation_result(), "org-1", db, [rule],
                now=now + timedelta(seconds=i),
            )

        key = ("cam-01", 1, "ppe_violation")
        assert key in engine._state
        assert engine._state[key].frame_count == 2

        # Violation clears before reaching 5
        engine.process_frame(
            self._make_empty_result(), "org-1", db, [rule],
            now=now + timedelta(seconds=5),
        )

        # State should be deleted (ACCUMULATING clears immediately)
        assert key not in engine._state
        assert len(db.added) == 0  # No event created


# ==============================================================================
# 5. Event Engine — DB Persistence Tests
# ==============================================================================

class TestEventEngineDBPersistence:
    """Verify correct Safety Event row creation."""

    def test_event_has_correct_fields(self):
        """Created Event has correct event_type, org_id, detection_data."""
        from app.schemas.detection import RuleEvaluationResult, RuleViolation

        engine = EventEngine()
        db = MockDBSession()
        rule = MockRule(parameters={"min_persistence_frames": 1})
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        result = RuleEvaluationResult(
            camera_id="cam-01",
            violations=[
                RuleViolation(
                    rule_id="rule-ppe-01",
                    rule_name="Helmet Required",
                    rule_type="ppe_violation",
                    severity="high",
                    camera_id="cam-01",
                    track_id=17,
                    person_bbox=[100.0, 200.0, 300.0, 400.0],
                    person_centroid=(200.0, 300.0),
                    missing_ppe=["helmet"],
                    detected_ppe=["safety_vest"],
                    message="Track 17 missing helmet",
                    details={"person_confidence": 0.95},
                    zone_id="zone-01",
                ),
            ],
            total_persons_detected=1,
        )

        events = engine.process_frame(result, "org-abc", db, [rule], now=now)

        assert len(events) == 1
        event = events[0]
        assert event.camera_id == "cam-01"
        assert event.org_id == "org-abc"
        assert event.event_type == EventType.PPE_DETECTION
        assert event.timestamp == now
        assert event.confidence == 0.95

        # Verify detection_data JSONB
        data = event.detection_data
        assert data["rule_id"] == "rule-ppe-01"
        assert data["track_id"] == 17
        assert data["missing_ppe"] == ["helmet"]
        assert data["detected_ppe"] == ["safety_vest"]
        assert data["person_centroid"] == [200.0, 300.0]
        assert data["zone_id"] == "zone-01"

    def test_zone_intrusion_event_type(self):
        """Exclusion zone violations map to ZONE_INTRUSION event type."""
        from app.schemas.detection import RuleEvaluationResult, RuleViolation

        engine = EventEngine()
        db = MockDBSession()
        rule = MockRule(
            rule_type=RuleType.EXCLUSION_ZONE,
            parameters={"min_persistence_frames": 1},
        )

        result = RuleEvaluationResult(
            camera_id="cam-01",
            violations=[
                RuleViolation(
                    rule_type="exclusion_zone",
                    severity="critical",
                    camera_id="cam-01",
                    track_id=5,
                    message="Person in restricted zone",
                    details={"person_confidence": 0.92},
                ),
            ],
            total_persons_detected=1,
        )

        events = engine.process_frame(result, "org-1", db, [rule])
        assert events[0].event_type == EventType.ZONE_INTRUSION


# ==============================================================================
# 6. State Management Tests
# ==============================================================================

class TestEventEngineStateManagement:
    """State summary and cleanup."""

    def test_state_summary(self):
        """get_state_summary returns correct counts."""
        engine = EventEngine()
        db = MockDBSession()
        rule = MockRule(parameters={"min_persistence_frames": 3, "cooldown_seconds": 60})
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)

        from app.schemas.detection import RuleEvaluationResult, RuleViolation

        # Create 2 violations for different tracks
        result = RuleEvaluationResult(
            camera_id="cam-01",
            violations=[
                RuleViolation(rule_type="ppe_violation", severity="high",
                              camera_id="cam-01", track_id=1,
                              message="v1", details={"person_confidence": 0.9}),
                RuleViolation(rule_type="ppe_violation", severity="high",
                              camera_id="cam-01", track_id=2,
                              message="v2", details={"person_confidence": 0.9}),
            ],
            total_persons_detected=2,
        )

        engine.process_frame(result, "org-1", db, [rule], now=now)

        summary = engine.get_state_summary()
        assert summary["accumulating"] == 2

    def test_clear_camera_state(self):
        """clear_camera_state removes all state for a specific camera."""
        engine = EventEngine()
        db = MockDBSession()
        rule = MockRule(parameters={"min_persistence_frames": 5})
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)

        from app.schemas.detection import RuleEvaluationResult, RuleViolation

        for cam in ["cam-01", "cam-02"]:
            result = RuleEvaluationResult(
                camera_id=cam,
                violations=[
                    RuleViolation(rule_type="ppe_violation", severity="high",
                                  camera_id=cam, track_id=1,
                                  message="v", details={"person_confidence": 0.9}),
                ],
                total_persons_detected=1,
            )
            engine.process_frame(result, "org-1", db, [rule], now=now)

        assert engine.active_violations == 2

        cleared = engine.clear_camera_state("cam-01")
        assert cleared == 1
        assert engine.active_violations == 1
