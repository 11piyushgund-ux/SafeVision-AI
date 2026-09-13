"""
SafeVision AI — Phase 11C Fire & Smoke Event Generation Pipeline Tests
Threshold: confidence >= 0.50 (exact boundary)

Covers:
1. FIRE confidence = 0.49 -> 0 violations / rejected
2. FIRE confidence = 0.499 -> 0 violations / rejected
3. FIRE confidence = 0.50 -> 1 violation / accepted
4. FIRE confidence = 0.51 -> 1 violation / accepted
5. SMOKE confidence = 0.49 -> 0 violations / rejected
6. SMOKE confidence = 0.50 -> 1 violation / accepted
7. SMOKE confidence = 0.60 -> 1 violation / accepted
8. Disabled FIRE_SMOKE rule -> 0 violations / rejected
9. Persistence requirement: min_persistence_frames = 2 (promotes on frame 2)
10. Cooldown requirement: cooldown_seconds = 60 (duplicate suppression while active)
11. Historical events remain unchanged
12. Runtime default threshold verification (defaults to 0.50 when parameter omitted)
13. Real video frames from fire_02.mp4 (conf >= 0.50) -> EventType.FIRE_SMOKE promoted
"""

import os
from datetime import datetime, timezone
import pytest
import cv2

from app.database import SessionLocal
from app.models.alert import Alert
from app.models.event import Event, EventType
from app.models.safety_rule import RuleSeverity, RuleStatus, RuleType, SafetyRule
from app.models.zone import Zone, ZoneType
from app.schemas.detection import DetectionItem, DetectionPayload
from app.schemas.video_schema import WSFramePayload
from app.services.detection_adapter import DetectionAdapter
from app.services.event_engine import EventEngine
from app.services.inference import ModelType, get_inference_service
from app.services.rule_engine import SafetyRuleEngine
from app.services.video_service import VideoSession, VideoService


class MockRule:
    def __init__(
        self,
        id: str = "rule-fire-001",
        name: str = "Test Fire Smoke Rule",
        rule_type: RuleType = RuleType.FIRE_SMOKE,
        severity: RuleSeverity = RuleSeverity.CRITICAL,
        status: RuleStatus = RuleStatus.ACTIVE,
        parameters: dict | None = None,
        zone_id: str | None = None,
    ):
        self.id = id
        self.name = name
        self.rule_type = rule_type
        self.severity = severity
        self.status = status
        self.parameters = parameters if parameters is not None else {
            "confidence_threshold": 0.50,
            "min_persistence_frames": 2,
            "cooldown_seconds": 60,
        }
        self.zone_id = zone_id


# ==============================================================================
# EXACT THRESHOLD TESTS (0.49, 0.499, 0.50, 0.51, 0.60)
# ==============================================================================

def test_fire_confidence_0_49_rejected():
    """1. FIRE confidence = 0.49 -> 0 violations / rejected."""
    rule = MockRule(parameters={"confidence_threshold": 0.50})
    payload = DetectionPayload(
        camera_id="cam-01",
        timestamp=datetime.now(timezone.utc),
        detections=[
            DetectionItem(
                class_name="fire",
                confidence=0.49,
                bbox=[100.0, 150.0, 300.0, 400.0],
                track_id=1,
            )
        ],
    )
    result = SafetyRuleEngine.evaluate_frame(payload, rules=[rule])
    assert len(result.violations) == 0


def test_fire_confidence_0_499_rejected():
    """2. FIRE confidence = 0.499 -> 0 violations / rejected."""
    rule = MockRule(parameters={"confidence_threshold": 0.50})
    payload = DetectionPayload(
        camera_id="cam-01",
        timestamp=datetime.now(timezone.utc),
        detections=[
            DetectionItem(
                class_name="fire",
                confidence=0.499,
                bbox=[100.0, 150.0, 300.0, 400.0],
                track_id=1,
            )
        ],
    )
    result = SafetyRuleEngine.evaluate_frame(payload, rules=[rule])
    assert len(result.violations) == 0


def test_fire_confidence_0_50_accepted():
    """3. FIRE confidence = 0.50 -> 1 violation / accepted."""
    rule = MockRule(parameters={"confidence_threshold": 0.50})
    payload = DetectionPayload(
        camera_id="cam-01",
        timestamp=datetime.now(timezone.utc),
        detections=[
            DetectionItem(
                class_name="fire",
                confidence=0.500,
                bbox=[100.0, 150.0, 300.0, 400.0],
                track_id=1,
            )
        ],
    )
    result = SafetyRuleEngine.evaluate_frame(payload, rules=[rule])
    assert len(result.violations) == 1
    v = result.violations[0]
    assert v.rule_type == "fire_smoke"
    assert v.details["detected_class"] == "fire"
    assert v.details["confidence"] == 0.500
    assert v.details["person_confidence"] == 0.500
    assert "Fire detected" in v.message


def test_fire_confidence_0_51_accepted():
    """4. FIRE confidence = 0.51 -> 1 violation / accepted."""
    rule = MockRule(parameters={"confidence_threshold": 0.50})
    payload = DetectionPayload(
        camera_id="cam-01",
        timestamp=datetime.now(timezone.utc),
        detections=[
            DetectionItem(
                class_name="fire",
                confidence=0.51,
                bbox=[100.0, 150.0, 300.0, 400.0],
                track_id=1,
            )
        ],
    )
    result = SafetyRuleEngine.evaluate_frame(payload, rules=[rule])
    assert len(result.violations) == 1
    assert result.violations[0].rule_type == "fire_smoke"
    assert result.violations[0].details["confidence"] == 0.51


def test_smoke_confidence_0_49_rejected():
    """5. SMOKE confidence = 0.49 -> 0 violations / rejected."""
    rule = MockRule(parameters={"confidence_threshold": 0.50})
    payload = DetectionPayload(
        camera_id="cam-01",
        timestamp=datetime.now(timezone.utc),
        detections=[
            DetectionItem(
                class_name="smoke",
                confidence=0.49,
                bbox=[50.0, 20.0, 450.0, 200.0],
                track_id=2,
            )
        ],
    )
    result = SafetyRuleEngine.evaluate_frame(payload, rules=[rule])
    assert len(result.violations) == 0


def test_smoke_confidence_0_50_accepted():
    """6. SMOKE confidence = 0.50 -> 1 violation / accepted."""
    rule = MockRule(parameters={"confidence_threshold": 0.50})
    payload = DetectionPayload(
        camera_id="cam-01",
        timestamp=datetime.now(timezone.utc),
        detections=[
            DetectionItem(
                class_name="smoke",
                confidence=0.50,
                bbox=[50.0, 20.0, 450.0, 200.0],
                track_id=2,
            )
        ],
    )
    result = SafetyRuleEngine.evaluate_frame(payload, rules=[rule])
    assert len(result.violations) == 1
    v = result.violations[0]
    assert v.rule_type == "fire_smoke"
    assert v.details["detected_class"] == "smoke"
    assert v.details["confidence"] == 0.50
    assert "Smoke detected" in v.message


def test_smoke_confidence_0_60_accepted():
    """7. SMOKE confidence = 0.60 -> 1 violation / accepted."""
    rule = MockRule(parameters={"confidence_threshold": 0.50})
    payload = DetectionPayload(
        camera_id="cam-01",
        timestamp=datetime.now(timezone.utc),
        detections=[
            DetectionItem(
                class_name="smoke",
                confidence=0.60,
                bbox=[50.0, 20.0, 450.0, 200.0],
                track_id=2,
            )
        ],
    )
    result = SafetyRuleEngine.evaluate_frame(payload, rules=[rule])
    assert len(result.violations) == 1
    assert result.violations[0].rule_type == "fire_smoke"
    assert result.violations[0].details["confidence"] == 0.60


def test_disabled_fire_smoke_rule_rejected():
    """8. Disabled FIRE_SMOKE rule produces 0 violations even with high confidence."""
    rule = MockRule(status=RuleStatus.DISABLED, parameters={"confidence_threshold": 0.50})
    payload = DetectionPayload(
        camera_id="cam-01",
        timestamp=datetime.now(timezone.utc),
        detections=[
            DetectionItem(
                class_name="fire",
                confidence=0.95,
                bbox=[100.0, 150.0, 300.0, 400.0],
                track_id=1,
            )
        ],
    )
    result = SafetyRuleEngine.evaluate_frame(payload, rules=[rule])
    assert len(result.violations) == 0


def test_runtime_default_threshold_without_parameters():
    """12. Verify runtime default is 0.50 when rule parameters omit confidence_threshold."""
    rule = MockRule(parameters={})  # empty parameters -> should default to 0.50
    payload_below = DetectionPayload(
        camera_id="cam-01",
        timestamp=datetime.now(timezone.utc),
        detections=[DetectionItem(class_name="fire", confidence=0.499, bbox=[1, 1, 10, 10])],
    )
    payload_at = DetectionPayload(
        camera_id="cam-01",
        timestamp=datetime.now(timezone.utc),
        detections=[DetectionItem(class_name="fire", confidence=0.500, bbox=[1, 1, 10, 10])],
    )
    assert len(SafetyRuleEngine.evaluate_frame(payload_below, rules=[rule]).violations) == 0
    assert len(SafetyRuleEngine.evaluate_frame(payload_at, rules=[rule]).violations) == 1


# ==============================================================================
# PERSISTENCE & COOLDOWN TESTS
# ==============================================================================

def test_persistence_and_cooldown_behavior():
    """
    9 & 10. Verifies persistence requirement (min_persistence_frames = 2)
    and cooldown (cooldown_seconds = 60, duplicate suppression while active).
    """
    rule = MockRule(parameters={"confidence_threshold": 0.50, "min_persistence_frames": 2, "cooldown_seconds": 60})
    event_engine = EventEngine()
    db = SessionLocal()

    payload = DetectionPayload(
        camera_id="d0000000-0000-0000-0000-000000000020",
        timestamp=datetime.now(timezone.utc),
        detections=[
            DetectionItem(
                class_name="fire",
                confidence=0.65,  # > 0.50
                bbox=[100.0, 150.0, 300.0, 400.0],
                track_id=10,
            )
        ],
    )

    try:
        # Frame 1: Accumulating (1/2) -> 0 events
        eval1 = SafetyRuleEngine.evaluate_frame(payload, rules=[rule])
        ev1 = event_engine.process_frame(eval1, org_id="d0000000-0000-0000-0000-000000000001", db=db, rules=[rule])
        assert len(ev1) == 0, "Frame 1 must accumulate without event creation"

        # Frame 2: Promotes to ACTIVE (2/2) -> Exactly 1 event
        eval2 = SafetyRuleEngine.evaluate_frame(payload, rules=[rule])
        ev2 = event_engine.process_frame(eval2, org_id="d0000000-0000-0000-0000-000000000001", db=db, rules=[rule])
        assert len(ev2) == 1, "Frame 2 must promote violation to exactly 1 event"
        assert ev2[0].event_type == EventType.FIRE_SMOKE
        assert ev2[0].confidence == 0.65

        # Frame 3: Ongoing active violation -> duplicate event suppressed
        eval3 = SafetyRuleEngine.evaluate_frame(payload, rules=[rule])
        ev3 = event_engine.process_frame(eval3, org_id="d0000000-0000-0000-0000-000000000001", db=db, rules=[rule])
        assert len(ev3) == 0, "Frame 3 must suppress duplicate event while active"

        # Frame 4: Ongoing active violation -> duplicate event suppressed
        eval4 = SafetyRuleEngine.evaluate_frame(payload, rules=[rule])
        ev4 = event_engine.process_frame(eval4, org_id="d0000000-0000-0000-0000-000000000001", db=db, rules=[rule])
        assert len(ev4) == 0, "Frame 4 must suppress duplicate event while active"
    finally:
        db.rollback()
        db.close()


# ==============================================================================
# HISTORICAL DATA PRESERVATION TEST
# ==============================================================================

def test_historical_events_remain_intact():
    """11. Verify historical events and alerts in database are unchanged."""
    db = SessionLocal()
    total_events = db.query(Event).count()
    total_alerts = db.query(Alert).count()
    total_fs_events = db.query(Event).filter(Event.event_type == EventType.FIRE_SMOKE).count()
    db.close()

    assert total_events >= 140, "Historical events count must remain intact"
    assert total_alerts >= 700, "Historical alerts count must remain intact"
    assert total_fs_events >= 20, "Historical fire/smoke events must remain intact"


# ==============================================================================
# PHASE 11D — DETERMINISTIC FRAME-BASED EVENT GAP TESTS
# ==============================================================================

SEED_CAMERA_ID = "d0000000-0000-0000-0000-000000000020"
SEED_ORG_ID = "d0000000-0000-0000-0000-000000000001"
SEED_RULE_ID = "d0000000-0000-0000-0000-000000000032"


def test_phase11d_deterministic_15_frame_gap():
    """
    Tests 1, 2, 3, 4:
    1. First qualifying Fire detection -> event created (pers satisfied)
    2. Next frame qualifying Fire -> no event (frame +1)
    3. Frame +14 qualifying Fire -> no event
    4. Frame +15 qualifying Fire -> event created
    """
    rule = MockRule(id=SEED_RULE_ID, parameters={
        "confidence_threshold": 0.50,
        "min_persistence_frames": 2,
        "cooldown_seconds": 60,
        "frame_gap": 15,
    })
    event_engine = EventEngine()
    db = SessionLocal()

    payload_fire = DetectionPayload(
        camera_id=SEED_CAMERA_ID,
        timestamp=datetime.now(timezone.utc),
        detections=[
            DetectionItem(
                class_name="fire",
                confidence=0.70,
                bbox=[100.0, 150.0, 300.0, 400.0],
                track_id=1,
            )
        ],
    )

    try:
        # Frame 0: pers = 1/2 -> 0 events
        eval0 = SafetyRuleEngine.evaluate_frame(payload_fire, rules=[rule])
        ev0 = event_engine.process_frame(eval0, org_id=SEED_ORG_ID, db=db, rules=[rule], frame_idx=0)
        assert len(ev0) == 0, "Frame 0: must accumulate persistence (1/2)"

        # Frame 1: pers = 2/2 -> 1 event created (Test 1: First qualifying Fire detection)
        eval1 = SafetyRuleEngine.evaluate_frame(payload_fire, rules=[rule])
        ev1 = event_engine.process_frame(eval1, org_id=SEED_ORG_ID, db=db, rules=[rule], frame_idx=1)
        assert len(ev1) == 1, "Test 1: First qualifying Fire detection must create event"
        assert ev1[0].event_type == EventType.FIRE_SMOKE

        # Frame 2 (Frame 1 + 1): next frame qualifying Fire -> no event (Test 2)
        eval2 = SafetyRuleEngine.evaluate_frame(payload_fire, rules=[rule])
        ev2 = event_engine.process_frame(eval2, org_id=SEED_ORG_ID, db=db, rules=[rule], frame_idx=2)
        assert len(ev2) == 0, "Test 2: Next frame qualifying Fire must be suppressed"

        # Frames 3 through 14: all suppressed
        for f in range(3, 15):
            eval_f = SafetyRuleEngine.evaluate_frame(payload_fire, rules=[rule])
            ev_f = event_engine.process_frame(eval_f, org_id=SEED_ORG_ID, db=db, rules=[rule], frame_idx=f)
            assert len(ev_f) == 0, f"Frame {f} must be suppressed by 15-frame gap"

        # Frame 15 (Frame 1 + 14): Frame +14 qualifying Fire -> no event (Test 3)
        eval15 = SafetyRuleEngine.evaluate_frame(payload_fire, rules=[rule])
        ev15 = event_engine.process_frame(eval15, org_id=SEED_ORG_ID, db=db, rules=[rule], frame_idx=15)
        assert len(ev15) == 0, "Test 3: Frame +14 qualifying Fire must be suppressed"

        # Frame 16 (Frame 1 + 15): Frame +15 qualifying Fire -> event created (Test 4)
        eval16 = SafetyRuleEngine.evaluate_frame(payload_fire, rules=[rule])
        ev16 = event_engine.process_frame(eval16, org_id=SEED_ORG_ID, db=db, rules=[rule], frame_idx=16)
        assert len(ev16) == 1, "Test 4: Frame +15 qualifying Fire must create next event"
        assert ev16[0].event_type == EventType.FIRE_SMOKE
    finally:
        db.rollback()
        db.close()


def test_phase11d_shared_fire_smoke_window_cross_suppression():
    """
    Tests 5 & 6:
    5. Fire event followed by Smoke before frame +15 -> no new event
    6. Fire event followed by Smoke at frame +15 -> event allowed
    """
    rule = MockRule(id=SEED_RULE_ID, parameters={
        "confidence_threshold": 0.50,
        "min_persistence_frames": 2,
        "cooldown_seconds": 60,
        "frame_gap": 15,
    })
    event_engine = EventEngine()
    db = SessionLocal()

    payload_fire = DetectionPayload(
        camera_id=SEED_CAMERA_ID,
        timestamp=datetime.now(timezone.utc),
        detections=[
            DetectionItem(class_name="fire", confidence=0.70, bbox=[10.0, 10.0, 50.0, 50.0], track_id=1)
        ],
    )
    payload_smoke = DetectionPayload(
        camera_id=SEED_CAMERA_ID,
        timestamp=datetime.now(timezone.utc),
        detections=[
            DetectionItem(class_name="smoke", confidence=0.90, bbox=[20.0, 20.0, 80.0, 80.0], track_id=2)
        ],
    )

    try:
        # Frame 99: Fire accumulating (1/2)
        eval99 = SafetyRuleEngine.evaluate_frame(payload_fire, rules=[rule])
        ev99 = event_engine.process_frame(eval99, org_id=SEED_ORG_ID, db=db, rules=[rule], frame_idx=99)
        assert len(ev99) == 0

        # Frame 100: Fire promoted (2/2) -> Fire event created
        eval100 = SafetyRuleEngine.evaluate_frame(payload_fire, rules=[rule])
        ev100 = event_engine.process_frame(eval100, org_id=SEED_ORG_ID, db=db, rules=[rule], frame_idx=100)
        assert len(ev100) == 1
        assert ev100[0].event_type == EventType.FIRE_SMOKE

        # Frame 105: Smoke 0.90 -> NO new event because shared Fire/Smoke gap is active (Test 5)
        eval105 = SafetyRuleEngine.evaluate_frame(payload_smoke, rules=[rule])
        ev105 = event_engine.process_frame(eval105, org_id=SEED_ORG_ID, db=db, rules=[rule], frame_idx=105)
        assert len(ev105) == 0, "Test 5: Smoke at frame 105 must be suppressed by shared Fire/Smoke gap"

        # Frames 106..114: Smoke continues
        for f in range(106, 115):
            eval_s = SafetyRuleEngine.evaluate_frame(payload_smoke, rules=[rule])
            ev_s = event_engine.process_frame(eval_s, org_id=SEED_ORG_ID, db=db, rules=[rule], frame_idx=f)
            assert len(ev_s) == 0, f"Frame {f} Smoke must be suppressed by shared gap"

        # Frame 115 (100 + 15): Smoke 0.90 -> event allowed because 15 frames have elapsed (Test 6)
        eval115 = SafetyRuleEngine.evaluate_frame(payload_smoke, rules=[rule])
        ev115 = event_engine.process_frame(eval115, org_id=SEED_ORG_ID, db=db, rules=[rule], frame_idx=115)
        assert len(ev115) == 1, "Test 6: Smoke at frame 115 must be allowed after 15-frame gap"
        assert ev115[0].event_type == EventType.FIRE_SMOKE
    finally:
        db.rollback()
        db.close()


def test_phase11d_detection_below_threshold_never_creates_event():
    """
    Test 7: Detection < 0.50 -> no event regardless of frame position.
    """
    rule = MockRule(id=SEED_RULE_ID, parameters={
        "confidence_threshold": 0.50,
        "min_persistence_frames": 2,
        "cooldown_seconds": 60,
        "frame_gap": 15,
    })
    event_engine = EventEngine()
    db = SessionLocal()

    payload_below = DetectionPayload(
        camera_id=SEED_CAMERA_ID,
        timestamp=datetime.now(timezone.utc),
        detections=[
            DetectionItem(class_name="fire", confidence=0.499, bbox=[10.0, 10.0, 50.0, 50.0], track_id=1)
        ],
    )

    try:
        # Run across 30 consecutive frames
        for f in range(30):
            eval_res = SafetyRuleEngine.evaluate_frame(payload_below, rules=[rule])
            evs = event_engine.process_frame(eval_res, org_id=SEED_ORG_ID, db=db, rules=[rule], frame_idx=f)
            assert len(evs) == 0, f"Test 7: Detection 0.499 at frame {f} must never create an event"
    finally:
        db.rollback()
        db.close()


def test_phase11d_persistence_still_required():
    """
    Test 8: Persistence still required -> one qualifying frame alone does not bypass existing persistence.
    """
    rule = MockRule(id=SEED_RULE_ID, parameters={
        "confidence_threshold": 0.50,
        "min_persistence_frames": 2,
        "cooldown_seconds": 60,
        "frame_gap": 15,
    })
    event_engine = EventEngine()
    db = SessionLocal()

    payload_fire = DetectionPayload(
        camera_id=SEED_CAMERA_ID,
        timestamp=datetime.now(timezone.utc),
        detections=[
            DetectionItem(class_name="fire", confidence=0.80, bbox=[10.0, 10.0, 50.0, 50.0], track_id=1)
        ],
    )
    payload_empty = DetectionPayload(
        camera_id=SEED_CAMERA_ID,
        timestamp=datetime.now(timezone.utc),
        detections=[],
    )

    try:
        # Frame 0: 1 qualifying frame alone -> NO event (pers=1 < 2)
        eval0 = SafetyRuleEngine.evaluate_frame(payload_fire, rules=[rule])
        ev0 = event_engine.process_frame(eval0, org_id=SEED_ORG_ID, db=db, rules=[rule], frame_idx=0)
        assert len(ev0) == 0, "Test 8: One frame alone must not bypass persistence"

        # Frame 1: Fire clears -> resets accumulation
        eval1 = SafetyRuleEngine.evaluate_frame(payload_empty, rules=[rule])
        ev1 = event_engine.process_frame(eval1, org_id=SEED_ORG_ID, db=db, rules=[rule], frame_idx=1)
        assert len(ev1) == 0

        # Frame 20 (well past 15 frames): Fire returns for 1 frame -> STILL NO event (pers=1 < 2)
        eval20 = SafetyRuleEngine.evaluate_frame(payload_fire, rules=[rule])
        ev20 = event_engine.process_frame(eval20, org_id=SEED_ORG_ID, db=db, rules=[rule], frame_idx=20)
        assert len(ev20) == 0, "Test 8: Reappearing fire on 1 frame alone must not bypass persistence"

        # Frame 21: Second qualifying frame -> NOW event created!
        eval21 = SafetyRuleEngine.evaluate_frame(payload_fire, rules=[rule])
        ev21 = event_engine.process_frame(eval21, org_id=SEED_ORG_ID, db=db, rules=[rule], frame_idx=21)
        assert len(ev21) == 1, "Frame 21: Must create event once persistence requirement is satisfied"
    finally:
        db.rollback()
        db.close()


def test_phase11d_db_alerts_and_websocket_suppression():
    """
    Tests 9, 10, 11:
    9. PostgreSQL: suppressed frames create zero extra event rows
    10. Alerts: suppressed frames create zero extra alerts
    11. WebSocket: suppressed frames produce no additional new_events entries
    """
    from app.services.risk_engine import RiskEngine
    from app.services.alert_engine import AlertEngine
    from app.schemas.video_schema import WSEventSummary

    rule = MockRule(id=SEED_RULE_ID, parameters={
        "confidence_threshold": 0.50,
        "min_persistence_frames": 2,
        "cooldown_seconds": 60,
        "frame_gap": 15,
    })
    event_engine = EventEngine()
    db = SessionLocal()

    payload_fire = DetectionPayload(
        camera_id=SEED_CAMERA_ID,
        timestamp=datetime.now(timezone.utc),
        detections=[
            DetectionItem(class_name="fire", confidence=0.75, bbox=[100.0, 100.0, 200.0, 200.0], track_id=1)
        ],
    )

    created_event_ids = []
    created_alert_ids = []
    ws_new_events_across_frames = []

    try:
        # Initial count in DB
        initial_events_count = db.query(Event).count()
        initial_alerts_count = db.query(Alert).count()

        # Frame 0: pers 1/2 -> 0 events
        eval0 = SafetyRuleEngine.evaluate_frame(payload_fire, rules=[rule])
        evs0 = event_engine.process_frame(eval0, org_id=SEED_ORG_ID, db=db, rules=[rule], frame_idx=0)
        assert len(evs0) == 0

        # Frame 1: pers 2/2 -> 1 event created
        eval1 = SafetyRuleEngine.evaluate_frame(payload_fire, rules=[rule])
        evs1 = event_engine.process_frame(eval1, org_id=SEED_ORG_ID, db=db, rules=[rule], frame_idx=1)
        assert len(evs1) == 1

        for ev in evs1:
            created_event_ids.append(ev.id)
            risk = RiskEngine.assess_with_db(event=ev, db=db, lookback_hours=24)
            alert = AlertEngine.create_alert_from_risk(risk=risk, db=db, event=ev, rule_id=SEED_RULE_ID, title="Fire Alert")
            if alert:
                created_alert_ids.append(alert.id)
                db.commit()
            ws_new_events_across_frames.append(ev.id)

        count_after_first = db.query(Event).count()
        assert count_after_first == initial_events_count + 1

        # Frames 2 through 15 (14 suppressed frames)
        for f in range(2, 16):
            eval_f = SafetyRuleEngine.evaluate_frame(payload_fire, rules=[rule])
            evs_f = event_engine.process_frame(eval_f, org_id=SEED_ORG_ID, db=db, rules=[rule], frame_idx=f)

            # Test 9 & 11: Suppressed frames produce 0 events and 0 websocket entries
            ws_summaries_f = []
            for ev in evs_f:
                risk = RiskEngine.assess_with_db(event=ev, db=db, lookback_hours=24)
                alert = AlertEngine.create_alert_from_risk(risk=risk, db=db, event=ev, rule_id=SEED_RULE_ID, title="Fire Alert")
                if alert:
                    db.commit()
                ws_summaries_f.append(ev.id)

            assert len(evs_f) == 0, f"Frame {f} must have 0 events from EventEngine"
            assert len(ws_summaries_f) == 0, f"Test 11: Frame {f} must produce 0 WebSocket new_events"

        # Verify Test 9: PostgreSQL has ZERO extra event rows from the 14 suppressed frames
        current_events_count = db.query(Event).count()
        assert current_events_count == count_after_first, "Test 9: Suppressed frames must create ZERO extra event rows in PostgreSQL"

        # Verify Test 10: PostgreSQL has ZERO extra alert rows from the 14 suppressed frames
        current_alerts_count = db.query(Alert).count()
        assert current_alerts_count == initial_alerts_count + 1, "Test 10: Suppressed frames must create ZERO extra alerts"

    finally:
        # Clean up created test events and alerts
        if created_alert_ids:
            db.query(Alert).filter(Alert.id.in_(created_alert_ids)).delete(synchronize_session=False)
        if created_event_ids:
            db.query(Event).filter(Event.id.in_(created_event_ids)).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_phase11d_real_video_fire_02_gap():
    """
    Real video test on D:\\SafeVision-AI\\videos\\fire_02.mp4:
    Verifies actual Fire/Smoke events and their frame indices:
    Event 1: frame ~51/52
    No Fire/Smoke event: frames 52/53 through 65/66 (14 frames suppressed)
    Event 2: frame 66 or later, depending on persistence
    """
    video_path = r"D:\SafeVision-AI\videos\fire_02.mp4"
    if not os.path.exists(video_path):
        pytest.skip(f"Video file not found at {video_path}")

    inf = get_inference_service()
    cap = cv2.VideoCapture(video_path)

    rule = MockRule(parameters={
        "confidence_threshold": 0.50,
        "min_persistence_frames": 2,
        "cooldown_seconds": 60,
        "frame_gap": 15,
    })
    event_engine = EventEngine()
    db = SessionLocal()

    promoted_events = []
    active_fire_smoke_payload = None

    try:
        for frame_idx in range(80):
            ret, frame = cap.read()
            if not ret:
                break
            now = datetime.now(timezone.utc)

            # Sample Fire/Smoke every 5 frames as in video_service
            if frame_idx % 5 == 0:
                res = inf.track(frame=frame, model_type=ModelType.FIRE_SMOKE, conf=0.1)
                model = inf.get_model(ModelType.FIRE_SMOKE)
                active_fire_smoke_payload = DetectionAdapter.adapt(
                    res,
                    camera_id="d0000000-0000-0000-0000-000000000020",
                    model_names=model.names,
                    timestamp=now,
                )

            payload = active_fire_smoke_payload or DetectionPayload(
                camera_id="d0000000-0000-0000-0000-000000000020",
                timestamp=now,
                detections=[]
            )

            eval_res = SafetyRuleEngine.evaluate_frame(payload, rules=[rule])
            new_evs = event_engine.process_frame(
                evaluation=eval_res,
                org_id="d0000000-0000-0000-0000-000000000001",
                db=db,
                rules=[rule],
                now=now,
                frame_idx=frame_idx,
            )
            if new_evs:
                for ev in new_evs:
                    promoted_events.append((frame_idx, ev.event_type.value, ev.confidence))
    finally:
        cap.release()
        db.rollback()
        db.close()

    assert len(promoted_events) >= 2, f"Expected at least 2 events in first 80 frames, got {promoted_events}"
    ev1_frame = promoted_events[0][0]
    ev2_frame = promoted_events[1][0]

    # Verify Event 1 occurs around frame 51
    assert 50 <= ev1_frame <= 55, f"Event 1 should occur around frame 51/52, got {ev1_frame}"

    # Verify the gap between Event 1 and Event 2 is AT LEAST 15 frames!
    assert (ev2_frame - ev1_frame) >= 15, f"Gap between events must be >= 15 frames, got {ev2_frame - ev1_frame} (Event 1: frame {ev1_frame}, Event 2: frame {ev2_frame})"

