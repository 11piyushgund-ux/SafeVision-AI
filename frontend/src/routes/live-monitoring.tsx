import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Activity,
  AlertTriangle,
  Camera,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  Eye,
  FileText,
  Flame,
  HardHat,
  Loader2,
  Maximize2,
  Minimize2,
  Pause,
  PersonStanding,
  Play,
  Radio,
  RefreshCw,
  RotateCcw,
  Settings,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Square,
  TrendingUp,
  Upload,
  Video,
  VideoOff,
  X,
} from "lucide-react";
import { AppHeader } from "@/components/AppHeader";
import { AuthGuard } from "@/components/auth-guard";
import { VideoCanvasOverlay } from "@/components/safevision/VideoCanvasOverlay";
import {
  analyzeEventWithAI,
  deleteVideoSession,
  fetchCameras,
  fetchDashboardSummary,
  fetchEvents,
  fetchZones,
  getAuthToken,
  getWebSocketUrl,
  uploadVideoForMonitoring,
} from "@/lib/api-client";
import type {
  AIAnalysisResult,
  CameraResponse,
  EventResponse,
  VideoUploadResponse,
  WSFramePayload,
  ZoneResponse,
} from "@/lib/api-types";

export const Route = createFileRoute("/live-monitoring")({
  head: () => ({
    meta: [
      { title: "Live Monitoring | SafeVision AI" },
      {
        name: "description",
        content:
          "Real-time AI monitoring of safety events, PPE compliance, and restricted areas.",
      },
      { property: "og:title", content: "Live Monitoring | SafeVision AI" },
      {
        property: "og:description",
        content:
          "Real-time AI monitoring of safety events, PPE compliance, and restricted areas.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: LiveMonitoring,
});

type Severity = "high" | "medium" | "safe";

const severityStyles: Record<Severity, { chip: string; text: string; iconBg: string; dot: string }> = {
  high: {
    chip: "bg-danger-soft text-danger",
    text: "text-danger",
    iconBg: "bg-danger-soft text-danger",
    dot: "bg-danger",
  },
  medium: {
    chip: "bg-warn-soft text-warn",
    text: "text-warn",
    iconBg: "bg-warn-soft text-warn",
    dot: "bg-warn",
  },
  safe: {
    chip: "bg-safe-soft text-safe",
    text: "text-safe",
    iconBg: "bg-safe-soft text-safe",
    dot: "bg-safe",
  },
};

const EVENT_ICONS: Record<string, typeof AlertTriangle> = {
  zone_intrusion: AlertTriangle,
  ppe_detection: HardHat,
  fire_smoke: Flame,
  person_detected: PersonStanding,
  tracking_update: ShieldCheck,
};

function eventSeverity(e: EventResponse): Severity {
  if (e.event_type === "fire_smoke" || e.event_type === "zone_intrusion") return "high";
  if (e.event_type === "ppe_detection") return "medium";
  return "safe";
}

const EVENT_TYPE_LABELS: Record<string, string> = {
  ppe_detection: "PPE Violation",
  fire_smoke: "Fire / Smoke Detected",
  zone_intrusion: "Restricted Zone Incursion",
  person_detected: "Person Detected",
  tracking_update: "Tracking Update",
};

const quickActions = [
  {
    title: "Report Alert",
    sub: "Create Incident Report",
    Icon: AlertTriangle,
    tone: "bg-danger-soft text-danger",
  },
  {
    title: "View Alerts",
    sub: "Go to Safety Alerts",
    Icon: ClipboardList,
    tone: "bg-brand-soft text-brand",
  },
  {
    title: "Export Report",
    sub: "Generate Live Report",
    Icon: FileText,
    tone: "bg-safe-soft text-safe",
  },
  {
    title: "AI Insights",
    sub: "Go to Insights Module",
    Icon: TrendingUp,
    tone: "bg-insight-soft text-insight",
  },
];

function LiveMonitoring() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const videoContainerRef = useRef<HTMLDivElement | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(document.fullscreenElement === videoContainerRef.current);
    };
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
    };
  }, []);

  const toggleFullscreen = async () => {
    try {
      if (!document.fullscreenElement) {
        if (videoContainerRef.current?.requestFullscreen) {
          await videoContainerRef.current.requestFullscreen();
        }
      } else {
        if (document.exitFullscreen) {
          await document.exitFullscreen();
        }
      }
    } catch (err) {
      console.error("Failed to toggle fullscreen:", err);
    }
  };

  const [cameraOn, setCameraOn] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);

  // Video Streaming State (Phase 11)
  const [isUploading, setIsUploading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [activeSession, setActiveSession] = useState<VideoUploadResponse | null>(null);
  const [currentFrame, setCurrentFrame] = useState<WSFramePayload | null>(null);
  const [streamingError, setStreamingError] = useState<string | null>(null);
  const [selectedCameraId, setSelectedCameraId] = useState<string>("");

  // Live event accumulation & AI Modal state
  const [liveEventsList, setLiveEventsList] = useState<EventResponse[]>([]);
  const [selectedEventForAI, setSelectedEventForAI] = useState<EventResponse | null>(null);
  const [isAnalyzingAI, setIsAnalyzingAI] = useState(false);
  const [aiAnalysisResult, setAiAnalysisResult] = useState<AIAnalysisResult | null>(null);
  const [aiAnalysisError, setAiAnalysisError] = useState<string | null>(null);
  const [lastAnalyzedInsightId, setLastAnalyzedInsightId] = useState<string | null>(null);

  // Queries
  const { data: cameras } = useQuery({
    queryKey: ["cameras"],
    queryFn: fetchCameras,
  });

  const { data: zones } = useQuery({
    queryKey: ["zones"],
    queryFn: fetchZones,
  });

  const { data: recentEvents, isLoading: eventsLoading } = useQuery({
    queryKey: ["live-events"],
    queryFn: () => fetchEvents({ page: 1, size: 8 }),
    refetchInterval: isStreaming ? 5_000 : 30_000,
  });

  const { data: stats } = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: fetchDashboardSummary,
    refetchInterval: isStreaming ? 5_000 : 30_000,
  });

  // Sync initial camera selection
  useEffect(() => {
    if (cameras && cameras.length > 0 && !selectedCameraId) {
      const firstCam = cameras[0];
      if (firstCam) {
        setSelectedCameraId(firstCam.id);
      }
    }
  }, [cameras, selectedCameraId]);

  // Sync recent events to liveEventsList initially
  useEffect(() => {
    if (recentEvents?.data && liveEventsList.length === 0) {
      setLiveEventsList(recentEvents.data);
    }
  }, [recentEvents, liveEventsList.length]);

  const activeSessionRef = useRef<VideoUploadResponse | null>(null);
  activeSessionRef.current = activeSession;

  // Cleanup on true component unmount only
  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop());
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (activeSessionRef.current) {
        void deleteVideoSession(activeSessionRef.current.session_id);
      }
    };
  }, []);

  const selectedCamera = cameras?.find((c) => c.id === selectedCameraId) || cameras?.[0];
  const selectedZone = zones?.find((z) => z.id === selectedCamera?.zone_id) || zones?.[0];

  // Webcam controls
  const startCamera = async () => {
    setCameraError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      streamRef.current = stream;
      setCameraOn(true);
      requestAnimationFrame(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          void videoRef.current.play();
        }
      });
    } catch {
      setCameraError("Camera access was blocked. Allow camera permission and try again.");
    }
  };

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setCameraOn(false);
  };

  // Video File Upload & WebSocket Connection (Phase 11)
  const onFileSelect = async (file: File | undefined) => {
    if (!file) return;

    if (!selectedCamera) {
      toast.error("Please select a camera to monitor before uploading video");
      return;
    }

    // Stop webcam if active
    if (cameraOn) {
      stopCamera();
    }

    // Close previous WebSocket if active
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (activeSessionRef.current) {
      void deleteVideoSession(activeSessionRef.current.session_id);
    }

    setIsUploading(true);
    setStreamingError(null);
    setCurrentFrame(null);
    setIsStreaming(false);
    setIsPaused(false);

    try {
      const session = await uploadVideoForMonitoring(
        file,
        selectedCamera.id,
        selectedCamera.zone_id || selectedZone?.id || null
      );

      setActiveSession(session);
      setIsUploading(false);
      toast.success(`Video "${file.name}" uploaded (${session.total_frames} frames @ ${session.source_fps} FPS)`);

      // Initiate WebSocket with Immediate Auth Handshake (IPv4 normalized for Windows)
      const wsUrl = getWebSocketUrl(`/api/cv/video/ws/${session.session_id}`);

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        // Step 1: Send Immediate Authentication First Message (Within 3s)
        const token = getAuthToken() || "";
        ws.send(JSON.stringify({ type: "auth", token }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.type === "auth_ok") {
            // Step 2: Auth verified, request stream start
            ws.send(JSON.stringify({ action: "start" }));
            setIsStreaming(true);
          } else if (data.type === "auth_error") {
            setStreamingError(data.message || "Authentication failed");
            toast.error(`Stream Auth Error: ${data.message}`);
            ws.close();
          } else if (data.type === "frame") {
            const framePayload = data as WSFramePayload;
            setCurrentFrame(framePayload);

            // If frame produced new safety events, prepend to stream
            if (framePayload.new_events && framePayload.new_events.length > 0) {
              framePayload.new_events.forEach((ev) => {
                const newEventRow: EventResponse = {
                  id: ev.event_id,
                  camera_id: session.camera_id,
                  org_id: "",
                  event_type: ev.event_type,
                  timestamp: ev.timestamp,
                  confidence: 0.9,
                  detection_data: {
                    message: ev.message,
                    risk_assessment: {
                      risk_score: ev.risk_score,
                      risk_level: ev.risk_level,
                      explanation: ev.message,
                    },
                  },
                  evidence_path: null,
                  created_at: ev.timestamp,
                  camera_name: selectedCamera?.name || "Camera",
                  zone_name: selectedZone?.name || null,
                };
                setLiveEventsList((prev) => [newEventRow, ...prev.slice(0, 19)]);
              });

              // Refresh stats
              void queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
              void queryClient.invalidateQueries({ queryKey: ["live-events"] });
            }
          } else if (data.type === "completed") {
            setIsStreaming(false);
            toast.success(
              `Video analysis completed: ${data.total_frames_processed} frames evaluated, ${data.total_events_generated} events created.`
            );
          } else if (data.type === "error") {
            setStreamingError(data.message);
            toast.error(`Inference Error: ${data.message}`);
          }
        } catch (err) {
          console.error("Failed to parse WebSocket frame:", err);
        }
      };

      ws.onerror = (err) => {
        console.error("WebSocket error:", err);
        setStreamingError("WebSocket connection error. Ensure backend is running at http://localhost:8000.");
      };

      ws.onclose = (ev) => {
        setIsStreaming(false);
        if (ev.code === 4401) {
          setStreamingError("Authentication failed on video stream. Please log in again.");
        }
      };
    } catch (err) {
      setIsUploading(false);
      const msg = err instanceof Error ? err.message : "Failed to upload video";
      setStreamingError(msg);
      toast.error(msg);
    }
  };

  // Stream controls
  const togglePause = () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    const nextPaused = !isPaused;
    wsRef.current.send(JSON.stringify({ action: nextPaused ? "pause" : "resume" }));
    setIsPaused(nextPaused);
  };

  const stopStream = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: "stop" }));
      wsRef.current.close();
    }
    if (activeSession) {
      void deleteVideoSession(activeSession.session_id);
    }
    setIsStreaming(false);
    setIsPaused(false);
    setActiveSession(null);
    setCurrentFrame(null);
  };

  // AI Analysis on real selected event
  const triggerAIAnalysis = async (event: EventResponse) => {
    if (isAnalyzingAI) return;
    setSelectedEventForAI(event);
    setIsAnalyzingAI(true);
    setAiAnalysisResult(null);
    setAiAnalysisError(null);

    try {
      const response = await analyzeEventWithAI(event.id);
      if (response.success && response.analysis) {
        setAiAnalysisResult(response.analysis);
        setLastAnalyzedInsightId(response.insight_id ?? null);
        toast.success("AI Safety Analysis completed");
        await queryClient.invalidateQueries({ queryKey: ["ai-insights"] });
      } else {
        const errorMsg = response.error || "Analysis failed";
        setAiAnalysisError(errorMsg);
        toast.error(errorMsg);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to analyze event";
      setAiAnalysisError(msg);
      toast.error(msg);
    } finally {
      setIsAnalyzingAI(false);
    }
  };

  return (
    <AuthGuard>
      <div className="min-h-screen bg-background text-foreground">
        <AppHeader />

        <main className="mx-auto max-w-[1560px] px-6 py-6">
          {/* Header with Camera Selection */}
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold tracking-tight">LIVE MONITORING</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                Real-time AI monitoring of safety events, PPE compliance, and restricted areas.
              </p>
            </div>

            {/* Camera & Zone Selector */}
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-1.5 shadow-sm">
                <Camera className="h-4 w-4 text-brand" />
                <span className="text-xs font-medium text-muted-foreground">Camera:</span>
                <select
                  aria-label="Select Camera"
                  value={selectedCameraId}
                  onChange={(e) => setSelectedCameraId(e.target.value)}
                  disabled={isStreaming}
                  className="bg-transparent text-xs font-semibold text-foreground focus:outline-none cursor-pointer"
                >
                  {cameras?.map((cam) => (
                    <option key={cam.id} value={cam.id} className="bg-card text-foreground">
                      {cam.name} {cam.zone_name ? `(${cam.zone_name})` : ""}
                    </option>
                  ))}
                </select>
              </div>

              {selectedZone && (
                <div className="flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground shadow-sm">
                  <ShieldAlert className="h-3.5 w-3.5 text-warn" />
                  <span>Zone: <strong className="text-foreground">{selectedZone.name}</strong></span>
                </div>
              )}
            </div>
          </div>

          <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-[1.9fr_1fr]">
            {/* Left column — Video Monitoring Window */}
            <section className="space-y-5">
              <div className="relative overflow-hidden rounded-xl border border-border bg-[oklch(0.16_0.02_260)] shadow-lg">
                {/* 16:9 Aspect Video Viewport */}
                <div
                  ref={videoContainerRef}
                  className={`relative w-full bg-black/90 flex items-center justify-center ${
                    isFullscreen ? "h-full" : "aspect-video"
                  }`}
                >
                  {isUploading ? (
                    <div className="flex flex-col items-center justify-center gap-3 text-center">
                      <Loader2 className="h-10 w-10 animate-spin text-brand" />
                      <p className="text-sm font-semibold text-[oklch(0.97_0_0)]">
                        Uploading Video & Initializing CV Session...
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Preparing frame extraction & YOLO26 tracker
                      </p>
                    </div>
                  ) : currentFrame ? (
                    // Real Frame-by-Frame Canvas Overlay with Detections + ROI
                    <VideoCanvasOverlay
                      frame={currentFrame}
                      cameraName={selectedCamera?.name}
                      zoneName={selectedZone?.name}
                      className="h-full w-full"
                    />
                  ) : cameraOn ? (
                    <video
                      ref={videoRef}
                      muted
                      playsInline
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <div className="flex h-full w-full flex-col items-center justify-center gap-4 text-center p-6">
                      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-[oklch(1_0_0/0.08)] text-[oklch(0.9_0_0)]">
                        <Video className="h-7 w-7" />
                      </div>
                      <div>
                        <p className="text-base font-semibold text-[oklch(0.97_0_0)]">
                          Camera feed is idle
                        </p>
                        <p className="mt-1 text-sm text-[oklch(0.75_0_0)] max-w-md">
                          Upload recorded factory footage to run real frame-by-frame CV inference with YOLO, BoT-SORT tracking, and safety compliance monitoring.
                        </p>
                      </div>
                      <div className="flex items-center gap-3">
                        <button
                          onClick={() => fileInputRef.current?.click()}
                          className="inline-flex items-center gap-2 rounded-lg bg-brand px-5 py-2.5 text-sm font-semibold text-primary-foreground shadow-md transition-all hover:opacity-90 active:scale-95"
                        >
                          <Upload className="h-4 w-4" />
                          Upload MP4 Video
                        </button>
                        <button
                          onClick={startCamera}
                          className="inline-flex items-center gap-2 rounded-lg border border-[oklch(1_0_0/0.2)] bg-card/60 px-4 py-2.5 text-sm font-semibold text-[oklch(0.97_0_0)] transition-colors hover:bg-[oklch(1_0_0/0.1)]"
                        >
                          <Video className="h-4 w-4" />
                          Turn On Webcam
                        </button>
                      </div>
                      {cameraError && <p className="text-xs text-danger">{cameraError}</p>}
                      {streamingError && <p className="text-xs text-danger">{streamingError}</p>}
                    </div>
                  )}

                  {/* Overlaid Status Badges (Top Left & Top Right) */}
                  <div className="pointer-events-none absolute inset-0 p-4 flex flex-col justify-between">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="inline-flex items-center gap-2 rounded-md bg-[oklch(0.15_0_0/0.8)] px-3 py-1.5 text-xs font-semibold text-[oklch(0.98_0_0)] backdrop-blur-md">
                          <span
                            className={`h-2 w-2 rounded-full ${
                              isStreaming
                                ? isPaused
                                  ? "bg-amber-400"
                                  : "bg-safe animate-pulse"
                                : cameraOn
                                ? "bg-safe"
                                : "bg-[oklch(0.6_0_0)]"
                            }`}
                          />
                          {isStreaming
                            ? isPaused
                              ? "PAUSED"
                              : "LIVE CV INFERENCE"
                            : cameraOn
                            ? "LIVE WEBCAM"
                            : "OFFLINE"}
                        </span>
                        <span className="rounded-md bg-[oklch(0.15_0_0/0.8)] px-3 py-1.5 text-xs font-medium text-[oklch(0.98_0_0)] backdrop-blur-md">
                          {selectedCamera?.name || "Camera 01"} — {selectedZone?.name || "No Zone"}
                        </span>
                      </div>

                      <div className="pointer-events-auto flex items-center gap-2">
                        {currentFrame && (
                          <span className="rounded-md bg-[oklch(0.15_0_0/0.85)] px-2.5 py-1 text-xs font-bold text-brand backdrop-blur-md">
                            INFERENCE: {currentFrame.stats.inference_fps} FPS
                          </span>
                        )}
                        <button
                          type="button"
                          onClick={toggleFullscreen}
                          aria-label={isFullscreen ? "Exit fullscreen" : "Maximize view"}
                          className="rounded-md bg-[oklch(0.15_0_0/0.75)] p-2 text-[oklch(0.98_0_0)] hover:opacity-80 transition-colors"
                        >
                          {isFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
                        </button>
                      </div>
                    </div>

                    {/* Bottom HUD Bar when streaming */}
                    {currentFrame && (
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3 rounded-md bg-[oklch(0.15_0_0/0.85)] px-3 py-1.5 text-xs font-medium text-[oklch(0.95_0_0)] backdrop-blur-md">
                          <span>
                            FRAME: <strong>{currentFrame.frame_idx + 1}</strong> / {currentFrame.total_frames}
                          </span>
                          <span>|</span>
                          <span>
                            PERSONS: <strong className="text-safe">{currentFrame.stats.persons_detected}</strong>
                          </span>
                          <span>|</span>
                          <span>
                            VIOLATIONS:{" "}
                            <strong className={currentFrame.stats.active_violations > 0 ? "text-danger" : "text-safe"}>
                              {currentFrame.stats.active_violations}
                            </strong>
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Video Controls & Actions Bar */}
                <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[oklch(1_0_0/0.1)] bg-[oklch(0.2_0.02_260)] px-4 py-3">
                  <div className="flex flex-wrap items-center gap-2">
                    {/* Upload File Button */}
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      disabled={isUploading}
                      className="inline-flex items-center gap-2 rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-primary-foreground shadow transition-all hover:opacity-90 disabled:opacity-50"
                    >
                      <Upload className="h-4 w-4" />
                      {isStreaming ? "Upload Another Video" : "Upload Video File"}
                    </button>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="video/mp4,video/x-m4v,video/*"
                      className="hidden"
                      onChange={(e) => onFileSelect(e.target.files?.[0])}
                    />

                    {/* Stream Controls */}
                    {isStreaming && (
                      <>
                        <button
                          onClick={togglePause}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-sm font-semibold transition-colors hover:bg-accent"
                        >
                          {isPaused ? <Play className="h-4 w-4 text-safe" /> : <Pause className="h-4 w-4" />}
                          {isPaused ? "Resume" : "Pause"}
                        </button>
                        <button
                          onClick={stopStream}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-danger/40 bg-danger-soft px-3 py-2 text-sm font-semibold text-danger transition-colors hover:bg-danger/20"
                        >
                          <Square className="h-4 w-4" />
                          Stop
                        </button>
                      </>
                    )}

                    {cameraOn && (
                      <button
                        onClick={stopCamera}
                        className="inline-flex items-center gap-2 rounded-lg bg-danger px-4 py-2 text-sm font-semibold text-primary-foreground"
                      >
                        <VideoOff className="h-4 w-4" />
                        Turn Off Webcam
                      </button>
                    )}
                  </div>

                  {activeSession ? (
                    <div className="flex items-center gap-2 text-xs text-[oklch(0.85_0_0)]">
                      <span className="truncate max-w-[200px] font-semibold">{activeSession.filename}</span>
                      <span>({activeSession.width}x{activeSession.height} @ {activeSession.source_fps} FPS)</span>
                    </div>
                  ) : (
                    <span className="text-xs text-[oklch(0.72_0_0)]">
                      Supported formats: MP4, AVI, MOV, WebM (Max 100MB)
                    </span>
                  )}
                </div>
              </div>

              {/* Quick actions */}
              <div className="rounded-xl border border-border bg-card p-5">
                <p className="text-xs font-bold tracking-[0.12em] text-muted-foreground">
                  QUICK ACTIONS
                </p>
                <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  {quickActions.map(({ title, sub, Icon, tone }) => (
                    <button
                      key={title}
                      className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-3 text-left transition-colors hover:bg-accent"
                    >
                      <span className={`flex h-10 w-10 items-center justify-center rounded-lg ${tone}`}>
                        <Icon className="h-5 w-5" />
                      </span>
                      <span>
                        <span className="block text-sm font-semibold">{title}</span>
                        <span className="block text-xs text-muted-foreground">{sub}</span>
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            </section>

            {/* Right column — Live Event Stream & AI Insights */}
            <aside className="space-y-5">
              {/* Live Event Stream */}
              <div className="rounded-xl border border-border bg-card shadow-sm">
                <div className="flex items-center justify-between border-b border-border px-5 py-4">
                  <span className="inline-flex items-center gap-2 text-sm font-bold tracking-wide">
                    <Radio className="h-4 w-4 text-danger animate-pulse" />
                    LIVE EVENT STREAM
                  </span>
                  <span className="text-xs font-medium text-muted-foreground">
                    {liveEventsList.length} Events
                  </span>
                </div>

                {eventsLoading && liveEventsList.length === 0 ? (
                  <div className="flex items-center justify-center gap-2 py-8">
                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                    <span className="text-xs text-muted-foreground">Loading events...</span>
                  </div>
                ) : liveEventsList.length === 0 ? (
                  <div className="px-5 py-8 text-center text-sm text-muted-foreground">
                    No safety events detected yet.
                  </div>
                ) : (
                  <ul className="max-h-[360px] overflow-y-auto divide-y divide-border">
                    {liveEventsList.map((e: EventResponse) => {
                      const sev = eventSeverity(e);
                      const s = severityStyles[sev];
                      const Icon = EVENT_ICONS[e.event_type] ?? AlertTriangle;
                      return (
                        <li
                          key={e.id}
                          onClick={() => {
                            setSelectedEventForAI(e);
                            setAiAnalysisResult(null);
                            setAiAnalysisError(null);
                            setLastAnalyzedInsightId(null);
                          }}
                          className="flex items-start gap-3 p-4 transition-colors hover:bg-accent/60 cursor-pointer group"
                        >
                          <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${s.iconBg}`}>
                            <Icon className="h-5 w-5" />
                          </span>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center justify-between">
                              <p className="text-[11px] text-muted-foreground">
                                {new Date(e.timestamp).toLocaleTimeString()}
                              </p>
                              <div className="flex items-center gap-1.5">
                                <button
                                  type="button"
                                  onClick={(evt) => {
                                    evt.stopPropagation();
                                    triggerAIAnalysis(e);
                                  }}
                                  className="inline-flex items-center gap-1 rounded bg-insight/10 px-1.5 py-0.5 text-[9px] font-semibold text-insight hover:bg-insight hover:text-white transition-colors"
                                  title="Analyze this event with AI"
                                >
                                  <Sparkles className="h-2.5 w-2.5" />
                                  <span>Analyze</span>
                                </button>
                                <span className={`rounded px-1.5 py-0.5 text-[9px] font-bold tracking-wide ${s.chip}`}>
                                  {sev.toUpperCase()}
                                </span>
                              </div>
                            </div>
                            <p className={`mt-0.5 text-sm font-semibold truncate ${s.text}`}>
                              {EVENT_TYPE_LABELS[e.event_type] ?? e.event_type}
                            </p>
                            <p className="mt-0.5 text-xs text-muted-foreground truncate">
                              {e.zone_name ?? e.camera_name ?? "Zone A"}
                            </p>
                          </div>
                          <div className="flex items-center text-muted-foreground group-hover:text-brand transition-colors pt-2">
                            <ChevronRight className="h-4 w-4" />
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>

              {/* AI Live Insights / Event Analysis Drawer */}
              <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
                <div className="flex items-center justify-between border-b border-border pb-3">
                  <span className="inline-flex items-center gap-2 text-sm font-bold tracking-wide">
                    <Sparkles className="h-4 w-4 text-insight" />
                    AI SAFETY INSIGHTS
                  </span>
                  {selectedEventForAI && (
                    <button
                      onClick={() => {
                        setSelectedEventForAI(null);
                        setAiAnalysisResult(null);
                      }}
                      className="text-xs text-muted-foreground hover:text-foreground"
                    >
                      Clear
                    </button>
                  )}
                </div>

                <div className="mt-4">
                  {selectedEventForAI ? (
                    <div className="space-y-3">
                      <div className="rounded-lg border border-border bg-accent/30 p-3">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-foreground">
                            {EVENT_TYPE_LABELS[selectedEventForAI.event_type] || selectedEventForAI.event_type}
                          </span>
                          <span className="text-[10px] text-muted-foreground">
                            {new Date(selectedEventForAI.timestamp).toLocaleTimeString()}
                          </span>
                        </div>
                        {Boolean(selectedEventForAI.detection_data?.["risk_assessment"]) && (
                          <div className="mt-2 flex items-center gap-2 text-xs">
                            <span className="text-muted-foreground">Deterministic Risk:</span>
                            <span className="font-bold text-danger">
                              {Number((selectedEventForAI.detection_data?.["risk_assessment"] as { risk_score?: number })?.risk_score ?? 0).toFixed(2)} (
                              {String((selectedEventForAI.detection_data?.["risk_assessment"] as { risk_level?: string })?.risk_level ?? "UNKNOWN").toUpperCase()})
                            </span>
                          </div>
                        )}
                      </div>

                      {isAnalyzingAI ? (
                        <div className="flex items-center justify-center gap-2 py-6">
                          <Loader2 className="h-5 w-5 animate-spin text-insight" />
                          <span className="text-xs text-muted-foreground">Running AI safety reasoning with policy RAG...</span>
                        </div>
                      ) : aiAnalysisResult ? (
                        <div className="space-y-3 rounded-lg border border-insight/30 bg-insight-soft/10 p-3.5 text-xs">
                          <div className="flex items-center justify-between border-b border-border/60 pb-2">
                            <span className="inline-flex items-center gap-1.5 font-bold text-foreground">
                              <Sparkles className="h-3.5 w-3.5 text-insight" />
                              AI Safety Analysis
                            </span>
                            <span className="inline-flex items-center rounded bg-insight/10 px-2 py-0.5 font-mono text-[10px] font-medium text-insight">
                              {aiAnalysisResult.provider} ({aiAnalysisResult.model})
                            </span>
                          </div>

                          {/* Summary */}
                          <div>
                            <p className="font-semibold text-foreground leading-relaxed">
                              {aiAnalysisResult.summary}
                            </p>
                          </div>

                          {/* Risk Explanation */}
                          {aiAnalysisResult.risk_explanation && (
                            <div>
                              <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                                Risk Explanation
                              </p>
                              <p className="mt-0.5 text-muted-foreground leading-relaxed">
                                {aiAnalysisResult.risk_explanation}
                              </p>
                            </div>
                          )}

                          {/* Visual Observations */}
                          {aiAnalysisResult.visual_observations && aiAnalysisResult.visual_observations.length > 0 && (
                            <div>
                              <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                                Visual Observations
                              </p>
                              <ul className="mt-1 list-disc list-inside space-y-0.5 text-foreground">
                                {aiAnalysisResult.visual_observations.map((obs, i) => (
                                  <li key={i}>{obs}</li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {/* Visual Validation */}
                          {aiAnalysisResult.visual_validation && typeof aiAnalysisResult.visual_validation === "object" && (
                            <div className="rounded border border-border bg-card/60 p-2 text-[11px] space-y-0.5">
                              <p className="font-semibold text-foreground">Visual Validation</p>
                              {Object.entries(aiAnalysisResult.visual_validation).map(([k, v]) => (
                                <div key={k} className="text-muted-foreground">
                                  <span className="font-medium text-foreground capitalize">{k.replace(/_/g, " ")}: </span>
                                  <span>{typeof v === "object" ? JSON.stringify(v) : String(v)}</span>
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Hazard Interpretation (Phase 14F) */}
                          {aiAnalysisResult.hazard_interpretation && (
                            <div className="rounded border border-amber-500/25 bg-amber-500/5 p-2 text-xs">
                              <p className="text-[10px] font-bold uppercase tracking-wider text-amber-500">
                                Hazard Interpretation
                              </p>
                              <p className="mt-1 text-foreground leading-relaxed">
                                {aiAnalysisResult.hazard_interpretation}
                              </p>
                            </div>
                          )}

                          {/* Recommended Actions Plan (Structured or Legacy) */}
                          {((aiAnalysisResult.immediate_actions && aiAnalysisResult.immediate_actions.length > 0) ||
                            (aiAnalysisResult.investigation_actions && aiAnalysisResult.investigation_actions.length > 0) ||
                            (aiAnalysisResult.preventive_actions && aiAnalysisResult.preventive_actions.length > 0) ||
                            (aiAnalysisResult.recommended_actions && aiAnalysisResult.recommended_actions.length > 0)) && (
                            <div className="space-y-2">
                              <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                                Recommended Action Plan
                              </p>
                              {aiAnalysisResult.immediate_actions && aiAnalysisResult.immediate_actions.length > 0 ? (
                                <div className="space-y-1.5">
                                  {aiAnalysisResult.immediate_actions.map((act, i) => {
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
                                  {aiAnalysisResult.investigation_actions?.map((act, i) => {
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
                                  {aiAnalysisResult.preventive_actions?.map((act, i) => {
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
                                <ul className="mt-1 list-disc list-inside space-y-0.5 text-foreground">
                                  {aiAnalysisResult.recommended_actions.map((act, i) => (
                                    <li key={i}>{act}</li>
                                  ))}
                                </ul>
                              )}
                            </div>
                          )}

                          {/* Navigation Button */}
                          {lastAnalyzedInsightId && (
                            <div className="pt-2 border-t border-border flex items-center justify-between">
                              <span className="text-[10px] text-muted-foreground font-mono">
                                ID: {lastAnalyzedInsightId.slice(0, 8)}...
                              </span>
                              <button
                                type="button"
                                id="drawer-view-full-ai-insight-btn"
                                onClick={() => {
                                  navigate({
                                    to: "/ai-safety-insights",
                                    search: { insight_id: lastAnalyzedInsightId },
                                  });
                                }}
                                className="inline-flex items-center gap-1 rounded bg-insight px-2.5 py-1 text-xs font-semibold text-white shadow-sm hover:opacity-90"
                              >
                                <span>View Full AI Insight</span>
                                <ChevronRight className="h-3 w-3" />
                              </button>
                            </div>
                          )}
                        </div>
                      ) : aiAnalysisError ? (
                        <div className="rounded-lg border border-danger/30 bg-danger-soft p-3 text-xs text-danger">
                          {aiAnalysisError}
                        </div>
                      ) : (
                        <button
                          type="button"
                          id="live-analyze-event-btn"
                          disabled={isAnalyzingAI}
                          onClick={() => triggerAIAnalysis(selectedEventForAI)}
                          className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-insight px-4 py-2 text-xs font-semibold text-white shadow transition-all hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {isAnalyzingAI ? (
                            <>
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              <span>Analyzing...</span>
                            </>
                          ) : (
                            <>
                              <Sparkles className="h-3.5 w-3.5" />
                              <span>Analyze Event</span>
                            </>
                          )}
                        </button>
                      )}
                    </div>
                  ) : (
                    <div className="flex items-start gap-3">
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-insight-soft text-insight">
                        <Sparkles className="h-4 w-4" />
                      </span>
                      <p className="text-sm leading-relaxed text-muted-foreground">
                        Click any event in the stream above to review deterministic risk factors and generate AI incident insights with safety policy guidance.
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {/* Stats Cards */}
              <div className="grid grid-cols-3 gap-3">
                <div className="min-w-0 rounded-lg border border-border bg-card p-3 shadow-sm">
                  <p className="flex items-center gap-1.5 text-[10px] font-semibold text-muted-foreground">
                    <Shield className="h-3.5 w-3.5 text-insight" />
                    <span>ALERTS</span>
                  </p>
                  <p className="mt-1.5 text-base font-bold text-warn">
                    {stats ? String(stats.new_alerts).padStart(2, "0") : "--"}
                  </p>
                  <p className="mt-0.5 truncate text-[10px] text-muted-foreground">Active Unresolved</p>
                </div>
                <div className="min-w-0 rounded-lg border border-border bg-card p-3 shadow-sm">
                  <p className="flex items-center gap-1.5 text-[10px] font-semibold text-muted-foreground">
                    <AlertTriangle className="h-3.5 w-3.5 text-danger" />
                    <span>EVENTS</span>
                  </p>
                  <p className="mt-1.5 text-base font-bold text-foreground">
                    {stats ? String(stats.total_events).padStart(2, "0") : "--"}
                  </p>
                  <p className="mt-0.5 truncate text-[10px] text-muted-foreground">Total Detected</p>
                </div>
                <div className="min-w-0 rounded-lg border border-border bg-card p-3 shadow-sm">
                  <p className="flex items-center gap-1.5 text-[10px] font-semibold text-muted-foreground">
                    <ShieldCheck className="h-3.5 w-3.5 text-safe" />
                    <span>ZONES</span>
                  </p>
                  <p className="mt-1.5 text-base font-bold text-foreground">
                    {stats ? `${stats.active_zones}/${stats.total_zones}` : "--"}
                  </p>
                  <p className="mt-0.5 truncate text-[10px] text-muted-foreground">Active Monitored</p>
                </div>
              </div>
            </aside>
          </div>
        </main>
      </div>
    </AuthGuard>
  );
}
