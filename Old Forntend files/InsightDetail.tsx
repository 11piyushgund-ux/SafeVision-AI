import {
  BookOpen,
  CheckCircle2,
  Clock,
  FileText,
  History,
  Info,
  Lightbulb,
  ShieldCheck,
  Sparkles,
  UserCheck,
} from "lucide-react";
import type { SafetyInsight } from "@/data/safety-insights";
import { InsightIcon } from "./InsightIcon";
import { RiskChip } from "./RiskBadge";

export type DetailTab = "analysis" | "recommendation" | "safety" | "history";

const tabs: { id: DetailTab; label: string; Icon: typeof Sparkles }[] = [
  { id: "analysis", label: "AI Analysis", Icon: Sparkles },
  { id: "recommendation", label: "AI Recommendation", Icon: Lightbulb },
  { id: "safety", label: "Safety Information", Icon: FileText },
  { id: "history", label: "Historical Context", Icon: History },
];

export function InsightDetail({
  insight,
  tab,
  onTabChange,
}: {
  insight: SafetyInsight;
  tab: DetailTab;
  onTabChange: (t: DetailTab) => void;
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
        <span className="inline-flex items-center gap-2 rounded-full bg-primary-soft px-3.5 py-1.5 text-[13px] font-medium text-primary">
          <span className="h-2 w-2 rounded-full bg-primary" />
          Active Insight
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

function AnalysisTab({ insight }: { insight: SafetyInsight }) {
  return (
    <div>
      <SectionHeading>Event Summary</SectionHeading>
      <p className="mt-3 max-w-3xl text-[15px] leading-[1.75] text-foreground">
        {insight.analysis.eventSummary}
      </p>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-border p-5">
          <div className="flex flex-wrap items-center gap-3">
            <SectionHeading>Risk Assessment</SectionHeading>
            <RiskChip risk={insight.risk} />
          </div>
          <p className="mt-3.5 text-[15px] leading-[1.75] text-foreground">
            {insight.analysis.riskAssessment}
          </p>
        </div>
        <div className="rounded-xl border border-border p-5">
          <SectionHeading>Contributing Factors</SectionHeading>
          <ul className="mt-3.5 list-disc space-y-2 pl-5 text-[15px] leading-[1.6] text-foreground marker:text-muted-foreground">
            {insight.analysis.contributingFactors.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

function RecommendationTab({ insight }: { insight: SafetyInsight }) {
  const rec = insight.recommendations;
  return (
    <div className="space-y-6">
      {/* Strategic Objective & Standard Banner */}
      <div className="rounded-xl border border-border bg-primary-soft/50 p-5">
        <div className="flex items-start gap-3.5">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <Lightbulb className="h-5 w-5" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <SectionHeading>Strategic AI Recommendation</SectionHeading>
              <span className="inline-flex items-center gap-1.5 rounded-md border border-primary/20 bg-card px-2.5 py-1 text-xs font-semibold text-primary">
                <ShieldCheck className="h-3.5 w-3.5" />
                {rec.complianceStandard}
              </span>
            </div>
            <p className="mt-2 text-[15px] font-semibold text-foreground">
              {rec.strategicObjective}
            </p>
            <p className="mt-1.5 text-[14px] leading-relaxed text-muted-foreground">
              {rec.executiveSummary}
            </p>
          </div>
        </div>
      </div>

      {/* Action Plan */}
      <div>
        <div className="flex items-center justify-between">
          <SectionHeading>Prioritized Action Plan</SectionHeading>
          <span className="text-xs text-muted-foreground">
            {rec.actions.length} Recommended Actions
          </span>
        </div>

        <div className="mt-4 space-y-3.5">
          {rec.actions.map((act, index) => {
            const priorityBadge =
              act.priority === "Immediate"
                ? "bg-danger-soft text-danger border-danger/20"
                : act.priority === "Short-term"
                  ? "bg-warn-soft text-warn border-warn/20"
                  : "bg-brand-soft text-brand border-brand/20";

            return (
              <div
                key={act.id}
                className="rounded-xl border border-border bg-card p-4 transition-all hover:border-primary/40 hover:shadow-sm"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="flex items-center gap-2.5">
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                      {index + 1}
                    </span>
                    <h4 className="text-[15px] font-bold text-foreground">{act.title}</h4>
                  </div>
                  <span
                    className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${priorityBadge}`}
                  >
                    {act.priority}
                  </span>
                </div>

                <p className="mt-2 pl-8.5 text-[14px] leading-relaxed text-muted-foreground">
                  {act.description}
                </p>

                <div className="mt-3.5 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-border/60 pl-8.5 pt-3 text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1.5">
                    <UserCheck className="h-3.5 w-3.5 text-primary" />
                    <strong className="font-semibold text-foreground">Owner:</strong> {act.owner}
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <Clock className="h-3.5 w-3.5 text-primary" />
                    <strong className="font-semibold text-foreground">Timeline:</strong> {act.targetDate}
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-safe" />
                    <strong className="font-semibold text-foreground">Target Outcome:</strong>{" "}
                    {act.expectedOutcome}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Preventive Guidance Checklist */}
      {rec.preventiveGuidance?.length > 0 && (
        <div className="rounded-xl border border-border p-5">
          <SectionHeading>Preventive Guidance & Best Practices</SectionHeading>
          <ul className="mt-3.5 space-y-2.5">
            {rec.preventiveGuidance.map((guide, i) => (
              <li key={i} className="flex items-start gap-2.5 text-[14px] leading-relaxed text-foreground">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
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

function SafetyTab({ insight }: { insight: SafetyInsight }) {
  const info = insight.safetyInformation;
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

      <div className="mt-5 rounded-xl border border-border p-6">
        <div className="flex items-start gap-4">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-risk-low-soft">
            <FileText className="h-5 w-5 text-risk-low" strokeWidth={1.8} />
          </span>
          <div>
            <h4 className="text-[17px] font-bold text-foreground">{info.policyTitle}</h4>
            <p className="mt-0.5 text-[14px] text-muted-foreground">Source: {info.source}</p>
          </div>
        </div>

        <p className="mt-5 max-w-3xl text-[15px] leading-[1.75] text-foreground">
          {info.policyText}
        </p>

        <div className="mt-5 border-t border-border pt-5">
          <h5 className="text-[15px] font-semibold text-risk-low">Key Requirements</h5>
          <ul className="mt-3.5 space-y-3">
            {info.keyRequirements.map((req) => (
              <li key={req} className="flex items-start gap-3 text-[15px] leading-[1.6] text-foreground">
                <CheckCircle2 className="mt-0.5 h-[18px] w-[18px] shrink-0 text-risk-low" />
                {req}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <InfoNote>
        This information is retrieved from the company&apos;s Safety Knowledge Base and is relevant
        to the detected safety event.
      </InfoNote>
    </div>
  );
}

function HistoryTab({ insight }: { insight: SafetyInsight }) {
  return (
    <div>
      <SectionHeading>Historical Context</SectionHeading>
      <p className="mt-2 text-[15px] text-muted-foreground">
        Summary of similar past events to provide context on event frequency, patterns, and
        outcomes.
      </p>

      <div className="mt-5 overflow-hidden rounded-xl border border-border">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] border-collapse text-left">
            <thead>
              <tr className="bg-muted">
                {["Date & Time", "Event Description", "Location / Area", "Risk Level", "Outcome"].map(
                  (h) => (
                    <th
                      key={h}
                      className="px-5 py-3.5 text-[14px] font-semibold text-foreground"
                    >
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {insight.historicalContext.map((row) => (
                <tr key={`${row.date}-${row.time}`} className="border-t border-border align-top">
                  <td className="px-5 py-4 text-[14px] leading-[1.6] text-foreground">
                    {row.date}
                    <br />
                    {row.time}
                  </td>
                  <td className="max-w-[240px] px-5 py-4 text-[14px] leading-[1.6] text-foreground">
                    {row.description}
                  </td>
                  <td className="px-5 py-4 text-[14px] text-foreground">{row.location}</td>
                  <td className="px-5 py-4">
                    <RiskChip risk={row.risk} label={row.risk} />
                  </td>
                  <td className="px-5 py-4 text-[14px] text-foreground">{row.outcome}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <InfoNote>
        This historical data is used by AI to understand recurring patterns and improve the accuracy
        of recommendations.
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
