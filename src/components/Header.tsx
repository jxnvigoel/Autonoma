import React from "react";
import { StatusBadge } from "./StatusBadge";
import { EngineStatus } from "../lib/engine";

interface HeaderProps {
  status: EngineStatus | null;
  isChecking: boolean;
  onRefreshStatus: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  status,
  isChecking,
  onRefreshStatus,
}) => {
  return (
    <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur-md px-6 py-4 flex items-center justify-between sticky top-0 z-10">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-white shadow-lg shadow-indigo-500/25">
          A
        </div>
        <div>
          <h1 className="text-base font-semibold text-white tracking-tight">
            Autonoma
          </h1>
          <p className="text-xs text-slate-400">
            Local AI Desktop • Electron + Python Engine
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-800/80 border border-slate-700/60 text-xs text-slate-300">
          <span className="text-indigo-400 font-medium">Model:</span>
          <span>llama3.2:3b</span>
        </div>
        <StatusBadge
          status={status}
          isChecking={isChecking}
          onRefresh={onRefreshStatus}
        />
      </div>
    </header>
  );
};
