import React, { useState, useEffect, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  FolderOpen,
  Plus,
  ArrowRight,
  Clock,
  Search,
  X,
  FileCheck,
  Layers,
  Sparkles,
  Loader2,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  Briefcase,
} from "lucide-react";
import { useConversation } from "../context/ConversationContext";
import { EngineStatus } from "../lib/engine";
import { StatusBadge } from "../components/StatusBadge";
import { ThemeToggle } from "../components/ThemeToggle";

interface ProjectSelectorProps {
  onSelectProject: (sessionId: string) => Promise<void>;
  onNewProject: () => void;
  onBackToLanding: () => void;
  status?: EngineStatus | null;
  isCheckingStatus?: boolean;
  onRefreshStatus?: () => void;
}

function formatSessionDate(isoString: string): string {
  if (!isoString) return "";
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return "";
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMin < 1) return "Just now";
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: date.getFullYear() !== now.getFullYear() ? "numeric" : undefined,
    });
  } catch {
    return "";
  }
}

export const ProjectSelector: React.FC<ProjectSelectorProps> = ({
  onSelectProject,
  onNewProject,
  onBackToLanding,
  status,
  isCheckingStatus = false,
  onRefreshStatus,
}) => {
  const { sessions, isLoadingSessions, refreshSessions } = useConversation();

  const [resumingSessionId, setResumingSessionId] = useState<string | null>(null);
  const [showPickerModal, setShowPickerModal] = useState<boolean>(false);
  const [pickerSearch, setPickerSearch] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  // Refresh sessions on mount to ensure most recent order is fresh
  useEffect(() => {
    refreshSessions();
  }, [refreshSessions]);

  // Most recent project is the first item (backend sorts by updated_at descending)
  const mostRecentProject = useMemo(() => {
    if (!sessions || sessions.length === 0) return null;
    return sessions[0];
  }, [sessions]);

  const handleResume = async (sessionId: string) => {
    setResumingSessionId(sessionId);
    setError(null);
    try {
      await onSelectProject(sessionId);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(`Failed to resume project: ${msg}`);
      setResumingSessionId(null);
    }
  };

  const filteredSessions = useMemo(() => {
    if (!pickerSearch.trim()) return sessions;
    const q = pickerSearch.toLowerCase().trim();
    return sessions.filter(
      (s) =>
        s.project_name.toLowerCase().includes(q) ||
        s.description.toLowerCase().includes(q)
    );
  }, [sessions, pickerSearch]);

  return (
    <div className="min-h-screen bg-brand-bg text-brand-headline flex flex-col selection:bg-brand-accent selection:text-brand-accent-text transition-colors duration-200">
      {/* Top Navigation */}
      <header className="sticky top-0 z-40 bg-brand-bg/90 backdrop-blur-sm border-b border-brand-border px-6 py-4 transition-colors duration-200">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onBackToLanding}
              className="p-1.5 -ml-1 text-brand-body hover:text-brand-headline rounded-lg hover:bg-brand-subtle transition-colors cursor-pointer flex items-center gap-1 text-xs font-medium"
              title="Back to Landing Page"
            >
              <ChevronLeft className="w-4 h-4" />
              <span className="hidden sm:inline">Overview</span>
            </button>

            <div className="h-4 w-px bg-brand-border" />

            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-brand-accent text-brand-accent-text flex items-center justify-center font-bold text-xs shadow-sm">
                A
              </div>
              <span className="text-sm font-bold text-brand-headline tracking-tight">
                Autonoma
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {status !== undefined && onRefreshStatus && (
              <div className="hidden sm:block">
                <StatusBadge
                  status={status}
                  isChecking={isCheckingStatus}
                  onRefresh={onRefreshStatus}
                />
              </div>
            )}
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* Main Container: Harness Config Style Project Selector */}
      <main className="flex-1 flex flex-col items-center justify-center px-4 py-10 sm:py-16">
        <div className="w-full max-w-2xl space-y-6">
          {/* Header Title & Subtitle */}
          <div className="space-y-1 text-left">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-brand-subtle text-brand-accent border border-brand-border text-[11px] font-semibold font-mono uppercase tracking-wide">
              <Briefcase className="w-3 h-3" />
              <span>Workspace Config</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-brand-headline mt-1">
              Select Project
            </h1>
            <p className="text-xs sm:text-sm text-brand-body leading-relaxed">
              Resume your active project workspace or initialize a new project brief.
            </p>
          </div>

          {/* Error Banner if any */}
          {error && (
            <div className="p-3.5 rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300 text-xs flex items-center justify-between gap-2 shadow-xs">
              <span>{error}</span>
              <button
                type="button"
                onClick={() => setError(null)}
                className="text-rose-700 dark:text-rose-300 hover:opacity-80 cursor-pointer"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Section 1: Prominently Highlighted Recent Project (if any exists) */}
          {isLoadingSessions && !mostRecentProject ? (
            <div className="p-8 rounded-2xl bg-brand-card border border-brand-border shadow-card flex items-center justify-center gap-2 text-xs text-brand-body">
              <Loader2 className="w-4 h-4 animate-spin text-brand-accent" />
              <span>Checking workspace sessions...</span>
            </div>
          ) : mostRecentProject ? (
            <div className="relative group rounded-2xl bg-brand-card border-2 border-brand-accent/40 shadow-card p-5 sm:p-6 transition-all duration-200 hover:border-brand-accent hover:shadow-lg">
              {/* Highlight Tag */}
              <div className="flex items-center justify-between gap-2 mb-3">
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-brand-accent/15 text-brand-accent text-[10px] font-mono font-bold uppercase tracking-wider border border-brand-accent/30">
                  <Sparkles className="w-3 h-3" />
                  <span>Last Active Project</span>
                </span>

                <span className="text-[11px] font-mono text-brand-body flex items-center gap-1">
                  <Clock className="w-3 h-3 opacity-60" />
                  <span>{formatSessionDate(mostRecentProject.updated_at || mostRecentProject.created_at)}</span>
                </span>
              </div>

              {/* Project Info */}
              <div className="space-y-1.5 pr-2">
                <h2 className="text-lg font-bold text-brand-headline tracking-tight group-hover:text-brand-accent transition-colors">
                  {mostRecentProject.project_name || "Untitled Project"}
                </h2>
                <p className="text-xs text-brand-body leading-relaxed line-clamp-2">
                  {mostRecentProject.description || "BA discovery and product planning workspace."}
                </p>
              </div>

              {/* Status Ribbon & Open Action */}
              <div className="mt-5 pt-4 border-t border-brand-border/70 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-[11px]">
                  {mostRecentProject.has_requirements ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-semibold text-[10px]">
                      <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                      <span>Requirements Ready</span>
                    </span>
                  ) : mostRecentProject.round > 0 ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-brand-subtle text-brand-body font-mono text-[10px]">
                      <span>Discovery Round {mostRecentProject.round}</span>
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-brand-subtle text-brand-body text-[10px]">
                      <span>Active Workspace</span>
                    </span>
                  )}
                </div>

                <button
                  type="button"
                  disabled={resumingSessionId === mostRecentProject.session_id}
                  onClick={() => handleResume(mostRecentProject.session_id)}
                  className="px-5 py-2.5 rounded-xl bg-brand-accent hover:bg-brand-accent-hover text-brand-accent-text text-xs font-semibold shadow-sm flex items-center gap-2 active:scale-95 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
                >
                  {resumingSessionId === mostRecentProject.session_id ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Opening...</span>
                    </>
                  ) : (
                    <>
                      <span>Open Project</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </>
                  )}
                </button>
              </div>
            </div>
          ) : null}

          {/* Section 2: Two Explicit Choices Below */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
            {/* Choice 1: New Project */}
            <button
              type="button"
              onClick={onNewProject}
              className="p-5 rounded-2xl bg-brand-card hover:bg-brand-card-alt border border-brand-border hover:border-brand-accent/50 shadow-card transition-all duration-200 text-left flex flex-col justify-between gap-4 cursor-pointer group active:scale-[0.99]"
            >
              <div className="space-y-3">
                <div className="w-10 h-10 rounded-xl bg-brand-subtle group-hover:bg-brand-accent group-hover:text-brand-accent-text border border-brand-border flex items-center justify-center text-brand-accent transition-colors duration-200">
                  <Plus className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-brand-headline group-hover:text-brand-accent transition-colors">
                    New project
                  </h3>
                  <p className="text-xs text-brand-body leading-relaxed mt-1">
                    Fill in a brief to start a clean discovery session with your Business Analyst.
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-1.5 text-xs font-semibold text-brand-accent group-hover:translate-x-0.5 transition-transform">
                <span>Start brief</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </div>
            </button>

            {/* Choice 2: Open Existing Project */}
            <button
              type="button"
              onClick={() => {
                if (sessions.length > 0) {
                  setShowPickerModal(true);
                }
              }}
              disabled={sessions.length === 0}
              className={`p-5 rounded-2xl bg-brand-card hover:bg-brand-card-alt border border-brand-border shadow-card transition-all duration-200 text-left flex flex-col justify-between gap-4 ${
                sessions.length > 0
                  ? "hover:border-brand-accent/50 cursor-pointer group active:scale-[0.99]"
                  : "opacity-60 cursor-not-allowed"
              }`}
            >
              <div className="space-y-3">
                <div className="w-10 h-10 rounded-xl bg-brand-subtle group-hover:bg-brand-accent group-hover:text-brand-accent-text border border-brand-border flex items-center justify-center text-brand-accent transition-colors duration-200">
                  <FolderOpen className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-bold text-brand-headline group-hover:text-brand-accent transition-colors">
                      Open existing project
                    </h3>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-brand-subtle text-brand-body border border-brand-border">
                      {sessions.length}
                    </span>
                  </div>
                  <p className="text-xs text-brand-body leading-relaxed mt-1">
                    {sessions.length > 0
                      ? "Browse and resume any prior session from your local workspace library."
                      : "No past project workspaces found yet."}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-1.5 text-xs font-semibold text-brand-accent group-hover:translate-x-0.5 transition-transform">
                <span>{sessions.length > 0 ? "Browse all" : "No sessions"}</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </div>
            </button>
          </div>
        </div>
      </main>

      {/* Full Picker Modal for "Open Existing Project" */}
      <AnimatePresence>
        {showPickerModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
            <motion.div
              initial={{ opacity: 0, scale: 0.96, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 8 }}
              transition={{ duration: 0.2 }}
              className="w-full max-w-xl bg-brand-card border border-brand-border rounded-2xl shadow-xl flex flex-col max-h-[85vh] overflow-hidden"
            >
              {/* Modal Header */}
              <div className="p-4 sm:p-5 border-b border-brand-border/80 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-brand-subtle flex items-center justify-center text-brand-accent border border-brand-border">
                    <FolderOpen className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-brand-headline">
                      All Existing Projects
                    </h3>
                    <p className="text-[11px] text-brand-body">
                      Select a project workspace to resume its Virtual Office and agent threads.
                    </p>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => setShowPickerModal(false)}
                  className="p-1.5 text-brand-body hover:text-brand-headline hover:bg-brand-subtle rounded-lg transition-colors cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Search Bar */}
              <div className="px-4 sm:px-5 py-3 border-b border-brand-border/60 bg-brand-bg/50">
                <div className="relative">
                  <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-brand-body/60" />
                  <input
                    type="text"
                    value={pickerSearch}
                    onChange={(e) => setPickerSearch(e.target.value)}
                    placeholder="Search past projects..."
                    className="w-full pl-9 pr-3.5 py-1.5 text-xs rounded-lg bg-brand-card border border-brand-border focus:border-brand-accent focus:outline-none text-brand-headline placeholder:text-brand-body/50 transition-colors shadow-inner"
                  />
                </div>
              </div>

              {/* Project List */}
              <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-2">
                {filteredSessions.length === 0 ? (
                  <div className="py-12 px-4 text-center">
                    <Layers className="w-8 h-8 text-brand-body/30 mx-auto mb-2" />
                    <p className="text-xs font-medium text-brand-headline">
                      No matching projects found
                    </p>
                    <p className="text-[11px] text-brand-body mt-1">
                      Try searching with a different term.
                    </p>
                  </div>
                ) : (
                  filteredSessions.map((s) => {
                    const isResuming = resumingSessionId === s.session_id;
                    const dateStr = formatSessionDate(s.updated_at || s.created_at);

                    return (
                      <button
                        key={s.session_id}
                        type="button"
                        disabled={Boolean(resumingSessionId)}
                        onClick={async () => {
                          await handleResume(s.session_id);
                          setShowPickerModal(false);
                        }}
                        className="w-full text-left p-3.5 rounded-xl border border-brand-border bg-brand-bg hover:bg-brand-subtle hover:border-brand-accent/40 transition-all cursor-pointer group flex items-start gap-3 shadow-2xs active:scale-[0.99] disabled:opacity-50"
                      >
                        <div className="w-8 h-8 rounded-lg bg-brand-subtle flex items-center justify-center shrink-0 mt-0.5 text-brand-accent group-hover:bg-brand-accent group-hover:text-brand-accent-text transition-colors">
                          {s.has_requirements ? (
                            <FileCheck className="w-4 h-4" />
                          ) : (
                            <FolderOpen className="w-4 h-4" />
                          )}
                        </div>

                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs font-bold text-brand-headline truncate group-hover:text-brand-accent transition-colors">
                              {s.project_name || "Untitled Project"}
                            </span>
                            {dateStr && (
                              <span className="text-[10px] text-brand-body font-mono flex items-center gap-1 shrink-0">
                                <Clock className="w-3 h-3 opacity-60" />
                                {dateStr}
                              </span>
                            )}
                          </div>

                          <p className="text-[11px] text-brand-body line-clamp-2 mt-0.5 leading-relaxed">
                            {s.description || "Project workspace session."}
                          </p>

                          <div className="flex items-center gap-2 mt-2">
                            {s.has_requirements ? (
                              <span className="text-[9px] px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-semibold flex items-center gap-1">
                                <CheckCircle2 className="w-2.5 h-2.5" />
                                <span>Requirements Ready</span>
                              </span>
                            ) : s.round > 0 ? (
                              <span className="text-[9px] px-2 py-0.5 rounded-full bg-brand-subtle text-brand-body font-mono">
                                Discovery Round {s.round}
                              </span>
                            ) : (
                              <span className="text-[9px] px-2 py-0.5 rounded-full bg-brand-subtle text-brand-body">
                                New Session
                              </span>
                            )}
                          </div>
                        </div>

                        {isResuming ? (
                          <Loader2 className="w-4 h-4 animate-spin text-brand-accent self-center" />
                        ) : (
                          <ChevronRight className="w-4 h-4 text-brand-body/40 group-hover:text-brand-accent group-hover:translate-x-0.5 transition-all self-center" />
                        )}
                      </button>
                    );
                  })
                )}
              </div>

              {/* Modal Footer */}
              <div className="p-3 sm:p-4 border-t border-brand-border/80 bg-brand-bg/40 flex items-center justify-between">
                <span className="text-[11px] text-brand-body">
                  {filteredSessions.length} project{filteredSessions.length !== 1 ? "s" : ""}
                </span>
                <button
                  type="button"
                  onClick={() => setShowPickerModal(false)}
                  className="px-3.5 py-1.5 rounded-lg border border-brand-border bg-brand-card hover:bg-brand-subtle text-xs font-medium text-brand-headline transition-colors cursor-pointer"
                >
                  Close
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default ProjectSelector;
