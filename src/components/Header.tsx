import React from "react";
import { MessageSquare, Code2 } from "lucide-react";
import { StatusBadge } from "./StatusBadge";
import { ThemeToggle } from "./ThemeToggle";
import { EngineStatus } from "../lib/engine";
import { cn } from "../lib/utils";

interface HeaderProps {
  status: EngineStatus | null;
  isChecking: boolean;
  onRefreshStatus: () => void;
  onBackToLanding?: () => void;
  activeScreen?: "chat" | "editor" | "landing";
  onOpenChat?: () => void;
  onOpenEditor?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  status,
  isChecking,
  onRefreshStatus,
  onBackToLanding,
  activeScreen,
  onOpenChat,
  onOpenEditor,
}) => {
  return (
    <header className="border-b border-brand-border bg-brand-bg/95 backdrop-blur-sm px-6 py-3 flex items-center justify-between sticky top-0 z-30 transition-colors duration-200">
      <div className="flex items-center gap-6">
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
            <p className="text-[11px] text-brand-body transition-colors duration-200">
              Local AI Desktop • Electron + Python Engine
            </p>
          </div>
        </div>

        {/* Workspace Screen Switcher */}
        {(onOpenChat || onOpenEditor) && (
          <nav className="hidden md:flex items-center p-1 rounded-xl bg-brand-subtle/70 border border-brand-border text-xs font-medium">
            {onOpenChat && (
              <button
                type="button"
                onClick={onOpenChat}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-1 rounded-lg transition-all cursor-pointer",
                  activeScreen === "chat"
                    ? "bg-brand-card text-brand-accent font-semibold shadow-xs"
                    : "text-brand-body hover:text-brand-headline"
                )}
              >
                <MessageSquare className="w-3.5 h-3.5" />
                <span>Chat</span>
              </button>
            )}
            {onOpenEditor && (
              <button
                type="button"
                onClick={onOpenEditor}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-1 rounded-lg transition-all cursor-pointer",
                  activeScreen === "editor"
                    ? "bg-brand-card text-brand-accent font-semibold shadow-xs"
                    : "text-brand-body hover:text-brand-headline"
                )}
              >
                <Code2 className="w-3.5 h-3.5" />
                <span>Code Editor</span>
              </button>
            )}
          </nav>
        )}
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
