/**
 * SafeVision AI — API Client
 *
 * Centralized fetch wrapper with JWT token management.
 * Base URL is configured via VITE_API_BASE_URL environment variable,
 * falling back to http://localhost:8000 for local development.
 */

import type {
  AIAnalysisRequest,
  AIAnalysisResponse,
  AlertDetailResponse,
  AlertListResponse,
  AlertTransitionRequest,
  CameraResponse,
  DashboardSummary,
  DocumentDetailResponse,
  DocumentListResponse,
  DocumentResponse,
  EventListResponse,
  HealthResponse,
  KnowledgeSearchRequest,
  KnowledgeSearchResponse,
  LLMProvidersResponse,
  LoginResponse,
  NotificationListResponse,
  NotificationResponse,
  OrgNotificationSettingsResponse,
  OrgNotificationSettingsUpdate,
  PatternListResponse,
  UserResponse,
  VideoUploadResponse,
  ZoneResponse,
  ControlsResponse,
  DetectionFilterUpdate,
  RestrictedAreaUpdate,
  AiInsightListResponse,
} from "./api-types";

// ==============================================================================
// Configuration
// ==============================================================================

const API_BASE_URL =
  (typeof import.meta !== "undefined" && import.meta.env?.["VITE_API_BASE_URL"]) ||
  "http://localhost:8000";

const TOKEN_KEY = "safevision_token";

// ==============================================================================
// Token Management
// ==============================================================================

export function getAuthToken(): string | null {
  return localStorage.getItem(TOKEN_KEY) ?? sessionStorage.getItem(TOKEN_KEY);
}

export function setAuthToken(token: string, remember: boolean): void {
  // Clear both storages first to avoid stale tokens
  localStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(TOKEN_KEY);

  if (remember) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    sessionStorage.setItem(TOKEN_KEY, token);
  }
}

export function clearAuthToken(): void {
  // Defensive: always clear both storages
  localStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
}

/**
 * Construct WebSocket URL corresponding to backend API.
 * Converts http/https to ws/wss and normalizes localhost -> 127.0.0.1
 * on local development to avoid Windows IPv6 (::1) connection timeout.
 */
export function getWebSocketUrl(path: string): string {
  let wsUrl = "";
  if (API_BASE_URL.startsWith("http://") || API_BASE_URL.startsWith("https://")) {
    wsUrl = API_BASE_URL.replace(/^http:/i, "ws:").replace(/^https:/i, "wss:");
  } else if (typeof window !== "undefined") {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.hostname || "127.0.0.1";
    wsUrl = `${protocol}//${host}:8000`;
  } else {
    wsUrl = "ws://127.0.0.1:8000";
  }
  // On Windows, 'localhost' resolves to IPv6 [::1] first. If backend is listening
  // strictly on IPv4 (127.0.0.1), browser WebSocket fails or times out.
  // Normalize localhost to 127.0.0.1 for direct IPv4 loopback connection.
  wsUrl = wsUrl.replace(/\/\/localhost(?::|$)/i, (match) => match.replace("localhost", "127.0.0.1"));
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${wsUrl}${normalizedPath}`;
}

// ==============================================================================
// Core Fetch Wrapper
// ==============================================================================

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getAuthToken();
  const headers: Record<string, string> = {};

  // Copy any existing headers
  if (options?.headers) {
    const existing = options.headers as Record<string, string>;
    Object.assign(headers, existing);
  }

  // Attach authorization
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  // Only set Content-Type for non-FormData requests
  if (!(options?.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
    });
  } catch {
    throw new ApiError(0, "Unable to connect to SafeVision server. Please check your network or server status.");
  }

  // Handle 401 — clear token and redirect (for login, retain the specific backend message)
  if (response.status === 401) {
    clearAuthToken();
    let detail = "Invalid email or password";
    try {
      const errorBody = await response.json();
      if (errorBody?.detail) {
        detail = typeof errorBody.detail === "string" ? errorBody.detail : JSON.stringify(errorBody.detail);
      }
    } catch {
      // Response body is not JSON — use fallback
    }
    if (typeof window !== "undefined" && !window.location.pathname.includes("/login")) {
      window.location.href = "/login";
    }
    throw new ApiError(401, detail);
  }

  // Handle non-OK responses
  if (!response.ok) {
    let detail = `API error ${response.status}`;
    try {
      const errorBody = await response.json();
      if (errorBody?.detail) {
        if (typeof errorBody.detail === "string") {
          detail = errorBody.detail;
        } else if (Array.isArray(errorBody.detail) && errorBody.detail.length > 0) {
          const first = errorBody.detail[0];
          detail = typeof first === "object" && first?.msg ? first.msg : JSON.stringify(errorBody.detail);
        } else {
          detail = JSON.stringify(errorBody.detail);
        }
      }
    } catch {
      // Response body is not JSON — use default message
    }
    throw new ApiError(response.status, detail);
  }

  // 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

// ==============================================================================
// Auth API
// ==============================================================================

export async function loginApi(email: string, password: string): Promise<LoginResponse> {
  return apiFetch<LoginResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function fetchMe(): Promise<UserResponse> {
  return apiFetch<UserResponse>("/api/users/me");
}

// ==============================================================================
// Alerts API
// ==============================================================================

export async function fetchAlerts(params?: {
  page?: number;
  size?: number;
  severity?: string | null;
  status?: string | null;
}): Promise<AlertListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.size) searchParams.set("size", String(params.size));
  if (params?.severity) searchParams.set("severity", params.severity);
  if (params?.status) searchParams.set("status", params.status);

  const query = searchParams.toString();
  return apiFetch<AlertListResponse>(`/api/alerts${query ? `?${query}` : ""}`);
}

export async function fetchAlertDetail(alertId: string): Promise<AlertDetailResponse> {
  return apiFetch<AlertDetailResponse>(`/api/alerts/${alertId}`);
}

export async function transitionAlert(
  alertId: string,
  body: AlertTransitionRequest,
): Promise<AlertDetailResponse> {
  return apiFetch<AlertDetailResponse>(`/api/alerts/${alertId}/status`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

// ==============================================================================
// Documents API
// ==============================================================================

export async function fetchDocuments(params?: {
  page?: number;
  size?: number;
}): Promise<DocumentListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.size) searchParams.set("size", String(params.size));

  const query = searchParams.toString();
  return apiFetch<DocumentListResponse>(`/api/documents${query ? `?${query}` : ""}`);
}

export async function fetchDocumentDetail(documentId: string): Promise<DocumentDetailResponse> {
  return apiFetch<DocumentDetailResponse>(`/api/documents/${documentId}`);
}

export async function uploadDocument(
  file: File,
  title: string,
  description?: string | null,
): Promise<DocumentResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("title", title);
  if (description) {
    formData.append("description", description);
  }

  return apiFetch<DocumentResponse>("/api/documents/upload", {
    method: "POST",
    body: formData,
  });
}

export async function deleteDocument(documentId: string): Promise<void> {
  return apiFetch<void>(`/api/documents/${documentId}`, {
    method: "DELETE",
  });
}

// ==============================================================================
// Knowledge Search API
// ==============================================================================

export async function searchKnowledge(
  body: KnowledgeSearchRequest,
): Promise<KnowledgeSearchResponse> {
  return apiFetch<KnowledgeSearchResponse>("/api/knowledge/search", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// ==============================================================================
// AI Analysis API
// ==============================================================================

export async function analyzeAI(body: AIAnalysisRequest): Promise<AIAnalysisResponse> {
  return apiFetch<AIAnalysisResponse>("/api/ai/analyze", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function fetchProviders(): Promise<LLMProvidersResponse> {
  return apiFetch<LLMProvidersResponse>("/api/ai/providers");
}

// ==============================================================================
// Health API
// ==============================================================================

export async function fetchHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/api/health");
}

// ==============================================================================
// Phase 10B — Events, Cameras, Zones, Patterns, Stats
// ==============================================================================

export async function fetchEvents(params?: {
  page?: number;
  size?: number;
  event_type?: string | null;
  camera_id?: string | null;
}): Promise<EventListResponse> {
  const sp = new URLSearchParams();
  if (params?.page) sp.set("page", String(params.page));
  if (params?.size) sp.set("size", String(params.size));
  if (params?.event_type) sp.set("event_type", params.event_type);
  if (params?.camera_id) sp.set("camera_id", params.camera_id);
  const q = sp.toString();
  return apiFetch<EventListResponse>(`/api/events${q ? `?${q}` : ""}`);
}

export async function fetchCameras(): Promise<CameraResponse[]> {
  return apiFetch<CameraResponse[]>("/api/cameras");
}

export async function fetchZones(): Promise<ZoneResponse[]> {
  return apiFetch<ZoneResponse[]>("/api/zones");
}

export async function fetchPatterns(params?: {
  page?: number;
  size?: number;
  pattern_type?: string | null;
  status?: string | null;
}): Promise<PatternListResponse> {
  const sp = new URLSearchParams();
  if (params?.page) sp.set("page", String(params.page));
  if (params?.size) sp.set("size", String(params.size));
  if (params?.pattern_type) sp.set("pattern_type", params.pattern_type);
  if (params?.status) sp.set("status", params.status);
  const q = sp.toString();
  return apiFetch<PatternListResponse>(`/api/patterns${q ? `?${q}` : ""}`);
}

export async function fetchDashboardSummary(): Promise<DashboardSummary> {
  return apiFetch<DashboardSummary>("/api/stats/summary");
}

// ==============================================================================
// Phase 11 — Real Video CV Streaming & AI Analysis
// ==============================================================================

export async function uploadVideoForMonitoring(
  file: File,
  cameraId: string,
  zoneId?: string | null
): Promise<VideoUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("camera_id", cameraId);
  if (zoneId) {
    formData.append("zone_id", zoneId);
  }

  return apiFetch<VideoUploadResponse>("/api/cv/video/upload", {
    method: "POST",
    body: formData,
  });
}

export async function deleteVideoSession(sessionId: string): Promise<void> {
  return apiFetch<void>(`/api/cv/video/session/${sessionId}`, {
    method: "DELETE",
  });
}

export async function analyzeEventWithAI(eventId: string): Promise<AIAnalysisResponse> {
  // 5-minute timeout — Gemma 4 multimodal reports take 50-90s via OpenRouter
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 300_000);
  try {
    return await apiFetch<AIAnalysisResponse>(`/api/ai/analyze-event/${eventId}`, {
      method: "POST",
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function getSafetyControls(): Promise<ControlsResponse> {
  return await apiFetch<ControlsResponse>('/api/rules/controls');
}

export async function updateDetectionFilter(data: DetectionFilterUpdate): Promise<ControlsResponse> {
  return await apiFetch<ControlsResponse>('/api/rules/controls/detection-filter', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function updateRestrictedArea(data: RestrictedAreaUpdate): Promise<ControlsResponse> {
  return await apiFetch<ControlsResponse>('/api/rules/controls/restricted-area', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function fetchEventEvidenceBlobUrl(eventId: string): Promise<string | null> {
  const token = getAuthToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  try {
    const response = await fetch(`${API_BASE_URL}/api/events/${eventId}/evidence`, {
      headers,
    });
    if (!response.ok) {
      return null;
    }
    const blob = await response.blob();
    return URL.createObjectURL(blob);
  } catch {
    return null;
  }
}

export async function fetchAlertEvidenceBlobUrl(alertId: string): Promise<string | null> {
  const token = getAuthToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  try {
    const response = await fetch(`${API_BASE_URL}/api/alerts/${alertId}/evidence`, {
      headers,
    });
    if (!response.ok) {
      return null;
    }
    const blob = await response.blob();
    return URL.createObjectURL(blob);
  } catch {
    return null;
  }
}

// ==============================================================================
// AI Insights — Paginated Read
// ==============================================================================

export async function fetchAIInsights(params?: {
  page?: number;
  size?: number;
  sort?: string;
}): Promise<AiInsightListResponse> {
  const sp = new URLSearchParams();
  if (params?.page) sp.set("page", String(params.page));
  if (params?.size) sp.set("size", String(params.size));
  if (params?.sort) sp.set("sort", params.sort);
  const q = sp.toString();
  return apiFetch<AiInsightListResponse>(`/api/ai/insights${q ? `?${q}` : ""}`);
}

// ==============================================================================
// Phase 15 — Notifications API
// ==============================================================================

export async function fetchNotificationSettings(): Promise<OrgNotificationSettingsResponse> {
  return apiFetch<OrgNotificationSettingsResponse>("/api/notifications/settings");
}

export async function saveNotificationSettings(
  body: OrgNotificationSettingsUpdate,
): Promise<OrgNotificationSettingsResponse> {
  return apiFetch<OrgNotificationSettingsResponse>("/api/notifications/settings", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function fetchNotifications(params?: {
  page?: number;
  size?: number;
  alert_id?: string | null;
  channel?: string | null;
  status?: string | null;
}): Promise<NotificationListResponse> {
  const sp = new URLSearchParams();
  if (params?.page) sp.set("page", String(params.page));
  if (params?.size) sp.set("size", String(params.size));
  if (params?.alert_id) sp.set("alert_id", params.alert_id);
  if (params?.channel) sp.set("channel", params.channel);
  if (params?.status) sp.set("status", params.status);
  const q = sp.toString();
  return apiFetch<NotificationListResponse>(`/api/notifications${q ? `?${q}` : ""}`);
}

export async function fetchNotification(notificationId: string): Promise<NotificationResponse> {
  return apiFetch<NotificationResponse>(`/api/notifications/${notificationId}`);
}