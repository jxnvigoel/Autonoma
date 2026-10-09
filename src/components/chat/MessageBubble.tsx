import React, { useState } from "react";
import { motion } from "framer-motion";
import { Copy, Check, FileCode, Clock } from "lucide-react";
import { cn } from "../../lib/utils";
import { ChatMessage } from "../../lib/engine";

interface MessageBubbleProps {
  message: ChatMessage;
  compact?: boolean;
}

export const TypingDots: React.FC = () => {
  return (
    <div className="flex items-center ml-1">
      {[1, 2, 3].map((dot) => (
        <motion.div
          key={dot}
          className="w-1.5 h-1.5 bg-brand-accent rounded-full mx-0.5"
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
        />
      ))}
    </div>
  );
};

export const MessageBubble: React.FC<MessageBubbleProps> = ({
  message,
  compact = false,
}) => {
  const [copied, setCopied] = useState(false);
  const [showFullContext, setShowFullContext] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isUser = message.role === "user";

  // Parse file context prefix if present: "Current file: {path}\n\n{content}\n\n---\nUser: {prompt}"
  let displayContent = message.content;
  let attachedFilePath: string | null = null;
  let attachedFileSnippet: string | null = null;

  if (isUser && message.content.startsWith("Current file:")) {
    const splitParts = message.content.split("\n\n---\nUser: ");
    if (splitParts.length >= 2) {
      displayContent = splitParts.slice(1).join("\n\n---\nUser: ");
      const headerPart = splitParts[0];
      const match = headerPart.match(/^Current file:\s*([^\n]+)(?:\n\n([\s\S]*))?$/);
      if (match) {
        attachedFilePath = match[1].trim();
        attachedFileSnippet = match[2]?.trim() || null;
      }
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18 }}
      className={cn("flex flex-col group", isUser ? "items-end" : "items-start")}
    >
      {isUser ? (
        <div
          className={cn(
            "rounded-2xl rounded-tr-sm bg-brand-accent text-brand-accent-text px-4 py-2.5 shadow-sm transition-colors duration-200 flex flex-col gap-1.5",
            compact ? "max-w-[92%] text-xs" : "max-w-[85%] text-sm"
          )}
        >
          {attachedFilePath && (
            <div className="flex flex-col gap-1 pb-1.5 border-b border-white/20 text-[11px]">
              <div className="flex items-center justify-between gap-2">
                <span className="flex items-center gap-1.5 font-mono opacity-90 font-medium">
                  <FileCode className="w-3 h-3 text-brand-accent-text/80" />
                  <span className="truncate max-w-[200px]">{attachedFilePath}</span>
                </span>
                {attachedFileSnippet && (
                  <button
                    type="button"
                    onClick={() => setShowFullContext((prev) => !prev)}
                    className="text-[10px] underline opacity-80 hover:opacity-100 cursor-pointer"
                  >
                    {showFullContext ? "hide code" : "view code"}
                  </button>
                )}
              </div>
              {showFullContext && attachedFileSnippet && (
                <pre className="max-h-36 overflow-y-auto bg-black/20 p-2 rounded text-[10px] font-mono whitespace-pre-wrap">
                  {attachedFileSnippet}
                </pre>
              )}
            </div>
          )}
          <div className="whitespace-pre-wrap leading-relaxed">
            {displayContent}
          </div>
        </div>
      ) : (
        <div
          className={cn(
            "rounded-2xl rounded-tl-sm bg-brand-card border border-brand-border px-4 py-3 text-brand-headline shadow-card space-y-2 transition-colors duration-200 relative group/bubble",
            compact ? "max-w-[95%] text-xs" : "max-w-[90%] text-sm"
          )}
        >
          <div className="flex items-center justify-between pb-1 text-[11px] font-semibold text-brand-accent border-b border-brand-border/40">
            <span className="flex items-center gap-1">
              <span>llama3.2:3b</span>
            </span>
            <button
              onClick={handleCopy}
              className="opacity-0 group-hover/bubble:opacity-100 hover:text-brand-headline transition-opacity p-0.5 rounded text-brand-body cursor-pointer flex items-center gap-1"
              title="Copy message"
            >
              {copied ? (
                <Check className="w-3 h-3 text-emerald-500" />
              ) : (
                <Copy className="w-3 h-3" />
              )}
              <span className="text-[10px]">{copied ? "Copied" : "Copy"}</span>
            </button>
          </div>

          <div className="whitespace-pre-wrap leading-relaxed font-sans select-text">
            {displayContent}
          </div>

          {message.meta?.duration !== undefined && (
            <div className="text-[10px] text-brand-body font-mono pt-1.5 border-t border-brand-border/60 flex items-center justify-between gap-2 transition-colors duration-200">
              <span className="flex items-center gap-1">
                <Clock className="w-2.5 h-2.5" />
                {(message.meta.duration / 1e9).toFixed(2)}s
              </span>
              <span>Tokens: {message.meta.token_count ?? "N/A"}</span>
            </div>
          )}
        </div>
      )}
    </motion.div>
  );
};
