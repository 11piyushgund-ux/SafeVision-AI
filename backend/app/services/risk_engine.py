"""
SafeVision AI — Deterministic Risk Engine (Phase 7A)

Takes a validated Safety Event plus context (zone, recurrence) and
deterministically calculates:
  1. numeric risk score  [0.0, 1.0]
  2. risk level          (AlertSeverity: critical/high/medium/low/info)
  3. contributing factors (event_type, zone, confidence, recurrence)
  4. human-readable explanation

Design decisions:
  - ALL weights, thresholds, and scores are explicit constants — reviewable,
    auditable, and deterministic.
  - No LLM, RAG, vision model, or probabilistic reasoning.
  - Pure function mode (assess) works without a DB — usable in unit tests.
  - DB mode (assess_with_db) queries actual historical events for recurrence.
  - Every recurrence query is scoped by org_id — tenant-isolated.

Phase boundary:
  - The Risk Engine PRODUCES a RiskAssessment.
  - The future Alert Engine CONSUMES it to decide whether to create/escalate alerts.
  - This module does NOT create alerts, send notifications, or invoke AI.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.alert import AlertSeverity
from app.models.event import Event, EventType
from app.models.zone import Zone, ZoneType
from app.schemas.risk import RiskAssessment, RiskFactor

log = structlog.get_logger()

# ============================================================================
# Constants — All explicit, reviewable, deterministic
# ============================================================================

# --- Factor Weights (must sum to 1.0) ---
W_EVENT: float = 0.35
W_ZONE: float = 0.25
W_CONFIDENCE: float = 0.15
W_RECURRENCE: float = 0.25

_WEIGHT_SUM = W_EVENT + W_ZONE + W_CONFIDENCE + W_RECURRENCE
assert abs(_WEIGHT_SUM - 1.0) < 1e-9, f"Weights must sum to 1.0, got {_WEIGHT_SUM}"

# --- Event Type Base Scores ---
# Keyed by EventType.value (the string stored in the DB)
EVENT_TYPE_SCORES: dict[str, float] = {
    EventType.FIRE_SMOKE.value: 1.00,       # Immediate life safety threat
    EventType.ZONE_INTRUSION.value: 0.85,   # Exclusion/dangerous zone breach
    EventType.PPE_DETECTION.value: 0.65,    # PPE violation — serious
    EventType.PERSON_DETECTED.value: 0.30,  # Presence detection — low baseline
    EventType.TRACKING_UPDATE.value: 0.10,  # Routine tracking — informational
}
DEFAULT_EVENT_TYPE_SCORE: float = 0.50  # Unknown event types

# --- Zone Criticality Scores ---
# Keyed by ZoneType.value (the string stored in the DB)
ZONE_CRITICALITY_SCORES: dict[str, float] = {
    ZoneType.EXCLUSION.value: 1.00,      # No one should be there
    ZoneType.FIRE_WATCH.value: 0.85,     # Active fire/chemical hazard
    ZoneType.PPE_REQUIRED.value: 0.60,   # Known hazard requiring PPE
    ZoneType.SPEED_LIMIT.value: 0.50,    # Vehicle/movement hazard
    ZoneType.GENERAL.value: 0.30,        # Normal area, low baseline
}
DEFAULT_ZONE_SCORE: float = 0.40  # No zone or unknown zone type

# --- Confidence Defaults ---
DEFAULT_CONFIDENCE: float = 0.50  # When confidence is None/missing

# --- Recurrence ---
DEFAULT_LOOKBACK_HOURS: int = 24
RECURRENCE_CAP: float = 10.0  # prior_count at which recurrence_score = 1.0

# --- Risk Level Thresholds ---
# Ordered from highest to lowest — first match wins
RISK_THRESHOLDS: list[tuple[float, AlertSeverity]] = [
    (0.80, AlertSeverity.CRITICAL),
    (0.60, AlertSeverity.HIGH),
    (0.40, AlertSeverity.MEDIUM),
    (0.20, AlertSeverity.LOW),
    (0.00, AlertSeverity.INFO),
]

# --- Human-Readable Labels ---
_EVENT_TYPE_LABELS: dict[str, str] = {
    EventType.FIRE_SMOKE.value: "Fire/Smoke Detection",
    EventType.ZONE_INTRUSION.value: "Zone Intrusion",
    EventType.PPE_DETECTION.value: "PPE Violation",
    EventType.PERSON_DETECTED.value: "Person Detected",
    EventType.TRACKING_UPDATE.value: "Tracking Update",
}

_ZONE_TYPE_LABELS: dict[str, str] = {
    ZoneType.EXCLUSION.value: "Exclusion Zone",
    ZoneType.FIRE_WATCH.value: "Fire Watch Zone",
    ZoneType.PPE_REQUIRED.value: "PPE Required Zone",
    ZoneType.SPEED_LIMIT.value: "Speed Limit Zone",
    ZoneType.GENERAL.value: "General Zone",
}

_RISK_LEVEL_LABELS: dict[str, str] = {
    AlertSeverity.CRITICAL.value: "CRITICAL",
    AlertSeverity.HIGH.value: "HIGH",
    AlertSeverity.MEDIUM.value: "MEDIUM",
    AlertSeverity.LOW.value: "LOW",
    AlertSeverity.INFO.value: "INFO",
}


# ============================================================================
# Risk Engine
# ============================================================================

class RiskEngine:
    """
    Deterministic, explainable risk assessment engine.

    Stateless — all state is passed in via arguments.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def assess(
        event: Event,
        zone: Zone | None = None,
        recurrence_count: int | None = None,
    ) -> RiskAssessment:
        """
        Pure deterministic risk assessment — no DB access.

        Args:
            event: The safety event to assess. Must have event_type,
                   confidence, camera_id, org_id, id.
            zone: Optional zone context for criticality scoring.
            recurrence_count: Number of prior similar events. None → 0.

        Returns:
            RiskAssessment with score, level, factors, and explanation.
        """
        now = datetime.now(timezone.utc)

        # Extract event type string
        event_type_str = _extract_event_type(event)
        prior_count = recurrence_count if recurrence_count is not None else 0

        # --- Factor 1: Event Type ---
        event_score = EVENT_TYPE_SCORES.get(event_type_str, DEFAULT_EVENT_TYPE_SCORE)
        event_label = _EVENT_TYPE_LABELS.get(event_type_str, event_type_str)
        event_factor = RiskFactor(
            name="event_type",
            raw_value=event_type_str,
            score=event_score,
            weight=W_EVENT,
            weighted_score=round(event_score * W_EVENT, 6),
            explanation=f"{event_label} has base risk score {event_score:.2f}",
        )

        # --- Factor 2: Zone Criticality ---
        zone_score, zone_explanation = _score_zone(zone)
        zone_factor = RiskFactor(
            name="zone_criticality",
            raw_value=_extract_zone_type(zone),
            score=zone_score,
            weight=W_ZONE,
            weighted_score=round(zone_score * W_ZONE, 6),
            explanation=zone_explanation,
        )

        # --- Factor 3: Confidence ---
        conf_score, conf_explanation = _score_confidence(event.confidence)
        conf_factor = RiskFactor(
            name="confidence",
            raw_value=event.confidence,
            score=conf_score,
            weight=W_CONFIDENCE,
            weighted_score=round(conf_score * W_CONFIDENCE, 6),
            explanation=conf_explanation,
        )

        # --- Factor 4: Recurrence ---
        recur_score = min(prior_count / RECURRENCE_CAP, 1.0)
        recur_explanation = (
            f"{prior_count} similar event(s) in lookback window → "
            f"recurrence score {recur_score:.2f}"
        )
        if prior_count == 0:
            recur_explanation = "No prior similar events in lookback window"
        recur_factor = RiskFactor(
            name="recurrence",
            raw_value=prior_count,
            score=recur_score,
            weight=W_RECURRENCE,
            weighted_score=round(recur_score * W_RECURRENCE, 6),
            explanation=recur_explanation,
        )

        # --- Aggregate ---
        factors = [event_factor, zone_factor, conf_factor, recur_factor]
        risk_score = round(sum(f.weighted_score for f in factors), 6)
        # Clamp to [0.0, 1.0] for safety (should be in range due to weights=1.0)
        risk_score = max(0.0, min(1.0, risk_score))

        risk_level = _score_to_level(risk_score)
        level_label = _RISK_LEVEL_LABELS.get(risk_level.value, risk_level.value.upper())

        explanation = (
            f"Risk assessment: {level_label} (score {risk_score:.3f}). "
            f"{event_label} in {_zone_label(zone)} "
            f"with {conf_score:.0%} confidence. "
            f"{prior_count} prior similar event(s) in lookback window."
        )

        return RiskAssessment(
            risk_score=risk_score,
            risk_level=risk_level.value,
            factors=factors,
            explanation=explanation,
            event_id=getattr(event, "id", None),
            event_type=event_type_str,
            camera_id=getattr(event, "camera_id", None),
            org_id=getattr(event, "org_id", ""),
            assessed_at=now,
        )

    @staticmethod
    def assess_with_db(
        event: Event,
        db: Session,
        zone: Zone | None = None,
        lookback_hours: int = DEFAULT_LOOKBACK_HOURS,
    ) -> RiskAssessment:
        """
        Risk assessment with DB-based recurrence lookup.

        Queries actual historical events in PostgreSQL to compute recurrence,
        then delegates to the pure assess() method.

        Args:
            event: The safety event to assess.
            db: SQLAlchemy session (for recurrence query).
            zone: Optional zone context.
            lookback_hours: How far back to count similar events (default 24h).

        Returns:
            RiskAssessment with real recurrence data.
        """
        event_type_str = _extract_event_type(event)

        recurrence_count = RiskEngine.count_recent_events(
            db=db,
            org_id=event.org_id,
            event_type=event_type_str,
            camera_id=event.camera_id,
            exclude_event_id=getattr(event, "id", None),
            lookback_hours=lookback_hours,
        )

        log.debug(
            "risk_recurrence_query",
            org_id=event.org_id,
            event_type=event_type_str,
            camera_id=event.camera_id,
            lookback_hours=lookback_hours,
            recurrence_count=recurrence_count,
        )

        return RiskEngine.assess(
            event=event,
            zone=zone,
            recurrence_count=recurrence_count,
        )

    @staticmethod
    def count_recent_events(
        db: Session,
        org_id: str,
        event_type: str,
        camera_id: str,
        exclude_event_id: str | None = None,
        lookback_hours: int = DEFAULT_LOOKBACK_HOURS,
    ) -> int:
        """
        Count recent events matching the given criteria.

        CRITICAL: Always filters by org_id for tenant isolation.
        Never counts events from a different organization.

        Args:
            db: SQLAlchemy session.
            org_id: Organization ID — REQUIRED for tenant isolation.
            event_type: Event type string to match.
            camera_id: Camera ID to match.
            exclude_event_id: Exclude this event (the current one) from the count.
            lookback_hours: How far back to look (default 24h).

        Returns:
            Number of matching events (0 if none).
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        query = (
            db.query(func.count(Event.id))
            .filter(
                Event.org_id == org_id,          # TENANT ISOLATION
                Event.event_type == event_type,
                Event.camera_id == camera_id,
                Event.timestamp >= cutoff,
            )
        )

        if exclude_event_id is not None:
            query = query.filter(Event.id != exclude_event_id)

        result = query.scalar()
        return result or 0


# ============================================================================
# Internal Helpers
# ============================================================================

def _extract_event_type(event: Event) -> str:
    """Extract the event_type string from an Event object.

    Handles both:
      - SQLAlchemy-mapped Event with event_type as Enum or string
      - Mock objects used in tests
    """
    et = getattr(event, "event_type", None)
    if et is None:
        return "unknown"
    # If it's an EventType enum member, use .value
    if isinstance(et, EventType):
        return et.value
    # If it's already a string, use as-is
    if isinstance(et, str):
        return et
    return str(et)


def _extract_zone_type(zone: Zone | None) -> str | None:
    """Extract zone_type string from a Zone object."""
    if zone is None:
        return None
    zt = getattr(zone, "zone_type", None)
    if zt is None:
        return None
    if isinstance(zt, ZoneType):
        return zt.value
    if isinstance(zt, str):
        return zt
    return str(zt)


def _score_zone(zone: Zone | None) -> tuple[float, str]:
    """Compute zone criticality score and explanation."""
    if zone is None:
        return DEFAULT_ZONE_SCORE, "No zone context — default criticality applied (0.40)"

    zone_type_str = _extract_zone_type(zone)
    if zone_type_str is None:
        return DEFAULT_ZONE_SCORE, "Zone has no type — default criticality applied (0.40)"

    score = ZONE_CRITICALITY_SCORES.get(zone_type_str, DEFAULT_ZONE_SCORE)
    label = _ZONE_TYPE_LABELS.get(zone_type_str, zone_type_str)
    zone_name = getattr(zone, "name", "Unknown")
    return score, f"{label} '{zone_name}' has criticality score {score:.2f}"


def _score_confidence(confidence: float | None) -> tuple[float, str]:
    """Normalize confidence to [0.0, 1.0] with safe defaults."""
    if confidence is None:
        return DEFAULT_CONFIDENCE, "No confidence provided — default 0.50 applied"

    # Clamp to valid range
    clamped = max(0.0, min(1.0, float(confidence)))

    if clamped != confidence:
        return clamped, (
            f"Confidence {confidence} clamped to {clamped:.2f} "
            f"(valid range 0.0–1.0)"
        )

    return clamped, f"Detection confidence {clamped:.2f}"


def _score_to_level(score: float) -> AlertSeverity:
    """Map a risk score to an AlertSeverity level using thresholds."""
    for threshold, level in RISK_THRESHOLDS:
        if score >= threshold:
            return level
    # Should never reach here given thresholds include 0.0
    return AlertSeverity.INFO


def _zone_label(zone: Zone | None) -> str:
    """Human-readable zone label for explanations."""
    if zone is None:
        return "unzoned area"
    zone_name = getattr(zone, "name", "Unknown")
    zone_type_str = _extract_zone_type(zone)
    type_label = _ZONE_TYPE_LABELS.get(zone_type_str or "", zone_type_str or "unknown")
    return f"{type_label} '{zone_name}'"
