import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  FileText,
  X,
  Copy,
  Check,
  Download,
  Sparkles,
  ShieldCheck,
} from "lucide-react";

interface RequirementsModalProps {
  isOpen: boolean;
  onClose: () => void;
  content: string | null;
  projectName?: string;
}

export const RequirementsModal: React.FC<RequirementsModalProps> = ({
  isOpen,
  onClose,
  content,
  projectName = "Project",
}) => {
  const [copied, setCopied] = useState(false);

  if (!isOpen || !content) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${projectName.toLowerCase().replace(/\s+/g, "_")}_requirements.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 md:p-8 bg-black/60 backdrop-blur-sm">
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 12 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 12 }}
          transition={{ duration: 0.22, ease: "easeOut" }}
          className="w-full max-w-4xl max-h-[85vh] bg-brand-card border border-brand-border rounded-2xl shadow-2xl flex flex-col overflow-hidden text-brand-headline transition-colors duration-200"
        >
          {/* Modal Header */}
          <div className="px-6 py-4 border-b border-brand-border flex items-center justify-between bg-brand-card shrink-0">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-brand-accent text-brand-accent-text flex items-center justify-center shadow-xs">
                <FileText className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-bold tracking-tight text-brand-headline">
                    requirements.md
                  </h3>
                  <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
                    <ShieldCheck className="w-3 h-3" />
                    Verified BA Output
                  </span>
                </div>
                <p className="text-xs text-brand-body">
                  Generated requirements specification for <span className="font-semibold text-brand-headline">{projectName}</span>
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleCopy}
                className="px-3 py-1.5 rounded-lg bg-brand-subtle hover:bg-brand-subtle-hover text-brand-headline border border-brand-border text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer"
                title="Copy markdown content"
              >
                {copied ? (
                  <Check className="w-3.5 h-3.5 text-emerald-500" />
                ) : (
                  <Copy className="w-3.5 h-3.5" />
                )}
                <span>{copied ? "Copied" : "Copy"}</span>
              </button>

              <button
                onClick={handleDownload}
                className="px-3 py-1.5 rounded-lg bg-brand-subtle hover:bg-brand-subtle-hover text-brand-headline border border-brand-border text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer"
                title="Download as .md file"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Export .md</span>
              </button>

              <button
                onClick={onClose}
                className="p-1.5 rounded-lg hover:bg-brand-subtle text-brand-body hover:text-brand-headline transition-colors cursor-pointer ml-1"
                title="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Modal Body - Markdown Document */}
          <div className="flex-1 overflow-y-auto p-6 sm:p-8 bg-brand-bg/50 select-text">
            <div className="max-w-3xl mx-auto bg-brand-card p-6 sm:p-8 rounded-xl border border-brand-border shadow-sm">
              <div className="flex items-center gap-2 mb-4 pb-3 border-b border-brand-border/60 text-xs text-brand-body font-mono">
                <Sparkles className="w-4 h-4 text-brand-accent" />
                <span>Grounded Specification • Generated by Autonoma Business Analyst</span>
              </div>
              <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-brand-headline overflow-x-auto">
                {content}
              </pre>
            </div>
          </div>

          {/* Modal Footer */}
          <div className="px-6 py-3 border-t border-brand-border bg-brand-card flex items-center justify-between text-xs text-brand-body shrink-0">
            <span>Written to <code className="font-mono text-brand-headline">docs/requirements.md</code></span>
            <button
              onClick={onClose}
              className="px-4 py-1.5 rounded-lg bg-brand-accent hover:bg-brand-accent-hover text-brand-accent-text font-semibold text-xs transition-colors cursor-pointer"
            >
              Done
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};

export default RequirementsModal;
