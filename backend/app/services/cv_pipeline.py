"""
SafeVision AI — CV Pipeline

Top-level per-frame callable that chains:
  frame → InferenceService.track() → DetectionAdapter → DetectionPayload
      → SafetyRuleEngine.evaluate_frame() → EventEngine.process_frame()
      → Safety Event rows in PostgreSQL

Phase boundary:
  This module exposes process_frame() as a callable.
  Phase 7 will invoke this in a camera stream loop (RTSP reader, Celery worker).
  This module does NOT contain RTSP readers, frame loops, or stream lifecycle.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import structlog
from sqlalchemy.orm import Session

from app.models.zone import Zone
from app.schemas.detection import RuleEvaluationResult
from app.services.detection_adapter import DetectionAdapter
from app.services.event_engine import EventEngine
from app.services.inference import InferenceService, ModelType
from app.services.rule_engine import SafetyRuleEngine

log = structlog.get_logger()


class CVPipeline:
    """
    Single-frame CV processing pipeline.

    Orchestrates: inference → adaptation → rule evaluation → event persistence.
    Stateful only through the EventEngine (temporal accumulation).
    """

    def __init__(
        self,
        inference_service: InferenceService,
        event_engine: EventEngine,
    ) -> None:
        self._inference = inference_service
        self._event_engine = event_engine

    def process_frame(
        self,
        frame: np.ndarray,
        camera_id: str,
        org_id: str,
        db: Session,
        zone: Zone | None = None,
        rules: list | None = None,
        timestamp: datetime | None = None,
        run_fire_smoke: bool = False,
    ) -> RuleEvaluationResult:
        """
        Process a single video frame through the full SafeVision pipeline.

        Steps:
        1. Run YOLO26 inference with BoT-SORT tracking (PPE model)
        2. Optionally run fire/smoke model on the same frame
        3. Convert Ultralytics Results → DetectionPayload via adapter
        4. Evaluate safety rules via SafetyRuleEngine
        5. Process violations through EventEngine (temporal persistence + DB)

        Args:
            frame: BGR numpy array (OpenCV format) — the raw video frame
            camera_id: Source camera identifier
            org_id: Organization ID for tenant isolation
            db: SQLAlchemy session for DB persistence
            zone: Optional Zone object for zone-scoped rules
            rules: List of SafetyRule instances to evaluate
            timestamp: Frame capture time (defaults to now)
            run_fire_smoke: Whether to also run fire/smoke detection

        Returns:
            RuleEvaluationResult with all violations and compliant tracks.
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        # Step 1: PPE model inference with BoT-SORT tracking
        ppe_results = self._inference.track(
            frame=frame,
            model_type=ModelType.PPE,
        )

        ppe_model = self._inference.get_model(ModelType.PPE)
        ppe_payload = DetectionAdapter.adapt(
            results=ppe_results,
            camera_id=camera_id,
            model_names=ppe_model.names,
            timestamp=timestamp,
        )

        # Step 2: Optional fire/smoke model
        if run_fire_smoke:
            fire_results = self._inference.track(
                frame=frame,
                model_type=ModelType.FIRE_SMOKE,
            )
            fire_model = self._inference.get_model(ModelType.FIRE_SMOKE)
            fire_payload = DetectionAdapter.adapt(
                results=fire_results,
                camera_id=camera_id,
                model_names=fire_model.names,
                timestamp=timestamp,
            )
            # Merge PPE + fire/smoke detections
            payload = DetectionAdapter.merge_payloads(ppe_payload, fire_payload)
        else:
            payload = ppe_payload

        log.debug(
            "pipeline_inference_complete",
            camera_id=camera_id,
            num_detections=len(payload.detections),
            classes=[d.class_name for d in payload.detections],
        )

        # Step 3: Evaluate safety rules
        evaluation = SafetyRuleEngine.evaluate_frame(
            payload=payload,
            rules=rules or [],
            zone=zone,
        )

        # Step 4: Process violations through event engine
        new_events = self._event_engine.process_frame(
            evaluation=evaluation,
            org_id=org_id,
            db=db,
            rules=rules,
            now=timestamp,
        )

        if new_events:
            log.info(
                "pipeline_events_created",
                camera_id=camera_id,
                num_new_events=len(new_events),
                event_ids=[e.id for e in new_events],
            )

        return evaluation
