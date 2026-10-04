import React from "react";
import { EngineStatus } from "../lib/engine";

interface StatusBadgeProps {
  status: EngineStatus | null;
  isChecking: boolean;
  onRefresh?: () => void;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  isChecking,
  onRefresh,
}) => {
  const isStarting = !status || status.status === "starting";
  const isReady =
    status?.status === "ready" && status.ollama_online && status.model_ready;
  const isOllamaDown = status && !status.ollama_online && status.status !== "starting";
  const isModelMissing =
    status?.status === "ready" && status.ollama_online && !status.model_ready;

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-slate-800 bg-slate-900/80 text-xs">
      {isChecking || isStarting ? (
        <span className="flex items-center gap-1.5 text-slate-400">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500"></span>
          </span>
          {isStarting ? "Starting Python Engine..." : "Checking Engine..."}
        </span>
      ) : isReady ? (
        <span className="flex items-center gap-1.5 text-emerald-400">
          <span className="h-2 w-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.7)]"></span>
          <span>
            Engine & Llama Active {status.version ? `(v${status.version})` : ""}
          </span>
        </span>
      ) : isModelMissing ? (
        <span className="flex items-center gap-1.5 text-amber-400">
          <span className="h-2 w-2 rounded-full bg-amber-500"></span>
          <span>Model Missing</span>
        </span>
      ) : isOllamaDown ? (
        <span className="flex items-center gap-1.5 text-rose-400">
          <span className="h-2 w-2 rounded-full bg-rose-500"></span>
          <span>Ollama Offline</span>
        </span>
      ) : (
        <span className="flex items-center gap-1.5 text-rose-400">
          <span className="h-2 w-2 rounded-full bg-rose-500"></span>
          <span>Engine Error</span>
        </span>
      )}

      {onRefresh && (
        <button
          onClick={onRefresh}
          disabled={isChecking}
          title="Re-check Engine status"
          className="ml-1 text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
        >
          <svg
            className={`w-3.5 h-3.5 ${isChecking ? "animate-spin" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
        </button>
      )}
    </div>
  );
};
