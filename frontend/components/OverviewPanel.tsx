"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getCameraStatus,
  getDetailedHealth,
  listCameras,
  listIncidents,
} from "@/lib/api";
import type { DetailedHealth } from "@/lib/types";

interface Stats {
  cameras: number;
  streaming: number;
  people: number;
  zones: number;
  incidents24h: number;
  highCritical: number;
  health: DetailedHealth | null;
}

function StatCard({
  label,
  value,
  sub,
  alert,
}: {
  label: string;
  value: string;
  sub?: string;
  alert?: boolean;
}) {
  return (
    <div
      className={`rounded-lg border p-4 ${
        alert
          ? "border-red-500/30 bg-red-500/5"
          : "border-cyan-500/15 bg-[#0a101b]/80"
      }`}
    >
      <p className="text-[11px] tracking-widest text-slate-500 uppercase">{label}</p>
      <p
        className={`mt-1 font-mono text-2xl ${
          alert ? "text-red-300" : "text-cyan-100"
        }`}
      >
        {value}
      </p>
      {sub && <p className="mt-1 font-mono text-xs text-slate-500">{sub}</p>}
    </div>
  );
}

export default function OverviewPanel({ refreshKey }: { refreshKey: number }) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [cameras, health, recent, critical] = await Promise.all([
        listCameras(),
        getDetailedHealth(),
        listIncidents({ page: 1, page_size: 5 }),
        listIncidents({ page: 1, page_size: 1, severity: "CRITICAL" }),
      ]);
      const statuses = await Promise.all(
        cameras.map((c) =>
          getCameraStatus(c.id).catch(() => null),
        ),
      );
      const streaming = statuses.filter((s) => s?.status === "streaming").length;
      const people = statuses.reduce((n, s) => n + (s?.person_count ?? 0), 0);
      const zones = statuses.reduce((n, s) => n + (s?.active_zones ?? 0), 0);
      const high = await listIncidents({ page: 1, page_size: 1, severity: "HIGH" });
      setStats({
        cameras: cameras.length,
        streaming,
        people,
        zones,
        incidents24h: recent.total,
        highCritical: high.total + critical.total,
        health,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load overview");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  // Lightweight refresh cadence; paused when the tab is hidden.
  useEffect(() => {
    const id = setInterval(() => {
      if (!document.hidden) load();
    }, 15000);
    return () => clearInterval(id);
  }, [load]);

  if (loading && !stats) {
    return (
      <section className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-6" aria-busy="true">
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="h-24 animate-pulse rounded-lg border border-cyan-500/15 bg-[#0a101b]/80"
          />
        ))}
      </section>
    );
  }

  if (error && !stats) {
    return (
      <section className="mt-6 rounded-lg border border-red-500/30 bg-red-500/5 p-5">
        <p className="font-mono text-sm text-red-300">
          Backend unavailable. Retrying…{" "}
          <button onClick={load} className="underline">
            retry now
          </button>
        </p>
      </section>
    );
  }

  if (!stats) return null;

  const subsys = stats.health;
  const degraded =
    subsys &&
    (subsys.postgres?.status !== "up" || subsys.chromadb?.status === "error");

  return (
    <section aria-label="Overview">
      <div className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-6">
        <StatCard label="Cameras" value={String(stats.cameras)} sub={`${stats.streaming} streaming`} />
        <StatCard label="People detected" value={String(stats.people)} />
        <StatCard label="Active zones" value={String(stats.zones)} />
        <StatCard label="Incidents" value={String(stats.incidents24h)} sub="total recorded" />
        <StatCard
          label="High / Critical"
          value={String(stats.highCritical)}
          alert={stats.highCritical > 0}
        />
        <StatCard
          label="System"
          value={degraded ? "Degraded" : "Operational"}
          sub="see health below"
          alert={!!degraded}
        />
      </div>
    </section>
  );
}
