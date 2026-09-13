"""
SafeVision AI — Event Engine

Implements the temporal accumulation layer between the Phase 5 Safety Rule Engine
and the PostgreSQL database. Manages the full violation lifecycle:

    ACCUMULATING → ACTIVE → COOLDOWN → CLEARED

State machine:
- ACCUMULATING: Violation detected but frame_count < min_persistence_frames.
  No event created yet. If violation clears, counter resets to 0.
- ACTIVE: frame_count reached min_persistence_frames. Exactly one Safety Event
  is created in the DB. All subsequent frames with the same violation are
  SUPPRESSED (no duplicate events).
- COOLDOWN: Violation clears while ACTIVE. State is retained for cooldown_seconds.
  If the same violation returns during cooldown → back to ACTIVE (same event_id,
  no new event). If cooldown expires without recurrence → CLEARED.
- CLEARED: State is deleted. Next qualifying violation starts a fresh cycle.

Parameters read from safety_rules.parameters:
- min_persistence_frames (default: 3)
- cooldown_seconds (default: 60)

Phase boundary:
  This engine is called per-frame by CVPipeline.process_frame().
  It does NOT manage camera streams or background workers (Phase 7).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum

import structlog
from sqlalchemy.orm import Session

from app.models.event import Event, EventType
from app.schemas.detection import RuleEvaluationResult, RuleViolation

log = structlog.get_logger()


class ViolationState(str, Enum):
    """Violation lifecycle state."""
    ACCUMULATING = "accumulating"
    ACTIVE = "active"
    COOLDOWN = "cooldown"


class ViolationTracker:
    """
    Tracks the temporal state of a single violation instance.

    Keyed by (camera_id, track_id, violation_type).
    """

    def __init__(self) -> None:
        self.state: ViolationState = ViolationState.ACCUMULATING
        self.frame_count: int = 0
        self.first_seen_at: datetime = datetime.now(timezone.utc)
        self.last_seen_at: datetime = datetime.now(timezone.utc)
        self.event_id: str | None = None  # DB event ID (set on promotion to ACTIVE)
        self.cooldown_until: datetime | None = None
        self.last_violation: RuleViolation | None = None  # Most recent violation details
        self.last_event_frame: int | None = None  # Frame index of last created event

    def __repr__(self) -> str:
        return (
            f"<ViolationTracker(state={self.state.value}, frames={self.frame_count}, "
            f"event_id={self.event_id}, last_event_frame={self.last_event_frame})>"
        )


# Map rule_type string → EventType enum
_RULE_TYPE_TO_EVENT_TYPE: dict[str, EventType] = {
    "ppe_violation": EventType.PPE_DETECTION,
    "exclusion_zone": EventType.ZONE_INTRUSION,
    "fire_smoke": EventType.FIRE_SMOKE,
}


class EventEngine:
    """
    Temporal event accumulation and duplicate suppression engine.

    Maintains in-memory violation state per (camera_id, track_id, violation_type).
    Persists Safety Events to PostgreSQL when violations are promoted.
    """

    def __init__(self) -> None:
        # State map: (camera_id, track_id, violation_type) → ViolationTracker
        self._state: dict[tuple[str, int | str | None, str], ViolationTracker] = {}
        self._frame_counter: int = 0

    def _make_key(
        self, camera_id: str, track_id: int | str | None, violation_type: str,
    ) -> tuple[str, int | str | None, str]:
        """
        Create the state key for a violation instance.
        For Fire and Smoke detections, a single shared key is used per camera
        so they share one common accumulation and re-trigger suppression window.
        """
        if violation_type == "fire_smoke":
            return (camera_id, "shared_fire_smoke", "fire_smoke")
        return (camera_id, track_id, violation_type)

    def _get_rule_parameters(
        self, violation: RuleViolation, rules: list | None = None,
    ) -> tuple[int, int, int]:
        """
        Extract (min_persistence_frames, cooldown_seconds, frame_gap) for a specific violation.

        Default semantics:
        - fire_smoke: min_persistence_frames=2, cooldown_seconds=60, frame_gap=15
        - other rules: min_persistence_frames=3, cooldown_seconds=60, frame_gap=0
        """
        is_fire_smoke = violation.rule_type == "fire_smoke"
        min_persistence = 2 if is_fire_smoke else 3
        cooldown = 60
        frame_gap = 15 if is_fire_smoke else 0

        if rules:
            for rule in rules:
                r_type = getattr(rule, "rule_type", None)
                r_type_val = r_type.value if hasattr(r_type, "value") else str(r_type)
                r_id = getattr(rule, "id", None)

                # Match by rule_id or rule_type
                if (violation.rule_id and r_id == violation.rule_id) or r_type_val == violation.rule_type:
                    params = getattr(rule, "parameters", {}) or {}
                    if "min_persistence_frames" in params:
                        min_persistence = int(params["min_persistence_frames"])
                    if "cooldown_seconds" in params:
                        cooldown = int(params["cooldown_seconds"])
                    if "frame_gap" in params:
                        frame_gap = int(params["frame_gap"])
                    break

        return min_persistence, cooldown, frame_gap

    def _get_parameters(
        self, rules: list | None = None,
    ) -> tuple[int, int]:
        """
        Legacy fallback: Extract min_persistence_frames and cooldown_seconds from rules.
        """
        min_persistence = 3
        cooldown = 60

        if rules:
            for rule in rules:
                params = getattr(rule, "parameters", {}) or {}
                if "min_persistence_frames" in params:
                    min_persistence = int(params["min_persistence_frames"])
                if "cooldown_seconds" in params:
                    cooldown = int(params["cooldown_seconds"])
                if "min_persistence_frames" in params or "cooldown_seconds" in params:
                    break

        return min_persistence, cooldown

    def process_frame(
        self,
        evaluation: RuleEvaluationResult,
        org_id: str,
        db: Session,
        rules: list | None = None,
        now: datetime | None = None,
        frame_idx: int | None = None,
    ) -> list[Event]:
        """
        Process a single frame's rule evaluation results.

        Steps:
        1. For each unique violation key in the evaluation, update or create a ViolationTracker.
        2. Deduplicate multi-box fire/smoke detections within the same frame to avoid false accumulation.
        3. Promote ACCUMULATING → ACTIVE when frame_count >= min_persistence_frames.
        4. When frame_gap > 0 is configured, enforce re-trigger interval between events.
        5. Persist new Safety Events to the database.
        6. For violations NOT present in this frame, handle state transitions
           (ACTIVE → COOLDOWN, COOLDOWN → CLEARED).
        """
        if now is None:
            now = datetime.now(timezone.utc)

        if frame_idx is None:
            current_frame = self._frame_counter
            self._frame_counter += 1
        else:
            current_frame = frame_idx
            self._frame_counter = frame_idx + 1

        # Deduplicate violations in this frame by key, picking highest confidence detection
        violations_by_key: dict[tuple[str, int | str | None, str], RuleViolation] = {}
        for violation in evaluation.violations:
            key = self._make_key(
                evaluation.camera_id,
                violation.track_id,
                violation.rule_type,
            )
            if key not in violations_by_key:
                violations_by_key[key] = violation
            else:
                prev_conf = float(violations_by_key[key].details.get("confidence", 0.0) or 0.0)
                curr_conf = float(violation.details.get("confidence", 0.0) or 0.0)
                if curr_conf > prev_conf:
                    violations_by_key[key] = violation

        active_keys_this_frame: set[tuple[str, int | str | None, str]] = set(violations_by_key.keys())
        new_events: list[Event] = []

        # Step 1: Process each unique violation key in the current frame
        for key, violation in violations_by_key.items():
            min_persistence, cooldown_seconds, frame_gap = self._get_rule_parameters(violation, rules)

            if key not in self._state:
                # New violation — start ACCUMULATING
                tracker = ViolationTracker()
                tracker.first_seen_at = now
                tracker.last_seen_at = now
                tracker.frame_count = 1
                tracker.last_violation = violation
                self._state[key] = tracker

                # Check for immediate promotion (min_persistence_frames == 1)
                if tracker.frame_count >= min_persistence:
                    tracker.state = ViolationState.ACTIVE
                    event = self._create_event(
                        violation=violation,
                        camera_id=evaluation.camera_id,
                        org_id=org_id,
                        now=now,
                        db=db,
                    )
                    tracker.event_id = event.id
                    tracker.last_event_frame = current_frame
                    new_events.append(event)

                    log.info(
                        "violation_promoted",
                        camera_id=evaluation.camera_id,
                        track_id=violation.track_id,
                        rule_type=violation.rule_type,
                        event_id=event.id,
                        frame_count=tracker.frame_count,
                        frame_idx=current_frame,
                    )
                else:
                    log.debug(
                        "violation_accumulating",
                        camera_id=evaluation.camera_id,
                        track_id=violation.track_id,
                        rule_type=violation.rule_type,
                        frame_count=1,
                        frame_idx=current_frame,
                    )

            else:
                tracker = self._state[key]
                tracker.last_seen_at = now
                tracker.last_violation = violation

                if tracker.state == ViolationState.ACCUMULATING:
                    tracker.frame_count += 1

                    if tracker.frame_count >= min_persistence:
                        # Check frame gap if a previous event was recorded on this key
                        if frame_gap > 0 and tracker.last_event_frame is not None and (current_frame - tracker.last_event_frame) < frame_gap:
                            log.debug(
                                "violation_frame_gap_suppressed",
                                camera_id=evaluation.camera_id,
                                rule_type=violation.rule_type,
                                current_frame=current_frame,
                                last_event_frame=tracker.last_event_frame,
                                frame_gap=frame_gap,
                            )
                        else:
                            # Promote to ACTIVE — create Safety Event
                            tracker.state = ViolationState.ACTIVE
                            event = self._create_event(
                                violation=violation,
                                camera_id=evaluation.camera_id,
                                org_id=org_id,
                                now=now,
                                db=db,
                            )
                            tracker.event_id = event.id
                            tracker.last_event_frame = current_frame
                            new_events.append(event)

                            log.info(
                                "violation_promoted",
                                camera_id=evaluation.camera_id,
                                track_id=violation.track_id,
                                rule_type=violation.rule_type,
                                event_id=event.id,
                                frame_count=tracker.frame_count,
                                frame_idx=current_frame,
                            )

                elif tracker.state == ViolationState.ACTIVE:
                    tracker.frame_count += 1
                    if frame_gap > 0:
                        # Re-trigger interval check for ongoing incidents
                        if tracker.last_event_frame is not None and (current_frame - tracker.last_event_frame) >= frame_gap:
                            # Frame gap has elapsed AND persistence is satisfied (frame_count >= min_persistence)
                            event = self._create_event(
                                violation=violation,
                                camera_id=evaluation.camera_id,
                                org_id=org_id,
                                now=now,
                                db=db,
                            )
                            tracker.event_id = event.id
                            tracker.last_event_frame = current_frame
                            new_events.append(event)

                            log.info(
                                "violation_frame_gap_retriggered",
                                camera_id=evaluation.camera_id,
                                rule_type=violation.rule_type,
                                event_id=event.id,
                                frame_count=tracker.frame_count,
                                current_frame=current_frame,
                            )
                        else:
                            # Suppressed within frame gap
                            log.debug(
                                "violation_frame_gap_suppressed",
                                camera_id=evaluation.camera_id,
                                rule_type=violation.rule_type,
                                event_id=tracker.event_id,
                                current_frame=current_frame,
                                last_event_frame=tracker.last_event_frame,
                                frame_gap=frame_gap,
                            )
                    else:
                        # Standard duplicate suppression (e.g. PPE)
                        log.debug(
                            "violation_suppressed",
                            camera_id=evaluation.camera_id,
                            track_id=violation.track_id,
                            rule_type=violation.rule_type,
                            event_id=tracker.event_id,
                        )

                elif tracker.state == ViolationState.COOLDOWN:
                    tracker.frame_count += 1
                    if frame_gap > 0:
                        # Re-evaluate returned violation with persistence and frame_gap
                        if tracker.frame_count >= min_persistence:
                            if tracker.last_event_frame is None or (current_frame - tracker.last_event_frame) >= frame_gap:
                                tracker.state = ViolationState.ACTIVE
                                tracker.cooldown_until = None
                                event = self._create_event(
                                    violation=violation,
                                    camera_id=evaluation.camera_id,
                                    org_id=org_id,
                                    now=now,
                                    db=db,
                                )
                                tracker.event_id = event.id
                                tracker.last_event_frame = current_frame
                                new_events.append(event)

                                log.info(
                                    "violation_retriggered_after_cooldown",
                                    camera_id=evaluation.camera_id,
                                    rule_type=violation.rule_type,
                                    event_id=event.id,
                                    current_frame=current_frame,
                                )
                            else:
                                tracker.state = ViolationState.ACTIVE
                                tracker.cooldown_until = None
                                log.debug(
                                    "violation_frame_gap_suppressed_after_cooldown",
                                    camera_id=evaluation.camera_id,
                                    rule_type=violation.rule_type,
                                    current_frame=current_frame,
                                    last_event_frame=tracker.last_event_frame,
                                    frame_gap=frame_gap,
                                )
                        else:
                            # Requires accumulation to meet persistence
                            tracker.state = ViolationState.ACCUMULATING
                            tracker.cooldown_until = None
                            log.debug(
                                "violation_reaccumulating_after_cooldown",
                                camera_id=evaluation.camera_id,
                                rule_type=violation.rule_type,
                                frame_count=tracker.frame_count,
                            )
                    else:
                        # Standard cooldown return without frame_gap
                        tracker.state = ViolationState.ACTIVE
                        tracker.cooldown_until = None
                        log.info(
                            "violation_reactivated_during_cooldown",
                            camera_id=evaluation.camera_id,
                            track_id=violation.track_id,
                            rule_type=violation.rule_type,
                            event_id=tracker.event_id,
                        )

        # Step 2: Handle violations NOT present in this frame
        keys_to_delete: list[tuple[str, int | str | None, str]] = []

        for key, tracker in self._state.items():
            if key[0] != evaluation.camera_id:
                continue

            if key not in active_keys_this_frame:
                cooldown_seconds = 60
                if tracker.last_violation:
                    _, cooldown_seconds, _ = self._get_rule_parameters(tracker.last_violation, rules)

                if tracker.state == ViolationState.ACCUMULATING:
                    # Condition didn't persist long enough — reset
                    keys_to_delete.append(key)
                    log.debug(
                        "violation_accumulation_reset",
                        camera_id=key[0],
                        track_id=key[1],
                        rule_type=key[2],
                        frame_count=tracker.frame_count,
                    )

                elif tracker.state == ViolationState.ACTIVE:
                    # Violation cleared — enter cooldown
                    tracker.state = ViolationState.COOLDOWN
                    tracker.cooldown_until = now + timedelta(seconds=cooldown_seconds)
                    tracker.frame_count = 0

                    log.info(
                        "violation_entering_cooldown",
                        camera_id=key[0],
                        track_id=key[1],
                        rule_type=key[2],
                        event_id=tracker.event_id,
                        cooldown_until=str(tracker.cooldown_until),
                    )

                elif tracker.state == ViolationState.COOLDOWN:
                    # Check if cooldown has expired
                    if tracker.cooldown_until and now >= tracker.cooldown_until:
                        keys_to_delete.append(key)

                        log.info(
                            "violation_cooldown_expired",
                            camera_id=key[0],
                            track_id=key[1],
                            rule_type=key[2],
                            event_id=tracker.event_id,
                        )

        # Step 3: Clean up cleared state
        for key in keys_to_delete:
            del self._state[key]

        # Commit new events to DB
        if new_events:
            db.commit()

        return new_events

    def _create_event(
        self,
        violation: RuleViolation,
        camera_id: str,
        org_id: str,
        now: datetime,
        db: Session,
    ) -> Event:
        """
        Create a Safety Event row in PostgreSQL.

        Maps the RuleViolation to an Event ORM instance and adds to session.
        """
        # Map rule type to event type
        event_type = _RULE_TYPE_TO_EVENT_TYPE.get(
            violation.rule_type, EventType.PPE_DETECTION,
        )

        # Build detection_data JSONB from violation details
        detection_data = {
            "rule_id": violation.rule_id,
            "rule_name": violation.rule_name,
            "rule_type": violation.rule_type,
            "severity": violation.severity,
            "track_id": violation.track_id,
            "person_bbox": violation.person_bbox,
            "person_centroid": list(violation.person_centroid) if violation.person_centroid else None,
            "missing_ppe": violation.missing_ppe,
            "detected_ppe": violation.detected_ppe,
            "message": violation.message,
            "details": violation.details,
            "zone_id": violation.zone_id,
        }

        # Extract primary confidence from violation details
        confidence = violation.details.get("person_confidence")

        event = Event(
            id=str(uuid.uuid4()),
            camera_id=camera_id,
            org_id=org_id,
            event_type=event_type,
            timestamp=now,
            confidence=confidence,
            detection_data=detection_data,
        )

        db.add(event)
        log.info(
            "safety_event_created",
            event_id=event.id,
            event_type=event_type.value,
            camera_id=camera_id,
            org_id=org_id,
            track_id=violation.track_id,
            rule_type=violation.rule_type,
        )

        return event

    @property
    def active_violations(self) -> int:
        """Count of currently tracked violations (all states)."""
        return len(self._state)

    def get_state_summary(self) -> dict[str, int]:
        """Summary of violation states for monitoring."""
        summary: dict[str, int] = {
            ViolationState.ACCUMULATING.value: 0,
            ViolationState.ACTIVE.value: 0,
            ViolationState.COOLDOWN.value: 0,
        }
        for tracker in self._state.values():
            summary[tracker.state.value] += 1
        return summary

    def clear_camera_state(self, camera_id: str) -> int:
        """
        Clear all violation state for a camera.

        Call when a camera stream is stopped or restarted.
        Returns the number of cleared entries.
        """
        keys_to_delete = [k for k in self._state if k[0] == camera_id]
        for key in keys_to_delete:
            del self._state[key]
        return len(keys_to_delete)

    def clear_all(self) -> None:
        """Clear all state. Use for testing or full reset."""
        self._state.clear()
        self._frame_counter = 0
