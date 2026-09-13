/**
 * Domain model for SafeVision AI.
 *
 * Field names mirror the intended backend tables so wiring a database later is
 * a 1:1 mapping (snake_case columns, ISO timestamps, enum-friendly unions).
 *
 * Planned tables:
 *   cameras        -> Camera
 *   zones          -> Zone
 *   safety_events  -> SafetyEvent   (raw AI detections from the live stream)
 *   safety_alerts  -> SafetyAlert   (events that require human action)
 */

export type AlertSeverity = "high" | "medium" | "low" | "safe";
export type AlertStatus = "active" | "acknowledged" | "escalated" | "resolved";

export type SafetyEventType =
  | "restricted_zone_entry"
  | "missing_safety_helmet"
  | "ppe_compliance_verified"
  | "unsafe_posture"
  | "fire_smoke_detected";

export interface Zone {
  id: string;
  name: string;
  facility: string;
}

export interface Camera {
  id: string;
  name: string;
  zone_id: string;
  is_streaming: boolean;
}

export interface SafetyEvent {
  id: string;
  event_type: SafetyEventType;
  severity: AlertSeverity;
  zone_name: string;
  camera_name: string;
  detected_at: string; // ISO timestamp
  confidence_score: number; // 0..1
  status: AlertStatus;
}

export interface SafetyAlert extends SafetyEvent {
  description: string;
  recommended_action: string;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  resolved_at: string | null;
  resolved_by: string | null;
}

export const EVENT_TYPE_LABELS: Record<SafetyEventType, string> = {
  restricted_zone_entry: "Restricted Zone Entry",
  missing_safety_helmet: "Missing Safety Helmet",
  ppe_compliance_verified: "PPE Compliance Verified",
  unsafe_posture: "Unsafe Posture Detected",
  fire_smoke_detected: "Fire / Smoke Detected",
};

export const SEVERITY_LABELS: Record<AlertSeverity, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
  safe: "Safe",
};

export const STATUS_LABELS: Record<AlertStatus, string> = {
  active: "Active",
  acknowledged: "Acknowledged",
  escalated: "Escalated",
  resolved: "Resolved",
};

export const severityToneClass: Record<AlertSeverity, string> = {
  high: "bg-danger-soft text-danger",
  medium: "bg-warn-soft text-warn",
  low: "bg-brand-soft text-brand",
  safe: "bg-safe-soft text-safe",
};

export function formatDetectedAt(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/**
 * Planned table: recurring_patterns -> RecurringPattern
 * Groups repeated safety_events of the same event_type + location into a
 * single trackable pattern with trend + preventive recommendation.
 */
export type PatternTrend = "increasing" | "stable" | "decreasing";
export type PatternFrequency = "daily" | "weekly" | "monthly" | "sporadic";
export type PatternSortKey = "risk_priority" | "total_occurrences" | "latest_occurrence";

export interface PatternTrendPoint {
  id: string;
  pattern_id: string;
  bucket_start: string; // ISO timestamp for the aggregation bucket
  occurrence_count: number;
}

export interface RecurringPattern {
  id: string;
  event_type: SafetyEventType;
  primary_location: string; // zones.name
  zone_id: string | null;
  total_occurrences: number;
  first_detected_at: string; // ISO timestamp
  latest_occurrence_at: string; // ISO timestamp
  risk_priority: AlertSeverity;
  trend: PatternTrend;
  frequency: PatternFrequency;
  most_affected_time: string; // e.g. "10:00 - 11:00"
  confidence_score: number; // 0..1
  preventive_recommendation: string | null;
  trend_points: PatternTrendPoint[];
}

export const TREND_LABELS: Record<PatternTrend, string> = {
  increasing: "Increasing",
  stable: "Stable",
  decreasing: "Decreasing",
};

export const FREQUENCY_LABELS: Record<PatternFrequency, string> = {
  daily: "Daily",
  weekly: "Weekly",
  monthly: "Monthly",
  sporadic: "Sporadic",
};

export const PATTERN_SORT_LABELS: Record<PatternSortKey, string> = {
  risk_priority: "Risk Priority",
  total_occurrences: "Total Occurrences",
  latest_occurrence: "Latest Occurrence",
};

export function formatPatternDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "2-digit",
  });
}

/**
 * Planned tables:
 *   user_settings              -> UserSettings          (general app preferences)
 *   notification_preferences   -> NotificationPreferences
 */
export type AppTheme = "light" | "dark" | "system";
export type DateFormat = "MMM_DD_YYYY" | "DD_MM_YYYY" | "YYYY_MM_DD";
export type TimeFormat = "12_hour" | "24_hour";
export type AppLanguage = "en" | "hi" | "es" | "fr";
export type DefaultDashboard = "overview" | "live_monitoring" | "safety_alerts" | "recurring_patterns";
export type NotificationChannel = "email" | "whatsapp";
export type SettingsSection = "general" | "notifications" | "zone_controls";

export interface UserSettings {
  id: string;
  user_id: string;
  facility_site_name: string;
  time_zone: string;
  date_format: DateFormat;
  time_format: TimeFormat;
  language: AppLanguage;
  updated_at: string | null;
}

export interface NotificationPreferences {
  id: string;
  user_id: string;
  notification_channel: NotificationChannel;
  email_address: string;
  email_verified: boolean;
  whatsapp_number: string;
  whatsapp_verified: boolean;
  updated_at: string | null;
}

export const THEME_LABELS: Record<AppTheme, string> = {
  light: "Light",
  dark: "Dark",
  system: "System",
};

export const DATE_FORMAT_LABELS: Record<DateFormat, string> = {
  MMM_DD_YYYY: "May 24, 2025 (MMM DD, YYYY)",
  DD_MM_YYYY: "24/05/2025 (DD/MM/YYYY)",
  YYYY_MM_DD: "2025-05-24 (YYYY-MM-DD)",
};

export const TIME_FORMAT_LABELS: Record<TimeFormat, string> = {
  "12_hour": "12-hour (AM/PM)",
  "24_hour": "24-hour",
};

export const LANGUAGE_LABELS: Record<AppLanguage, string> = {
  en: "English",
  hi: "Hindi",
  es: "Spanish",
  fr: "French",
};

export const DEFAULT_DASHBOARD_LABELS: Record<DefaultDashboard, string> = {
  overview: "Overview Dashboard",
  live_monitoring: "Live Monitoring",
  safety_alerts: "Safety Alerts",
  recurring_patterns: "Recurring Patterns",
};

export const ITEMS_PER_PAGE_OPTIONS = [10, 25, 50, 100];
export const AUTO_REFRESH_OPTIONS_SECONDS = [15, 30, 60, 300];

export const DEFAULT_USER_SETTINGS: UserSettings = {
  id: "",
  user_id: "",
  facility_site_name: "SafeVision Facility Alpha",
  time_zone: "UTC",
  date_format: "MMM_DD_YYYY",
  time_format: "12_hour",
  language: "en",
  updated_at: null,
};

export const DEFAULT_NOTIFICATION_PREFERENCES: NotificationPreferences = {
  id: "",
  user_id: "",
  notification_channel: "email",
  email_address: "manager@safevision.com",
  email_verified: true,
  whatsapp_number: "+91 98765 43210",
  whatsapp_verified: true,
  updated_at: null,
};

/**
 * Planned table: safety_documents -> SafetyDocument
 * Approved safety policies / SOPs that feed the AI recommendation knowledge base.
 */
export type DocumentKind = "policy" | "sop";
export type DocumentFileType = "pdf" | "doc";
export type DocumentStatus = "approved" | "pending_review" | "archived";

export interface SafetyDocument {
  id: string;
  document_code: string; // e.g. DOC-2025-001
  document_title: string;
  source_department: string;
  document_kind: DocumentKind;
  version: string;
  file_type: DocumentFileType;
  file_url: string | null;
  uploaded_at: string; // ISO timestamp
  uploaded_by: string;
  status: DocumentStatus;
}

export const DOCUMENT_KIND_LABELS: Record<DocumentKind, string> = {
  policy: "Policy",
  sop: "SOP",
};

export const DOCUMENT_STATUS_LABELS: Record<DocumentStatus, string> = {
  approved: "Approved",
  pending_review: "Pending Review",
  archived: "Archived",
};

export const documentStatusToneClass: Record<DocumentStatus, string> = {
  approved: "bg-safe-soft text-safe",
  pending_review: "bg-warn-soft text-warn",
  archived: "bg-muted text-muted-foreground",
};

export function formatDocumentDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "2-digit",
  });
}

export function formatDocumentTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });
}
