import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  AlertTriangle,
  Calendar,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  Clock,
  FileText,
  ImageOff,
  Info,
  Loader2,
  MapPin,
  Maximize2,
  Minimize2,
  Search,
  Shield,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-react";
import { AppHeader } from "@/components/AppHeader";
import { AuthGuard } from "@/components/auth-guard";
import { fetchAlerts, fetchAlertEvidenceBlobUrl, transitionAlert, analyzeEventWithAI } from "@/lib/api-client";
import type { AlertResponse, AIAnalysisResult } from "@/lib/api-types";

export const Route = createFileRoute("/alerts")({
  head: () => ({
    meta: [
      { title: "Safety Alerts | SafeVision AI" },
      {
        name: "description",
        content:
          "Review, acknowledge, escalate and resolve AI-detected workplace safety alerts across cameras and zones.",
      },
      { property: "og:title", content: "Safety Alerts | SafeVision AI" },
      {
        property: "og:description",
        content: "Review and manage safety events that require attention.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: SafetyAlertsPage,
});

// Severity config matching backend AlertSeverity enum values
const SEVERITY_OPTIONS = ["critical", "high", "medium", "low", "info"] as const;
const SEVERITY_LABELS: Record<string, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  info: "Info",
};
const severityToneClass: Record<string, string> = {
  critical: "bg-destructive/10 text-destructive",
  high: "bg-destructive/10 text-destructive",
  medium: "bg-amber-500/10 text-amber-600",
  low: "bg-blue-500/10 text-blue-600",
  info: "bg-muted text-muted-foreground",
};

// Status config matching backend AlertStatus enum values
const STATUS_OPTIONS = ["new", "acknowledged", "investigating", "escalated", "resolved", "closed", "false_positive"] as const;
const STATUS_LABELS: Record<string, string> = {
  new: "New",
  acknowledged: "Acknowledged",
  investigating: "Investigating",
  escalated: "Escalated",
  resolved: "Resolved",
  closed: "Closed",
  false_positive: "False Positive",
};

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function AlertEvidenceImage({ alert }: { alert: AlertResponse | null }) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(document.fullscreenElement === containerRef.current);
    };
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
    };
  }, []);

  const toggleFullscreen = async () => {
    try {
      if (!document.fullscreenElement) {
        if (containerRef.current?.requestFullscreen) {
          await containerRef.current.requestFullscreen();
        }
      } else {
        if (document.exitFullscreen) {
          await document.exitFullscreen();
        }
      }
    } catch (err) {
      console.error("Failed to toggle evidence fullscreen:", err);
    }
  };

  useEffect(() => {
    let active = true;
    let currentUrl: string | null = null;

    if (alert?.id && alert.evidence_path) {
      setIsLoading(true);
      setImageUrl(null);
      fetchAlertEvidenceBlobUrl(alert.id)
        .then((url) => {
          if (!active) {
            if (url) URL.revokeObjectURL(url);
            return;
          }
          currentUrl = url;
          setImageUrl(url);
        })
        .finally(() => {
          if (active) setIsLoading(false);
        });
    } else {
      setImageUrl(null);
      setIsLoading(false);
    }

    return () => {
      active = false;
      if (currentUrl) URL.revokeObjectURL(currentUrl);
    };
  }, [alert?.id, alert?.evidence_path]);

  if (!alert) {
    return (
      <span className="flex h-24 w-24 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
        <ClipboardList className="h-10 w-10" />
      </span>
    );
  }

  if (isLoading) {
    return (
      <div className="flex h-36 w-full max-w-xs items-center justify-center rounded-xl border border-border bg-black/40 text-muted-foreground">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
      </div>
    );
  }

  if (imageUrl) {
    return (
      <div
        ref={containerRef}
        className={
          isFullscreen
            ? "flex h-full w-full items-center justify-center bg-black relative"
            : "relative w-full max-w-xs overflow-hidden rounded-xl border border-border bg-black/90 shadow-sm"
        }
      >
        <button
          type="button"
          onClick={toggleFullscreen}
          aria-label={isFullscreen ? "Exit fullscreen" : "Maximize evidence"}
          className="absolute right-2.5 top-2.5 z-10 rounded-md bg-[oklch(0.15_0_0/0.75)] p-1.5 text-[oklch(0.98_0_0)] backdrop-blur-md transition-colors hover:opacity-80"
        >
          {isFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
        </button>
        <img
          src={imageUrl}
          alt={`Visual evidence for alert ${alert.id}`}
          className={
            isFullscreen
              ? "max-h-full max-w-full object-contain"
              : "aspect-video w-full object-contain"
          }
        />
      </div>
    );
  }

  return (
    <div className="flex h-28 w-full max-w-xs flex-col items-center justify-center gap-1.5 rounded-xl border border-dashed border-border bg-muted/30 p-3 text-center">
      <ImageOff className="h-6 w-6 text-muted-foreground/60" />
      <span className="text-xs font-medium text-foreground">Evidence unavailable</span>
      <span className="text-[11px] text-muted-foreground">Historical alert or capture unavailable</span>
    </div>
  );
}

function SafetyAlertsPage() {
  return (
    <AuthGuard>
      <SafetyAlertsContent />
    </AuthGuard>
  );
}

function SafetyAlertsContent() {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState("");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [aiResult, setAiResult] = useState<AIAnalysisResult | null>(null);
  const [createdInsightId, setCreatedInsightId] = useState<string | null>(null);
  const [aiError, setAiError] = useState<string | null>(null);

  const queryClient = useQueryClient();

  // Fetch alerts from backend
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["alerts", page, severityFilter, statusFilter],
    queryFn: () =>
      fetchAlerts({
        page,
        size: 50,
        severity: severityFilter === "all" ? null : severityFilter,
        status: statusFilter === "all" ? null : statusFilter,
      }),
  });

  // Transition mutation
  const transitionMutation = useMutation({
    mutationFn: ({ alertId, status, reason }: { alertId: string; status: string; reason?: string }) =>
      transitionAlert(alertId, { status, reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      toast.success("Alert status updated");
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : "Failed to update alert status");
    },
  });

  const alerts = data?.data ?? [];

  // Client-side search filter (backend handles severity/status)
  const filteredAlerts = alerts.filter((alert) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.trim().toLowerCase();
    return (
      alert.title.toLowerCase().includes(q) ||
      (alert.description?.toLowerCase().includes(q) ?? false)
    );
  });

  const selectedAlert = filteredAlerts.find((a) => a.id === selectedAlertId) ?? null;

  useEffect(() => {
    setAiResult(null);
    setCreatedInsightId(null);
    setAiError(null);
  }, [selectedAlertId]);

  const handleAnalyze = async () => {
    if (!selectedAlert?.event_id) {
      toast.error("No associated safety event found for this alert");
      return;
    }
    if (isAnalyzing) return;
    setIsAnalyzing(true);
    setAiError(null);

    try {
      const res = await analyzeEventWithAI(selectedAlert.event_id);
      if (res.success && res.analysis) {
        setAiResult(res.analysis);
        setCreatedInsightId(res.insight_id ?? null);
        toast.success("AI Safety Analysis completed");
        await queryClient.invalidateQueries({ queryKey: ["ai-insights"] });
      } else {
        const errorMsg = res.error || "AI Analysis failed";
        setAiError(errorMsg);
        toast.error(errorMsg);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to analyze event";
      setAiError(msg);
      toast.error(msg);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const detailRows: { label: string; value: string; Icon: typeof MapPin }[] = [
    { label: "Title", value: selectedAlert?.title ?? "—", Icon: FileText },
    { label: "Severity", value: selectedAlert ? (SEVERITY_LABELS[selectedAlert.severity] ?? selectedAlert.severity) : "—", Icon: AlertTriangle },
    { label: "Status", value: selectedAlert ? (STATUS_LABELS[selectedAlert.status] ?? selectedAlert.status) : "—", Icon: ShieldCheck },
    { label: "Created At", value: selectedAlert ? formatDateTime(selectedAlert.created_at) : "—", Icon: Clock },
    { label: "Updated At", value: selectedAlert ? formatDateTime(selectedAlert.updated_at) : "—", Icon: Calendar },
  ];

  const canAcknowledge = selectedAlert?.status === "new";

  const canEscalate =
    selectedAlert?.status === "new" ||
    selectedAlert?.status === "acknowledged" ||
    selectedAlert?.status === "investigating";

  const canResolve =
    selectedAlert?.status === "acknowledged" ||
    selectedAlert?.status === "escalated" ||
    selectedAlert?.status === "investigating";

  const acknowledgeSub = !selectedAlert
    ? "Mark as acknowledged"
    : selectedAlert.status === "new"
    ? "Mark as acknowledged"
    : selectedAlert.status === "acknowledged"
    ? "Already acknowledged"
    : selectedAlert.status === "resolved"
    ? "Alert is resolved"
    : "Not available for current status";

  const escalateSub = !selectedAlert
    ? "Notify supervisor"
    : canEscalate
    ? "Notify supervisor"
    : selectedAlert.status === "escalated"
    ? "Already escalated"
    : selectedAlert.status === "resolved"
    ? "Alert is resolved"
    : "Not available for current status";

  const resolveSub = !selectedAlert
    ? "Mark as resolved"
    : canResolve
    ? "Mark as resolved"
    : selectedAlert.status === "new"
    ? "Acknowledge or escalate first"
    : selectedAlert.status === "resolved"
    ? "Alert is resolved"
    : "Not available for current status";

  const handleTransition = (status: string) => {
    if (!selectedAlert) return;
    if (status === "acknowledged" && !canAcknowledge) return;
    if (status === "escalated" && !canEscalate) return;
    if (status === "resolved" && !canResolve) return;
    transitionMutation.mutate({ alertId: selectedAlert.id, status });
  };

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <AppHeader />

      <main className="mx-auto w-full max-w-[1560px] flex-1 px-6 py-6">
        <h1 className="inline-flex items-center gap-3 text-3xl font-bold tracking-tight">
          SAFETY ALERTS
          <ShieldCheck className="h-6 w-6 text-muted-foreground" />
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Review and manage safety events that require attention.
        </p>

        <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-2">
          {/* Alert list */}
          <section className="flex flex-col rounded-xl border border-border bg-card">
            <div className="flex flex-wrap items-center gap-3 border-b border-border p-5">
              <label className="relative min-w-[220px] flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search alerts..."
                  aria-label="Search alerts"
                  className="w-full rounded-lg border border-border bg-card py-2.5 pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-ring"
                />
              </label>

              <FilterSelect
                label="Severity"
                value={severityFilter}
                onChange={setSeverityFilter}
                options={[
                  { value: "all", label: "All" },
                  ...SEVERITY_OPTIONS.map((s) => ({ value: s, label: SEVERITY_LABELS[s] ?? s })),
                ]}
              />
              <FilterSelect
                label="Status"
                value={statusFilter}
                onChange={setStatusFilter}
                options={[
                  { value: "all", label: "All" },
                  ...STATUS_OPTIONS.map((s) => ({ value: s, label: STATUS_LABELS[s] ?? s })),
                ]}
              />
            </div>

            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <p className="text-xs font-bold tracking-[0.12em] text-muted-foreground">
                ALERT LIST
              </p>
              <p className="text-sm text-muted-foreground">
                Total: <span className="font-semibold text-foreground">{data?.total ?? 0}</span>
                {data && data.total > data.size && (
                  <span className="ml-2 text-xs">
                    (Page {data.page})
                  </span>
                )}
              </p>
            </div>

            {isLoading ? (
              <div className="flex flex-1 items-center justify-center py-24">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : isError ? (
              <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 py-24 text-center">
                <AlertTriangle className="h-8 w-8 text-destructive" />
                <p className="text-sm text-destructive">{error instanceof Error ? error.message : "Failed to load alerts"}</p>
              </div>
            ) : filteredAlerts.length === 0 ? (
              <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 py-24 text-center">
                <span className="flex h-24 w-24 items-center justify-center rounded-full bg-primary/10 text-primary">
                  <ShieldCheck className="h-10 w-10" />
                </span>
                <div>
                  <p className="text-xl font-bold">No active safety alerts</p>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Real-time safety events requiring attention
                    <br />
                    will appear here automatically.
                  </p>
                </div>
              </div>
            ) : (
              <ul className="flex-1">
                {filteredAlerts.map((alert) => (
                  <li key={alert.id}>
                    <button
                      onClick={() => setSelectedAlertId(alert.id)}
                      className={`flex w-full items-start gap-3 border-b border-border px-5 py-4 text-left transition-colors hover:bg-accent ${
                        selectedAlertId === alert.id ? "bg-accent" : ""
                      }`}
                    >
                      <span
                        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${severityToneClass[alert.severity] ?? "bg-muted text-muted-foreground"}`}
                      >
                        <AlertTriangle className="h-5 w-5" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm font-semibold">
                          {alert.title}
                        </span>
                        <span className="block text-xs text-muted-foreground">
                          {STATUS_LABELS[alert.status] ?? alert.status} · {SEVERITY_LABELS[alert.severity] ?? alert.severity}
                        </span>
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {formatDateTime(alert.created_at)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {/* Pagination */}
            {data && data.total > data.size && (
              <div className="flex items-center justify-between border-t border-border px-5 py-3">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="rounded-lg px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent disabled:opacity-50"
                >
                  Previous
                </button>
                <span className="text-xs text-muted-foreground">Page {page}</span>
                <button
                  disabled={page * data.size >= data.total}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded-lg px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            )}
          </section>

          {/* Alert details */}
          <section className="flex flex-col rounded-xl border border-border bg-card">
            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <span className="inline-flex items-center gap-2 text-sm font-bold tracking-wide">
                <AlertTriangle className="h-5 w-5 text-destructive" />
                ALERT DETAILS
              </span>
              <div className="flex items-center gap-3">
                {selectedAlert && (
                  <button
                    type="button"
                    id="alert-details-analyze-btn"
                    disabled={isAnalyzing}
                    onClick={handleAnalyze}
                    className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground shadow-sm transition-all hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isAnalyzing ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        <span>Analyzing...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-3.5 w-3.5" />
                        <span>Analyze</span>
                      </>
                    )}
                  </button>
                )}
                <span className="text-sm text-muted-foreground">
                  {selectedAlert ? (SEVERITY_LABELS[selectedAlert.severity] ?? selectedAlert.severity) : "No alert selected"}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-6 border-b border-border p-6 md:grid-cols-2">
              <div className="flex flex-col items-center justify-center gap-4 text-center md:border-r md:border-border md:pr-6">
                <AlertEvidenceImage alert={selectedAlert} />
                <div>
                  <p className="text-lg font-bold">
                    {selectedAlert?.title ?? "No alert selected"}
                  </p>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {selectedAlert
                      ? `Status: ${STATUS_LABELS[selectedAlert.status] ?? selectedAlert.status}`
                      : "Select an alert from the list to view details and take action."}
                  </p>
                </div>
              </div>

              <dl className="space-y-4">
                {detailRows.map(({ label, value, Icon }) => (
                  <div key={label} className="flex items-start gap-3">
                    <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                    <div>
                      <dt className="text-sm font-semibold">{label}</dt>
                      <dd className="text-sm text-muted-foreground">{value}</dd>
                    </div>
                  </div>
                ))}
              </dl>
            </div>

            <div className="grid grid-cols-1 gap-4 border-b border-border p-6 md:grid-cols-2">
              <div className="rounded-lg border border-border p-4">
                <p className="text-xs font-bold tracking-[0.1em] text-muted-foreground">
                  ALERT DESCRIPTION
                </p>
                <p className="mt-3 text-sm text-muted-foreground">
                  {selectedAlert?.description ??
                    "Select an alert to view description and more information."}
                </p>
              </div>
              <div className="rounded-lg border border-border bg-primary/5 p-4">
                <p className="inline-flex items-center gap-2 text-xs font-bold tracking-[0.1em] text-primary">
                  <Shield className="h-4 w-4" />
                  METADATA
                </p>
                <div className="mt-3 space-y-1 text-sm text-muted-foreground">
                  {selectedAlert?.event_id && <p>Event: {selectedAlert.event_id}</p>}
                  {selectedAlert?.rule_id && <p>Rule: {selectedAlert.rule_id}</p>}
                  {selectedAlert?.assigned_to && <p>Assigned to: {selectedAlert.assigned_to}</p>}
                  {selectedAlert?.resolved_at && <p>Resolved: {formatDateTime(selectedAlert.resolved_at)}</p>}
                  {!selectedAlert && <p>Select an alert to view metadata.</p>}
                </div>
              </div>
            </div>

            {/* Inline AI Analysis Result Section */}
            {aiError && (
              <div className="border-b border-border p-6">
                <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-xs text-destructive">
                  <p className="font-semibold">AI Analysis Failed</p>
                  <p className="mt-1">{aiError}</p>
                </div>
              </div>
            )}

            {aiResult && (
              <div className="border-b border-border p-6">
                <div className="rounded-xl border border-primary/20 bg-primary/5 p-5 space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 pb-3">
                    <div className="flex items-center gap-2">
                      <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
                        <Sparkles className="h-4 w-4" />
                      </span>
                      <div>
                        <h4 className="text-sm font-bold text-foreground">AI Safety Intelligence</h4>
                        <p className="text-[11px] text-muted-foreground">
                          Multimodal evaluation of authoritative event evidence
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="inline-flex items-center rounded-md bg-primary/10 px-2 py-0.5 text-xs font-mono font-medium text-primary">
                        {aiResult.provider} ({aiResult.model})
                      </span>
                      {createdInsightId && (
                        <button
                          type="button"
                          id="alert-view-full-ai-insight-header-btn"
                          onClick={() => {
                            navigate({
                              to: "/ai-safety-insights",
                              search: { insight_id: createdInsightId },
                            });
                          }}
                          className="inline-flex items-center gap-1 rounded-md bg-primary px-2.5 py-1 text-xs font-semibold text-primary-foreground shadow-sm hover:opacity-90"
                        >
                          <span>View Full AI Insight</span>
                          <ChevronRight className="h-3 w-3" />
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Summary */}
                  <div>
                    <p className="text-xs font-bold tracking-wider text-muted-foreground uppercase">
                      Executive Summary
                    </p>
                    <p className="mt-1 text-sm font-medium text-foreground leading-relaxed">
                      {aiResult.summary}
                    </p>
                  </div>

                  {/* Risk Explanation */}
                  {aiResult.risk_explanation && (
                    <div>
                      <p className="text-xs font-bold tracking-wider text-muted-foreground uppercase">
                        Risk Assessment Explanation
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
                        {aiResult.risk_explanation}
                      </p>
                    </div>
                  )}

                  {/* Visual Observations */}
                  {aiResult.visual_observations && aiResult.visual_observations.length > 0 && (
                    <div>
                      <p className="text-xs font-bold tracking-wider text-muted-foreground uppercase">
                        Visual Evidence Observations
                      </p>
                      <ul className="mt-1.5 list-disc list-inside space-y-1 text-xs text-foreground">
                        {aiResult.visual_observations.map((obs, i) => (
                          <li key={i}>{obs}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Visual Validation */}
                  {aiResult.visual_validation && typeof aiResult.visual_validation === "object" && (
                    <div className="rounded-lg border border-border bg-card/60 p-3 text-xs space-y-1">
                      <p className="font-semibold text-foreground">Visual Validation</p>
                      {Object.entries(aiResult.visual_validation).map(([k, v]) => (
                        <div key={k} className="text-muted-foreground">
                          <span className="font-medium text-foreground capitalize">{k.replace(/_/g, " ")}: </span>
                          <span>{typeof v === "object" ? JSON.stringify(v) : String(v)}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Hazard Interpretation (Phase 14F) */}
                  {aiResult.hazard_interpretation && (
                    <div className="rounded border border-amber-500/25 bg-amber-500/5 p-2.5 text-xs">
                      <p className="text-[10px] font-bold uppercase tracking-wider text-amber-500">
                        Hazard Interpretation
                      </p>
                      <p className="mt-1 text-foreground leading-relaxed">
                        {aiResult.hazard_interpretation}
                      </p>
                    </div>
                  )}

                  {/* Recommended Actions Plan (Structured or Legacy) */}
                  {((aiResult.immediate_actions && aiResult.immediate_actions.length > 0) ||
                    (aiResult.investigation_actions && aiResult.investigation_actions.length > 0) ||
                    (aiResult.preventive_actions && aiResult.preventive_actions.length > 0) ||
                    (aiResult.recommended_actions && aiResult.recommended_actions.length > 0)) && (
                    <div className="space-y-2">
                      <p className="text-xs font-bold tracking-wider text-muted-foreground uppercase">
                        Recommended Action Plan
                      </p>
                      {aiResult.immediate_actions && aiResult.immediate_actions.length > 0 ? (
                        <div className="space-y-1.5">
                          {aiResult.immediate_actions.map((act, i) => {
                            const title = typeof act === "object" ? act.title : (act.includes(":") ? act.split(":")[0] : act);
                            const proc = typeof act === "object" ? act.procedure : (act.includes(":") ? act.split(":").slice(1).join(":") : act);
                            return (
                              <div key={i} className="rounded border border-risk-high/30 bg-risk-high/5 p-2 text-xs">
                                <div className="flex items-center gap-1.5 font-semibold text-foreground">
                                  <span className="rounded bg-risk-high/20 px-1 py-0.5 text-[9px] font-bold text-risk-high uppercase">Immediate</span>
                                  <span>{title}</span>
                                </div>
                                <p className="mt-1 text-muted-foreground text-[11px] leading-relaxed">{proc}</p>
                              </div>
                            );
                          })}
                          {aiResult.investigation_actions?.map((act, i) => {
                            const title = typeof act === "object" ? act.title : (act.includes(":") ? act.split(":")[0] : act);
                            const proc = typeof act === "object" ? act.procedure : (act.includes(":") ? act.split(":").slice(1).join(":") : act);
                            return (
                              <div key={i} className="rounded border border-primary/30 bg-primary/5 p-2 text-xs">
                                <div className="flex items-center gap-1.5 font-semibold text-foreground">
                                  <span className="rounded bg-primary/20 px-1 py-0.5 text-[9px] font-bold text-primary uppercase">Investigation</span>
                                  <span>{title}</span>
                                </div>
                                <p className="mt-1 text-muted-foreground text-[11px] leading-relaxed">{proc}</p>
                              </div>
                            );
                          })}
                          {aiResult.preventive_actions?.map((act, i) => {
                            const title = typeof act === "object" ? act.title : (act.includes(":") ? act.split(":")[0] : act);
                            const proc = typeof act === "object" ? act.procedure : (act.includes(":") ? act.split(":").slice(1).join(":") : act);
                            return (
                              <div key={i} className="rounded border border-risk-low/30 bg-risk-low/5 p-2 text-xs">
                                <div className="flex items-center gap-1.5 font-semibold text-foreground">
                                  <span className="rounded bg-risk-low/20 px-1 py-0.5 text-[9px] font-bold text-risk-low uppercase">Preventive</span>
                                  <span>{title}</span>
                                </div>
                                <p className="mt-1 text-muted-foreground text-[11px] leading-relaxed">{proc}</p>
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <ul className="mt-1.5 list-disc list-inside space-y-1 text-xs text-foreground">
                          {aiResult.recommended_actions.map((act, i) => (
                            <li key={i}>{act}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}

                  {/* Footer navigation */}
                  {createdInsightId && (
                    <div className="pt-2 border-t border-border flex items-center justify-between">
                      <span className="text-[11px] text-muted-foreground">
                        Persisted to AI Safety Insights (ID: <code className="font-mono text-[10px]">{createdInsightId.slice(0, 8)}...</code>)
                      </span>
                      <button
                        type="button"
                        id="alert-view-full-ai-insight-footer-btn"
                        onClick={() => {
                          navigate({
                            to: "/ai-safety-insights",
                            search: { insight_id: createdInsightId },
                          });
                        }}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-1.5 text-xs font-semibold text-primary-foreground shadow-sm hover:opacity-90"
                      >
                        <span>View Full AI Insight</span>
                        <ChevronRight className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )}

            <div className="p-6">
              <p className="text-xs font-bold tracking-[0.1em] text-muted-foreground">
                ALERT ACTIONS
              </p>
              <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
                <ActionButton
                  Icon={CheckCircle2}
                  title={selectedAlert?.status === "acknowledged" ? "Acknowledged" : "Acknowledge"}
                  sub={acknowledgeSub}
                  disabled={!selectedAlert || !canAcknowledge || transitionMutation.isPending}
                  className={
                    canAcknowledge
                      ? "bg-primary text-primary-foreground shadow-sm hover:opacity-90"
                      : "border border-border bg-muted/40 text-muted-foreground"
                  }
                  iconClass={canAcknowledge ? "text-primary-foreground" : "text-muted-foreground"}
                  titleClass={canAcknowledge ? "" : "text-muted-foreground"}
                  onClick={() => handleTransition("acknowledged")}
                />
                <ActionButton
                  Icon={UserRound}
                  title={selectedAlert?.status === "escalated" ? "Escalated" : "Escalate"}
                  sub={escalateSub}
                  disabled={!selectedAlert || !canEscalate || transitionMutation.isPending}
                  className={
                    canEscalate
                      ? "border border-amber-500/40 bg-card hover:bg-amber-500/10"
                      : "border border-border bg-muted/40 text-muted-foreground"
                  }
                  iconClass={canEscalate ? "text-amber-500" : "text-muted-foreground"}
                  titleClass={canEscalate ? "" : "text-muted-foreground"}
                  onClick={() => handleTransition("escalated")}
                />
                <ActionButton
                  Icon={CheckCircle2}
                  title={selectedAlert?.status === "resolved" ? "Resolved" : "Resolve"}
                  sub={resolveSub}
                  disabled={!selectedAlert || !canResolve || transitionMutation.isPending}
                  className={
                    canResolve
                      ? "border border-green-500/40 bg-green-500/5 hover:bg-green-500/15"
                      : "border border-border bg-muted/40 text-muted-foreground"
                  }
                  iconClass={canResolve ? "text-green-500" : "text-muted-foreground"}
                  titleClass={canResolve ? "text-green-600 font-bold" : "text-muted-foreground"}
                  onClick={() => handleTransition("resolved")}
                />
              </div>

              <p className="mt-4 inline-flex w-full items-center gap-2 rounded-lg border border-border bg-primary/5 px-4 py-3 text-sm text-muted-foreground">
                <Info className="h-4 w-4 shrink-0 text-primary" />
                After acknowledging and resolving, this alert will be moved to the Event History.
              </p>
            </div>
          </section>
        </div>
      </main>

      <footer className="border-t border-border py-5 text-center text-sm text-muted-foreground">
        © 2025 SafeVision AI. All rights reserved.
      </footer>
    </div>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="rounded-lg border border-border px-3 py-1.5">
      <span className="block text-[11px] text-muted-foreground">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-transparent text-sm font-medium outline-none"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function ActionButton({
  Icon,
  title,
  sub,
  disabled,
  className,
  iconClass,
  titleClass,
  onClick,
}: {
  Icon: typeof CheckCircle2;
  title: string;
  sub: string;
  disabled?: boolean;
  className?: string;
  iconClass?: string;
  titleClass?: string;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`flex items-center gap-3 rounded-lg px-4 py-3 text-left transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50 ${className ?? ""}`}
    >
      <Icon className={`h-6 w-6 shrink-0 ${iconClass ?? ""}`} />
      <span>
        <span className={`block text-sm font-semibold ${titleClass ?? ""}`}>{title}</span>
        <span className="block text-xs opacity-80">{sub}</span>
      </span>
    </button>
  );
}
