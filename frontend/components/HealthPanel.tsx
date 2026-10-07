"use client";

import { useCallback, useEffect, useState } from "react";
import { getDetailedHealth } from "@/lib/api";
import type { ComponentStatus, DetailedHealth } from "@/lib/types";

const STATUS_STYLE: Record<string, string> = {
  up: "border-emerald-500/30 text-emerald-300",
  ok: "border-emerald-500/30 text-emerald-300",
  ready: "border-emerald-500/30 text-emerald-300",
  configured: "border-amber-500/30 text-amber-300",
  degraded: "border-amber-500/30 text-amber-300",
  initializing: "border-amber-500/30 text-amber-300",
  unavailable: "border-slate-600 text-slate-400",
  down: "border-red-500/30 text-red-300",
  error: "border-red-500/30 text-red-300",
};

function Row({
  name,
  sub,
  component,
}: {
  name: string;
  sub: string;
  component: ComponentStatus | null | undefined;
}) {
  const status = component?.status ?? "unavailable";
  const cls = STATUS_STYLE[status] ?? STATUS_STYLE.unavailable;
  return (
    <div className="flex items-center justify-between gap-3 border-t border-slate-800 py-2.5 first:border-t-0 first:pt-0 last:pb-0">
      <div>
        <p className="text-sm text-slate-200">{name}</p>
        <p className="font-mono text-[11px] text-slate-500">{sub}</p>
        {component?.detail && (
          <p className="mt-0.5 font-mono text-[11px] text-slate-500">
            {component.detail}
          </p>
        )}
      </div>
      <span
        className={`shrink-0 rounded border px-2 py-0.5 font-mono text-xs uppercase ${cls}`}
      >
        {status}
      </span>
    </div>
  );
}

export default function HealthPanel() {
  const [health, setHealth] = useState<DetailedHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setHealth(await getDetailedHealth());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Health check failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <section
      id="system"
      className="mt-6 rounded-lg border border-cyan-500/15 bg-[#0a101b]/80 p-5"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold tracking-widest text-slate-300 uppercase">
          System Health
        </h2>
        <button
          onClick={load}
          className="rounded border border-slate-700 px-3 py-1 font-mono text-xs text-slate-300 hover:bg-slate-800"
        >
          Refresh
        </button>
      </div>

      {loading && !health && (
        <p className="mt-3 font-mono text-xs text-slate-500" aria-busy="true">
          Checking subsystems…
        </p>
      )}
      {error && !health && (
        <p className="mt-3 font-mono text-xs text-red-300">
          Backend unavailable.{" "}
          <button onClick={load} className="underline">
            Retry
          </button>
        </p>
      )}
      {health && (
        <div className="mt-3">
          <Row name="Backend" sub="FastAPI" component={{ status: health.status === "ok" ? "up" : "degraded", detail: `v${health.version}` }} />
          <Row name="PostgreSQL" sub="incidents + reports" component={health.postgres} />
          <Row name="Incident store" sub="migrations + tables" component={health.postgres_incidents} />
          <Row name="ChromaDB / RAG" sub="policy vector index" component={health.chromadb} />
          <Row name="LangChain" sub="retriever + policy tool" component={health.langchain} />
          <Row name="LangGraph" sub="incident workflow" component={health.langgraph} />
          <Row name="YOLO vision" sub="person detection" component={health.yolo} />
          <Row
            name="n8n"
            sub="notifications (Phase 9)"
            component={{ status: "unavailable", detail: "not configured" }}
          />
        </div>
      )}
    </section>
  );
}
