"""
SafeVision AI — Video Processing & Ingestion Service (Phase 11)

Handles:
- Upload validation and temporary file storage
- VideoSession state and lifecycle
- Frame extraction via OpenCV VideoCapture
- Cadence management:
    * PPE + Person tracking: 100% of pipeline frames (BoT-SORT continuity)
    * Fire / Smoke: Sampled every 5th frame (CPU efficiency)
- Coordinate scaling: Normalized Zone.polygon -> Frame pixel coordinates
- Execution of CVPipeline -> EventEngine -> RiskEngine -> AlertEngine
- JPEG encoding and WebSocket frame serialization
"""

from __future__ import annotations

import base64
import os
import shutil
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

import cv2
import numpy as np
import structlog
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.config import get_settings
from app.database import get_db
from app.models.camera import Camera
from app.models.event import Event, EventType
from app.models.safety_rule import SafetyRule, RuleType, RuleStatus, RuleSeverity
from app.models.zone import Zone, ZoneType
from app.schemas.detection import DetectionPayload
from app.schemas.video_schema import (
    WSDetectionItem,
    WSEventSummary,
    WSFramePayload,
    WSFrameStats,
    WSZoneViolation,
)
from app.services.alert_engine import AlertEngine
from app.services.detection_adapter import DetectionAdapter
from app.services.event_engine import EventEngine
from app.services.evidence_service import EvidenceService
from app.services.inference import ModelType, get_inference_service
from app.services.notification_service import NotificationService
from app.services.risk_engine import RiskEngine
from app.services.rule_engine import SafetyRuleEngine

log = structlog.get_logger()

# Allowed video extensions
ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

# Global session store (in-memory, thread-safe)
_sessions: dict[str, VideoSession] = {}
_sessions_lock = threading.Lock()

# Inference concurrency lock to prevent CPU saturation & BoT-SORT cross-contamination
_inference_lock = threading.Lock()


@dataclass
class VideoSession:
    """Represents an active video monitoring session."""
    session_id: str
    file_path: str
    filename: str
    camera_id: str
    zone_id: str | None
    org_id: str
    user_id: str
    total_frames: int
    source_fps: float
    width: int
    height: int
    duration_seconds: float
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True

    def cleanup(self) -> None:
        """Purge temporary video file."""
        self.is_active = False
        try:
            if os.path.exists(self.file_path):
                os.remove(self.file_path)
                log.info("video_session_temp_file_removed", session_id=self.session_id, path=self.file_path)
        except Exception as e:
            log.warning("video_session_cleanup_error", session_id=self.session_id, error=str(e))


class VideoService:
    """Service managing video file ingestion and frame-by-frame CV streaming."""

    @staticmethod
    def get_upload_dir() -> Path:
        """Get and ensure video uploads temporary directory exists."""
        settings = get_settings()
        upload_dir = Path(settings.video_upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        return upload_dir

    @classmethod
    def create_session(
        cls,
        temp_file_path: str,
        filename: str,
        camera: Camera,
        zone: Zone | None,
        user_id: str,
        org_id: str,
    ) -> VideoSession:
        """
        Validate video file with OpenCV and create a VideoSession.
        Raises ValueError if file cannot be opened or has no frames.
        """
        cap = cv2.VideoCapture(temp_file_path)
        if not cap.isOpened():
            cap.release()
            raise ValueError("Could not open video file. Invalid or unsupported codec/format.")

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        source_fps = float(cap.get(cv2.CAP_PROP_FPS))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()

        if total_frames <= 0 or width <= 0 or height <= 0:
            raise ValueError("Video contains no valid video frames or dimensions.")

        if source_fps <= 0 or np.isnan(source_fps):
            source_fps = 30.0  # Fallback standard FPS if container header missing

        duration_seconds = total_frames / source_fps if source_fps > 0 else 0.0

        session_id = str(uuid.uuid4())
        session = VideoSession(
            session_id=session_id,
            file_path=temp_file_path,
            filename=filename,
            camera_id=camera.id,
            zone_id=zone.id if zone else camera.zone_id,
            org_id=org_id,
            user_id=user_id,
            total_frames=total_frames,
            source_fps=round(source_fps, 2),
            width=width,
            height=height,
            duration_seconds=round(duration_seconds, 2),
        )

        with _sessions_lock:
            _sessions[session_id] = session

        log.info(
            "video_session_created",
            session_id=session_id,
            filename=filename,
            total_frames=total_frames,
            source_fps=source_fps,
            dimensions=f"{width}x{height}",
        )
        return session

    @classmethod
    def get_session(cls, session_id: str) -> VideoSession | None:
        """Retrieve active VideoSession by ID."""
        with _sessions_lock:
            return _sessions.get(session_id)

    @classmethod
    def delete_session(cls, session_id: str) -> None:
        """Cleanup and remove session."""
        with _sessions_lock:
            session = _sessions.pop(session_id, None)
        if session:
            session.cleanup()

    @classmethod
    def scale_polygon_to_pixels(
        cls,
        normalized_polygon: list[list[float]] | None,
        frame_width: int,
        frame_height: int,
    ) -> list[list[float]] | None:
        """
        Scale normalized 0.0-1.0 polygon coordinates to pixel coordinates
        matching YOLO bounding box dimensions for point-in-polygon evaluation.
        """
        if not normalized_polygon or len(normalized_polygon) < 3:
            return None
        return [
            [float(pt[0]) * frame_width, float(pt[1]) * frame_height]
            for pt in normalized_polygon
        ]

    @classmethod
    def process_video_generator(
        cls,
        session: VideoSession,
        db: Session,
        fire_smoke_interval: int = 5,
    ) -> AsyncGenerator[WSFramePayload, None]:
        """
        Synchronous/threaded generator yielding WSFramePayload per frame.
        Guarantees:
        - 100% cadence for PPE & BoT-SORT person tracking.
        - Sampled cadence for Fire/Smoke (every N frames).
        - Direct call to EventEngine -> RiskEngine -> AlertEngine.
        - Real deterministic risk stored on Event row.
        """
        inference = get_inference_service()

        # Isolate EventEngine per video session so violation state resets clean
        event_engine = EventEngine()

        # Reset BoT-SORT tracker state for clean tracking session
        with _inference_lock:
            inference.reset_tracker(ModelType.PPE)
            # WORKAROUND: inference.py clears model.predictor.trackers = [] which breaks Ultralytics track().
            # By setting model.predictor = None, we force Ultralytics to cleanly reinitialize the tracker array.
            model = inference.get_model(ModelType.PPE)
            if hasattr(model, "predictor") and model.predictor is not None:
                model.predictor = None

        # Retrieve Zone and SafetyRules for this camera/session
        zone = None
        if session.zone_id:
            zone = db.query(Zone).filter(Zone.id == session.zone_id).first()

        rules_query = (
            db.query(SafetyRule)
            .filter(SafetyRule.org_id == session.org_id)
            .all()
        )

        ignored_classes = set()
        active_rules = []

        import copy

        for r in rules_query:
            if r.status.value != RuleStatus.ACTIVE.value:
                continue
                
            if r.rule_type.value == RuleType.CUSTOM.value and r.name == "Detection Filter":
                ignored = r.parameters.get("ignored_classes", [])
                ignored_classes.update([cls.lower().strip() for cls in ignored])
            elif r.rule_type.value in {RuleType.EXCLUSION_ZONE.value, "zone_intrusion"}:
                # Restricted Area / Exclusion Zone is COMPLETELY IGNORED for video inference
                continue
            elif r.rule_type.value == RuleType.PPE_VIOLATION.value:
                # Dynamically strip ignored classes from required_ppe
                r_copy = copy.copy(r)
                params_copy = copy.deepcopy(r_copy.parameters)
                req_ppe = params_copy.get("required_ppe", [])
                params_copy["required_ppe"] = [p for p in req_ppe if p.lower().strip() not in ignored_classes]
                r_copy.parameters = params_copy
                active_rules.append(r_copy)
            else:
                if "exclusion" not in r.rule_type.value.lower() and "restricted" not in (r.name or "").lower():
                    active_rules.append(r)

        # Prepare zone for evaluation
        eval_zone = None
        if zone:
            eval_zone = copy.copy(zone)
            # Prevent automatic EXCLUSION zone fallback in rule_engine.py
            if eval_zone.zone_type.value == ZoneType.EXCLUSION.value:
                eval_zone.zone_type = ZoneType.GENERAL
            # Dynamically strip ignored classes from zone.required_ppe
            if eval_zone.required_ppe:
                eval_zone.required_ppe = [p for p in eval_zone.required_ppe if p.lower().strip() not in ignored_classes]

        cap = cv2.VideoCapture(session.file_path)
        frame_idx = 0
        total_events_generated = 0
        prev_time = time.perf_counter()
        active_fire_smoke_payload: DetectionPayload | None = None

        try:
            while cap.isOpened() and session.is_active:
                ret, frame = cap.read()
                if not ret:
                    break

                t_start = time.perf_counter()
                now = datetime.now(timezone.utc)

                # Acquire inference lock to ensure thread safety
                with _inference_lock:
                    # 1. PPE model runs on 100% of pipeline frames
                    ppe_results = inference.track(
                        frame=frame,
                        model_type=ModelType.PPE,
                        conf=0.1,
                    )
                    ppe_model = inference.get_model(ModelType.PPE)
                    ppe_payload = DetectionAdapter.adapt(
                        results=ppe_results,
                        camera_id=session.camera_id,
                        model_names=ppe_model.names,
                        timestamp=now,
                    )

                    # 2. Fire/Smoke runs on sampled cadence (every N frames)
                    if frame_idx % fire_smoke_interval == 0:
                        fs_results = inference.track(
                            frame=frame,
                            model_type=ModelType.FIRE_SMOKE,
                            conf=0.1,
                        )
                        fs_model = inference.get_model(ModelType.FIRE_SMOKE)
                        active_fire_smoke_payload = DetectionAdapter.adapt(
                            results=fs_results,
                            camera_id=session.camera_id,
                            model_names=fs_model.names,
                            timestamp=now,
                        )

                    # Merge payloads if fire/smoke detections exist
                    if active_fire_smoke_payload and active_fire_smoke_payload.detections:
                        payload = DetectionAdapter.merge_payloads(ppe_payload, active_fire_smoke_payload)
                    else:
                        payload = ppe_payload

                # Apply Ignore Class filtering
                if ignored_classes:
                    filtered_detections = []
                    for d in payload.detections:
                        cls_lower = d.class_name.lower().strip()
                        if cls_lower not in ignored_classes:
                            filtered_detections.append(d)
                        elif cls_lower in {"person", "worker"}:
                            # If PERSON is ignored, all person tracks are suppressed from this frame
                            pass
                    payload.detections = filtered_detections

                # 3. Rule Evaluation with sanitized zone and rules
                evaluation = SafetyRuleEngine.evaluate_frame(
                    payload=payload,
                    rules=active_rules,
                    zone=eval_zone,
                )

                # Filter out any exclusion_zone / restricted zone violations completely
                evaluation.violations = [
                    v for v in evaluation.violations
                    if v.rule_type not in {"exclusion_zone", "zone_intrusion"}
                    and "restricted" not in (v.rule_name or "").lower()
                    and "exclusion" not in (v.rule_name or "").lower()
                ]

                # 4. Temporal accumulation through EventEngine
                new_events_orm = event_engine.process_frame(
                    evaluation=evaluation,
                    org_id=session.org_id,
                    db=db,
                    rules=active_rules,
                    now=now,
                    frame_idx=frame_idx,
                )

                # Ensure no restricted zone events leak downstream
                new_events_orm = [
                    e for e in new_events_orm
                    if getattr(e, "event_type", None) != EventType.ZONE_INTRUSION
                    and "restricted" not in getattr(e, "description", "").lower()
                    and "exclusion" not in getattr(e, "description", "").lower()
                ]

                # 5. For each newly promoted Event: compute REAL RiskAssessment + Alert
                new_events_summaries: list[WSEventSummary] = []
                for event in new_events_orm:
                    # Authoritative Event Frame Evidence Capture (non-fatal)
                    evidence_rel_path = EvidenceService.capture_and_save(
                        frame=frame,
                        event=event,
                        frame_idx=frame_idx,
                        violations=evaluation.violations,
                    )
                    if evidence_rel_path:
                        event.evidence_path = evidence_rel_path

                    # Deterministic Risk Assessment via RiskEngine
                    risk = RiskEngine.assess_with_db(event=event, db=db, lookback_hours=24)

                    # Persist authentic risk assessment inside event.detection_data
                    det_data = event.detection_data or {}
                    det_data["risk_assessment"] = {
                        "risk_score": risk.risk_score,
                        "risk_level": risk.risk_level,
                        "factors": [f.model_dump() for f in risk.factors],
                        "explanation": risk.explanation,
                        "assessed_at": risk.assessed_at.isoformat(),
                    }
                    # Save authoritative video source & evidence metadata
                    det_data["source"] = {
                        "type": "uploaded_video",
                        "filename": session.filename,
                        "frame_index": frame_idx,
                        "evidence_image": evidence_rel_path,
                    }
                    event.detection_data = det_data
                    flag_modified(event, "detection_data")

                    # Deterministic Alert Creation via AlertEngine (links event.evidence_path)
                    alert = AlertEngine.create_alert_from_risk(
                        risk=risk,
                        db=db,
                        event=event,
                        rule_id=det_data.get("rule_id"),
                        title=f"{event.event_type.replace('_', ' ').title()} - {session.filename}",
                        description=risk.explanation,
                    )
                    db.commit()

                    # Phase 15 — Notification dispatch
                    # MUST be called AFTER db.commit() so the Alert is fully persisted.
                    # dispatch() is guaranteed not to raise — any failure is logged and
                    # persisted as Notification(status=FAILED) without affecting the pipeline.
                    try:
                        NotificationService.dispatch(
                            alert=alert,
                            event=event,
                            db=db,
                        )
                    except Exception:
                        log.exception(
                            "notification_dispatch_failed",
                            alert_id=alert.id,
                        )

                    total_events_generated += 1
                    new_events_summaries.append(
                        WSEventSummary(
                            event_id=event.id,
                            event_type=event.event_type if isinstance(event.event_type, str) else event.event_type.value,
                            severity=risk.risk_level,
                            message=det_data.get("message") or risk.explanation,
                            timestamp=event.timestamp.isoformat() if event.timestamp else now.isoformat(),
                            risk_score=risk.risk_score,
                            risk_level=risk.risk_level,
                        )
                    )

                # Measure frame inference throughput
                t_end = time.perf_counter()
                inference_duration = t_end - t_start
                inference_fps = round(1.0 / max(inference_duration, 0.001), 1)

                # Build detection items for frontend
                ws_detections: list[WSDetectionItem] = []
                violation_track_ids = {v.track_id for v in evaluation.violations if v.track_id is not None}
                violation_by_track = {v.track_id: v for v in evaluation.violations if v.track_id is not None}

                for d in payload.detections:
                    is_compliant = True
                    missing_ppe: list[str] = []
                    detected_ppe: list[str] = []

                    if d.track_id is not None and d.track_id in violation_track_ids:
                        is_compliant = False
                        viol = violation_by_track[d.track_id]
                        missing_ppe = viol.missing_ppe
                        detected_ppe = viol.detected_ppe

                    ws_detections.append(
                        WSDetectionItem(
                            class_name=d.class_name,
                            confidence=round(d.confidence, 3),
                            bbox=[round(coord, 1) for coord in (d.bbox or [])],
                            track_id=d.track_id,
                            is_compliant=is_compliant,
                            missing_ppe=missing_ppe,
                            detected_ppe=detected_ppe,
                        )
                    )

                # Zone violations are disabled for restricted areas
                ws_zone_violations: list[WSZoneViolation] = []

                # Encode frame to JPEG Base64
                _, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
                b64_image = "data:image/jpeg;base64," + base64.b64encode(buffer).decode("ascii")

                stats = WSFrameStats(
                    source_fps=session.source_fps,
                    inference_fps=inference_fps,
                    persons_detected=evaluation.total_persons_detected,
                    active_violations=len(evaluation.violations),
                    total_events_generated=total_events_generated,
                )

                timestamp_ms = int((frame_idx / session.source_fps) * 1000)

                payload_obj = WSFramePayload(
                    type="frame",
                    frame_idx=frame_idx,
                    total_frames=session.total_frames,
                    timestamp_ms=timestamp_ms,
                    image=b64_image,
                    detections=ws_detections,
                    zone_polygon=zone.polygon if zone else None,
                    zone_violations=ws_zone_violations,
                    new_events=new_events_summaries,
                    stats=stats,
                )

                yield payload_obj
                frame_idx += 1

        finally:
            cap.release()
            event_engine.clear_all()
            log.info(
                "video_processing_finished",
                session_id=session.session_id,
                frames_processed=frame_idx,
                total_events=total_events_generated,
            )
