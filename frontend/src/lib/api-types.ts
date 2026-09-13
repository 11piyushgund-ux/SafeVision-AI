/**
 * SafeVision AI — Backend API TypeScript Types
 *
 * Every interface below mirrors the corresponding backend Pydantic schema
 * field-by-field. Source of truth: backend/app/schemas/*.py
 *
 * DO NOT add fields that don't exist in the backend schemas.
 */

// ==============================================================================
// Auth (from schemas/auth.py)
// ==============================================================================

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserResponse;
}

export interface UserResponse {
  id: string;
  org_id: string;
  email: string;
  name: string;
  role_id: string;
  role_name: string | null;
  status: string;
  last_login: string | null;
  created_at: string;
}

// ==============================================================================
// Alerts (from schemas/alert.py)
// ==============================================================================

export interface AlertResponse {
  id: string;
  event_id: string | null;
  rule_id: string | null;
  org_id: string;
  title: string;
  description: string | null;
  severity: string;
  status: string;
  assigned_to: string | null;
  evidence_path: string | null;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

export interface AlertStateResponse {
  id: string;
  from_status: string | null;
  to_status: string;
  changed_by: string | null;
  reason: string | null;
  created_at: string;
}

export interface AlertDetailResponse extends AlertResponse {
  states: AlertStateResponse[];
}

export interface AlertListResponse {
  data: AlertResponse[];
  total: number;
  page: number;
  size: number;
}

export interface AlertTransitionRequest {
  status: string;
  reason?: string | null | undefined;
}

// ==============================================================================
// Documents (from schemas/document.py)
// ==============================================================================

export interface DocumentResponse {
  id: string;
  org_id: string;
  title: string;
  description: string | null;
  document_type: string;
  filename: string;
  file_size: number | null;
  status: string;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

export interface DocumentChunkResponse {
  id: string;
  document_id: string;
  chunk_index: number;
  content: string;
  char_count: number;
}

export interface DocumentDetailResponse extends DocumentResponse {
  chunks: DocumentChunkResponse[];
}

export interface DocumentListResponse {
  data: DocumentResponse[];
  total: number;
  page: number;
  size: number;
}

export interface KnowledgeSearchRequest {
  query: string;
  top_k?: number;
}

export interface KnowledgeSearchResult {
  chunk_id: string;
  content: string;
  score: number;
  metadata: Record<string, unknown>;
}

export interface KnowledgeSearchResponse {
  query: string;
  results: KnowledgeSearchResult[];
  total_results: number;
}

// ==============================================================================
// AI Analysis (from schemas/ai_analysis.py)
// ==============================================================================

export interface AIAnalysisRequest {
  event_type: string;
  event_details?: Record<string, unknown>;
  risk_score: number;
  risk_level: string;
  risk_factors?: Array<Record<string, unknown>>;
  risk_explanation?: string;
  camera_id?: string | null | undefined;
  zone_name?: string | null | undefined;
  event_id?: string | null | undefined;
  recurrence_count?: number;
  user_query?: string | null | undefined;
  use_rag?: boolean;
  rag_top_k?: number;
}

export interface SafetyActionItem {
  title: string;
  procedure: string;
  rationale?: string;
  role?: string;
  timeframe?: string;
  expected_outcome?: string;
}

export interface AIAnalysisResult {
  summary: string;
  risk_explanation: string;
  hazard_interpretation?: string;
  contributing_factors: string[];
  safety_policy_guidance: string;
  historical_context: string;
  recommended_actions: string[];
  immediate_actions?: (SafetyActionItem | string)[];
  investigation_actions?: (SafetyActionItem | string)[];
  preventive_actions?: (SafetyActionItem | string)[];
  uncertainties?: string[];
  provider: string;
  model: string;
  generated_at: string;
  visual_observations?: string[];
  visual_validation?: {
    detection_supported?: boolean;
    confidence_note?: string;
    scene_context?: string;
    [key: string]: unknown;
  } | null;
}

export interface AIAnalysisResponse {
  success: boolean;
  analysis: AIAnalysisResult | null;
  error: string | null;
  provider: string | null;
  model: string | null;
  insight_id?: string | null;
}

// ==============================================================================
// Health (from api/health.py)
// ==============================================================================

export interface DependencyStatus {
  name: string;
  status: string;
  latency_ms: number | null;
  error: string | null;
}

export interface HealthResponse {
  status: string;
  timestamp: string;
  version: string;
  environment: string;
  dependencies: DependencyStatus[];
}

// ==============================================================================
// LLM Providers (from api/ai_analysis.py — untyped response)
// ==============================================================================

export interface LLMProviderInfo {
  name: string;
  model: string;
  available: boolean;
  is_primary: boolean;
  is_fallback: boolean;
}

export interface LLMProvidersResponse {
  active_provider: string;
  mode: string;
  providers: LLMProviderInfo[];
}

// ==============================================================================
// Phase 10B — Events, Cameras, Zones, Patterns, Stats
// ==============================================================================

export interface EventResponse {
  id: string;
  camera_id: string;
  org_id: string;
  event_type: string;
  timestamp: string;
  confidence: number | null;
  detection_data: Record<string, unknown> | null;
  evidence_path: string | null;
  created_at: string;
  camera_name: string | null;
  zone_name: string | null;
}

export interface EventListResponse {
  data: EventResponse[];
  total: number;
  page: number;
  size: number;
}

export interface CameraResponse {
  id: string;
  name: string;
  description: string | null;
  status: string;
  stream_url: string | null;
  stream_type: string | null;
  resolution_width: number | null;
  resolution_height: number | null;
  fps: number | null;
  last_frame_at: string | null;
  created_at: string;
  updated_at: string;
  site_id: string;
  zone_id: string | null;
  zone_name: string | null;
}

export interface ZoneResponse {
  id: string;
  name: string;
  description: string | null;
  zone_type: string;
  status: string;
  /** ROI polygon boundary: [[x,y], ...] in normalized 0.0-1.0 coordinates */
  polygon: number[][] | null;
  /** Required PPE class names for this zone */
  required_ppe: string[] | null;
  site_id: string;
  created_at: string;
  updated_at: string;
}

export interface DailyTrendItem {
  date: string;
  occurrences: number;
}

export interface PatternResponse {
  id: string;
  org_id: string;
  zone_id: string | null;
  rule_id: string | null;
  pattern_type: string;
  title: string;
  description: string | null;
  occurrence_count: number;
  confidence_score: number | null;
  pattern_data: Record<string, unknown> | null;
  status: string;
  first_detected_at: string;
  last_detected_at: string;
  created_at: string;
  zone_name: string | null;
  daily_trend?: DailyTrendItem[] | null;
}

export interface PatternListResponse {
  data: PatternResponse[];
  total: number;
  page: number;
  size: number;
}

export interface DashboardSummary {
  total_alerts: number;
  new_alerts: number;
  acknowledged_alerts: number;
  total_events: number;
  total_cameras: number;
  online_cameras: number;
  total_zones: number;
  active_zones: number;
}

// ==============================================================================
// Phase 11 — Real Video CV Streaming & Monitoring
// ==============================================================================

export interface VideoUploadResponse {
  session_id: string;
  filename: string;
  camera_id: string;
  zone_id: string | null;
  total_frames: number;
  source_fps: number;
  duration_seconds: number;
  width: number;
  height: number;
}

export interface WSDetectionItem {
  class_name: string;
  confidence: number;
  bbox: number[]; // [x1, y1, x2, y2]
  track_id: number | string | null;
  is_compliant: boolean;
  missing_ppe: string[];
  detected_ppe: string[];
}

export interface WSZoneViolation {
  track_id: number | string | null;
  rule_name: string;
  rule_type: string;
  severity: string;
  message: string;
}

export interface WSEventSummary {
  event_id: string;
  event_type: string;
  severity: string;
  message: string;
  timestamp: string;
  risk_score: number;
  risk_level: string;
}

export interface WSFrameStats {
  source_fps: number;
  inference_fps: number;
  persons_detected: number;
  active_violations: number;
  total_events_generated: number;
}

export interface WSFramePayload {
  type: "frame";
  frame_idx: number;
  total_frames: number;
  timestamp_ms: number;
  image: string;
  detections: WSDetectionItem[];
  zone_polygon: number[][] | null;
  zone_violations: WSZoneViolation[];
  new_events: WSEventSummary[];
  stats: WSFrameStats;
}

export interface WSAuthOkMessage {
  type: "auth_ok";
  user_id: string;
  user_name: string;
  org_id: string;
}

export interface WSErrorMessage {
  type: "error" | "auth_error";
  message: string;
}

export interface WSCompletedMessage {
  type: "completed";
  total_frames_processed: number;
  total_events_generated: number;
}


// ==============================================================================
// Rules (from schemas/rule_schema.py)
// ==============================================================================

export interface ControlsResponse {
  ignored_classes: string[];
  restricted_area_enabled: boolean;
}

export interface DetectionFilterUpdate {
  ignored_classes: string[];
}

export interface RestrictedAreaUpdate {
  enabled: boolean;
}

// ==============================================================================
// AI Insights (from schemas/ai_analysis.py — read endpoint)
// ==============================================================================

export interface AiInsightResponse {
  id: string;
  insight_type: string;
  title: string;
  content: string; // raw JSON string — frontend parses
  query: string | null;
  source_context: Record<string, unknown> | null;
  llm_metadata: Record<string, unknown> | null;
  status: string;
  created_at: string;
}

export interface AiInsightListResponse {
  data: AiInsightResponse[];
  total: number;
  page: number;
  size: number;
}

// ==============================================================================
// Notifications (from schemas/notification_schema.py) — Phase 15
// ==============================================================================

export interface OrgNotificationSettingsResponse {
  id: string;
  org_id: string;
  notifications_enabled: boolean;
  notification_mode: "email" | "whatsapp";
  email_recipient: string | null;
  whatsapp_recipient: string | null;
  notification_recipient: string | null;
  created_at: string;
  updated_at: string;
}

export interface OrgNotificationSettingsUpdate {
  notifications_enabled: boolean;
  notification_mode: "email" | "whatsapp";
  email_recipient?: string | null;
  whatsapp_recipient?: string | null;
  notification_recipient?: string | null;
}

export interface NotificationResponse {
  id: string;
  alert_id: string;
  event_id: string | null;
  org_id: string;
  recipient_user_id: string | null;
  recipient_address: string | null;
  channel: string;
  status: string;
  subject: string | null;
  body: string | null;
  provider_response: Record<string, unknown> | null;
  retry_count: number;
  sent_at: string | null;
  delivered_at: string | null;
  created_at: string;
}

export interface NotificationListResponse {
  data: NotificationResponse[];
  total: number;
  page: number;
  size: number;
}