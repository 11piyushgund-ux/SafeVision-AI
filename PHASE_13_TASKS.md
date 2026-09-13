# Phase 13 — Task Checklist

This document defines the strictly ordered, dependency-tracked execution tasks for implementing the data-driven **Recurring Patterns** feature in SafeVision AI.

---

## Task Matrix

| Task ID | Task Title | Primary File(s) | Dependencies | Status |
| :--- | :--- | :--- | :--- | :---: |
| **P13-001** | Define Pattern Response Schemas with Daily Trend | `backend/app/schemas/pattern_schema.py` | None | Completed |
| **P13-002** | Implement `PatternEngine` Service | `backend/app/services/pattern_engine.py` | P13-001 | Completed |
| **P13-003** | Integrate `PatternEngine` into Patterns API | `backend/app/api/patterns.py` | P13-002 | Completed |
| **P13-003A** | Reconcile Legacy Seed Patterns | `backend/app/services/pattern_engine.py`, `backend/app/api/patterns.py` | P13-002, P13-003 | Completed |
| **P13-004** | Create Automated Unit/Integration Tests for `PatternEngine` | `backend/tests/test_pattern_engine.py` | P13-002, P13-003, P13-003A | Completed |
| **P13-005** | Update Frontend API Types for Daily Trend | `frontend/src/lib/api-types.ts` | P13-001 | Completed |
| **P13-006** | Implement "Trend Over Time" Recharts Visual Component | `frontend/src/routes/patterns.tsx` | P13-005 | Completed |
| **P13-007** | Implement "Export Report" Client-Side CSV Handler | `frontend/src/routes/patterns.tsx` | None | Completed |
| **P13-008** | Align Pattern Type and Status Filters | `frontend/src/routes/patterns.tsx` | None | Completed |
| **P13-009** | Execute Full Backend Test Suite & Health Check | Backend runtime | P13-004 | Completed |
| **P13-010** | Execute Frontend TypeScript & Production Build Checks | `frontend/` build scripts | P13-006, P13-007, P13-008 | Completed |
| **P13-011** | Database Reality Verification | PostgreSQL read-only check | P13-009 | Completed |
| **P13-012** | End-to-End Browser Acceptance Verification | Live browser at `/patterns` | P13-010, P13-011 | Completed |

---

## Detailed Task Breakdown

### P13-001 — Define Pattern Response Schemas with Daily Trend
- **Objective:** Extend Pydantic response models to formally represent day-wise occurrence history.
- **Files Involved:** [backend/app/schemas/pattern_schema.py](file:///d:/SafeVision-AI/backend/app/schemas/pattern_schema.py)
- **Dependencies:** None
- **Implementation Details:**
  - Add `DailyTrendItem(BaseModel)` with `date: str` (`YYYY-MM-DD`) and `occurrences: int`.
  - Add `daily_trend: list[DailyTrendItem] | None = None` to `PatternResponse`.
  - Ensure single authoritative derivation: top-level `daily_trend` is projected from `pattern_data["daily_trend"]` at serialization time to avoid split-brain representations.
- **Validation:** Python schema validation in test runner.
- **Acceptance Condition:** Schema serializes pattern objects and exposes `daily_trend` derived from `pattern_data["daily_trend"]` without breaking existing fields.

---

### P13-002 — Implement `PatternEngine` Service
- **Objective:** Create the core domain service that analyzes real safety events, groups recurring incidents, and calculates pattern metrics.
- **Files Involved:** `backend/app/services/pattern_engine.py` (NEW)
- **Dependencies:** P13-001
- **Implementation Details:**
  - Group real events by `(org_id, event_type, camera.zone_id)`.
  - Filter by recurrence threshold (`count >= 2`).
  - Calculate `first_detected_at = min(timestamp)`, `last_detected_at = max(timestamp)`.
  - Calculate `confidence_score = round(avg(confidence), 2)`.
  - Map `pattern_type` (`fire_smoke -> trend`, `zone_intrusion -> spatial`, `ppe_detection -> temporal`).
  - Compute day-wise frequency distribution in UTC dates and store authoritatively in `pattern_data["daily_trend"]`.
  - **Strict Status Lifecycle (Correction 1):**
    - `active`: currently recognized recurring pattern backed by $\ge 2$ real events.
    - `dismissed`: explicitly dismissed by human operator, or legacy seed records reconciled.
    - `resolved`: explicitly resolved by human operator.
    - **NO INFERRED RESOLUTION:** Do NOT automatically set an active pattern to `resolved` merely because no occurrences were seen for 14+ days. A safety hazard is never presumed resolved due to inactivity.
    - **Preservation Rule:** Preserve explicit `dismissed` or `resolved` states across sync cycles; do not revert them to `active`.
  - Upsert patterns into PostgreSQL `patterns` table idempotently.
- **Validation:** Python unit execution.
- **Acceptance Condition:** Service aggregates real event records into structured `Pattern` ORM instances with authoritative day-wise trends and strictly preserves pattern statuses.

---

### P13-003 — Integrate `PatternEngine` into Patterns API
- **Objective:** Ensure `GET /api/patterns` actively synchronizes and delivers real-time event patterns.
- **Files Involved:** [backend/app/api/patterns.py](file:///d:/SafeVision-AI/backend/app/api/patterns.py)
- **Dependencies:** P13-002
- **Implementation Details:**
  - Call `PatternEngine.sync_patterns(db, current_user.org_id)` on `GET /api/patterns`.
  - Derive `daily_trend` on `PatternResponse` directly from `pattern_data["daily_trend"]` at serialization time (Correction 4).
  - Preserve tenant isolation and pagination.
- **Validation:** Query `GET /api/patterns` with authenticated test token.
- **Acceptance Condition:** API response returns active recurring patterns backed by real events, with dynamically computed `daily_trend` derived from underlying event timestamps.

---

### P13-003A — Reconcile Legacy Seed Patterns
- **Objective:** Identify legacy Pattern records that have zero backing real Event records and safely mark them `dismissed` so they do not pollute the active Recurring Patterns view, without deleting any database rows.
- **Files Involved:** [backend/app/services/pattern_engine.py](file:///d:/SafeVision-AI/backend/app/services/pattern_engine.py), [backend/app/api/patterns.py](file:///d:/SafeVision-AI/backend/app/api/patterns.py)
- **Dependencies:** P13-002, P13-003
- **Implementation Details:**
  - During pattern synchronization, query all existing pattern records for `org_id`.
  - For each pattern, check if backing real events exist in the `events` table (matching `org_id`, `event_type`, and `camera.zone_id`).
  - For legacy seed patterns with zero backing real events:
    - **DO NOT DELETE:** Preserve database rows for audit history and referential integrity.
    - **SAFELY MARK DISMISSED:** Update `status = PatternStatus.DISMISSED`.
    - Annotate `pattern_data` with reconciliation metadata (e.g. `{"reconciled": True, "reason": "Legacy seed record with zero backing events"}`).
  - Ensure default active queries (`GET /api/patterns?status=active` and default view) exclude these dismissed seed patterns.
- **Validation:** Automated test in `backend/tests/test_pattern_engine.py` and direct SQL verification.
- **Acceptance Condition:** Stale seed records no longer pollute the active Recurring Patterns view. Direct check verifies $\text{COUNT}(\text{patterns WHERE status = 'active' AND backing\_real\_events == 0}) == 0$.

---

### P13-004 — Create Automated Tests for `PatternEngine`
- **Objective:** Write exhaustive automated test coverage for pattern generation, legacy reconciliation, and API contracts using database-driven assertions.
- **Files Involved:** `backend/tests/test_pattern_engine.py` (NEW)
- **Dependencies:** P13-002, P13-003, P13-003A
- **Implementation Details:**
  - **Dynamic Database-Driven Assertions (Correction 3):**
    - Assert `pattern.occurrence_count == COUNT(matching real events)`.
    - Assert `pattern.first_detected_at == MIN(matching event timestamps)`.
    - Assert `pattern.last_detected_at == MAX(matching event timestamps)`.
    - Assert `pattern.daily_trend == actual grouped event counts by day`.
  - **Legacy Seed Reconciliation Tests (Correction 2):**
    - Test that pattern records with zero backing events are marked `status = 'dismissed'`.
    - Verify orphan seed records are excluded from active pattern lists.
  - **Status Inactivity & Preservation Tests (Correction 1):**
    - Test that active patterns with zero events in 14+ days remain `status = 'active'` (never inferred resolved).
    - Test that explicitly `dismissed` or `resolved` patterns maintain their status across repeated syncs.
  - **Authoritative Daily Trend Tests (Correction 4):**
    - Test that top-level `daily_trend` and `pattern_data["daily_trend"]` match identically and derive from the same source.
  - **Threshold & Isolation Tests:**
    - Test recurrence threshold filtering (single isolated event does not create a pattern).
    - Test tenant isolation between Organization A and Organization B.
- **Validation:** `pytest backend/tests/test_pattern_engine.py`
- **Acceptance Condition:** All tests pass cleanly with 100% assertions satisfied against dynamic test data.

---

### P13-005 — Update Frontend API Types for Daily Trend
- **Objective:** Synchronize TypeScript interfaces with the backend schema.
- **Files Involved:** [frontend/src/lib/api-types.ts](file:///d:/SafeVision-AI/frontend/src/lib/api-types.ts)
- **Dependencies:** P13-001
- **Implementation Details:**
  - Add `daily_trend?: { date: string; occurrences: number }[] | null` to `PatternResponse`.
- **Validation:** `npx tsc --noEmit`
- **Acceptance Condition:** Zero TypeScript type errors.

---

### P13-006 — Implement "Trend Over Time" Recharts Visual Component
- **Objective:** Replace the static icon placeholder in the "Trend Over Time" card with an interactive Recharts chart.
- **Files Involved:** [frontend/src/routes/patterns.tsx](file:///d:/SafeVision-AI/frontend/src/routes/patterns.tsx)
- **Dependencies:** P13-005
- **Implementation Details:**
  - Import Recharts components (`AreaChart`, `Area`, `XAxis`, `YAxis`, `CartesianGrid`, `ResponsiveContainer`) and `ChartContainer`, `ChartTooltip`, `ChartTooltipContent` from `@/components/ui/chart`.
  - Extract authoritative `daily_trend` from `selected.daily_trend ?? selected.pattern_data?.daily_trend`.
  - Format X-axis dates cleanly (e.g. "Sep 4", "Sep 7").
  - Render an elegant branded gradient area chart.
  - Show a polished empty state when no pattern is selected or no trend data exists.
- **Validation:** Browser rendering test.
- **Acceptance Condition:** Real historical day-wise occurrences are visually plotted with responsive tooltips.

---

### P13-007 — Implement "Export Report" Client-Side CSV Handler
- **Objective:** Make the "Export Report" button fully functional.
- **Files Involved:** [frontend/src/routes/patterns.tsx](file:///d:/SafeVision-AI/frontend/src/routes/patterns.tsx)
- **Dependencies:** None
- **Implementation Details:**
  - Implement `handleExportReport` to format the current patterns list into CSV text:
    `"Pattern Title","Type","Zone","Occurrences","Confidence","Status","First Detected","Last Detected"`
  - Create a temporary blob URL and trigger download of `safevision-patterns-report.csv`.
  - Bind `onClick={handleExportReport}` to the Export button.
- **Validation:** Click button in browser and inspect downloaded file.
- **Acceptance Condition:** Browser immediately downloads a valid CSV file containing current pattern rows.

---

### P13-008 — Align Pattern Type and Status Filters
- **Objective:** Fix non-existent enum options and make filter controls intuitive.
- **Files Involved:** [frontend/src/routes/patterns.tsx](file:///d:/SafeVision-AI/frontend/src/routes/patterns.tsx)
- **Dependencies:** None
- **Implementation Details:**
  - Remove non-existent `"correlation"` option from the Pattern Type `<select>` dropdown.
  - Ensure options match valid enum types (`all`, `temporal`, `spatial`, `trend`, `rule_based`, `worker`).
  - Upgrade the "Status" control to an interactive `<select>` dropdown supporting `all`, `active`, `dismissed`, `resolved`.
- **Validation:** Select different filter combinations in the UI.
- **Acceptance Condition:** Filtering by type and status correctly filters the patterns list without returning empty screens or API errors.

---

### P13-009 — Execute Full Backend Test Suite & Health Check
- **Objective:** Verify overall backend stability.
- **Files Involved:** Backend test suite
- **Dependencies:** P13-004
- **Implementation Details:**
  - Run `pytest backend/tests/test_pattern_engine.py`.
  - Run `pytest backend/tests/test_phase10b_api.py`.
  - Run `pytest backend/tests/test_alert_engine.py`.
- **Validation:** Pytest summary report.
- **Acceptance Condition:** All backend tests pass with exit code 0.

---

### P13-010 — Execute Frontend TypeScript & Production Build Checks
- **Objective:** Verify client bundle compilation and strict typing.
- **Files Involved:** Frontend source tree
- **Dependencies:** P13-006, P13-007, P13-008
- **Implementation Details:**
  - Run `npx tsc --noEmit` in `frontend/`.
  - Run `npm run build` in `frontend/`.
- **Validation:** Command exit codes.
- **Acceptance Condition:** Both commands exit with code 0.

---

### P13-011 — Database Reality Verification
- **Objective:** Confirm PostgreSQL table reflects real, synchronized patterns using dynamic database comparisons.
- **Files Involved:** Database inspection script
- **Dependencies:** P13-009
- **Implementation Details:**
  - Query `patterns` table for the demo organization.
  - Evaluate dynamic database assertions (Correction 3):
    - `pattern.occurrence_count == COUNT(matching events in events table)`.
    - `pattern.first_detected_at == MIN(matching event timestamps)`.
    - `pattern.last_detected_at == MAX(matching event timestamps)`.
    - `daily_trend` matches SQL `GROUP BY cast(timestamp at time zone 'UTC' as date)`.
  - Verify legacy seed reconciliation (Correction 2):
    - All legacy seed pattern records with zero backing events have `status == 'dismissed'`.
    - Zero legacy seed records have `status == 'active'`.
- **Validation:** Direct SQL / ORM output inspection.
- **Acceptance Condition:** Pattern records strictly match dynamic database aggregates and all orphan seed patterns are marked dismissed.

---

### P13-012 — End-to-End Browser Acceptance Verification
- **Objective:** Perform UI acceptance in the live browser against actual database state.
- **Files Involved:** Browser at `http://localhost:8080/patterns`
- **Dependencies:** P13-010, P13-011
- **Implementation Details:**
  - Open `http://localhost:8080/patterns`.
  - Select an active recurring pattern in the Patterns List.
  - Verify that displayed occurrence count matches `COUNT(matching real events)` from the database at test time.
  - Verify that first detected and last detected dates in Pattern Details match database `MIN` and `MAX` event timestamps.
  - Verify that Trend Over Time chart renders data points matching the actual grouped event counts by day from the database.
  - Test hover tooltips on the chart.
  - Test Pattern Type and Status dropdown filters. Verify that legacy seed patterns do not appear when filtering by "Active".
  - Click "Export Report" and confirm CSV download contains the real pattern rows.
- **Validation:** Visual confirmation and screenshot/recording artifacts.
- **Acceptance Condition:** Complete browser acceptance criteria met with real data-driven patterns.

---

## Definition of Done

- [x] `backend/app/services/pattern_engine.py` created and operational.
- [x] `backend/app/schemas/pattern_schema.py` updated with `daily_trend`.
- [x] `backend/app/api/patterns.py` actively synchronizes real event patterns.
- [x] `P13-003A` implemented: legacy seed records with zero backing real events safely marked `dismissed` without deletion.
- [x] Stale seed records no longer pollute the active Recurring Patterns view.
- [x] `backend/tests/test_pattern_engine.py` created and passing.
- [x] Database-driven acceptance verification: assertions dynamically compare against actual `events` table (`COUNT`, `MIN`, `MAX`, `GROUP BY date`) with zero hard-coded counts or dates.
- [x] Strict status lifecycle enforced: only `active`, `dismissed`, `resolved`.
- [x] Inactivity never auto-resolves patterns: active status preserved regardless of elapsed time; only explicit human action or reconciliation transitions status.
- [x] Explicit `dismissed` and `resolved` states preserved across sync cycles.
- [x] Single authoritative representation used for daily trend (`pattern_data["daily_trend"]` projected to top-level `daily_trend` without duplication).
- [x] `frontend/src/lib/api-types.ts` updated with `daily_trend`.
- [x] `frontend/src/routes/patterns.tsx` renders real Recharts `AreaChart`.
- [x] `frontend/src/routes/patterns.tsx` "Export Report" generates CSV download.
- [x] `frontend/src/routes/patterns.tsx` filter dropdowns aligned with database enums.
- [x] Pattern identity strictly enforced as `(org_id, event_type, zone_id)`.
- [x] Recurrence threshold strictly enforced as `count >= 2`.
- [x] Zero database migrations created.
- [x] `npx tsc --noEmit` exits 0.
- [x] `npm run build` exits 0.
- [x] Pytest test suites exit 0.
- [x] Live browser acceptance confirms real patterns, charts, and details.
