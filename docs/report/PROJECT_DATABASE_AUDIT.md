# SafeVision-AI Database Audit (Phase 5)

## 1. Overview
- **Database Engine**: PostgreSQL
- **ORM**: SQLAlchemy
- **Migrations**: Alembic

## 2. Table Inventory
| Model Class | Table Name | Key Columns/Types | Relationships | Tenant Isolation |
|---|---|---|---|---|
| `AiInsight` | `ai_insights` | ... + JSON/JSONB | organization->Organization | No |
| `Alert` | `alerts` | ... + JSON/JSONB | event->Event, rule->SafetyRule, organization->Organization, assigned_user->User, states->AlertState, notifications->Notification, alert->Alert, user->User | No |
| `AlertState` | `alert_states` | ... + JSON/JSONB | alert->Alert, user->User | No |
| `AuditLog` | `audit_logs` | ... + JSON/JSONB | organization->Organization, user->User | No |
| `Camera` | `cameras` | ... + JSON/JSONB | site->Site, zone->Zone, organization->Organization, events->Event | No |
| `SafetyDocument` | `safety_documents` | ... + JSON/JSONB | organization->Organization, uploader->User, document->SafetyDocument, organization->Organization | No |
| `DocumentChunk` | `document_chunks` | ... + JSON/JSONB | document->SafetyDocument, organization->Organization | No |
| `Event` | `events` | ... + JSON/JSONB | camera->Camera, organization->Organization, alerts->Alert | No |
| `Notification` | `notifications` | ... + JSON/JSONB | alert->Alert, organization->Organization, recipient->User, event->Event | No |
| `Organization` | `organizations` | TBD | users->User, roles->Role | No |
| `OrgNotificationSettings` | `org_notification_settings` | TBD | organization->Organization | No |
| `Pattern` | `patterns` | ... + JSON/JSONB | organization->Organization, zone->Zone, rule->SafetyRule | No |
| `Role` | `roles` | TBD | organization->Organization, permissions->Permission, users->User, role->Role | No |
| `Permission` | `permissions` | TBD | role->Role | No |
| `SafetyRule` | `safety_rules` | ... + JSON/JSONB | organization->Organization, zone->Zone, alerts->Alert | No |
| `Site` | `sites` | TBD | organization->Organization, zones->Zone, cameras->Camera | No |
| `User` | `users` | TBD | organization->Organization, role->Role | No |
| `Zone` | `zones` | ... + JSON/JSONB | site->Site, organization->Organization, cameras->Camera, safety_rules->SafetyRule | No |

## 3. Migration History (Alembic)
| Revision | Purpose |
|---|---|
