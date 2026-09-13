"""
SafeVision AI — Detection Adapter

Converts Ultralytics YOLO26 Results objects into Phase 5 DetectionPayload
format that the SafetyRuleEngine expects.

Contract guarantees:
- bbox coordinates are preserved as-is from Ultralytics (original frame coords)
- track_id is preserved as-is (integer from BoT-SORT, or None if untracked)
- class_name uses exact model names (helmet, gloves, goggles, safety_shoes,
  safety_vest, person, fire, smoke)
- No NMS, no confidence filtering, no duplicate removal — raw model output
  is passed through. Filtering is the rule engine's job.
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog

from app.schemas.detection import DetectionItem, DetectionPayload

log = structlog.get_logger()


class DetectionAdapter:
    """
    Converts Ultralytics Results → Phase 5 DetectionPayload.

    Stateless adapter — each call is independent.
    """

    @staticmethod
    def adapt(
        results: object,
        camera_id: str,
        model_names: dict[int, str],
        timestamp: datetime | None = None,
    ) -> DetectionPayload:
        """
        Convert a single Ultralytics Results object to DetectionPayload.

        Args:
            results: Ultralytics Results object (from model.track() or model.predict())
            camera_id: Source camera identifier
            model_names: Class index → class name mapping (model.names)
            timestamp: Frame capture timestamp (defaults to now if not provided)

        Returns:
            DetectionPayload with all detections from the frame.
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        detections: list[DetectionItem] = []

        if results is None:
            return DetectionPayload(
                camera_id=camera_id,
                timestamp=timestamp,
                detections=[],
            )

        # Handle list of results (Ultralytics returns list even for single frame)
        result = results[0] if isinstance(results, list) else results

        if result.boxes is None or len(result.boxes) == 0:
            return DetectionPayload(
                camera_id=camera_id,
                timestamp=timestamp,
                detections=[],
            )

        boxes = result.boxes

        # Extract tensors
        xyxy = boxes.xyxy  # [N, 4] — pixel coords in original frame dimensions
        confs = boxes.conf  # [N] — confidence scores
        cls_ids = boxes.cls  # [N] — class indices

        # Track IDs: populated by model.track(), None for model.predict()
        track_ids = boxes.id  # [N] tensor or None

        num_detections = len(xyxy)

        for i in range(num_detections):
            # Extract bbox — preserved as-is from Ultralytics
            bbox = [
                float(xyxy[i][0]),
                float(xyxy[i][1]),
                float(xyxy[i][2]),
                float(xyxy[i][3]),
            ]

            # Extract confidence — preserved as-is
            confidence = float(confs[i])

            # Map class index to class name using model.names
            cls_idx = int(cls_ids[i])
            class_name = model_names.get(cls_idx, f"unknown_{cls_idx}")

            # Extract track_id — integer from BoT-SORT, or None
            track_id = None
            if track_ids is not None:
                track_id = int(track_ids[i])

            detections.append(
                DetectionItem(
                    class_name=class_name,
                    confidence=confidence,
                    bbox=bbox,
                    track_id=track_id,
                )
            )

        log.debug(
            "adapted_detections",
            camera_id=camera_id,
            num_detections=num_detections,
            classes=[d.class_name for d in detections],
            track_ids=[d.track_id for d in detections],
        )

        return DetectionPayload(
            camera_id=camera_id,
            timestamp=timestamp,
            detections=detections,
        )

    @staticmethod
    def merge_payloads(
        *payloads: DetectionPayload,
    ) -> DetectionPayload:
        """
        Merge multiple DetectionPayloads (e.g. PPE + fire/smoke) into one.

        All payloads must share the same camera_id.
        Uses the earliest timestamp.
        """
        if not payloads:
            raise ValueError("At least one payload is required")

        camera_id = payloads[0].camera_id
        all_detections: list[DetectionItem] = []
        earliest_ts = payloads[0].timestamp

        for payload in payloads:
            if payload.camera_id != camera_id:
                raise ValueError(
                    f"Cannot merge payloads from different cameras: "
                    f"{camera_id} vs {payload.camera_id}"
                )
            all_detections.extend(payload.detections)
            if payload.timestamp and earliest_ts:
                if isinstance(payload.timestamp, datetime) and isinstance(earliest_ts, datetime):
                    if payload.timestamp < earliest_ts:
                        earliest_ts = payload.timestamp

        return DetectionPayload(
            camera_id=camera_id,
            timestamp=earliest_ts,
            detections=all_detections,
        )
