/**
 * SafeVision AI — Safety Intelligence Report Generator
 *
 * Builds a self-contained, print-optimized HTML document from a persisted
 * AI Safety Insight and its associated event evidence image.
 *
 * Architecture:
 *   selectedDetail → fetch event metadata → fetch evidence JPEG
 *   → convert to Base64 data URL → build HTML → iframe → window.print()
 *
 * Zero new dependencies. No AI regeneration. No secrets exposed.
 */

import type { InsightDetailViewModel, RecommendationAction } from "@/components/safevision/InsightDetail";
import type { EventResponse } from "@/lib/api-types";
import { getAuthToken } from "@/lib/api-client";

// ==============================================================================
// Public API
// ==============================================================================

const API_BASE_URL =
  (typeof import.meta !== "undefined" && import.meta.env?.["VITE_API_BASE_URL"]) ||
  "http://localhost:8000";

export interface ReportMetadata {
  /** Provider name (e.g. "openrouter", "ollama") — safe to display. */
  provider?: string | undefined;
  /** Model identifier (e.g. "google/gemma-4-26b-a4b-it:free") — safe to display. */
  model?: string | undefined;
  /** Risk score number if available. */
  riskScore?: number | undefined;
}

/**
 * Generate and print a complete Safety Intelligence Report for the given insight.
 *
 * Returns `true` on success, throws on critical failure.
 */
export async function generateSafetyInsightReport(
  insight: InsightDetailViewModel,
  meta?: ReportMetadata,
): Promise<boolean> {
  // 1. Fetch event metadata (camera name, zone name, confidence, timestamp)
  let eventDetails: EventResponse | null = null;
  if (insight.eventId) {
    eventDetails = await fetchEventById(insight.eventId);
  }

  // 2. Fetch evidence image and convert to Base64 data URL
  let evidenceDataUrl: string | null = null;
  if (insight.eventId) {
    evidenceDataUrl = await fetchEvidenceAsDataUrl(insight.eventId);
  }

  // 3. Build the complete HTML document
  const html = buildReportHtml(insight, eventDetails, evidenceDataUrl, meta);

  // 4. Print via hidden iframe
  await triggerPrint(html);

  return true;
}

// ==============================================================================
// Data Fetchers (Authenticated, Read-Only)
// ==============================================================================

async function fetchEventById(eventId: string): Promise<EventResponse | null> {
  const token = getAuthToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  try {
    const response = await fetch(`${API_BASE_URL}/api/events/${eventId}`, { headers });
    if (!response.ok) return null;
    return (await response.json()) as EventResponse;
  } catch {
    return null;
  }
}

async function fetchEvidenceAsDataUrl(eventId: string): Promise<string | null> {
  const token = getAuthToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  try {
    const response = await fetch(`${API_BASE_URL}/api/events/${eventId}/evidence`, { headers });
    if (!response.ok) return null;
    const blob = await response.blob();
    return await blobToDataUrl(blob);
  } catch {
    return null;
  }
}

function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(new Error("Failed to read evidence image"));
    reader.readAsDataURL(blob);
  });
}

// ==============================================================================
// Print Trigger (Hidden Iframe)
// ==============================================================================

function triggerPrint(html: string): Promise<void> {
  return new Promise((resolve) => {
    const iframe = document.createElement("iframe");
    iframe.style.position = "fixed";
    iframe.style.left = "-10000px";
    iframe.style.top = "-10000px";
    iframe.style.width = "0";
    iframe.style.height = "0";
    iframe.style.border = "none";
    document.body.appendChild(iframe);

    const iframeDoc = iframe.contentDocument ?? iframe.contentWindow?.document;
    if (!iframeDoc) {
      document.body.removeChild(iframe);
      resolve();
      return;
    }

    iframeDoc.open();
    iframeDoc.write(html);
    iframeDoc.close();

    // Wait for content (images) to load before printing
    iframe.onload = () => {
      setTimeout(() => {
        try {
          iframe.contentWindow?.focus();
          iframe.contentWindow?.print();
        } catch {
          // Fallback: open in new window
          const printWindow = window.open("", "_blank");
          if (printWindow) {
            printWindow.document.write(html);
            printWindow.document.close();
            printWindow.focus();
            printWindow.print();
          }
        }

        // Cleanup after print dialog closes
        setTimeout(() => {
          try {
            document.body.removeChild(iframe);
          } catch {
            // Already removed
          }
          resolve();
        }, 500);
      }, 300);
    };
  });
}

// ==============================================================================
// HTML Report Builder
// ==============================================================================

function esc(text: string | null | undefined): string {
  if (!text) return "";
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function buildReportHtml(
  insight: InsightDetailViewModel,
  event: EventResponse | null,
  evidenceDataUrl: string | null,
  meta?: ReportMetadata,
): string {
  const now = new Date();
  const exportTimestamp = now.toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  }) + " at " + now.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });

  const riskColors: Record<string, string> = {
    High: "#dc2626",
    Critical: "#dc2626",
    Medium: "#ea580c",
    Low: "#16a34a",
  };
  const riskColor = riskColors[insight.risk] ?? "#6b7280";

  const eventTypeLabel = insight.eventType
    ? insight.eventType.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
    : "—";

  const statusLabel = insight.status
    ? insight.status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
    : "Pending";

  // Format event timestamp
  let eventTimestamp = "—";
  if (event?.timestamp) {
    try {
      const d = new Date(event.timestamp);
      eventTimestamp = d.toLocaleDateString("en-US", {
        year: "numeric", month: "long", day: "numeric",
      }) + " at " + d.toLocaleTimeString("en-US", {
        hour: "numeric", minute: "2-digit", second: "2-digit", hour12: true,
      });
    } catch {
      eventTimestamp = event.timestamp;
    }
  }

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SafeVision AI — Safety Intelligence Report</title>
<style>
  @page {
    size: A4 portrait;
    margin: 14mm 12mm;
  }
  @media print {
    html, body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    .no-break { break-inside: avoid; page-break-inside: avoid; }
    .page-break-before { break-before: page; page-break-before: always; }
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html { font-size: 13px; }
  body {
    font-family: "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif;
    color: #1a1a2e;
    line-height: 1.6;
    background: #ffffff;
  }
  .report { max-width: 210mm; margin: 0 auto; padding: 8mm 0; }

  /* ===== HEADER ===== */
  .header {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    color: #ffffff;
    padding: 28px 32px;
    border-radius: 10px;
    margin-bottom: 24px;
  }
  .header-brand {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 2.5px;
    text-transform: uppercase;
    color: #60a5fa;
    margin-bottom: 6px;
  }
  .header-title {
    font-size: 26px;
    font-weight: 800;
    letter-spacing: -0.3px;
    margin-bottom: 4px;
  }
  .header-subtitle {
    font-size: 14px;
    color: #94a3b8;
    font-weight: 400;
  }
  .header-meta {
    display: flex;
    gap: 24px;
    margin-top: 18px;
    flex-wrap: wrap;
  }
  .header-meta-item {
    font-size: 11px;
    color: #cbd5e1;
  }
  .header-meta-item strong {
    display: block;
    font-size: 13px;
    color: #f1f5f9;
    margin-top: 2px;
  }

  /* ===== SECTIONS ===== */
  .section {
    margin-bottom: 22px;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    overflow: hidden;
  }
  .section-header {
    background: #f8fafc;
    border-bottom: 1px solid #e2e8f0;
    padding: 12px 20px;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .section-icon {
    width: 22px;
    height: 22px;
    border-radius: 5px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 700;
    color: #ffffff;
  }
  .section-title {
    font-size: 15px;
    font-weight: 700;
    color: #0f172a;
    letter-spacing: -0.2px;
  }
  .section-body { padding: 18px 20px; }

  /* ===== INFO GRID ===== */
  .info-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
  }
  .info-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 10px 14px;
  }
  .info-card-label {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #64748b;
    margin-bottom: 4px;
  }
  .info-card-value {
    font-size: 13px;
    font-weight: 600;
    color: #1e293b;
    word-break: break-all;
  }

  /* ===== RISK BADGE ===== */
  .risk-badge {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #ffffff;
  }

  /* ===== EVIDENCE ===== */
  .evidence-container {
    text-align: center;
    padding: 16px 0;
  }
  .evidence-img {
    max-width: 100%;
    max-height: 360px;
    object-fit: contain;
    border: 2px solid #e2e8f0;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  }
  .evidence-caption {
    margin-top: 10px;
    font-size: 11px;
    color: #64748b;
    font-style: italic;
  }
  .evidence-unavailable {
    background: #fef2f2;
    border: 1px dashed #fca5a5;
    border-radius: 8px;
    padding: 24px;
    text-align: center;
    color: #991b1b;
    font-size: 13px;
  }

  /* ===== CONTENT BLOCKS ===== */
  .content-block { margin-bottom: 16px; }
  .content-block:last-child { margin-bottom: 0; }
  .content-label {
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #475569;
    margin-bottom: 6px;
    padding-bottom: 4px;
    border-bottom: 1px solid #f1f5f9;
  }
  .content-text {
    font-size: 13px;
    color: #334155;
    line-height: 1.7;
    white-space: pre-wrap;
  }

  /* ===== LISTS ===== */
  .content-list {
    list-style: none;
    padding: 0;
  }
  .content-list li {
    position: relative;
    padding-left: 18px;
    margin-bottom: 6px;
    font-size: 13px;
    color: #334155;
    line-height: 1.6;
  }
  .content-list li::before {
    content: "▸";
    position: absolute;
    left: 0;
    color: #3b82f6;
    font-weight: 700;
  }

  /* ===== ACTION TABLE ===== */
  .action-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    margin-top: 8px;
  }
  .action-table th {
    background: #f1f5f9;
    border: 1px solid #e2e8f0;
    padding: 8px 10px;
    text-align: left;
    font-weight: 700;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #475569;
  }
  .action-table td {
    border: 1px solid #e2e8f0;
    padding: 8px 10px;
    vertical-align: top;
    color: #334155;
    line-height: 1.5;
  }
  .action-table tr:nth-child(even) td {
    background: #fafbfc;
  }
  .action-title {
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 4px;
  }
  .action-procedure {
    font-size: 11.5px;
    color: #475569;
    line-height: 1.5;
  }
  .action-rationale {
    font-size: 11px;
    color: #64748b;
    font-style: italic;
    margin-top: 4px;
  }

  /* ===== CHECKLIST ===== */
  .checklist {
    list-style: none;
    padding: 0;
  }
  .checklist li {
    position: relative;
    padding-left: 24px;
    margin-bottom: 6px;
    font-size: 13px;
    color: #334155;
    line-height: 1.6;
  }
  .checklist li::before {
    content: "☐";
    position: absolute;
    left: 0;
    font-size: 14px;
    color: #3b82f6;
  }

  /* ===== FOOTER ===== */
  .report-footer {
    margin-top: 28px;
    padding-top: 16px;
    border-top: 2px solid #e2e8f0;
    font-size: 10px;
    color: #94a3b8;
    text-align: center;
    line-height: 1.6;
  }
  .report-footer strong { color: #64748b; }

  /* ===== VISUAL VALIDATION ===== */
  .vv-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    margin-top: 8px;
  }
  .vv-card {
    background: #f0f9ff;
    border: 1px solid #bae6fd;
    border-radius: 6px;
    padding: 10px 12px;
  }
  .vv-card-label {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #0369a1;
    margin-bottom: 4px;
  }
  .vv-card-value {
    font-size: 12px;
    color: #1e293b;
    font-weight: 500;
  }
</style>
</head>
<body>
<div class="report">

  <!-- ===== HEADER ===== -->
  <div class="header no-break">
    <div class="header-brand">SafeVision AI</div>
    <div class="header-title">Safety Intelligence Report</div>
    <div class="header-subtitle">${esc(insight.title)}</div>
    <div class="header-meta">
      <div class="header-meta-item">
        Status
        <strong>${esc(statusLabel)}</strong>
      </div>
      <div class="header-meta-item">
        Risk Level
        <strong><span class="risk-badge" style="background:${riskColor}">${esc(insight.risk)}</span></strong>
      </div>
      <div class="header-meta-item">
        Generated
        <strong>${esc(insight.generatedAt)}</strong>
      </div>
      <div class="header-meta-item">
        Report Exported
        <strong>${esc(exportTimestamp)}</strong>
      </div>
    </div>
  </div>

  <!-- ===== EVENT INFORMATION ===== -->
  <div class="section no-break">
    <div class="section-header">
      <div class="section-icon" style="background:#3b82f6">ℹ</div>
      <div class="section-title">Event Information</div>
    </div>
    <div class="section-body">
      <div class="info-grid">
        <div class="info-card">
          <div class="info-card-label">Event Type</div>
          <div class="info-card-value">${esc(eventTypeLabel)}</div>
        </div>
        <div class="info-card">
          <div class="info-card-label">Risk Level</div>
          <div class="info-card-value" style="color:${riskColor}">${esc(insight.riskLevelRaw ?? insight.risk)}</div>
        </div>
        <div class="info-card">
          <div class="info-card-label">Risk Score</div>
          <div class="info-card-value">${meta?.riskScore != null ? meta.riskScore.toFixed(1) : "—"}</div>
        </div>
        <div class="info-card">
          <div class="info-card-label">Confidence</div>
          <div class="info-card-value">${event?.confidence != null ? (event.confidence * 100).toFixed(0) + "%" : "—"}</div>
        </div>
        <div class="info-card">
          <div class="info-card-label">Event Timestamp</div>
          <div class="info-card-value">${esc(eventTimestamp)}</div>
        </div>
        <div class="info-card">
          <div class="info-card-label">Camera</div>
          <div class="info-card-value">${esc(event?.camera_name ?? "—")}</div>
        </div>
        <div class="info-card">
          <div class="info-card-label">Zone</div>
          <div class="info-card-value">${esc(event?.zone_name ?? "—")}</div>
        </div>
        <div class="info-card">
          <div class="info-card-label">Event ID</div>
          <div class="info-card-value" style="font-size:10px">${esc(insight.eventId ?? "—")}</div>
        </div>
        <div class="info-card">
          <div class="info-card-label">Insight ID</div>
          <div class="info-card-value" style="font-size:10px">${esc(insight.id)}</div>
        </div>
      </div>
    </div>
  </div>

  <!-- ===== EVENT EVIDENCE ===== -->
  <div class="section no-break">
    <div class="section-header">
      <div class="section-icon" style="background:#8b5cf6">📷</div>
      <div class="section-title">Event Evidence — Visual Proof</div>
    </div>
    <div class="section-body">
      ${evidenceDataUrl
        ? `<div class="evidence-container">
            <img class="evidence-img" src="${evidenceDataUrl}" alt="Authoritative event evidence frame" />
            <div class="evidence-caption">Authoritative event evidence frame — captured at time of detection</div>
          </div>`
        : `<div class="evidence-unavailable">
            Visual evidence unavailable for this event.<br/>
            This analysis was conducted based on machine telemetry and detection data.
          </div>`}
    </div>
  </div>

  <!-- ===== AI SAFETY ANALYSIS ===== -->
  <div class="section">
    <div class="section-header">
      <div class="section-icon" style="background:#f59e0b">✦</div>
      <div class="section-title">AI Safety Analysis</div>
    </div>
    <div class="section-body">
      ${insight.analysis.eventSummary ? `
      <div class="content-block no-break">
        <div class="content-label">Event Summary</div>
        <div class="content-text">${esc(insight.analysis.eventSummary)}</div>
      </div>` : ""}

      ${insight.analysis.hazardInterpretation ? `
      <div class="content-block no-break">
        <div class="content-label">Hazard Interpretation</div>
        <div class="content-text">${esc(insight.analysis.hazardInterpretation)}</div>
      </div>` : ""}

      ${insight.analysis.riskAssessment ? `
      <div class="content-block no-break">
        <div class="content-label">Risk Assessment</div>
        <div class="content-text">${esc(insight.analysis.riskAssessment)}</div>
      </div>` : ""}

      ${insight.analysis.visualObservations && insight.analysis.visualObservations.length > 0 ? `
      <div class="content-block no-break">
        <div class="content-label">Visual Observations</div>
        <ul class="content-list">
          ${insight.analysis.visualObservations.map((o) => `<li>${esc(o)}</li>`).join("\n          ")}
        </ul>
      </div>` : ""}

      ${insight.analysis.visualValidation ? `
      <div class="content-block no-break">
        <div class="content-label">Visual Validation</div>
        <div class="vv-grid">
          <div class="vv-card">
            <div class="vv-card-label">Detection Supported</div>
            <div class="vv-card-value">${insight.analysis.visualValidation.detection_supported != null
              ? (insight.analysis.visualValidation.detection_supported ? "✓ Yes" : "✗ No")
              : "—"}</div>
          </div>
          <div class="vv-card">
            <div class="vv-card-label">Confidence Note</div>
            <div class="vv-card-value">${esc(insight.analysis.visualValidation.confidence_note as string ?? "—")}</div>
          </div>
          <div class="vv-card">
            <div class="vv-card-label">Scene Context</div>
            <div class="vv-card-value">${esc(insight.analysis.visualValidation.scene_context as string ?? "—")}</div>
          </div>
        </div>
      </div>` : ""}

      ${insight.analysis.contributingFactors && insight.analysis.contributingFactors.length > 0 ? `
      <div class="content-block no-break">
        <div class="content-label">Contributing Factors</div>
        <ul class="content-list">
          ${insight.analysis.contributingFactors.map((f) => `<li>${esc(f)}</li>`).join("\n          ")}
        </ul>
      </div>` : ""}

      ${insight.analysis.uncertainties && insight.analysis.uncertainties.length > 0 ? `
      <div class="content-block no-break">
        <div class="content-label">Uncertainties</div>
        <ul class="content-list">
          ${insight.analysis.uncertainties.map((u) => `<li>${esc(u)}</li>`).join("\n          ")}
        </ul>
      </div>` : ""}
    </div>
  </div>

  <!-- ===== AI RECOMMENDATIONS ===== -->
  <div class="section">
    <div class="section-header">
      <div class="section-icon" style="background:#10b981">💡</div>
      <div class="section-title">AI Recommendations</div>
    </div>
    <div class="section-body">
      ${buildActionSection("Immediate Actions", insight.recommendations.immediateActions)}
      ${buildActionSection("Investigation Actions", insight.recommendations.investigationActions)}
      ${buildActionSection("Preventive Actions", insight.recommendations.preventiveActions)}

      ${insight.recommendations.preventiveGuidance && insight.recommendations.preventiveGuidance.length > 0 ? `
      <div class="content-block no-break">
        <div class="content-label">Preventive Guidance Checklist</div>
        <ul class="checklist">
          ${insight.recommendations.preventiveGuidance.map((g) => `<li>${esc(g)}</li>`).join("\n          ")}
        </ul>
      </div>` : ""}

      ${(!insight.recommendations.immediateActions || insight.recommendations.immediateActions.length === 0)
       && (!insight.recommendations.investigationActions || insight.recommendations.investigationActions.length === 0)
       && (!insight.recommendations.preventiveActions || insight.recommendations.preventiveActions.length === 0)
       && insight.recommendations.actions && insight.recommendations.actions.length > 0
        ? buildActionSection("Recommended Actions", insight.recommendations.actions)
        : ""}
    </div>
  </div>

  <!-- ===== SAFETY INFORMATION ===== -->
  ${insight.safetyInformation.policyText ? `
  <div class="section no-break">
    <div class="section-header">
      <div class="section-icon" style="background:#6366f1">📋</div>
      <div class="section-title">Safety Policy Guidance</div>
    </div>
    <div class="section-body">
      <div class="content-text">${esc(insight.safetyInformation.policyText)}</div>
    </div>
  </div>` : ""}

  <!-- ===== HISTORICAL CONTEXT ===== -->
  ${insight.historicalContext ? `
  <div class="section no-break">
    <div class="section-header">
      <div class="section-icon" style="background:#0ea5e9">📊</div>
      <div class="section-title">Historical Context</div>
    </div>
    <div class="section-body">
      <div class="content-text">${esc(insight.historicalContext)}</div>
    </div>
  </div>` : ""}

  <!-- ===== AUDIT METADATA ===== -->
  <div class="section no-break">
    <div class="section-header">
      <div class="section-icon" style="background:#64748b">🔒</div>
      <div class="section-title">Report Audit Metadata</div>
    </div>
    <div class="section-body">
      <div class="info-grid">
        <div class="info-card">
          <div class="info-card-label">Insight ID</div>
          <div class="info-card-value" style="font-size:10px">${esc(insight.id)}</div>
        </div>
        <div class="info-card">
          <div class="info-card-label">Event ID</div>
          <div class="info-card-value" style="font-size:10px">${esc(insight.eventId ?? "—")}</div>
        </div>
        <div class="info-card">
          <div class="info-card-label">Analysis Generated</div>
          <div class="info-card-value">${esc(insight.generatedAt)}</div>
        </div>
        <div class="info-card">
          <div class="info-card-label">AI Provider</div>
          <div class="info-card-value">${esc(meta?.provider ?? "—")}</div>
        </div>
        <div class="info-card">
          <div class="info-card-label">AI Model</div>
          <div class="info-card-value" style="font-size:10px">${esc(meta?.model ?? "—")}</div>
        </div>
        <div class="info-card">
          <div class="info-card-label">Report Exported</div>
          <div class="info-card-value">${esc(exportTimestamp)}</div>
        </div>
      </div>
    </div>
  </div>

  <!-- ===== FOOTER ===== -->
  <div class="report-footer">
    <strong>SafeVision AI — Safety Intelligence Report</strong><br/>
    This report was generated from persisted AI analysis data. No AI regeneration occurred during export.<br/>
    Confidential — For authorized personnel only. © ${now.getFullYear()} SafeVision AI. All rights reserved.
  </div>

</div>
</body>
</html>`;
}

// ==============================================================================
// Action Table Builder (Reused for Immediate / Investigation / Preventive)
// ==============================================================================

function buildActionSection(
  title: string,
  actions: RecommendationAction[] | undefined,
): string {
  if (!actions || actions.length === 0) return "";

  const rows = actions.map((a) => `
        <tr>
          <td>
            <div class="action-title">${esc(a.title)}</div>
            ${a.procedure && a.procedure !== a.title ? `<div class="action-procedure">${esc(a.procedure)}</div>` : ""}
            ${a.rationale ? `<div class="action-rationale">Rationale: ${esc(a.rationale)}</div>` : ""}
          </td>
          <td>${esc(a.owner)}</td>
          <td>${esc(a.targetDate)}</td>
          <td>${esc(a.expectedOutcome)}</td>
        </tr>`).join("");

  return `
      <div class="content-block no-break">
        <div class="content-label">${esc(title)}</div>
        <table class="action-table">
          <thead>
            <tr>
              <th style="width:40%">Action</th>
              <th style="width:18%">Assigned Role</th>
              <th style="width:18%">Target Timeframe</th>
              <th style="width:24%">Expected Outcome</th>
            </tr>
          </thead>
          <tbody>${rows}
          </tbody>
        </table>
      </div>`;
}
