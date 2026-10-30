import React, { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Circle, Loader2, X } from "lucide-react";
import { ChecklistStatus, CompanyChecklist as Checklist, apiGetChecklist } from "../../lib/engine";
import { cn, useEscapeToClose } from "../../lib/utils";

/**
 * The company checklist: what the whole office still has to do, who owns each item, and what is done.
 * Read live from the engine every few seconds; items tick themselves when the work behind them finishes.
 */

type Tab = "stages" | "features" | "tests" | "agents";

const ICON: Record<ChecklistStatus, React.ReactNode> = {
  done: <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />,
  in_progress: <Loader2 className="w-3.5 h-3.5 text-blue-500 animate-spin shrink-0" />,
  needs_attention: <AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0" />,
  blocked: <AlertTriangle className="w-3.5 h-3.5 text-rose-500 shrink-0" />,
  todo: <Circle className="w-3.5 h-3.5 text-brand-body/50 shrink-0" />,
};

const LABEL: Record<ChecklistStatus, string> = {
  done: "Done", in_progress: "In progress", needs_attention: "Needs attention", blocked: "Blocked", todo: "To do",
};

export function useChecklist(sessionId: string | null, enabled = true) {
  const [data, setData] = useState<Checklist | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!sessionId || !enabled) return;
    let alive = true;
    const load = () =>
      apiGetChecklist(sessionId)
        .then((d) => alive && (setData(d), setError(null)))
        .catch((e) => alive && setError(e instanceof Error ? e.message : String(e)));
    load();
    const t = setInterval(load, 5000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [sessionId, enabled]);
  return { data, error };
}

const Owner: React.FC<{ name?: string | null; role?: string | null; id?: string | null }> = ({ name, role, id }) =>
  name || id ? (
    <span className="px-1.5 py-0.5 rounded bg-brand-accent/10 text-brand-accent text-[10px] font-medium shrink-0" title={id || ""}>
      {name || id}{role ? ` · ${role}` : ""}
    </span>
  ) : null;

export const ChecklistBody: React.FC<{ sessionId: string | null; initialTab?: Tab; compact?: boolean }> = ({
  sessionId,
  initialTab = "stages",
  compact = false,
}) => {
  const { data, error } = useChecklist(sessionId);
  const [tab, setTab] = useState<Tab>(initialTab);
  const [agentFilter, setAgentFilter] = useState<string>("");

  if (!sessionId) return <p className="text-xs text-brand-body p-4">Open a project to see its checklist.</p>;
  if (error && !data) return <p className="text-xs text-rose-600 p-4">Could not load the checklist: {error}</p>;
  if (!data) return <p className="text-xs text-brand-body p-4">Loading the checklist…</p>;

  const tabs: { key: Tab; label: string; count: string }[] = [
    { key: "stages", label: "Stages", count: `${data.stages.filter((s) => s.status === "done").length}/${data.stages.length}` },
    { key: "features", label: "Features", count: `${data.features.filter((f) => f.status === "done").length}/${data.features.length}` },
    {
      key: "tests",
      label: "Tests",
      count: (() => {
        const all = data.features.flatMap((f) => f.acceptance_tests);
        return `${all.filter((a) => a.status === "done").length}/${all.length}`;
      })(),
    },
    { key: "agents", label: "By agent", count: String(data.agents.length) },
  ];
  const features = agentFilter
    ? data.features.filter((f) => f.owners.some((o) => o.id === agentFilter))
    : data.features;

  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <div className="flex items-center justify-between text-xs">
          <span className="font-semibold text-brand-headline">
            {data.progress.done} of {data.progress.total} done ({data.progress.percent}%)
          </span>
          {data.progress.needs_attention > 0 && (
            <span className="text-amber-600">{data.progress.needs_attention} need attention</span>
          )}
        </div>
        <div className="h-2 rounded-full bg-brand-subtle overflow-hidden">
          <div className="h-full bg-emerald-500 transition-all duration-700" style={{ width: `${data.progress.percent}%` }} />
        </div>
        <p className="text-[10px] text-brand-body">Updates by itself as agents finish work (every 5 seconds).</p>
      </div>

      <div className="flex flex-wrap gap-1">
        {tabs.map((t) => (
          <button key={t.key} type="button" onClick={() => setTab(t.key)}
            className={cn("px-2.5 py-1 rounded-lg text-[11px] font-medium border cursor-pointer",
              tab === t.key ? "bg-brand-accent text-brand-accent-text border-brand-accent" : "bg-brand-card text-brand-body border-brand-border hover:text-brand-headline")}>
            {t.label} <span className="opacity-70">{t.count}</span>
          </button>
        ))}
        {tab === "features" && data.agents.length > 0 && (
          <select value={agentFilter} onChange={(e) => setAgentFilter(e.target.value)}
            className="ml-auto text-[11px] rounded-lg border border-brand-border bg-brand-card px-2 py-1 text-brand-headline">
            <option value="">All agents</option>
            {data.agents.map((a) => <option key={a.id} value={a.id}>{a.name || a.id} ({a.role})</option>)}
          </select>
        )}
      </div>

      {tab === "stages" && (
        <ul className="space-y-1">
          {data.stages.map((s) => (
            <li key={s.id} className="flex items-center gap-2 rounded-lg border border-brand-border bg-brand-card px-2.5 py-1.5 text-xs" title={LABEL[s.status]}>
              {ICON[s.status]}
              <span className={cn("text-brand-headline", s.status === "done" && "line-through decoration-emerald-500/40")}>{s.title}</span>
              {s.detail && <span className="text-[10px] text-brand-body truncate">{s.detail}</span>}
              <span className="ml-auto text-[10px] text-brand-body shrink-0">{s.owner_role}</span>
            </li>
          ))}
        </ul>
      )}

      {tab === "features" && (
        <div className="space-y-2">
          {features.length === 0 && <p className="text-xs text-brand-body">No features yet (the PRD lists them).</p>}
          {features.map((f) => (
            <div key={f.id} className="rounded-xl border border-brand-border bg-brand-card p-2.5 space-y-1.5">
              <div className="flex items-center gap-2 text-xs flex-wrap">
                {ICON[f.status]}
                <span className="font-mono font-bold text-brand-accent">{f.id}</span>
                <span className="font-semibold text-brand-headline">{f.name}</span>
                {f.priority && <span className="text-[10px] text-brand-body">{f.priority}</span>}
                <span className="ml-auto flex flex-wrap gap-1">
                  {f.owners.length ? f.owners.map((o) => <Owner key={o.id} {...o} />) : (
                    <span className="text-[10px] text-brand-body">No owner yet (the Scrum Master assigns)</span>
                  )}
                </span>
              </div>
              <ul className={cn("grid gap-1", compact ? "grid-cols-1" : "grid-cols-1 sm:grid-cols-2")}>
                {f.items.map((i) => (
                  <li key={i.id} className="flex items-start gap-1.5 text-[11px]">
                    {ICON[i.status]}
                    <span>
                      <span className="text-brand-headline">{i.title}</span>
                      {i.detail && <span className="block text-[10px] text-brand-body">{i.detail}</span>}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      {tab === "tests" && (
        <div className="space-y-2">
          {data.features.map((f) =>
            f.acceptance_tests.length ? (
              <div key={f.id}>
                <div className="text-[11px] font-semibold text-brand-headline mb-1">{f.id} {f.name}</div>
                <ul className="space-y-1">
                  {f.acceptance_tests.map((a) => (
                    <li key={a.id} className="flex items-start gap-2 rounded-lg border border-brand-border bg-brand-card px-2.5 py-1.5 text-[11px]">
                      {ICON[a.status]}
                      <span className="font-mono text-brand-accent shrink-0">{a.id}</span>
                      <span className="text-brand-body">{a.text}</span>
                      <span className="ml-auto text-[10px] text-brand-body shrink-0">{a.detail}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null
          )}
        </div>
      )}

      {tab === "agents" && (
        <div className="space-y-2">
          {data.agents.length === 0 && (
            <p className="text-xs text-brand-body">No assignments yet. After hiring, the Scrum Master assigns every story to an agent.</p>
          )}
          {data.agents.map((a) => (
            <div key={a.id} className="rounded-xl border border-brand-border bg-brand-card p-2.5">
              <div className="flex items-center gap-2 text-xs">
                <span className="font-semibold text-brand-headline">{a.name || a.id}</span>
                <span className="text-[10px] text-brand-body">{a.role}</span>
                <span className="ml-auto text-[10px] font-mono text-brand-body">{a.done}/{a.stories.length} stories done</span>
              </div>
              <ul className="mt-1 space-y-0.5">
                {a.stories.map((s) => (
                  <li key={s.id} className="flex items-center gap-2 text-[11px]">
                    {ICON[s.status === "done" || s.status === "done_perf_not_run" ? "done"
                      : ["building", "fixing", "qa", "merged"].includes(s.status) ? "in_progress"
                      : ["escalated", "blocked"].includes(s.status) ? "needs_attention" : "todo"]}
                    <span className="font-mono text-brand-accent">{s.id}</span>
                    <span className="text-brand-body truncate">{s.title}</span>
                    <span className="ml-auto font-mono text-[10px] text-brand-body shrink-0">{s.features.join(" ")}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

/** The checklist as a side panel, opened from the top navigation on any screen. */
export const ChecklistDrawer: React.FC<{ sessionId: string | null; projectName?: string; onClose: () => void }> = ({
  sessionId,
  projectName,
  onClose,
}) => {
  useEscapeToClose(true, onClose);
  return (
  <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={onClose}>
    <aside className="h-full w-full max-w-xl bg-brand-bg border-l border-brand-border shadow-2xl flex flex-col" onClick={(e) => e.stopPropagation()}>
      <div className="px-4 py-3 border-b border-brand-border flex items-center justify-between">
        <div>
          <h2 className="text-sm font-bold text-brand-headline">Company checklist</h2>
          <p className="text-[11px] text-brand-body">{projectName || "Project"}: every stage, feature and test, with its owner</p>
        </div>
        <button type="button" onClick={onClose} className="p-1.5 rounded-lg hover:bg-brand-subtle cursor-pointer" title="Close">
          <X className="w-4 h-4" />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        <ChecklistBody sessionId={sessionId} />
      </div>
    </aside>
  </div>
  );
};

export default ChecklistBody;
