"use client";

import { useCallback, useEffect, useState } from "react";
import Sidebar from "@/components/Sidebar";
import StatusCard from "@/components/StatusCard";
import { API_URL, getDetailedHealth } from "@/lib/api";
import type { DetailedHealth } from "@/lib/types";

export default function Dashboard() {
  const [health, setHealth] = useState<DetailedHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<string>("—");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getDetailedHealth();
      setHealth(data);
      setLastChecked(new Date().toLocaleTimeString());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
      setHealth(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const overallUp = health?.status === "ok";

  return (
    <div className="flex min-h-screen bg-[#05080e] text-slate-200">
      <Sidebar />
      <main className="flex-1 p-8">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-wide text-cyan-50">
              System Status
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              GuardX foundation health · backend{" "}
              <span className="font-mono text-cyan-400">{API_URL}</span>
            </p>
          </div>
          <button
            onClick={refresh}
            disabled={loading}
            className="rounded-md border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-sm font-medium tracking-wide text-cyan-200 hover:bg-cyan-500/20 disabled:opacity-50 transition-colors"
          >
            {loading ? "Checking…" : "Refresh"}
          </button>
        </header>

        <div className="mt-6 flex items-center gap-3 rounded-lg border border-cyan-500/15 bg-[#0a101b]/80 px-5 py-4">
          <span
            className={`inline-block h-3 w-3 rounded-full ${
              error
                ? "bg-red-400 shadow-[0_0_12px_#f87171]"
                : overallUp
                  ? "bg-emerald-400 shadow-[0_0_12px_#34d399]"
                  : "bg-amber-400 shadow-[0_0_12px_#fbbf24]"
            }`}
          />
          <p className="text-sm">
            {error ? (
              <span className="text-red-300">
                Backend unreachable: <span className="font-mono">{error}</span>
              </span>
            ) : (
              <span className="text-slate-300">
                Overall:{" "}
                <span className="font-mono uppercase tracking-wider text-cyan-200">
                  {health?.status ?? "…"}
                </span>{" "}
                <span className="text-slate-500">
                  · backend v{health?.version ?? "…"} · checked {lastChecked}
                </span>
              </span>
            )}
          </p>
        </div>

        <section className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatusCard
            title="PostgreSQL"
            subtitle="System of record"
            component={health?.postgres ?? null}
            loading={loading}
          />
          <StatusCard
            title="ChromaDB"
            subtitle="Policy vector store (Phase 4)"
            component={health?.chromadb ?? null}
            loading={loading}
          />
          <StatusCard
            title="YOLO Vision"
            subtitle="Person detection (Phase 2)"
            component={health?.yolo ?? null}
            loading={loading}
          />
          <StatusCard
            title="LangGraph"
            subtitle="Incident workflow (Phase 6)"
            component={
              health
                ? {
                    status: "down",
                    detail: "workflow not wired yet (Phase 6)",
                  }
                : null
            }
            loading={loading}
          />
        </section>

        <section className="mt-6 rounded-lg border border-cyan-500/15 bg-[#0a101b]/80 p-5">
          <h2 className="text-sm font-semibold tracking-widest text-slate-300 uppercase">
            Pipeline
          </h2>
          <p className="mt-3 font-mono text-xs leading-6 text-slate-500">
            camera → yolo → zone engine → incident → langgraph → rag → reason →
            report → dashboard → n8n
          </p>
          <p className="mt-2 text-xs text-slate-600">
            Phase 1 delivers the foundation: API, database, dashboard shell.
            Detection starts in Phase 2.
          </p>
        </section>
      </main>
    </div>
  );
}
