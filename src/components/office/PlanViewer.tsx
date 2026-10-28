import React, { useState } from "react";
import {
  Calendar,
  Users,
  Copy,
  Check,
  ArrowRight,
  GitBranch,
  BarChart3,
} from "lucide-react";
import { CriticalPathInfo, LoadBalanceInfo, GanttData } from "../../lib/engine";

interface PlanViewerProps {
  planContent?: string;
  criticalPath?: CriticalPathInfo | null;
  loadBalance?: LoadBalanceInfo | null;
  gantt?: GanttData | null;
  onProceedToReadiness?: () => void;
}

export const PlanViewer: React.FC<PlanViewerProps> = ({
  planContent,
  criticalPath,
  loadBalance,
  gantt,
  onProceedToReadiness,
}) => {
  const [activeTab, setActiveTab] = useState<"gantt" | "critical_path" | "load" | "markdown">("gantt");
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (!planContent) return;
    navigator.clipboard.writeText(planContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const tasks = gantt?.tasks || [];
  const totalDays = gantt?.total_days || criticalPath?.estimated_days || 1;

  return (
    <div className="h-full flex flex-col space-y-4">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-4 rounded-xl bg-brand-card border border-brand-border shadow-xs">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 flex items-center justify-center font-bold text-sm">
            <Calendar className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-brand-headline">
                Implementation Plan & Critical Path
              </h3>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
                {totalDays} Agent-Days Duration
              </span>
            </div>
            <p className="text-xs text-brand-muted">
              Computed by code &bull; DAG critical path &bull; 1 story per agent WIP limit
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex p-0.5 rounded-lg bg-brand-surface border border-brand-border">
            <button
              onClick={() => setActiveTab("gantt")}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                activeTab === "gantt"
                  ? "bg-brand-card text-brand-headline shadow-xs"
                  : "text-brand-muted hover:text-brand-body"
              }`}
            >
              Timeline / Gantt
            </button>
            <button
              onClick={() => setActiveTab("critical_path")}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                activeTab === "critical_path"
                  ? "bg-brand-card text-brand-headline shadow-xs"
                  : "text-brand-muted hover:text-brand-body"
              }`}
            >
              Critical Path
            </button>
            <button
              onClick={() => setActiveTab("load")}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                activeTab === "load"
                  ? "bg-brand-card text-brand-headline shadow-xs"
                  : "text-brand-muted hover:text-brand-body"
              }`}
            >
              Load Balancing
            </button>
            <button
              onClick={() => setActiveTab("markdown")}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                activeTab === "markdown"
                  ? "bg-brand-card text-brand-headline shadow-xs"
                  : "text-brand-muted hover:text-brand-body"
              }`}
            >
              Plan Doc
            </button>
          </div>

          {onProceedToReadiness && (
            <button
              onClick={onProceedToReadiness}
              className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium flex items-center gap-1.5 shadow-xs transition-all"
            >
              <span>Tech Lead Review</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {activeTab === "gantt" && (
          <div className="space-y-4">
            {/* Visual Timeline Bars */}
            <div className="p-4 rounded-xl bg-brand-card border border-brand-border">
              <div className="flex items-center justify-between mb-4">
                <h4 className="text-xs font-bold text-brand-headline uppercase tracking-wider flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-brand-accent" />
                  Scheduled Timeline by Agent & Story
                </h4>
                <div className="flex items-center gap-3 text-[11px]">
                  <span className="flex items-center gap-1 text-rose-500 font-semibold">
                    <span className="w-2.5 h-2.5 rounded bg-rose-500 inline-block" /> Critical Path
                  </span>
                  <span className="flex items-center gap-1 text-indigo-500 font-semibold">
                    <span className="w-2.5 h-2.5 rounded bg-indigo-500 inline-block" /> Standard Story
                  </span>
                </div>
              </div>

              {/* Day header ticks */}
              <div className="grid grid-cols-12 gap-1 mb-2 text-[10px] text-brand-muted border-b border-brand-border pb-1 font-mono">
                <div className="col-span-4 text-left">Story / Owner</div>
                <div className="col-span-8 flex justify-between px-1">
                  <span>Day 1</span>
                  <span>Day {Math.ceil(totalDays / 2)}</span>
                  <span>Day {totalDays}</span>
                </div>
              </div>

              {/* Story rows */}
              <div className="space-y-2">
                {tasks.map((t) => {
                  const leftPct = ((t.start_day - 1) / totalDays) * 100;
                  const widthPct = Math.max(((t.finish_day - t.start_day + 1) / totalDays) * 100, 8);
                  return (
                    <div
                      key={t.id}
                      className="grid grid-cols-12 gap-1 items-center py-1.5 hover:bg-brand-surface/40 rounded px-1 transition-colors"
                    >
                      <div className="col-span-4 flex items-center gap-2 truncate">
                        <span className="font-mono text-[10px] font-bold text-brand-headline px-1 rounded bg-brand-surface border border-brand-border">
                          {t.id}
                        </span>
                        <span className="text-xs text-brand-body truncate" title={t.title}>
                          {t.title}
                        </span>
                      </div>
                      <div className="col-span-8 relative h-6 bg-brand-surface/60 rounded flex items-center px-1">
                        <div
                          style={{
                            marginLeft: `${leftPct}%`,
                            width: `${widthPct}%`,
                          }}
                          className={`h-4 rounded flex items-center justify-between px-1.5 text-[9px] font-bold text-white shadow-xs truncate ${
                            t.is_critical ? "bg-rose-500" : "bg-indigo-600"
                          }`}
                          title={`Day ${t.start_day}-${t.finish_day} (${t.points} pts) - Owner: ${t.owner}`}
                        >
                          <span className="truncate">{t.points}d</span>
                          <span className="opacity-80 text-[8px] truncate">{t.role}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Mermaid Syntax Preview */}
            {gantt?.mermaid_diagram && (
              <div className="p-4 rounded-xl bg-brand-surface border border-brand-border">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-brand-headline">
                    Mermaid Gantt Syntax
                  </span>
                </div>
                <pre className="font-mono text-xs text-brand-body overflow-x-auto p-2 bg-brand-card rounded border border-brand-border">
                  {gantt.mermaid_diagram}
                </pre>
              </div>
            )}
          </div>
        )}

        {activeTab === "critical_path" && (
          <div className="space-y-4">
            <div className="p-5 rounded-xl bg-brand-card border border-brand-border">
              <h4 className="text-xs font-bold text-brand-headline uppercase tracking-wider mb-2 flex items-center gap-2">
                <GitBranch className="w-4 h-4 text-rose-500" />
                Critical Path Sequence (Longest Chain)
              </h4>
              <p className="text-xs text-brand-muted mb-4">
                The critical path dictates the minimum time required to deliver the project. Any delay in these
                stories directly extends the total delivery date.
              </p>

              <div className="flex flex-wrap items-center gap-2">
                {criticalPath?.critical_path_story_ids.map((cid, idx) => (
                  <React.Fragment key={cid}>
                    <div className="px-3 py-2 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-600 dark:text-rose-400 flex items-center gap-2 font-mono text-xs font-bold shadow-xs">
                      <span>{cid}</span>
                      <span className="text-[10px] px-1 py-0.5 rounded bg-rose-500 text-white">
                        {criticalPath.story_schedules?.[cid]?.duration_days || 1} pts
                      </span>
                    </div>
                    {idx < (criticalPath.critical_path_story_ids.length - 1) && (
                      <ArrowRight className="w-4 h-4 text-brand-muted" />
                    )}
                  </React.Fragment>
                ))}
              </div>

              <div className="grid grid-cols-2 gap-4 mt-6 pt-4 border-t border-brand-border">
                <div>
                  <div className="text-[10px] text-brand-muted uppercase font-bold">Total Critical Points</div>
                  <div className="text-lg font-bold text-rose-500">{criticalPath?.total_critical_points || 0} pts</div>
                </div>
                <div>
                  <div className="text-[10px] text-brand-muted uppercase font-bold">Estimated Earliest Finish</div>
                  <div className="text-lg font-bold text-brand-headline">Day {criticalPath?.estimated_days || 0}</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === "load" && (
          <div className="p-4 rounded-xl bg-brand-card border border-brand-border">
            <h4 className="text-xs font-bold text-brand-headline uppercase tracking-wider mb-3 flex items-center gap-2">
              <Users className="w-4 h-4 text-indigo-500" />
              Agent Workload & Sizing Balance
            </h4>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-brand-surface text-brand-muted border-b border-brand-border font-medium">
                  <tr>
                    <th className="py-2 px-3">Agent Owner</th>
                    <th className="py-2 px-3">Role</th>
                    <th className="py-2 px-3">Story Count</th>
                    <th className="py-2 px-3">Total Points</th>
                    <th className="py-2 px-3">Assigned Stories</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-brand-border/60">
                  {Object.entries(loadBalance?.by_owner || {}).map(([ownerId, info]) => (
                    <tr key={ownerId} className="hover:bg-brand-surface/40">
                      <td className="py-2.5 px-3 font-mono font-bold text-brand-headline">
                        {ownerId}
                      </td>
                      <td className="py-2.5 px-3 uppercase font-bold text-[10px] text-brand-muted">
                        {info.role}
                      </td>
                      <td className="py-2.5 px-3 font-semibold text-brand-body">
                        {info.story_count}
                      </td>
                      <td className="py-2.5 px-3 font-bold text-indigo-600 dark:text-indigo-400">
                        {info.points} pts
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[10px] text-brand-muted">
                        {info.stories?.join(", ") || "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activeTab === "markdown" && (
          <div className="p-5 rounded-xl bg-brand-card border border-brand-border relative">
            <button
              onClick={handleCopy}
              className="absolute top-4 right-4 p-1.5 rounded-lg border border-brand-border hover:bg-brand-surface text-brand-muted hover:text-brand-headline transition-all"
            >
              {copied ? <Check className="w-4 h-4 text-emerald-500" /> : <Copy className="w-4 h-4" />}
            </button>
            <pre className="font-mono text-xs text-brand-headline whitespace-pre-wrap">
              {planContent || "*No implementation plan content available.*"}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
};
