import { CalendarDays, ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import type { SafetyInsight } from "@/data/safety-insights";
import { totalInsights, totalPages } from "@/data/safety-insights";
import { InsightIcon } from "./InsightIcon";
import { RiskDotLabel } from "./RiskBadge";

type Props = {
  insights: SafetyInsight[];
  selectedId: string;
  onSelect: (id: string) => void;
  dateRange: string;
  onDateRangeChange: (v: string) => void;
  sortBy: string;
  onSortByChange: (v: string) => void;
  page: number;
  onPageChange: (p: number) => void;
};

const selectClass =
  "appearance-none rounded-lg border border-border bg-card py-2.5 pl-4 pr-9 text-[14px] font-medium text-foreground outline-none focus:border-primary";

export function InsightsList({
  insights,
  selectedId,
  onSelect,
  dateRange,
  onDateRangeChange,
  sortBy,
  onSortByChange,
  page,
  onPageChange,
}: Props) {
  return (
    <section className="flex flex-col overflow-hidden rounded-xl border border-border bg-card shadow-card">
      <div className="px-5 pb-4 pt-5">
        <h2 className="text-[15px] font-bold uppercase tracking-[0.04em] text-foreground">
          AI Insights
        </h2>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[220px]">
            <CalendarDays className="pointer-events-none absolute left-3.5 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-primary" />
            <select
              aria-label="Date range"
              value={dateRange}
              onChange={(e) => onDateRangeChange(e.target.value)}
              className={`${selectClass} w-full pl-10`}
            >
              <option>May 18, 2025 - May 24, 2025</option>
              <option>May 11, 2025 - May 17, 2025</option>
              <option>May 1, 2025 - May 24, 2025</option>
            </select>
            <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[14px] text-muted-foreground">Sort by:</span>
            <div className="relative">
              <select
                aria-label="Sort by"
                value={sortBy}
                onChange={(e) => onSortByChange(e.target.value)}
                className={selectClass}
              >
                <option>Newest First</option>
                <option>Oldest First</option>
                <option>Highest Risk</option>
              </select>
              <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            </div>
          </div>
        </div>
      </div>

      <ul className="border-t border-border">
        {insights.map((insight) => {
          const active = insight.id === selectedId;
          return (
            <li key={insight.id} className="border-b border-border last:border-b-0">
              <button
                type="button"
                onClick={() => onSelect(insight.id)}
                className={`flex w-full items-start gap-3.5 px-5 py-4 text-left transition-colors ${
                  active
                    ? "border-l-[3px] border-l-primary bg-primary-soft"
                    : "border-l-[3px] border-l-transparent hover:bg-muted"
                }`}
              >
                <InsightIcon icon={insight.icon} />
                <span className="min-w-0 flex-1">
                  <span className="flex items-start justify-between gap-3">
                    <span className="text-[15px] font-semibold text-foreground">
                      {insight.title}
                    </span>
                    <span className="whitespace-nowrap pt-0.5 text-[13px] text-muted-foreground">
                      {insight.date}, {insight.time}
                    </span>
                  </span>
                  <span className="mt-1.5 block">
                    <RiskDotLabel risk={insight.risk} />
                  </span>
                  <span className="mt-1.5 block max-w-[92%] text-[14px] leading-relaxed text-muted-foreground">
                    {insight.summary}
                  </span>
                </span>
                <ChevronRight className="mt-6 h-5 w-5 shrink-0 text-muted-foreground" />
              </button>
            </li>
          );
        })}
      </ul>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-4">
        <span className="text-[14px] text-muted-foreground">
          Showing 1 to {insights.length} of {totalInsights} insights
        </span>
        <nav className="flex items-center gap-2" aria-label="Insight pagination">
          <PagerButton
            onClick={() => onPageChange(Math.max(1, page - 1))}
            disabled={page === 1}
            label="Previous page"
          >
            <ChevronLeft className="h-4 w-4" />
          </PagerButton>
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => onPageChange(p)}
              aria-current={p === page ? "page" : undefined}
              className={`h-9 w-9 rounded-lg border text-[14px] font-medium transition-colors ${
                p === page
                  ? "border-primary bg-primary-soft text-primary"
                  : "border-border text-muted-foreground hover:bg-muted"
              }`}
            >
              {p}
            </button>
          ))}
          <PagerButton
            onClick={() => onPageChange(Math.min(totalPages, page + 1))}
            disabled={page === totalPages}
            label="Next page"
          >
            <ChevronRight className="h-4 w-4" />
          </PagerButton>
        </nav>
      </div>
    </section>
  );
}

function PagerButton({
  children,
  onClick,
  disabled,
  label,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  label: string;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
      className="flex h-9 w-9 items-center justify-center rounded-lg border border-border text-muted-foreground transition-colors hover:bg-muted disabled:opacity-40"
    >
      {children}
    </button>
  );
}
