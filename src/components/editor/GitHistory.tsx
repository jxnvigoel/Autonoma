import React, { useCallback, useEffect, useState } from "react";
import { GitCommit, RefreshCw } from "lucide-react";
import { ProjectCommit, apiGetProjectCommit, apiGetProjectGit } from "../../lib/engine";
import { cn } from "../../lib/utils";

interface GitHistoryProps {
  sessionId: string;
  /** Opens a commit's diff as a read-only editor tab. */
  onOpenDiff: (title: string, diff: string) => void;
  /** Poll while the agents are building, so new commits appear as they land. */
  live: boolean;
}

const ago = (iso: string) => {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  return s < 60 ? "just now" : s < 3600 ? `${Math.floor(s / 60)}m ago` : s < 86400 ? `${Math.floor(s / 3600)}h ago` : `${Math.floor(s / 86400)}d ago`;
};

/** The project's commit history: what each agent changed, newest first (read-only). */
export const GitHistory: React.FC<GitHistoryProps> = ({ sessionId, onOpenDiff, live }) => {
  const [data, setData] = useState<{ branch: string; commits: ProjectCommit[]; uncommitted: string[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [opening, setOpening] = useState<string | null>(null);

  const load = useCallback(() => {
    apiGetProjectGit(sessionId)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [sessionId]);

  useEffect(() => {
    load();
    if (!live) return;
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load, live]);

  const open = async (c: ProjectCommit) => {
    setOpening(c.sha);
    try {
      const d = await apiGetProjectCommit(sessionId, c.sha);
      onOpenDiff(`${c.sha}.diff`, d.diff + (d.truncated ? "\n\n[diff truncated]" : ""));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setOpening(null);
    }
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="p-2 border-b border-brand-border flex items-center justify-between text-xs shrink-0">
        <span className="font-semibold text-brand-headline">
          History {data?.branch && <span className="font-mono text-[10px] text-brand-body">({data.branch})</span>}
        </span>
        <button type="button" onClick={load} className="p-1 rounded hover:bg-brand-subtle cursor-pointer" title="Refresh history">
          <RefreshCw className="w-3.5 h-3.5 text-brand-body" />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-1.5 space-y-0.5">
        {error && <p className="text-[11px] text-brand-body p-2">{error}</p>}
        {data?.uncommitted.length ? (
          <div className="p-2 rounded bg-amber-500/10 text-[11px] text-amber-700 dark:text-amber-300">
            Not committed: {data.uncommitted.join(", ")}
          </div>
        ) : null}
        {data?.commits.map((c) => (
          <button
            key={c.sha}
            type="button"
            onClick={() => open(c)}
            className={cn("w-full text-left rounded-lg px-2 py-1.5 hover:bg-brand-subtle cursor-pointer", opening === c.sha && "opacity-60")}
            title="Open this commit's changes"
          >
            <div className="flex items-start gap-1.5">
              <GitCommit className="w-3.5 h-3.5 text-brand-accent shrink-0 mt-0.5" />
              <span className="text-[11px] text-brand-headline leading-snug">{c.subject}</span>
            </div>
            <div className="pl-5 flex flex-wrap gap-x-2 text-[10px] font-mono text-brand-body">
              <span>{c.sha}</span>
              <span>{c.author}</span>
              <span>{ago(c.at)}</span>
              <span className="text-emerald-600">+{c.insertions}</span>
              <span className="text-rose-600">-{c.deletions}</span>
            </div>
          </button>
        ))}
        {data && !data.commits.length && <p className="text-[11px] text-brand-body p-2">No commits yet.</p>}
      </div>
    </div>
  );
};

export default GitHistory;
