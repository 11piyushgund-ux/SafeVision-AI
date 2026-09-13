import { useEffect, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { analyzeEventWithAI, fetchEventEvidenceBlobUrl } from "@/lib/api-client";
import type { AIAnalysisResult, EventResponse } from "@/lib/api-types";
import { Camera, ChevronRight, Clock, Film, ImageOff, Layers, Loader2, MapPin, ShieldAlert, Sparkles } from "lucide-react";

interface EventEvidenceModalProps {
  event: EventResponse | null;
  isOpen: boolean;
  onClose: () => void;
}

export function EventEvidenceModal({ event, isOpen, onClose }: EventEvidenceModalProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [aiResult, setAiResult] = useState<AIAnalysisResult | null>(null);
  const [createdInsightId, setCreatedInsightId] = useState<string | null>(null);
  const [aiError, setAiError] = useState<string | null>(null);

  useEffect(() => {
    setAiResult(null);
    setCreatedInsightId(null);
    setAiError(null);
  }, [event?.id, isOpen]);

  const handleAnalyze = async () => {
    if (!event?.id || isAnalyzing) return;
    setIsAnalyzing(true);
    setAiError(null);

    try {
      const res = await analyzeEventWithAI(event.id);
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


  useEffect(() => {
    let active = true;
    let currentObjectUrl: string | null = null;

    if (isOpen && event?.evidence_path) {
      setIsLoading(true);
      setHasError(false);
      setImageUrl(null);

      fetchEventEvidenceBlobUrl(event.id)
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
  }, [isOpen, event?.id, event?.evidence_path]);

  if (!event) return null;

  const detData = (event.detection_data || {}) as Record<string, any>;
  const riskData = (detData["risk_assessment"] || {}) as Record<string, any>;
  const sourceData = (detData["source"] || {}) as Record<string, any>;

  const frameIndex = sourceData["frame_index"] ?? "—";
  const sourceFilename = sourceData["filename"] ?? "—";
  const riskLevel = riskData["risk_level"] ?? "—";
  const riskScore = riskData["risk_score"] != null ? Math.round(riskData["risk_score"] * 100) : null;
  const eventTypeLabel = (event.event_type || "").replace(/_/g, " ").toUpperCase();

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-3xl overflow-hidden p-0 sm:rounded-xl">
        <DialogHeader className="border-b border-border bg-card px-6 py-4">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <ShieldAlert className="h-4 w-4" />
            </span>
            <div>
              <DialogTitle className="text-base font-bold text-foreground">
                Event Evidence & Details
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground">
                Authoritative frame evidence captured at promotion time.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="max-h-[80vh] overflow-y-auto p-6 space-y-6">
          {/* Visual Evidence Section */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold tracking-wider text-muted-foreground uppercase">
                Visual Evidence Frame
              </span>
              {frameIndex !== "—" && (
                <span className="inline-flex items-center gap-1 rounded bg-secondary px-2 py-0.5 text-xs font-mono font-medium text-secondary-foreground">
                  <Film className="h-3 w-3" />
                  Frame #{frameIndex}
                </span>
              )}
            </div>

            <div className="relative aspect-video w-full overflow-hidden rounded-lg border border-border bg-black/90 flex items-center justify-center">
              {isLoading && (
                <div className="flex flex-col items-center justify-center gap-2 text-muted-foreground">
                  <Loader2 className="h-8 w-8 animate-spin text-primary" />
                  <span className="text-xs">Loading authoritative evidence...</span>
                </div>
              )}

              {!isLoading && imageUrl && (
                <img
                  src={imageUrl}
                  alt={`Evidence frame for event ${event.id}`}
                  className="h-full w-full object-contain"
                />
              )}

              {!isLoading && (!imageUrl || hasError || !event.evidence_path) && (
                <div className="flex flex-col items-center justify-center gap-2 p-6 text-center text-muted-foreground">
                  <ImageOff className="h-10 w-10 text-muted-foreground/60" />
                  <p className="text-sm font-semibold text-foreground">Evidence unavailable</p>
                  <p className="max-w-sm text-xs text-muted-foreground">
                    Historical event or visual evidence was not persisted for this event record.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Authoritative Metadata Grid */}
          <div className="space-y-2">
            <span className="text-xs font-bold tracking-wider text-muted-foreground uppercase">
              Authoritative Event Metadata
            </span>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <div className="rounded-lg border border-border bg-card p-3">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Layers className="h-3.5 w-3.5" />
                  <span>Event Type</span>
                </div>
                <p className="mt-1 text-sm font-semibold text-foreground truncate">
                  {eventTypeLabel}
                </p>
              </div>

              <div className="rounded-lg border border-border bg-card p-3">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Camera className="h-3.5 w-3.5" />
                  <span>Camera</span>
                </div>
                <p className="mt-1 text-sm font-semibold text-foreground truncate">
                  {event.camera_name || event.camera_id || "—"}
                </p>
              </div>

              <div className="rounded-lg border border-border bg-card p-3">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <MapPin className="h-3.5 w-3.5" />
                  <span>Zone</span>
                </div>
                <p className="mt-1 text-sm font-semibold text-foreground truncate">
                  {event.zone_name || "—"}
                </p>
              </div>

              <div className="rounded-lg border border-border bg-card p-3">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Clock className="h-3.5 w-3.5" />
                  <span>Timestamp</span>
                </div>
                <p className="mt-1 text-sm font-semibold text-foreground truncate">
                  {new Date(event.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                </p>
              </div>

              <div className="rounded-lg border border-border bg-card p-3">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Sparkles className="h-3.5 w-3.5" />
                  <span>Confidence</span>
                </div>
                <p className="mt-1 text-sm font-semibold text-foreground">
                  {event.confidence != null ? `${Math.round(event.confidence * 100)}%` : "—"}
                </p>
              </div>

              <div className="rounded-lg border border-border bg-card p-3 flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <ShieldAlert className="h-3.5 w-3.5" />
                    <span>Risk Level</span>
                  </div>
                  <p className="mt-1 text-sm font-semibold text-foreground truncate">
                    {riskLevel !== "—" ? `${riskLevel.toUpperCase()}${riskScore != null ? ` (${riskScore})` : ""}` : "—"}
                  </p>
                </div>
                <button
                  type="button"
                  id="event-evidence-analyze-btn"
                  disabled={isAnalyzing}
                  onClick={handleAnalyze}
                  className="mt-2.5 inline-flex w-full items-center justify-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground shadow-sm transition-all hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
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
              </div>

              <div className="rounded-lg border border-border bg-card p-3">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Film className="h-3.5 w-3.5" />
                  <span>Frame Index</span>
                </div>
                <p className="mt-1 text-sm font-semibold text-foreground font-mono">
                  {frameIndex}
                </p>
              </div>

              <div className="rounded-lg border border-border bg-card p-3 col-span-2">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Film className="h-3.5 w-3.5" />
                  <span>Source Video</span>
                </div>
                <p className="mt-1 text-sm font-semibold text-foreground truncate">
                  {sourceFilename}
                </p>
              </div>
            </div>
          </div>

          {/* Inline AI Analysis Result Section */}
          {aiError && (
            <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-xs text-destructive">
              <p className="font-semibold">AI Analysis Failed</p>
              <p className="mt-1">{aiError}</p>
            </div>
          )}

          {aiResult && (
            <div className="rounded-xl border border-primary/20 bg-primary/5 p-5 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 pb-3">
                <div className="flex items-center gap-2">
                  <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <Sparkles className="h-4 w-4" />
                  </span>
                  <div>
                    <h4 className="text-sm font-bold text-foreground">AI Safety Intelligence</h4>
                    <p className="text-[11px] text-muted-foreground">
                      Multimodal evaluation of authoritative event frame
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
                      id="view-full-ai-insight-header-btn"
                      onClick={() => {
                        onClose();
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

              {/* Visual Observations (Gemma Multimodal) */}
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
                    id="view-full-ai-insight-footer-btn"
                    onClick={() => {
                      onClose();
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
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
