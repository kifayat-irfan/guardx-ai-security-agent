"use client";

import { useEffect, useRef, useState } from "react";
import type { CameraStatus, Detection, ZoneEvent } from "@/lib/types";

interface CameraHudProps {
  cameraName: string;
  cameraId: string;
  status: CameraStatus | null;
  streaming: boolean;
  alert: ZoneEvent | null;
}

function formatClock(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

function Corner({ className }: { className: string }) {
  return (
    <div
      aria-hidden="true"
      className={`pointer-events-none absolute h-7 w-7 border-cyan-400/70 ${className}`}
    />
  );
}

export default function CameraHud({
  cameraName,
  cameraId,
  status,
  streaming,
  alert,
}: CameraHudProps) {
  const [clock, setClock] = useState(formatClock);
  const [flash, setFlash] = useState(false);
  const flashTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const id = setInterval(() => setClock(formatClock()), 1000);
    return () => clearInterval(id);
  }, []);

  // Flash the alert banner briefly on every new zone_enter.
  useEffect(() => {
    if (!alert) return;
    setFlash(true);
    if (flashTimer.current) clearTimeout(flashTimer.current);
    flashTimer.current = setTimeout(() => setFlash(false), 4000);
    return () => {
      if (flashTimer.current) clearTimeout(flashTimer.current);
    };
  }, [alert]);

  const fw = status?.frame_width ?? 0;
  const fh = status?.frame_height ?? 0;
  const detections: Detection[] =
    fw > 0 && fh > 0 ? (status?.detections ?? []) : [];

  return (
    <div
      aria-label="Camera HUD overlay"
      className="pointer-events-none absolute inset-0 z-10 overflow-hidden font-mono select-none"
    >
      {/* scanlines + vignette */}
      <div
        aria-hidden="true"
        className="absolute inset-0 opacity-[0.14]"
        style={{
          backgroundImage:
            "repeating-linear-gradient(0deg, rgba(0,0,0,0.9) 0px, rgba(0,0,0,0.9) 1px, transparent 1px, transparent 3px)",
        }}
      />
      <div
        aria-hidden="true"
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.55) 100%)",
        }}
      />

      {/* corner brackets */}
      <Corner className="top-2 left-2 border-t-2 border-l-2" />
      <Corner className="top-2 right-2 border-t-2 border-r-2" />
      <Corner className="bottom-2 left-2 border-b-2 border-l-2" />
      <Corner className="right-2 bottom-2 border-r-2 border-b-2" />

      {/* top bar */}
      <div className="absolute inset-x-0 top-0 flex items-center justify-between px-9 pt-2.5 text-[11px] tracking-widest">
        <div className="flex items-center gap-2">
          <span
            className={`inline-block h-2 w-2 rounded-full ${
              streaming ? "animate-pulse bg-red-500" : "bg-slate-600"
            }`}
            aria-hidden="true"
          />
          <span className="text-red-400">
            {streaming ? "REC" : "OFFLINE"}
          </span>
          <span className="text-cyan-300/90">▸ {cameraName}</span>
        </div>
        <div className="flex items-center gap-3 text-slate-400">
          <span className="hidden sm:inline">{cameraId.slice(0, 8)}</span>
          <span className="text-slate-200 tabular-nums">{clock}</span>
        </div>
      </div>

      {/* detection boxes */}
      {detections.map((d, i) => {
        const [x1, y1, x2, y2] = d.bbox;
        const left = Math.max(0, (x1 / fw) * 100);
        const top = Math.max(0, (y1 / fh) * 100);
        const width = Math.min(100 - left, ((x2 - x1) / fw) * 100);
        const height = Math.min(100 - top, ((y2 - y1) / fh) * 100);
        const label =
          d.track_id !== null && d.track_id !== undefined
            ? `T${d.track_id}`
            : "PERSON";
        return (
          <div key={`${d.track_id ?? i}-${i}`}>
            <div
              aria-hidden="true"
              className="absolute border border-emerald-400/80"
              style={{ left: `${left}%`, top: `${top}%`, width: `${width}%`, height: `${height}%` }}
            />
            <div
              className="absolute bg-emerald-400/90 px-1 py-px text-[10px] leading-tight font-bold text-black"
              style={{ left: `${left}%`, top: `calc(${top}% - 16px)` }}
            >
              {label} {(d.confidence * 100).toFixed(0)}%
            </div>
          </div>
        );
      })}

      {/* intrusion alert banner */}
      {alert && flash && (
        <div
          role="alert"
          className="absolute inset-x-0 top-12 flex justify-center"
        >
          <div className="animate-pulse border border-red-500/80 bg-red-950/80 px-4 py-1.5 text-center text-xs font-bold tracking-[0.2em] text-red-300">
            ⚠ INTRUSION — {alert.zone_name.toUpperCase()} · TRACK{" "}
            {alert.tracking_id}
          </div>
        </div>
      )}

      {/* bottom telemetry strip */}
      <div className="absolute inset-x-0 bottom-0 flex items-center justify-between gap-2 bg-black/55 px-9 py-1.5 text-[10px] tracking-wider text-slate-300 backdrop-blur-[1px]">
        <span>
          PERSONS{" "}
          <span className="text-cyan-300">{status?.person_count ?? "—"}</span>
        </span>
        <span>
          FPS{" "}
          <span className="text-cyan-300">{status?.fps?.toFixed(1) ?? "—"}</span>
        </span>
        <span className="hidden sm:inline">
          INFER{" "}
          <span className="text-cyan-300">
            {status ? `${status.inference_ms.toFixed(0)}ms` : "—"}
          </span>
        </span>
        <span className="hidden md:inline">
          FRAME{" "}
          <span className="text-slate-200">{status?.frame_index ?? "—"}</span>
        </span>
        <span>
          ZONES{" "}
          <span
            className={
              (status?.active_zones ?? 0) > 0 ? "text-red-300" : "text-slate-400"
            }
          >
            {status?.active_zones ?? "—"}
          </span>
        </span>
        <span className="hidden lg:inline">
          TRACKS{" "}
          <span className="text-cyan-300">
            {status?.active_track_ids?.length
              ? status.active_track_ids.join(",")
              : "—"}
          </span>
        </span>
      </div>
    </div>
  );
}
