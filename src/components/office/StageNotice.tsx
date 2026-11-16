import React, { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, Loader2, PauseCircle, X } from "lucide-react";
import { BudgetGuardStatus, JobKind, JobStatus, apiGetBudgetStatus, apiGetJob, apiRaiseBudget } from "../../lib/engine";

const BUDGET_RE = /budget exhausted|budget reached|raises? the budget/i;
const n = (v: number) => v.toLocaleString("en-US");

/** A practical new limit: well clear of what is already spent, in round numbers. */
const suggestLimit = (g: BudgetGuardStatus) =>
  Math.max(1_000_000, Math.ceil((g.spent_tokens * 3) / 500_000) * 500_000, g.budget_limit_tokens * 2);

const jobErrorText = (job: JobStatus): string => {
  if (job.status === "interrupted") {
    return "This stage was interrupted: the engine stopped before it finished. Run it again.";
  }
  const e = job.error;
  return typeof e === "string" ? e : e ? JSON.stringify(e) : `The ${job.kind} stage ${job.status}.`;
};

/** What the user can do about a failure, when the message makes that clear. */
const hintFor = (text: string): string | null => {
  if (/tokens per day|daily quota|rate limit|\b429\b|quota used up/i.test(text)) {
    return "Groq's free limit for this model is used up. Wait for it to reset, or run the agents on a local Ollama model.";
  }
  if (/GROQ_API_KEY|api key|cloud is disabled|GroqKeyMissing/i.test(text)) {
    return "Add GROQ_API_KEY to the .env file, or run the agents on a local Ollama model.";
  }
  if (/did not finish within|too slow on this machine/i.test(text)) {
    return "The local model is too slow for this step on this computer. Close other apps, or install a smaller model.";
  }
  if (/no local model|no usable model|is not installed in ollama|ollama (is )?not (reachable|running)|NoLocalModel|ollama pull/i.test(text)) {
    return "The agents run on Ollama. Open the Ollama app, and install a model once with: ollama pull qwen2.5-coder:7b";
  }
  if (/failed to fetch|networkerror|ECONNREFUSED/i.test(text)) {
    return "The engine did not answer. Check that the app's engine is running, then try again.";
  }
  return null;
};

/**
 * Shown when the project's token budget is at 100% (Handbook 26.4: hard pause until the client raises
 * the budget). Every model call is refused while paused, so this is where the client raises it.
 */
export const BudgetPausedBanner: React.FC<{
  sessionId: string | null;
  /** Changes whenever the budget may have moved (an error arrived, a stage ended). */
  refreshKey?: unknown;
  onRaised?: (guard: BudgetGuardStatus) => void;
  className?: string;
}> = ({ sessionId, refreshKey, onRaised, className = "m-4" }) => {
  const [guard, setGuard] = useState<BudgetGuardStatus | null>(null);
  const [limit, setLimit] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [raisedTo, setRaisedTo] = useState<number | null>(null);

  useEffect(() => {
    if (!sessionId) {
      setGuard(null);
      return;
    }
    let alive = true;
    const load = () =>
      apiGetBudgetStatus(sessionId)
        .then((r) => {
          if (!alive) return;
          setGuard(r.guard);
          if (r.guard.pause_100) {
            setRaisedTo(null);
            setLimit((cur) => cur || String(suggestLimit(r.guard)));
          }
        })
        .catch(() => undefined);
    load();
    // A running stage can use up the budget at any moment; keep the banner honest without a reload.
    const poll = setInterval(load, 15000);
    return () => {
      alive = false;
      clearInterval(poll);
    };
  }, [sessionId, refreshKey]);

  useEffect(() => {
    setLimit("");
    setRaisedTo(null);
    setProblem(null);
  }, [sessionId]);

  if (!sessionId || !guard) return null;

  if (!guard.pause_100) {
    if (raisedTo === null) return null;
    return (
      <div className={`${className} p-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-xs flex items-start gap-2 text-emerald-700 dark:text-emerald-300`}>
        <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
        <span className="flex-1">
          Budget raised to {n(raisedTo)} tokens. The agents can work again: run the stage you wanted.
        </span>
        <button type="button" onClick={() => setRaisedTo(null)} aria-label="Dismiss" className="cursor-pointer opacity-70 hover:opacity-100">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    );
  }

  const tokensOver = guard.token_percent >= 100;
  const value = Number(limit.replace(/[,\s_]/g, ""));
  const valid = Number.isFinite(value) && value > (tokensOver ? guard.spent_tokens : 0);

  const raise = async () => {
    if (!valid || busy) return;
    setBusy(true);
    setProblem(null);
    try {
      const next = tokensOver
        ? await apiRaiseBudget(sessionId, { tokens: Math.round(value) })
        : await apiRaiseBudget(sessionId, { usd: value });
      setGuard(next);
      if (next.pause_100) {
        setProblem("That is still below what the project has already used. Enter a higher limit.");
      } else {
        setRaisedTo(tokensOver ? Math.round(value) : next.budget_limit_tokens);
        onRaised?.(next);
      }
    } catch (e) {
      setProblem(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={`${className} p-3 rounded-xl border border-amber-500/40 bg-amber-500/10 text-xs space-y-2`} role="alert">
      <div className="flex items-center gap-2 font-bold text-amber-700 dark:text-amber-300">
        <PauseCircle className="w-4 h-4 shrink-0" />
        <span>Budget used up: the agents are paused</span>
      </div>
      <p className="text-[11px] text-brand-body leading-relaxed">
        {tokensOver ? (
          <>
            This project has used <b>{n(guard.spent_tokens)}</b> of its <b>{n(guard.budget_limit_tokens)}</b> token budget (
            {Math.round(guard.token_percent)}%).
          </>
        ) : (
          <>
            This project has spent <b>${guard.spent_cost_usd.toFixed(2)}</b> of its <b>${guard.budget_limit_usd}</b> budget.
          </>
        )}{" "}
        No agent can run, and the buttons that start a stage will fail, until you raise the budget. A PRD plus architecture
        usually takes 100,000 to 500,000 tokens; building the product takes millions.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <label className="text-[11px] font-semibold text-brand-headline" htmlFor="budget-new-limit">
          {tokensOver ? "New token limit" : "New budget (USD)"}
        </label>
        <input
          id="budget-new-limit"
          value={limit}
          onChange={(e) => setLimit(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && raise()}
          inputMode="numeric"
          className="w-36 rounded-md border border-brand-border bg-brand-card px-2 py-1 text-xs font-mono text-brand-headline focus:outline-none focus:ring-1 focus:ring-amber-500"
        />
        <button
          type="button"
          onClick={raise}
          disabled={!valid || busy}
          className="px-3 py-1 rounded-md bg-amber-600 hover:bg-amber-500 text-white text-[11px] font-semibold cursor-pointer flex items-center gap-1.5 disabled:opacity-50"
        >
          {busy && <Loader2 className="w-3 h-3 animate-spin" />}
          Raise budget
        </button>
      </div>
      {problem && <p className="text-[11px] text-rose-600 dark:text-rose-300">{problem}</p>}
    </div>
  );
};

/**
 * Why a stage button "did nothing": the error from the action just taken, or the reason the desk's last
 * run failed (kept by the engine, so it is still here after leaving the screen or restarting the app).
 */
export const StageNotice: React.FC<{
  sessionId: string | null;
  /** Stage jobs of the desk on screen. */
  kinds: JobKind[];
  /** True while one of those stages is running. */
  active: boolean;
  /** The error from what the user just did. */
  error: string | null;
  onDismissError: () => void;
  onBudgetRaised?: () => void;
  /** Runs the failed stage again (a desk whose documents already exist shows no other button for it). */
  onRetry?: (kind: JobKind) => void;
}> = ({ sessionId, kinds, active, error, onDismissError, onBudgetRaised, onRetry }) => {
  const [failed, setFailed] = useState<JobStatus | null>(null);
  const [dismissed, setDismissed] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);
  const [budgetTick, setBudgetTick] = useState(0);
  const kindsKey = kinds.join(",");

  useEffect(() => {
    setFailed(null);
    if (!sessionId || active || kinds.length === 0) return;
    let alive = true;
    (async () => {
      const jobs = await Promise.all(kinds.map((k) => apiGetJob(k, sessionId).catch(() => null)));
      const bad = jobs
        .filter((j): j is JobStatus => !!j && (j.status === "failed" || j.status === "interrupted"))
        .sort((a, b) => String(b.finished_at || b.started_at || "").localeCompare(String(a.finished_at || a.started_at || "")));
      if (alive) setFailed(bad[0] || null);
    })();
    return () => {
      alive = false;
    };
  }, [sessionId, kindsKey, active]);

  useEffect(() => {
    if (!sessionId) {
      setPaused(false);
      return;
    }
    let alive = true;
    apiGetBudgetStatus(sessionId)
      .then((r) => alive && setPaused(!!r.guard.pause_100))
      .catch(() => alive && setPaused(false));
    return () => {
      alive = false;
    };
  }, [sessionId, error, active, budgetTick]);

  const failedKey = failed ? `${failed.kind}:${failed.started_at}` : null;
  const jobText = failed && failedKey !== dismissed ? jobErrorText(failed) : null;
  // A budget failure is explained by the budget banner; once the budget is raised an old one is no longer true.
  const isBudget = (t: string | null) => !!t && BUDGET_RE.test(t);
  const text = error ? (isBudget(error) && paused ? null : error) : isBudget(jobText) ? null : jobText;
  const hint = text ? hintFor(text) : null;

  return (
    <>
      <BudgetPausedBanner
        sessionId={sessionId}
        refreshKey={`${error}|${active}|${budgetTick}`}
        onRaised={() => {
          setBudgetTick((t) => t + 1);
          if (error && BUDGET_RE.test(error)) onDismissError();
          onBudgetRaised?.();
        }}
      />
      {text && !active && (
        <div className="m-4 p-3 rounded-xl border border-rose-500/30 bg-rose-500/10 text-xs flex items-start gap-2" role="alert">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-rose-500" />
          <div className="flex-1 min-w-0 space-y-1">
            <p className="font-bold text-rose-700 dark:text-rose-300">
              {error ? "That did not work" : `The last ${failed?.kind === "pm" ? "PM" : failed?.kind} run did not finish`}
            </p>
            <p className="text-[11px] text-rose-700 dark:text-rose-300 whitespace-pre-wrap break-words max-h-40 overflow-y-auto">
              {text}
            </p>
            {hint && <p className="text-[11px] text-brand-body">{hint}</p>}
            {failed && onRetry && !paused && (
              <button
                type="button"
                onClick={() => {
                  if (error) onDismissError();
                  onRetry(failed.kind);
                }}
                className="mt-1 px-3 py-1 rounded-md bg-rose-600 hover:bg-rose-500 text-white text-[11px] font-semibold cursor-pointer"
              >
                Run again
              </button>
            )}
          </div>
          <button
            type="button"
            onClick={() => (error ? onDismissError() : setDismissed(failedKey))}
            aria-label="Dismiss"
            className="cursor-pointer text-rose-700 dark:text-rose-300 opacity-70 hover:opacity-100"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </>
  );
};
