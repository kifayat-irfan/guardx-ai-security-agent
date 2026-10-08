"use client";

import { useEffect, useState } from "react";
import { analyzeIncident, getLangChainStatus, getWorkflow } from "@/lib/api";
import type { IncidentDecision, WorkflowState } from "@/lib/types";

function randomId() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

const SEVERITY_COLOR: Record<string, string> = {
  LOW: "text-emerald-300 border-emerald-500/30",
  MEDIUM: "text-amber-300 border-amber-500/30",
  HIGH: "text-orange-300 border-orange-500/30",
  CRITICAL: "text-red-300 border-red-500/30",
};

export default function IncidentPanel() {
  const [zoneName, setZoneName] = useState("server-room");
  const [eventType, setEventType] = useState("zone_enter");
  const [trackingId, setTrackingId] = useState(2);
  const [confidence, setConfidence] = useState(0.87);
  const [running, setRunning] = useState(false);
  const [decision, setDecision] = useState<IncidentDecision | null>(null);
  const [workflow, setWorkflow] = useState<WorkflowState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [aiProvider, setAiProvider] = useState<string | null>(null);

  useEffect(() => {
    getLangChainStatus()
      .then((st) => setAiProvider(st.llm_provider ?? null))
      .catch(() => setAiProvider(null));
  }, []);

  async function run() {
    setRunning(true);
    setError(null);
    setDecision(null);
    setWorkflow(null);
    try {
      const event = {
        event_id: randomId(),
        camera_id: randomId(),
        zone_id: randomId(),
        zone_name: zoneName.trim() || "server-room",
        tracking_id: trackingId,
        event_type: eventType,
        timestamp: 0,
        confidence,
        bounding_box: [0.4, 0.5, 0.6, 0.9],
        point: [0.5, 0.9],
        metadata: { source: "dashboard-demo" },
      };
      const d = await analyzeIncident(event);
      setDecision(d);
      const w = await getWorkflow(d.workflow_id);
      setWorkflow(w);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Workflow request failed");
    } finally {
      setRunning(false);
    }
  }

  const failed = decision && decision.status !== "completed";
  const llmDown = decision?.status === "llm_unavailable";

  return (
    <section className="mt-6 rounded-lg border border-cyan-500/15 bg-[#0a101b]/80 p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold tracking-widest text-slate-300 uppercase">
          Incident Workflow · LangGraph
        </h2>
        <span className="font-mono text-xs text-slate-500">
          validate → query → retrieve → analyze → validate → decide
        </span>
        {aiProvider && (
          <span className="rounded border border-cyan-500/30 bg-cyan-500/10 px-2 py-0.5 font-mono text-[11px] uppercase tracking-wider text-cyan-200">
            AI provider: {aiProvider}
          </span>
        )}
      </div>

      <div className="mt-4 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          Zone
          <input
            value={zoneName}
            onChange={(e) => setZoneName(e.target.value)}
            className="rounded border border-slate-700 bg-slate-900 px-2 py-1 font-mono text-slate-200"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          Event type
          <select
            value={eventType}
            onChange={(e) => setEventType(e.target.value)}
            className="rounded border border-slate-700 bg-slate-900 px-2 py-1 font-mono text-slate-200"
          >
            <option value="zone_enter">zone_enter</option>
            <option value="zone_exit">zone_exit</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          Track ID
          <input
            type="number"
            value={trackingId}
            onChange={(e) => setTrackingId(Number(e.target.value))}
            className="w-24 rounded border border-slate-700 bg-slate-900 px-2 py-1 font-mono text-slate-200"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          Confidence
          <input
            type="number"
            step="0.01"
            min="0"
            max="1"
            value={confidence}
            onChange={(e) => setConfidence(Number(e.target.value))}
            className="w-24 rounded border border-slate-700 bg-slate-900 px-2 py-1 font-mono text-slate-200"
          />
        </label>
        <button
          onClick={run}
          disabled={running}
          className="rounded border border-cyan-500/40 bg-cyan-500/10 px-4 py-1.5 font-mono text-sm text-cyan-200 hover:bg-cyan-500/20 disabled:opacity-50"
        >
          {running ? "Running…" : "Run workflow"}
        </button>
      </div>

      {error && <p className="mt-3 font-mono text-xs text-red-300">{error}</p>}

      {llmDown && (
        <p className="mt-3 rounded border border-amber-500/30 bg-amber-500/10 px-3 py-2 font-mono text-xs text-amber-200">
          AI analysis unavailable — no local LLM reachable. Retrieval ran; the
          workflow refused to fabricate an analysis.
        </p>
      )}

      {decision && (
        <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="rounded border border-slate-700/60 p-4">
            <p className="font-mono text-xs text-slate-500">
              workflow <span className="text-slate-300">{decision.workflow_id}</span>
            </p>
            <div className="mt-2 flex items-center gap-2">
              <span
                className={`rounded border px-2 py-0.5 font-mono text-xs uppercase ${
                  failed
                    ? "border-red-500/30 text-red-300"
                    : "border-emerald-500/30 text-emerald-300"
                }`}
              >
                {decision.status}
              </span>
              {decision.severity && (
                <span
                  className={`rounded border px-2 py-0.5 font-mono text-xs ${SEVERITY_COLOR[decision.severity] ?? ""}`}
                >
                  {decision.severity}
                </span>
              )}
              <span className="font-mono text-xs text-slate-500">
                {decision.duration_ms} ms · {decision.retrieved_policy_count}{" "}
                policies
              </span>
            </div>
            {decision.summary && (
              <p className="mt-3 text-sm text-slate-200">{decision.summary}</p>
            )}
            {decision.recommended_action && (
              <p className="mt-2 text-sm text-slate-400">
                <span className="text-slate-500">Action: </span>
                {decision.recommended_action}
              </p>
            )}
            {decision.confidence !== null && (
              <p className="mt-1 font-mono text-xs text-slate-500">
                confidence {decision.confidence.toFixed(2)}
              </p>
            )}
            {decision.error && (
              <p className="mt-2 font-mono text-xs text-red-300">
                {decision.error.node}: {decision.error.message}
              </p>
            )}
          </div>
          <div className="rounded border border-slate-700/60 p-4 font-mono text-xs">
            <p className="text-slate-500">
              node trace{" "}
              <span className="text-slate-300">
                {workflow
                  ? Object.entries(workflow.timings_ms)
                      .map(([n, ms]) => `${n} ${ms}ms`)
                      .join(" · ")
                  : "…"}
              </span>
            </p>
            <p className="mt-2 text-slate-500">
              cited chunk IDs{" "}
              <span className="text-cyan-200">
                {decision.cited_policy_chunk_ids.join(", ") || "—"}
              </span>
            </p>
            <p className="mt-1 text-slate-500">
              retrieved{" "}
              <span className="text-slate-300">
                {workflow?.retrieved_chunk_ids.join(", ") || "—"}
              </span>
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
