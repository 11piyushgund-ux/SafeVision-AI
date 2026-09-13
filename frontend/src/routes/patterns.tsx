import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  ClipboardList,
  Download,
  Lightbulb,
  LineChart,
  ListFilter,
  Loader2,
  ShieldAlert,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import { AppHeader } from "@/components/AppHeader";
import { AuthGuard } from "@/components/auth-guard";
import { fetchPatterns } from "@/lib/api-client";
import type { PatternResponse } from "@/lib/api-types";

export const Route = createFileRoute("/patterns")({
  head: () => ({
    meta: [
      { title: "Recurring Patterns | SafeVision AI" },
      {
        name: "description",
        content:
          "Identify repeated safety events and recurring risks across zones, review trends and take preventive action.",
      },
      { property: "og:title", content: "Recurring Patterns | SafeVision AI" },
      {
        property: "og:description",
        content: "Repeated safety events, trend analysis and preventive recommendations.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: RecurringPatternsPage,
});

const PATTERN_TYPE_LABELS: Record<string, string> = {
  temporal: "Temporal Pattern",
  spatial: "Spatial Pattern",
  trend: "Trend Pattern",
  rule_based: "Rule-based Pattern",
  worker: "Worker Pattern",
};

const STATUS_TONE: Record<string, string> = {
  active: "bg-danger-soft text-danger",
  dismissed: "bg-muted text-muted-foreground",
  resolved: "bg-safe-soft text-safe",
};

function RecurringPatternsPage() {
  const [typeFilter, setTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("active");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["patterns", typeFilter, statusFilter],
    queryFn: () => {
      const params: { page: number; size: number; pattern_type?: string; status?: string } = {
        page: 1,
        size: 50,
      };
      if (typeFilter !== "all") params.pattern_type = typeFilter;
      if (statusFilter !== "all") params.status = statusFilter;
      return fetchPatterns(params);
    },
  });

  const patterns = data?.data ?? [];
  const selected = patterns.find((p) => p.id === selectedId) ?? patterns[0] ?? null;
  const trendData =
    selected?.daily_trend ??
    (selected?.pattern_data as { daily_trend?: { date: string; occurrences: number }[] } | null)?.daily_trend ??
    [];

  const handleExportReport = () => {
    if (patterns.length === 0) return;
    const headers = [
      "Pattern Title",
      "Type",
      "Zone",
      "Occurrences",
      "Confidence",
      "Status",
      "First Detected",
      "Last Detected",
    ];
    const rows = patterns.map((p) => [
      `"${(p.title || "").replace(/"/g, '""')}"`,
      `"${p.pattern_type}"`,
      `"${p.zone_name ?? "General Facility"}"`,
      p.occurrence_count,
      p.confidence_score != null ? `${Math.round(p.confidence_score * 100)}%` : "N/A",
      `"${p.status}"`,
      `"${p.first_detected_at}"`,
      `"${p.last_detected_at}"`,
    ]);
    const csvContent = [headers.join(","), ...rows.map((r) => r.join(","))].join("\r\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute(
      "download",
      `safevision-patterns-report-${new Date().toISOString().split("T")[0]}.csv`,
    );
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <AuthGuard>
      <div className="flex min-h-screen flex-col bg-background text-foreground">
        <AppHeader />

        <main className="mx-auto w-full max-w-[1560px] flex-1 px-6 py-6">
          <div className="flex min-w-0 items-center gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-soft text-brand">
              <TrendingUp className="h-5 w-5" />
            </span>
            <h1 className="truncate text-2xl font-bold tracking-tight">Recurring Patterns</h1>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Identify repeated safety events and recurring risks across zones to take preventive action.
          </p>

          {/* Filter bar */}
          <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-[repeat(2,minmax(0,1fr))_auto]">
            <label className="flex min-w-0 items-center gap-3 rounded-xl border border-border bg-card px-4 py-2.5">
              <ListFilter className="h-5 w-5 shrink-0 text-muted-foreground" />
              <span className="min-w-0 flex-1">
                <span className="block text-[11px] text-muted-foreground">Pattern Type</span>
                <select
                  value={typeFilter}
                  onChange={(e) => {
                    setTypeFilter(e.target.value);
                    setSelectedId(null);
                  }}
                  className="w-full bg-transparent text-sm font-medium outline-none"
                >
                  <option value="all">All Types</option>
                  <option value="trend">Trend (Hazard Clusters)</option>
                  <option value="temporal">Temporal (Time/Shift)</option>
                  <option value="spatial">Spatial (Zone Incursions)</option>
                  <option value="rule_based">Rule-based</option>
                  <option value="worker">Worker</option>
                </select>
              </span>
            </label>

            <label className="flex min-w-0 items-center gap-3 rounded-xl border border-border bg-card px-4 py-2.5">
              <ShieldAlert className="h-5 w-5 shrink-0 text-muted-foreground" />
              <span className="min-w-0 flex-1">
                <span className="block text-[11px] text-muted-foreground">Pattern Status</span>
                <select
                  value={statusFilter}
                  onChange={(e) => {
                    setStatusFilter(e.target.value);
                    setSelectedId(null);
                  }}
                  className="w-full bg-transparent text-sm font-medium outline-none"
                >
                  <option value="active">Active Patterns</option>
                  <option value="all">All Statuses</option>
                  <option value="dismissed">Dismissed</option>
                  <option value="resolved">Resolved</option>
                </select>
              </span>
            </label>

            <button
              onClick={handleExportReport}
              disabled={patterns.length === 0}
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-brand px-5 py-2.5 text-sm font-semibold text-brand transition-colors hover:bg-brand-soft disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Download className="h-4 w-4" />
              Export Report
            </button>
          </div>

          {/* Main content */}
          {isLoading ? (
            <div className="mt-10 flex items-center justify-center gap-3 py-16">
              <Loader2 className="h-5 w-5 animate-spin text-primary" />
              <span className="text-[14px] text-muted-foreground">Loading patterns...</span>
            </div>
          ) : isError ? (
            <div className="mt-10 rounded-xl border border-border bg-card px-6 py-16 text-center text-[14px] text-danger">
              Failed to load patterns. Please try again.
            </div>
          ) : (
            <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.6fr)]">
              {/* Patterns list */}
              <section className="flex flex-col rounded-xl border border-border bg-card">
                <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
                  <p className="text-xs font-bold tracking-[0.12em] text-muted-foreground">
                    PATTERNS LIST ({patterns.length})
                  </p>
                </div>

                {patterns.length === 0 ? (
                  <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 py-20 text-center">
                    <span className="flex h-24 w-24 items-center justify-center rounded-full bg-muted text-muted-foreground">
                      <ClipboardList className="h-10 w-10" />
                    </span>
                    <div>
                      <p className="text-lg font-bold">No recurring patterns found</p>
                      <p className="mt-2 text-sm text-muted-foreground">
                        No recurring safety patterns detected for the selected filters.
                      </p>
                    </div>
                  </div>
                ) : (
                  <ul className="flex-1">
                    {patterns.map((pattern: PatternResponse) => {
                      const isSelected = selected?.id === pattern.id;
                      return (
                        <li key={pattern.id}>
                          <button
                            onClick={() => setSelectedId(pattern.id)}
                            className={`flex w-full items-start gap-3 border-b border-border px-5 py-4 text-left transition-colors hover:bg-accent ${
                              isSelected ? "bg-accent border-l-4 border-l-brand" : ""
                            }`}
                          >
                            <span
                              className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${STATUS_TONE[pattern.status] ?? "bg-brand-soft text-brand"}`}
                            >
                              <TrendingUp className="h-5 w-5" />
                            </span>
                            <span className="min-w-0 flex-1">
                              <span className="block truncate text-sm font-semibold">
                                {pattern.title}
                              </span>
                              <span className="block truncate text-xs text-muted-foreground">
                                {pattern.zone_name ?? "General Facility"} · {pattern.occurrence_count} occurrences
                              </span>
                            </span>
                            <span className="shrink-0 text-xs font-semibold text-muted-foreground">
                              {PATTERN_TYPE_LABELS[pattern.pattern_type] ?? pattern.pattern_type}
                            </span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </section>

              {/* Pattern details */}
              <section className="flex flex-col gap-5">
                <div className="rounded-xl border border-border bg-card">
                  <div className="flex items-center gap-2 border-b border-border px-5 py-4">
                    <ShieldCheck className="h-5 w-5 text-brand" />
                    <p className="text-sm font-bold tracking-wide">PATTERN DETAILS</p>
                  </div>
                  <dl className="grid grid-cols-2 lg:grid-cols-4">
                    {[
                      { label: "Zone", value: selected?.zone_name ?? "General Facility" },
                      { label: "Occurrences", value: selected ? String(selected.occurrence_count) : "—" },
                      {
                        label: "First Detected",
                        value: selected
                          ? new Date(selected.first_detected_at).toLocaleDateString("en-US", {
                              month: "short",
                              day: "numeric",
                              year: "numeric",
                            })
                          : "—",
                      },
                      {
                        label: "Last Detected",
                        value: selected
                          ? new Date(selected.last_detected_at).toLocaleDateString("en-US", {
                              month: "short",
                              day: "numeric",
                              year: "numeric",
                            })
                          : "—",
                      },
                    ].map((row) => (
                      <div key={row.label} className="min-w-0 border-b border-r border-border p-4 last:border-r-0">
                        <dt className="truncate text-xs text-muted-foreground">{row.label}</dt>
                        <dd className="mt-2 truncate text-sm font-semibold">{row.value}</dd>
                      </div>
                    ))}
                  </dl>
                </div>

                <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
                  {/* Trend Over Time with real Recharts AreaChart */}
                  <div className="flex flex-col rounded-xl border border-border bg-card">
                    <div className="flex items-center justify-between border-b border-border px-5 py-4">
                      <div className="flex items-center gap-2">
                        <LineChart className="h-5 w-5 text-brand" />
                        <p className="text-sm font-bold tracking-wide">TREND OVER TIME</p>
                      </div>
                      {selected && trendData.length > 0 && (
                        <span className="text-xs text-muted-foreground">
                          {trendData.length} {trendData.length === 1 ? "day" : "days"} recorded
                        </span>
                      )}
                    </div>
                    <div className="flex flex-1 flex-col p-5">
                      {selected && trendData.length > 0 ? (
                        <div>
                          <div className="mb-3 flex items-center justify-between">
                            <div>
                              <p className="text-xs text-muted-foreground">Daily Occurrence Frequency</p>
                              <p className="text-lg font-bold text-foreground">
                                {selected.occurrence_count} total occurrences
                              </p>
                            </div>
                            <div className="flex items-center gap-2 text-xs font-medium text-brand">
                              <span className="inline-block h-2 w-2 rounded-full bg-brand"></span>
                              Daily Incidents
                            </div>
                          </div>
                          <div className="h-56 w-full">
                            <ResponsiveContainer width="100%" height="100%">
                              <AreaChart data={trendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                                <defs>
                                  <linearGradient id="patternTrendGradient" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="hsl(var(--brand))" stopOpacity={0.35} />
                                    <stop offset="95%" stopColor="hsl(var(--brand))" stopOpacity={0.0} />
                                  </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.6} />
                                <XAxis
                                  dataKey="date"
                                  tickFormatter={(val: string) => {
                                    try {
                                      const parts = val.split("-");
                                      if (parts.length === 3) {
                                        const date = new Date(
                                          Number(parts[0]),
                                          Number(parts[1]) - 1,
                                          Number(parts[2]),
                                        );
                                        return date.toLocaleDateString("en-US", {
                                          month: "short",
                                          day: "numeric",
                                        });
                                      }
                                      return val;
                                    } catch {
                                      return val;
                                    }
                                  }}
                                  tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
                                  tickLine={false}
                                  axisLine={{ stroke: "hsl(var(--border))" }}
                                />
                                <YAxis
                                  allowDecimals={false}
                                  tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
                                  tickLine={false}
                                  axisLine={false}
                                />
                                <Tooltip
                                  content={({ active, payload, label }) => {
                                    if (!active || !payload || !payload.length || !payload[0]) return null;
                                    const dateFormatted = (() => {
                                      try {
                                        const parts = String(label).split("-");
                                        if (parts.length === 3) {
                                          const d = new Date(
                                            Number(parts[0]),
                                            Number(parts[1]) - 1,
                                            Number(parts[2]),
                                          );
                                          return d.toLocaleDateString("en-US", {
                                            weekday: "short",
                                            month: "short",
                                            day: "numeric",
                                            year: "numeric",
                                          });
                                        }
                                        return String(label);
                                      } catch {
                                        return String(label);
                                      }
                                    })();
                                    return (
                                      <div className="rounded-lg border border-border bg-card px-3 py-2 text-xs shadow-lg">
                                        <p className="font-semibold text-foreground">{dateFormatted}</p>
                                        <p className="mt-1 font-medium text-brand">
                                          <span className="text-sm font-bold">{payload[0]?.value ?? 0}</span> occurrences
                                        </p>
                                      </div>
                                    );
                                  }}
                                />
                                <Area
                                  type="monotone"
                                  dataKey="occurrences"
                                  stroke="hsl(var(--brand))"
                                  strokeWidth={2.5}
                                  fill="url(#patternTrendGradient)"
                                  dot={{
                                    r: 4,
                                    fill: "hsl(var(--brand))",
                                    strokeWidth: 2,
                                    stroke: "hsl(var(--card))",
                                  }}
                                  activeDot={{
                                    r: 6,
                                    stroke: "hsl(var(--brand))",
                                    strokeWidth: 2,
                                    fill: "hsl(var(--card))",
                                  }}
                                />
                              </AreaChart>
                            </ResponsiveContainer>
                          </div>
                        </div>
                      ) : (
                        <div className="flex flex-1 flex-col items-center justify-center gap-3 py-12 text-center">
                          <LineChart className="h-10 w-10 text-muted-foreground/40" />
                          <div>
                            <p className="text-base font-bold text-foreground">
                              {selected ? "No trend data recorded" : "No pattern selected"}
                            </p>
                            <p className="mt-1 text-sm text-muted-foreground">
                              {selected
                                ? `Daily occurrence trend data is not available for "${selected.title}".`
                                : "Select a recurring pattern from the list to view its historical trend."}
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Pattern insights */}
                  <div className="rounded-xl border border-border bg-card">
                    <div className="flex items-center gap-2 border-b border-border px-5 py-4">
                      <Lightbulb className="h-5 w-5 text-warn" />
                      <p className="text-sm font-bold tracking-wide">PATTERN INSIGHTS</p>
                    </div>
                    <dl className="p-5">
                      {[
                        { label: "Status", value: selected?.status ?? "—" },
                        {
                          label: "Confidence",
                          value:
                            selected?.confidence_score != null
                              ? `${Math.round(selected.confidence_score * 100)}%`
                              : "—",
                        },
                        {
                          label: "Pattern Type",
                          value: selected
                            ? PATTERN_TYPE_LABELS[selected.pattern_type] ?? selected.pattern_type
                            : "—",
                        },
                      ].map((row) => (
                        <div
                          key={row.label}
                          className="flex items-center justify-between gap-3 py-2.5 text-sm"
                        >
                          <dt className="min-w-0 truncate text-muted-foreground">{row.label}</dt>
                          <dd className="shrink-0 font-semibold capitalize">{row.value}</dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                </div>

                {/* Description & Hazard overview */}
                <div className="rounded-xl border border-border bg-card">
                  <div className="flex items-center gap-2 border-b border-border px-5 py-4">
                    <ShieldCheck className="h-5 w-5 text-safe" />
                    <p className="text-sm font-bold tracking-wide">DESCRIPTION</p>
                  </div>
                  <div className="flex items-center gap-4 p-6">
                    <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-safe-soft text-safe">
                      <ShieldCheck className="h-7 w-7" />
                    </span>
                    <div className="min-w-0">
                      <p className="text-base font-bold">
                        {selected ? selected.title : "No pattern selected"}
                      </p>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {selected?.description ??
                          "Select a pattern from the list to view details and insights."}
                      </p>
                    </div>
                  </div>
                </div>
              </section>
            </div>
          )}
        </main>

        <footer className="border-t border-border py-5 text-center text-sm text-muted-foreground">
          &copy; 2026 SafeVision AI. All rights reserved.
        </footer>
      </div>
    </AuthGuard>
  );
}
