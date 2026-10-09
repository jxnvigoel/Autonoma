import React, { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  FileCheck,
  ArrowRight,
  Loader2,
  Sparkles,
  Users,
  Calendar,
  DollarSign,
  Layers,
  AlertCircle,
  FolderOpen,
  X,
  Search,
  Clock,
  MessageSquare,
} from "lucide-react";
import { IntakeFormData } from "../../lib/engine";
import { useConversation } from "../../context/ConversationContext";
import { cn } from "../../lib/utils";

interface IntakeFormProps {
  onSubmit: (data: IntakeFormData) => Promise<void>;
  onSelectSession?: (sessionId: string) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
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

export const IntakeForm: React.FC<IntakeFormProps> = ({
  onSubmit,
  onSelectSession,
  isLoading = false,
  error = null,
}) => {
  const {
    sessions,
    isLoadingSessions,
    selectSession: contextSelectSession,
    refreshSessions,
  } = useConversation();

  const [formData, setFormData] = useState<IntakeFormData>({
    projectName: "",
    description: "",
    targetUsers: "",
    timeline: "",
    budget: "",
  });

  const [validationError, setValidationError] = useState<string | null>(null);
  const [showPickerModal, setShowPickerModal] = useState<boolean>(false);
  const [pickerSearch, setPickerSearch] = useState<string>("");
  const [isOpeningProject, setIsOpeningProject] = useState<boolean>(false);

  const handleSelectSessionAction = onSelectSession || contextSelectSession;

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (validationError) {
      setValidationError(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.projectName.trim()) {
      setValidationError("Please enter a project name.");
      return;
    }
    if (!formData.description.trim()) {
      setValidationError("Please describe what you are trying to build.");
      return;
    }
    if (!formData.targetUsers.trim()) {
      setValidationError("Please specify who will use this application.");
      return;
    }
    if (!formData.timeline.trim()) {
      setValidationError("Please enter your target timeline (e.g. 6 weeks).");
      return;
    }
    if (!formData.budget.trim()) {
      setValidationError(
        "Please enter your budget and expected monthly running costs."
      );
      return;
    }

    try {
      await onSubmit(formData);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setValidationError(msg);
    }
  };

  const handleOpenPicker = async () => {
    setPickerSearch("");
    setShowPickerModal(true);
    await refreshSessions();
  };

  const handleSelectProject = async (targetSessionId: string) => {
    setIsOpeningProject(true);
    try {
      await handleSelectSessionAction(targetSessionId);
      setShowPickerModal(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setValidationError(`Failed to load project: ${msg}`);
    } finally {
      setIsOpeningProject(false);
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

  const activeError = validationError || error;

  return (
    <div className="min-h-full flex-1 flex flex-col items-center justify-center p-4 sm:p-6 md:p-8 bg-brand-bg text-brand-headline transition-colors duration-200">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: "easeOut" }}
        className="w-full max-w-2xl bg-brand-card border border-brand-border rounded-2xl shadow-card p-6 sm:p-8 space-y-6 transition-colors duration-200"
      >
        {/* Header / Intro */}
        <div className="space-y-2 border-b border-brand-border/70 pb-5">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-brand-accent text-brand-accent-text flex items-center justify-center shadow-xs">
              <FileCheck className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold tracking-tight text-brand-headline">
                  Project Intake
                </h2>
                <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-brand-subtle text-brand-accent border border-brand-border">
                  Step 01 • BA Discovery
                </span>
              </div>
              <p className="text-xs text-brand-body">
                Fill in these core details to brief your Business Analyst, or resume an existing project.
              </p>
            </div>
          </div>
        </div>

        {/* Error Alert */}
        {activeError && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            className="p-3.5 rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300 text-xs flex items-start gap-2.5 shadow-xs"
          >
            <AlertCircle className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
            <span className="leading-relaxed">{activeError}</span>
          </motion.div>
        )}

        {/* Form Fields */}
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Field 1: Project Name */}
          <div className="space-y-1.5">
            <label
              htmlFor="projectName"
              className="text-xs font-semibold text-brand-headline flex items-center gap-1.5"
            >
              <Layers className="w-3.5 h-3.5 text-brand-accent" />
              <span>Project Name</span>
              <span className="text-rose-500 text-xs">*</span>
            </label>
            <input
              id="projectName"
              name="projectName"
              type="text"
              required
              disabled={isLoading || isOpeningProject}
              value={formData.projectName}
              onChange={handleChange}
              placeholder="e.g. TaskFlow Pro, Local Artisan Marketplace"
              className="w-full px-3.5 py-2.5 rounded-xl bg-brand-bg border border-brand-border focus:border-brand-accent focus:outline-none text-xs text-brand-headline placeholder:text-brand-body/50 transition-colors shadow-inner"
            />
          </div>

          {/* Field 2: What are you trying to build? */}
          <div className="space-y-1.5">
            <label
              htmlFor="description"
              className="text-xs font-semibold text-brand-headline flex items-center gap-1.5"
            >
              <Sparkles className="w-3.5 h-3.5 text-brand-accent" />
              <span>In a sentence or two, what are you trying to build?</span>
              <span className="text-rose-500 text-xs">*</span>
            </label>
            <textarea
              id="description"
              name="description"
              required
              rows={3}
              disabled={isLoading || isOpeningProject}
              value={formData.description}
              onChange={handleChange}
              placeholder="e.g. A fast web platform for freelance designers to send interactive invoices, collect client feedback, and track payments without paying high platform fees."
              className="w-full px-3.5 py-2.5 rounded-xl bg-brand-bg border border-brand-border focus:border-brand-accent focus:outline-none text-xs text-brand-headline placeholder:text-brand-body/50 transition-colors resize-none shadow-inner leading-relaxed"
            />
          </div>

          {/* Field 3: Who will use it? */}
          <div className="space-y-1.5">
            <label
              htmlFor="targetUsers"
              className="text-xs font-semibold text-brand-headline flex items-center gap-1.5"
            >
              <Users className="w-3.5 h-3.5 text-brand-accent" />
              <span>Who will use it?</span>
              <span className="text-rose-500 text-xs">*</span>
            </label>
            <input
              id="targetUsers"
              name="targetUsers"
              type="text"
              required
              disabled={isLoading || isOpeningProject}
              value={formData.targetUsers}
              onChange={handleChange}
              placeholder="e.g. Solo freelancers, creative studios, and their direct clients"
              className="w-full px-3.5 py-2.5 rounded-xl bg-brand-bg border border-brand-border focus:border-brand-accent focus:outline-none text-xs text-brand-headline placeholder:text-brand-body/50 transition-colors shadow-inner"
            />
          </div>

          {/* 2-Column Row for Timeline and Budget */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Field 4: Target Timeline */}
            <div className="space-y-1.5">
              <label
                htmlFor="timeline"
                className="text-xs font-semibold text-brand-headline flex items-center gap-1.5"
              >
                <Calendar className="w-3.5 h-3.5 text-brand-accent" />
                <span>Target timeline</span>
                <span className="text-rose-500 text-xs">*</span>
              </label>
              <input
                id="timeline"
                name="timeline"
                type="text"
                required
                disabled={isLoading || isOpeningProject}
                value={formData.timeline}
                onChange={handleChange}
                placeholder="e.g. 6 weeks for MVP"
                className="w-full px-3.5 py-2.5 rounded-xl bg-brand-bg border border-brand-border focus:border-brand-accent focus:outline-none text-xs text-brand-headline placeholder:text-brand-body/50 transition-colors shadow-inner"
              />
            </div>

            {/* Field 5: Budget */}
            <div className="space-y-1.5">
              <label
                htmlFor="budget"
                className="text-xs font-semibold text-brand-headline flex items-center gap-1.5"
              >
                <DollarSign className="w-3.5 h-3.5 text-brand-accent" />
                <span>Budget & running costs</span>
                <span className="text-rose-500 text-xs">*</span>
              </label>
              <input
                id="budget"
                name="budget"
                type="text"
                required
                disabled={isLoading || isOpeningProject}
                value={formData.budget}
                onChange={handleChange}
                placeholder="e.g. $5,000 build, under $50/mo hosting"
                className="w-full px-3.5 py-2.5 rounded-xl bg-brand-bg border border-brand-border focus:border-brand-accent focus:outline-none text-xs text-brand-headline placeholder:text-brand-body/50 transition-colors shadow-inner"
              />
            </div>
          </div>

          {/* Submit Button */}
          <div className="pt-2 flex items-center justify-end">
            <button
              type="submit"
              disabled={isLoading || isOpeningProject}
              className="w-full sm:w-auto px-6 py-3 rounded-xl bg-brand-accent hover:bg-brand-accent-hover text-brand-accent-text text-xs font-semibold shadow-sm flex items-center justify-center gap-2 active:scale-95 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Connecting with Business Analyst...</span>
                </>
              ) : (
                <>
                  <span>Start with my BA</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </form>

        {/* Secondary Divider "or" */}
        <div className="relative my-4">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-brand-border/80" />
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-brand-card px-3 text-brand-body/70 font-semibold tracking-wider">
              or
            </span>
          </div>
        </div>

        {/* Secondary Option: Open an Existing Project */}
        <div>
          <button
            type="button"
            disabled={isLoading || isOpeningProject}
            onClick={handleOpenPicker}
            className="w-full py-3 px-4 rounded-xl border border-brand-border bg-brand-subtle/50 hover:bg-brand-subtle text-brand-headline text-xs font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer shadow-xs hover:border-brand-accent/50 disabled:opacity-50 disabled:cursor-not-allowed group"
          >
            {isOpeningProject ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-brand-accent" />
                <span>Loading existing project...</span>
              </>
            ) : (
              <>
                <FolderOpen className="w-4 h-4 text-brand-accent group-hover:scale-110 transition-transform" />
                <span>Open an existing project</span>
                {sessions.length > 0 && (
                  <span className="ml-1 text-[10px] px-2 py-0.5 rounded-full bg-brand-card border border-brand-border text-brand-body font-mono">
                    {sessions.length}
                  </span>
                )}
              </>
            )}
          </button>
        </div>
      </motion.div>

      {/* Existing Projects Picker Modal */}
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
                      Open an Existing Project
                    </h3>
                    <p className="text-[11px] text-brand-body">
                      Select a prior BA discovery session to resume conversation and view requirements.
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
              {sessions.length > 0 && (
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
              )}

              {/* Project List */}
              <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-2">
                {isLoadingSessions ? (
                  <div className="py-12 flex flex-col items-center justify-center text-xs text-brand-body gap-2">
                    <Loader2 className="w-5 h-5 animate-spin text-brand-accent" />
                    <span>Loading past projects...</span>
                  </div>
                ) : filteredSessions.length === 0 ? (
                  <div className="py-12 px-4 text-center">
                    <MessageSquare className="w-8 h-8 text-brand-body/30 mx-auto mb-2" />
                    <p className="text-xs font-medium text-brand-headline">
                      {pickerSearch ? "No matching projects found." : "No previous projects found."}
                    </p>
                    <p className="text-[11px] text-brand-body mt-1">
                      {pickerSearch
                        ? "Try searching with a different term."
                        : "Submit the intake form to start your very first BA session!"}
                    </p>
                  </div>
                ) : (
                  filteredSessions.map((session) => {
                    const timeStr = formatSessionDate(
                      session.updated_at || session.created_at
                    );

                    return (
                      <button
                        key={session.session_id}
                        type="button"
                        disabled={isOpeningProject}
                        onClick={() => handleSelectProject(session.session_id)}
                        className={cn(
                          "w-full text-left p-3 rounded-xl border border-brand-border bg-brand-bg hover:bg-brand-subtle hover:border-brand-accent/40 transition-all cursor-pointer group flex items-start gap-3 shadow-2xs active:scale-[0.99]",
                          isOpeningProject && "opacity-60 cursor-not-allowed"
                        )}
                      >
                        <div
                          className={cn(
                            "w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5 transition-colors",
                            session.has_requirements || session.ready_for_requirements
                              ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                              : "bg-brand-subtle text-brand-accent group-hover:bg-brand-accent group-hover:text-brand-accent-text"
                          )}
                        >
                          {session.has_requirements || session.ready_for_requirements ? (
                            <FileCheck className="w-4 h-4" />
                          ) : (
                            <Layers className="w-4 h-4" />
                          )}
                        </div>

                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs font-bold text-brand-headline truncate group-hover:text-brand-accent transition-colors">
                              {session.project_name || "Untitled Project"}
                            </span>
                            {timeStr && (
                              <span className="text-[10px] text-brand-body/70 shrink-0 font-mono flex items-center gap-1">
                                <Clock className="w-3 h-3 opacity-60" />
                                {timeStr}
                              </span>
                            )}
                          </div>

                          <p className="text-[11px] text-brand-body line-clamp-2 mt-1 leading-relaxed">
                            {session.description || "BA discovery conversation history."}
                          </p>

                          <div className="flex items-center gap-2 mt-2">
                            {session.has_requirements ? (
                              <span className="text-[9px] px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-semibold flex items-center gap-1">
                                <FileCheck className="w-2.5 h-2.5" />
                                <span>Requirements Ready</span>
                              </span>
                            ) : session.round > 0 ? (
                              <span className="text-[9px] px-2 py-0.5 rounded-full bg-brand-subtle text-brand-body font-mono">
                                Discovery Round {session.round}
                              </span>
                            ) : (
                              <span className="text-[9px] px-2 py-0.5 rounded-full bg-brand-subtle text-brand-body">
                                New Session
                              </span>
                            )}
                          </div>
                        </div>
                      </button>
                    );
                  })
                )}
              </div>

              {/* Modal Footer */}
              <div className="p-3 sm:p-4 border-t border-brand-border/80 bg-brand-bg/40 flex items-center justify-between">
                <span className="text-[11px] text-brand-body">
                  {filteredSessions.length} project{filteredSessions.length !== 1 ? "s" : ""} available
                </span>
                <button
                  type="button"
                  onClick={() => setShowPickerModal(false)}
                  className="px-3.5 py-1.5 rounded-lg border border-brand-border bg-brand-card hover:bg-brand-subtle text-xs font-medium text-brand-headline transition-colors cursor-pointer"
                >
                  Cancel
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default IntakeForm;
