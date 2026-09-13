import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Download, Sparkles } from "lucide-react";
import { AppHeader } from "@/components/AppHeader";
import { InsightsList } from "@/components/safevision/InsightsList";
import { InsightDetail, type DetailTab } from "@/components/safevision/InsightDetail";
import { safetyInsights } from "@/data/safety-insights";

export const Route = createFileRoute("/ai-safety-insights")({
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

function AISafetyInsightsPage() {
  const [selectedId, setSelectedId] = useState(safetyInsights[0]!.id);
  const [tab, setTab] = useState<DetailTab>("analysis");
  const [dateRange, setDateRange] = useState("May 18, 2025 - May 24, 2025");
  const [sortBy, setSortBy] = useState("Newest First");
  const [page, setPage] = useState(1);

  const selected = safetyInsights.find((i) => i.id === selectedId) ?? safetyInsights[0]!;

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
            className="inline-flex items-center gap-2.5 rounded-lg border border-primary bg-card px-5 py-3 text-[15px] font-semibold text-primary transition-colors hover:bg-primary-soft"
          >
            <Download className="h-[18px] w-[18px]" strokeWidth={2} />
            Export Report
          </button>
        </div>

        <div className="mt-6 grid items-start gap-6 lg:grid-cols-[minmax(0,0.62fr)_minmax(0,1fr)]">
          <InsightsList
            insights={safetyInsights}
            selectedId={selectedId}
            onSelect={(id) => {
              setSelectedId(id);
              setTab("analysis");
            }}
            dateRange={dateRange}
            onDateRangeChange={setDateRange}
            sortBy={sortBy}
            onSortByChange={setSortBy}
            page={page}
            onPageChange={setPage}
          />
          <InsightDetail insight={selected} tab={tab} onTabChange={setTab} />
        </div>

        <footer className="mt-8 border-t border-border pt-5 text-center text-[13px] text-muted-foreground">
          © 2025 SafeVision AI. All rights reserved.
        </footer>
      </main>
    </div>
  );
}
