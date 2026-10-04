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
  Trash2,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import {
  sendChatMessage,
  checkEngineStatus,
  EngineStatus,
} from "@/lib/engine";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: Date;
  meta?: {
    duration?: number;
    token_count?: number;
  };
}

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
  ({ className, containerClassName, showRing = true, ...props }, ref) => {
    const [isFocused, setIsFocused] = React.useState(false);

    return (
      <div className={cn("relative", containerClassName)}>
        <textarea
          className={cn(
            "flex min-h-[60px] w-full rounded-md border border-transparent bg-transparent px-3 py-2 text-sm",
            "transition-all duration-200 ease-in-out",
            "placeholder:text-white/30 text-white/90",
            "disabled:cursor-not-allowed disabled:opacity-50",
            showRing
              ? "focus-visible:outline-none focus-visible:ring-0 focus-visible:ring-offset-0"
              : "",
            className
          )}
          ref={ref}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          {...props}
        />

        {showRing && isFocused && (
          <motion.span
            className="absolute inset-0 rounded-md pointer-events-none ring-2 ring-offset-0 ring-violet-500/30"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          />
        )}
      </div>
    );
  }
);
Textarea.displayName = "Textarea";

export function AnimatedAIChat() {
  const [value, setValue] = useState("");
  const [attachments, setAttachments] = useState<string[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [activeSuggestion, setActiveSuggestion] = useState<number>(-1);
  const [showCommandPalette, setShowCommandPalette] = useState(false);
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  const [inputFocused, setInputFocused] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [engineStatus, setEngineStatus] = useState<EngineStatus | null>(null);
  const [engineError, setEngineError] = useState<string | null>(null);
  const [isCheckingStatus, setIsCheckingStatus] = useState(true);

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
      if (!engineStatus || engineStatus.status === "starting") {
        probeEngine();
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [probeEngine, engineStatus]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

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
    const handleMouseMove = (e: MouseEvent) => {
      setMousePosition({ x: e.clientX, y: e.clientY });
    };
    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);

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
    if (!textToSend || isTyping) return;

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: textToSend,
      createdAt: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setValue("");
    adjustHeight(true);
    setIsTyping(true);
    setEngineError(null);

    try {
      const data = await sendChatMessage(textToSend);
      const botMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: data.response,
        createdAt: new Date(),
        meta: {
          duration: data.duration,
          token_count: data.token_count,
        },
      };
      setMessages((prev) => [...prev, botMessage]);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setEngineError(message);
    } finally {
      setIsTyping(false);
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

  const clearChat = () => {
    setMessages([]);
    setEngineError(null);
  };

  return (
    <div className="min-h-screen flex flex-col w-full items-center bg-transparent text-white p-4 sm:p-6 relative overflow-hidden">
      {/* Background Animated Gradients */}
      <div className="absolute inset-0 w-full h-full overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-violet-500/10 rounded-full mix-blend-normal filter blur-[128px] animate-pulse" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-indigo-500/10 rounded-full mix-blend-normal filter blur-[128px] animate-pulse delay-700" />
        <div className="absolute top-1/4 right-1/3 w-64 h-64 bg-fuchsia-500/10 rounded-full mix-blend-normal filter blur-[96px] animate-pulse delay-1000" />
      </div>

      <div className="w-full max-w-3xl mx-auto flex-1 flex flex-col relative z-10">
        {/* Header / Intro if no messages */}
        {messages.length === 0 ? (
          <motion.div
            className="flex-1 flex flex-col items-center justify-center space-y-6 my-auto py-12"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: "easeOut" }}
          >
            <div className="text-center space-y-3">
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2, duration: 0.5 }}
                className="inline-block"
              >
                <h1 className="text-3xl sm:text-4xl font-medium tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white via-white/90 to-white/50 pb-1">
                  How can I help today?
                </h1>
                <motion.div
                  className="h-px bg-gradient-to-r from-transparent via-white/20 to-transparent"
                  initial={{ width: 0, opacity: 0 }}
                  animate={{ width: "100%", opacity: 1 }}
                  transition={{ delay: 0.5, duration: 0.8 }}
                />
              </motion.div>
              <p className="text-sm text-white/40">
                Connected to Python Engine (<span className="text-emerald-400">FastAPI :8765</span>) •{" "}
                <span className="text-indigo-400">llama3.2:3b</span> • Apple Metal M4
              </p>
            </div>
          </motion.div>
        ) : (
          /* Messages Stream */
          <div className="flex-1 overflow-y-auto space-y-4 py-4 pr-1 mb-4">
            <div className="flex justify-between items-center pb-2 border-b border-white/[0.05] text-xs text-white/40">
              <span>Conversation with Llama 3.2 3B via Python Engine</span>
              <button
                onClick={clearChat}
                className="flex items-center gap-1.5 hover:text-white/80 transition-colors cursor-pointer"
                title="Clear conversation"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Clear chat</span>
              </button>
            </div>

            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25 }}
                className={cn(
                  "flex flex-col",
                  msg.role === "user" ? "items-end" : "items-start"
                )}
              >
                {msg.role === "user" ? (
                  <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-gradient-to-br from-indigo-600/30 to-violet-600/30 backdrop-blur-md border border-indigo-500/30 px-4 py-3 text-sm text-white shadow-lg">
                    {msg.content}
                  </div>
                ) : (
                  <div className="max-w-[90%] rounded-2xl rounded-tl-sm bg-white/[0.03] backdrop-blur-xl border border-white/[0.08] px-4 py-3.5 text-sm text-white/90 shadow-xl space-y-2">
                    <div className="whitespace-pre-wrap leading-relaxed">
                      {msg.content}
                    </div>
                    {msg.meta?.duration !== undefined && (
                      <div className="text-[11px] text-white/40 font-mono pt-1.5 border-t border-white/[0.06] flex items-center gap-2">
                        <span>
                          Duration: {(msg.meta.duration / 1e9).toFixed(2)}s
                        </span>
                        <span>•</span>
                        <span>Tokens: {msg.meta.token_count ?? "N/A"}</span>
                      </div>
                    )}
                  </div>
                )}
              </motion.div>
            ))}

            {/* In-stream typing indicator */}
            {isTyping && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex items-start"
              >
                <div className="rounded-2xl rounded-tl-sm bg-white/[0.03] backdrop-blur-xl border border-white/[0.08] px-4 py-3 shadow-xl">
                  <div className="flex items-center gap-2 text-sm text-white/70">
                    <span className="text-xs font-semibold text-indigo-400">
                      llama3.2:3b
                    </span>
                    <span>Thinking</span>
                    <TypingDots />
                  </div>
                </div>
              </motion.div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}

        {/* Inline Engine / Ollama Error or Starting Banner */}
        <AnimatePresence>
          {engineError && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="mb-4 p-3.5 rounded-xl border border-rose-500/30 bg-rose-950/40 backdrop-blur-xl text-rose-200 text-xs flex items-start gap-3 shadow-xl"
            >
              <AlertCircle className="w-4 h-4 text-rose-400 mt-0.5 shrink-0" />
              <div className="flex-1 whitespace-pre-wrap font-mono leading-relaxed">
                {engineError}
              </div>
              <button
                type="button"
                onClick={probeEngine}
                disabled={isCheckingStatus}
                className="text-xs px-2.5 py-1 rounded bg-rose-900/60 hover:bg-rose-800/80 text-rose-100 border border-rose-700/50 transition-colors shrink-0 flex items-center gap-1 cursor-pointer"
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
        <motion.div
          className="relative backdrop-blur-2xl bg-white/[0.02] rounded-2xl border border-white/[0.08] shadow-2xl mt-auto"
          initial={{ scale: 0.98 }}
          animate={{ scale: 1 }}
          transition={{ delay: 0.1 }}
        >
          {/* Command Palette Dropdown */}
          <AnimatePresence>
            {showCommandPalette && (
              <motion.div
                ref={commandPaletteRef}
                className="absolute left-4 right-4 bottom-full mb-2 backdrop-blur-xl bg-slate-950/95 rounded-lg z-50 shadow-2xl border border-white/10 overflow-hidden"
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 5 }}
                transition={{ duration: 0.15 }}
              >
                <div className="py-1">
                  {commandSuggestions.map((suggestion, index) => (
                    <motion.div
                      key={suggestion.prefix}
                      className={cn(
                        "flex items-center gap-2 px-3 py-2 text-xs transition-colors cursor-pointer",
                        activeSuggestion === index
                          ? "bg-white/10 text-white"
                          : "text-white/70 hover:bg-white/5"
                      )}
                      onClick={() => selectCommandSuggestion(index)}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: index * 0.03 }}
                    >
                      <div className="w-5 h-5 flex items-center justify-center text-white/60">
                        {suggestion.icon}
                      </div>
                      <div className="font-medium">{suggestion.label}</div>
                      <div className="text-white/40 text-xs ml-auto font-mono">
                        {suggestion.prefix}
                      </div>
                    </motion.div>
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
              onFocus={() => setInputFocused(true)}
              onBlur={() => setInputFocused(false)}
              placeholder="Ask Llama 3.2 3B anything... (Enter to send, Shift+Enter for newline, '/' for commands)"
              containerClassName="w-full"
              className={cn(
                "w-full px-3 py-2",
                "resize-none",
                "bg-transparent",
                "border-none",
                "text-white/90 text-sm",
                "focus:outline-none",
                "placeholder:text-white/20",
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
                  <motion.div
                    key={index}
                    className="flex items-center gap-2 text-xs bg-white/[0.04] py-1.5 px-3 rounded-lg text-white/70 border border-white/[0.05]"
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.9 }}
                  >
                    <span>{file}</span>
                    <button
                      onClick={() => removeAttachment(index)}
                      className="text-white/40 hover:text-white transition-colors cursor-pointer"
                    >
                      <XIcon className="w-3 h-3" />
                    </button>
                  </motion.div>
                ))}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Action Row */}
          <div className="p-3 sm:p-4 border-t border-white/[0.05] flex items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <motion.button
                type="button"
                onClick={handleAttachFile}
                whileTap={{ scale: 0.94 }}
                title="Attach context file"
                className="p-2 text-white/40 hover:text-white/90 rounded-lg transition-colors relative group cursor-pointer"
              >
                <Paperclip className="w-4 h-4" />
                <motion.span
                  className="absolute inset-0 bg-white/[0.05] rounded-lg opacity-0 group-hover:opacity-100 transition-opacity"
                  layoutId="button-highlight"
                />
              </motion.button>

              <motion.button
                type="button"
                data-command-button
                onClick={(e) => {
                  e.stopPropagation();
                  setShowCommandPalette((prev) => !prev);
                }}
                whileTap={{ scale: 0.94 }}
                title="Command Palette"
                className={cn(
                  "p-2 text-white/40 hover:text-white/90 rounded-lg transition-colors relative group cursor-pointer",
                  showCommandPalette && "bg-white/10 text-white/90"
                )}
              >
                <Command className="w-4 h-4" />
                <motion.span
                  className="absolute inset-0 bg-white/[0.05] rounded-lg opacity-0 group-hover:opacity-100 transition-opacity"
                  layoutId="button-highlight"
                />
              </motion.button>
            </div>

            <motion.button
              type="button"
              onClick={() => handleSendMessage()}
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.98 }}
              disabled={isTyping || !value.trim()}
              className={cn(
                "px-4 py-2 rounded-lg text-sm font-medium transition-all cursor-pointer",
                "flex items-center gap-2",
                value.trim() && !isTyping
                  ? "bg-white text-slate-950 shadow-lg shadow-white/10 hover:bg-white/90"
                  : "bg-white/[0.05] text-white/40 cursor-not-allowed"
              )}
            >
              {isTyping ? (
                <LoaderIcon className="w-4 h-4 animate-[spin_2s_linear_infinite]" />
              ) : (
                <SendIcon className="w-4 h-4" />
              )}
              <span>{isTyping ? "Thinking..." : "Send"}</span>
            </motion.button>
          </div>
        </motion.div>

        {/* Suggestion Chips */}
        {messages.length === 0 && (
          <div className="flex flex-wrap items-center justify-center gap-2 mt-4">
            {commandSuggestions.map((suggestion, index) => (
              <motion.button
                key={suggestion.prefix}
                onClick={() => selectCommandSuggestion(index)}
                className="flex items-center gap-2 px-3 py-2 bg-white/[0.02] hover:bg-white/[0.06] rounded-lg text-xs sm:text-sm text-white/60 hover:text-white/90 transition-all relative group cursor-pointer"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.08 }}
              >
                {suggestion.icon}
                <span>{suggestion.label}</span>
                <motion.div
                  className="absolute inset-0 border border-white/[0.05] rounded-lg"
                  initial={false}
                  animate={{
                    opacity: [0, 1],
                    scale: [0.98, 1],
                  }}
                  transition={{
                    duration: 0.3,
                    ease: "easeOut",
                  }}
                />
              </motion.button>
            ))}
          </div>
        )}
      </div>

      {/* Floating Thinking Indicator */}
      <AnimatePresence>
        {isTyping && messages.length === 0 && (
          <motion.div
            className="fixed bottom-8 mx-auto transform -translate-x-1/2 backdrop-blur-2xl bg-white/[0.04] rounded-full px-4 py-2 shadow-xl border border-white/[0.08]"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
          >
            <div className="flex items-center gap-3">
              <div className="w-8 h-7 rounded-full bg-white/[0.08] flex items-center justify-center text-center">
                <span className="text-xs font-medium text-white/90 mb-0.5">
                  llama
                </span>
              </div>
              <div className="flex items-center gap-2 text-sm text-white/70">
                <span>Thinking</span>
                <TypingDots />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Mouse Gradient Follower */}
      {inputFocused && (
        <motion.div
          className="fixed w-[50rem] h-[50rem] rounded-full pointer-events-none z-0 opacity-[0.02] bg-gradient-to-r from-violet-500 via-fuchsia-500 to-indigo-500 blur-[96px]"
          animate={{
            x: mousePosition.x - 400,
            y: mousePosition.y - 400,
          }}
          transition={{
            type: "spring",
            damping: 25,
            stiffness: 150,
            mass: 0.5,
          }}
        />
      )}
    </div>
  );
}

function TypingDots() {
  return (
    <div className="flex items-center ml-1">
      {[1, 2, 3].map((dot) => (
        <motion.div
          key={dot}
          className="w-1.5 h-1.5 bg-white/90 rounded-full mx-0.5"
          initial={{ opacity: 0.3 }}
          animate={{
            opacity: [0.3, 0.9, 0.3],
            scale: [0.85, 1.1, 0.85],
          }}
          transition={{
            duration: 1.2,
            repeat: Infinity,
            delay: dot * 0.15,
            ease: "easeInOut",
          }}
          style={{
            boxShadow: "0 0 4px rgba(255, 255, 255, 0.3)",
          }}
        />
      ))}
    </div>
  );
}

export default AnimatedAIChat;
