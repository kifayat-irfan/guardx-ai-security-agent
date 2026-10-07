"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getLangChainStatus,
  getRagStatus,
  listPolicies,
  reindexPolicies,
  searchPolicies,
} from "@/lib/api";
import type {
  LangChainStatus,
  PolicyMeta,
  PolicySearchResult,
  RagStatus,
} from "@/lib/types";

export default function PolicyPanel() {
  const [policies, setPolicies] = useState<PolicyMeta[]>([]);
  const [status, setStatus] = useState<RagStatus | null>(null);
  const [lcStatus, setLcStatus] = useState<LangChainStatus | null>(null);
  const [query, setQuery] = useState(
    "A person entered the restricted server room without authorization",
  );
  const [result, setResult] = useState<PolicySearchResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [p, s, lc] = await Promise.all([
        listPolicies(),
        getRagStatus(),
        getLangChainStatus(),
      ]);
      setPolicies(p);
      setStatus(s);
      setLcStatus(lc);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load policies");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleReindex() {
    setBusy(true);
    setError(null);
    try {
      await reindexPolicies();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reindex failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await searchPolicies(query, 3);
      setResult(r);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setBusy(false);
    }
  }

  const stateColor =
    status?.state === "ready"
      ? "bg-emerald-400 shadow-[0_0_12px_#34d399]"
      : status?.state === "error"
        ? "bg-red-400 shadow-[0_0_12px_#f87171]"
        : "bg-amber-400 shadow-[0_0_12px_#fbbf24]";

  return (
    <section className="mt-6 rounded-lg border border-violet-500/20 bg-[#0a101b]/80 p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold tracking-widest text-slate-300 uppercase">
          Policy RAG — Retrieval Only
        </h2>
        <button
          onClick={handleReindex}
          disabled={busy}
          className="text-xs text-violet-200 border border-violet-500/40 rounded px-3 py-1.5 hover:bg-violet-500/10 disabled:opacity-50"
        >
          {busy ? "Working…" : "Reindex policies"}
        </button>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        Retrieves relevant policy sections. It does not make security decisions.
      </p>

      {error && <p className="mt-3 text-xs text-red-400">{error}</p>}

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <div className="space-y-2 text-sm">
          <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
            <span
              className={`inline-block h-2.5 w-2.5 rounded-full ${stateColor}`}
            />
            <span className="text-slate-500">RAG state</span>
            <span className="ml-auto font-mono text-violet-200">
              {status?.state ?? "—"}
            </span>
          </div>
          {[
            ["Policies", String(policies.length)],
            ["Indexed chunks", String(status?.chunk_count ?? "—")],
            ["Embedding model", status?.embedding_model ?? "—"],
            ["Collection", status?.collection ?? "—"],
            [
              "LangChain",
              lcStatus
                ? `${lcStatus.state} · retriever ${lcStatus.retriever_ready ? "ready" : "not-ready"} · LLM ${lcStatus.llm_available ? lcStatus.llm_model : "unavailable"}`
                : "—",
            ],
          ].map(([k, v]) => (
            <div
              key={k}
              className="flex justify-between border-b border-slate-800 pb-2"
            >
              <span className="text-slate-500">{k}</span>
              <span className="font-mono text-slate-300 text-xs break-all text-right max-w-48">
                {v}
              </span>
            </div>
          ))}
          {status?.detail && status.state !== "ready" && (
            <p className="text-xs text-slate-500">{status.detail}</p>
          )}
        </div>

        <div className="lg:col-span-2">
          <p className="text-xs font-semibold tracking-widest text-slate-400 uppercase mb-2">
            Policies
          </p>
          <div className="space-y-1">
            {policies.map((p) => (
              <div
                key={p.policy_id}
                className="flex items-center gap-2 rounded border border-slate-800 bg-[#05080e] px-3 py-1.5 text-xs"
              >
                <span className="font-mono text-violet-300">{p.policy_id}</span>
                <span className="text-slate-300 truncate">{p.title}</span>
                <span className="ml-auto text-slate-600">
                  v{p.version} · {p.category}
                </span>
              </div>
            ))}
            {policies.length === 0 && (
              <p className="text-xs text-slate-600">
                No policies loaded — press Reindex.
              </p>
            )}
          </div>
        </div>
      </div>

      <form onSubmit={handleSearch} className="mt-4 flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Describe the security event…"
          className="flex-1 rounded border border-slate-700 bg-[#05080e] px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600"
        />
        <button
          type="submit"
          disabled={busy}
          className="rounded border border-violet-500/40 bg-violet-500/10 px-4 py-2 text-sm text-violet-200 hover:bg-violet-500/20 disabled:opacity-50"
        >
          Search
        </button>
      </form>

      {result && (
        <div className="mt-3 space-y-2">
          <p className="text-[11px] text-slate-500">
            {result.chunks.length} chunks · {result.took_ms.toFixed(0)} ms
          </p>
          {result.chunks.map((c) => (
            <div
              key={c.chunk_id}
              className="rounded border border-slate-800 bg-[#05080e] p-3"
            >
              <div className="flex items-center gap-2 text-xs">
                <span className="font-mono text-violet-300">{c.chunk_id}</span>
                <span className="text-slate-500">{c.section}</span>
                <span className="ml-auto font-mono text-emerald-300">
                  score {c.score.toFixed(3)}
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-400 line-clamp-3">
                {c.content}
              </p>
              <p className="mt-1 text-[11px] text-slate-600">
                {c.policy_title} · v{c.metadata.version} · {c.metadata.source}
              </p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
