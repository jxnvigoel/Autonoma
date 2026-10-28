import React, { useState } from "react";
import {
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Copy,
  Check,
  ArrowRight,
  Loader2,
  Sparkles,
} from "lucide-react";
import { ReadinessState } from "../../lib/engine";

interface ReadinessViewerProps {
  readinessState: ReadinessState | null;
  readinessContent?: string;
  isExecutingReview?: boolean;
  onExecuteReview?: () => void;
  canStartReview?: boolean;
  onProceedToBuild?: () => void;
}

export const ReadinessViewer: React.FC<ReadinessViewerProps> = ({
  readinessState,
  readinessContent,
  isExecutingReview = false,
  onExecuteReview,
  canStartReview = false,
  onProceedToBuild,
}) => {
  const [activeTab, setActiveTab] = useState<"summary" | "matrix" | "gaps" | "markdown">("summary");
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (!readinessContent) return;
    navigator.clipboard.writeText(readinessContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const status = readinessState?.status || "not_conducted";
  const verdict = readinessState?.verdict || "not_ready";
  const isReady = status === "ready" && verdict === "ready";
  const isInvalidated = status === "invalidated";
  const gaps = readinessState?.gaps || [];
  const contradictions = readinessState?.contradictions || [];
  const matrix = readinessState?.traceability?.chains || [];

  if (status === "not_conducted" && !readinessContent) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-8 text-center bg-brand-card/50 rounded-2xl border border-brand-border">
        <div className="w-14 h-14 rounded-2xl bg-purple-500/10 border border-purple-500/20 text-purple-600 dark:text-purple-400 flex items-center justify-center mb-4 shadow-sm">
          <ShieldCheck className="w-7 h-7" />
        </div>
        <h3 className="text-base font-bold text-brand-headline">
          Tech Lead Pre-Build Readiness Review (Stage 5 Step 19b)
        </h3>
        <p className="text-xs text-brand-body max-w-md mt-1.5 leading-relaxed">
          Handbook Section 10.1.4: No code is written before the Tech Lead's readiness review says ready.
          The review validates complete traceability (Feature &rarr; Journey &rarr; Endpoint &rarr; Table &rarr; Story &rarr; Test),
          identifies missing specifications, and ensures zero architectural contradictions.
        </p>

        {canStartReview && onExecuteReview && (
          <button
            type="button"
            onClick={onExecuteReview}
            disabled={isExecutingReview}
            className="mt-6 px-5 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-700 text-white font-medium text-xs flex items-center gap-2 shadow-sm transition-all"
          >
            {isExecutingReview ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Running Readiness Review...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>Run Tech Lead Readiness Review</span>
              </>
            )}
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col space-y-4">
      {/* Top Banner with Verdict Status */}
      <div
        className={`p-4 rounded-xl border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-xs transition-all ${
          isReady
            ? "bg-emerald-500/5 border-emerald-500/30"
            : isInvalidated
            ? "bg-amber-500/5 border-amber-500/30"
            : "bg-rose-500/5 border-rose-500/30"
        }`}
      >
        <div className="flex items-center gap-3">
          <div
            className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold ${
              isReady
                ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                : isInvalidated
                ? "bg-amber-500/10 text-amber-600 dark:text-amber-400"
                : "bg-rose-500/10 text-rose-600 dark:text-rose-400"
            }`}
          >
            {isReady ? (
              <CheckCircle2 className="w-5 h-5" />
            ) : isInvalidated ? (
              <AlertTriangle className="w-5 h-5" />
            ) : (
              <XCircle className="w-5 h-5" />
            )}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-brand-headline">
                Tech Lead Readiness Review: {isReady ? "READY" : isInvalidated ? "INVALIDATED" : "NOT READY"}
              </h3>
              <span
                className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                  isReady
                    ? "bg-emerald-500/10 text-emerald-600 border-emerald-500/20"
                    : isInvalidated
                    ? "bg-amber-500/10 text-amber-600 border-amber-500/20"
                    : "bg-rose-500/10 text-rose-600 border-rose-500/20"
                }`}
              >
                {isReady
                  ? "Build Unlocked (HTTP 200)"
                  : isInvalidated
                  ? "Invalidated by Edit (HTTP 403)"
                  : "Build Gate Locked (HTTP 403)"}
              </span>
            </div>
            <p className="text-xs text-brand-muted">
              {isReady
                ? "All Must-have features, endpoints, tables, and stories trace cleanly with zero blocking gaps."
                : isInvalidated
                ? "Backlog, architecture, or PRD was modified after approval. Re-run review required."
                : `${gaps.length} gaps and ${contradictions.length} contradictions block code generation.`}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex p-0.5 rounded-lg bg-brand-surface border border-brand-border">
            <button
              onClick={() => setActiveTab("summary")}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                activeTab === "summary"
                  ? "bg-brand-card text-brand-headline shadow-xs"
                  : "text-brand-muted hover:text-brand-body"
              }`}
            >
              Summary
            </button>
            <button
              onClick={() => setActiveTab("matrix")}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                activeTab === "matrix"
                  ? "bg-brand-card text-brand-headline shadow-xs"
                  : "text-brand-muted hover:text-brand-body"
              }`}
            >
              Traceability Matrix
            </button>
            <button
              onClick={() => setActiveTab("gaps")}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                activeTab === "gaps"
                  ? "bg-brand-card text-brand-headline shadow-xs"
                  : "text-brand-muted hover:text-brand-body"
              }`}
            >
              Gaps ({gaps.length})
            </button>
            <button
              onClick={() => setActiveTab("markdown")}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                activeTab === "markdown"
                  ? "bg-brand-card text-brand-headline shadow-xs"
                  : "text-brand-muted hover:text-brand-body"
              }`}
            >
              Review Doc
            </button>
          </div>

          {onExecuteReview && (
            <button
              onClick={onExecuteReview}
              disabled={isExecutingReview}
              className="p-1.5 rounded-lg border border-brand-border hover:bg-brand-surface text-brand-muted hover:text-brand-headline transition-all"
              title="Re-run review"
            >
              {isExecutingReview ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            </button>
          )}

          {isReady && onProceedToBuild && (
            <button
              onClick={onProceedToBuild}
              className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium flex items-center gap-1.5 shadow-xs transition-all"
            >
              <span>Start Stage 6 Build</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {activeTab === "summary" && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 rounded-xl bg-brand-card border border-brand-border">
                <div className="text-[10px] text-brand-muted uppercase font-bold">Traceability Coverage</div>
                <div className="text-xl font-bold text-brand-headline mt-1">100%</div>
                <div className="text-[11px] text-emerald-600 mt-0.5">All Must-haves linked to stories</div>
              </div>
              <div className="p-4 rounded-xl bg-brand-card border border-brand-border">
                <div className="text-[10px] text-brand-muted uppercase font-bold">Unresolved Gaps</div>
                <div className={`text-xl font-bold mt-1 ${gaps.length === 0 ? "text-emerald-600" : "text-rose-500"}`}>
                  {gaps.length}
                </div>
                <div className="text-[11px] text-brand-muted mt-0.5">Missing specifications</div>
              </div>
              <div className="p-4 rounded-xl bg-brand-card border border-brand-border">
                <div className="text-[10px] text-brand-muted uppercase font-bold">Contradictions</div>
                <div className={`text-xl font-bold mt-1 ${contradictions.length === 0 ? "text-emerald-600" : "text-rose-500"}`}>
                  {contradictions.length}
                </div>
                <div className="text-[11px] text-brand-muted mt-0.5">Conflicting ID references</div>
              </div>
            </div>

            {/* Invalidation Alert if any */}
            {isInvalidated && readinessState?.invalidation_reasons && (
              <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-900 dark:text-amber-200 text-xs">
                <div className="font-bold flex items-center gap-1.5 mb-1 text-amber-700 dark:text-amber-300">
                  <AlertTriangle className="w-4 h-4" />
                  Readiness Verdict Invalidated
                </div>
                <ul className="list-disc pl-5 space-y-0.5">
                  {readinessState.invalidation_reasons.map((r, idx) => (
                    <li key={idx}>{r}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {activeTab === "matrix" && (
          <div className="rounded-xl border border-brand-border bg-brand-card overflow-hidden">
            <div className="p-3 bg-brand-surface border-b border-brand-border text-xs text-brand-muted font-medium flex items-center justify-between">
              <span>Handbook Appendix A.9 Traceability Matrix (F &rarr; J &rarr; API &rarr; TBL &rarr; ST &rarr; Test)</span>
              <span>{matrix.length} Feature Chains</span>
            </div>
            <table className="w-full text-left text-xs">
              <thead className="bg-brand-surface/60 text-brand-muted border-b border-brand-border font-medium">
                <tr>
                  <th className="py-2.5 px-3">Feature (F-)</th>
                  <th className="py-2.5 px-3">Journey (J-)</th>
                  <th className="py-2.5 px-3">API (API-)</th>
                  <th className="py-2.5 px-3">Table (TBL-)</th>
                  <th className="py-2.5 px-3">Story (ST-)</th>
                  <th className="py-2.5 px-3">Test</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-brand-border/60">
                {matrix.map((row: any) => (
                  <tr key={row.feature_id} className="hover:bg-brand-surface/40">
                    <td className="py-2.5 px-3 font-mono font-bold text-brand-headline">
                      {row.feature_id}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-brand-body">
                      {row.journeys?.join(", ") || "-"}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-emerald-600 dark:text-emerald-400">
                      {row.apis?.join(", ") || "-"}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-purple-600 dark:text-purple-400">
                      {row.tables?.join(", ") || "-"}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[11px] font-bold text-indigo-600 dark:text-indigo-400">
                      {row.stories?.join(", ") || <span className="text-rose-500">MISSING</span>}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[10px] text-brand-muted">
                      {row.planned_tests?.join(", ") || "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === "gaps" && (
          <div className="space-y-4">
            {gaps.length === 0 && contradictions.length === 0 ? (
              <div className="p-8 text-center rounded-xl bg-brand-card border border-brand-border">
                <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
                <h4 className="text-xs font-bold text-brand-headline">Zero Gaps or Contradictions</h4>
                <p className="text-xs text-brand-muted mt-1">
                  Architecture, PRD, and Backlog are completely aligned. Development is ready to proceed.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {gaps.map((g, idx) => (
                  <div key={idx} className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-xs text-rose-700 dark:text-rose-300 flex items-start gap-2">
                    <XCircle className="w-4 h-4 shrink-0 mt-0.5 text-rose-500" />
                    <span>{g}</span>
                  </div>
                ))}
                {contradictions.map((c, idx) => (
                  <div key={idx} className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs text-amber-700 dark:text-amber-300 flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-amber-500" />
                    <span>{c}</span>
                  </div>
                ))}
              </div>
            )}
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
              {readinessContent || "*No readiness review content available.*"}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
};
