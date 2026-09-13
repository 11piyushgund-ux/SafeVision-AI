import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Calendar, ChevronDown, ChevronLeft, ChevronRight, Eye, Loader2 } from "lucide-react";
import { AppHeader } from "@/components/AppHeader";
import { AuthGuard } from "@/components/auth-guard";
import { EventEvidenceModal } from "@/components/safevision/EventEvidenceModal";
import { fetchEvents } from "@/lib/api-client";
import type { EventResponse } from "@/lib/api-types";

export const Route = createFileRoute("/event-history")({
  head: () => ({
    meta: [
      { title: "Event History — SafeVision AI" },
      {
        name: "description",
        content:
          "View and review historical safety events detected by the SafeVision AI system, with filters for date, event type, location, risk level and status.",
      },
      { property: "og:title", content: "Event History — SafeVision AI" },
      {
        property: "og:description",
        content:
          "Browse detected workplace safety events with confidence scores, risk levels and review status.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: EventHistoryPage,
});

const EVENT_TYPES = [
  "All",
  "ppe_detection",
  "fire_smoke",
  "zone_intrusion",
  "person_detected",
  "tracking_update",
];

const EVENT_TYPE_LABELS: Record<string, string> = {
  ppe_detection: "PPE Detection",
  fire_smoke: "Fire / Smoke",
  zone_intrusion: "Zone Intrusion",
  person_detected: "Person Detected",
  tracking_update: "Tracking Update",
};

function confidenceColor(c: number | null): string {
  if (c == null) return "text-muted-foreground";
  if (c >= 0.9) return "text-risk-high";
  if (c >= 0.7) return "text-risk-medium";
  return "text-risk-low";
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <label className="block min-w-[150px] flex-1">
      <span className="mb-2 block text-[13px] text-muted-foreground">{label}</span>
      <span className="relative block">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full appearance-none rounded-lg border border-border bg-card px-3.5 py-2.5 text-[14px] font-medium text-foreground outline-none focus:border-primary"
        >
          {options.map((o) => (
            <option key={o} value={o}>
              {EVENT_TYPE_LABELS[o] ?? o}
            </option>
          ))}
        </select>
        <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      </span>
    </label>
  );
}

const PAGE_SIZE = 20;

function EventHistoryPage() {
  const [eventType, setEventType] = useState("All");
  const [page, setPage] = useState(1);
  const [selectedEvent, setSelectedEvent] = useState<EventResponse | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["events", page, eventType],
    queryFn: () =>
      fetchEvents({
        page,
        size: PAGE_SIZE,
        event_type: eventType === "All" ? null : eventType,
      }),
  });

  const events = data?.data ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const clearFilters = () => {
    setEventType("All");
    setPage(1);
  };

  return (
    <AuthGuard>
      <div className="min-h-screen bg-background">
        <AppHeader />

        <main className="mx-auto max-w-[1560px] px-6 py-7">
          <h1 className="text-[28px] font-bold tracking-tight text-foreground">Event History</h1>
          <p className="mt-2 text-[14px] text-muted-foreground">
            View and review historical safety events detected by the AI system.
          </p>

          {/* Filters */}
          <section className="mt-6 rounded-xl border border-border bg-card p-5 shadow-card">
            <div className="flex flex-wrap items-end gap-4">
              <FilterSelect
                label="Event Type"
                value={eventType}
                options={EVENT_TYPES}
                onChange={(v) => {
                  setEventType(v);
                  setPage(1);
                }}
              />
              <button
                type="button"
                onClick={clearFilters}
                className="rounded-lg border border-border bg-card px-5 py-2.5 text-[14px] font-medium text-foreground transition-colors hover:bg-muted"
              >
                Clear Filters
              </button>
            </div>
          </section>

          {/* Table */}
          <section className="mt-6 overflow-hidden rounded-xl border border-border bg-card shadow-card">
            {isLoading ? (
              <div className="flex items-center justify-center gap-3 py-16">
                <Loader2 className="h-5 w-5 animate-spin text-primary" />
                <span className="text-[14px] text-muted-foreground">Loading events...</span>
              </div>
            ) : isError ? (
              <div className="px-6 py-16 text-center text-[14px] text-danger">
                Failed to load events. Please try again.
              </div>
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[900px] border-collapse text-left">
                    <thead>
                      <tr className="border-b border-border bg-muted/40">
                        {[
                          "Event Type",
                          "Camera",
                          "Zone",
                          "Timestamp",
                          "Confidence",
                          "Actions",
                        ].map((h, i) => (
                          <th
                            key={h}
                            className={`px-6 py-4 text-[13px] font-semibold text-foreground ${
                              i >= 4 ? "text-center" : ""
                            }`}
                          >
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {events.map((e: EventResponse) => (
                        <tr key={e.id} className="border-b border-border last:border-0">
                          <td className="px-6 py-4 text-[14px] font-medium text-foreground">
                            {EVENT_TYPE_LABELS[e.event_type] ?? e.event_type}
                          </td>
                          <td className="px-6 py-4 text-[14px] text-foreground">
                            {e.camera_name ?? "—"}
                          </td>
                          <td className="px-6 py-4 text-[14px] text-foreground">
                            {e.zone_name ?? "—"}
                          </td>
                          <td className="px-6 py-4 text-[14px] text-foreground">
                            {new Date(e.timestamp).toLocaleString()}
                          </td>
                          <td className={`px-6 py-4 text-center text-[14px] font-semibold ${confidenceColor(e.confidence)}`}>
                            {e.confidence != null ? `${Math.round(e.confidence * 100)}%` : "—"}
                          </td>
                          <td className="px-6 py-4 text-center">
                            <button
                              type="button"
                              onClick={() => setSelectedEvent(e)}
                              className="inline-flex items-center gap-1.5 text-[14px] font-medium text-primary hover:underline transition-colors"
                            >
                              <Eye className="h-[18px] w-[18px]" strokeWidth={1.8} />
                              View
                            </button>
                          </td>
                        </tr>
                      ))}
                      {events.length === 0 && (
                        <tr>
                          <td colSpan={6} className="px-6 py-10 text-center text-[14px] text-muted-foreground">
                            No events match the selected filters.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                {/* Pagination */}
                <div className="flex flex-wrap items-center justify-between gap-4 px-6 py-4">
                  <span className="text-[14px] text-muted-foreground">
                    Page {page} of {totalPages} ({total} events)
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      disabled={page <= 1}
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      className="flex h-9 w-9 items-center justify-center rounded-lg border border-border text-muted-foreground transition-colors hover:bg-muted disabled:opacity-40"
                      aria-label="Previous page"
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </button>
                    {Array.from({ length: Math.min(5, totalPages) }, (_, i) => i + 1).map((p) => (
                      <button
                        key={p}
                        type="button"
                        onClick={() => setPage(p)}
                        className={`h-9 w-9 rounded-lg border text-[14px] font-medium transition-colors ${
                          page === p
                            ? "border-primary text-primary"
                            : "border-border text-foreground hover:bg-muted"
                        }`}
                      >
                        {p}
                      </button>
                    ))}
                    {totalPages > 5 && (
                      <>
                        <span className="px-1 text-[14px] text-muted-foreground">...</span>
                        <button
                          type="button"
                          onClick={() => setPage(totalPages)}
                          className={`h-9 w-9 rounded-lg border text-[14px] font-medium transition-colors ${
                            page === totalPages
                              ? "border-primary text-primary"
                              : "border-border text-foreground hover:bg-muted"
                          }`}
                        >
                          {totalPages}
                        </button>
                      </>
                    )}
                    <button
                      type="button"
                      disabled={page >= totalPages}
                      onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                      className="flex h-9 w-9 items-center justify-center rounded-lg border border-border text-muted-foreground transition-colors hover:bg-muted disabled:opacity-40"
                      aria-label="Next page"
                    >
                      <ChevronRight className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </>
            )}
          </section>
        </main>

        <EventEvidenceModal
          event={selectedEvent}
          isOpen={selectedEvent !== null}
          onClose={() => setSelectedEvent(null)}
        />
      </div>
    </AuthGuard>
  );
}
