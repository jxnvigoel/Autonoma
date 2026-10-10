import React, { useState } from "react";
import {
  FileCheck,
  MessageSquare,
  Copy,
  Check,
  ArrowRight,
  Sparkles,
  Layers,
  Loader2,
} from "lucide-react";
import { QALogEntry } from "../../context/ConversationContext";

interface BAOutputViewerProps {
  requirementsContent: string | null;
  qaLog: QALogEntry[];
  projectName?: string;
  readyForRequirements?: boolean;
  onSendToPM?: () => void;
  isSendingToPM?: boolean;
}

export const BAOutputViewer: React.FC<BAOutputViewerProps> = ({
  requirementsContent,
  qaLog,
  projectName = "Project",
  readyForRequirements = false,
  onSendToPM,
  isSendingToPM = false,
}) => {
  const [activeTab, setActiveTab] = useState<"requirements" | "qalog">(
    requirementsContent ? "requirements" : "qalog"
  );
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    const textToCopy =
      activeTab === "requirements"
        ? requirementsContent || ""
        : JSON.stringify(qaLog, null, 2);
    if (!textToCopy) return;
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="h-full flex flex-col bg-brand-card rounded-2xl border border-brand-border shadow-card overflow-hidden">
      {/* Top Header & Tab Ribbon */}
      <div className="px-4 py-3 border-b border-brand-border/70 flex items-center justify-between gap-3 bg-brand-bg/40 shrink-0">
        <div className="flex items-center gap-1.5 p-1 rounded-xl bg-brand-subtle/80 border border-brand-border text-xs">
          <button
            type="button"
            onClick={() => setActiveTab("requirements")}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-lg font-medium transition-all cursor-pointer ${
              activeTab === "requirements"
                ? "bg-brand-card text-brand-headline shadow-2xs font-bold"
                : "text-brand-body hover:text-brand-headline"
            }`}
          >
            <FileCheck className="w-3.5 h-3.5 text-blue-500" />
            <span>Requirements Doc</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("qalog")}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-lg font-medium transition-all cursor-pointer ${
              activeTab === "qalog"
                ? "bg-brand-card text-brand-headline shadow-2xs font-bold"
                : "text-brand-body hover:text-brand-headline"
            }`}
          >
            <MessageSquare className="w-3.5 h-3.5 text-emerald-500" />
            <span>Q&A Log ({qaLog.length})</span>
          </button>
        </div>

        <div className="flex items-center gap-2">
          {readyForRequirements && onSendToPM && (
            <button
              type="button"
              onClick={onSendToPM}
              disabled={isSendingToPM}
              className="px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-700 text-white text-xs font-semibold flex items-center gap-1.5 shadow-sm active:scale-95 transition-all cursor-pointer disabled:opacity-50"
              title="Hand off requirements to Product Manager"
            >
              {isSendingToPM ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Handoff...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Send to PM</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </>
              )}
            </button>
          )}

          <button
            type="button"
            onClick={handleCopy}
            className="p-1.5 text-brand-body hover:text-brand-headline hover:bg-brand-subtle rounded-lg border border-brand-border transition-colors cursor-pointer flex items-center gap-1 text-[11px]"
            title="Copy content"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-500" />
                <span className="text-emerald-600 dark:text-emerald-400 text-[10px] font-semibold">
                  Copied
                </span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" />
                <span className="text-[10px]">Copy</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-3">
        {activeTab === "requirements" ? (
          requirementsContent ? (
            <div className="space-y-3">
              {requirementsContent.split("\n\n").map((chunk, idx) => {
                if (chunk.startsWith("# ")) {
                  return (
                    <div
                      key={idx}
                      className="pb-2 border-b border-brand-border/60 pt-2"
                    >
                      <h2 className="text-base sm:text-lg font-bold text-brand-headline flex items-center gap-2">
                        <Layers className="w-4 h-4 text-blue-500" />
                        <span>{chunk.replace("# ", "")}</span>
                      </h2>
                    </div>
                  );
                }
                return (
                  <div
                    key={idx}
                    className="text-xs text-brand-body whitespace-pre-wrap leading-relaxed font-sans"
                  >
                    {chunk}
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="py-12 flex flex-col items-center justify-center text-center">
              <FileCheck className="w-8 h-8 text-brand-body/30 mb-2" />
              <p className="text-xs font-semibold text-brand-headline">
                Requirements document in progress
              </p>
              <p className="text-[11px] text-brand-body mt-1 max-w-sm">
                Complete the Business Analyst discovery questions to automatically generate requirements.md.
              </p>
            </div>
          )
        ) : (
          <div className="space-y-3">
            {qaLog.length === 0 ? (
              <div className="py-12 flex flex-col items-center justify-center text-center">
                <MessageSquare className="w-8 h-8 text-brand-body/30 mb-2" />
                <p className="text-xs font-semibold text-brand-headline">
                  No Q&A recorded yet
                </p>
                <p className="text-[11px] text-brand-body mt-1">
                  Answers provided during the BA interview will appear here in real-time.
                </p>
              </div>
            ) : (
              qaLog.map((item) => (
                <div
                  key={item.id}
                  className="p-3.5 rounded-xl border border-brand-border bg-brand-bg/50 shadow-2xs space-y-2 transition-colors duration-150"
                >
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="font-mono font-bold text-blue-600 dark:text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20">
                      {item.id}
                    </span>
                    <span className="text-[10px] text-brand-body font-mono">
                      Round {item.round}
                    </span>
                  </div>

                  <div className="text-xs text-brand-headline font-medium pl-1 leading-relaxed">
                    <span className="text-brand-body text-[11px] block font-normal mb-0.5">
                      Question:
                    </span>
                    {item.question}
                  </div>

                  <div className="text-xs text-emerald-800 dark:text-emerald-300 bg-emerald-500/10 p-2.5 rounded-lg border border-emerald-500/20 leading-relaxed">
                    <span className="text-[10px] uppercase font-bold tracking-wider text-emerald-600 dark:text-emerald-400 block mb-0.5 font-mono">
                      Client Response:
                    </span>
                    {item.answer}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Footer info */}
      <div className="px-4 py-2 border-t border-brand-border/60 bg-brand-bg/30 text-[10px] font-mono text-brand-body flex items-center justify-between shrink-0">
        <span>Project: {projectName} • docs/requirements.md</span>
        <span>Entries: {qaLog.length} Q&A logged</span>
      </div>
    </div>
  );
};

export default BAOutputViewer;
