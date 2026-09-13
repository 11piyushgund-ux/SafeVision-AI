"""
SafeVision AI — Shared YOLO26 Inference Service

Singleton service that loads both trained YOLO26 models (PPE + fire/smoke) once
and provides tracked inference via BoT-SORT.

Key design decisions:
- Models are lazy-loaded on first inference call, not at import time.
- BoT-SORT tracker is explicitly configured via botsort.yaml (not default).
- Runtime NMS-free assertion: verifies model.model.end2end == True on load.
- track_id is a temporary per-session integer — never persistent worker identity.
- Thread-safe singleton via module-level instance.
- No NMS/post-processing: output is the final detection set from end-to-end models.

Phase boundary:
  This service provides model loading and per-frame inference.
  It does NOT manage camera streams, frame loops, or background workers (Phase 7).
"""

from __future__ import annotations

import threading
from enum import Enum
from pathlib import Path

import numpy as np
import structlog

from app.config import get_settings

log = structlog.get_logger()

# Path to BoT-SORT tracker config relative to this file
_BOTSORT_CONFIG = str(Path(__file__).parent.parent / "cv" / "botsort.yaml")


class ModelType(str, Enum):
    """Available trained YOLO26 models."""
    PPE = "ppe"
    FIRE_SMOKE = "fire_smoke"


class InferenceService:
    """
    Shared, thread-safe YOLO26 inference service.

    Loads models lazily on first call. Provides tracked inference
    using explicit BoT-SORT configuration.
    """

    def __init__(self) -> None:
        self._models: dict[ModelType, object] = {}
        self._lock = threading.Lock()
        self._loaded = False

    def _get_model_path(self, model_type: ModelType) -> str:
        """Resolve model weight file path from configuration."""
        settings = get_settings()
        if model_type == ModelType.PPE:
            return settings.cv_ppe_model_path
        elif model_type == ModelType.FIRE_SMOKE:
            return settings.cv_fire_smoke_model_path
        else:
            raise ValueError(f"Unknown model type: {model_type}")

    def _load_model(self, model_type: ModelType) -> object:
        """
        Load a YOLO26 model and verify it is NMS-free (end-to-end).

        Raises RuntimeError if the model is not end-to-end, which would mean
        the output requires additional NMS post-processing — a contract violation.
        """
        # Import here to allow mocking in tests without requiring ultralytics
        from ultralytics import YOLO

        model_path = self._get_model_path(model_type)
        resolved_path = Path(model_path)

        # Resolve relative paths from backend directory
        if not resolved_path.is_absolute():
            resolved_path = Path(get_settings().cv_ppe_model_path).parent.parent.parent / model_path
            # Try relative to current working directory
            if not resolved_path.exists():
                resolved_path = Path.cwd() / model_path
            # Try relative to backend directory
            if not resolved_path.exists():
                resolved_path = Path(__file__).parent.parent.parent / model_path

        log.info(
            "loading_yolo_model",
            model_type=model_type.value,
            path=str(resolved_path),
        )

        model = YOLO(str(resolved_path))

        # Runtime NMS-free verification
        # Both SafeVision models must be end-to-end (NMS-free)
        is_end2end = getattr(model.model, "end2end", False)
        if not is_end2end:
            raise RuntimeError(
                f"Model {model_type.value} at {resolved_path} is NOT end-to-end NMS-free. "
                f"model.model.end2end = {is_end2end}. "
                f"SafeVision requires NMS-free models — do not add post-processing NMS."
            )

        log.info(
            "model_loaded",
            model_type=model_type.value,
            end2end=True,
            classes=model.names,
            num_classes=len(model.names),
        )

        return model

    def get_model(self, model_type: ModelType) -> object:
        """Get or lazily load a model. Thread-safe."""
        if model_type not in self._models:
            with self._lock:
                # Double-check after acquiring lock
                if model_type not in self._models:
                    self._models[model_type] = self._load_model(model_type)
        return self._models[model_type]

    def track(
        self,
        frame: np.ndarray,
        model_type: ModelType = ModelType.PPE,
        conf: float = 0.1,
        verbose: bool = False,
    ) -> object:
        """
        Run tracked inference on a single frame using BoT-SORT.

        Args:
            frame: BGR numpy array (standard OpenCV format)
            model_type: Which model to use (PPE or FIRE_SMOKE)
            conf: Minimum confidence threshold for detection (NOT NMS — this is
                  the model's internal confidence filter only). Set low (0.1)
                  to let the rule engine apply its own configurable threshold.
            verbose: Whether to print Ultralytics inference logs

        Returns:
            Ultralytics Results object with boxes.id populated from BoT-SORT.

        Raises:
            RuntimeError: If tracker fails to produce track IDs.
        """
        model = self.get_model(model_type)

        results = model.track(
            frame,
            persist=True,
            tracker=_BOTSORT_CONFIG,
            conf=conf,
            verbose=verbose,
        )

        # Verify tracker produced IDs
        if results and len(results) > 0 and results[0].boxes is not None:
            boxes = results[0].boxes
            if len(boxes) > 0 and boxes.id is None:
                log.warning(
                    "tracker_no_ids",
                    model_type=model_type.value,
                    num_boxes=len(boxes),
                    msg="BoT-SORT did not assign track IDs — detections will have track_id=None",
                )

        return results

    def predict(
        self,
        frame: np.ndarray,
        model_type: ModelType = ModelType.PPE,
        conf: float = 0.1,
        verbose: bool = False,
    ) -> object:
        """
        Run inference WITHOUT tracking (for single-frame analysis).

        Use track() for continuous camera streams where track_id is needed.
        """
        model = self.get_model(model_type)
        return model.predict(frame, conf=conf, verbose=verbose)

    def reset_tracker(self, model_type: ModelType) -> None:
        """
        Reset the BoT-SORT tracker state for a model.

        Call this when a camera stream is restarted or re-initialized.
        After reset, track IDs will restart from 1.
        """
        if model_type in self._models:
            model = self._models[model_type]
            if hasattr(model, "predictor") and model.predictor is not None:
                if hasattr(model.predictor, "trackers"):
                    model.predictor.trackers = []
                    log.info("tracker_reset", model_type=model_type.value)

    @property
    def is_loaded(self) -> bool:
        """Check if any models are loaded."""
        return len(self._models) > 0

    @property
    def loaded_models(self) -> list[str]:
        """List currently loaded model types."""
        return [mt.value for mt in self._models]


# Module-level singleton — import and use directly
_inference_service: InferenceService | None = None
_singleton_lock = threading.Lock()


def get_inference_service() -> InferenceService:
    """Get the singleton InferenceService instance."""
    global _inference_service
    if _inference_service is None:
        with _singleton_lock:
            if _inference_service is None:
                _inference_service = InferenceService()
    return _inference_service
