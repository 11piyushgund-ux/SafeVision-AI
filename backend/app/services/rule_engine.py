"""
SafeVision AI — Deterministic Safety Rule Engine

Evaluates computer vision detection payloads against organization/zone safety rules:
1. PPE Compliance: Compares detected PPE associated with a person against
   required PPE list (from rule parameters → zone fallback).
2. Restricted/Exclusion Zone Incursion: Computes person centroid and tests
   point-in-polygon against restricted zone boundaries.

PPE → Person Association Strategy (dual-mode):
  - PRIMARY: track_id-based grouping. BoT-SORT assigns the same track_id to
    a person and their associated PPE detections. This is the CV contract
    defined in deep-research-report.md (lines 232-238).
  - FALLBACK: Spatial bbox containment. When track_id is None (tracker loss,
    re-identification failure), PPE items are associated with the nearest
    person whose bounding box contains the PPE item's centroid. This is
    deterministic — no ML or network calls involved.

Zero hardcoded thresholds:
All confidence cutoffs and required PPE lists are read dynamically from
`safety_rules.parameters`.

Temporal parameters NOT implemented in Phase 5:
  min_persistence_frames, min_violation_duration_seconds, cooldown_seconds
These are configuration fields stored in safety_rules.parameters for use by
the Phase 6 Event Pipeline (frame-level temporal accumulation). Phase 5
evaluates single frames only.
"""

import structlog

from app.models.safety_rule import RuleSeverity, RuleStatus, RuleType
from app.models.zone import Zone, ZoneType
from app.schemas.detection import (
    DetectionItem,
    DetectionPayload,
    RuleEvaluationResult,
    RuleViolation,
)
from app.services.geometry import bbox_contains, calculate_centroid, point_in_polygon

log = structlog.get_logger()

# Phase 1 CV model class names for person detection
PERSON_CLASS_NAMES = {"person", "worker"}

# Phase 1 CV model PPE class names — canonical list
# Any detection with a class_name matching one of these (case-insensitive)
# is treated as a PPE item, not a person.
VALID_PPE_CLASSES = {"helmet", "gloves", "goggles", "safety_shoes", "safety_vest"}


class SafetyRuleEngine:
    """
    Deterministic safety rule evaluator for multi-tenant industrial monitoring.

    Phase 5 scope: single-frame evaluation only.
    Phase 6 scope: temporal accumulation (persistence, cooldown, duration).
    """

    @staticmethod
    def _associate_ppe_to_persons(
        detections: list[DetectionItem],
        ppe_conf_threshold: float,
        person_conf_threshold: float,
    ) -> tuple[dict[int | str, list[DetectionItem]], dict[int | str, set[str]]]:
        """
        Associate PPE detections with persons using dual-mode strategy:

        1. PRIMARY (track_id): If both person and PPE share the same track_id,
           they are grouped directly. This is the BoT-SORT contract.

        2. FALLBACK (spatial bbox containment): If a PPE detection has
           track_id=None, its bbox centroid is tested against all tracked person
           bounding boxes. The PPE is assigned to the first person whose bbox
           contains the PPE centroid. If no person contains it, the PPE is
           discarded (no phantom associations).

        Returns:
            (persons_by_track, ppe_by_track) — maps of track_id to person
            detections and PPE class sets respectively.
        """
        # Step 1: Extract tracked persons
        persons_by_track: dict[int | str, list[DetectionItem]] = {}
        ppe_by_track: dict[int | str, set[str]] = {}
        untracked_ppe: list[DetectionItem] = []

        for det in detections:
            class_lower = det.class_name.lower().strip()

            if class_lower in PERSON_CLASS_NAMES:
                if det.confidence >= person_conf_threshold and det.track_id is not None:
                    if det.track_id not in persons_by_track:
                        persons_by_track[det.track_id] = []
                    persons_by_track[det.track_id].append(det)
                    # Ensure ppe_by_track entry exists even if no PPE found
                    if det.track_id not in ppe_by_track:
                        ppe_by_track[det.track_id] = set()
            elif class_lower in VALID_PPE_CLASSES:
                if det.confidence >= ppe_conf_threshold:
                    if det.track_id is not None:
                        # PRIMARY: track_id-based association
                        if det.track_id not in ppe_by_track:
                            ppe_by_track[det.track_id] = set()
                        ppe_by_track[det.track_id].add(class_lower)
                    else:
                        # FALLBACK: will try spatial association
                        untracked_ppe.append(det)
            # else: unknown class — silently ignored (not person, not known PPE)

        # Step 2: Spatial fallback for untracked PPE
        if untracked_ppe and persons_by_track:
            for ppe_det in untracked_ppe:
                if not ppe_det.bbox or len(ppe_det.bbox) < 4:
                    continue
                ppe_class = ppe_det.class_name.lower().strip()

                # Find the person whose bbox contains the PPE item centroid
                for track_id, person_dets in persons_by_track.items():
                    for person_det in person_dets:
                        if person_det.bbox and bbox_contains(person_det.bbox, ppe_det.bbox):
                            ppe_by_track[track_id].add(ppe_class)
                            break
                    else:
                        continue
                    break  # Associated — stop searching persons

        return persons_by_track, ppe_by_track

    @staticmethod
    def evaluate_ppe(
        payload: DetectionPayload,
        required_ppe: list[str],
        parameters: dict | None = None,
        rule_id: str | None = None,
        rule_name: str | None = None,
        severity: str = RuleSeverity.HIGH.value,
        zone_id: str | None = None,
    ) -> list[RuleViolation]:
        """
        Evaluate PPE compliance for all tracked persons in the detection payload.

        For each person identified by track_id:
        1. Find all PPE detections matching that track_id whose confidence meets
           or exceeds `confidence_threshold` (from parameters).
        2. For untracked PPE items, apply spatial bbox containment fallback.
        3. Identify which items in `required_ppe` are missing.
        4. If any required items are missing, generate a RuleViolation.
        """
        params = parameters or {}
        # Read configurable confidence thresholds — never hardcoded
        ppe_conf_threshold = float(params.get("confidence_threshold", 0.5))
        person_conf_threshold = float(params.get("person_confidence_threshold", ppe_conf_threshold))

        # Effective required PPE: rule parameter overrides zone if specified
        effective_required_ppe = params.get("required_ppe") or required_ppe or []
        if not effective_required_ppe:
            return []

        # Standardize required PPE names to lowercase
        req_ppe_set = {str(item).lower().strip() for item in effective_required_ppe}

        # Associate PPE to persons using dual-mode strategy
        persons_by_track, ppe_by_track = SafetyRuleEngine._associate_ppe_to_persons(
            detections=payload.detections,
            ppe_conf_threshold=ppe_conf_threshold,
            person_conf_threshold=person_conf_threshold,
        )

        violations: list[RuleViolation] = []

        # Check compliance for each tracked person
        for track_id, person_dets in persons_by_track.items():
            detected_items = ppe_by_track.get(track_id, set())
            missing_items = sorted(list(req_ppe_set - detected_items))

            if missing_items:
                primary_person = person_dets[0]
                centroid = None
                if primary_person.bbox:
                    try:
                        centroid = calculate_centroid(primary_person.bbox)
                    except ValueError:
                        centroid = None

                msg_template = params.get(
                    "recommendation_template",
                    "Person track {track_id} missing required PPE: {missing_ppe}",
                )
                message = msg_template.format(
                    track_id=track_id,
                    missing_ppe=", ".join(missing_items),
                    zone_id=zone_id or "unspecified",
                )

                violations.append(
                    RuleViolation(
                        rule_id=rule_id,
                        rule_name=rule_name or "PPE Compliance Violation",
                        rule_type=RuleType.PPE_VIOLATION.value,
                        severity=severity,
                        zone_id=zone_id,
                        camera_id=payload.camera_id,
                        track_id=track_id,
                        person_bbox=primary_person.bbox,
                        person_centroid=centroid,
                        missing_ppe=missing_items,
                        detected_ppe=sorted(list(detected_items)),
                        details={
                            "required_ppe": sorted(list(req_ppe_set)),
                            "missing_ppe": missing_items,
                            "detected_ppe": sorted(list(detected_items)),
                            "confidence_threshold": ppe_conf_threshold,
                            "person_confidence": primary_person.confidence,
                        },
                        message=message,
                    )
                )

        return violations

    @staticmethod
    def evaluate_restricted_zone(
        payload: DetectionPayload,
        polygon: list[list[float]],
        parameters: dict | None = None,
        rule_id: str | None = None,
        rule_name: str | None = None,
        severity: str = RuleSeverity.CRITICAL.value,
        zone_id: str | None = None,
    ) -> list[RuleViolation]:
        """
        Evaluate restricted/exclusion zone incursion.

        For each person in the detection payload:
        1. Calculate the centroid of the bounding box: ((x1 + x2)/2, (y1 + y2)/2)
        2. Perform ray-casting point-in-polygon test against the zone polygon.
        3. If centroid falls inside the restricted polygon, generate a RuleViolation.
        """
        if not polygon or len(polygon) < 3:
            return []

        params = parameters or {}
        person_conf_threshold = float(params.get("confidence_threshold", 0.5))

        violations: list[RuleViolation] = []

        for det in payload.detections:
            class_lower = det.class_name.lower().strip()
            if class_lower not in PERSON_CLASS_NAMES:
                continue

            if det.confidence < person_conf_threshold:
                continue

            if not det.bbox or len(det.bbox) < 4:
                continue

            try:
                centroid = calculate_centroid(det.bbox)
            except ValueError:
                continue

            is_inside = point_in_polygon(centroid, polygon)

            if is_inside:
                msg_template = params.get(
                    "recommendation_template",
                    "Unauthorized person track {track_id} detected inside restricted zone",
                )
                message = msg_template.format(
                    track_id=det.track_id or "untracked",
                    zone_id=zone_id or "unspecified",
                )

                violations.append(
                    RuleViolation(
                        rule_id=rule_id,
                        rule_name=rule_name or "Restricted Zone Incursion",
                        rule_type=RuleType.EXCLUSION_ZONE.value,
                        severity=severity,
                        zone_id=zone_id,
                        camera_id=payload.camera_id,
                        track_id=det.track_id,
                        person_bbox=det.bbox,
                        person_centroid=centroid,
                        missing_ppe=[],
                        detected_ppe=[],
                        details={
                            "centroid": centroid,
                            "bbox": det.bbox,
                            "person_confidence": det.confidence,
                            "confidence_threshold": person_conf_threshold,
                            "zone_polygon_vertices": len(polygon),
                        },
                        message=message,
                    )
                )

        return violations

    @staticmethod
    def evaluate_fire_smoke(
        payload: DetectionPayload,
        parameters: dict | None = None,
        rule_id: str | None = None,
        rule_name: str | None = None,
        severity: str = RuleSeverity.CRITICAL.value,
        zone_id: str | None = None,
    ) -> list[RuleViolation]:
        """
        Evaluate fire and smoke safety rule.

        For each fire or smoke detection in the detection payload:
        1. Checks whether class_name is 'fire' or 'smoke'.
        2. Compares confidence against the configured confidence_threshold.
        3. Emits a RuleViolation with rule_type='fire_smoke'.
        """
        params = parameters or {}
        conf_threshold = float(params.get("confidence_threshold", 0.50))

        violations: list[RuleViolation] = []

        for det in payload.detections:
            class_lower = det.class_name.lower().strip()
            if class_lower not in {"fire", "smoke"}:
                continue

            if det.confidence < conf_threshold:
                continue

            centroid = None
            if det.bbox and len(det.bbox) >= 4:
                try:
                    centroid = calculate_centroid(det.bbox)
                except ValueError:
                    centroid = None

            track_id = det.track_id if det.track_id is not None else class_lower
            message = f"{class_lower.capitalize()} detected with confidence {det.confidence:.1%}"

            violations.append(
                RuleViolation(
                    rule_id=rule_id,
                    rule_name=rule_name or "Fire / Smoke Detection Rule",
                    rule_type=RuleType.FIRE_SMOKE.value,
                    severity=severity,
                    zone_id=zone_id,
                    camera_id=payload.camera_id,
                    track_id=track_id,
                    person_bbox=det.bbox,
                    person_centroid=centroid,
                    missing_ppe=[],
                    detected_ppe=[],
                    details={
                        "detected_class": class_lower,
                        "confidence": det.confidence,
                        "person_confidence": det.confidence,  # Enables EventEngine to populate Event.confidence
                        "bbox": det.bbox,
                        "track_id": det.track_id,
                        "confidence_threshold": conf_threshold,
                    },
                    message=message,
                )
            )

        return violations

    @classmethod
    def evaluate_frame(
        cls,
        payload: DetectionPayload,
        rules: list,  # list of SafetyRule ORM instances or dict-like rule representations
        zone: Zone | None = None,
    ) -> RuleEvaluationResult:
        """
        Comprehensive frame-level rule evaluation across all configured rules.

        Evaluates active rules against the detection payload in a single pass.
        Returns all violations and compliant track IDs.

        Phase 5 scope: Single-frame deterministic evaluation.
        NOT implemented here (Phase 6):
          - min_persistence_frames (temporal frame accumulation)
          - min_violation_duration_seconds (time-based suppression)
          - cooldown_seconds (repeat-suppression after resolution)
        """
        all_violations: list[RuleViolation] = []
        rules_evaluated = 0

        # Collect unique person track IDs
        all_person_tracks: set[int | str] = set()
        for det in payload.detections:
            if det.class_name.lower().strip() in PERSON_CLASS_NAMES and det.track_id is not None:
                all_person_tracks.add(det.track_id)

        # Evaluate each rule
        for rule in rules:
            # Check rule status if available
            status_val = getattr(rule, "status", None)
            if status_val is not None:
                status_str = status_val.value if hasattr(status_val, "value") else str(status_val)
                if status_str.lower() != RuleStatus.ACTIVE.value.lower():
                    continue

            rule_type_val = getattr(rule, "rule_type", None)
            rule_type_str = rule_type_val.value if hasattr(rule_type_val, "value") else str(rule_type_val)

            rule_id = getattr(rule, "id", None)
            rule_name = getattr(rule, "name", None)
            severity_val = getattr(rule, "severity", RuleSeverity.MEDIUM)
            severity_str = severity_val.value if hasattr(severity_val, "value") else str(severity_val)
            parameters = getattr(rule, "parameters", {}) or {}

            # Determine zone association
            rule_zone_id = getattr(rule, "zone_id", None)
            target_zone_id = rule_zone_id or (zone.id if zone else None)

            rules_evaluated += 1

            if rule_type_str == RuleType.PPE_VIOLATION.value:
                # Required PPE source priority: rule parameters -> zone.required_ppe
                zone_ppe = zone.required_ppe if zone else []
                violations = cls.evaluate_ppe(
                    payload=payload,
                    required_ppe=zone_ppe,
                    parameters=parameters,
                    rule_id=rule_id,
                    rule_name=rule_name,
                    severity=severity_str,
                    zone_id=target_zone_id,
                )
                all_violations.extend(violations)

            elif rule_type_str == RuleType.EXCLUSION_ZONE.value:
                # Polygon source priority: rule parameters -> zone.polygon
                zone_poly = parameters.get("polygon") or (zone.polygon if zone else None)
                if zone_poly:
                    violations = cls.evaluate_restricted_zone(
                        payload=payload,
                        polygon=zone_poly,
                        parameters=parameters,
                        rule_id=rule_id,
                        rule_name=rule_name,
                        severity=severity_str,
                        zone_id=target_zone_id,
                    )
                    all_violations.extend(violations)

            elif rule_type_str == RuleType.FIRE_SMOKE.value:
                violations = cls.evaluate_fire_smoke(
                    payload=payload,
                    parameters=parameters,
                    rule_id=rule_id,
                    rule_name=rule_name,
                    severity=severity_str,
                    zone_id=target_zone_id,
                )
                all_violations.extend(violations)

        # If zone is marked as EXCLUSION or PPE_REQUIRED directly and no explicit rule matched
        if zone is not None and not rules:
            zone_type_str = zone.zone_type.value if hasattr(zone.zone_type, "value") else str(zone.zone_type)
            if zone_type_str == ZoneType.PPE_REQUIRED.value and zone.required_ppe:
                rules_evaluated += 1
                all_violations.extend(
                    cls.evaluate_ppe(
                        payload=payload,
                        required_ppe=zone.required_ppe,
                        zone_id=zone.id,
                        rule_name=f"Zone PPE Rule ({zone.name})",
                    )
                )
            elif zone_type_str == ZoneType.EXCLUSION.value and zone.polygon:
                rules_evaluated += 1
                all_violations.extend(
                    cls.evaluate_restricted_zone(
                        payload=payload,
                        polygon=zone.polygon,
                        zone_id=zone.id,
                        rule_name=f"Exclusion Zone ({zone.name})",
                    )
                )

        # Identify tracks that had zero violations
        violated_tracks = {v.track_id for v in all_violations if v.track_id is not None}
        compliant_tracks = sorted(list(all_person_tracks - violated_tracks), key=str)

        return RuleEvaluationResult(
            camera_id=payload.camera_id,
            violations=all_violations,
            compliant_track_ids=compliant_tracks,
            total_persons_detected=len(all_person_tracks),
            rules_evaluated_count=rules_evaluated,
        )
