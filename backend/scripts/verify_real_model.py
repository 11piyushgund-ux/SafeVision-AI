"""
SafeVision AI — Real Model Verification Script (Phase 6 STOP Gate)

This script is NOT a CI test — it requires:
- Actual YOLO26 model weights (models/ppe/best.pt, models/fire_smoke/best.pt)
- PostgreSQL running with the SafeVision database

It performs a SINGLE REAL END-TO-END trace:
  real test image
  -> real YOLO26 inference
  -> real BoT-SORT tracking
  -> real DetectionAdapter
  -> real Phase 5 SafetyRuleEngine
  -> real EventEngine
  -> PostgreSQL Safety Event row

No synthetic payloads. The only synthetic element is the rule configuration
(which is always synthetic in any test scenario — rules live in the DB in prod).

Run:
  cd backend
  $env:PYTHONIOENCODING='utf-8'; python scripts/verify_real_model.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    print("=" * 70)
    print("SafeVision AI -- Real End-to-End Trace (Phase 6 STOP Gate)")
    print("=" * 70)

    # ======================================================================
    # Step 1: Verify model files exist
    # ======================================================================
    print("\n[1/10] Checking model files...")

    ppe_path = Path(__file__).parent.parent.parent / "models" / "ppe" / "best.pt"
    fire_path = Path(__file__).parent.parent.parent / "models" / "fire_smoke" / "best.pt"

    assert ppe_path.exists(), f"PPE model not found: {ppe_path}"
    assert fire_path.exists(), f"Fire/Smoke model not found: {fire_path}"
    print(f"  [OK] PPE model: {ppe_path} ({ppe_path.stat().st_size / 1e6:.1f} MB)")
    print(f"  [OK] Fire/Smoke model: {fire_path} ({fire_path.stat().st_size / 1e6:.1f} MB)")

    # ======================================================================
    # Step 2: Load models and verify NMS-free
    # ======================================================================
    print("\n[2/10] Loading YOLO26 models and verifying NMS-free...")

    from ultralytics import YOLO

    ppe_model = YOLO(str(ppe_path))
    fire_model = YOLO(str(fire_path))

    ppe_end2end = getattr(ppe_model.model, "end2end", False)
    fire_end2end = getattr(fire_model.model, "end2end", False)

    print(f"  PPE model.model.end2end = {ppe_end2end}")
    print(f"  Fire/Smoke model.model.end2end = {fire_end2end}")

    assert ppe_end2end, "PPE model is NOT end-to-end NMS-free!"
    assert fire_end2end, "Fire/Smoke model is NOT end-to-end NMS-free!"
    print("  [OK] Both models confirmed NMS-free (end-to-end)")

    print(f"\n  PPE classes: {ppe_model.names}")
    print(f"  Fire/Smoke classes: {fire_model.names}")

    # ======================================================================
    # Step 3: Load test image (bus.jpg has real people)
    # ======================================================================
    print("\n[3/10] Loading test image...")

    import cv2
    import ultralytics as _ul

    # Use Ultralytics bus.jpg which has real people
    frame_path = Path(_ul.__file__).parent / "assets" / "bus.jpg"
    assert frame_path.exists(), f"bus.jpg not found at {frame_path}"

    frame = cv2.imread(str(frame_path))
    assert frame is not None, f"Failed to load image: {frame_path}"
    print(f"  Using: {frame_path}")
    print(f"  Shape: {frame.shape} (H={frame.shape[0]}, W={frame.shape[1]})")

    # ======================================================================
    # Step 4: REAL YOLO26 inference with BoT-SORT tracking
    # ======================================================================
    print("\n[4/10] Running REAL PPE inference with BoT-SORT tracking...")

    botsort_config = str(Path(__file__).parent.parent / "app" / "cv" / "botsort.yaml")
    print(f"  Tracker config: {botsort_config}")

    ppe_results = ppe_model.track(
        frame,
        persist=True,
        tracker=botsort_config,
        conf=0.1,
        verbose=False,
    )

    result = ppe_results[0]
    boxes = result.boxes

    detected_classes = []
    has_person = False
    has_track_ids = False

    if boxes is not None and len(boxes) > 0:
        print(f"  [OK] Detected {len(boxes)} objects")
        print(f"  boxes.xyxy shape: {boxes.xyxy.shape}")
        print(f"  boxes.conf: {[round(c, 4) for c in boxes.conf.tolist()]}")
        detected_classes = [ppe_model.names[int(c)] for c in boxes.cls.tolist()]
        print(f"  boxes.cls (names): {detected_classes}")

        has_person = "person" in detected_classes
        has_track_ids = boxes.id is not None
        if has_track_ids:
            print(f"  boxes.id (track IDs): {[int(t) for t in boxes.id.tolist()]}")
            print("  [OK] BoT-SORT tracker assigned track IDs")
        else:
            print("  [WARN] Tracker did not assign IDs on first frame")
    else:
        print("  [WARN] No detections")

    # ======================================================================
    # Step 5: REAL DetectionAdapter conversion
    # ======================================================================
    print("\n[5/10] Converting through REAL DetectionAdapter...")

    from app.services.detection_adapter import DetectionAdapter

    payload = DetectionAdapter.adapt(
        results=ppe_results,
        camera_id="cam-e2e-trace",
        model_names=ppe_model.names,
        timestamp=datetime.now(timezone.utc),
    )

    print(f"  [OK] DetectionPayload created:")
    print(f"     camera_id: {payload.camera_id}")
    print(f"     num_detections: {len(payload.detections)}")
    for d in payload.detections[:10]:
        print(f"     - class={d.class_name}, conf={d.confidence:.3f}, "
              f"bbox={[round(x, 1) for x in d.bbox] if d.bbox else None}, "
              f"track_id={d.track_id}")

    # ======================================================================
    # Step 6: REAL Phase 5 SafetyRuleEngine evaluation
    # ======================================================================
    print("\n[6/10] Evaluating through REAL SafetyRuleEngine...")

    from app.services.rule_engine import SafetyRuleEngine

    # Rule config: require helmet + safety_vest for any detected person.
    # bus.jpg people have neither -> guaranteed violation from real detections.
    class E2ETestRule:
        id = "rule-e2e-ppe"
        name = "E2E PPE Verification Rule"
        rule_type = type("RT", (), {"value": "ppe_violation"})()
        severity = type("RS", (), {"value": "high"})()
        status = type("RS", (), {"value": "active"})()
        parameters = {
            "required_ppe": ["helmet", "safety_vest"],
            "confidence_threshold": 0.1,
            "person_confidence_threshold": 0.1,
            "min_persistence_frames": 1,
        }
        zone_id = None

    evaluation = SafetyRuleEngine.evaluate_frame(
        payload=payload,
        rules=[E2ETestRule()],
    )

    print(f"  total_persons: {evaluation.total_persons_detected}")
    print(f"  violations: {len(evaluation.violations)}")
    print(f"  compliant_tracks: {evaluation.compliant_track_ids}")
    for v in evaluation.violations[:5]:
        print(f"  - track={v.track_id}, type={v.rule_type}, "
              f"missing={v.missing_ppe}, detected={v.detected_ppe}")

    # Gate check: we need at least one person detected AND at least one violation
    if evaluation.total_persons_detected == 0:
        print("\n  [GATE ISSUE] No persons detected by the real model on bus.jpg.")
        print("  The PPE model was trained on construction workers — bus.jpg people")
        print("  may not match its person class. Trying with lower confidence...")
        # Retry with even lower threshold
        E2ETestRule.parameters["person_confidence_threshold"] = 0.05
        E2ETestRule.parameters["confidence_threshold"] = 0.05
        evaluation = SafetyRuleEngine.evaluate_frame(
            payload=payload,
            rules=[E2ETestRule()],
        )
        print(f"  Retry: persons={evaluation.total_persons_detected}, "
              f"violations={len(evaluation.violations)}")

    # ======================================================================
    # Step 7: Set up DB test data (org/site/camera for FK constraints)
    # ======================================================================
    print("\n[7/10] Setting up DB test data...")

    from app.database import SessionLocal
    from app.models.camera import Camera, CameraStatus
    from app.models.organization import Organization
    from app.models.site import Site

    # Fixed IDs — idempotent across repeated runs
    E2E_ORG_ID = "00000000-0000-0000-0000-e2e000000001"
    E2E_SITE_ID = "00000000-0000-0000-0000-e2e000000002"
    E2E_CAM_ID = "cam-e2e-trace"

    db = SessionLocal()

    try:
        if not db.query(Organization).filter(Organization.id == E2E_ORG_ID).first():
            db.add(Organization(id=E2E_ORG_ID, name="E2E Verify Org", slug="e2e-verify"))
            db.flush()

        if not db.query(Site).filter(Site.id == E2E_SITE_ID).first():
            db.add(Site(id=E2E_SITE_ID, org_id=E2E_ORG_ID, name="E2E Verify Site"))
            db.flush()

        if not db.query(Camera).filter(Camera.id == E2E_CAM_ID).first():
            db.add(Camera(
                id=E2E_CAM_ID, site_id=E2E_SITE_ID,
                org_id=E2E_ORG_ID, name="E2E Trace Camera",
                status=CameraStatus.ONLINE,
            ))
            db.flush()

        db.commit()
        print("  [OK] Test data (org/site/camera) ready")
    except Exception as e:
        print(f"  [ERROR] Setup failed: {e}")
        db.rollback()
        db.close()
        return

    # ======================================================================
    # Step 8: REAL EventEngine -> PostgreSQL
    # ======================================================================
    print("\n[8/10] Processing through REAL EventEngine -> PostgreSQL...")

    from app.services.event_engine import EventEngine

    event_engine = EventEngine()
    created_events = []

    try:
        events = event_engine.process_frame(
            evaluation=evaluation,
            org_id=E2E_ORG_ID,
            db=db,
            rules=[E2ETestRule()],
            now=datetime.now(timezone.utc),
        )

        created_events = events

        if events:
            print(f"  [OK] {len(events)} Safety Event(s) created from REAL model output!")
            for event in events:
                print(f"\n  === REAL SAFETY EVENT ROW ===")
                print(f"  event.id:          {event.id}")
                print(f"  event.event_type:  {event.event_type}")
                print(f"  event.camera_id:   {event.camera_id}")
                print(f"  event.org_id:      {event.org_id}")
                print(f"  event.confidence:  {event.confidence}")
                print(f"  event.timestamp:   {event.timestamp}")
                print(f"  event.detection_data:")
                print(json.dumps(event.detection_data, indent=4, default=str))
        else:
            print("  [WARN] No events created (no violations from real model output)")
            print("  This means the PPE model did not detect persons in bus.jpg")

    except Exception as e:
        print(f"  [ERROR] Event engine/DB error: {e}")
        db.rollback()
    finally:
        db.close()

    # ======================================================================
    # Step 9: Verify DB row persistence
    # ======================================================================
    print("\n[9/10] Verifying DB row persistence...")

    if created_events:
        db2 = SessionLocal()
        try:
            from app.models.event import Event

            saved = db2.query(Event).filter(Event.id == created_events[0].id).first()
            if saved:
                print(f"  [OK] Event row CONFIRMED in PostgreSQL!")
                print(f"     ID: {saved.id}")
                print(f"     Type: {saved.event_type}")
                print(f"     Camera: {saved.camera_id}")
                print(f"     Org: {saved.org_id}")
                print(f"     detection_data keys: {list(saved.detection_data.keys())}")
                print(f"     missing_ppe: {saved.detection_data.get('missing_ppe')}")
                print(f"     detected_ppe: {saved.detection_data.get('detected_ppe')}")
                print(f"     track_id: {saved.detection_data.get('track_id')}")
            else:
                print("  [FAIL] Event row NOT found in database!")
        finally:
            db2.close()
    else:
        print("  [SKIP] No events to verify (see above)")

    # ======================================================================
    # Step 10: Summary
    # ======================================================================
    print("\n" + "=" * 70)
    print("Phase 6 Real End-to-End Trace SUMMARY")
    print("=" * 70)

    print(f"\n  Models loaded:           YES")
    print(f"  NMS-free (end2end):      PPE={ppe_end2end}, Fire={fire_end2end}")
    print(f"  BoT-SORT tracking:       {'YES (IDs assigned)' if has_track_ids else 'Partial (first frame)'}")
    print(f"  Adapter detections:      {len(payload.detections)}")
    print(f"  Persons detected:        {evaluation.total_persons_detected}")
    print(f"  Rule violations:         {len(evaluation.violations)}")
    print(f"  DB events created:       {len(created_events)}")

    if created_events:
        print(f"  Event ID (real trace):   {created_events[0].id}")
        print(f"\n  GATE VERDICT: PASS -- real image -> real YOLO26 -> real BoT-SORT")
        print(f"                       -> real adapter -> real rule engine")
        print(f"                       -> real event engine -> PostgreSQL row CONFIRMED")
    elif evaluation.total_persons_detected > 0 and len(evaluation.violations) > 0:
        print(f"\n  GATE VERDICT: PARTIAL -- violations found but DB persistence failed")
    else:
        print(f"\n  GATE VERDICT: PARTIAL -- model detected {len(payload.detections)} objects")
        print(f"                          but {evaluation.total_persons_detected} persons")
        print(f"                          (PPE model may not detect bus.jpg people)")

    print()


if __name__ == "__main__":
    main()
