import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Hammer,
  ShieldCheck,
  Play,
  Rocket,
  PackageCheck,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  MessageSquareWarning,
  Activity,
} from "lucide-react";
import {
  BuildState,
  BuildStoryState,
  CommandAllowlist,
  GateState,
  OfficeEvent,
  apiApproveAllowlist,
  apiApproveGate3,
  apiApproveGate4,
  apiDeliver,
  apiGetAllowlist,
  apiGetBuildStatus,
  apiGetEvents,
  apiGetGateState,
  apiPrepareRelease,
  apiSendUatFeedback,
  apiStartBeta,
  apiStartBuild,
} from "../../lib/engine";

interface BuildViewerProps {
  sessionId: string | null;
  canBuild: boolean; // Gate 2 approved and readiness verdict ready
}

// Board columns follow the story stages of Handbook 28.2 (build -> review -> QA -> perf -> done).
const COLUMNS: { key: string; title: string; statuses: string[] }[] = [
  { key: "todo", title: "To do", statuses: ["todo"] },
  { key: "build", title: "Build / CI", statuses: ["building", "fixing"] },
  { key: "review", title: "Review & merge", statuses: ["merged"] },
  { key: "qa", title: "QA / Judge", statuses: ["qa"] },
  { key: "done", title: "Done", statuses: ["done", "done_perf_not_run"] },
  { key: "stuck", title: "Escalated / blocked", statuses: ["escalated", "blocked"] },
];

const statusTone = (s: string) =>
  s === "complete"
    ? "bg-emerald-500/15 text-emerald-600"
    : s === "running"
    ? "bg-blue-500/15 text-blue-600"
    : s.includes("issues") || s.startsWith("paused") || s === "failed"
    ? "bg-amber-500/15 text-amber-600"
    : "bg-brand-subtle text-brand-muted";

const StoryCard: React.FC<{ s: BuildStoryState }> = ({ s }) => (
  <div className="rounded-lg border border-brand-border bg-brand-card p-2 text-[11px] space-y-1">
    <div className="flex items-center justify-between gap-2">
      <span className="font-bold text-brand-headline">{s.id}</span>
      <span className="text-brand-muted capitalize">{s.story.role}</span>
    </div>
    <p className="text-brand-body leading-snug">{s.story.title}</p>
    <div className="flex flex-wrap gap-x-2 text-brand-muted">
      <span>{s.story.points} pt</span>
      <span>review rounds {s.rounds ?? 0}</span>
      <span>QA rounds {s.qa_rounds ?? 0}</span>
    </div>
    {s.status === "done_perf_not_run" && (
      <p className="text-amber-600">Perf not run: {s.perf?.reason}</p>
    )}
    {s.escalation && (
      <p className="text-red-600">
        → {s.escalation.to}: {s.escalation.reason}
      </p>
    )}
    {s.blocked_reason && <p className="text-red-600">{s.blocked_reason}</p>}
  </div>
);

export const BuildViewer: React.FC<BuildViewerProps> = ({ sessionId, canBuild }) => {
  const [build, setBuild] = useState<BuildState | null>(null);
  const [allowlist, setAllowlist] = useState<CommandAllowlist | null>(null);
  const [gate3, setGate3] = useState<GateState | null>(null);
  const [gate4, setGate4] = useState<GateState | null>(null);
  const [events, setEvents] = useState<OfficeEvent[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState("");
  const [delivered, setDelivered] = useState<{ path: string; report: string } | null>(null);

  const refresh = useCallback(async () => {
    if (!sessionId) return;
    const [b, a, g3, g4, ev] = await Promise.all([
      apiGetBuildStatus(sessionId).catch(() => null),
      apiGetAllowlist(sessionId).catch(() => null),
      apiGetGateState(3, sessionId).catch(() => null),
      apiGetGateState(4, sessionId).catch(() => null),
      apiGetEvents(sessionId).catch(() => ({ events: [] })),
    ]);
    setBuild(b);
    setAllowlist(a);
    setGate3(g3);
    setGate4(g4);
    setEvents(ev.events.filter((e) => e.type !== "agent.status").slice(-40).reverse());
  }, [sessionId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Poll while the background build is running.
  useEffect(() => {
    if (!build?.thread_alive) return;
    const t = setInterval(refresh, 3000);
    return () => clearInterval(t);
  }, [build?.thread_alive, refresh]);

  const act = async (name: string, fn: () => Promise<unknown>) => {
    setBusy(name);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
      refresh();
    }
  };

  const stories = useMemo(() => Object.values(build?.stories ?? {}), [build]);
  const buildFinished = build?.status === "complete" || build?.status === "complete_with_issues";

  if (!sessionId) {
    return <div className="p-6 text-xs text-brand-body">Select a project first.</div>;
  }

  return (
    <div className="h-full overflow-y-auto space-y-4 p-1">
      {/* Status and actions */}
      <div className="rounded-2xl border border-brand-border bg-brand-card p-4 space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Hammer className="w-4 h-4 text-orange-500" />
          <h3 className="text-sm font-bold text-brand-headline">Build &amp; Release (Stages 6–9)</h3>
          <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${statusTone(build?.status ?? "")}`}>
            {build?.status ?? "not started"}
          </span>
          {build?.thread_alive && <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-500" />}
        </div>
        {build?.message && <p className="text-[11px] text-amber-600">{build.message}</p>}
        {error && (
          <p className="flex items-start gap-1.5 text-[11px] text-red-600">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
            {error}
          </p>
        )}

        {!canBuild && (
          <p className="text-[11px] text-brand-body">
            Building unlocks after Gate 2 is approved and the readiness verdict is <b>ready</b>.
          </p>
        )}

        {canBuild && allowlist && !allowlist.approved && (
          <div className="rounded-xl border border-brand-border bg-brand-surface p-3 space-y-2">
            <p className="text-[11px] font-semibold text-brand-headline">
              Approve the commands agents may run ({allowlist.stack}; network stays off)
            </p>
            <ul className="text-[11px] font-mono text-brand-body space-y-0.5">
              {Object.entries(allowlist.commands).map(([id, cmd]) => (
                <li key={id}>
                  <span className="text-brand-muted">{id}:</span> {cmd}
                </li>
              ))}
            </ul>
            <button
              type="button"
              disabled={busy !== null}
              onClick={() => act("allowlist", () => apiApproveAllowlist(sessionId))}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold disabled:opacity-50 cursor-pointer"
            >
              <ShieldCheck className="w-3.5 h-3.5" /> Approve allowlist
            </button>
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={!canBuild || !allowlist?.approved || build?.thread_alive || busy !== null}
            onClick={() => act("build", () => apiStartBuild(sessionId))}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold disabled:opacity-40 cursor-pointer"
          >
            <Play className="w-3.5 h-3.5" /> {build?.status && build.status !== "not_started" ? "Resume build" : "Start build"}
          </button>
          <button
            type="button"
            disabled={!buildFinished || build?.thread_alive || busy !== null}
            onClick={() => act("beta", () => apiStartBeta(sessionId))}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold disabled:opacity-40 cursor-pointer"
          >
            <Activity className="w-3.5 h-3.5" /> Start Beta (Gate 3)
          </button>
          <button
            type="button"
            disabled={!gate3?.approved || busy !== null}
            onClick={() => act("release", () => apiPrepareRelease(sessionId))}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-700 text-white text-xs font-semibold disabled:opacity-40 cursor-pointer"
          >
            <Rocket className="w-3.5 h-3.5" /> Prepare release (Gate 4)
          </button>
          <button
            type="button"
            disabled={!gate4?.approved || busy !== null}
            onClick={() =>
              act("deliver", async () => {
                const d = await apiDeliver(sessionId);
                setDelivered({ path: d.path, report: d.report });
              })
            }
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold disabled:opacity-40 cursor-pointer"
          >
            <PackageCheck className="w-3.5 h-3.5" /> Deliver
          </button>
          {busy && <Loader2 className="w-4 h-4 animate-spin text-brand-muted self-center" />}
        </div>
      </div>

      {/* Board */}
      <div className="grid grid-cols-2 lg:grid-cols-6 gap-2">
        {COLUMNS.map((col) => {
          const items = stories.filter((s) => col.statuses.includes(s.status));
          return (
            <div key={col.key} className="rounded-xl border border-brand-border bg-brand-surface p-2 space-y-2 min-h-[120px]">
              <p className="text-[11px] font-bold text-brand-headline">
                {col.title} <span className="text-brand-muted">({items.length})</span>
              </p>
              {items.map((s) => (
                <StoryCard key={s.id} s={s} />
              ))}
            </div>
          );
        })}
      </div>

      {/* Gate 3 */}
      {gate3 && gate3.status !== "not_open" && (
        <div className="rounded-2xl border border-brand-border bg-brand-card p-4 space-y-2">
          <p className="text-xs font-bold text-brand-headline">Gate 3 · Beta / UAT — {gate3.status}</p>
          <pre className="text-[11px] whitespace-pre-wrap text-brand-body bg-brand-surface rounded-lg p-2 max-h-64 overflow-y-auto">
            {gate3.summary}
          </pre>
          {gate3.status === "open" && (
            <div className="space-y-2">
              <textarea
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="Report a problem found while testing the preview (goes through the BA)"
                className="w-full text-xs rounded-lg border border-brand-border bg-brand-surface p-2 text-brand-headline"
                rows={2}
              />
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={!feedback.trim() || busy !== null}
                  onClick={() =>
                    act("uat", async () => {
                      await apiSendUatFeedback(sessionId, feedback.trim(), "bug");
                      setFeedback("");
                    })
                  }
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold disabled:opacity-40 cursor-pointer"
                >
                  <MessageSquareWarning className="w-3.5 h-3.5" /> Report bug (back to build)
                </button>
                <button
                  type="button"
                  disabled={busy !== null}
                  onClick={() => act("gate3", () => apiApproveGate3(sessionId, "UAT passed"))}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold disabled:opacity-40 cursor-pointer"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" /> Approve Gate 3
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Gate 4 */}
      {gate4 && gate4.status !== "not_open" && (
        <div className="rounded-2xl border border-brand-border bg-brand-card p-4 space-y-2">
          <p className="text-xs font-bold text-brand-headline">Gate 4 · Go live — {gate4.status}</p>
          <pre className="text-[11px] whitespace-pre-wrap text-brand-body bg-brand-surface rounded-lg p-2 max-h-64 overflow-y-auto">
            {gate4.summary}
          </pre>
          {gate4.status === "open" && (
            <button
              type="button"
              disabled={busy !== null}
              onClick={() => act("gate4", () => apiApproveGate4(sessionId, "go live"))}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold disabled:opacity-40 cursor-pointer"
            >
              <CheckCircle2 className="w-3.5 h-3.5" /> Approve go-live
            </button>
          )}
        </div>
      )}

      {delivered && (
        <div className="rounded-2xl border border-emerald-500/40 bg-brand-card p-4 space-y-2">
          <p className="text-xs font-bold text-emerald-600">Delivered locally to {delivered.path}</p>
          <pre className="text-[11px] whitespace-pre-wrap text-brand-body max-h-72 overflow-y-auto">{delivered.report}</pre>
        </div>
      )}

      {/* Activity feed (from the event log) */}
      <div className="rounded-2xl border border-brand-border bg-brand-card p-4">
        <p className="text-xs font-bold text-brand-headline mb-2">Activity</p>
        <ul className="space-y-1 text-[11px] font-mono text-brand-body max-h-64 overflow-y-auto">
          {events.length === 0 && <li className="text-brand-muted">No events yet.</li>}
          {events.map((e) => (
            <li key={e.seq}>
              <span className="text-brand-muted">#{e.seq}</span> {e.type}
              {e.task_id ? ` · ${e.task_id}` : ""}
              {e.actor ? ` · ${e.actor}` : ""}
              {e.type === "tool.call" && e.data?.tool ? ` · ${e.data.tool}${e.data.ok ? "" : " (error)"}` : ""}
              {e.type === "ci.completed" ? ` · ${e.data?.green ? "green" : "red"}` : ""}
              {e.type === "review.completed" ? ` · ${e.data?.decision}` : ""}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};

export default BuildViewer;
