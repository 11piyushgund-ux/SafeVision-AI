import { useState, useEffect, useRef } from "react";
import {
  AlertTriangle,
  BookOpen,
  Camera,
  CheckCircle2,
  Clock,
  Eye,
  FileText,
  HelpCircle,
  History,
  ImageOff,
  Info,
  Lightbulb,
  Loader2,
  Maximize2,
  Minimize2,
  Sparkles,
  UserCheck,
} from "lucide-react";
import type { InsightIconName } from "./InsightIcon";
import type { RiskLevel } from "./RiskBadge";
import { InsightIcon } from "./InsightIcon";
import { RiskChip } from "./RiskBadge";
import { fetchEventEvidenceBlobUrl } from "@/lib/api-client";

export type DetailTab = "analysis" | "recommendation" | "safety" | "history" | "evidence";

/** Recommendation action — populated from real backend data. */
export type RecommendationAction = {
  id: string;
  title: string;
  description: string;
  procedure?: string | undefined;
  rationale?: string | undefined;
  category?: ("immediate" | "investigation" | "preventive") | undefined;
  owner: string;
  targetDate: string;
  expectedOutcome: string;
};

/** View-model consumed by InsightDetail. */
export type InsightDetailViewModel = {
  id: string;
  title: string;
  risk: RiskLevel;
  icon: InsightIconName;
  generatedAt: string;
  /** Real backend status: pending | reviewed | acted_on | dismissed */
  status: string;
  /** Event ID from source_context — used for evidence retrieval. */
  eventId?: string | null;
  /** Event type label from source_context. */
  eventType?: string | undefined;
  /** Risk level string from source_context (for evidence metadata). */
  riskLevelRaw?: string | undefined;
  analysis: {
    eventSummary: string;
    hazardInterpretation?: string | undefined;
    riskAssessment: string;
    contributingFactors: string[];
    uncertainties?: string[] | undefined;
    visualObservations?: string[] | undefined;
    visualValidation?: {
      detection_supported?: boolean | undefined;
      confidence_note?: string | undefined;
      scene_context?: string | undefined;
      [key: string]: unknown;
    } | null | undefined;
  };
  recommendations: {
    actions: RecommendationAction[];
    immediateActions?: RecommendationAction[] | undefined;
    investigationActions?: RecommendationAction[] | undefined;
    preventiveActions?: RecommendationAction[] | undefined;
    preventiveGuidance: string[];
  };
  safetyInformation: {
    policyText: string;
  };
  historicalContext: string;
};

const tabs: { id: DetailTab; label: string; Icon: typeof Sparkles }[] = [
  { id: "analysis", label: "AI Analysis", Icon: Sparkles },
  { id: "recommendation", label: "AI Recommendation", Icon: Lightbulb },
  { id: "safety", label: "Safety Information", Icon: FileText },
  { id: "history", label: "Historical Context", Icon: History },
  { id: "evidence", label: "Event Evidence", Icon: Camera },
];

/** Maps backend status values to human-readable labels. */
function formatStatus(status: string): string {
  switch (status) {
    case "pending":
      return "Pending";
    case "reviewed":
      return "Reviewed";
    case "acted_on":
      return "Acted On";
    case "dismissed":
      return "Dismissed";
    default:
      return status.charAt(0).toUpperCase() + status.slice(1);
  }
}

/** Maps backend status to badge styling. */
function statusBadgeClass(status: string): string {
  switch (status) {
    case "reviewed":
      return "bg-risk-low-soft text-risk-low";
    case "acted_on":
      return "bg-primary-soft text-primary";
    case "dismissed":
      return "bg-muted text-muted-foreground";
    default: // pending
      return "bg-primary-soft text-primary";
  }
}

export function InsightDetail({
  insight,
  tab,
  onTabChange,
}: {
  insight: InsightDetailViewModel;
  tab: DetailTab;
  onTabChange: (tab: DetailTab) => void;
}) {
  return (
    <section className="overflow-hidden rounded-xl border border-border bg-card shadow-card">
      <div className="flex flex-wrap items-start gap-4 px-7 pt-7">
        <InsightIcon icon={insight.icon} size="lg" />
        <div className="min-w-0 flex-1">
          <h2 className="text-[24px] font-bold tracking-tight text-foreground">{insight.title}</h2>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <RiskChip risk={insight.risk} />
            <span className="text-[14px] text-muted-foreground">
              AI Insight generated on {insight.generatedAt}
            </span>
          </div>
        </div>
        <span className={`inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-[13px] font-medium ${statusBadgeClass(insight.status)}`}>
          <span className="h-2 w-2 rounded-full bg-current" />
          {formatStatus(insight.status)}
        </span>
      </div>

      <div className="mt-6 border-b border-border px-7">
        <div role="tablist" className="flex flex-wrap gap-8">
          {tabs.map(({ id, label, Icon }) => {
            const active = id === tab;
            return (
              <button
                key={id}
                role="tab"
                aria-selected={active}
                type="button"
                onClick={() => onTabChange(id)}
                className={`-mb-px flex items-center gap-2 border-b-2 pb-3.5 text-[15px] font-medium transition-colors ${
                  active
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                <Icon className="h-[18px] w-[18px]" strokeWidth={1.8} />
                {label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="px-7 py-7">
        {tab === "analysis" && <AnalysisTab insight={insight} />}
        {tab === "recommendation" && <RecommendationTab insight={insight} />}
        {tab === "safety" && <SafetyTab insight={insight} />}
        {tab === "history" && <HistoryTab insight={insight} />}
        {tab === "evidence" && <EvidenceTab insight={insight} />}
      </div>
    </section>
  );
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-[15px] font-bold uppercase tracking-[0.04em] text-foreground">
      {children}
    </h3>
  );
}

function AnalysisTab({ insight }: { insight: InsightDetailViewModel }) {
  const { analysis } = insight;

  return (
    <div className="space-y-6">
      {/* Event Summary */}
      <div>
        <SectionHeading>Event Summary</SectionHeading>
        <p className="mt-3 max-w-3xl text-[15px] leading-[1.75] text-foreground">
          {analysis.eventSummary}
        </p>
      </div>

      {/* Hazard Interpretation (Phase 14F) */}
      {analysis.hazardInterpretation && (
        <div className="rounded-xl border border-amber-500/25 bg-amber-500/5 p-5">
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            <SectionHeading>Hazard Interpretation & Escalation Analysis</SectionHeading>
          </div>
          <p className="mt-3 text-[15px] leading-[1.75] text-foreground">
            {analysis.hazardInterpretation}
          </p>
        </div>
      )}

      {/* Visual Evidence Validation (Phase 14F Multimodal) */}
      {(analysis.visualValidation || (analysis.visualObservations && analysis.visualObservations.length > 0)) && (
        <div className="rounded-xl border border-border bg-card p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Eye className="h-5 w-5 text-primary" />
              <SectionHeading>Visual Evidence Validation</SectionHeading>
            </div>
            {analysis.visualValidation && (
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${
                  analysis.visualValidation.detection_supported
                    ? "bg-risk-low-soft text-risk-low"
                    : "bg-risk-high-soft text-risk-high"
                }`}
              >
                <CheckCircle2 className="h-3.5 w-3.5" />
                {analysis.visualValidation.detection_supported
                  ? "Detection Supported by Visual Evidence"
                  : "Visual Evidence Contradicts Detection"}
              </span>
            )}
          </div>

          {analysis.visualValidation?.confidence_note && (
            <p className="mt-3 text-[14px] leading-relaxed text-muted-foreground">
              <strong className="text-foreground">Validation Assessment: </strong>
              {String(analysis.visualValidation.confidence_note)}
            </p>
          )}

          {analysis.visualValidation?.scene_context && (
            <p className="mt-2 text-[14px] leading-relaxed text-muted-foreground">
              <strong className="text-foreground">Scene Context: </strong>
              {String(analysis.visualValidation.scene_context)}
            </p>
          )}

          {analysis.visualObservations && analysis.visualObservations.length > 0 && (
            <div className="mt-3.5 border-t border-border/60 pt-3">
              <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                Observed Visual Indicators
              </h4>
              <ul className="mt-2 list-disc space-y-1.5 pl-5 text-[14px] leading-relaxed text-foreground marker:text-primary">
                {analysis.visualObservations.map((obs, i) => (
                  <li key={i}>{obs}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Risk Assessment & Contributing Factors */}
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-border p-5">
          <div className="flex flex-wrap items-center gap-3">
            <SectionHeading>Risk Assessment</SectionHeading>
            <RiskChip risk={insight.risk} />
          </div>
          <p className="mt-3.5 text-[15px] leading-[1.75] text-foreground">
            {analysis.riskAssessment}
          </p>
        </div>
        <div className="rounded-xl border border-border p-5">
          <SectionHeading>Contributing Factors</SectionHeading>
          {analysis.contributingFactors.length > 0 ? (
            <ul className="mt-3.5 list-disc space-y-2 pl-5 text-[15px] leading-[1.6] text-foreground marker:text-muted-foreground">
              {analysis.contributingFactors.map((f) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-3.5 text-[14px] text-muted-foreground">
              No contributing factors identified.
            </p>
          )}
        </div>
      </div>

      {/* Uncertainties & Epistemic Boundaries */}
      {analysis.uncertainties && analysis.uncertainties.length > 0 && (
        <div className="rounded-xl border border-border bg-surface/40 p-5">
          <div className="flex items-center gap-2">
            <HelpCircle className="h-5 w-5 text-muted-foreground" />
            <SectionHeading>Uncertainties & Epistemic Boundaries</SectionHeading>
          </div>
          <ul className="mt-3 list-disc space-y-1.5 pl-5 text-[14px] leading-relaxed text-muted-foreground marker:text-muted-foreground">
            {analysis.uncertainties.map((u, i) => (
              <li key={i}>{u}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function ActionCard({
  act,
  index,
  categoryBadge,
}: {
  act: RecommendationAction;
  index: number;
  categoryBadge?: { label: string; className: string };
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4.5 transition-all hover:border-primary/40 hover:shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
            {index + 1}
          </span>
          <h4 className="text-[15px] font-bold text-foreground">{act.title}</h4>
        </div>
        {categoryBadge && (
          <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${categoryBadge.className}`}>
            {categoryBadge.label}
          </span>
        )}
      </div>

      <p className="mt-2.5 pl-8.5 text-[14px] leading-relaxed text-foreground/90">
        {act.procedure || act.description}
      </p>

      {act.rationale && (
        <div className="mt-3 ml-8.5 rounded-lg border border-primary/15 bg-primary/5 p-3 text-xs leading-relaxed text-muted-foreground">
          <strong className="font-semibold text-foreground">Operational Rationale: </strong>
          {act.rationale}
        </div>
      )}

      {(act.owner !== "—" || act.targetDate !== "—" || act.expectedOutcome !== "—") && (
        <div className="mt-3.5 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-border/60 pl-8.5 pt-3 text-xs text-muted-foreground">
          {act.owner !== "—" && (
            <span className="inline-flex items-center gap-1.5">
              <UserCheck className="h-3.5 w-3.5 text-primary" />
              <strong className="font-semibold text-foreground">Role:</strong> {act.owner}
            </span>
          )}
          {act.targetDate !== "—" && (
            <span className="inline-flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5 text-primary" />
              <strong className="font-semibold text-foreground">Timeline:</strong> {act.targetDate}
            </span>
          )}
          {act.expectedOutcome !== "—" && (
            <span className="inline-flex items-center gap-1.5">
              <CheckCircle2 className="h-3.5 w-3.5 text-safe" />
              <strong className="font-semibold text-foreground">Target Outcome:</strong>{" "}
              {act.expectedOutcome}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function RecommendationTab({ insight }: { insight: InsightDetailViewModel }) {
  const { immediateActions, investigationActions, preventiveActions, actions, preventiveGuidance } = insight.recommendations;
  const hasCategorized =
    (immediateActions && immediateActions.length > 0) ||
    (investigationActions && investigationActions.length > 0) ||
    (preventiveActions && preventiveActions.length > 0);

  const totalActions = hasCategorized
    ? (immediateActions?.length || 0) + (investigationActions?.length || 0) + (preventiveActions?.length || 0)
    : actions.length;

  if (totalActions === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
        <Lightbulb className="h-10 w-10 text-muted-foreground/40" />
        <p className="text-[15px] text-muted-foreground">
          No AI recommendations are available for this insight.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-7">
      {hasCategorized ? (
        <>
          {/* 1. Immediate Containment Actions */}
          {immediateActions && immediateActions.length > 0 && (
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <SectionHeading>Immediate Containment Actions</SectionHeading>
                  <span className="rounded-full bg-risk-high-soft px-2.5 py-0.5 text-[11px] font-semibold text-risk-high">
                    Life Safety & Isolation
                  </span>
                </div>
                <span className="text-xs text-muted-foreground">
                  {immediateActions.length} Action{immediateActions.length !== 1 ? "s" : ""}
                </span>
              </div>
              <div className="mt-3.5 space-y-3.5">
                {immediateActions.map((act, index) => (
                  <ActionCard
                    key={act.id}
                    act={act}
                    index={index}
                    categoryBadge={{ label: "Immediate", className: "bg-risk-high-soft text-risk-high" }}
                  />
                ))}
              </div>
            </div>
          )}

          {/* 2. Investigation & Site Actions */}
          {investigationActions && investigationActions.length > 0 && (
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <SectionHeading>Root Cause & Site Investigation</SectionHeading>
                  <span className="rounded-full bg-primary-soft px-2.5 py-0.5 text-[11px] font-semibold text-primary">
                    Evidence Preservation
                  </span>
                </div>
                <span className="text-xs text-muted-foreground">
                  {investigationActions.length} Action{investigationActions.length !== 1 ? "s" : ""}
                </span>
              </div>
              <div className="mt-3.5 space-y-3.5">
                {investigationActions.map((act, index) => (
                  <ActionCard
                    key={act.id}
                    act={act}
                    index={index}
                    categoryBadge={{ label: "Investigation", className: "bg-primary-soft text-primary" }}
                  />
                ))}
              </div>
            </div>
          )}

          {/* 3. Systemic Preventive Controls */}
          {preventiveActions && preventiveActions.length > 0 && (
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <SectionHeading>Systemic Preventive Controls</SectionHeading>
                  <span className="rounded-full bg-risk-low-soft px-2.5 py-0.5 text-[11px] font-semibold text-risk-low">
                    Recurrence Prevention
                  </span>
                </div>
                <span className="text-xs text-muted-foreground">
                  {preventiveActions.length} Action{preventiveActions.length !== 1 ? "s" : ""}
                </span>
              </div>
              <div className="mt-3.5 space-y-3.5">
                {preventiveActions.map((act, index) => (
                  <ActionCard
                    key={act.id}
                    act={act}
                    index={index}
                    categoryBadge={{ label: "Preventive", className: "bg-risk-low-soft text-risk-low" }}
                  />
                ))}
              </div>
            </div>
          )}
        </>
      ) : (
        /* Legacy flat actions fallback */
        <div>
          <div className="flex items-center justify-between">
            <SectionHeading>Recommended Actions</SectionHeading>
            <span className="text-xs text-muted-foreground">
              {actions.length} Recommended Action{actions.length !== 1 ? "s" : ""}
            </span>
          </div>
          <div className="mt-4 space-y-3.5">
            {actions.map((act, index) => (
              <ActionCard key={act.id} act={act} index={index} />
            ))}
          </div>
        </div>
      )}

      {/* Preventive Guidance Checklist */}
      {preventiveGuidance.length > 0 && (
        <div className="rounded-xl border border-border bg-card p-5">
          <SectionHeading>Preventive Guidance & Best Practices</SectionHeading>
          <ul className="mt-3.5 space-y-2.5">
            {preventiveGuidance.map((guide, i) => (
              <li key={i} className="flex items-start gap-2.5 text-[14px] leading-relaxed text-foreground">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-safe" />
                <span>{guide}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <InfoNote>
        These recommendations are synthesized in real-time by SafeVision AI based on event telemetry,
        observed risk patterns, and active site safety standards.
      </InfoNote>
    </div>
  );
}

function SafetyTab({ insight }: { insight: InsightDetailViewModel }) {
  const policyText = insight.safetyInformation.policyText;
  const isEmpty = !policyText;

  return (
    <div>
      <div className="flex items-start gap-4">
        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-risk-low-soft">
          <BookOpen className="h-6 w-6 text-risk-low" strokeWidth={1.8} />
        </span>
        <div>
          <SectionHeading>Relevant Safety Information</SectionHeading>
          <p className="mt-1.5 max-w-2xl text-[15px] leading-[1.7] text-muted-foreground">
            The following safety policy/procedure has been retrieved from the Safety Knowledge Base
            and is relevant to this event.
          </p>
        </div>
      </div>

      {isEmpty ? (
        <div className="mt-5 flex flex-col items-center justify-center gap-3 rounded-xl border border-border py-12 text-center">
          <FileText className="h-10 w-10 text-muted-foreground/40" />
          <p className="text-[14px] text-muted-foreground">
            No safety policy information is available for this insight.
          </p>
        </div>
      ) : (
        <div className="mt-5 rounded-xl border border-border p-6">
          <div className="flex items-start gap-4">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-risk-low-soft">
              <FileText className="h-5 w-5 text-risk-low" strokeWidth={1.8} />
            </span>
            <div>
              <h4 className="text-[17px] font-bold text-foreground">Safety Policy Guidance</h4>
              <p className="mt-0.5 text-[14px] text-muted-foreground">Source: Safety Knowledge Base (RAG)</p>
            </div>
          </div>

          <p className="mt-5 max-w-3xl text-[15px] leading-[1.75] text-foreground whitespace-pre-wrap">
            {policyText}
          </p>
        </div>
      )}

      <InfoNote>
        This information is retrieved from the company&apos;s Safety Knowledge Base and is relevant
        to the detected safety event.
      </InfoNote>
    </div>
  );
}

function HistoryTab({ insight }: { insight: InsightDetailViewModel }) {
  const context = insight.historicalContext;
  const isEmpty = !context;

  return (
    <div>
      <SectionHeading>Historical Context</SectionHeading>
      <p className="mt-2 text-[15px] text-muted-foreground">
        Summary of similar past events to provide context on event frequency, patterns, and
        outcomes.
      </p>

      {isEmpty ? (
        <div className="mt-5 flex flex-col items-center justify-center gap-3 rounded-xl border border-border py-12 text-center">
          <History className="h-10 w-10 text-muted-foreground/40" />
          <p className="text-[14px] text-muted-foreground">
            No historical context is available for this insight.
          </p>
        </div>
      ) : (
        <div className="mt-5 rounded-xl border border-border p-6">
          <p className="max-w-3xl text-[15px] leading-[1.75] text-foreground whitespace-pre-wrap">
            {context}
          </p>
        </div>
      )}

      <InfoNote>
        This historical data is used by AI to understand recurring patterns and improve the accuracy
        of recommendations.
      </InfoNote>
    </div>
  );
}

function EvidenceTab({ insight }: { insight: InsightDetailViewModel }) {
  const eventId = insight.eventId;
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Listen for fullscreen changes
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

  // Fetch evidence image when eventId changes
  useEffect(() => {
    let active = true;
    let currentObjectUrl: string | null = null;

    if (eventId) {
      setIsLoading(true);
      setHasError(false);
      setImageUrl(null);

      fetchEventEvidenceBlobUrl(eventId)
        .then((url) => {
          if (!active) {
            if (url) URL.revokeObjectURL(url);
            return;
          }
          if (url) {
            currentObjectUrl = url;
            setImageUrl(url);
          } else {
            setHasError(true);
          }
        })
        .catch(() => {
          if (active) setHasError(true);
        })
        .finally(() => {
          if (active) setIsLoading(false);
        });
    } else {
      setImageUrl(null);
      setIsLoading(false);
      setHasError(false);
    }

    return () => {
      active = false;
      if (currentObjectUrl) {
        URL.revokeObjectURL(currentObjectUrl);
      }
    };
  }, [eventId]);

  const eventTypeLabel = insight.eventType
    ? insight.eventType.replace(/_/g, " ").toUpperCase()
    : null;

  return (
    <div>
      <div className="flex items-start gap-4">
        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-primary/10">
          <Camera className="h-6 w-6 text-primary" strokeWidth={1.8} />
        </span>
        <div>
          <SectionHeading>Event Evidence</SectionHeading>
          <p className="mt-1.5 max-w-2xl text-[15px] leading-[1.7] text-muted-foreground">
            Authoritative frame evidence captured for this safety event.
          </p>
        </div>
      </div>

      {/* Evidence image */}
      <div className="mt-5">
        <div
          ref={containerRef}
          className={
            isFullscreen
              ? "flex h-full w-full items-center justify-center bg-black relative"
              : "relative aspect-video w-full max-w-3xl overflow-hidden rounded-xl border border-border bg-black/90 shadow-sm flex items-center justify-center"
          }
        >
          {/* Fullscreen toggle */}
          {imageUrl && (
            <button
              type="button"
              onClick={toggleFullscreen}
              aria-label={isFullscreen ? "Exit fullscreen" : "Maximize evidence"}
              className="absolute right-2.5 top-2.5 z-10 rounded-md bg-[oklch(0.15_0_0/0.75)] p-1.5 text-[oklch(0.98_0_0)] backdrop-blur-md transition-colors hover:opacity-80"
            >
              {isFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
            </button>
          )}

          {/* Loading */}
          {isLoading && (
            <div className="flex flex-col items-center justify-center gap-2 text-muted-foreground">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
              <span className="text-xs">Loading event evidence…</span>
            </div>
          )}

          {/* Image */}
          {!isLoading && imageUrl && (
            <img
              src={imageUrl}
              alt={`Evidence frame for event ${eventId}`}
              className={
                isFullscreen
                  ? "max-h-full max-w-full object-contain"
                  : "h-full w-full object-contain"
              }
            />
          )}

          {/* Empty / Error */}
          {!isLoading && !imageUrl && (
            <div className="flex flex-col items-center justify-center gap-2 p-6 text-center text-muted-foreground">
              <ImageOff className="h-10 w-10 text-muted-foreground/60" />
              <p className="text-sm font-semibold text-foreground">No evidence image available for this event.</p>
              <p className="max-w-sm text-xs text-muted-foreground">
                {hasError
                  ? "The evidence image could not be loaded."
                  : "Historical event or visual evidence was not persisted for this event record."}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Event metadata (only what is already in the insight view model) */}
      {(eventTypeLabel || insight.riskLevelRaw) && (
        <div className="mt-5 max-w-3xl">
          <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
            Event Metadata
          </span>
          <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-3">
            {eventTypeLabel && (
              <div className="rounded-lg border border-border bg-card p-3">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Camera className="h-3.5 w-3.5" />
                  <span>Event Type</span>
                </div>
                <p className="mt-1 text-sm font-semibold text-foreground truncate">{eventTypeLabel}</p>
              </div>
            )}
            {insight.riskLevelRaw && (
              <div className="rounded-lg border border-border bg-card p-3">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <AlertTriangle className="h-3.5 w-3.5" />
                  <span>Risk Level</span>
                </div>
                <p className="mt-1 text-sm font-semibold text-foreground truncate">
                  {insight.riskLevelRaw.charAt(0).toUpperCase() + insight.riskLevelRaw.slice(1)}
                </p>
              </div>
            )}
            <div className="rounded-lg border border-border bg-card p-3">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Clock className="h-3.5 w-3.5" />
                <span>Generated</span>
              </div>
              <p className="mt-1 text-sm font-semibold text-foreground truncate">{insight.generatedAt}</p>
            </div>
          </div>
        </div>
      )}

      <InfoNote>
        This is the authoritative visual evidence frame associated with the safety event that
        triggered this AI Insight. It is the same frame used during multimodal AI analysis.
      </InfoNote>
    </div>
  );
}

function InfoNote({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-6 flex items-start gap-3 rounded-xl bg-primary-soft px-5 py-4">
      <Info className="mt-0.5 h-5 w-5 shrink-0 text-primary" strokeWidth={1.8} />
      <p className="max-w-3xl text-[15px] leading-[1.7] text-foreground">{children}</p>
    </div>
  );
}
