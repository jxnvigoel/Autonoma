import React, { useEffect, useMemo, useState } from "react";
import { Database, GitBranch, Layers, Network, Server, Users } from "lucide-react";
import { ArchitectureModel, apiGetArchitectureModel } from "../../lib/engine";
import { cn } from "../../lib/utils";

/**
 * The Architect's design as pictures: system diagram, data model, API map, decisions and build plan.
 * Everything is drawn from the parsed documents (engine/architecture_model.py), so it matches them.
 */

type View = "system" | "data" | "api" | "decisions" | "plan";

const METHOD_TONE: Record<string, string> = {
  GET: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30",
  POST: "bg-blue-500/15 text-blue-700 dark:text-blue-300 border-blue-500/30",
  PUT: "bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30",
  PATCH: "bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30",
  DELETE: "bg-rose-500/15 text-rose-700 dark:text-rose-300 border-rose-500/30",
};

// ---------------------------------------------------------------- system diagram (layered layout)

const NODE_W = 170;
const NODE_H = 54;
const GAP_X = 36;
const GAP_Y = 84;
const PAD = 44;

function layoutSystem(sys: ArchitectureModel["system"]) {
  // Rank = longest path from a source, so arrows always point down the page.
  const rank: Record<string, number> = {};
  sys.nodes.forEach((n) => (rank[n.id] = 0));
  for (let pass = 0; pass < sys.nodes.length; pass++) {
    let changed = false;
    for (const e of sys.edges) {
      if (rank[e.to] !== undefined && rank[e.from] !== undefined && rank[e.to] < rank[e.from] + 1) {
        rank[e.to] = rank[e.from] + 1;
        changed = true;
      }
    }
    if (!changed) break;
  }
  const rows: Record<number, string[]> = {};
  sys.nodes.forEach((n) => (rows[rank[n.id]] = [...(rows[rank[n.id]] || []), n.id]));
  const maxRow = Math.max(1, ...Object.values(rows).map((r) => r.length));
  const width = PAD * 2 + maxRow * NODE_W + (maxRow - 1) * GAP_X;
  const pos: Record<string, { x: number; y: number }> = {};
  Object.entries(rows).forEach(([r, ids]) => {
    const rowW = ids.length * NODE_W + (ids.length - 1) * GAP_X;
    ids.forEach((id, i) => {
      pos[id] = { x: (width - rowW) / 2 + i * (NODE_W + GAP_X), y: PAD + 18 + Number(r) * (NODE_H + GAP_Y) };
    });
  });
  const height = PAD * 2 + 18 + (Object.keys(rows).length) * (NODE_H + GAP_Y) - GAP_Y;
  // Group boxes enclose their nodes (and nested groups).
  const members = (gid: string): string[] => [
    ...sys.nodes.filter((n) => n.group === gid).map((n) => n.id),
    ...sys.groups.filter((g) => g.parent === gid).flatMap((g) => members(g.id)),
  ];
  const depth = (gid: string | null): number => (gid ? 1 + depth(sys.groups.find((g) => g.id === gid)?.parent ?? null) : 0);
  // How many group levels sit inside a group: outer boxes get more room so their labels never overlap.
  const levelsInside = (gid: string): number =>
    Math.max(0, ...sys.groups.filter((g) => g.parent === gid).map((g) => 1 + levelsInside(g.id)));
  const boxes = sys.groups
    .map((g) => {
      const ids = members(g.id).filter((id) => pos[id]);
      if (!ids.length) return null;
      const inset = 8 + 18 * levelsInside(g.id);
      const xs = ids.map((id) => pos[id].x), ys = ids.map((id) => pos[id].y);
      return {
        ...g,
        x: Math.min(...xs) - inset - 8,
        y: Math.min(...ys) - inset - 16,
        w: Math.max(...xs) - Math.min(...xs) + NODE_W + 2 * (inset + 8),
        h: Math.max(...ys) - Math.min(...ys) + NODE_H + 2 * inset + 24,
        depth: depth(g.id),
      };
    })
    .filter(Boolean) as (ArchitectureModel["system"]["groups"][number] & { x: number; y: number; w: number; h: number; depth: number })[];
  return { pos, width, height, boxes };
}

const SystemDiagram: React.FC<{ model: ArchitectureModel }> = ({ model }) => {
  const sys = model.system;
  const [focus, setFocus] = useState<string | null>(null);
  const { pos, width, height, boxes } = useMemo(() => layoutSystem(sys), [sys]);
  if (!sys.nodes.length) {
    return <Empty text="architecture.md has no system diagram (section 4) to draw." />;
  }
  const linked = (id: string) =>
    !focus || id === focus || sys.edges.some((e) => (e.from === focus && e.to === id) || (e.to === focus && e.from === id));
  return (
    <div className="space-y-2">
      {model.pattern && (
        <p className="text-xs text-brand-body">
          <span className="font-semibold text-brand-headline">Pattern:</span> {model.pattern}
        </p>
      )}
      <div className="overflow-auto rounded-xl border border-brand-border bg-brand-bg">
        <svg viewBox={`0 0 ${width} ${height + 20}`} className="w-full min-w-[520px]" role="img" aria-label="System diagram">
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" className="fill-brand-body" />
            </marker>
          </defs>
          {boxes
            .sort((a, b) => a.depth - b.depth)
            .map((b) => (
              <g key={b.id}>
                <rect x={b.x} y={b.y} width={b.w} height={b.h} rx={12}
                  fill={b.depth > 1 ? "var(--color-accent)" : "var(--color-subtle)"}
                  fillOpacity={b.depth > 1 ? 0.06 : 0.45}
                  stroke={b.depth > 1 ? "var(--color-accent)" : "var(--color-border)"}
                  strokeOpacity={b.depth > 1 ? 0.45 : 1}
                  strokeDasharray={b.depth > 1 ? "4 3" : undefined} />
                <text x={b.x + 10} y={b.y + 14} className="fill-brand-body text-[10px] font-semibold uppercase tracking-wide">
                  {b.label}
                </text>
              </g>
            ))}
          {sys.edges.map((e, i) => {
            const a = pos[e.from], b = pos[e.to];
            if (!a || !b) return null;
            const x1 = a.x + NODE_W / 2, y1 = a.y + NODE_H, x2 = b.x + NODE_W / 2, y2 = b.y;
            const my = (y1 + y2) / 2;
            const on = !focus || e.from === focus || e.to === focus;
            return (
              <g key={i} opacity={on ? 1 : 0.15}>
                <path d={`M ${x1} ${y1} C ${x1} ${my}, ${x2} ${my}, ${x2} ${y2 - 2}`} fill="none"
                  className="stroke-brand-body" strokeWidth={1.4} markerEnd="url(#arrow)" />
                {e.label && (
                  <text x={(x1 + x2) / 2 + 6} y={my} className="fill-brand-body text-[10px]">{e.label}</text>
                )}
              </g>
            );
          })}
          {sys.nodes.map((n) => {
            const p = pos[n.id];
            const lines = n.label.split("\n").slice(0, 2);
            return (
              <g key={n.id} transform={`translate(${p.x},${p.y})`} opacity={linked(n.id) ? 1 : 0.25}
                onMouseEnter={() => setFocus(n.id)} onMouseLeave={() => setFocus(null)} className="cursor-pointer">
                {n.kind === "database" ? (
                  <>
                    <rect y={8} width={NODE_W} height={NODE_H - 8} className="fill-amber-500/10 stroke-amber-500/60" />
                    <ellipse cx={NODE_W / 2} cy={8} rx={NODE_W / 2} ry={8} className="fill-amber-500/20 stroke-amber-500/60" />
                    <ellipse cx={NODE_W / 2} cy={NODE_H} rx={NODE_W / 2} ry={6} className="fill-amber-500/10 stroke-amber-500/60" />
                  </>
                ) : (
                  <rect width={NODE_W} height={NODE_H} rx={10} fill="var(--color-card)" stroke="var(--color-accent)" strokeOpacity={0.6} strokeWidth={1.4} />
                )}
                {lines.map((l, i) => (
                  <text key={i} x={NODE_W / 2} y={NODE_H / 2 + (i - (lines.length - 1) / 2) * 14 + 4} textAnchor="middle"
                    className={i === 0 ? "fill-brand-headline text-[12px] font-semibold" : "fill-brand-body text-[10px]"}>
                    {l.length > 26 ? l.slice(0, 25) + "…" : l}
                  </text>
                ))}
              </g>
            );
          })}
        </svg>
      </div>
      <p className="text-[10px] text-brand-body">Hover a component to see what it talks to. Drawn from architecture.md section 4.</p>
      {model.stack.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {model.stack.map((s) => (
            <div key={s.layer} className="rounded-lg border border-brand-border bg-brand-card px-3 py-2 text-xs">
              <div className="text-[10px] uppercase tracking-wide text-brand-body">{s.layer}</div>
              <div className="font-semibold text-brand-headline">{s.choice}</div>
              {s.refs.length > 0 && <div className="text-[10px] font-mono text-brand-accent">{s.refs.join(" ")}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------- data model (ER)

const DataModel: React.FC<{ model: ArchitectureModel }> = ({ model }) => {
  const tables = model.tables;
  if (!tables.length) return <Empty text="schema.md has no CREATE TABLE statements to draw." />;
  const COL_W = 210, ROW_H = 18, HEAD = 26, GAP = 70;
  const cols = Math.min(3, tables.length);
  const heights = tables.map((t) => HEAD + t.columns.length * ROW_H + 8);
  const rowH = Math.max(...heights);
  const place = tables.map((t, i) => ({ t, x: 20 + (i % cols) * (COL_W + GAP), y: 20 + Math.floor(i / cols) * (rowH + 40) }));
  const at = Object.fromEntries(place.map((p) => [p.t.name, p]));
  const width = 40 + cols * COL_W + (cols - 1) * GAP;
  const height = 40 + Math.ceil(tables.length / cols) * (rowH + 40);
  return (
    <div className="space-y-2">
      <div className="overflow-auto rounded-xl border border-brand-border bg-brand-bg">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full min-w-[520px]" role="img" aria-label="Data model">
          {place.flatMap((p) =>
            p.t.foreign_keys.map((fk, i) => {
              const target = at[fk.table];
              const ci = p.t.columns.findIndex((c) => c.name === fk.column);
              if (!target || ci < 0) return null;
              const y1 = p.y + HEAD + ci * ROW_H + ROW_H / 2;
              const ti = target.t.columns.findIndex((c) => c.name === fk.ref_column);
              const y2 = target.y + HEAD + Math.max(0, ti) * ROW_H + ROW_H / 2;
              const leftToRight = target.x > p.x;
              const x1 = leftToRight ? p.x + COL_W : p.x;
              const x2 = leftToRight ? target.x : target.x + COL_W;
              const bend = target.x === p.x ? -40 : 0;
              return (
                <path key={`${p.t.name}-${i}`} fill="none" className="stroke-brand-accent" strokeWidth={1.3}
                  d={target.x === p.x
                    ? `M ${p.x} ${y1} C ${p.x + bend} ${y1}, ${p.x + bend} ${y2}, ${p.x} ${y2}`
                    : `M ${x1} ${y1} C ${(x1 + x2) / 2} ${y1}, ${(x1 + x2) / 2} ${y2}, ${x2} ${y2}`} />
              );
            })
          )}
          {place.map(({ t, x, y }) => (
            <g key={t.name} transform={`translate(${x},${y})`}>
              <rect width={COL_W} height={HEAD + t.columns.length * ROW_H + 8} rx={10} className="fill-brand-card stroke-brand-border" />
              <rect width={COL_W} height={HEAD} rx={10} fill="var(--color-accent)" fillOpacity={0.15} />
              <text x={10} y={17} className="fill-brand-headline text-[12px] font-bold">{t.name}</text>
              {t.id && <text x={COL_W - 10} y={17} textAnchor="end" className="fill-brand-accent text-[10px] font-mono">{t.id}</text>}
              {t.columns.map((c, i) => (
                <g key={c.name} transform={`translate(0,${HEAD + i * ROW_H})`}>
                  <text x={10} y={13} className={cn("text-[10.5px] font-mono", c.pk ? "fill-amber-600 font-bold" : c.fk ? "fill-brand-accent" : "fill-brand-headline")}>
                    {c.pk ? "🔑 " : c.fk ? "↗ " : ""}{c.name}
                  </text>
                  <text x={COL_W - 10} y={13} textAnchor="end" className="fill-brand-body text-[10px] font-mono">
                    {c.type}{c.nullable ? "?" : ""}
                  </text>
                </g>
              ))}
            </g>
          ))}
        </svg>
      </div>
      <p className="text-[10px] text-brand-body">🔑 primary key · ↗ foreign key (lines show the reference) · ? nullable. From schema.md.</p>
    </div>
  );
};

// ---------------------------------------------------------------- API map + coverage chart

const ApiMap: React.FC<{ model: ArchitectureModel }> = ({ model }) => {
  if (!model.endpoints.length) return <Empty text="openapi.yaml has no endpoints yet." />;
  const max = Math.max(1, ...model.endpoints_per_feature.map((f) => f.count));
  const name = (fid: string) => model.features.find((f) => f.id === fid)?.name || fid;
  const methods = model.endpoints.reduce<Record<string, number>>((m, e) => ({ ...m, [e.method]: (m[e.method] || 0) + 1 }), {});
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <Stat label="Endpoints" value={model.endpoints.length} />
        <Stat label="Features covered" value={`${model.features.length - model.uncovered_features.length}/${model.features.length}`} />
        <Stat label="Need sign-in" value={model.endpoints.filter((e) => e.auth).length} />
        <Stat label="Tables" value={model.tables.length} />
      </div>
      <div className="rounded-xl border border-brand-border bg-brand-card p-3 space-y-1.5">
        <div className="text-xs font-semibold text-brand-headline">Endpoints per feature</div>
        {model.endpoints_per_feature.map((f) => (
          <div key={f.feature} className="flex items-center gap-2 text-[11px]">
            <span className="w-14 font-mono text-brand-accent shrink-0">{f.feature}</span>
            <span className="w-40 truncate text-brand-body shrink-0" title={name(f.feature)}>{name(f.feature)}</span>
            <div className="flex-1 h-3 rounded bg-brand-subtle overflow-hidden">
              <div className={cn("h-full rounded", f.count ? "bg-brand-accent" : "bg-rose-500")} style={{ width: `${f.count ? (f.count / max) * 100 : 4}%` }} />
            </div>
            <span className="w-6 text-right font-mono text-brand-headline">{f.count}</span>
          </div>
        ))}
        {model.uncovered_features.length > 0 && (
          <p className="text-[11px] text-rose-600">No endpoint yet for {model.uncovered_features.join(", ")}.</p>
        )}
        <div className="flex gap-1.5 pt-1">
          {Object.entries(methods).map(([m, n]) => (
            <span key={m} className={cn("px-1.5 py-0.5 rounded border text-[10px] font-mono", METHOD_TONE[m])}>{m} {n}</span>
          ))}
        </div>
      </div>
      <div className="space-y-1">
        {model.endpoints.map((e) => (
          <div key={e.method + e.path} className="flex items-center gap-2 rounded-lg border border-brand-border bg-brand-card px-2.5 py-1.5 text-[11px]">
            <span className={cn("w-14 text-center px-1 py-0.5 rounded border font-mono font-bold shrink-0", METHOD_TONE[e.method])}>{e.method}</span>
            <span className="font-mono text-brand-headline truncate">{e.path}</span>
            <span className="text-brand-body truncate hidden md:inline">{e.summary}</span>
            <span className="ml-auto font-mono text-brand-accent shrink-0">{[...e.features, e.api_id].filter(Boolean).join(" ")}</span>
            {e.auth && <span className="text-[10px] text-brand-body shrink-0" title="Needs sign-in">🔒</span>}
          </div>
        ))}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------- decisions + build plan

const Decisions: React.FC<{ model: ArchitectureModel }> = ({ model }) =>
  model.adrs.length ? (
    <div className="space-y-2">
      {model.adrs.map((a) => (
        <div key={a.id} className="rounded-xl border border-brand-border bg-brand-card p-3 text-xs space-y-1">
          <div className="flex items-center gap-2">
            <span className="font-mono font-bold text-brand-accent">{a.id}</span>
            <span className="font-semibold text-brand-headline">{a.title}</span>
            {a.status && <span className="ml-auto px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 text-[10px] capitalize">{a.status}</span>}
          </div>
          {a.decision && <p className="text-brand-body">{a.decision.replace(/\*\*/g, "")}</p>}
          {a.driven_by.length > 0 && <p className="text-[10px] font-mono text-brand-body">Driven by {a.driven_by.join(" ")}</p>}
        </div>
      ))}
    </div>
  ) : (
    <Empty text="No decision records (docs/adr) yet." />
  );

const BuildPlan: React.FC<{ model: ArchitectureModel }> = ({ model }) => (
  <div className="space-y-4">
    {model.build_slices.length ? (
      <ol className="relative border-l-2 border-brand-accent/40 ml-2 space-y-3">
        {model.build_slices.map((s, i) => (
          <li key={s.title} className="ml-4">
            <span className="absolute -left-[9px] w-4 h-4 rounded-full bg-brand-accent text-brand-accent-text text-[9px] font-bold flex items-center justify-center">{i + 1}</span>
            <div className="text-xs font-semibold text-brand-headline">{s.title}</div>
            <ul className="mt-1 space-y-0.5 text-[11px] text-brand-body list-disc ml-4">
              {s.items.map((it, j) => <li key={j}>{it.replace(/\*\*|`/g, "")}</li>)}
            </ul>
          </li>
        ))}
      </ol>
    ) : (
      <Empty text="architecture.md has no build order (section 11)." />
    )}
    {model.team.length > 0 && (
      <div className="rounded-xl border border-brand-border bg-brand-card p-3">
        <div className="text-xs font-semibold text-brand-headline mb-2 flex items-center gap-1.5"><Users className="w-3.5 h-3.5" /> Team the Architect asks HR for</div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {model.team.map((t) => (
            <div key={t.seat} className="rounded-lg border border-brand-border px-2.5 py-1.5 text-[11px]">
              <div className="font-semibold text-brand-headline">{t.role} × {t.count}</div>
              <div className="font-mono text-[10px] text-brand-body">{t.seat} · {t.refs.join(" ")}</div>
            </div>
          ))}
        </div>
      </div>
    )}
  </div>
);

// ---------------------------------------------------------------- shell

const Stat: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
  <div className="rounded-lg border border-brand-border bg-brand-card px-3 py-2">
    <div className="text-[10px] uppercase tracking-wide text-brand-body">{label}</div>
    <div className="text-lg font-black text-brand-headline">{value}</div>
  </div>
);

const Empty: React.FC<{ text: string }> = ({ text }) => (
  <div className="rounded-xl border border-dashed border-brand-border p-6 text-center text-xs text-brand-body">{text}</div>
);

export const ArchitectureVisuals: React.FC<{ sessionId: string | null; refreshKey?: string }> = ({ sessionId, refreshKey }) => {
  const [model, setModel] = useState<ArchitectureModel | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<View>("system");

  useEffect(() => {
    if (!sessionId) return;
    apiGetArchitectureModel(sessionId)
      .then((m) => {
        setModel(m);
        setError(null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [sessionId, refreshKey]);

  if (error) return <Empty text={`Could not load the architecture: ${error}`} />;
  if (!model) return <Empty text="Loading the architecture…" />;
  if (!model.has_architecture) return <Empty text="The Architect has not written the architecture yet." />;

  const views: { key: View; label: string; icon: React.ReactNode }[] = [
    { key: "system", label: "System", icon: <Network className="w-3.5 h-3.5" /> },
    { key: "data", label: "Data model", icon: <Database className="w-3.5 h-3.5" /> },
    { key: "api", label: "API map", icon: <Server className="w-3.5 h-3.5" /> },
    { key: "decisions", label: "Decisions", icon: <GitBranch className="w-3.5 h-3.5" /> },
    { key: "plan", label: "Build plan", icon: <Layers className="w-3.5 h-3.5" /> },
  ];
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1">
        {views.map((v) => (
          <button key={v.key} type="button" onClick={() => setView(v.key)}
            className={cn("flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium border cursor-pointer",
              view === v.key ? "bg-brand-accent text-brand-accent-text border-brand-accent" : "bg-brand-card text-brand-body border-brand-border hover:text-brand-headline")}>
            {v.icon}{v.label}
          </button>
        ))}
      </div>
      {view === "system" && <SystemDiagram model={model} />}
      {view === "data" && <DataModel model={model} />}
      {view === "api" && <ApiMap model={model} />}
      {view === "decisions" && <Decisions model={model} />}
      {view === "plan" && <BuildPlan model={model} />}
    </div>
  );
};

export default ArchitectureVisuals;
