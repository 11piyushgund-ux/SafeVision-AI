# Phase 13 — Recurring Patterns Implementation Plan

## 1. Current-State Summary

The SafeVision AI platform includes a **Recurring Patterns** page located at [frontend/src/routes/patterns.tsx](file:///d:/SafeVision-AI/frontend/src/routes/patterns.tsx) and served at `http://localhost:8080/patterns`. The page currently queries `GET /api/patterns` via TanStack Query and displays:
- A filter bar with a "Pattern Type" dropdown, a static "Status" summary label, and an inert "Export Report" button.
- A two-column master-detail layout with a **Patterns List** on the left and **Pattern Details**, **Trend Over Time**, **Pattern Insights**, and **Description** on the right.

### The Problem
1. **Static / Seeded Records Only:** The backend endpoint `GET /api/patterns` in [backend/app/api/patterns.py](file:///d:/SafeVision-AI/backend/app/api/patterns.py) only queries existing rows in the `patterns` PostgreSQL table. No dynamic analysis engine or pattern generation service exists anywhere in the codebase.
2. **Disconnected from Real Safety Events:** The active database contains real detection events across Fire/Smoke, PPE compliance, and Zone Intrusions generated during live video processing in Phases 11 and 12. However, the `patterns` table contains only three static demo rows inserted on `2026-08-21` by [backend/scripts/seed_dev_data.py](file:///d:/SafeVision-AI/backend/scripts/seed_dev_data.py).
3. **No Real Historical Trend Chart:** In [frontend/src/routes/patterns.tsx](file:///d:/SafeVision-AI/frontend/src/routes/patterns.tsx#L215-L233), the "Trend Over Time" section contains only a placeholder card with a Lucide icon and a static text count. No day-wise event frequency is computed or plotted, despite `recharts` being installed in the project.
4. **Non-Functional UI Controls:** The "Export Report" button has no `onClick` handler. The "Pattern Type" dropdown contains `"correlation"`, which does not exist in the backend `PatternType` enum.

---

## 2. Goal

Transform the Recurring Patterns feature from a static demo screen into a **genuinely data-driven, event-connected intelligence system**.

When real safety events occur (e.g. repeated Fire/Smoke detections or PPE non-compliance in a specific zone), the system must:
1. Group and aggregate real events into concrete recurring safety patterns.
2. Accurately calculate total occurrence count, first detected timestamp, and last detected timestamp from actual `events` rows.
3. Compute day-wise frequency distribution (daily occurrence history).
4. Render an interactive, responsive **Trend Over Time** visual chart using the existing Recharts component system.
5. Provide a functional **Export Report** capability to download current recurring pattern findings.
6. Reconcile legacy seed records safely by marking orphan records `dismissed` rather than deleting them.

---

## 3. Architecture Overview

```
+-----------------------------------------------------------------------------------+
|                              CV Pipeline & Video Session                          |
|             (Video Frames -> YOLO / BoT-SORT -> Safety Rules -> EventEngine)      |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                             PostgreSQL `events` Table                             |
|          (id, camera_id -> zone_id, org_id, event_type, timestamp, confidence)    |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                        PatternEngine (Service Layer)                              |
|   - Groups real events by (org_id, event_type, zone_id)                           |
|   - Evaluates recurrence threshold (count >= 2)                                   |
|   - Calculates: occurrence_count, first_detected_at, last_detected_at             |
|   - Aggregates day-wise trend: [{"date": "YYYY-MM-DD", "occurrences": N}, ...]   |
|   - Maps pattern_type (temporal, spatial, trend)                                 |
|   - Enforces strict PatternStatus (active, dismissed, resolved)                   |
|   - Reconciles orphan seed patterns (marks them dismissed, never deletes)         |
|   - Upserts records into PostgreSQL `patterns` table                              |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                             GET /api/patterns API                                 |
|   - Invokes PatternEngine.sync_patterns(db, org_id)                               |
|   - Returns PatternListResponse with single-source daily_trend array              |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                         Frontend UI (/patterns Route)                             |
|   - Patterns List: Displays real safety patterns sorted by recency/occurrences   |
|   - Pattern Details: Shows real counts, first/last detected dates, zone, type     |
|   - Trend Over Time: Real Recharts AreaChart plotting day-wise occurrences        |
|   - Export Report: Client-side CSV export of current recurring patterns           |
+-----------------------------------------------------------------------------------+
```

---

## 4. Key Design Decisions

### 4.1 Pattern Identity Definition
* **Canonical Identity:** `(org_id, event_type, zone_id)`
* **Rationale:** In workplace safety, a recurring pattern is a *location-based hazard*. An assembly zone with multiple fire/smoke incidents or a loading dock with repeated zone intrusions represents an ongoing hazard that requires intervention.
* **Camera Handling:** Camera ID is **not** part of pattern identity. Cameras are sensors observing physical zones (`camera.zone_id`). Multiple cameras can observe the same zone; events captured by any camera within that zone must aggregate into that zone's safety pattern. If a camera has no assigned zone, its unassigned status is grouped under `zone_id = None` ("General Facility").

### 4.2 Recurrence Threshold
* **Threshold Value:** `occurrence_count >= 2`
* **Rationale:** A single detection is an isolated incident, not a pattern. Two or more qualified events within the organization's event history establish recurrence.

### 4.3 Participating Event Types
Only actionable safety violation event types participate in recurring pattern generation:
- `EventType.FIRE_SMOKE`: Environmental / hazard risk.
- `EventType.PPE_DETECTION`: Worker compliance risk.
- `EventType.ZONE_INTRUSION`: Physical boundary / exclusion zone risk.
*Excluded:* `person_detected` and `tracking_update` are raw computer vision telemetry records, not safety violations.

### 4.4 Pattern Type Mapping
Using the existing `PatternType` enum defined in [backend/app/models/pattern.py](file:///d:/SafeVision-AI/backend/app/models/pattern.py#L20-L27):
- `fire_smoke` $\longrightarrow$ `PatternType.TREND` (rising or clustered hazard frequency over time).
- `zone_intrusion` $\longrightarrow$ `PatternType.SPATIAL` (repeated breaches of defined geographic boundaries).
- `ppe_detection` $\longrightarrow$ `PatternType.TEMPORAL` (compliance lapses across operating hours/shifts).

### 4.5 Pattern Status Lifecycle (CRITICAL CORRECTION)
* **Strict Constraint:** Only existing database `PatternStatus` enum values are permitted:
  - `active`
  - `dismissed`
  - `resolved`
* **NO INFERRED RESOLUTION:** Do NOT automatically set an active pattern to `RESOLVED` merely because no occurrences were recorded for 14+ days. A safety hazard is not resolved simply because events temporarily paused.
* **Status Rules for Phase 13:**
  - `active`: A currently recognized recurring safety pattern backed by $\ge 2$ real events.
  - `dismissed`: Explicitly dismissed by a human operator, OR legacy seed records marked dismissed during reconciliation.
  - `resolved`: Explicitly marked resolved through human action or safety resolution workflow.
  - **Preservation Rule:** If an existing pattern has already been explicitly marked `dismissed` or `resolved`, `sync_patterns` must preserve its status and NOT revert it back to `active`.

### 4.6 Legacy Seed Pattern Reconciliation (CRITICAL CORRECTION)
* The database currently contains three seeded demo records (`d0000000-0000-0000-0000-000000000040`, `...41`, `...42`) inserted during dev seeding with synthetic dates (`2026-08-21`).
* **Handling Strategy:**
  - `PatternEngine` checks whether each existing pattern has matching real event records in the `events` table.
  - If an existing pattern has **zero** backing real events, it is identified as a legacy seed record.
  - **DO NOT DELETE:** The system does **not** delete database rows.
  - **SAFELY MARK DISMISSED:** The engine updates `status = PatternStatus.DISMISSED` and notes `"Legacy seed record with no backing events"` in its metadata.
  - This immediately prevents stale seed records from polluting the active Recurring Patterns view, while maintaining complete database audit history and referential integrity.

### 4.7 Synchronization Strategy
* **Selected Strategy:** **On-demand synchronization during `GET /api/patterns`**.
* **Rationale:** Deterministic, zero background infrastructure, guaranteed 100% fresh whenever the user navigates to or refreshes `/patterns`.
* `PatternEngine.sync_patterns(db, org_id)` is invoked at the start of `GET /api/patterns`, ensuring every API request reads current aggregated events.

### 4.8 Daily Trend Authoritative Source
* **Single Authoritative Source:** Daily trend data is calculated directly from `Event.timestamp` grouped by UTC date.
* **Storage:** Stored in the existing `patterns.pattern_data` PostgreSQL `JSONB` column under the key `"daily_trend"`:
  ```json
  "daily_trend": [
    { "date": "2026-09-04", "occurrences": 3 },
    { "date": "2026-09-07", "occurrences": 93 }
  ]
  ```
* **Serialization:** In `PatternResponse`, the top-level `daily_trend` field is derived directly from `pattern_data["daily_trend"]` at response construction time. It is never independently maintained or duplicated, avoiding split-brain data states.
* **No Database Migrations Required:** Reusing `pattern_data` JSONB requires zero database schema changes.

### 4.9 Timezone Handling
* All timestamps in PostgreSQL are stored with timezone UTC (`DateTime(timezone=True)`).
* Daily grouping queries truncate to UTC dates (`cast(timestamp at time zone 'UTC' as date)`).
* Date labels are serialized in standard ISO `YYYY-MM-DD` format, preventing date-shift discrepancies around midnight.

---

## 5. Proposed File Changes

### 5.1 Backend Changes

#### [NEW] [backend/app/services/pattern_engine.py](file:///d:/SafeVision-AI/backend/app/services/pattern_engine.py)
- **Responsibility:** Core pattern analysis, legacy reconciliation, and event synchronization service.
- **Key Methods:**
  - `sync_patterns(db: Session, org_id: str) -> list[Pattern]`:
    1. Reconciles orphan/seed records: finds patterns in `org_id` with 0 backing events and sets `status = PatternStatus.DISMISSED`.
    2. Queries real events for `org_id` where `event_type IN ('fire_smoke', 'ppe_detection', 'zone_intrusion')`.
    3. Groups by `(event_type, camera.zone_id)`.
    4. Filters groups with `count >= 2`.
    5. Calculates `first_detected_at`, `last_detected_at`, `occurrence_count`, and `confidence_score`.
    6. Builds `daily_trend` array.
    7. Upserts pattern records idempotently (preserves explicit `dismissed`/`resolved` statuses).
  - `_generate_title(event_type: str, zone_name: str | None) -> str`.
  - `_generate_description(event_type: str, zone_name: str | None, count: int, first_dt: datetime, last_dt: datetime) -> str`.

#### [MODIFY] [backend/app/schemas/pattern_schema.py](file:///d:/SafeVision-AI/backend/app/schemas/pattern_schema.py)
- **Responsibility:** Add `DailyTrendItem(BaseModel)` schema (`date: str`, `occurrences: int`). Add `daily_trend: list[DailyTrendItem] | None = None` to `PatternResponse`.

#### [MODIFY] [backend/app/api/patterns.py](file:///d:/SafeVision-AI/backend/app/api/patterns.py)
- **Responsibility:** Call `PatternEngine.sync_patterns(db, current_user.org_id)` on `GET /api/patterns`. Populate `daily_trend` on `PatternResponse` directly from `pattern_data["daily_trend"]`.

#### [NEW] [backend/tests/test_pattern_engine.py](file:///d:/SafeVision-AI/backend/tests/test_pattern_engine.py)
- **Responsibility:** Comprehensive automated tests:
  - Pattern generation from multiple events.
  - Database-driven calculation checks (`COUNT`, `MIN`, `MAX`, day-wise breakdown).
  - Threshold enforcement (ignores single events).
  - Legacy seed pattern reconciliation (marks orphan records `dismissed`).
  - Status preservation (does not revert `resolved`/`dismissed` to `active`).
  - Tenant isolation between organizations.

---

### 5.2 Frontend Changes

#### [MODIFY] [frontend/src/lib/api-types.ts](file:///d:/SafeVision-AI/frontend/src/lib/api-types.ts)
- **Responsibility:** Add `daily_trend?: { date: string; occurrences: number }[] | null` to `PatternResponse` interface.

#### [MODIFY] [frontend/src/routes/patterns.tsx](file:///d:/SafeVision-AI/frontend/src/routes/patterns.tsx)
- **Responsibility:**
  1. **Trend Over Time Chart:** Replace the placeholder in lines 215–233 with an `AreaChart` using Recharts primitives and `@/components/ui/chart`.
  2. **Export Report Button:** Connect lines 118–121 to a client-side CSV download handler generating `safevision-patterns-report.csv`.
  3. **Filter Corrections:** Remove non-existent `"correlation"` option from Pattern Type dropdown; align options with `all`, `temporal`, `spatial`, `trend`, `rule_based`, `worker`.
  4. **Status Filter:** Upgrade the static "Status" indicator into an interactive `<select>` dropdown supporting `all`, `active`, `dismissed`, `resolved`.

---

### 5.3 Files That MUST NOT Be Modified
- `backend/app/models/**` (No database schema alterations or migrations).
- `backend/app/services/video_service.py`
- `backend/app/services/cv_pipeline.py`
- `backend/app/services/event_engine.py`
- `backend/app/services/alert_engine.py`
- `frontend/src/routes/live-monitoring.tsx`
- `frontend/src/routes/alerts.tsx`
- `frontend/src/components/safevision/VideoCanvasOverlay.tsx`
- `frontend/src/components/safevision/EventEvidenceModal.tsx`
- `package.json`, `package-lock.json`

---

## 6. API Contract Specification

### `GET /api/patterns`
- **Authentication:** Bearer JWT required (`current_user`).
- **Query Parameters:**
  - `page`: integer (default 1)
  - `size`: integer (default 50)
  - `pattern_type`: string | null (`temporal`, `spatial`, `trend`, `rule_based`, `worker`)
  - `status`: string | null (`active`, `dismissed`, `resolved`)
- **Response Model:** `PatternListResponse`

> [!NOTE]
> The JSON payload below contains illustrative sample schema values. In accordance with Correction 3, acceptance criteria and tests will evaluate dynamic mathematical assertions against actual events table records at test time rather than fixed numbers or dates.

```json
{
  "data": [
    {
      "id": "c1f7a8e2-...",
      "org_id": "d0000000-0000-0000-0000-000000000001",
      "zone_id": "d0000000-0000-0000-0000-000000000010",
      "zone_name": "Assembly Zone A",
      "rule_id": null,
      "pattern_type": "trend",
      "title": "Recurring Fire/Smoke Activity — Assembly Zone A",
      "description": "Detected recurring fire/smoke in Assembly Zone A.",
      "occurrence_count": 101,
      "confidence_score": 0.76,
      "status": "active",
      "first_detected_at": "2026-09-04T09:00:00Z",
      "last_detected_at": "2026-09-08T00:21:32Z",
      "created_at": "2026-09-08T01:00:00Z",
      "pattern_data": {
        "daily_trend": [
          { "date": "2026-09-04", "occurrences": 3 },
          { "date": "2026-09-07", "occurrences": 93 },
          { "date": "2026-09-08", "occurrences": 5 }
        ]
      },
      "daily_trend": [
        { "date": "2026-09-04", "occurrences": 3 },
        { "date": "2026-09-07", "occurrences": 93 },
        { "date": "2026-09-08", "occurrences": 5 }
      ]
    }
  ],
  "total": 1,
  "page": 1,
  "size": 50
}
```

---

## 7. Database-Driven Acceptance Verification

Acceptance criteria must **never** compare against fixed/hard-coded values. Acceptance tests will evaluate dynamic mathematical assertions directly against the PostgreSQL `events` table at test execution time:

1. **Occurrence Count Identity:**
   $$\text{pattern.occurrence\_count} == \text{COUNT}(\text{events where org, type, and zone match})$$
2. **First Detected Timestamp:**
   $$\text{pattern.first\_detected\_at} == \text{MIN}(\text{event.timestamp for matching events})$$
3. **Last Detected Timestamp:**
   $$\text{pattern.last\_detected\_at} == \text{MAX}(\text{event.timestamp for matching events})$$
4. **Daily Trend Distribution:**
   $$\text{daily\_trend} == \text{day-by-day frequency counts matching SQL GROUP BY date}$$
5. **Legacy Seed Reconciliation:**
   $$\text{COUNT}(\text{patterns where status == 'active' and matching\_events == 0}) == 0$$
   All orphan seed records must have `status == 'dismissed'`.

---

## 8. Implementation Order

1. Update backend schema with `DailyTrendItem` and `daily_trend` field.
2. Implement `PatternEngine` service with real aggregation, day-wise trends, and seed reconciliation.
3. Integrate `PatternEngine.sync_patterns` into `backend/app/api/patterns.py`.
4. Implement `P13-003A — Reconcile Legacy Seed Patterns` and verify orphan seed patterns are marked dismissed.
5. Create automated unit/integration tests in `backend/tests/test_pattern_engine.py`.
6. Update frontend API types in `frontend/src/lib/api-types.ts`.
7. Implement Recharts visual `AreaChart` for "Trend Over Time" in `frontend/src/routes/patterns.tsx`.
8. Implement CSV export handler on "Export Report" button.
9. Fix filter dropdowns (remove "correlation", add active status filter).
10. Run backend tests (`pytest`), frontend TypeScript (`tsc`), and production build (`npm run build`).
11. Perform live browser verification at `http://localhost:8080/patterns`.
