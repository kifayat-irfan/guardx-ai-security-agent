"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getIncidentDetail,
  listIncidents,
  reprocessIncident,
} from "@/lib/api";
import type { Incident, IncidentDetail } from "@/lib/types";

const SEVERITY_COLOR: Record<string, string> = {
  LOW: "text-emerald-300 border-emerald-500/30",
  MEDIUM: "text-amber-300 border-amber-500/30",
  HIGH: "text-orange-300 border-orange-500/30",
  CRITICAL: "text-red-300 border-red-500/30",
};

function short(id: string) {
  return id.slice(0, 8);
}

function fmt(ts: string) {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

export default function IncidentHistoryPanel() {
  const [items, setItems] = useState<Incident[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [statusF, setStatusF] = useState("");
  const [severityF, setSeverityF] = useState("");
  const [zoneF, setZoneF] = useState("");
  const [selected, setSelected] = useState<IncidentDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [reprocessing, setReprocessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await listIncidents({
        page,
        page_size: 10,
        status: statusF || undefined,
        severity: severityF || undefined,
        zone_name: zoneF || undefined,
      });
      setItems(r.items);
      setTotal(r.total);
      setTotalPages(r.total_pages);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load incidents");
    } finally {
      setLoading(false);
    }
  }, [page, statusF, severityF, zoneF]);

  useEffect(() => {
    load();
  }, [load]);

  async function open(id: string) {
    try {
      setSelected(await getIncidentDetail(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load incident");
    }
  }

  async function reprocess() {
    if (!selected) return;
    setReprocessing(true);
    try {
      await reprocessIncident(selected.incident.id);
      setSelected(await getIncidentDetail(selected.incident.id));
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reprocess failed");
    } finally {
      setReprocessing(false);
    }
  }

  const d = selected;

  return (
    <section className="mt-6 rounded-lg border border-cyan-500/15 bg-[#0a101b]/80 p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold tracking-widest text-slate-300 uppercase">
          Incident History · PostgreSQL
        </h2>
        <span className="font-mono text-xs text-slate-500">
          {total} incident{total === 1 ? "" : "s"}
        </span>
      </div>

      <div className="mt-4 flex flex-wrap gap-3">
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          Status
          <select
            value={statusF}
            onChange={(e) => {
              setStatusF(e.target.value);
              setPage(1);
            }}
            className="rounded border border-slate-700 bg-slate-900 px-2 py-1 font-mono text-slate-200"
          >
            <option value="">all</option>
            <option value="completed">completed</option>
            <option value="llm_unavailable">llm_unavailable</option>
            <option value="no_policies">no_policies</option>
            <option value="analysis_failed">analysis_failed</option>
            <option value="citation_invalid">citation_invalid</option>
            <option value="invalid_event">invalid_event</option>
            <option value="retrieval_failed">retrieval_failed</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          Severity
          <select
            value={severityF}
            onChange={(e) => {
              setSeverityF(e.target.value);
              setPage(1);
            }}
            className="rounded border border-slate-700 bg-slate-900 px-2 py-1 font-mono text-slate-200"
          >
            <option value="">all</option>
            <option value="LOW">LOW</option>
            <option value="MEDIUM">MEDIUM</option>
            <option value="HIGH">HIGH</option>
            <option value="CRITICAL">CRITICAL</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          Zone
          <input
            value={zoneF}
            onChange={(e) => {
              setZoneF(e.target.value);
              setPage(1);
            }}
            placeholder="server-room"
            className="rounded border border-slate-700 bg-slate-900 px-2 py-1 font-mono text-slate-200"
          />
        </label>
        <button
          onClick={load}
          className="self-end rounded border border-slate-700 px-3 py-1 font-mono text-xs text-slate-300 hover:bg-slate-800"
        >
          Refresh
        </button>
      </div>

      {error && <p className="mt-3 font-mono text-xs text-red-300">{error}</p>}

      <div className="mt-4 overflow-x-auto">
        <table className="w-full font-mono text-xs">
          <thead>
            <tr className="text-left text-slate-500">
              <th className="pb-2 pr-4">Time</th>
              <th className="pb-2 pr-4">Zone</th>
              <th className="pb-2 pr-4">Camera</th>
              <th className="pb-2 pr-4">Event</th>
              <th className="pb-2 pr-4">Severity</th>
              <th className="pb-2 pr-4">Status</th>
            </tr>
          </thead>
          <tbody>
            {items.map((i) => (
              <tr
                key={i.id}
                onClick={() => open(i.id)}
                className="cursor-pointer border-t border-slate-800 text-slate-300 hover:bg-slate-800/40"
              >
                <td className="py-2 pr-4 whitespace-nowrap">{fmt(i.occurred_at)}</td>
                <td className="py-2 pr-4">{i.zone_name}</td>
                <td className="py-2 pr-4 text-slate-500">{short(i.camera_id)}</td>
                <td className="py-2 pr-4">{i.event_type}</td>
                <td className="py-2 pr-4">
                  {i.severity ? (
                    <span
                      className={`rounded border px-1.5 py-0.5 ${SEVERITY_COLOR[i.severity] ?? ""}`}
                    >
                      {i.severity}
                    </span>
                  ) : (
                    <span className="text-slate-600">—</span>
                  )}
                </td>
                <td className="py-2 pr-4">
                  <span
                    className={`rounded border px-1.5 py-0.5 ${
                      i.status === "completed"
                        ? "border-emerald-500/30 text-emerald-300"
                        : "border-red-500/30 text-red-300"
                    }`}
                  >
                    {i.status}
                  </span>
                </td>
              </tr>
            ))}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={6} className="py-4 text-center text-slate-600">
                  No incidents yet — run the workflow above or wait for zone events.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-3 flex items-center gap-3 font-mono text-xs text-slate-500">
        <button
          disabled={page <= 1}
          onClick={() => setPage((p) => p - 1)}
          className="rounded border border-slate-700 px-2 py-0.5 disabled:opacity-40"
        >
          ← Prev
        </button>
        <span>
          page {page} / {totalPages}
        </span>
        <button
          disabled={page >= totalPages}
          onClick={() => setPage((p) => p + 1)}
          className="rounded border border-slate-700 px-2 py-0.5 disabled:opacity-40"
        >
          Next →
        </button>
      </div>

      {d && (
        <div className="mt-4 rounded border border-slate-700/60 p-4">
          <div className="flex items-center justify-between">
            <h3 className="font-mono text-sm text-slate-200">
              {d.report?.title ?? `Incident ${short(d.incident.id)}`}
            </h3>
            <div className="flex gap-2">
              <button
                onClick={reprocess}
                disabled={reprocessing}
                className="rounded border border-cyan-500/40 bg-cyan-500/10 px-3 py-1 font-mono text-xs text-cyan-200 hover:bg-cyan-500/20 disabled:opacity-50"
              >
                {reprocessing ? "Reprocessing…" : "Reprocess"}
              </button>
              <button
                onClick={() => setSelected(null)}
                className="rounded border border-slate-700 px-3 py-1 font-mono text-xs text-slate-400"
              >
                Close
              </button>
            </div>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="text-sm">
              {d.incident.summary && (
                <p className="text-slate-200">{d.incident.summary}</p>
              )}
              {d.incident.recommended_action && (
                <p className="mt-2 text-slate-400">
                  <span className="text-slate-500">Action: </span>
                  {d.incident.recommended_action}
                </p>
              )}
              {d.report?.reasoning && (
                <p className="mt-2 text-slate-400">
                  <span className="text-slate-500">Reasoning: </span>
                  {d.report.reasoning}
                </p>
              )}
              {d.incident.error && (
                <p className="mt-2 font-mono text-xs text-red-300">
                  {d.incident.error.node}: {d.incident.error.message}
                </p>
              )}
              <p className="mt-3 font-mono text-xs text-slate-500">
                event {d.incident.event_type} · track {d.incident.tracking_id} ·
                conf {d.incident.detection_confidence.toFixed(2)} ·{" "}
                {fmt(d.incident.occurred_at)}
              </p>
            </div>
            <div className="font-mono text-xs">
              <p className="text-slate-500">
                cited{" "}
                <span className="text-cyan-200">
                  {d.report?.cited_policy_chunk_ids.join(", ") || "—"}
                </span>
              </p>
              <p className="mt-1 text-slate-500">
                retrieved ({d.report?.retrieved_policy_count ?? 0}){" "}
                <span className="text-slate-300">
                  {d.report?.retrieved_chunk_ids.join(", ") || "—"}
                </span>
              </p>
              <p className="mt-1 text-slate-500">
                workflow{" "}
                <span className="text-slate-300">
                  {short(d.incident.workflow_id)}
                </span>
              </p>
              <p className="mt-1 text-slate-500">
                report{" "}
                <span className="text-slate-300">
                  {d.report ? fmt(d.report.generated_at) : "none (workflow failed)"}
                </span>
              </p>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
