"""
SafeVision AI — Computer Vision Detection & Rule Evaluation Schemas

Defines contracts for:
- Frame-level detection payloads from CV pipelines
- Rule evaluation results and detected violations
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DetectionItem(BaseModel):
    """Single detection emitted by the computer vision model."""
    class_name: str = Field(..., alias="class", description="Detected class name (e.g. person, helmet, safety_vest)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence score")
    bbox: list[float] | None = Field(default=None, description="Bounding box [x1, y1, x2, y2]")
    track_id: int | str | None = Field(default=None, description="Tracker ID linking detections across frames")

    model_config = ConfigDict(populate_by_name=True)


class DetectionPayload(BaseModel):
    """Batch of detections for a given frame from a camera."""
    camera_id: str = Field(..., description="Source camera identifier")
    timestamp: datetime | str | None = Field(default=None, description="Frame capture timestamp")
    detections: list[DetectionItem] = Field(default_factory=list, description="List of detections in the frame")


class RuleViolation(BaseModel):
    """Specific violation detected during rule evaluation."""
    rule_id: str | None = None
    rule_name: str | None = None
    rule_type: str
    severity: str
    zone_id: str | None = None
    camera_id: str
    track_id: int | str | None = None
    person_bbox: list[float] | None = None
    person_centroid: tuple[float, float] | None = None
    missing_ppe: list[str] = Field(default_factory=list)
    detected_ppe: list[str] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)
    message: str


class RuleEvaluationResult(BaseModel):
    """Aggregate output from the Safety Rule Engine evaluating a frame payload."""
    camera_id: str
    violations: list[RuleViolation] = Field(default_factory=list)
    compliant_track_ids: list[int | str] = Field(default_factory=list)
    total_persons_detected: int = 0
    rules_evaluated_count: int = 0
