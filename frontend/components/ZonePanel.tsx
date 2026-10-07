"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createZone,
  deleteZone,
  listZones,
  updateZone,
  type ZoneInput,
} from "@/lib/api";
import type { Zone, ZoneEvent } from "@/lib/types";

const DEFAULT_POLYGON = `[
  [0.10, 0.20],
  [0.80, 0.20],
  [0.80, 0.80],
  [0.10, 0.80]
]`;

export default function ZonePanel({
  cameraId,
  events,
  activeTrackIds,
}: {
  cameraId: string;
  events: ZoneEvent[];
  activeTrackIds: number[];
}) {
  const [zones, setZones] = useState<Zone[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    polygon: DEFAULT_POLYGON,
    dwell_seconds: "2",
    cooldown_seconds: "60",
  });

  const load = useCallback(async () => {
    if (!cameraId) return;
    try {
      setZones(await listZones(cameraId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load zones");
    }
  }, [cameraId]);

  useEffect(() => {
    load();
  }, [load]);

  function parsePolygon(): ZoneInput["polygon"] {
    const raw = JSON.parse(form.polygon);
    if (!Array.isArray(raw) || raw.length < 3) {
      throw new Error("Polygon needs at least 3 points");
    }
    return raw;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const polygon = parsePolygon();
      const body = {
        name: form.name || "Restricted zone",
        polygon,
        dwell_seconds: parseFloat(form.dwell_seconds) || 0,
        cooldown_seconds: parseFloat(form.cooldown_seconds) || 0,
      };
      if (editingId) {
        await updateZone(editingId, body);
      } else {
        await createZone({ camera_id: cameraId, ...body });
      }
      setForm({
        name: "",
        polygon: DEFAULT_POLYGON,
        dwell_seconds: "2",
        cooldown_seconds: "60",
      });
      setEditingId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  function startEdit(z: Zone) {
    setEditingId(z.id);
    setForm({
      name: z.name,
      polygon: JSON.stringify(z.polygon, null, 2),
      dwell_seconds: String(z.dwell_seconds),
      cooldown_seconds: String(z.cooldown_seconds),
    });
  }

  async function toggleActive(z: Zone) {
    setError(null);
    try {
      await updateZone(z.id, { active: !z.active });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Toggle failed");
    }
  }

  async function handleDelete(id: string) {
    setError(null);
    try {
      await deleteZone(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  const latestEnter = events.find((e) => e.event_type === "zone_enter");

  return (
    <section className="mt-6 rounded-lg border border-red-500/20 bg-[#0a101b]/80 p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold tracking-widest text-slate-300 uppercase">
          Restricted Zones
        </h2>
        <span className="text-xs text-slate-500">
          {zones.filter((z) => z.active).length} active · polygons drawn on the
          live feed
        </span>
      </div>

      {error && (
        <p className="mt-3 text-xs text-red-400">{error}</p>
      )}

      {/* zone list */}
      <div className="mt-4 space-y-2">
        {zones.length === 0 && (
          <p className="text-xs text-slate-500">
            No zones yet — draw one with the form below. Coordinates are
            normalized 0–1 (x right, y down).
          </p>
        )}
        {zones.map((z) => (
          <div
            key={z.id}
            className="flex items-center gap-3 rounded border border-slate-800 bg-[#05080e] px-3 py-2"
          >
            <button
              onClick={() => toggleActive(z)}
              title={z.active ? "Disable" : "Enable"}
              className={`h-3 w-3 rounded-full ${
                z.active ? "bg-red-500 shadow-[0_0_8px_#ef4444]" : "bg-slate-700"
              }`}
            />
            <div className="flex-1 min-w-0">
              <p className="text-sm text-slate-200 truncate">{z.name}</p>
              <p className="text-[11px] text-slate-500">
                {z.polygon.length} pts · dwell {z.dwell_seconds}s · cooldown{" "}
                {z.cooldown_seconds}s ·{" "}
                {z.active ? "enabled" : "disabled"}
              </p>
            </div>
            <button
              onClick={() => startEdit(z)}
              className="text-xs text-cyan-300 border border-cyan-500/30 rounded px-2 py-1 hover:bg-cyan-500/10"
            >
              Edit
            </button>
            <button
              onClick={() => handleDelete(z.id)}
              className="text-xs text-red-300 border border-red-500/30 rounded px-2 py-1 hover:bg-red-500/10"
            >
              Delete
            </button>
          </div>
        ))}
      </div>

      {/* create / edit form */}
      <form onSubmit={handleSubmit} className="mt-4 rounded border border-slate-800 p-3">
        <p className="text-xs font-semibold tracking-widest text-slate-400 uppercase mb-2">
          {editingId ? "Edit zone" : "New zone"}
        </p>
        <div className="grid gap-2 md:grid-cols-2">
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Zone name (e.g. Server room door)"
            className="rounded border border-slate-700 bg-[#05080e] px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600"
          />
          <div className="flex gap-2">
            <label className="flex items-center gap-1 text-xs text-slate-400">
              Dwell
              <input
                value={form.dwell_seconds}
                onChange={(e) => setForm({ ...form, dwell_seconds: e.target.value })}
                className="w-16 rounded border border-slate-700 bg-[#05080e] px-2 py-2 text-sm text-slate-200"
              />
              s
            </label>
            <label className="flex items-center gap-1 text-xs text-slate-400">
              Cooldown
              <input
                value={form.cooldown_seconds}
                onChange={(e) => setForm({ ...form, cooldown_seconds: e.target.value })}
                className="w-16 rounded border border-slate-700 bg-[#05080e] px-2 py-2 text-sm text-slate-200"
              />
              s
            </label>
          </div>
        </div>
        <textarea
          value={form.polygon}
          onChange={(e) => setForm({ ...form, polygon: e.target.value })}
          rows={5}
          spellCheck={false}
          className="mt-2 w-full rounded border border-slate-700 bg-[#05080e] px-3 py-2 font-mono text-xs text-slate-200"
        />
        <div className="mt-2 flex gap-2">
          <button
            type="submit"
            disabled={busy}
            className="text-xs text-red-200 border border-red-500/40 rounded px-3 py-1.5 hover:bg-red-500/10 disabled:opacity-50"
          >
            {busy ? "Saving…" : editingId ? "Save changes" : "Create zone"}
          </button>
          {editingId && (
            <button
              type="button"
              onClick={() => {
                setEditingId(null);
                setForm({
                  name: "",
                  polygon: DEFAULT_POLYGON,
                  dwell_seconds: "2",
                  cooldown_seconds: "60",
                });
              }}
              className="text-xs text-slate-400 border border-slate-700 rounded px-3 py-1.5 hover:bg-slate-800"
            >
              Cancel
            </button>
          )}
        </div>
      </form>

      {/* live zone events */}
      <div className="mt-4">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold tracking-widest text-slate-400 uppercase">
            Zone events
          </p>
          <p className="text-[11px] text-slate-500">
            tracks: {activeTrackIds.length > 0 ? activeTrackIds.join(", ") : "—"}
          </p>
        </div>
        {latestEnter && (
          <div className="mt-2 rounded border border-red-500/50 bg-red-500/10 px-3 py-2">
            <p className="text-sm text-red-300 font-semibold">
              ⚠ PERSON IN RESTRICTED ZONE — {latestEnter.zone_name} (track{" "}
              {latestEnter.tracking_id})
            </p>
          </div>
        )}
        <div className="mt-2 max-h-48 overflow-y-auto space-y-1">
          {events.length === 0 && (
            <p className="text-xs text-slate-600">No zone events yet.</p>
          )}
          {events
            .slice()
            .reverse()
            .map((e) => (
              <div
                key={e.event_id}
                className="flex items-center gap-2 rounded border border-slate-800 bg-[#05080e] px-3 py-1.5 text-xs"
              >
                <span
                  className={`rounded px-1.5 py-0.5 font-semibold ${
                    e.event_type === "zone_enter"
                      ? "bg-red-500/20 text-red-300"
                      : "bg-emerald-500/20 text-emerald-300"
                  }`}
                >
                  {e.event_type === "zone_enter" ? "ENTER" : "EXIT"}
                </span>
                <span className="text-slate-300">{e.zone_name}</span>
                <span className="text-slate-500">track {e.tracking_id}</span>
                <span className="text-slate-600 ml-auto">
                  t={e.timestamp.toFixed(1)}s
                </span>
              </div>
            ))}
        </div>
      </div>
    </section>
  );
}
