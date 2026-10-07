"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  createCamera,
  getCameraStatus,
  listCameras,
  startCamera,
  stopCamera,
  streamUrl,
} from "@/lib/api";
import type { Camera, CameraStatus } from "@/lib/types";

export default function CameraPanel() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [status, setStatus] = useState<CameraStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", source_url: "" });
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadCameras = useCallback(async () => {
    try {
      const list = await listCameras();
      setCameras(list);
      if (!selectedId && list.length > 0) setSelectedId(list[0].id);
      if (selectedId && !list.some((c) => c.id === selectedId)) {
        setSelectedId(list.length > 0 ? list[0].id : "");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load cameras");
    }
  }, [selectedId]);

  const refreshStatus = useCallback(async () => {
    if (!selectedId) return;
    try {
      const s = await getCameraStatus(selectedId);
      setStatus(s);
    } catch {
      /* keep last known status while polling */
    }
  }, [selectedId]);

  useEffect(() => {
    loadCameras();
  }, [loadCameras]);

  useEffect(() => {
    setStatus(null);
    refreshStatus();
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(refreshStatus, 2000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [selectedId, refreshStatus]);

  const streaming = status?.status === "streaming";

  async function handleStart() {
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    try {
      const s = await startCamera(selectedId);
      setStatus(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Start failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleStop() {
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    try {
      const s = await stopCamera(selectedId);
      setStatus(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Stop failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const cam = await createCamera(
        form.name || "Camera",
        "file",
        form.source_url,
      );
      setForm({ name: "", source_url: "" });
      setShowForm(false);
      await loadCameras();
      setSelectedId(cam.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mt-6 rounded-lg border border-cyan-500/15 bg-[#0a101b]/80 p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold tracking-widest text-slate-300 uppercase">
          Vision — Camera Feed
        </h2>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="text-xs text-cyan-300 border border-cyan-500/30 rounded px-2.5 py-1 hover:bg-cyan-500/10"
        >
          {showForm ? "Cancel" : "+ Add camera"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="mt-4 flex flex-wrap gap-2">
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Name (e.g. Gate Camera)"
            className="rounded border border-slate-700 bg-[#05080e] px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600"
          />
          <input
            value={form.source_url}
            onChange={(e) => setForm({ ...form, source_url: e.target.value })}
            placeholder="Video file path"
            required
            className="rounded border border-slate-700 bg-[#05080e] px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 flex-1 min-w-52"
          />
          <button
            type="submit"
            disabled={busy}
            className="rounded border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-200 hover:bg-cyan-500/20 disabled:opacity-50"
          >
            Add
          </button>
        </form>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <select
          value={selectedId}
          onChange={(e) => setSelectedId(e.target.value)}
          className="rounded border border-slate-700 bg-[#05080e] px-3 py-2 text-sm text-slate-200"
        >
          {cameras.length === 0 && <option value="">No cameras yet</option>}
          {cameras.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} ({c.source_type})
            </option>
          ))}
        </select>
        {selectedId && (
          <>
            <button
              onClick={handleStart}
              disabled={busy || streaming}
              className="rounded border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-200 hover:bg-emerald-500/20 disabled:opacity-50"
            >
              Start
            </button>
            <button
              onClick={handleStop}
              disabled={busy || !streaming}
              className="rounded border border-red-500/30 bg-red-500/10 px-4 py-2 text-sm text-red-200 hover:bg-red-500/20 disabled:opacity-50"
            >
              Stop
            </button>
          </>
        )}
      </div>

      {error && (
        <p className="mt-3 text-xs font-mono text-red-300 break-words">{error}</p>
      )}

      {selectedId && (
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          <div className="lg:col-span-2 rounded border border-slate-800 bg-black overflow-hidden">
            {streaming ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={streamUrl(selectedId)}
                alt="Camera stream"
                className="w-full h-auto block"
              />
            ) : (
              <div className="aspect-video flex items-center justify-center text-slate-600 text-sm">
                Stream offline — press Start
              </div>
            )}
          </div>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between border-b border-slate-800 pb-2">
              <span className="text-slate-500">Status</span>
              <span
                className={`font-mono uppercase ${
                  streaming ? "text-emerald-300" : "text-slate-400"
                }`}
              >
                {status?.status ?? "—"}
              </span>
            </div>
            <div className="flex justify-between border-b border-slate-800 pb-2">
              <span className="text-slate-500">Persons</span>
              <span className="font-mono text-cyan-200 text-lg">
                {status?.person_count ?? "—"}
              </span>
            </div>
            <div className="flex justify-between border-b border-slate-800 pb-2">
              <span className="text-slate-500">FPS</span>
              <span className="font-mono text-cyan-200">
                {status?.fps?.toFixed(1) ?? "—"}
              </span>
            </div>
            <div className="flex justify-between border-b border-slate-800 pb-2">
              <span className="text-slate-500">Inference</span>
              <span className="font-mono text-slate-300">
                {status ? `${status.inference_ms.toFixed(0)} ms` : "—"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Frame</span>
              <span className="font-mono text-slate-300">
                {status?.frame_index ?? "—"}
              </span>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
