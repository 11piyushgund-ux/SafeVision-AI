# Executive Summary  
SafeVision AI is envisioned as a **multi-tenant industrial safety intelligence platform** that continuously monitors workplaces via video to automatically detect and respond to safety risks.  It leverages real-time computer vision (YOLO-based detection of people, PPE items, fire, and smoke) **plus BoT-SORT tracking** and polygon zone models to understand each scene. Detected risks flow through a **safety rule engine** (e.g. “Helmet Required” or “Restricted Zone”) and **temporal validation** to confirm true violations. Confirmed *safety events* enter a **risk assessment** module to classify severity (LOW, MEDIUM, HIGH, CRITICAL), then an **alert engine** decides whether to create alerts. Alerts follow a state machine (NEW → ACKNOWLEDGED → ESCALATED → RESOLVED) and trigger notifications (in-app, email, WhatsApp). All events, alerts, users, and organizations are stored in a **PostgreSQL database** with strict tenant scoping. A concurrent **AI/RAG** subsystem provides grounded safety insights by retrieving relevant SOPs and rules from a knowledge base and querying a language model, without impacting core safety logic.

SafeVision’s architecture forms one coherent product, not disconnected modules. **Non-negotiable constraints**: the existing backend and CV pipeline must be preserved as-is (only extensions added); no fake data or duplicated functionality. The final system supports **real computer vision** (no synthetic detection), **real event flow**, and **real-time UI updates**, all with full role-based access control (RBAC) and tenant isolation (Organization A can never see B’s data). Security-by-design pervades the system (hashed passwords, secure tokens, input validation, rate limits, CORS, logging, audit trails). A clear multi-phase implementation roadmap – from repository inspection through testing, deployment, and monitoring – ensures production readiness. The following sections detail every component, data flow, API, and security control in depth.

## Project Overview and Goals  
SafeVision AI targets **industrial safety monitoring** by automating detection of PPE violations, fire, smoke, and unauthorized zone intrusions. Its goals are:  
- **Real-time detection and alerting**: Continuous camera streams feed the system, generating alerts within seconds of hazards (e.g. a person entering a **restricted zone** without gear). This is more proactive than manual or sensor-based methods.  
- **Multi-tenant SaaS**: Support multiple organizations (tenants) securely on one platform. Every resource (users, sites, cameras, events, documents) is scoped by organization. Rigorous tenant isolation ensures “A must never see B”.  
- **Extensible safety intelligence**: Beyond detection, SafeVision integrates with AI/RAG to provide contextual insights and preventive recommendations (e.g. pointing to a relevant SOP) while ensuring no hallucinated facts leak through.  
- **Auditability and compliance**: Every critical action (logins, alert acknowledgments, config changes) is logged. Reports and evidence (video snapshots) support safety audits and incident investigations. For example, similar systems auto-generate OSHA logs and track near-misses.  
- **Modular, maintainable design**: The existing core backend (authentication, data models, APIs, CV pipeline) is **the source of truth**. We only *extend*, not rewrite it. This preserves proven functionality (e.g. existing YOLO inference) and avoids two diverging codebases.  

## Non-Negotiable Constraints  
1. **Preserve the existing backend/CV core:** All current services, routes, models, and database schemas must remain intact and continue working. We may only *add* or *extend*. No architecture overhaul or duplicate system.  
2. **Real CV, no fakes:** The system must operate on *real* camera feeds and produce genuine alerts. The backend’s YOLO-based pipeline and BoT-SORT tracking remain authoritative; the frontend only displays their output. No demo data or hardcoded charts.  
3. **Strict multi-tenancy:** Every operation must verify the user’s organization context. Do not trust any organization_id or resource ID from the client without backend checks.  
4. **Security by default:** Follow least-privilege and defense-in-depth. Inputs are validated; secrets are protected; all state transitions check permissions; audit logs cover sensitive actions.  
5. **Consistency:** The final product must feel like *one* platform. The frontend UI, realtime data, and analytics all reflect the single integrated backend. UI actions (e.g. “Acknowledge Alert”) call the secured backend APIs to change state.

## System Architecture and Data Flow  

```mermaid
flowchart LR
    subgraph Cameras
        C[Camera Streams] 
    end
    subgraph CV
        direction TB
        D[YOLO Detection: Person/PPE/Fire/Smoke]
        T[BoT-SORT Tracking]
        Z[Polygon Zone Evaluation]
        R[RULE Engine (PPE/Zone rules)]
        V[Temporal Validation]
        E[Safety Event Engine]
    end
    subgraph Backend
        BDB[(PostgreSQL Database)]
        Rk[Risk Engine]
        A[Alert Engine]
        N[Notification Service]
        AI[AI / RAG Engine]
    end
    subgraph Frontend
        UI[Dashboard & Views]
    end

    C --> D 
    D --> T
    T --> Z
    Z --> R
    R --> V
    V --> E
    E --> Rk
    Rk --> A
    A --> N
    E --> BDB
    A --> BDB
    BDB --> UI
    N --> UI
    AI -- Insights --> UI
```

*Figure: SafeVision AI data flow (camera → CV pipeline → safety event → risk/alert → notifications/dashboard).*

- **Video Ingestion (Cameras):** IP cameras (including PTZ/thermal) stream real-time video to the inference service. In industrial settings, ruggedized cameras with IR/thermal modes cover large zones.

- **YOLO Detection:** Each frame is processed by one or more trained models (e.g. a PPE model for person+gear, a separate model for fire/smoke). The model outputs detections with classes (person, helmet, vest, fire, smoke, etc.) and confidence scores.  

- **BoT-SORT Tracking:** Detected objects are passed to BoT-SORT to assign persistent track IDs. This lets us link detections across frames, preventing duplicate events (e.g. one person remains id=17) and measuring how long a violation persists.

- **Polygon Zone Evaluation:** Each tracked person’s position is tested against configured polygonal zones (assembly areas, restricted areas, etc.). Polygons are stored in the DB (see schema). A “zone context” (which zone(s) a person is in) is appended to each track.

- **Safety Rule Engine:** For each track, compare detected gear to zone requirements. Example: Zone “Assembly” may require [helmet, vest, gloves]; if a tracked person lacks any required item, generate a “PPE_VIOLATION” event. Similarly, entering a zone marked “restricted” triggers a “RESTRICTED_ZONE” violation.

- **Temporal Validation & De-duplication:** Rather than creating an event each frame, enforce persistence. For example, require 3 consecutive frames of missing helmet before confirming a PPE_VIOLATION. Once an event is created for a track, suppress duplicates until conditions reset. This reduces false positives and spam.

- **Safety Event Engine:** Confirmed violations become *Safety Events* (entities stored in the database). Each event record includes organization, site, zone, camera, track ID, type, confidence, timestamp, status, etc. For instance, an event might be:  
  ```json
  {
    "event_id": "evt-1234",
    "organization_id": "org-456",
    "site_id": "site-789",
    "zone_id": "zone-321",
    "camera_id": "cam-101",
    "type": "PPE_VIOLATION",
    "severity": "MEDIUM",
    "confidence": 0.95,
    "timestamp": "2025-07-01T12:34:56Z",
    "details": {"missing_ppe": ["gloves","goggles"], "track_id": 17}
  }
  ```  
  *(Example payload; actual schema per DB.)*

- **Risk Assessment:** The risk engine evaluates each new event against configurable factors (zone criticality, past history, event type, confidence, duration). It assigns a risk score or level (e.g. HIGH for smoke or repeated PPE violations). Risk logic is deterministic and parameterized.

- **Alert Engine:** Based on risk and organization policies, decide if an alert should be raised. E.g. all CRITICAL events immediately raise alerts; MEDIUM/LOW might be logged only. Alerts link to events (an alert may group related events). They have fields like severity, status (NEW/ACK/ESCALATED/RESOLVED), assigned user, timestamps, etc.

- **Notification Service:** When alerts are created or updated, notify relevant personnel. An alert might trigger in-app notifications, emails, and WhatsApp messages via provider adapters. Delivery attempts and failures are logged. For example:  
  ```json
  {
    "notification_id": "noti-987",
    "alert_id": "alert-654",
    "channel": "EMAIL",
    "recipient": "supervisor@acme.com",
    "status": "SENT",
    "sent_at": "2025-07-01T12:35:00Z"
  }
  ```  

- **Database and History:** All events and alerts (with their lifecycle changes) are persisted. A relational schema (PostgreSQL) ties each record to an organization. Historical data fuels dashboards, reports, and the recurring-pattern analysis module.

- **Dashboard/Frontend:** Clients connect to the backend via REST and WebSockets. The live dashboard shows camera views with overlayed detections, active events, trends, and KPI charts, all driven by real backend data (no mocks). State changes (new alerts, acknowledged alerts, pattern detections) are pushed via real-time channels and update the UI.

- **AI/RAG Engine:** Parallel to core operations, an AI service generates insights and recommendations. When a user views an alert or event, the system can query an LLM with context (event details, related history, SOP documents) via a Retrieval-Augmented Generation pipeline. The LLM returns analysis like “The worker entered a high-risk area without gloves – recommend reinforcing glove compliance training.” These AI outputs cite knowledge sources and are clearly marked as suggestions. If the AI fails or returns nothing, the core alerts still stand unaffected.

## Component Inventory  

### Backend Services (Existing & Extensions)  
- **Authentication Service:** Manages login, JWT/session issuance, and user credentials (hashed).  
- **Tenant/Org Service:** Manages organizations; ensures each resource is linked to an `organization_id`. (REQUIRES INSPECTION of existing models.)  
- **User/Access Control:** User management, roles, permissions. Implements RBAC checks on every action.  
- **Site, Zone, Camera Services:** CRUD APIs and models for physical sites, polygon zones, cameras (with source config). Each zone has metadata and safety rules. Cameras link to zones.  
- **Safety Rule Service:** Configurable rules per organization/zone (e.g. required PPE lists, restricted zones).  
- **Detection/Tracking Service:** The existing CV service that ingests frames, runs YOLO models, and BoT-SORT. (We do *not* replace this; only extend its outputs.) Outputs structured detection payloads to the event engine.  
- **Event Engine:** Validates raw detections, applies rules, checks persistence, and creates **Safety Event** records.  
- **Risk Engine:** Evaluates events to assign risk/severity. Possibly a pluggable strategy to compute risk score.  
- **Alert Engine:** Listens for new high-risk events, creates **Alert** records (with state NEW). Manages alert state transitions (ACK, ESCALATE, RESOLVE).  
- **Notification Service:** Reads alerts, generates and dispatches notifications via adapters. Channels include In-App (websocket/inbox), Email (SMTP or third-party), and WhatsApp API. Logs delivery results and retries on failures.  
- **AI / RAG Service:** Coordinates AI analysis.  
  - **Context Builder:** Gathers relevant data (current event, similar past events, safety rules, organizational SOPs).  
  - **Retriever:** Queries a knowledge store of documents (indexed per org) to find relevant chunks.  
  - **LLM Adapter:** Sends a structured prompt (user question plus retrieved context) to an LLM endpoint.  
  - **Result Handler:** Saves the insight and references. (Example: “AI_Insight” record linked to event.)  
- **Recurring Pattern Service:** Runs periodic analytics on historical events to detect trends/patterns (e.g. repeated violations in the same zone over 7-day windows).  
- **Report Generation Service:** Exports filtered data to CSV/PDF on demand (with auth).  
- **Audit Service:** Records critical operations (login attempts, permission changes, camera edits, alert actions, report exports).  
- **Database & Migrations:** PostgreSQL with Alembic (or equivalent) for schema management.  
- **Background Workers:** Task queue for async jobs (notifications, AI calls, report exports, evidence processing, pattern analysis).  

### Computer Vision Pipeline (Existing)  
- **Models:** Pretrained YOLO models (and/or vision transformers) for PPE detection and separate models for fire/smoke. The PPE model outputs classes {person, helmet, vest, gloves, goggles, boots}. The fire model outputs {fire, smoke}.  
- **Confidence Thresholds:** Detections include confidences; configurable thresholds filter noise (e.g. only consider >70%). *For example, one system requires >95% confidence to trigger compliance checks.*  
- **Frame Rate:** Real-time (≥10fps) inference. Models are loaded in memory and run on GPU/accelerator to avoid latency.  

### Tracking & Zone Logic  
- **BoT-SORT:** Preserves object identities across frames. Tracks have IDs, bounding boxes, timestamps.  
- **Zone Polygons:** Each zone’s polygon is stored (array of coordinates) in the DB. Polygon math (point-in-poly) determines if track centroids enter zones.  
- **Zone Metadata:** Zones have types (e.g. “Assembly”, “Restricted”, “High Risk”), and reference which PPE is required or if entry is forbidden.  

### Frontend Inventory  
- **Screens/Routes:**  
  - **Login/Authentication.**  
  - **Dashboard** (overview metrics, charts, map).  
  - **Live Monitoring** (grid of camera feeds with overlays, status).  
  - **Alerts Page** (list of active alerts with filters).  
  - **Alert Details** (view one alert, event info, evidence, AI insight, actions).  
  - **Event History** (searchable log of past events).  
  - **Recurring Patterns** (analytics on repeat violations).  
  - **Safety Intelligence** (AI insights hub).  
  - **Management** (admin pages for Orgs, Sites, Zones, Cameras, Users, Roles, Rules, Documents).  
  - **Reports** (export interface).  
  - **Notifications Center** (in-app inbox).  

- **Components:** Reusable UI building blocks: tables, forms, charts (bar, line, pie), maps/polygons, video players, overlay canvases, status badges, modals, filters, date-pickers. Example components: `AlertTable`, `EventCard`, `CameraGrid`, `DetectionOverlay`, `ZoneLayer`, `RiskBadge`, `AIInsightCard`, etc.

- **State Management:** Likely a client-side store (e.g. Redux or Context). Separate slices for auth (user/org/permissions), alerts, events, camera statuses, dashboard data, patterns, AI insights. UI controls (filters, selected camera) are local state. Data fetched via service hooks.

- **Routing:** Authenticated routes vs public (login). Routes mirror API resources (e.g. `/alerts`, `/cameras/1`, `/patterns`, `/admin/users`). Guards prevent unauthorized access (redirect to login).

- **API Layer:** Centralized HTTP client (e.g. using Axios or Fetch). Services for each area (AuthService, AlertsService, EventsService, PatternsService, AIService, ManagementService). Handles base URL, auth headers (JWT), error handling.  

- **Real-Time Subscriptions:** WebSockets or Server-Sent Events provide push updates. The client subscribes after login using the session token. Listens for events like NEW_ALERT, ALERT_UPDATED, CAMERA_STATUS, etc., filtered by organization. On connection loss, retry. A visual indicator shows live/offline status.

## API Contract Catalog  

| Endpoint                        | Method | Auth            | Permissions Req.     | Request Parameters / Body                     | Response                          | Errors              |
|---------------------------------|--------|-----------------|----------------------|-----------------------------------------------|-----------------------------------|---------------------|
| **POST /auth/login**            | POST   | –               | –                    | `{ "username": "", "password": "" }`          | `{ "token": "", "user": {...} }`   | 401 Invalid creds   |
| **GET /users**                  | GET    | Bearer token    | `users.view`         | `?org_id={org}&page=1&size=50`                | `{ data:[users], pagination:{...} }` | 403, 500           |
| **POST /users**                 | POST   | Bearer token    | `users.manage`       | `{ "name": "", "email": "", "role_id": "" }`  | `{ "id": "user123", ... }`        | 400,403            |
| **GET /sites**                  | GET    | Bearer token    | `sites.view`         | `?org_id={org}`                              | `{ data:[sites], ...}`            | 403, 500           |
| **GET /zones**                  | GET    | Bearer token    | `zones.view`         | `?site_id={site}`                            | `{ data:[zones], ...}`            | 403, 500           |
| **POST /zones**                 | POST   | Bearer token    | `zones.manage`       | `{ "site_id":"", "name":"", "polygon":[[x,y],...], "rules":{...} }` | `{ "id":"zone123", ...}` | 400,403           |
| **GET /cameras**                | GET    | Bearer token    | `cameras.view`       | `?site_id={site}`                            | `{ data:[cameras], ...}`          | 403, 500           |
| **POST /cameras**               | POST   | Bearer token    | `cameras.manage`     | `{ "site_id":"", "zone_id":"", "name":"", "source_config":{...} }` | `{ "id":"cam456", ...}`| 400,403 |
| **GET /events**                 | GET    | Bearer token    | `events.view`        | `?org_id={org}&page=...&type=...&risk=...&from=...&to=...` | `{ data:[events], ...}` | 403, 500 |
| **GET /events/{id}**            | GET    | Bearer token    | `events.view`        | Path param `id`                              | `{ "id":"evt123", ...}`           | 403,404            |
| **GET /alerts**                 | GET    | Bearer token    | `alerts.view`        | `?org_id={org}&status=...&risk=...&site=...&page=...` | `{ data:[alerts], ...}`| 403,500 |
| **GET /alerts/{id}**            | GET    | Bearer token    | `alerts.view`        | Path param `id`                              | `{ "id":"alert789", ...}`         | 403,404            |
| **POST /alerts/{id}/acknowledge** | POST | Bearer token    | `alerts.acknowledge` | `{ "resolution_notes": "" }`                | `{ "status":"ACKNOWLEDGED" }`     | 400,403,409       |
| **POST /alerts/{id}/escalate**    | POST | Bearer token    | `alerts.escalate`    | `{ "to_role": "" }`                         | `{ "status":"ESCALATED" }`        | 400,403,409       |
| **POST /alerts/{id}/resolve**     | POST | Bearer token    | `alerts.resolve`     | `{ "resolution_notes": "" }`                | `{ "status":"RESOLVED" }`         | 400,403,409       |
| **GET /patterns**               | GET    | Bearer token    | `patterns.view`      | `?org_id={org}&type=...&from=...&to=...`     | `{ data:[patterns], ...}`         | 403,500           |
| **GET /intelligence/insights**  | GET    | Bearer token    | `ai.view`            | `?alert_id={id}`                            | `{ data:[insights], ...}`         | 403,500           |
| **GET /notifications**          | GET    | Bearer token    | `notifications.view` | `?user_id={self}&status=...`                | `{ data:[notifications], ...}`    | 403,500           |
| **POST /reports/export**        | POST   | Bearer token    | `reports.export`     | `{ "type": "", "filters": {...} }`          | `{ "job_id": "job123" }`          | 400,403,500       |

*Table: Representative API endpoints. All endpoints require authentication (Bearer token). `{org_id}` and `{user_id}` are server-resolved from the session unless explicitly filtering; do not trust client-supplied org IDs. Pagination (`page,size`) and filtering (`site_id, zone_id, event_type, risk_level`) are supported. Errors include 400 (bad request), 401 (unauth), 403 (forbidden), 404 (not found), 409 (invalid state), and 500 (server error).*

## Database Schema Overview  

| Table               | Key Fields                          | Indexes/Keys                 | Tenant Scope                               |
|---------------------|-------------------------------------|------------------------------|--------------------------------------------|
| **organizations**   | `id` (PK), `name`, `slug`, `status` | PK, unique(name), unique(slug) | – (root)                                  |
| **users**           | `id`, `org_id` (FK), `email`, `role_id`, `status`, `pwd_hash` | PK, FK(org_id), index(email) | scope by `org_id` (FK → organizations)     |
| **roles**           | `id`, `name`                        | PK, unique(name)             | – (global or per-tenant if using scoped roles) |
| **permissions**     | `id`, `role_id` (FK), `perm_name`   | PK, FK(role_id)              | roles are mapped to org or global          |
| **sites**           | `id`, `org_id` (FK), `name`, `address`, `timezone` | PK, FK(org_id)              | Tenant: org_id                            |
| **zones**           | `id`, `site_id` (FK), `name`, `type`, `polygon` (JSON array of coords), `required_ppe` (JSON list), `status` | PK, FK(site_id) | Indirect tenant: via site → org_id         |
| **cameras**         | `id`, `site_id` (FK), `zone_id` (FK), `name`, `source_config`, `status` | PK, FK(site_id), FK(zone_id) | Indirect tenant via site                 |
| **safety_rules**    | `id`, `org_id` (FK), `zone_id` (FK), `type`, `parameters` (JSON) | PK, FK(org_id), FK(zone_id) | org_id                                    |
| **events**          | `id`, `org_id` (FK), `site_id`, `zone_id`, `camera_id`, `event_type`, `risk_level`, `confidence`, `track_id`, `status`, `timestamp` | PK, FK(org_id), FK(site_id), FK(camera_id), index(event_type) | org_id, indexes on timestamps, types |
| **alerts**          | `id`, `org_id` (FK), `event_id` (FK), `severity`, `status`, `created_at`, `ack_user`, `ack_at`, `res_user`, `res_at` | PK, FK(org_id), FK(event_id), index(status), index(severity) | org_id                                  |
| **alert_states**    | *Audit trail of alerts* (optional)  | (id, alert_id, prev_status, new_status, user, timestamp) | org_id via alert → org_id                |
| **ai_insights**     | `id`, `org_id` (FK), `event_id` (FK), `insight`, `recommendation`, `confidence`, `source_refs`, `created_at` | PK, FK(org_id), FK(event_id) | org_id                                  |
| **notifications**   | `id`, `org_id`, `alert_id`, `user_id`, `channel`, `destination`, `status`, `attempted_at`, `delivered_at`, `retries` | PK, FK(org_id), FK(alert_id), FK(user_id), index(status) | org_id via alert                           |
| **patterns**        | `id`, `org_id`, `pattern_type`, `description`, `frequency`, `first_seen`, `last_seen`, `recommendation` | PK, FK(org_id), index(pattern_type) | org_id                                  |
| **audit_logs**      | `id`, `org_id`, `user_id`, `action`, `resource`, `resource_id`, `timestamp`, `details` | PK, FK(org_id), FK(user_id), index(timestamp) | org_id                                |
| **(others)**        | *e.g. reports, user_preferences, etc.* |                              |                                        |

*Table: Core database tables. Every organization-owned table includes an `org_id` or is linked via an `org_id` foreign key for strict tenant isolation. Unique constraints and foreign keys ensure data integrity. Indexes on common queries (e.g. events by org/time) will improve performance. Use transactions on multi-step operations (e.g. creating an alert and its history) to avoid partial failure.*

## Computer Vision Integration Contract  

- **Detection Payload:** Each camera push or CV job emits JSON with detections and optionally tracking IDs. For example:  
  ```json
  {
    "camera_id": "cam-001",
    "timestamp": "2025-07-01T12:34:56Z",
    "detections": [
      { "class": "person", "confidence": 0.97, "bbox": [100,200,180,350], "track_id": 17 },
      { "class": "helmet", "confidence": 0.93, "bbox": [110,210,150,250], "track_id": 17 },
      { "class": "gloves", "confidence": 0.88, "bbox": [120,300,160,340], "track_id": 17 }
    ]
  }
  ```  
  The `bbox` is `[x1,y1,x2,y2]` pixel coordinates. `track_id` links PPE items to a person track.  
- **Tracking:** BoT-SORT ensures a stable `track_id` per person. The system should treat the combination of (camera_id, track_id) as identifying a single worker over time.  
- **Zone Format:** Zones are polygons stored as arrays of [x,y] points (e.g. `[[0,0],[100,0],[100,50],[0,50]]` for a rectangle). The integration uses point-in-polygon tests on track centroids.  
- **Evidence Storage:** For qualifying events (e.g. first frame of a violation), the CV system or backend should capture an image snapshot. This becomes `evidence_reference` (e.g. an object store URI or database blob ID) saved in the event record. Access to evidence is via a secure endpoint – clients use time-limited signed URLs or authenticated fetches so raw paths are never exposed publicly.  
- **Model Metadata:** Each detection can optionally include model info (e.g. `"model": "PPEv3", "version": "1.2.3"`). At minimum, log the model and version used for future auditing or debugging.  

## Event and Alert Lifecycle  

1. **Detection → Tentative Event:** When CV outputs indicate a possible violation (e.g. missing PPE in Zone), the Event Engine queues a *tentative* event.  
2. **Validation & Persistence:** After required persistence (e.g. 3 frames of missing item), promote to a *Safety Event* record (status=OPEN) in the DB. This record is immutable once created except to update status (e.g. CLOSED after resolution).  
3. **Risk Scoring:** The Risk Engine evaluates the event and updates it with a `risk_level` (LOW/MEDIUM/HIGH/CRITICAL).  
4. **Alert Creation:** If policy dictates, an Alert record is created referencing the event. The alert has `status=NEW`, `severity` (mapped from risk), and a human-readable `title/description`.  
5. **Acknowledge:** A user with `alerts.acknowledge` permission can POST `/alerts/{id}/acknowledge`. Backend checks the user’s role and that the alert is currently NEW. If valid, it sets `status=ACKNOWLEDGED`, logs `ack_user`, `ack_at`, and appends an audit log.  
6. **Escalate:** From ACKNOWLEDGED, a user with `alerts.escalate` may escalate. The API sets `status=ESCALATED`, records `res_user` (the escalator), `escalated_at`, and audit log.  
7. **Resolve:** Finally, an authorized user may resolve an alert: set `status=RESOLVED`, record `res_user`, `res_at`, and notes.  
8. **Audit Trail:** Every state change (ACK, ESC, RES) is recorded in `alert_states` or audit_logs, including who and when. This satisfies accountability.  

```mermaid
flowchart LR
    A[Detection] -->|PPE/Zone rule check| B[Tentative Violation]
    B -->|Temporal confirm| C[Safety Event Created]
    C -->|Risk Score| D[Evaluate Risk]
    D -->|Trigger Alert?| E{Risk ≥ threshold?}
    E -->|No| C
    E -->|Yes| F[Alert Created (NEW)]
    F -->|Acknowledge| G[ACKNOWLEDGED]
    F -->|Escalate| H[ESCALATED]
    G -->|Resolve| I[RESOLVED]
    H -->|Resolve| I
```

*Figure: Event and Alert lifecycle with key transitions. All transitions enforce authentication, check that the acting user’s role permits that action, and log an audit entry.*

## RBAC and Tenant Isolation  

- **Roles:** Define roles such as *Organization Administrator*, *Safety Manager*, *Safety Supervisor*, *Safety Officer*, *Operator*, *Viewer*. Roles map to permission sets.  
- **Permissions:** Granular flags control actions, e.g.:  
  - `dashboard.view`, `monitoring.view`  
  - `events.view`, `alerts.view`, `alerts.acknowledge`, `alerts.escalate`, `alerts.resolve`  
  - `patterns.view`, `patterns.manage`  
  - `reports.export`  
  - `cameras.view`, `cameras.manage`  
  - `zones.view`, `zones.manage`  
  - `users.view`, `users.manage`, `roles.manage`  
  - `rules.view`, `rules.manage`  
  - `ai.view`, `ai.manage`, `rag.manage`  
  - `notifications.manage` (e.g. config channels).  

- **Permission Matrix:** (Example)  

  | Action                | OrgAdmin | SafetyMgr | SafetyOff | Operator | Viewer |
  |-----------------------|:--------:|:---------:|:---------:|:--------:|:------:|
  | users.manage          | X        |           |           |          |        |
  | sites.manage          | X        |           |           |          |        |
  | zones.manage          | X        | X         |           |          |        |
  | cameras.manage        | X        | X         |           |          |        |
  | rules.manage          | X        | X         |           |          |        |
  | alerts.acknowledge    | X        | X         | X         | X        |        |
  | alerts.escalate       | X        | X         | X         |          |        |
  | alerts.resolve        | X        | X         |           |          |        |
  | events.view           | X        | X         | X         | X        | X      |
  | reports.export        | X        | X         |           |          |        |
  | ai.view               | X        | X         | X         | X        | X      |
  | ai.manage             | X        |           |           |          |        |

  *(Permissions are illustrative. The backend enforces all checks server-side.)*

- **Tenant Isolation:** For every request, middleware extracts the user’s organization from the auth token. The backend must filter all data by that `org_id`. For instance, `SELECT * FROM alerts WHERE id=? AND org_id=?`. This prevents IDOR vulnerabilities. Even for multi-tenant queries (e.g. list all alerts), add `WHERE org_id=currentOrg`. Per OWASP guidance, client-submitted IDs are only selectors; always verify the authenticated user has membership in that tenant.

## Real-Time Architecture and Security  

- **Transport:** Use WebSockets (or SSE) for live updates. Upon login, the client establishes a secure WebSocket connection (authenticated via the JWT). The server validates the token and subscribes the client to channels for that user’s org.  
- **Event Types:** Define message types, e.g. `NEW_ALERT`, `ALERT_UPDATED`, `EVENT_CREATED`, `CAMERA_STATUS`, `MONITOR_OFFLINE`, `AI_INSIGHT`. Payloads carry minimal info (e.g. new alert ID); the client can then fetch details if needed.  
- **Tenant Filtering:** The backend only emits events to clients in the same org. No global broadcasts.  
- **Reconnection:** The client handles disconnection (e.g. show “Live: Offline” state) and retries. On reconnect, a sync snapshot can be fetched (e.g. missed alerts).  
- **Example:** When a new critical alert arises, the server sends:  
  ```json
  { "type": "NEW_ALERT", "payload": { "alert_id": "alert-789", "severity": "CRITICAL" } }
  ```  
  The client listens and increments the alert counter and highlights the new alert.

## AI/RAG Pipeline  

- **Context Building:** For an AI query (e.g. user asks “Why this alert?”), collect structured context: alert/event details, zone and camera info, recent similar events (same type/zone), defined rules, and organization-specific documents (SOPs, training guides). Only include data the user is authorized to see (same org).  
- **Retrieval:** Query the knowledge base (vector or keyword search) scoped to the org. For example, find SOPs on “PPE requirements” or the org’s safety manual.  
- **Prompt Assembly:** Combine context and retrieved text into a prompt template (system instructions + user question). Example:  
  ```
  System: You are a safety advisor AI. Based on the following facts, explain likely causes and recommendations. 
  Facts: [PPE violation event: missing gloves in Assembly Zone... Relevant rule: Helmets, gloves required in Assembly Zone...] 
  Knowledge: [excerpt from safety SOP on PPE, excerpt from OSHA guidelines] 
  Question: Why did this incident occur and how to prevent it? 
  ```  
- **LLM Call:** Send to a backend LLM (local or cloud). Limit length to avoid cost.  
- **No-Hallucination:** Since the LLM is grounded on provided facts, it should only output inference and suggestions. We must not trust it for new “events” or facts. If it seems unsure, it should say so (e.g. “Based on records, it appears…”).  
- **Tenant Safety:** Ensure the LLM **only sees authorized data**. According to best practices, do *not* feed the LLM any cross-tenant information. Use adversarial testing to check prompt security.  
- **Versioning:** Tag insights with the model and retrieval version. Log the used prompt and sources. This aids auditability and iterative improvement.  
- **Fallback:** If the LLM or retrieval fails, do not block the system. We simply show no AI insight. The core safety alerts remain valid regardless of AI status.

## Notification Workflow and Providers  

- **Policy:** Each organization configures who should be notified for which alert types. For example, a CRITICAL alert to Safety Manager + Supervisor via email+SMS.  
- **Channels:**  
  - *In-App:* A notification table entry is created and a WebSocket event sent to the user.  
  - *Email:* Using an SMTP or API (SendGrid, SES) provider, send HTML/text.  
  - *WhatsApp:* Via a WhatsApp Business API or Twilio integration for urgent alerts.  
- **Delivery:** Notifications are queued in the DB. A worker dequeues them and attempts delivery. Successes update `delivered_at`; failures record error and retry count. Retry policy (e.g. up to 3 times with backoff) is used. Critical alerts can escalate retry to a human admin if external channels fail.  
- **Logging:** Each attempt is logged. The notifications table captures status and errors for audit. This ensures alert data is never lost even if email/WhatsApp is down.

## Evidence and Secret Handling  

- **Camera Credentials:** Store in backend (encrypted). Never send raw RTSP/credentials to browser. For streaming, use a backend proxy or tokenized URL if needed (e.g. short-lived HLS URL).  
- **Evidence Images:** When capturing frames, store them in a secured blob store (e.g. S3 with private bucket). Provide the frontend a signed URL (expiring link) or a protected API route that streams the image after verifying user’s auth/org. Example in alert detail:  
  ```json
  {
    "alert_id": "alert-789",
    "evidence_url": "https://api.safevision.ai/evidence/alert-789?token=eyJhbGci..."
  }
  ```  
- **Secrets:** Use environment variables or a secrets manager for all sensitive keys (DB passwords, JWT_SECRET, API keys). Never commit real secrets. Provide an example `.env.sample`. Rotate any found leaked secrets.  

## Testing Plan and Acceptance  

- **Unit Tests:** For each module/service (e.g. rule engine, risk calculations, API handlers), write unit tests covering normal and edge cases.  
- **Integration Tests:** Simulate flows via APIs. Examples: detect a PPE violation and verify an event+alert is created. Call the alert acknowledgment endpoint and check DB changes and audit log.  
- **End-to-End Tests:** Automate scenarios (using tools like Selenium or Postman/Newman):  
  - **Scenario 1 (PPE Violation):** Simulate camera sending missing-helmet frames → event → HIGH alert → UI shows alert → user ACK → state updates.  
  - **Scenario 2 (Fire Event):** Simulate fire detection → event CRITICAL → auto-alert to safety team → evidence captured → alert shown.  
  - **Scenario 3 (Restricted Zone):** Person enters zone → event → alert → pattern analysis notes repeat intrusions.  
  - **Multi-Tenancy:** Create OrgA and OrgB with separate data. Login as OrgA user and verify attempts to access OrgB records (via UI and direct API) fail (403 or not found). Repeat for OrgB.  
  - **Security:** Test invalid/malformed inputs (SQLi attempts, invalid IDs), expired JWT, CORS, rate limits. Ensure no leaks.  
  - **AI/RAG:** Test that AI does not expose other-org data; if no SOP is found, response indicates unknown.  
  - **WebSockets:** Simulate connection drop and recovery; ensure UI updates after reconnect.  
- **Performance:** Benchmark CV throughput, API response times, DB query speeds on expected load.  
- **Acceptance:** The system meets the checklist: real CV models running, RBAC enforced, real-time updates, tenant isolation, no sensitive leaks, etc.

## Implementation Roadmap (Phased)  

| Phase | Focus                                                | Deliverables                                              | Estimate    |
|-------|------------------------------------------------------|-----------------------------------------------------------|-------------|
| **1. Inspect & Map**    | Audit existing repo (backend + frontend)                          | Architecture map, functionality inventory, gap list       | 1 week      |
| **2. Core Stability**   | Preserve all existing features; write regression tests            | Test suites covering current APIs and flows              | 1 week      |
| **3. Auth/RBAC/Tenancy**| Ensure auth middleware, JWT, org context are airtight             | Tenant-aware middleware, enhanced access checks          | 1 week      |
| **4. Data Models**      | Review/extend DB schema as needed (PPE requirements, RAG tables)   | Alembic migrations for new fields/tables; models updated | 1 week      |
| **5. Safety Rules**     | Implement configurable rules per zone (PPE lists, restricted zones) | Rule engine service and APIs                             | 1 week      |
| **6. CV Pipeline Int.** | Integrate detection outputs with event engine (already partially done) | Connection between CV service and event creation         | 1 week      |
| **7. Event Engine**     | Complete creation of SafetyEvent records (validation, de-dup)      | Event DB records, unit tests                             | 1 week      |
| **8. Risk Engine**      | Add configurable risk scoring logic                              | Risk-level assignment code and tests                      | 1 week      |
| **9. Alert Engine**     | Implement alert creation and state transitions (ACK, ESC, RES)    | Alert APIs, lifecycle management, unit tests             | 1 week      |
| **10. Notifications**   | Build notification adapter framework (in-app, email, WhatsApp)     | Notification table, background jobs, email/whatsapp impl. | 1 week      |
| **11. Frontend API**    | Connect frontend screens to real APIs (dashboard, monitoring)      | Replace static mock data with API calls; error/loading states | 2 weeks  |
| **12. Live Monitoring** | Integrate real-time overlays from CV: render bounding boxes & status | WebSocket client, overlay components                     | 1 week      |
| **13. Alerts UI**       | Hook up Alerts page to backend (filters, actions)                  | API hooks, filter form, action modals                    | 1 week      |
| **14. Event History**   | Connect history page with backend (pagination)                     | API query params, date pickers                           | 1 week      |
| **15. Patterns UI**     | Implement recurring patterns API + dashboard charts                | PatternsService, charts component                        | 1 week      |
| **16. AI Insights UI**  | Display AI/RAG results per event (or tab)                          | IntelligenceService, chat/card UI                        | 1 week      |
| **17. Management UI**   | CRUD UIs for Orgs, Users, Sites, Zones, Cameras, Rules, etc.       | Forms with validation, dropdowns, etc.                   | 2 weeks     |
| **18. Security Hardening** | Add rate limiting, CORS config, input validation globally        | API middleware, config changes                           | 1 week      |
| **19. Audit Logging**   | Ensure all actions write to audit logs                             | DB table + log calls in services                         | 1 week      |
| **20. Observability**   | Add structured logging, metrics endpoints, health checks           | Log format, `/health` API, Prometheus metrics            | 1 week      |
| **21. AI/RAG Implementation** | Hook up RAG pipeline (doc store, LLM calls)                   | RAG index, prompt templates, insight saving              | 2 weeks     |
| **22. Testing & QA**    | Automated test suite (unit/integration/e2e)                       | CI pipeline, test reports                                | 2 weeks     |
| **23. Deployment Prep** | Containerize services, setup DB migrations, environment vars       | Dockerfiles, helm chart or compose, docs                 | 1 week      |
| **24. Performance Tuning** | Load test pipeline end-to-end, optimize queries               | DB indexing, caching, scale config                       | 1 week      |
| **25. Documentation**   | Write API docs, runbooks, architecture notes                      | Markdown docs, swagger, operational guides               | 1 week      |
| **26. Final Audit & Review** | Security pen-test, review checklist                          | Formal sign-off checklist                                | 1 week      |

*(Timeline estimates assume dedicated engineering resources; adjust per team size.)*

## Security Hardening Checklist  

- **Authentication**: Use strong password hashing (bcrypt/argon2). JWT tokens signed with secure secret, validate expiry.  
- **Authorization**: Enforce RBAC on every endpoint. Never rely on client-supplied org or role.  
- **Input Validation**: Rigorously validate all user inputs (body, query, path). Reject invalid IDs, too-large payloads, unsafe content.  
- **SQL Safety**: Use parameterized ORM/queries. No raw string-building from user data.  
- **Secrets Management**: No credentials in code. Use env vars or vault. Rotate on suspicion of leaks.  
- **CORS & SSL**: Restrict CORS to allowed origins. Enforce HTTPS/TLS for all endpoints. Enable HSTS.  
- **Rate Limiting**: Especially on auth (login/reset) and heavy ops.  
- **Logging**: Structured logs without sensitive data. Centralized logging with request IDs for traceability.  
- **Audit Logs**: Immutable records of sensitive actions. Protect against tampering.  
- **Database Constraints**: Use foreign keys, unique constraints, NOT NULL. For example, indexing `organization_id` in every table prevents broad scans.  
- **Backup/DR**: Regular DB backups (encrypted), offsite copies. Disaster recovery plan in place.  
- **Dependency Security**: Regularly scan and update libraries.  
- **Tenant Isolation**: Follow OWASP multi-tenant best practices: verify tenant context from auth, prevent IDOR.

## Observability and Monitoring  

- **Metrics:** Instrument key metrics (API response times, error rates, event throughput, alert counts) exposed via Prometheus or similar.  
- **Health Checks:** `/health` endpoint reporting status of dependencies (DB, CV service, message broker, LLM API). UI shows system status (e.g. green/yellow/red).  
- **Correlation IDs:** Tag each request and event stream with an ID to trace across frontend/backend.  
- **Logging:** Use structured (JSON) logs including org_id, user_id, correlation_id. Monitor for anomalies (e.g. surges of violations).  
- **Alerts:** Monitor system health (e.g. if CV worker crashes, send ops alert).  

## Deployment & Infrastructure Recommendations  

- **Database:** Use PostgreSQL (per requirement). Deploy as a managed cluster or HA setup. Use a connection pool.  
- **CV Workers:** Dedicated servers with GPUs/TPUs for YOLO and tracking. These can be horizontally scaled per number of cameras.  
- **Message Broker:** A queue (RabbitMQ/Redis/RocketMQ) for decoupling CV results, notifications, AI jobs.  
- **Storage:** Scalable object storage (e.g. AWS S3) for evidence images and documents, with lifecycle policies.  
- **Frontend Host:** Serve frontend as SPA from a static host or web server behind CDN.  
- **Streaming:** If live video is shown, options include HLS stream via edge server or WebRTC proxies. Use RTSP-to-HLS proxies with token auth.  
- **Scaling:** Containers (Kubernetes/Docker Swarm). Autoscale CV pods under high load. Web/API pods behind load balancer.  
- **TLS:** All services behind TLS (load balancer termination).  
- **Secrets:** Use Kubernetes secrets or AWS Secrets Manager.  
- **Monitoring:** Tools like Prometheus + Grafana, ELK/EFK stack for logs, alert rules on high error or CPU usage.  

## Key Risks and Mitigations  

- **False Positives:** Over-alerting floods operators. Mitigate via confidence thresholds, temporal validation, and allow tuning (e.g. require 5s before alert).  
- **Model Failure:** If YOLO crashes or misclassifies, safety may be compromised. Run CV in isolated processes and implement watchdogs; degrade gracefully (e.g. show “CV offline” warnings).  
- **Cross-Tenant Leaks:** A bug allowing orgA to query orgB data is catastrophic. Mitigation: rigorous testing, automated security scans (e.g. probe IDOR via test accounts). Follow OWASP multi-tenant guidance.  
- **Credential Exposure:** Secret leakage (DB credentials, camera streams) could allow breaches. Mitigation: secret management, limited-scoped tokens, network segmentation (camera feeds only accessible by CV servers).  
- **Data Loss:** A crash or rollout might corrupt DB. Mitigation: backups, migrations with rollback plans, careful transactional operations.  

## Final Deliverables for Antigravity  

- **Gap Analysis Report:** Document mapping spec requirements to existing implementation, marking what’s implemented vs “REQUIRES INSPECTION” vs new.  
- **File-by-File Architecture Map:** A list of all relevant repo files/modules with descriptions, highlighting areas to modify or extend.  
- **API Documentation:** Swagger/OpenAPI spec and narrative docs for all endpoints (as above).  
- **Database Migration Plan:** Outline of new tables/columns and the sequence to apply them without downtime.  
- **Test Suite:** Automated tests (unit, integration, e2e) for core workflows and security.  
- **Runbook:** Operational playbook including deployment steps, health check procedures, rollback plan, contact info.  

**Implementation Checklist:** (Immediate action items)  

- [ ] **Inspect Repo:** Inventory existing code, configs, and DB schema. Identify what already exists vs gaps.  
- [ ] **Set Up Dev Environment:** Configure local DB, secrets, and CV model paths using placeholder values.  
- [ ] **Authentication & AuthZ:** Verify current auth flow. Implement missing RBAC checks in services.  
- [ ] **Organization Context:** Ensure every API extracts and enforces `org_id` from the user token.  
- [ ] **Extend Data Models:** Add any missing columns (e.g. event.track_id, alert.assigned_user).  
- [ ] **Safety Rules:** Implement per-zone PPE lists and restricted flags.  
- [ ] **Event Creation Logic:** Wire detections → rule evaluation → DB event writes (with de-dup).  
- [ ] **Alert Lifecycle:** Build endpoints for ACK/ESC/RES and test state transitions.  
- [ ] **Notifications:** Integrate an email provider and a dummy SMS/WhatsApp provider; log all attempts.  
- [ ] **Frontend Integration:** Replace all mock data with real API calls in a development build; handle loading/error states.  
- [ ] **Real-time Hooks:** Connect WebSocket client; test that creating an alert on backend pushes to UI without refresh.  
- [ ] **AI/RAG Setup:** Define knowledge sources (e.g. upload PDF SOPs). Create a basic retrieval function (even just keyword search).  
- [ ] **Testing:** Write critical tests (tenant access, alert actions, detection->alert flow).  
- [ ] **Security Review:** Run OWASP ZAP on APIs. Ensure CORS is locked, no credentials in frontend, etc.  
- [ ] **Documentation:** Begin drafting API docs and architecture diagrams (this report can seed that).  

Following this roadmap with ongoing testing and review will ensure SafeVision AI is delivered as a robust, secure, and production-ready safety platform.

