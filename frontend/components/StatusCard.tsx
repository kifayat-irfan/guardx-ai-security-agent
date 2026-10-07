import type { ComponentStatus } from "@/lib/types";

interface Props {
  title: string;
  subtitle: string;
  component: ComponentStatus | null;
  loading: boolean;
}

function dotClass(status: string | undefined): string {
  if (status === "up") return "bg-emerald-400 shadow-[0_0_10px_#34d399]";
  if (status === "down") return "bg-red-400 shadow-[0_0_10px_#f87171]";
  return "bg-slate-500";
}

function badgeClass(status: string | undefined): string {
  if (status === "up") return "text-emerald-300 border-emerald-500/30 bg-emerald-500/10";
  if (status === "down") return "text-red-300 border-red-500/30 bg-red-500/10";
  return "text-slate-400 border-slate-600 bg-slate-500/10";
}

export default function StatusCard({ title, subtitle, component, loading }: Props) {
  return (
    <div className="rounded-lg border border-cyan-500/15 bg-[#0a101b]/80 p-5 backdrop-blur">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold tracking-widest text-slate-300 uppercase">
          {title}
        </h3>
        <span className={`inline-block h-2.5 w-2.5 rounded-full ${dotClass(component?.status)}`} />
      </div>
      <p className="mt-1 text-xs text-slate-500">{subtitle}</p>
      <div className="mt-4">
        {loading ? (
          <span className="text-sm text-slate-500 animate-pulse">Checking…</span>
        ) : (
          <span
            className={`inline-block rounded border px-2.5 py-1 text-xs font-mono uppercase tracking-wider ${badgeClass(component?.status)}`}
          >
            {component?.status ?? "unknown"}
          </span>
        )}
      </div>
      {!loading && component?.detail && (
        <p className="mt-3 text-[11px] font-mono text-slate-500 break-words">
          {component.detail}
        </p>
      )}
    </div>
  );
}
