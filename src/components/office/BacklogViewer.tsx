import React, { useState } from "react";
import {
  ListChecks,
  Users,
  Copy,
  Check,
  Search,
  Filter,
  ArrowRight,
  Loader2,
  Sparkles,
  Activity,
} from "lucide-react";
import { BacklogData } from "../../lib/engine";

interface BacklogViewerProps {
  backlog: BacklogData | null;
  projectName?: string;
  isGenerating?: boolean;
  onGenerate?: () => void;
  canStart?: boolean;
  onProceedToPlan?: () => void;
  /** Hired agents (id -> name) so each story shows who owns it, not just an id. */
  agentNames?: Record<string, string>;
}

export const BacklogViewer: React.FC<BacklogViewerProps> = ({
  agentNames = {},
  backlog,
  projectName = "Active Project",
  isGenerating = false,
  onGenerate,
  canStart = false,
  onProceedToPlan,
}) => {
  const [activeTab, setActiveTab] = useState<"board" | "table" | "json">("board");
  const [filterRole, setFilterRole] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [copied, setCopied] = useState(false);

  const stories = backlog?.stories || [];
  const totalPoints = stories.reduce((acc, s) => acc + (s.points || 0), 0);
  const roles = Array.from(new Set(stories.map((s) => s.role)));

  const filteredStories = stories.filter((s) => {
    const matchesRole = filterRole === "all" || s.role === filterRole;
    const matchesSearch =
      searchQuery === "" ||
      s.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.owner.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (agentNames[s.owner] || "").toLowerCase().includes(searchQuery.toLowerCase());
    return matchesRole && matchesSearch;
  });

  const handleCopy = () => {
    if (!backlog) return;
    navigator.clipboard.writeText(JSON.stringify(backlog, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!backlog || stories.length === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-8 text-center bg-brand-card/50 rounded-2xl border border-brand-border">
        <div className="w-14 h-14 rounded-2xl bg-orange-500/10 border border-orange-500/20 text-orange-600 dark:text-orange-400 flex items-center justify-center mb-4 shadow-sm">
          <ListChecks className="w-7 h-7" />
        </div>
        <h3 className="text-base font-bold text-brand-headline">
          Scrum Master Backlog (Stage 5)
        </h3>
        <p className="text-xs text-brand-body max-w-md mt-1.5 leading-relaxed">
          The Scrum Master breaks the architecture and PRD into small, testable INVEST stories (&le; 5 points)
          with a walking skeleton proving the architecture first, balanced across the hired agent roster.
        </p>

        {canStart && onGenerate && (
          <button
            type="button"
            onClick={onGenerate}
            disabled={isGenerating}
            className="mt-6 px-5 py-2.5 rounded-xl bg-orange-600 hover:bg-orange-700 text-white font-medium text-xs flex items-center gap-2 shadow-sm transition-all"
          >
            {isGenerating ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Generating Sprint Backlog...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>Generate Backlog (Scrum Master)</span>
              </>
            )}
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col space-y-4">
      {/* Top Bar with Metrics and Tabs */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-4 rounded-xl bg-brand-card border border-brand-border shadow-xs">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-orange-500/10 text-orange-600 dark:text-orange-400 flex items-center justify-center font-bold text-sm">
            <ListChecks className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-brand-headline">
                Sprint Backlog ({stories.length} Stories)
              </h3>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-orange-500/10 text-orange-600 dark:text-orange-400 border border-orange-500/20">
                {totalPoints} Total Story Points
              </span>
            </div>
            <p className="text-xs text-brand-muted">
              {projectName} &bull; Walking skeleton first &bull; INVEST vertical slices &bull; Sized &le; 5 Fibonacci points
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
          <div className="flex p-0.5 rounded-lg bg-brand-surface border border-brand-border">
            <button
              onClick={() => setActiveTab("board")}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                activeTab === "board"
                  ? "bg-brand-card text-brand-headline shadow-xs"
                  : "text-brand-muted hover:text-brand-body"
              }`}
            >
              Board
            </button>
            <button
              onClick={() => setActiveTab("table")}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                activeTab === "table"
                  ? "bg-brand-card text-brand-headline shadow-xs"
                  : "text-brand-muted hover:text-brand-body"
              }`}
            >
              Table View
            </button>
            <button
              onClick={() => setActiveTab("json")}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                activeTab === "json"
                  ? "bg-brand-card text-brand-headline shadow-xs"
                  : "text-brand-muted hover:text-brand-body"
              }`}
            >
              JSON
            </button>
          </div>

          <button
            onClick={handleCopy}
            className="p-1.5 rounded-lg border border-brand-border hover:bg-brand-surface text-brand-muted hover:text-brand-headline transition-all"
            title="Copy backlog JSON"
          >
            {copied ? <Check className="w-4 h-4 text-emerald-500" /> : <Copy className="w-4 h-4" />}
          </button>

          {onProceedToPlan && (
            <button
              onClick={onProceedToPlan}
              className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-medium flex items-center gap-1.5 shadow-xs transition-all"
            >
              <span>View Plan</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-1">
        <div className="relative w-full sm:w-72">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-brand-muted" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by ID, title, owner..."
            className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-brand-card border border-brand-border text-xs text-brand-headline placeholder:text-brand-muted focus:outline-hidden focus:ring-1 focus:ring-brand-accent"
          />
        </div>

        <div className="flex items-center gap-2 self-end">
          <Filter className="w-3.5 h-3.5 text-brand-muted" />
          <span className="text-xs text-brand-muted">Role:</span>
          <select
            value={filterRole}
            onChange={(e) => setFilterRole(e.target.value)}
            className="px-2.5 py-1 rounded-lg bg-brand-card border border-brand-border text-xs text-brand-headline focus:outline-hidden"
          >
            <option value="all">All Roles ({stories.length})</option>
            {roles.map((r) => (
              <option key={r} value={r}>
                {r.toUpperCase()}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Content Tabs */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {activeTab === "board" && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 pb-4">
            {filteredStories.map((s) => (
              <div
                key={s.id}
                className={`p-4 rounded-xl bg-brand-card border transition-all flex flex-col justify-between ${
                  s.id === "ST-001"
                    ? "border-amber-500/50 shadow-sm ring-1 ring-amber-500/20"
                    : "border-brand-border hover:border-brand-accent/40"
                }`}
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono text-xs font-bold text-brand-headline px-1.5 py-0.5 rounded bg-brand-surface border border-brand-border">
                        {s.id}
                      </span>
                      {s.id === "ST-001" && (
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/30">
                          Walking Skeleton
                        </span>
                      )}
                      {s.needs_perf && (
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/30 flex items-center gap-0.5">
                          <Activity className="w-2.5 h-2.5" />
                          Perf QA
                        </span>
                      )}
                    </div>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
                      {s.points} pts
                    </span>
                  </div>

                  <h4 className="text-xs font-semibold text-brand-headline leading-snug line-clamp-2 mb-3">
                    {s.title}
                  </h4>

                  {/* Ref Badges */}
                  <div className="space-y-1.5 mb-3">
                    {s.refs?.ac && s.refs.ac.length > 0 && (
                      <div className="flex flex-wrap gap-1 items-center">
                        <span className="text-[10px] text-brand-muted">AC:</span>
                        {s.refs.ac.map((ac) => (
                          <span
                            key={ac}
                            className="font-mono text-[9px] px-1 py-0.5 rounded bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20"
                          >
                            {ac}
                          </span>
                        ))}
                      </div>
                    )}
                    {s.refs?.api && s.refs.api.length > 0 && (
                      <div className="flex flex-wrap gap-1 items-center">
                        <span className="text-[10px] text-brand-muted">API:</span>
                        {s.refs.api.map((api) => (
                          <span
                            key={api}
                            className="font-mono text-[9px] px-1 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
                          >
                            {api}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Dependencies */}
                  {s.depends_on && s.depends_on.length > 0 && (
                    <div className="text-[10px] text-brand-muted mb-2">
                      <span className="font-medium">Depends on:</span>{" "}
                      <span className="font-mono text-brand-body">
                        {s.depends_on.join(", ")}
                      </span>
                    </div>
                  )}
                </div>

                {/* Footer: Owner & Role */}
                <div className="pt-3 border-t border-brand-border/60 flex items-center justify-between text-[11px]">
                  <div className="flex items-center gap-1.5 text-brand-muted">
                    <Users className="w-3.5 h-3.5" />
                    <span className="font-medium text-brand-headline" title={s.owner}>{agentNames[s.owner] || s.owner}</span>
                  </div>
                  <span className="px-2 py-0.5 rounded uppercase font-bold text-[9px] bg-brand-surface text-brand-muted border border-brand-border">
                    {s.role}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === "table" && (
          <div className="rounded-xl border border-brand-border bg-brand-card overflow-hidden">
            <table className="w-full text-left text-xs">
              <thead className="bg-brand-surface text-brand-muted border-b border-brand-border font-medium">
                <tr>
                  <th className="py-2.5 px-3">ID</th>
                  <th className="py-2.5 px-3">Title</th>
                  <th className="py-2.5 px-3">Role</th>
                  <th className="py-2.5 px-3">Owner</th>
                  <th className="py-2.5 px-3">Points</th>
                  <th className="py-2.5 px-3">Cited ACs</th>
                  <th className="py-2.5 px-3">Dependencies</th>
                  <th className="py-2.5 px-3">Perf?</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-brand-border/60">
                {filteredStories.map((s) => (
                  <tr key={s.id} className="hover:bg-brand-surface/50 transition-colors">
                    <td className="py-2.5 px-3 font-mono font-bold text-brand-headline">
                      {s.id}
                    </td>
                    <td className="py-2.5 px-3 font-medium text-brand-headline max-w-xs">
                      {s.title}
                    </td>
                    <td className="py-2.5 px-3">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-brand-surface text-brand-body uppercase border border-brand-border">
                        {s.role}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-brand-body font-mono text-[11px]">
                      {agentNames[s.owner] ? `${agentNames[s.owner]} (${s.owner})` : s.owner}
                    </td>
                    <td className="py-2.5 px-3 font-bold text-indigo-600 dark:text-indigo-400">
                      {s.points}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[10px] text-blue-600 dark:text-blue-400">
                      {s.refs?.ac?.join(", ") || "-"}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[10px] text-brand-muted">
                      {s.depends_on?.join(", ") || "None"}
                    </td>
                    <td className="py-2.5 px-3">
                      {s.needs_perf ? (
                        <span className="text-[10px] font-bold text-rose-500">YES</span>
                      ) : (
                        <span className="text-[10px] text-brand-muted">No</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === "json" && (
          <div className="p-4 rounded-xl bg-brand-surface border border-brand-border">
            <pre className="font-mono text-xs text-brand-headline overflow-x-auto">
              {JSON.stringify(backlog, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
};
