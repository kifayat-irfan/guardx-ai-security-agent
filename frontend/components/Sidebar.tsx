const NAV = [
  { label: "Dashboard", active: true, phase: null as string | null },
  { label: "Incidents", active: false, phase: "Phase 7" },
  { label: "Zones", active: false, phase: "Phase 3" },
  { label: "Policies", active: false, phase: "Phase 4" },
];

export default function Sidebar() {
  return (
    <aside className="w-60 shrink-0 border-r border-cyan-500/15 bg-[#070b12]/90 flex flex-col">
      <div className="px-5 py-6 border-b border-cyan-500/15">
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
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV.map((item) => (
          <div
            key={item.label}
            className={`flex items-center justify-between rounded-md px-3 py-2.5 text-sm transition-colors ${
              item.active
                ? "bg-cyan-500/10 text-cyan-200 border border-cyan-500/25"
                : "text-slate-500 border border-transparent cursor-not-allowed"
            }`}
          >
            <span className="font-medium tracking-wide">{item.label}</span>
            {item.phase && (
              <span className="text-[10px] uppercase tracking-wider text-slate-600 border border-slate-700 rounded px-1.5 py-0.5">
                {item.phase}
              </span>
            )}
          </div>
        ))}
      </nav>
      <div className="px-5 py-4 border-t border-cyan-500/15">
        <p className="text-[11px] text-slate-500">
          Phase 1 foundation
          <br />
          <span className="text-slate-600">CV pipeline arrives in Phase 2</span>
        </p>
      </div>
    </aside>
  );
}
