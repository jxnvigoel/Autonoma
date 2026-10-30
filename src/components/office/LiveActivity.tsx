import React, { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Clock, Loader2 } from "lucide-react";
import { JobKind, JobStatus, apiGetJob } from "../../lib/engine";

interface LiveActivityProps {
  sessionId: string | null;
  /** Stage jobs this workstation shows (e.g. the Architect shows feasibility and architecture). */
  kinds: JobKind[];
  /** True while the context knows one of these stages is running. */
  active: boolean;
  title: string;
}

const since = (iso?: string) => (iso ? Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000)) : 0);
const fmt = (s: number) => (s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`);
const short = (m?: string) => (m ? m.split("/").pop() : "");

/**
 * What the agent is actually doing while a stage runs: the model call in flight (or the wait it is in)
 * and every finished step, read live from the engine job, not a canned animation.
 */
export const LiveActivity: React.FC<LiveActivityProps> = ({ sessionId, kinds, active, title }) => {
  const [job, setJob] = useState<JobStatus | null>(null);
  const [, tick] = useState(0);

  useEffect(() => {
    if (!sessionId || !active) {
      setJob(null);
      return;
    }
    let alive = true;
    const load = async () => {
      for (const kind of kinds) {
        const j = await apiGetJob(kind, sessionId).catch(() => null);
        if (alive && j?.status === "running") {
          setJob(j);
          return;
        }
      }
    };
    load();
    const poll = setInterval(load, 1500);
    const clock = setInterval(() => tick((t) => t + 1), 1000);
    return () => {
      alive = false;
      clearInterval(poll);
      clearInterval(clock);
    };
  }, [sessionId, active, kinds.join(",")]);

  if (!active) return null;
  const cur = job?.current;
  const done = (job?.activity || []).filter((a) => a.phase === "done").slice(-6).reverse();

  return (
    <div className="m-4 rounded-xl border border-brand-accent/30 bg-brand-accent/5 p-3 text-xs space-y-2" aria-live="polite">
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 font-bold text-brand-headline">
          <Loader2 className="w-3.5 h-3.5 animate-spin text-brand-accent" />
          {title}
        </span>
        <span className="font-mono text-[10px] text-brand-body">
          {fmt(since(job?.started_at))}
          {job?.stats ? ` · ${job.stats.calls} model calls · ${job.stats.tokens.toLocaleString()} tokens` : ""}
        </span>
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={cur ? `${cur.task_id}-${cur.phase}-${cur.at}` : "between"}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          className="flex items-start gap-2 rounded-lg bg-brand-card border border-brand-border px-2.5 py-2"
        >
          {cur?.phase === "waiting" ? (
            <>
              <Clock className="w-3.5 h-3.5 text-amber-500 shrink-0 mt-0.5" />
              <span className="text-brand-headline">
                {cur.label}: waiting{cur.reason ? ` (${cur.reason})` : ""}
                {cur.wait_s ? `, about ${fmt(Math.max(0, cur.wait_s - since(cur.at)))} left` : ""}
              </span>
            </>
          ) : cur ? (
            <>
              <span className="flex gap-0.5 mt-1.5 shrink-0">
                {[0, 1, 2].map((d) => (
                  <motion.span
                    key={d}
                    className="w-1 h-1 rounded-full bg-brand-accent"
                    animate={{ opacity: [0.3, 1, 0.3] }}
                    transition={{ duration: 1.1, repeat: Infinity, delay: d * 0.15 }}
                  />
                ))}
              </span>
              <span className="text-brand-headline">
                {cur.label}
                <span className="text-brand-body font-mono text-[10px]">
                  {" "}
                  · {short(cur.model)} · {fmt(since(cur.at))}
                </span>
              </span>
            </>
          ) : (
            <span className="text-brand-body">
              {job ? "Checking the result in code before the next step…" : "Starting…"}
            </span>
          )}
        </motion.div>
      </AnimatePresence>

      {done.length > 0 && (
        <ul className="space-y-1">
          {done.map((a, i) => (
            <motion.li
              key={`${a.at}-${i}`}
              initial={{ opacity: 0, x: -4 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center gap-2 text-brand-body"
            >
              <CheckCircle2 className="w-3 h-3 text-emerald-500 shrink-0" />
              <span className="truncate">{a.label}</span>
              <span className="ml-auto font-mono text-[10px] shrink-0">
                {short(a.model)}
                {a.tokens ? ` · ${a.tokens.toLocaleString()} tok` : ""}
                {a.ms ? ` · ${(a.ms / 1000).toFixed(1)}s` : ""}
              </span>
            </motion.li>
          ))}
        </ul>
      )}
      <p className="text-[10px] text-brand-body/80">
        You can leave this screen; the work continues on the engine and this view picks it up again.
      </p>
    </div>
  );
};

export default LiveActivity;
