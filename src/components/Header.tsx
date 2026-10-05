import React from "react";
import { StatusBadge } from "./StatusBadge";
import { ThemeToggle } from "./ThemeToggle";
import { EngineStatus } from "../lib/engine";

interface HeaderProps {
  status: EngineStatus | null;
  isChecking: boolean;
  onRefreshStatus: () => void;
  onBackToLanding?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  status,
  isChecking,
  onRefreshStatus,
  onBackToLanding,
}) => {
  return (
    <header className="border-b border-brand-border bg-brand-bg/95 backdrop-blur-sm px-6 py-3.5 flex items-center justify-between sticky top-0 z-10 transition-colors duration-200">
      <div
        onClick={onBackToLanding}
        className={`flex items-center gap-3 ${
          onBackToLanding ? "cursor-pointer group select-none" : ""
        }`}
        title={onBackToLanding ? "Back to Landing Page" : undefined}
      >
        <div className="w-8 h-8 rounded-lg bg-brand-accent text-brand-accent-text flex items-center justify-center font-bold text-sm group-hover:scale-105 transition-all shadow-sm">
          A
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-base font-bold text-brand-headline tracking-tight group-hover:text-brand-accent transition-colors duration-200">
              Autonoma
            </h1>
            {onBackToLanding && (
              <span className="text-[10px] font-medium text-brand-body bg-brand-subtle px-1.5 py-0.5 rounded transition-colors duration-200">
                ← Overview
              </span>
            )}
          </div>
          <p className="text-xs text-brand-body transition-colors duration-200">
            Local AI Desktop • Electron + Python Engine
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {onBackToLanding && (
          <button
            onClick={onBackToLanding}
            className="hidden sm:inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-brand-card hover:bg-brand-subtle border border-brand-border text-xs font-medium text-brand-headline transition-colors duration-200 cursor-pointer shadow-sm"
          >
            <span>Overview</span>
          </button>
        )}
        <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-brand-card border border-brand-border text-xs text-brand-body font-medium shadow-sm transition-colors duration-200">
          <span className="text-brand-body">Model:</span>
          <span className="font-semibold text-brand-headline">llama3.2:3b</span>
        </div>
        <StatusBadge
          status={status}
          isChecking={isChecking}
          onRefresh={onRefreshStatus}
        />
        <ThemeToggle />
      </div>
    </header>
  );
};

export default Header;
