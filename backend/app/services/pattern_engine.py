"""
SafeVision AI — Pattern Engine Service (Phase 13)

Analyzes real safety events from the events table, groups recurring incidents
by (org_id, event_type, zone_id), computes occurrence counts, date boundaries,
and daily occurrence frequency trends. Idempotently synchronizes Pattern records
and safely reconciles legacy seed records.
"""

from collections import defaultdict
from datetime import datetime, timezone
import uuid

import structlog
from sqlalchemy.orm import Session

from app.models.camera import Camera
from app.models.event import Event, EventType
from app.models.pattern import Pattern, PatternStatus, PatternType
from app.models.zone import Zone

log = structlog.get_logger()

# Mapping from EventType string/enum to PatternType
EVENT_TYPE_TO_PATTERN_TYPE: dict[str, PatternType] = {
    EventType.FIRE_SMOKE.value: PatternType.TREND,
    EventType.ZONE_INTRUSION.value: PatternType.SPATIAL,
    EventType.PPE_DETECTION.value: PatternType.TEMPORAL,
}

RECURRENCE_THRESHOLD = 2


def _get_utc_date_str(dt: datetime) -> str:
    """Format datetime as UTC YYYY-MM-DD string."""
    if dt.tzinfo is not None:
        utc_dt = dt.astimezone(timezone.utc)
    else:
        utc_dt = dt.replace(tzinfo=timezone.utc)
    return utc_dt.strftime("%Y-%m-%d")


def _generate_pattern_title(event_type: str, zone_name: str | None) -> str:
    """Generate human-readable title for a pattern."""
    location = zone_name or "General Facility"
    if event_type == EventType.FIRE_SMOKE.value:
        return f"Recurring Fire/Smoke Activity — {location}"
    elif event_type == EventType.PPE_DETECTION.value:
        return f"Recurring PPE Non-Compliance — {location}"
    elif event_type == EventType.ZONE_INTRUSION.value:
        return f"Repeated Zone Intrusion Breaches — {location}"
    return f"Recurring Safety Incidents — {location}"


def _generate_pattern_description(
    event_type: str, zone_name: str | None, count: int, first_dt: datetime, last_dt: datetime
) -> str:
    """Generate detailed description for a pattern."""
    location = zone_name or "General Facility"
    first_str = _get_utc_date_str(first_dt)
    last_str = _get_utc_date_str(last_dt)

    if event_type == EventType.FIRE_SMOKE.value:
        return (
            f"Detected {count} recurring fire or smoke incidents in {location} "
            f"between {first_str} and {last_str}."
        )
    elif event_type == EventType.PPE_DETECTION.value:
        return (
            f"Detected {count} recurring PPE compliance violations in {location} "
            f"between {first_str} and {last_str}."
        )
    elif event_type == EventType.ZONE_INTRUSION.value:
        return (
            f"Detected {count} unauthorized boundary or exclusion zone breaches in {location} "
            f"between {first_str} and {last_str}."
        )
    return f"Detected {count} recurring safety violations in {location}."


class PatternEngine:
    """Domain service for safety event pattern analysis, legacy reconciliation, and synchronization."""

    @classmethod
    def reconcile_legacy_seed_patterns(cls, db: Session, org_id: str) -> int:
        """
        Identify legacy Pattern records that have zero backing real Event records.
        Safely mark them DISMISSED without deleting them so they do not pollute
        the active Recurring Patterns view.

        Returns the number of patterns transitioned to DISMISSED.
        """
        # 1. Look up all cameras and their zone mappings for this org
        cameras = db.query(Camera.id, Camera.zone_id).filter(Camera.org_id == org_id).all()
        cam_to_zone = {c.id: c.zone_id for c in cameras}

        # 2. Query real actionable events for this org
        real_events = (
            db.query(Event.event_type, Event.camera_id)
            .filter(
                Event.org_id == org_id,
                Event.event_type.in_([
                    EventType.FIRE_SMOKE,
                    EventType.PPE_DETECTION,
                    EventType.ZONE_INTRUSION,
                ]),
            )
            .all()
        )

        # Build set of (pattern_type_str, zone_id) pairs with backing real events
        active_backing_pairs = set()
        for ev in real_events:
            etype = ev.event_type.value if hasattr(ev.event_type, "value") else str(ev.event_type)
            ptype = EVENT_TYPE_TO_PATTERN_TYPE.get(etype)
            if ptype:
                ptype_val = ptype.value if hasattr(ptype, "value") else str(ptype)
                zone_id = cam_to_zone.get(ev.camera_id)
                active_backing_pairs.add((ptype_val, zone_id))

        # 3. Query all patterns for this org
        patterns = db.query(Pattern).filter(Pattern.org_id == org_id).all()
        reconciled_count = 0

        for p in patterns:
            ptype_val = p.pattern_type.value if hasattr(p.pattern_type, "value") else str(p.pattern_type)
            is_seed_id = p.id.startswith("d0000000-0000-0000-0000-00000000004")
            has_no_daily_trend = not (isinstance(p.pattern_data, dict) and "daily_trend" in p.pattern_data)
            has_no_backing_events = (ptype_val, p.zone_id) not in active_backing_pairs

            # Seed patterns or orphan records without backing events
            if is_seed_id or (has_no_daily_trend and has_no_backing_events) or (isinstance(p.pattern_data, dict) and p.pattern_data.get("reconciled")):
                if p.status == PatternStatus.ACTIVE or (hasattr(p.status, "value") and p.status.value == "active") or str(p.status) == "active":
                    p.status = PatternStatus.DISMISSED
                    reconciled_count += 1
                
                existing_data = p.pattern_data if isinstance(p.pattern_data, dict) else {}
                p.pattern_data = {
                    **existing_data,
                    "reconciled": True,
                    "reconciliation_reason": "Legacy seed record with zero backing events",
                }
                db.add(p)

        if reconciled_count > 0:
            log.info("legacy_seed_patterns_reconciled", org_id=org_id, count=reconciled_count)
            db.flush()

        return reconciled_count

    @classmethod
    def sync_patterns(cls, db: Session, org_id: str) -> list[Pattern]:
        """
        Synchronize recurring safety patterns from real detection events.

        1. Reconcile orphan seed patterns (marks them DISMISSED, never deletes).
        2. Group real events by (event_type, zone_id).
        3. Filter by recurrence threshold (count >= 2).
        4. Calculate occurrence_count, date ranges, confidence, and daily_trend.
        5. Upsert Pattern records idempotently, strictly preserving explicit
           DISMISSED/RESOLVED states.
        """
        # Step 1: Reconcile legacy seed patterns
        cls.reconcile_legacy_seed_patterns(db, org_id)

        # Step 2: Query camera to zone mapping and zone names
        cameras = db.query(Camera.id, Camera.zone_id).filter(Camera.org_id == org_id).all()
        cam_to_zone = {c.id: c.zone_id for c in cameras}

        zones = db.query(Zone.id, Zone.name).filter(Zone.org_id == org_id).all()
        zone_names = {z.id: z.name for z in zones}

        # Step 3: Query all actionable events for this org
        events = (
            db.query(Event)
            .filter(
                Event.org_id == org_id,
                Event.event_type.in_([
                    EventType.FIRE_SMOKE,
                    EventType.PPE_DETECTION,
                    EventType.ZONE_INTRUSION,
                ]),
            )
            .all()
        )

        # Step 4: Group events by (event_type, zone_id)
        grouped_events: dict[tuple[str, str | None], list[Event]] = defaultdict(list)
        for ev in events:
            etype = ev.event_type.value if hasattr(ev.event_type, "value") else str(ev.event_type)
            if etype in EVENT_TYPE_TO_PATTERN_TYPE:
                zone_id = cam_to_zone.get(ev.camera_id)
                grouped_events[(etype, zone_id)].append(ev)

        # Step 5: Process each group meeting the recurrence threshold
        for (etype, zone_id), evts in grouped_events.items():
            if len(evts) < RECURRENCE_THRESHOLD:
                continue

            ptype = EVENT_TYPE_TO_PATTERN_TYPE[etype]
            occurrence_count = len(evts)
            first_detected_at = min(e.timestamp for e in evts)
            last_detected_at = max(e.timestamp for e in evts)

            # Average confidence score
            confidences = [e.confidence for e in evts if e.confidence is not None]
            confidence_score = round(sum(confidences) / len(confidences), 2) if confidences else 0.85

            # Day-wise occurrence distribution (UTC)
            daily_counts: dict[str, int] = defaultdict(int)
            for e in evts:
                daily_counts[_get_utc_date_str(e.timestamp)] += 1
            sorted_dates = sorted(daily_counts.keys())
            daily_trend = [{"date": d, "occurrences": daily_counts[d]} for d in sorted_dates]

            zone_name = zone_names.get(zone_id) if zone_id else None
            title = _generate_pattern_title(etype, zone_name)
            description = _generate_pattern_description(
                etype, zone_name, occurrence_count, first_detected_at, last_detected_at
            )

            pattern_data = {
                "daily_trend": daily_trend,
                "event_type": etype,
                "zone_id": zone_id,
            }

            # Find matching existing real pattern for this org, ptype, and zone_id
            query = db.query(Pattern).filter(
                Pattern.org_id == org_id,
                Pattern.pattern_type == ptype,
            )
            if zone_id is not None:
                query = query.filter(Pattern.zone_id == zone_id)
            else:
                query = query.filter(Pattern.zone_id.is_(None))

            candidates = query.all()
            existing_real_pattern = None
            for cand in candidates:
                cand_data = cand.pattern_data if isinstance(cand.pattern_data, dict) else {}
                if not cand_data.get("reconciled"):
                    existing_real_pattern = cand
                    break

            if existing_real_pattern:
                # Update existing record
                existing_real_pattern.occurrence_count = occurrence_count
                existing_real_pattern.confidence_score = confidence_score
                existing_real_pattern.first_detected_at = first_detected_at
                existing_real_pattern.last_detected_at = last_detected_at
                existing_real_pattern.title = title
                existing_real_pattern.description = description
                existing_data = existing_real_pattern.pattern_data if isinstance(existing_real_pattern.pattern_data, dict) else {}
                existing_real_pattern.pattern_data = {
                    **existing_data,
                    **pattern_data,
                }
                # Preserve explicit DISMISSED / RESOLVED status. Only keep ACTIVE if it is ACTIVE.
                # Inactivity never auto-resolves patterns!
                current_status = (
                    existing_real_pattern.status.value
                    if hasattr(existing_real_pattern.status, "value")
                    else str(existing_real_pattern.status)
                )
                if current_status not in (PatternStatus.DISMISSED.value, PatternStatus.RESOLVED.value, "dismissed", "resolved"):
                    existing_real_pattern.status = PatternStatus.ACTIVE

                db.add(existing_real_pattern)
            else:
                # Create new real pattern
                new_pattern = Pattern(
                    id=str(uuid.uuid4()),
                    org_id=org_id,
                    zone_id=zone_id,
                    rule_id=None,
                    pattern_type=ptype,
                    title=title,
                    description=description,
                    occurrence_count=occurrence_count,
                    confidence_score=confidence_score,
                    pattern_data=pattern_data,
                    status=PatternStatus.ACTIVE,
                    first_detected_at=first_detected_at,
                    last_detected_at=last_detected_at,
                    created_at=datetime.now(timezone.utc),
                )
                db.add(new_pattern)

        db.commit()

        # Return updated list of patterns for this org
        return (
            db.query(Pattern)
            .filter(Pattern.org_id == org_id)
            .order_by(Pattern.last_detected_at.desc())
            .all()
        )
