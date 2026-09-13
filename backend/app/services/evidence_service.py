"""
SafeVision AI — Evidence Service (Phase 12)

Captures, annotates, and persists visual frame evidence for promoted Safety Events.
Enforces:
1. Exact promotion frame correspondence (frame_idx).
2. Clean, focused event-specific annotations (Fire/Smoke or PPE).
3. Tenant-isolated local storage: evidence_storage/{org_id}/{event_id}.jpg.
4. Non-fatal failure semantics: failure to capture evidence never impedes event creation.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import structlog

from app.config import get_settings
from app.models.event import Event, EventType

log = structlog.get_logger()


class EvidenceService:
    """Service for capturing, annotating, storing, and retrieving event visual evidence."""

    @staticmethod
    def get_storage_base_dir() -> Path:
        """Get base directory for evidence storage."""
        settings = get_settings()
        base_dir = Path(settings.evidence_local_path).resolve()
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir

    @staticmethod
    def get_tenant_dir(org_id: str) -> Path:
        """Get or create tenant-specific evidence directory."""
        base_dir = EvidenceService.get_storage_base_dir()
        tenant_dir = (base_dir / org_id).resolve()
        # Security: verify tenant_dir does not traverse outside base_dir
        if not tenant_dir.is_relative_to(base_dir):
            raise ValueError(f"Invalid org_id directory traversal attempt: {org_id}")
        tenant_dir.mkdir(parents=True, exist_ok=True)
        return tenant_dir

    @classmethod
    def annotate_frame(
        cls,
        frame: np.ndarray,
        event: Event,
        frame_idx: int,
        violations: list[Any] | None = None,
    ) -> np.ndarray:
        """
        Create a focused, clean annotation of the exact event frame.
        Draws only the bounding boxes and labels relevant to the specific event.
        """
        annotated = frame.copy()
        h, w = annotated.shape[:2]

        det_data = event.detection_data or {}
        event_type_str = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)

        # 1. Top banner stamp: Frame index and Event Type
        banner_text = f"FRAME {frame_idx} | {event_type_str.replace('_', ' ').upper()}"
        cv2.rectangle(annotated, (10, 10), (min(w - 10, 420), 44), (18, 18, 24), -1)
        cv2.rectangle(annotated, (10, 10), (min(w - 10, 420), 44), (59, 130, 246), 1)
        cv2.putText(
            annotated,
            banner_text,
            (20, 33),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        # 2. Focused Detection Annotations
        if event_type_str == EventType.FIRE_SMOKE.value:
            # Fire / Smoke detection overlay
            detected_class = (det_data.get("details", {}).get("detected_class") or "fire").lower()
            conf = det_data.get("details", {}).get("confidence") or event.confidence or 0.0
            bbox = det_data.get("details", {}).get("bbox") or det_data.get("person_bbox")

            color = (0, 69, 255) if "fire" in detected_class else (180, 180, 180)  # Orange-red for fire, gray for smoke
            if bbox and len(bbox) >= 4:
                x1, y1, x2, y2 = [int(coord) for coord in bbox[:4]]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w - 1, x2), min(h - 1, y2)

                # Draw bounding box
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 3)

                # Label tag
                track_id = det_data.get("track_id")
                track_str = f" [ID:{track_id}]" if track_id and track_id not in {"fire", "smoke"} else ""
                label = f"{detected_class.upper()}{track_str} {conf:.0%}"
                (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                cv2.rectangle(annotated, (x1, max(0, y1 - lh - 10)), (x1 + lw + 12, y1), color, -1)
                cv2.putText(
                    annotated,
                    label,
                    (x1 + 6, max(lh + 4, y1 - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA,
                )

        elif event_type_str in {EventType.PPE_DETECTION.value, "ppe_violation"}:
            # PPE Violation overlay
            bbox = det_data.get("person_bbox") or det_data.get("bbox")
            track_id = det_data.get("track_id")
            missing_ppe = det_data.get("missing_ppe") or []
            color = (0, 0, 220)  # Red for violation

            if bbox and len(bbox) >= 4:
                x1, y1, x2, y2 = [int(coord) for coord in bbox[:4]]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w - 1, x2), min(h - 1, y2)

                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 3)

                track_str = f"Track {track_id}" if track_id is not None else "Person"
                missing_str = f"Missing: {', '.join(missing_ppe)}" if missing_ppe else "PPE Violation"
                label = f"{track_str} — {missing_str}"
                (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
                cv2.rectangle(annotated, (x1, max(0, y1 - lh - 10)), (x1 + lw + 12, y1), color, -1)
                cv2.putText(
                    annotated,
                    label,
                    (x1 + 6, max(lh + 4, y1 - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA,
                )

        return annotated

    @classmethod
    def capture_and_save(
        cls,
        frame: np.ndarray,
        event: Event,
        frame_idx: int,
        violations: list[Any] | None = None,
    ) -> str | None:
        """
        Capture and persist the exact event promotion frame.

        Returns relative path string "{org_id}/{event_id}.jpg" on success.
        Returns None on any error without raising, preserving event/alert creation.
        """
        if frame is None or frame.size == 0:
            log.warning("evidence_capture_empty_frame", event_id=event.id, frame_idx=frame_idx)
            return None

        try:
            tenant_dir = cls.get_tenant_dir(event.org_id)
            filename = f"{event.id}.jpg"
            file_path = tenant_dir / filename

            # Annotate frame copy
            annotated_frame = cls.annotate_frame(
                frame=frame,
                event=event,
                frame_idx=frame_idx,
                violations=violations,
            )

            # High quality, compact JPEG
            success, buffer = cv2.imencode(".jpg", annotated_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if not success:
                log.error("evidence_encoding_failed", event_id=event.id, frame_idx=frame_idx)
                return None

            with open(file_path, "wb") as f:
                f.write(buffer.tobytes())

            relative_path = f"{event.org_id}/{filename}"
            log.info(
                "evidence_captured",
                event_id=event.id,
                org_id=event.org_id,
                frame_idx=frame_idx,
                relative_path=relative_path,
                bytes=len(buffer),
            )
            return relative_path

        except Exception as e:
            # DEFENSIVE: Evidence failure must NEVER crash the event pipeline
            log.error(
                "evidence_capture_exception",
                event_id=event.id,
                frame_idx=frame_idx,
                error=str(e),
                exc_info=True,
            )
            return None

    @classmethod
    def resolve_evidence_path(cls, evidence_path: str | None, org_id: str) -> Path | None:
        """
        Validate and resolve an evidence path safely for a specific tenant.
        Prevents directory traversal and confirms file existence.
        """
        if not evidence_path:
            return None

        base_dir = cls.get_storage_base_dir()
        file_path = (base_dir / evidence_path).resolve()

        # Security check: must reside within base_dir / org_id
        expected_tenant_dir = (base_dir / org_id).resolve()
        if not file_path.is_relative_to(expected_tenant_dir):
            log.warning("evidence_access_traversal_denied", evidence_path=evidence_path, org_id=org_id)
            return None

        if not file_path.is_file():
            return None

        return file_path
