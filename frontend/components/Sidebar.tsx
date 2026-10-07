"use client";

const NAV = [
  { label: "Overview", href: "#overview" },
  { label: "Live Feed", href: "#live" },
  { label: "Cameras", href: "#cameras" },
  { label: "Zones", href: "#cameras" },
  { label: "Policies", href: "#policies" },
  { label: "Incidents", href: "#incidents" },
  { label: "AI Workflow", href: "#workflow" },
  { label: "System Health", href: "#system" },
];

export default function Sidebar() {
  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-cyan-500/15 bg-[#070b12]/90 md:flex">
      <div className="border-b border-cyan-500/15 px-5 py-6">
        <div className="flex items-center gap-2">
          <span className="inline-block h-3 w-3 rounded-full bg-cyan-400 shadow-[0_0_12px_#22d3ee]" />
          <span className="text-xl font-bold tracking-[0.25em] text-cyan-100">
            GUARD<span className="text-cyan-400">X</span>
          </span>
        </div>
        <p className="mt-1 text-[11px] uppercase tracking-widest text-slate-500">
          Security Operations
        </p>
      </div>
      <nav className="flex-1 space-y-1 px-3 py-4" aria-label="Dashboard sections">
        {NAV.map((item) => (
          <a
            key={item.href}
            href={item.href}
            className="block rounded-md border border-transparent px-3 py-2.5 text-sm text-slate-400 transition-colors hover:border-cyan-500/25 hover:bg-cyan-500/10 hover:text-cyan-200 focus-visible:border-cyan-400 focus-visible:outline-none"
          >
            <span className="font-medium tracking-wide">{item.label}</span>
          </a>
        ))}
      </nav>
      <div className="border-t border-cyan-500/15 px-5 py-4">
        <p className="text-[11px] text-slate-500">
          GuardX v0.1.0
          <br />
          <span className="text-slate-600">Phase 8 operations dashboard</span>
        </p>
      </div>
    </aside>
  );
}
