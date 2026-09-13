import React, { useEffect, useRef } from "react";
import type { WSFramePayload, WSDetectionItem } from "@/lib/api-types";

interface VideoCanvasOverlayProps {
  frame: WSFramePayload | null;
  cameraName?: string | undefined;
  zoneName?: string | undefined;
  className?: string | undefined;
}

export const VideoCanvasOverlay: React.FC<VideoCanvasOverlayProps> = ({
  frame,
  cameraName = "Camera 01",
  zoneName,
  className = "",
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);

  useEffect(() => {
    if (!imgRef.current) {
      imgRef.current = new Image();
    }
  }, []);

  useEffect(() => {
    if (!frame || !canvasRef.current || !imgRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const img = imgRef.current;
    img.src = frame.image;

    img.onload = () => {
      // Sync canvas dimensions to original frame resolution
      if (img.naturalWidth > 0 && (canvas.width !== img.naturalWidth || canvas.height !== img.naturalHeight)) {
        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
      }

      const w = canvas.width;
      const h = canvas.height;

      // 1. Draw raw video frame
      ctx.drawImage(img, 0, 0, w, h);

      // 2. Zone polygon overlay removed per Phase 11B requirements (clean video CV stream)

      // 3. Draw Detections
      if (frame.detections && frame.detections.length > 0) {
        frame.detections.forEach((det: WSDetectionItem) => {
          if (!det.bbox || det.bbox.length < 4) return;
          const x1 = det.bbox[0];
          const y1 = det.bbox[1];
          const x2 = det.bbox[2];
          const y2 = det.bbox[3];
          if (x1 === undefined || y1 === undefined || x2 === undefined || y2 === undefined) return;
          const bw = x2 - x1;
          const bh = y2 - y1;

          ctx.save();
          let strokeColor = "#22c55e"; // compliant green
          let fillColor = "rgba(34, 197, 94, 0.1)";

          const isPerson = det.class_name.toLowerCase() === "person" || det.class_name.toLowerCase() === "worker";
          const isFireSmoke = det.class_name.toLowerCase() === "fire" || det.class_name.toLowerCase() === "smoke";

          if (isFireSmoke) {
            strokeColor = "#f97316";
            fillColor = "rgba(249, 115, 22, 0.2)";
          } else if (isPerson && !det.is_compliant) {
            strokeColor = "#ef4444"; // violation red
            fillColor = "rgba(239, 68, 68, 0.15)";
          } else if (!isPerson) {
            strokeColor = "#3b82f6"; // PPE item blue
            fillColor = "rgba(59, 130, 246, 0.08)";
          }

          // Bounding box
          ctx.lineWidth = isPerson ? 2.5 : 1.5;
          ctx.strokeStyle = strokeColor;
          ctx.fillStyle = fillColor;
          ctx.beginPath();
          ctx.roundRect(x1, y1, bw, bh, 4);
          ctx.stroke();
          ctx.fill();

          // Label Pill
          ctx.font = "bold 12px Inter, sans-serif";
          let label = `${det.class_name.toUpperCase()}`;
          if (det.track_id !== null && det.track_id !== undefined) {
            label = `#${det.track_id} ${label}`;
          }
          label += ` ${Math.round(det.confidence * 100)}%`;

          const tagWidth = ctx.measureText(label).width;
          const tagH = 18;
          const tagY = Math.max(18, y1 - 4);

          ctx.fillStyle = strokeColor;
          ctx.beginPath();
          ctx.roundRect(x1, tagY - tagH + 3, tagWidth + 10, tagH, 3);
          ctx.fill();

          ctx.fillStyle = "#ffffff";
          ctx.fillText(label, x1 + 5, tagY);

          // Missing PPE alert tag below person
          if (isPerson && !det.is_compliant && det.missing_ppe && det.missing_ppe.length > 0) {
            const missingText = `MISSING: ${det.missing_ppe.join(", ").toUpperCase()}`;
            ctx.font = "bold 11px Inter, sans-serif";
            const mWidth = ctx.measureText(missingText).width;
            const mY = Math.min(h - 8, y2 + 16);

            ctx.fillStyle = "rgba(239, 68, 68, 0.95)";
            ctx.beginPath();
            ctx.roundRect(x1, mY - 13, mWidth + 10, 16, 3);
            ctx.fill();

            ctx.fillStyle = "#ffffff";
            ctx.fillText(missingText, x1 + 5, mY - 1);
          }

          ctx.restore();
        });
      }

      // 4. Subtle HUD Watermark in Bottom Left
      ctx.save();
      ctx.font = "11px Inter, sans-serif";
      ctx.fillStyle = "rgba(255, 255, 255, 0.85)";
      const hudText = `${cameraName} | FRAME ${frame.frame_idx + 1}/${frame.total_frames} | ${frame.stats.inference_fps} FPS`;
      ctx.fillStyle = "rgba(15, 23, 42, 0.7)";
      ctx.beginPath();
      ctx.roundRect(12, h - 28, ctx.measureText(hudText).width + 12, 18, 3);
      ctx.fill();
      ctx.fillStyle = "#ffffff";
      ctx.fillText(hudText, 18, h - 15);
      ctx.restore();
    };

    img.src = frame.image;
  }, [frame, cameraName, zoneName]);

  return (
    <canvas
      ref={canvasRef}
      className={`h-full w-full object-contain ${className}`}
    />
  );
};
