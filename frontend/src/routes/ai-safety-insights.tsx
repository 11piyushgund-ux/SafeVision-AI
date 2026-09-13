import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, Loader2, Sparkles, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import { AppHeader } from "@/components/AppHeader";
import { AuthGuard } from "@/components/auth-guard";
import { InsightsList } from "@/components/safevision/InsightsList";
import type { InsightListItem } from "@/components/safevision/InsightsList";
import { InsightDetail, type DetailTab } from "@/components/safevision/InsightDetail";
import type { InsightDetailViewModel, RecommendationAction } from "@/components/safevision/InsightDetail";
import type { InsightIconName } from "@/components/safevision/InsightIcon";
import type { RiskLevel } from "@/components/safevision/RiskBadge";
import { fetchAIInsights } from "@/lib/api-client";
import type { AiInsightResponse } from "@/lib/api-types";
import { generateSafetyInsightReport } from "@/lib/report-generator";
import type { ReportMetadata } from "@/lib/report-generator";

interface AISafetyInsightsSearch {
  insight_id?: string | undefined;
}

export const Route = createFileRoute("/ai-safety-insights")({
  validateSearch: (search: Record<string, unknown>): AISafetyInsightsSearch => {
    const raw = search["insight_id"];
    return {
      insight_id: typeof raw === "string" ? raw : undefined,
    };
  },
  head: () => ({
    meta: [
      { title: "AI Safety Insights — SafeVision AI" },
      {
        name: "description",
        content:
          "AI-assisted analysis and recommendations based on safety events, risk context, and relevant safety knowledge.",
      },
      { property: "og:title", content: "AI Safety Insights — SafeVision AI" },
      {
        property: "og:description",
        content:
          "Review detected safety events, risk assessments, safety policies, and historical context in one workplace safety dashboard.",
      },
    ],
  }),
  component: AISafetyInsightsPage,
});

// ==============================================================================
// Adapter — Backend AiInsightResponse → Frontend View-Models
// ==============================================================================

const PLACEHOLDER_TEXTS = new Set([
  "No policy docs available",
  "No specific policy documents available",
  "None",
  "N/A",
  "",
]);

const HISTORY_PLACEHOLDER_TEXTS = new Set([
  "No historical context available",
  "No similar events in recent history",
  "None",
  "N/A",
  "",
]);

function mapEventTypeToIcon(eventType: string | undefined): InsightIconName {
  if (!eventType) return "box";
  const lower = eventType.toLowerCase();
  if (lower.includes("ppe") || lower.includes("helmet")) return "helmet";
  if (lower.includes("fire") || lower.includes("smoke")) return "fire";
  if (lower.includes("zone") || lower.includes("intrusion")) return "crowd";
  if (lower.includes("slip") || lower.includes("fall")) return "slip";
  return "box";
}

function mapRiskLevel(level: string | undefined): RiskLevel {
  if (!level) return "Medium";
  const lower = level.toLowerCase();
  if (lower === "critical" || lower === "high") return "High";
  if (lower === "medium") return "Medium";
  if (lower === "low" || lower === "info") return "Low";
  return "Medium";
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return "—";
  }
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true });
  } catch {
    return "—";
  }
}

function formatGeneratedAt(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    }) + " at " + d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true });
  } catch {
    return "—";
  }
}

/** Sort key sent to the backend. */
function sortKeyFromLabel(label: string): string {
  if (label === "Oldest First") return "oldest";
  if (label === "Highest Risk") return "highest_risk";
  return "newest";
}

/**
 * Safely parse a single AiInsightResponse into list + detail view-models.
 * Returns null if the record is malformed (Correction #3 — resilience).
 */
function adaptInsight(raw: AiInsightResponse): {
  list: InsightListItem;
  detail: InsightDetailViewModel;
} | null {
  try {
    const sc = (raw.source_context ?? {}) as Record<string, unknown>;
    const eventType = String(sc["event_type"] ?? "");
    const riskLevel = mapRiskLevel(String(sc["risk_level"] ?? ""));
    const riskLevelRaw = String(sc["risk_level"] ?? "");
    const eventId = sc["event_id"] ? String(sc["event_id"]) : undefined;
    const icon = mapEventTypeToIcon(eventType);

    // Parse content JSON — the core AI analysis result
    let content: Record<string, unknown> = {};
    try {
      content = JSON.parse(raw.content) as Record<string, unknown>;
    } catch {
      // If content JSON is invalid, still show the row with title-only data
      content = {};
    }

    const summary = String(content["summary"] ?? raw.title ?? "");
    const riskExplanation = String(content["risk_explanation"] ?? "");
    const hazardInterpretation = content["hazard_interpretation"]
      ? String(content["hazard_interpretation"])
      : undefined;
    const contributingFactors = Array.isArray(content["contributing_factors"])
      ? (content["contributing_factors"] as string[])
      : [];
    const uncertainties = Array.isArray(content["uncertainties"])
      ? (content["uncertainties"] as string[])
      : undefined;
    const visualObservations = Array.isArray(content["visual_observations"])
      ? (content["visual_observations"] as string[])
      : undefined;
    const visualValidation = (content["visual_validation"] as {
      detection_supported?: boolean;
      confidence_note?: string;
      scene_context?: string;
      [key: string]: unknown;
    } | null) ?? undefined;

    const rawSpg = String(content["safety_policy_guidance"] ?? "");
    const safetyPolicyGuidance = PLACEHOLDER_TEXTS.has(rawSpg) ? "" : rawSpg;

    const rawHc = String(content["historical_context"] ?? "");
    const historicalContext = HISTORY_PLACEHOLDER_TEXTS.has(rawHc) ? "" : rawHc;

    const generatedAtRaw = String(content["generated_at"] ?? raw.created_at ?? "");

    // Helper to map an action item (object or string)
    const mapActionItem = (
      rawAction: unknown,
      idx: number,
      category: "immediate" | "investigation" | "preventive"
    ): RecommendationAction => {
      const defaultRole =
        category === "immediate"
          ? "Floor Supervisor"
          : category === "investigation"
          ? "Maintenance Lead"
          : "Operations Manager";
      const defaultTime =
        category === "immediate"
          ? "Immediate (<15m)"
          : category === "investigation"
          ? "Current Shift (<4h)"
          : "Next Maintenance Cycle";

      if (typeof rawAction === "object" && rawAction !== null) {
        const obj = rawAction as Record<string, unknown>;
        const title = String(obj["title"] || `Action ${idx + 1}`).trim();
        const procedure = String(obj["procedure"] || obj["description"] || title).trim();
        const rationale = obj["rationale"] ? String(obj["rationale"]).trim() : undefined;
        const owner = String(obj["role"] || obj["owner"] || defaultRole).trim();
        const targetDate = String(obj["timeframe"] || obj["targetDate"] || defaultTime).trim();
        const expectedOutcome = String(
          obj["expected_outcome"] || obj["expectedOutcome"] || "Hazard contained and verified safe"
        ).trim();

        return {
          id: `${category}-${idx + 1}`,
          title,
          description: procedure,
          procedure,
          rationale,
          category,
          owner: owner || defaultRole,
          targetDate: targetDate || defaultTime,
          expectedOutcome: expectedOutcome || "Hazard contained and verified safe",
        };
      }

      // Legacy string format
      const text = String(rawAction || "").trim();
      let title = text;
      let procedure = text;
      if (text.includes(":")) {
        const parts = text.split(":");
        const head = parts[0];
        if (head && head.trim().length < 60) {
          title = head.trim();
          procedure = parts.slice(1).join(":").trim();
        }
      } else if (text.length > 70) {
        const periodIdx = text.indexOf(".");
        if (periodIdx > 15 && periodIdx < 70) {
          title = text.slice(0, periodIdx).trim();
          procedure = text;
        } else {
          title = text.slice(0, 60).trim() + "…";
          procedure = text;
        }
      }

      return {
        id: `${category}-${idx + 1}`,
        title,
        description: procedure,
        procedure,
        category,
        owner: defaultRole,
        targetDate: defaultTime,
        expectedOutcome: "Hazard contained and verified safe",
      };
    };

    // Parse categorized actions if available
    const rawImmediate = Array.isArray(content["immediate_actions"]) ? content["immediate_actions"] : [];
    const rawInvestigation = Array.isArray(content["investigation_actions"]) ? content["investigation_actions"] : [];
    const rawPreventive = Array.isArray(content["preventive_actions"]) ? content["preventive_actions"] : [];
    const rawRecommended = Array.isArray(content["recommended_actions"])
      ? (content["recommended_actions"] as unknown[])
      : [];

    const immediateActions: RecommendationAction[] = rawImmediate.map((item, i) =>
      mapActionItem(item, i, "immediate")
    );
    const investigationActions: RecommendationAction[] = rawInvestigation.map((item, i) =>
      mapActionItem(item, i, "investigation")
    );
    const preventiveActions: RecommendationAction[] = rawPreventive.map((item, i) =>
      mapActionItem(item, i, "preventive")
    );

    // Flattened or legacy actions
    let actions: RecommendationAction[] = [];
    if (immediateActions.length > 0 || investigationActions.length > 0 || preventiveActions.length > 0) {
      actions = [...immediateActions, ...investigationActions, ...preventiveActions];
    } else if (rawRecommended.length > 0) {
      actions = rawRecommended.map((item, i) => {
        const category = i in [0, 1] ? "immediate" : i === 2 ? "investigation" : "preventive";
        return mapActionItem(item, i, category);
      });
    }

    // Populate Preventive Guidance Checklist
    const preventiveGuidance: string[] = [];
    if (preventiveActions.length > 0) {
      for (const act of preventiveActions) {
        if (act.procedure) {
          preventiveGuidance.push(act.procedure);
        } else if (act.title) {
          preventiveGuidance.push(act.title);
        }
      }
    } else if (rawPreventive.length > 0) {
      for (const p of rawPreventive) {
        if (typeof p === "string" && p.trim()) {
          preventiveGuidance.push(p.trim());
        }
      }
    }
    // Fallback: extract from recommendations if still empty
    if (preventiveGuidance.length === 0 && rawRecommended.length > 2) {
      for (let i = 2; i < rawRecommended.length; i++) {
        const text = String(rawRecommended[i] || "").trim();
        if (text) preventiveGuidance.push(text);
      }
    }

    const list: InsightListItem = {
      id: raw.id,
      title: raw.title,
      risk: riskLevel,
      summary,
      date: formatDate(raw.created_at),
      time: formatTime(raw.created_at),
      icon,
    };

    const detail: InsightDetailViewModel = {
      id: raw.id,
      title: raw.title,
      risk: riskLevel,
      icon,
      generatedAt: formatGeneratedAt(generatedAtRaw),
      status: raw.status,
      eventId: eventId || null,
      eventType: eventType || undefined,
      riskLevelRaw: riskLevelRaw || undefined,
      analysis: {
        eventSummary: summary,
        hazardInterpretation,
        riskAssessment: riskExplanation,
        contributingFactors,
        uncertainties,
        visualObservations,
        visualValidation,
      },
      recommendations: {
        actions,
        immediateActions: immediateActions.length > 0 ? immediateActions : undefined,
        investigationActions: investigationActions.length > 0 ? investigationActions : undefined,
        preventiveActions: preventiveActions.length > 0 ? preventiveActions : undefined,
        preventiveGuidance,
      },
      safetyInformation: {
        policyText: safetyPolicyGuidance,
      },
      historicalContext,
    };

    return { list, detail };
  } catch {
    // Malformed record — skip gracefully (Correction #3)
    return null;
  }
}

// ==============================================================================
// Page Component
// ==============================================================================

const PAGE_SIZE = 10;

function AISafetyInsightsPage() {
  return (
    <AuthGuard>
      <AISafetyInsightsContent />
    </AuthGuard>
  );
}

function AISafetyInsightsContent() {
  const search = Route.useSearch();
  const searchInsightId = search?.insight_id;
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tab, setTab] = useState<DetailTab>("analysis");
  const [dateRange, setDateRange] = useState("All Insights");
  const [sortBy, setSortBy] = useState("Newest First");
  const [page, setPage] = useState(1);
  const [isExporting, setIsExporting] = useState(false);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["ai-insights", page, sortBy],
    queryFn: () =>
      fetchAIInsights({
        page,
        size: PAGE_SIZE,
        sort: sortKeyFromLabel(sortBy),
      }),
  });

  // Adapt all backend records — skip malformed ones
  const adapted = (data?.data ?? [])
    .map(adaptInsight)
    .filter((x): x is NonNullable<typeof x> => x !== null);

  const listItems = adapted.map((a) => a.list);
  const detailMap = new Map(adapted.map((a) => [a.detail.id, a.detail]));

  // Selection priority:
  // 1. Explicit user selection on this page (if present in current data)
  // 2. Exact insight_id requested via search params from Analyze button
  // 3. First item in current page list
  const effectiveSelectedId =
    (selectedId && detailMap.has(selectedId) ? selectedId : null) ??
    (searchInsightId && detailMap.has(searchInsightId) ? searchInsightId : null) ??
    listItems[0]?.id ??
    null;

  const selectedDetail = effectiveSelectedId
    ? detailMap.get(effectiveSelectedId) ?? null
    : null;

  const totalInsights = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalInsights / PAGE_SIZE));

  // ---- Export Report Handler ----
  const handleExportReport = async () => {
    if (!selectedDetail || isExporting) return;
    setIsExporting(true);
    try {
      // Extract safe metadata from raw backend response
      const rawInsight = (data?.data ?? []).find((r) => r.id === selectedDetail.id);
      const llmMeta = (rawInsight?.llm_metadata ?? {}) as Record<string, unknown>;
      const srcCtx = (rawInsight?.source_context ?? {}) as Record<string, unknown>;
      const meta: ReportMetadata = {
        provider: llmMeta["provider"] ? String(llmMeta["provider"]) : undefined,
        model: llmMeta["model"] ? String(llmMeta["model"]) : undefined,
        riskScore: srcCtx["risk_score"] != null ? Number(srcCtx["risk_score"]) : undefined,
      };

      await generateSafetyInsightReport(selectedDetail, meta);
      toast.success("Safety Intelligence Report ready for export");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to generate report";
      toast.error(msg);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <AppHeader />

      <main className="mx-auto max-w-[1560px] px-6 py-7">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="flex items-center gap-2.5 text-[28px] font-bold tracking-tight text-foreground">
              <Sparkles className="h-7 w-7 text-primary" strokeWidth={1.8} />
              AI Safety Insights
            </h1>
            <p className="mt-2 max-w-md text-[14px] leading-[1.6] text-muted-foreground">
              AI-assisted analysis and recommendations based on safety events, risk context, and
              relevant safety knowledge.
            </p>
          </div>
          <button
            type="button"
            onClick={handleExportReport}
            disabled={isExporting || !selectedDetail}
            className="inline-flex items-center gap-2.5 rounded-lg border border-primary bg-card px-5 py-3 text-[15px] font-semibold text-primary transition-colors hover:bg-primary/5 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isExporting ? (
              <>
                <Loader2 className="h-[18px] w-[18px] animate-spin" strokeWidth={2} />
                Generating…
              </>
            ) : (
              <>
                <Download className="h-[18px] w-[18px]" strokeWidth={2} />
                Export Report
              </>
            )}
          </button>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="mt-16 flex flex-col items-center justify-center gap-4 py-20 text-center">
            <Loader2 className="h-10 w-10 animate-spin text-primary" />
            <p className="text-[15px] text-muted-foreground">Loading AI insights…</p>
          </div>
        )}

        {/* Error State */}
        {isError && (
          <div className="mt-16 flex flex-col items-center justify-center gap-4 py-20 text-center">
            <AlertTriangle className="h-10 w-10 text-destructive" />
            <p className="text-[15px] text-foreground font-semibold">Failed to load insights</p>
            <p className="text-[14px] text-muted-foreground max-w-md">
              {error instanceof Error ? error.message : "An unexpected error occurred."}
            </p>
          </div>
        )}

        {/* Empty State */}
        {!isLoading && !isError && listItems.length === 0 && (
          <div className="mt-16 flex flex-col items-center justify-center gap-4 py-20 text-center">
            <Sparkles className="h-10 w-10 text-muted-foreground/40" />
            <p className="text-[15px] text-foreground font-semibold">No AI Insights Yet</p>
            <p className="text-[14px] text-muted-foreground max-w-md">
              AI insights are generated when safety events are analyzed. Use the Live Monitoring page
              to process video and generate safety events.
            </p>
          </div>
        )}

        {/* Master-Detail Layout */}
        {!isLoading && !isError && listItems.length > 0 && selectedDetail && (
          <div className="mt-6 grid items-start gap-6 lg:grid-cols-[minmax(0,0.62fr)_minmax(0,1fr)]">
            <InsightsList
              insights={listItems}
              selectedId={effectiveSelectedId!}
              onSelect={(id) => {
                setSelectedId(id);
              }}
              dateRange={dateRange}
              onDateRangeChange={setDateRange}
              sortBy={sortBy}
              onSortByChange={(v) => {
                setSortBy(v);
                setPage(1);
              }}
              page={page}
              onPageChange={setPage}
              totalInsights={totalInsights}
              totalPages={totalPages}
            />
            <InsightDetail insight={selectedDetail} tab={tab} onTabChange={setTab} />
          </div>
        )}

        <footer className="mt-8 border-t border-border pt-5 text-center text-[13px] text-muted-foreground">
          © 2025 SafeVision AI. All rights reserved.
        </footer>
      </main>
    </div>
  );
}
