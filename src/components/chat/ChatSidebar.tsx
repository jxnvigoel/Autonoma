import React from "react";
import {
  Plus,
  MessageSquare,
  FileCheck,
  Clock,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  Layers,
  Loader2,
} from "lucide-react";
import { useConversation } from "@/context/ConversationContext";
import { cn } from "@/lib/utils";

interface ChatSidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  className?: string;
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
    });
  } catch {
    return "";
  }
}

export const ChatSidebar: React.FC<ChatSidebarProps> = ({
  isOpen,
  onToggle,
  className,
}) => {
  const {
    sessionId,
    sessions,
    isLoadingSessions,
    isLoadingSession,
    selectSession,
    newSession,
  } = useConversation();

  return (
    <aside
      className={cn(
        "h-full flex flex-col bg-brand-card/70 backdrop-blur-md border-r border-brand-border transition-all duration-300 ease-in-out shrink-0 select-none z-20",
        isOpen ? "w-64 sm:w-72" : "w-14",
        className
      )}
    >
      {/* Sidebar Header */}
      <div className="p-3 border-b border-brand-border/70 flex items-center justify-between gap-2">
        {isOpen ? (
          <>
            <button
              type="button"
              onClick={newSession}
              className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-xl bg-brand-accent hover:bg-brand-accent-hover text-brand-accent-text text-xs font-semibold shadow-xs active:scale-[0.98] transition-all cursor-pointer"
              title="Start a new project intake"
            >
              <Plus className="w-4 h-4" />
              <span>New conversation</span>
            </button>

            <button
              type="button"
              onClick={onToggle}
              className="p-2 text-brand-body hover:text-brand-headline rounded-lg hover:bg-brand-subtle transition-colors cursor-pointer"
              title="Collapse sidebar"
              aria-label="Collapse sidebar"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
          </>
        ) : (
          <div className="w-full flex flex-col items-center gap-2">
            <button
              type="button"
              onClick={newSession}
              className="w-8 h-8 rounded-lg bg-brand-accent hover:bg-brand-accent-hover text-brand-accent-text flex items-center justify-center shadow-xs transition-colors cursor-pointer"
              title="New conversation"
            >
              <Plus className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={onToggle}
              className="p-1.5 text-brand-body hover:text-brand-headline rounded-lg hover:bg-brand-subtle transition-colors cursor-pointer"
              title="Expand sidebar"
              aria-label="Expand sidebar"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>

      {/* Sidebar Content / Session List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {isOpen && (
          <div className="px-2 py-1.5 flex items-center justify-between text-[11px] font-semibold text-brand-body uppercase tracking-wider">
            <span className="flex items-center gap-1.5">
              <Layers className="w-3 h-3 text-brand-accent" />
              <span>Past Conversations</span>
            </span>
            <span className="text-[10px] bg-brand-subtle px-1.5 py-0.5 rounded text-brand-body font-mono">
              {sessions.length}
            </span>
          </div>
        )}

        {isLoadingSessions && sessions.length === 0 ? (
          <div className="py-8 flex flex-col items-center justify-center text-xs text-brand-body gap-2">
            <Loader2 className="w-4 h-4 animate-spin text-brand-accent" />
            {isOpen && <span>Loading sessions...</span>}
          </div>
        ) : sessions.length === 0 ? (
          isOpen && (
            <div className="py-8 px-4 text-center">
              <Sparkles className="w-6 h-6 text-brand-body/40 mx-auto mb-2" />
              <p className="text-xs text-brand-body">No past BA sessions yet.</p>
              <p className="text-[11px] text-brand-body/60 mt-1">
                Start a project intake to brief your Business Analyst.
              </p>
            </div>
          )
        ) : (
          sessions.map((s) => {
            const isActive = sessionId === s.session_id;
            const timeStr = formatSessionDate(s.updated_at || s.created_at);

            return (
              <button
                key={s.session_id}
                type="button"
                onClick={() => selectSession(s.session_id)}
                disabled={isLoadingSession && isActive}
                title={`${s.project_name}${s.description ? ` — ${s.description}` : ""}`}
                className={cn(
                  "w-full text-left rounded-xl transition-all cursor-pointer group flex items-center gap-2.5",
                  isOpen ? "px-3 py-2.5" : "p-2 justify-center",
                  isActive
                    ? "bg-brand-accent/15 text-brand-headline border border-brand-accent/30 font-medium shadow-xs"
                    : "text-brand-body hover:text-brand-headline hover:bg-brand-subtle/80 border border-transparent"
                )}
              >
                <div
                  className={cn(
                    "w-7 h-7 rounded-lg flex items-center justify-center shrink-0 transition-colors",
                    s.has_requirements || s.ready_for_requirements
                      ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                      : isActive
                      ? "bg-brand-accent text-brand-accent-text"
                      : "bg-brand-subtle text-brand-body group-hover:text-brand-headline"
                  )}
                >
                  {s.has_requirements || s.ready_for_requirements ? (
                    <FileCheck className="w-3.5 h-3.5" />
                  ) : (
                    <MessageSquare className="w-3.5 h-3.5" />
                  )}
                </div>

                {isOpen && (
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-1">
                      <span className="text-xs font-semibold text-brand-headline truncate">
                        {s.project_name || "Untitled Project"}
                      </span>
                      {timeStr && (
                        <span className="text-[10px] text-brand-body/70 shrink-0 font-mono flex items-center gap-0.5">
                          <Clock className="w-2.5 h-2.5 opacity-60" />
                          {timeStr}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center justify-between gap-1 mt-0.5">
                      <span className="text-[11px] text-brand-body/80 truncate">
                        {s.description || "BA Discovery Session"}
                      </span>
                      {s.has_requirements ? (
                        <span className="text-[9px] px-1.5 py-0.2 rounded bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 font-semibold shrink-0">
                          Ready
                        </span>
                      ) : s.round > 0 ? (
                        <span className="text-[9px] px-1.5 py-0.2 rounded bg-brand-subtle text-brand-body font-mono shrink-0">
                          R{s.round}
                        </span>
                      ) : null}
                    </div>
                  </div>
                )}
              </button>
            );
          })
        )}
      </div>

      {/* Footer / Status indication */}
      {isOpen && (
        <div className="p-3 border-t border-brand-border/70 text-[11px] text-brand-body flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>Local Engine Active</span>
          </div>
          <span className="text-[10px] font-mono text-brand-body/70">Llama 3.2</span>
        </div>
      )}
    </aside>
  );
};

export default ChatSidebar;
