"use client";

import { useCallback, useEffect, useState } from "react";
import Sidebar from "@/components/Sidebar";
import CameraPanel from "@/components/CameraPanel";
import HealthPanel from "@/components/HealthPanel";
import IncidentHistoryPanel from "@/components/IncidentHistoryPanel";
import IncidentPanel from "@/components/IncidentPanel";
import LiveFeedPanel from "@/components/LiveFeedPanel";
import OverviewPanel from "@/components/OverviewPanel";
import PolicyPanel from "@/components/PolicyPanel";
import { API_URL, getDetailedHealth } from "@/lib/api";

function useClock() {
  const [now, setNow] = useState("--:--:--");
  useEffect(() => {
    const tick = () => setNow(new Date().toLocaleTimeString());
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);
  return now;
}

export default function Dashboard() {
  const [backendUp, setBackendUp] = useState<boolean | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const now = useClock();

  const checkBackend = useCallback(async () => {
    try {
      await getDetailedHealth();
      setBackendUp(true);
    } catch {
      setBackendUp(false);
    }
  }, []);

  useEffect(() => {
    checkBackend();
  }, [checkBackend]);

  return (
    <div className="flex min-h-screen bg-[#05080e] text-slate-200">
      <Sidebar />
      <main className="mx-auto w-full max-w-[1440px] flex-1 p-4 md:p-8">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold tracking-wide text-cyan-50">
              Security Operations
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              GuardX command dashboard ·{" "}
              <span className="font-mono text-cyan-400">{API_URL}</span>
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span
              className="font-mono text-sm text-slate-400"
              aria-label="Current time"
            >
              {now}
            </span>
            <span
              className={`rounded border px-2 py-0.5 font-mono text-xs ${
                backendUp === null
                  ? "border-slate-600 text-slate-400"
                  : backendUp
                    ? "border-emerald-500/30 text-emerald-300"
                    : "border-red-500/30 text-red-300"
              }`}
              role="status"
            >
              {backendUp === null
                ? "checking…"
                : backendUp
                  ? "● backend connected"
                  : "● backend unreachable"}
            </span>
            <button
              onClick={() => {
                checkBackend();
                setRefreshKey((k) => k + 1);
              }}
              className="rounded-md border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-sm font-medium tracking-wide text-cyan-200 transition-colors hover:bg-cyan-500/20"
            >
              Refresh
            </button>
          </div>
        </header>

        {backendUp === false && (
          <p className="mt-4 rounded border border-red-500/30 bg-red-500/5 p-3 font-mono text-sm text-red-300" role="alert">
            Backend unavailable. Retrying… start the FastAPI backend and press
            Refresh.
          </p>
        )}

        <div id="overview" className="scroll-mt-4">
          <OverviewPanel refreshKey={refreshKey} />
        </div>

        <div id="live" className="scroll-mt-4">
          <LiveFeedPanel />
        </div>

        <div id="cameras" className="scroll-mt-4">
          <CameraPanel />
        </div>

        <div id="policies" className="scroll-mt-4">
          <PolicyPanel />
        </div>

        <div id="incidents" className="scroll-mt-4">
          <IncidentHistoryPanel />
        </div>

        <div id="workflow" className="scroll-mt-4">
          <IncidentPanel />
        </div>

        <HealthPanel />

        <footer className="mt-8 pb-4 text-center font-mono text-[11px] text-slate-600">
          GuardX · AI Autonomous Security Agent · Phase 8 operations dashboard
        </footer>
      </main>
    </div>
  );
}
