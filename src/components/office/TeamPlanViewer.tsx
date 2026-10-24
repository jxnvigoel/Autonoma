import React, { useState } from "react";
import {
  Users,
  Copy,
  Check,
  AlertTriangle,
  CheckCircle2,
  Sparkles,
  Loader2,
  ArrowRight,
  TrendingUp,
  Award,
} from "lucide-react";

import { TeamPlanData } from "../../lib/engine";

interface TeamPlanViewerProps {
  teamPlan: TeamPlanData | null;
  projectName?: string;
  isGenerating?: boolean;
  onGenerate?: () => void;
  canStart?: boolean;
  onProceedToHiring?: () => void;
}

export const TeamPlanViewer: React.FC<TeamPlanViewerProps> = ({
  teamPlan,
  projectName = "Active Project",
  isGenerating = false,
  onGenerate,
  canStart = false,
  onProceedToHiring,
}) => {
  const [activeTab, setActiveTab] = useState<"plan" | "requisitions" | "coverage" | "json">("plan");
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (!teamPlan) return;
    navigator.clipboard.writeText(JSON.stringify(teamPlan, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!teamPlan) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-8 text-center bg-brand-card/50 rounded-2xl border border-brand-border">
        <div className="w-14 h-14 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-600 dark:text-indigo-400 flex items-center justify-center mb-4 shadow-sm">
          <Users className="w-7 h-7" />
        </div>
        <h3 className="text-base font-bold text-brand-headline">
          HR Staffing Planner (Stage 4)
        </h3>
        <p className="text-xs text-brand-body max-w-md mt-1.5 leading-relaxed">
          The HR Staffing Planner reads the Technical Architecture (§10/12 Team plan), PRD features, and estimate.json
          to compute exact team sizing, role merging, and staggered schedules per Handbook Chapter 6.1 and 6.2.
        </p>

        {canStart && onGenerate && (
          <button
            type="button"
            onClick={onGenerate}
            disabled={isGenerating}
            className="mt-6 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs shadow-md transition-all flex items-center gap-2 cursor-pointer disabled:opacity-50"
          >
            {isGenerating ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Computing Sizing Arithmetic & Justifications...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>Generate Team Plan (docs/team-plan.json)</span>
              </>
            )}
          </button>
        )}

        {!canStart && (
          <div className="mt-4 flex items-center gap-1.5 text-xs text-amber-600 dark:text-amber-400 bg-amber-500/10 px-3 py-1.5 rounded-lg border border-amber-500/20">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
            <span>Architecture blueprint must be completed first.</span>
          </div>
        )}
      </div>
    );
  }

  const reqs = teamPlan.requisitions || [];
  const totalHeadcount = reqs.reduce((sum, r) => sum + (r.count || 1), 0);

  return (
    <div className="h-full flex flex-col overflow-hidden bg-brand-card/50 rounded-2xl border border-brand-border shadow-card">
      {/* Header bar */}
      <div className="px-4 py-3 border-b border-brand-border bg-brand-card flex flex-wrap items-center justify-between gap-3 shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-indigo-500/15 text-indigo-600 dark:text-indigo-400 flex items-center justify-center font-bold">
            <Users className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-brand-headline">
                Staffing & Team Plan
              </h3>
              <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30">
                docs/team-plan.json
              </span>
            </div>
            <p className="text-[11px] text-brand-body">
              {projectName} • Sizing arithmetic derived from PRD & Architecture
            </p>
          </div>
        </div>

        {/* Tab Switcher & Actions */}
        <div className="flex items-center gap-2">
          <div className="flex items-center p-0.5 rounded-lg bg-brand-subtle border border-brand-border text-xs">
            <button
              type="button"
              onClick={() => setActiveTab("plan")}
              className={`px-2.5 py-1 rounded-md font-medium text-[11px] transition-all cursor-pointer ${
                activeTab === "plan"
                  ? "bg-brand-card text-brand-headline shadow-2xs font-bold"
                  : "text-brand-body hover:text-brand-headline"
              }`}
            >
              Overview
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("requisitions")}
              className={`px-2.5 py-1 rounded-md font-medium text-[11px] transition-all cursor-pointer ${
                activeTab === "requisitions"
                  ? "bg-brand-card text-brand-headline shadow-2xs font-bold"
                  : "text-brand-body hover:text-brand-headline"
              }`}
            >
              Seats ({reqs.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("coverage")}
              className={`px-2.5 py-1 rounded-md font-medium text-[11px] transition-all cursor-pointer ${
                activeTab === "coverage"
                  ? "bg-brand-card text-brand-headline shadow-2xs font-bold"
                  : "text-brand-body hover:text-brand-headline"
              }`}
            >
              Coverage ({teamPlan.features_covered?.length || 0})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("json")}
              className={`px-2.5 py-1 rounded-md font-medium text-[11px] transition-all cursor-pointer ${
                activeTab === "json"
                  ? "bg-brand-card text-brand-headline shadow-2xs font-bold"
                  : "text-brand-body hover:text-brand-headline"
              }`}
            >
              Raw JSON
            </button>
          </div>

          <button
            type="button"
            onClick={handleCopy}
            className="p-1.5 rounded-lg border border-brand-border bg-brand-card hover:bg-brand-subtle text-brand-body transition-colors cursor-pointer"
            title="Copy JSON"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
          </button>

          {onProceedToHiring && (
            <button
              type="button"
              onClick={onProceedToHiring}
              className="px-3 py-1.5 rounded-lg bg-teal-600 hover:bg-teal-500 text-white font-semibold text-xs transition-all shadow-xs flex items-center gap-1.5 cursor-pointer"
            >
              <span>Recruiter Handoff</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Main Content Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* OVERVIEW TAB */}
        {activeTab === "plan" && (
          <div className="space-y-4">
            {/* Metric KPI cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-3 rounded-xl bg-brand-card border border-brand-border shadow-2xs">
                <span className="text-[11px] font-medium text-brand-body block">Total Project Weeks</span>
                <span className="text-xl font-extrabold text-brand-headline font-mono mt-0.5 block">
                  {teamPlan.total_weeks} wks
                </span>
                <span className="text-[10px] text-brand-body/70 mt-1 block">Timeline span</span>
              </div>

              <div className="p-3 rounded-xl bg-brand-card border border-brand-border shadow-2xs">
                <span className="text-[11px] font-medium text-brand-body block">Headcount-Weeks</span>
                <span className="text-xl font-extrabold text-indigo-600 dark:text-indigo-400 font-mono mt-0.5 block">
                  {teamPlan.total_headcount_weeks}
                </span>
                <span className="text-[10px] text-brand-body/70 mt-1 block">
                  Cap: {teamPlan.headcount_budget_cap} hc-wks
                </span>
              </div>

              <div className="p-3 rounded-xl bg-brand-card border border-brand-border shadow-2xs">
                <span className="text-[11px] font-medium text-brand-body block">Unique Staffed Seats</span>
                <span className="text-xl font-extrabold text-brand-headline font-mono mt-0.5 block">
                  {totalHeadcount} agents
                </span>
                <span className="text-[10px] text-brand-body/70 mt-1 block">{reqs.length} distinct requisitions</span>
              </div>

              <div className="p-3 rounded-xl bg-brand-card border border-brand-border shadow-2xs">
                <span className="text-[11px] font-medium text-brand-body block">Budget Status</span>
                <div className="flex items-center gap-1.5 mt-1">
                  {teamPlan.headcount_over_budget ? (
                    <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-rose-500/15 text-rose-700 dark:text-rose-300 border border-rose-500/30 flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" /> Over Budget
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" /> Within Cap
                    </span>
                  )}
                </div>
                <span className="text-[10px] text-brand-body/70 mt-1 block">Handbook 6.1.4</span>
              </div>
            </div>

            {/* Sizing Arithmetic Basis Callout */}
            <div className="p-3.5 rounded-xl bg-brand-subtle border border-brand-border text-xs space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="font-bold text-brand-headline flex items-center gap-1.5">
                  <TrendingUp className="w-3.5 h-3.5 text-indigo-500" />
                  <span>Sizing Arithmetic Basis (Handbook Chapter 6.1)</span>
                </span>
                <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-indigo-500/15 text-indigo-700 dark:text-indigo-300 border border-indigo-500/30 font-semibold">
                  Assumption [ASM-01]
                </span>
              </div>
              <p className="text-[11px] text-brand-body leading-relaxed">
                Capacity rate: <strong>{teamPlan.points_per_agent_per_week || 4} story points / agent / week</strong>.
                DevOps starts Week 1 for repo and CI scaffolding. QA begins at build week. Performance engineering starts
                after core API stabilization. No idle seats permitted.
              </p>
            </div>

            {/* Requisitions Quick Preview */}
            <div className="space-y-2">
              <h4 className="text-xs font-bold text-brand-headline uppercase tracking-wider font-mono">
                Staffed Requisitions Schedule
              </h4>
              <div className="space-y-2">
                {reqs.map((req) => (
                  <div
                    key={req.seat_id}
                    className="p-3 rounded-xl bg-brand-card border border-brand-border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-2xs"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-brand-subtle flex items-center justify-center font-mono text-xs font-bold text-brand-headline border border-brand-border">
                        {req.seat_id.replace("SEAT-", "")}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-brand-headline text-xs capitalize">{req.role}</span>
                          <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-brand-subtle border border-brand-border text-brand-body">
                            {req.count} {req.count > 1 ? "agents" : "agent"}
                          </span>
                          {req.replaces_roles && req.replaces_roles.length > 0 && (
                            <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/30">
                              Merged: {req.replaces_roles.join(", ")}
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-brand-body mt-0.5 line-clamp-1">{req.why}</p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
                      <span className="text-[11px] font-mono font-semibold px-2 py-0.5 rounded bg-brand-subtle border border-brand-border text-brand-headline">
                        Wk {req.start_week} → Wk {req.end_week}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* REQUISITIONS TAB */}
        {activeTab === "requisitions" && (
          <div className="space-y-3">
            <div className="overflow-x-auto rounded-xl border border-brand-border">
              <table className="w-full text-left text-xs">
                <thead className="bg-brand-card border-b border-brand-border text-brand-body font-mono text-[11px]">
                  <tr>
                    <th className="p-3 font-semibold">Seat ID</th>
                    <th className="p-3 font-semibold">Role</th>
                    <th className="p-3 font-semibold">Count</th>
                    <th className="p-3 font-semibold">Weeks</th>
                    <th className="p-3 font-semibold">Citations (PRD / Arch)</th>
                    <th className="p-3 font-semibold">Justification</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-brand-border bg-brand-bg/40 font-normal">
                  {reqs.map((req) => (
                    <tr key={req.seat_id} className="hover:bg-brand-card/30 transition-colors">
                      <td className="p-3 font-mono font-bold text-brand-headline">{req.seat_id}</td>
                      <td className="p-3 capitalize font-semibold text-brand-headline">{req.role}</td>
                      <td className="p-3 font-mono">{req.count}</td>
                      <td className="p-3 font-mono text-indigo-600 dark:text-indigo-400 font-medium">
                        Wk {req.start_week}–{req.end_week}
                      </td>
                      <td className="p-3">
                        <div className="flex flex-wrap gap-1">
                          {req.refs && req.refs.length > 0 ? (
                            req.refs.map((ref) => (
                              <span
                                key={ref}
                                className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-brand-subtle border border-brand-border text-brand-body"
                              >
                                {ref}
                              </span>
                            ))
                          ) : (
                            <span className="text-brand-body/50 text-[10px]">—</span>
                          )}
                        </div>
                      </td>
                      <td className="p-3 max-w-xs leading-relaxed text-brand-body text-[11px]">{req.why}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* COVERAGE TAB */}
        {activeTab === "coverage" && (
          <div className="space-y-4">
            <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs flex items-center justify-between">
              <div className="flex items-center gap-2 text-emerald-800 dark:text-emerald-300">
                <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-500" />
                <span className="font-bold">
                  Must-Have PRD Feature Coverage Complete
                </span>
              </div>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-800 dark:text-emerald-200 font-bold">
                {teamPlan.unstaffed_must_haves?.length || 0} unstaffed
              </span>
            </div>

            <div className="space-y-2">
              <span className="text-xs font-bold text-brand-headline uppercase tracking-wider font-mono">
                Assigned Features ({teamPlan.features_covered?.length || 0})
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                {teamPlan.features_covered?.map((fid) => (
                  <div
                    key={fid}
                    className="p-2.5 rounded-lg bg-brand-card border border-brand-border flex items-center gap-2 text-xs"
                  >
                    <Award className="w-3.5 h-3.5 text-indigo-500" />
                    <span className="font-mono font-semibold text-brand-headline">{fid}</span>
                    <span className="text-[10px] text-brand-body ml-auto">Covered</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* RAW JSON TAB */}
        {activeTab === "json" && (
          <div className="rounded-xl border border-brand-border overflow-hidden bg-brand-bg">
            <div className="px-3 py-1.5 bg-brand-card border-b border-brand-border flex items-center justify-between text-[11px] font-mono text-brand-body">
              <span>docs/team-plan.json</span>
              <span>UTF-8</span>
            </div>
            <pre className="p-4 font-mono text-xs overflow-x-auto text-brand-headline leading-relaxed">
              {JSON.stringify(teamPlan, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
};
