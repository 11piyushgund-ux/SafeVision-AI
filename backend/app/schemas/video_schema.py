"""
SafeVision AI — Video Ingestion & Streaming Schemas (Phase 11)

Defines data contracts for:
- Video file upload responses
- WebSocket authentication and control messages
- Frame-by-frame inference payloads streamed to the browser
"""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class VideoUploadResponse(BaseModel):
    """Response returned when a video file is successfully uploaded for monitoring."""
    session_id: str = Field(..., description="Unique video monitoring session ID")
    filename: str = Field(..., description="Sanitized original filename")
    camera_id: str = Field(..., description="Associated camera ID")
    zone_id: str | None = Field(None, description="Associated zone ID")
    total_frames: int = Field(..., ge=0, description="Total frame count in video")
    source_fps: float = Field(..., ge=0.0, description="Source video container FPS")
    duration_seconds: float = Field(..., ge=0.0, description="Duration in seconds")
    width: int = Field(..., ge=1, description="Frame pixel width")
    height: int = Field(..., ge=1, description="Frame pixel height")


class WSAuthMessage(BaseModel):
    """Initial client authentication frame sent over WebSocket."""
    type: Literal["auth"] = "auth"
    token: str = Field(..., description="JWT Bearer token")


class WSControlMessage(BaseModel):
    """Playback control message sent by client over WebSocket."""
    action: Literal["start", "pause", "resume", "stop"] = "start"


class WSDetectionItem(BaseModel):
    """Single detection with compliance and tracking status."""
    class_name: str
    confidence: float
    bbox: list[float]  # [x1, y1, x2, y2] in original frame pixels
    track_id: int | str | None = None
    is_compliant: bool = True
    missing_ppe: list[str] = Field(default_factory=list)
    detected_ppe: list[str] = Field(default_factory=list)


class WSZoneViolation(BaseModel):
    """Zone intrusion violation summary for the frame."""
    track_id: int | str | None = None
    rule_name: str
    rule_type: str
    severity: str
    message: str


class WSEventSummary(BaseModel):
    """Summary of a new Safety Event created during frame processing."""
    event_id: str
    event_type: str
    severity: str
    message: str
    timestamp: str
    risk_score: float
    risk_level: str


class WSFrameStats(BaseModel):
    """Real-time performance and detection metrics."""
    source_fps: float
    inference_fps: float
    persons_detected: int
    active_violations: int
    total_events_generated: int


class WSFramePayload(BaseModel):
    """Synchronized frame packet streamed to frontend over WebSocket."""
    type: Literal["frame"] = "frame"
    frame_idx: int
    total_frames: int
    timestamp_ms: int
    image: str  # Base64 encoded JPEG: "data:image/jpeg;base64,..."
    detections: list[WSDetectionItem] = Field(default_factory=list)
    zone_polygon: list[list[float]] | None = None  # Normalized [[x, y], ...]
    zone_violations: list[WSZoneViolation] = Field(default_factory=list)
    new_events: list[WSEventSummary] = Field(default_factory=list)
    stats: WSFrameStats

    model_config = ConfigDict(populate_by_name=True)


class WSAuthOkMessage(BaseModel):
    """Confirmation sent to client after successful WebSocket authentication."""
    type: Literal["auth_ok"] = "auth_ok"
    user_id: str
    user_name: str
    org_id: str


class WSErrorMessage(BaseModel):
    """Error frame sent to client."""
    type: Literal["error", "auth_error"] = "error"
    message: str


class WSCompletedMessage(BaseModel):
    """Sent when video stream processing reaches the final frame."""
    type: Literal["completed"] = "completed"
    total_frames_processed: int
    total_events_generated: int
