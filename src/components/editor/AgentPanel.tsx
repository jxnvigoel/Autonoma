import React, { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Send,
  Loader2,
  Trash2,
  FileCode,
  Sparkles,
  ChevronRight,
  Bot,
  AlertCircle,
  Code2,
  CheckCircle2,
} from "lucide-react";
import { useConversation } from "../../context/ConversationContext";
import { MessageBubble, TypingDots } from "../chat/MessageBubble";
import { cn } from "../../lib/utils";

interface ActiveFile {
  path: string;
  name: string;
  language: string;
  content: string;
}

interface AgentPanelProps {
  isOpen: boolean;
  onToggle: () => void;
  activeFile: ActiveFile;
}

export const AgentPanel: React.FC<AgentPanelProps> = ({
  isOpen,
  onToggle,
  activeFile,
}) => {
  const [inputPrompt, setInputPrompt] = useState("");
  const [includeFileContext, setIncludeFileContext] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const {
    messages,
    isSending,
    error,
    sendMessage,
    clearHistory,
  } = useConversation();

  const fileLines = activeFile.content.split("\n").length;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending, isOpen]);

  const handleSend = async (customPrompt?: string) => {
    const text = (customPrompt ?? inputPrompt).trim();
    if (!text || isSending) return;

    setInputPrompt("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    try {
      if (includeFileContext && activeFile) {
        await sendMessage(text, {
          path: activeFile.path,
          content: activeFile.content,
        });
      } else {
        await sendMessage(text);
      }
    } catch {
      // Error handled in context
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleQuickPrompt = (promptText: string) => {
    handleSend(promptText);
  };

  const quickPrompts = [
    {
      label: "Explain this file",
      prompt: `Explain the architecture and purpose of ${activeFile.path}.`,
    },
    {
      label: "Review for bugs",
      prompt: `Review ${activeFile.path} for potential bugs, edge cases, or performance improvements.`,
    },
    {
      label: "Refactor & optimize",
      prompt: `Suggest clean refactorings or optimizations for the code in ${activeFile.path}.`,
    },
  ];

  return (
    <AnimatePresence initial={false}>
      {isOpen ? (
        <motion.aside
          key="agent-panel-open"
          initial={{ width: 0, opacity: 0 }}
          animate={{ width: 420, opacity: 1 }}
          exit={{ width: 0, opacity: 0 }}
          transition={{ duration: 0.22, ease: "easeInOut" }}
          className="h-full border-l border-brand-border bg-brand-bg flex flex-col overflow-hidden shrink-0 shadow-lg relative z-20 select-none"
        >
          {/* Header */}
          <div className="px-4 py-3 border-b border-brand-border bg-brand-card flex items-center justify-between transition-colors duration-200 shrink-0">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-7 h-7 rounded-lg bg-brand-accent/10 border border-brand-accent/30 text-brand-accent flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-bold text-brand-headline truncate">
                    AI Agent
                  </span>
                  <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-brand-subtle text-brand-accent font-semibold border border-brand-border">
                    llama3.2:3b
                  </span>
                </div>
                <p className="text-[10px] text-brand-body truncate">
                  Shared conversation memory
                </p>
              </div>
            </div>

            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={clearHistory}
                title="Clear shared conversation"
                className="p-1.5 text-brand-body hover:text-brand-headline hover:bg-brand-subtle rounded-md transition-colors cursor-pointer"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                onClick={onToggle}
                title="Collapse Agent Panel"
                className="p-1.5 text-brand-body hover:text-brand-headline hover:bg-brand-subtle rounded-md transition-colors cursor-pointer"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Active File Context Notification Banner */}
          <div className="px-3.5 py-2 bg-brand-subtle/50 border-b border-brand-border flex items-center justify-between text-[11px] text-brand-body transition-colors duration-200 shrink-0">
            <div className="flex items-center gap-1.5 truncate">
              <FileCode className="w-3.5 h-3.5 text-brand-accent shrink-0" />
              <span className="font-mono text-brand-headline truncate font-medium">
                {activeFile.name}
              </span>
              <span className="text-[10px] text-brand-body/80">
                ({fileLines} lines)
              </span>
            </div>
            <button
              type="button"
              onClick={() => setIncludeFileContext((prev) => !prev)}
              className={cn(
                "text-[10px] px-2 py-0.5 rounded-full border transition-colors flex items-center gap-1 cursor-pointer shrink-0 font-medium",
                includeFileContext
                  ? "bg-brand-accent/10 border-brand-accent/30 text-brand-accent"
                  : "bg-brand-card border-brand-border text-brand-body"
              )}
              title="Toggle injecting current file context into prompt"
            >
              {includeFileContext ? (
                <>
                  <CheckCircle2 className="w-2.5 h-2.5" />
                  <span>File Context ON</span>
                </>
              ) : (
                <span>File Context OFF</span>
              )}
            </button>
          </div>

          {/* Conversation Stream */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3.5 select-text">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-4 space-y-3 my-auto">
                <div className="w-10 h-10 rounded-xl bg-brand-card border border-brand-border shadow-card flex items-center justify-center text-brand-accent">
                  <Sparkles className="w-5 h-5" />
                </div>
                <div className="space-y-1">
                  <p className="text-xs font-semibold text-brand-headline">
                    Code Editor Assistant
                  </p>
                  <p className="text-[11px] text-brand-body max-w-[240px]">
                    Ask questions about <span className="font-mono font-medium text-brand-headline">{activeFile.name}</span> or anything in your project.
                  </p>
                </div>

                <div className="w-full space-y-1.5 pt-2">
                  {quickPrompts.map((item) => (
                    <button
                      key={item.label}
                      onClick={() => handleQuickPrompt(item.prompt)}
                      className="w-full text-left px-3 py-2 rounded-lg bg-brand-card hover:bg-brand-subtle border border-brand-border text-xs text-brand-headline transition-colors shadow-sm cursor-pointer flex items-center justify-between group"
                    >
                      <span className="truncate">{item.label}</span>
                      <ChevronRight className="w-3 h-3 text-brand-body group-hover:translate-x-0.5 transition-transform" />
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <>
                {messages.map((msg) => (
                  <MessageBubble key={msg.id} message={msg} compact />
                ))}

                {isSending && (
                  <motion.div
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex items-start"
                  >
                    <div className="rounded-2xl rounded-tl-sm bg-brand-card border border-brand-border px-3.5 py-2.5 shadow-card text-xs text-brand-headline flex items-center gap-2">
                      <span className="font-semibold text-brand-accent">
                        llama3.2:3b
                      </span>
                      <span>Analyzing code</span>
                      <TypingDots />
                    </div>
                  </motion.div>
                )}
                <div ref={messagesEndRef} />
              </>
            )}
          </div>

          {/* Error Banner */}
          {error && (
            <div className="px-3 py-2 bg-rose-500/10 border-t border-rose-500/30 text-rose-600 dark:text-rose-300 text-xs flex items-start gap-2 shrink-0">
              <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              <span className="truncate">{error}</span>
            </div>
          )}

          {/* Bottom Input Area */}
          <div className="p-3 border-t border-brand-border bg-brand-card shrink-0 transition-colors duration-200">
            {includeFileContext && (
              <div className="mb-2 flex items-center gap-1.5 text-[10px] text-brand-body px-1">
                <Code2 className="w-3 h-3 text-brand-accent" />
                <span className="truncate">
                  Context attached: <strong className="font-mono text-brand-headline">{activeFile.path}</strong>
                </span>
              </div>
            )}

            <div className="relative rounded-xl border border-brand-border bg-brand-bg focus-within:border-brand-accent transition-colors shadow-inner flex flex-col">
              <textarea
                ref={textareaRef}
                value={inputPrompt}
                onChange={(e) => {
                  setInputPrompt(e.target.value);
                  e.target.style.height = "auto";
                  e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
                }}
                onKeyDown={handleKeyDown}
                placeholder={`Ask about ${activeFile.name}... (Enter to send, Shift+Enter for newline)`}
                rows={2}
                className="w-full bg-transparent px-3 py-2 text-xs text-brand-headline placeholder:text-brand-body/60 resize-none focus:outline-none min-h-[48px] max-h-[120px] select-text"
              />

              <div className="px-2 py-1.5 border-t border-brand-border/40 flex items-center justify-between">
                <span className="text-[10px] text-brand-body font-mono">
                  {inputPrompt.length} chars
                </span>
                <button
                  type="button"
                  onClick={() => handleSend()}
                  disabled={isSending || !inputPrompt.trim()}
                  className={cn(
                    "px-3 py-1 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer",
                    inputPrompt.trim() && !isSending
                      ? "bg-brand-accent hover:bg-brand-accent-hover text-brand-accent-text shadow-sm active:scale-95"
                      : "bg-brand-subtle text-brand-body/50 cursor-not-allowed"
                  )}
                >
                  {isSending ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <Send className="w-3 h-3" />
                  )}
                  <span>{isSending ? "Thinking..." : "Send"}</span>
                </button>
              </div>
            </div>
          </div>
        </motion.aside>
      ) : null}
    </AnimatePresence>
  );
};

export default AgentPanel;
