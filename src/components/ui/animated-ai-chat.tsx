"use client";

import React, { useEffect, useRef, useCallback, useState } from "react";
import { cn } from "@/lib/utils";
import {
  ImageIcon,
  Cpu,
  MonitorIcon,
  Paperclip,
  SendIcon,
  XIcon,
  LoaderIcon,
  Sparkles,
  Command,
  AlertCircle,
  RefreshCw,
  PlusCircle,
  FileCheck,
  FileText,
  Briefcase,
  Trash2,
  PanelLeft,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import {
  checkEngineStatus,
  EngineStatus,
} from "@/lib/engine";
import { useConversation } from "@/context/ConversationContext";
import { MessageBubble, TypingDots } from "@/components/chat/MessageBubble";
import { IntakeForm } from "@/components/chat/IntakeForm";
import { RequirementsModal } from "@/components/chat/RequirementsModal";
import { ChatSidebar } from "@/components/chat/ChatSidebar";

interface UseAutoResizeTextareaProps {
  minHeight: number;
  maxHeight?: number;
}

function useAutoResizeTextarea({
  minHeight,
  maxHeight,
}: UseAutoResizeTextareaProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const adjustHeight = useCallback(
    (reset?: boolean) => {
      const textarea = textareaRef.current;
      if (!textarea) return;

      if (reset) {
        textarea.style.height = `${minHeight}px`;
        return;
      }

      textarea.style.height = `${minHeight}px`;
      const newHeight = Math.max(
        minHeight,
        Math.min(textarea.scrollHeight, maxHeight ?? Number.POSITIVE_INFINITY)
      );

      textarea.style.height = `${newHeight}px`;
    },
    [minHeight, maxHeight]
  );

  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = `${minHeight}px`;
    }
  }, [minHeight]);

  useEffect(() => {
    const handleResize = () => adjustHeight();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [adjustHeight]);

  return { textareaRef, adjustHeight };
}

interface CommandSuggestion {
  icon: React.ReactNode;
  label: string;
  description: string;
  prefix: string;
}

interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  containerClassName?: string;
  showRing?: boolean;
}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, containerClassName, showRing = false, ...props }, ref) => {
    return (
      <div className={cn("relative", containerClassName)}>
        <textarea
          className={cn(
            "flex min-h-[60px] w-full rounded-md border border-transparent bg-transparent px-3 py-2 text-sm",
            "transition-all duration-200 ease-in-out",
            "placeholder:text-brand-body/60 text-brand-headline",
            "disabled:cursor-not-allowed disabled:opacity-50",
            showRing
              ? "focus-visible:outline-none focus-visible:ring-0 focus-visible:ring-offset-0"
              : "",
            className
          )}
          ref={ref}
          {...props}
        />
      </div>
    );
  }
);
Textarea.displayName = "Textarea";

export function AnimatedAIChat() {
  const [value, setValue] = useState("");
  const [attachments, setAttachments] = useState<string[]>([]);
  const [activeSuggestion, setActiveSuggestion] = useState<number>(-1);
  const [showCommandPalette, setShowCommandPalette] = useState(false);
  const [, setEngineStatus] = useState<EngineStatus | null>(null);
  const [engineError, setEngineError] = useState<string | null>(null);
  const [isCheckingStatus, setIsCheckingStatus] = useState(true);
  const [showRequirementsModal, setShowRequirementsModal] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const {
    sessionId,
    intakeData,
    messages,
    isLoadingSession,
    isSending,
    error: contextError,
    readyForRequirements,
    requirementsContent,
    startSession,
    selectSession,
    sendMessage,
    fetchRequirements,
    newSession,
    clearHistory,
  } = useConversation();

  const commandPaletteRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { textareaRef, adjustHeight } = useAutoResizeTextarea({
    minHeight: 60,
    maxHeight: 180,
  });

  const commandSuggestions: CommandSuggestion[] = [
    {
      icon: <Sparkles className="w-4 h-4" />,
      label: "Explain Concept",
      description: "Ask Llama 3.2 3B to break down a topic",
      prefix: "/explain",
    },
    {
      icon: <MonitorIcon className="w-4 h-4" />,
      label: "Generate Code",
      description: "Generate frontend or backend code",
      prefix: "/code",
    },
    {
      icon: <ImageIcon className="w-4 h-4" />,
      label: "Design Review",
      description: "Ask for UI/UX improvements",
      prefix: "/review",
    },
    {
      icon: <Cpu className="w-4 h-4" />,
      label: "Autonoma Status",
      description: "Verify Python engine & Apple Metal",
      prefix: "/hardware",
    },
  ];

  const probeEngine = useCallback(async () => {
    setIsCheckingStatus(true);
    try {
      const res = await checkEngineStatus();
      setEngineStatus(res);
      if (res.status === "starting") {
        setEngineError(res.message);
      } else if (res.status === "error" || !res.ollama_online || !res.model_ready) {
        setEngineError(res.message);
      } else {
        setEngineError(null);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setEngineError(msg);
      setEngineStatus({
        status: "error",
        ollama_online: false,
        model_ready: false,
        message: msg,
      });
    } finally {
      setIsCheckingStatus(false);
    }
  }, []);

  // Poll until engine is ready on startup
  useEffect(() => {
    probeEngine();
    const interval = setInterval(() => {
      probeEngine();
    }, 4000);
    return () => clearInterval(interval);
  }, [probeEngine]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending]);

  useEffect(() => {
    if (value.startsWith("/") && !value.includes(" ")) {
      setShowCommandPalette(true);
      const matchingSuggestionIndex = commandSuggestions.findIndex((cmd) =>
        cmd.prefix.startsWith(value)
      );
      if (matchingSuggestionIndex >= 0) {
        setActiveSuggestion(matchingSuggestionIndex);
      } else {
        setActiveSuggestion(-1);
      }
    } else {
      setShowCommandPalette(false);
    }
  }, [value]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      const commandButton = document.querySelector("[data-command-button]");
      if (
        commandPaletteRef.current &&
        !commandPaletteRef.current.contains(target) &&
        !commandButton?.contains(target)
      ) {
        setShowCommandPalette(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSendMessage = async (customPrompt?: string) => {
    const textToSend = (customPrompt ?? value).trim();
    if (!textToSend || isSending) return;

    setValue("");
    adjustHeight(true);

    try {
      await sendMessage(textToSend);
    } catch {
      // Error handled in context
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (showCommandPalette) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveSuggestion((prev) =>
          prev < commandSuggestions.length - 1 ? prev + 1 : 0
        );
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveSuggestion((prev) =>
          prev > 0 ? prev - 1 : commandSuggestions.length - 1
        );
      } else if (e.key === "Tab" || e.key === "Enter") {
        e.preventDefault();
        if (activeSuggestion >= 0) {
          const selectedCommand = commandSuggestions[activeSuggestion];
          setValue(selectedCommand.prefix + " ");
          setShowCommandPalette(false);
        }
      } else if (e.key === "Escape") {
        e.preventDefault();
        setShowCommandPalette(false);
      }
    } else if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (value.trim()) {
        handleSendMessage();
      }
    }
  };

  const selectCommandSuggestion = (index: number) => {
    const selectedCommand = commandSuggestions[index];
    setValue(selectedCommand.prefix + " ");
    setShowCommandPalette(false);
    textareaRef.current?.focus();
  };

  const handleAttachFile = () => {
    const mockFileName = `attachment-${Math.floor(Math.random() * 1000)}.json`;
    setAttachments((prev) => [...prev, mockFileName]);
  };

  const removeAttachment = (index: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index));
  };

  const handleViewRequirements = async () => {
    if (!requirementsContent) {
      await fetchRequirements();
    }
    setShowRequirementsModal(true);
  };

  const displayError = engineError || contextError;

  return (
    <div className="flex-1 flex w-full h-full overflow-hidden bg-brand-bg text-brand-headline transition-colors duration-200">
      {/* Left Claude-style Sidebar */}
      <ChatSidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen((prev) => !prev)}
      />

      {/* Main Content Area: Intake Form or Active Session Chat */}
      <div className="flex-1 flex flex-col h-full overflow-hidden relative">
        {!sessionId ? (
          <div className="flex-1 overflow-y-auto">
            <div className="relative">
              {!sidebarOpen && (
                <button
                  type="button"
                  onClick={() => setSidebarOpen(true)}
                  className="absolute top-4 left-4 z-20 p-2 text-brand-body hover:text-brand-headline rounded-lg bg-brand-card/80 backdrop-blur-md border border-brand-border shadow-xs hover:bg-brand-subtle transition-colors cursor-pointer flex items-center gap-1.5 text-xs font-medium"
                  title="Open conversations sidebar"
                >
                  <PanelLeft className="w-4 h-4" />
                  <span>Conversations</span>
                </button>
              )}
              <IntakeForm
                onSubmit={startSession}
                onSelectSession={selectSession}
                isLoading={isSending}
                error={displayError}
              />
            </div>
          </div>
        ) : isLoadingSession ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-3 text-brand-body p-6">
            <LoaderIcon className="w-6 h-6 animate-spin text-brand-accent" />
            <span className="text-xs font-medium">Loading session conversation...</span>
          </div>
        ) : (
          <div
            key={sessionId || "active-session-view"}
            className="min-h-full flex-1 flex flex-col w-full items-center p-4 sm:p-6 relative overflow-y-auto"
          >
            <div className="w-full max-w-3xl mx-auto flex-1 flex flex-col relative z-10">
              {/* Active Session Header / Status Ribbon */}
              <div className="flex items-center justify-between pb-3 mb-2 border-b border-brand-border text-xs text-brand-body transition-colors duration-200">
                <div className="flex items-center gap-2 min-w-0">
                  {!sidebarOpen && (
                    <button
                      type="button"
                      onClick={() => setSidebarOpen(true)}
                      className="p-1.5 text-brand-body hover:text-brand-headline rounded-lg hover:bg-brand-subtle transition-colors cursor-pointer mr-0.5"
                      title="Open conversations sidebar"
                    >
                      <PanelLeft className="w-4 h-4" />
                    </button>
                  )}
                  <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block animate-pulse shrink-0" />
                  <span className="font-semibold text-brand-headline truncate max-w-[180px] sm:max-w-md">
                    {intakeData?.projectName || "Business Analyst Session"}
                  </span>
                  <span className="text-[10px] bg-brand-subtle px-2 py-0.5 rounded-full border border-brand-border font-medium text-brand-accent shrink-0">
                    BA Active
                  </span>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={newSession}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-brand-subtle hover:bg-brand-subtle-hover text-brand-headline border border-brand-border transition-colors cursor-pointer text-xs font-medium"
                    title="Start a fresh project intake"
                  >
                    <PlusCircle className="w-3.5 h-3.5 text-brand-accent" />
                    <span>New BA Session</span>
                  </button>

                  <button
                    onClick={clearHistory}
                    className="p-1.5 text-brand-body hover:text-brand-headline rounded-lg hover:bg-brand-subtle transition-colors cursor-pointer"
                    title="Clear chat messages"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Requirements Ready Banner */}
              <AnimatePresence>
                {readyForRequirements && (
                  <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className="mb-4 p-4 rounded-xl border border-emerald-500/40 bg-emerald-500/10 text-brand-headline flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-md transition-colors duration-200"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-xl bg-emerald-500 text-white flex items-center justify-center shrink-0 shadow-xs">
                        <FileCheck className="w-5 h-5" />
                      </div>
                      <div>
                        <h4 className="text-xs font-bold text-emerald-800 dark:text-emerald-300">
                          Your requirements document is ready
                        </h4>
                        <p className="text-[11px] text-brand-body leading-relaxed">
                          Discovery completed! Requirements have been structured and saved to disk.
                        </p>
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={handleViewRequirements}
                      className="px-3.5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold flex items-center gap-1.5 shadow-sm active:scale-95 transition-all cursor-pointer shrink-0"
                    >
                      <FileText className="w-3.5 h-3.5" />
                      <span>View Requirements</span>
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Messages Stream */}
              <div className="flex-1 overflow-y-auto space-y-4 py-2 pr-1 mb-4">
                {messages.map((msg) => (
                  <MessageBubble key={msg.id} message={msg} />
                ))}

                {/* In-stream typing indicator */}
                {isSending && (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex items-start"
                  >
                    <div className="rounded-2xl rounded-tl-sm bg-brand-card border border-brand-border px-4 py-3 shadow-card transition-colors duration-200">
                      <div className="flex items-center gap-2 text-sm text-brand-headline font-medium">
                        <span className="text-xs font-semibold text-brand-accent flex items-center gap-1">
                          <Briefcase className="w-3.5 h-3.5" />
                          Business Analyst
                        </span>
                        <span className="text-brand-body text-xs">• Analyzing</span>
                        <TypingDots />
                      </div>
                    </div>
                  </motion.div>
                )}

                <div ref={messagesEndRef} />
              </div>

              {/* Inline Engine / Ollama Error Banner */}
              <AnimatePresence>
                {displayError && (
                  <motion.div
                    initial={{ opacity: 0, y: -8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    className="mb-4 p-3.5 rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300 text-xs flex items-start gap-3 shadow-sm transition-colors duration-200"
                  >
                    <AlertCircle className="w-4 h-4 text-rose-500 mt-0.5 shrink-0" />
                    <div className="flex-1 whitespace-pre-wrap font-mono leading-relaxed">
                      {displayError}
                    </div>
                    <button
                      type="button"
                      onClick={probeEngine}
                      disabled={isCheckingStatus}
                      className="text-xs px-2.5 py-1 rounded bg-rose-500/20 hover:bg-rose-500/30 text-rose-800 dark:text-rose-200 border border-rose-500/30 transition-colors shrink-0 flex items-center gap-1 cursor-pointer font-medium"
                    >
                      <RefreshCw
                        className={cn(
                          "w-3 h-3",
                          isCheckingStatus && "animate-spin"
                        )}
                      />
                      <span>Retry</span>
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Input Card */}
              <div className="relative bg-brand-card rounded-xl border border-brand-border shadow-card focus-within:border-brand-accent transition-colors duration-200 mt-auto">
                {/* Command Palette Dropdown */}
                <AnimatePresence>
                  {showCommandPalette && (
                    <motion.div
                      ref={commandPaletteRef}
                      className="absolute left-0 right-0 bottom-full mb-2 bg-brand-card rounded-xl shadow-lg border border-brand-border overflow-hidden z-50 transition-colors duration-200"
                      initial={{ opacity: 0, y: 5 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: 5 }}
                      transition={{ duration: 0.15 }}
                    >
                      <div className="py-1">
                        {commandSuggestions.map((suggestion, index) => (
                          <div
                            key={suggestion.prefix}
                            className={cn(
                              "flex items-center gap-2 px-3 py-2 text-xs transition-colors cursor-pointer",
                              activeSuggestion === index
                                ? "bg-brand-subtle text-brand-accent font-semibold"
                                : "text-brand-body hover:bg-brand-subtle/50"
                            )}
                            onClick={() => selectCommandSuggestion(index)}
                          >
                            <div className="w-5 h-5 flex items-center justify-center text-brand-accent">
                              {suggestion.icon}
                            </div>
                            <div className="text-brand-headline">{suggestion.label}</div>
                            <div className="text-brand-body text-xs ml-auto font-mono">
                              {suggestion.prefix}
                            </div>
                          </div>
                        ))}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Text Input Area */}
                <div className="p-3 sm:p-4">
                  <Textarea
                    ref={textareaRef}
                    value={value}
                    onChange={(e) => {
                      setValue(e.target.value);
                      adjustHeight();
                    }}
                    onKeyDown={handleKeyDown}
                    placeholder="Reply to your Business Analyst... (Enter to send, Shift+Enter for newline)"
                    containerClassName="w-full"
                    className={cn(
                      "w-full px-2 py-1",
                      "resize-none",
                      "bg-transparent",
                      "border-none",
                      "text-brand-headline text-sm",
                      "focus:outline-none",
                      "placeholder:text-brand-body/60",
                      "min-h-[60px]"
                    )}
                    style={{ overflow: "hidden" }}
                    showRing={false}
                  />
                </div>

                {/* Attachments Display */}
                <AnimatePresence>
                  {attachments.length > 0 && (
                    <motion.div
                      className="px-4 pb-3 flex gap-2 flex-wrap"
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                    >
                      {attachments.map((file, index) => (
                        <div
                          key={index}
                          className="flex items-center gap-2 text-xs bg-brand-subtle py-1.5 px-3 rounded-lg text-brand-headline border border-brand-border transition-colors duration-200"
                        >
                          <span>{file}</span>
                          <button
                            onClick={() => removeAttachment(index)}
                            className="text-brand-body hover:text-brand-headline transition-colors cursor-pointer"
                          >
                            <XIcon className="w-3 h-3" />
                          </button>
                        </div>
                      ))}
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Action Row */}
                <div className="p-3 sm:p-4 border-t border-brand-border/60 flex items-center justify-between gap-4 transition-colors duration-200">
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={handleAttachFile}
                      title="Attach context file"
                      className="p-2 text-brand-body hover:text-brand-headline hover:bg-brand-subtle rounded-lg transition-colors cursor-pointer"
                    >
                      <Paperclip className="w-4 h-4" />
                    </button>

                    <button
                      type="button"
                      data-command-button
                      onClick={(e) => {
                        e.stopPropagation();
                        setShowCommandPalette((prev) => !prev);
                      }}
                      title="Command Palette"
                      className={cn(
                        "p-2 text-brand-body hover:text-brand-headline hover:bg-brand-subtle rounded-lg transition-colors cursor-pointer",
                        showCommandPalette && "bg-brand-subtle text-brand-accent"
                      )}
                    >
                      <Command className="w-4 h-4" />
                    </button>
                  </div>

                  <button
                    type="button"
                    onClick={() => handleSendMessage()}
                    disabled={isSending || !value.trim()}
                    className={cn(
                      "px-4 py-2 rounded-lg text-xs font-semibold transition-all cursor-pointer",
                      "flex items-center gap-2",
                      value.trim() && !isSending
                        ? "bg-brand-accent hover:bg-brand-accent-hover text-brand-accent-text shadow-sm active:scale-95"
                        : "bg-brand-subtle text-brand-body/50 cursor-not-allowed"
                    )}
                  >
                    {isSending ? (
                      <LoaderIcon className="w-3.5 h-3.5 animate-[spin_2s_linear_infinite]" />
                    ) : (
                      <SendIcon className="w-3.5 h-3.5" />
                    )}
                    <span>{isSending ? "Analyzing..." : "Send"}</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Requirements Modal View */}
      <RequirementsModal
        isOpen={showRequirementsModal}
        onClose={() => setShowRequirementsModal(false)}
        content={requirementsContent}
        projectName={intakeData?.projectName || "Project"}
      />
    </div>
  );
}

export default AnimatedAIChat;
