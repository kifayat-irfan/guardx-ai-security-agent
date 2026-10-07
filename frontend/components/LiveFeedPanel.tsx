"use client";

import { useCallback, useRef, useState } from "react";
import { analyzeIncident } from "@/lib/api";
import { useEventStream } from "@/lib/useEventStream";
import type { StreamMessage } from "@/lib/eventStream";

interface ZoneEventItem {
  event_id: string;
  event_type: string;
  zone_name: string;
  camera_id: string;
  tracking_id: number;
  confidence: number;
  timestamp: number;
  received_at: number;
  analyzed?: boolean;
}

interface IncidentItem {
  incident_id: string;
  status: string;
  severity: string | null;
  zone_name: string;
  summary: string | null;
  reprocessed: boolean;
  received_at: number;
}

const MAX_ITEMS = 30;

const CONN_LABEL: Record<string, { text: string; cls: string }> = {
  connecting: { text: "connecting…", cls: "text-amber-300 border-amber-500/30" },
  open: { text: "live", cls: "text-emerald-300 border-emerald-500/30" },
  closed: { text: "disconnected", cls: "text-slate-400 border-slate-600" },
  error: { text: "reconnecting…", cls: "text-amber-300 border-amber-500/30" },
};

export default function LiveFeedPanel() {
  const [events, setEvents] = useState<ZoneEventItem[]>([]);
  const [incidents, setIncidents] = useState<IncidentItem[]>([]);
  const [autoAnalyze, setAutoAnalyze] = useState(true);
  const [analyzing, setAnalyzing] = useState(0);
  const analyzedRef = useRef<Set<string>>(new Set());
  const autoRef = useRef(autoAnalyze);
  autoRef.current = autoAnalyze;

  const onMessage = useCallback((msg: StreamMessage) => {
    if (msg.type === "zone_event") {
      const d = msg.data as Record<string, unknown>;
      const item: ZoneEventItem = {
        event_id: String(d.event_id ?? ""),
        event_type: String(d.event_type ?? ""),
        zone_name: String(d.zone_name ?? ""),
        camera_id: String(d.camera_id ?? ""),
        tracking_id: Number(d.tracking_id ?? 0),
        confidence: Number(d.confidence ?? 0),
        timestamp: Number(d.timestamp ?? 0),
        received_at: Date.now(),
      };
      setEvents((prev) => [item, ...prev].slice(0, MAX_ITEMS));

      // Demo flow: ENTER → automatic incident analysis (deduped).
      if (
        autoRef.current &&
        item.event_type === "zone_enter" &&
        item.event_id &&
        !analyzedRef.current.has(item.event_id)
      ) {
        analyzedRef.current.add(item.event_id);
        setAnalyzing((n) => n + 1);
        analyzeIncident(d as Record<string, unknown>)
          .catch(() => {
            /* failure surfaces via the incident SSE event / history */
          })
          .finally(() => setAnalyzing((n) => Math.max(0, n - 1)));
      }
    } else if (msg.type === "incident") {
      const d = msg.data as Record<string, unknown>;
      const item: IncidentItem = {
        incident_id: String(d.incident_id ?? ""),
        status: String(d.status ?? ""),
        severity: (d.severity as string) ?? null,
        zone_name: String(d.zone_name ?? ""),
        summary: (d.summary as string) ?? null,
        reprocessed: Boolean(d.reprocessed),
        received_at: Date.now(),
      };
      setIncidents((prev) => [item, ...prev].slice(0, MAX_ITEMS));
    }
  }, []);

  const conn = useEventStream(onMessage);
  const connInfo = CONN_LABEL[conn];

  return (
    <section className="mt-6 rounded-lg border border-cyan-500/15 bg-[#0a101b]/80 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-semibold tracking-widest text-slate-300 uppercase">
          Live Event Stream
        </h2>
        <div className="flex items-center gap-3">
          <label className="flex cursor-pointer items-center gap-2 text-xs text-slate-400">
            <input
              type="checkbox"
              checked={autoAnalyze}
              onChange={(e) => setAutoAnalyze(e.target.checked)}
              className="h-3.5 w-3.5 accent-cyan-500"
              aria-label="Auto-analyze zone entries"
            />
            Auto-analyze zone entries
          </label>
          {analyzing > 0 && (
            <span className="font-mono text-xs text-cyan-300">
              analyzing… ({analyzing})
            </span>
          )}
          <span
            className={`rounded border px-2 py-0.5 font-mono text-xs ${connInfo.cls}`}
            role="status"
            aria-label={`Stream ${connInfo.text}`}
          >
            ● {connInfo.text}
          </span>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div>
          <h3 className="font-mono text-xs tracking-wider text-slate-500 uppercase">
            Zone events
          </h3>
          <ul className="mt-2 max-h-72 space-y-2 overflow-y-auto" aria-live="polite">
            {events.length === 0 && (
              <li className="font-mono text-xs text-slate-600">
                No zone events yet — start a camera and enter a restricted zone.
              </li>
            )}
            {events.map((e) => (
              <li
                key={e.event_id || e.received_at}
                className={`rounded border px-3 py-2 font-mono text-xs ${
                  e.event_type === "zone_enter"
                    ? "border-orange-500/40 bg-orange-500/5"
                    : "border-slate-700/60"
                }`}
              >
                <span
                  className={`mr-2 rounded px-1.5 py-0.5 text-[10px] font-bold tracking-wider ${
                    e.event_type === "zone_enter"
                      ? "bg-orange-500/20 text-orange-300"
                      : "bg-slate-700/40 text-slate-400"
                  }`}
                >
                  {e.event_type === "zone_enter" ? "ENTER" : "EXIT"}
                </span>
                <span className="text-slate-200">{e.zone_name}</span>
                <span className="text-slate-500">
                  {" "}
                  · track {e.tracking_id} · conf {e.confidence.toFixed(2)}
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="font-mono text-xs tracking-wider text-slate-500 uppercase">
            Incidents (live)
          </h3>
          <ul className="mt-2 max-h-72 space-y-2 overflow-y-auto" aria-live="polite">
            {incidents.length === 0 && (
              <li className="font-mono text-xs text-slate-600">
                No incidents yet — they appear here the moment analysis completes.
              </li>
            )}
            {incidents.map((i) => (
              <li
                key={i.incident_id || i.received_at}
                className="rounded border border-slate-700/60 px-3 py-2 font-mono text-xs"
              >
                <span
                  className={`mr-2 rounded border px-1.5 py-0.5 text-[10px] ${
                    i.status === "completed"
                      ? "border-emerald-500/30 text-emerald-300"
                      : "border-red-500/30 text-red-300"
                  }`}
                >
                  {i.status}
                </span>
                {i.severity && (
                  <span className="mr-2 text-slate-200">{i.severity}</span>
                )}
                <span className="text-slate-400">{i.zone_name}</span>
                {i.reprocessed && (
                  <span className="ml-2 text-slate-600">(reprocessed)</span>
                )}
                {i.summary && (
                  <p className="mt-1 text-slate-500">{i.summary}</p>
                )}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
