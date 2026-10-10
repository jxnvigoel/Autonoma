import React, { useState } from "react";
import {
  FileText,
  Copy,
  Check,
  Sparkles,
  Layers,
  Target,
  CheckCircle2,
  ListTodo,
  BookOpen,
} from "lucide-react";

interface PRDViewerProps {
  content: string | null;
  projectName?: string;
  isUpdating?: boolean;
}

export const PRDViewer: React.FC<PRDViewerProps> = ({
  content,
  projectName = "Project",
  isUpdating = false,
}) => {
  const [copied, setCopied] = useState(false);
  const [viewMode, setViewMode] = useState<"formatted" | "raw">("formatted");

  const handleCopy = () => {
    if (!content) return;
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!content) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-8 text-center bg-brand-card/50 rounded-xl border border-brand-border">
        <div className="w-12 h-12 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-600 dark:text-purple-400 flex items-center justify-center mb-3">
          <FileText className="w-6 h-6" />
        </div>
        <h3 className="text-sm font-bold text-brand-headline">
          PRD Drafting Pending
        </h3>
        <p className="text-xs text-brand-body max-w-sm mt-1 leading-relaxed">
          The Product Manager generates the structured PRD once started and updates it incrementally as you refine scope.
        </p>
      </div>
    );
  }

  // Parse lines into sections for rich structured presentation
  const renderFormattedSections = () => {
    const lines = content.split("\n");
    const elements: React.ReactNode[] = [];
    let currentStory: { title: string; lines: string[] } | null = null;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      // H1 Header
      if (line.startsWith("# ")) {
        elements.push(
          <div key={`h1-${i}`} className="pb-3 mb-4 border-b border-brand-border">
            <span className="text-[10px] font-mono font-semibold tracking-wider text-purple-600 dark:text-purple-400 uppercase">
              Product Requirement Document
            </span>
            <h1 className="text-xl sm:text-2xl font-black text-brand-headline tracking-tight mt-0.5">
              {line.replace("# ", "")}
            </h1>
          </div>
        );
        continue;
      }

      // H2 Section Headers
      if (line.startsWith("## ")) {
        if (currentStory) {
          elements.push(renderUserStoryCard(currentStory, `story-${i}`));
          currentStory = null;
        }

        const title = line.replace("## ", "").trim();
        let icon = <Layers className="w-4 h-4 text-purple-500" />;
        if (title.toLowerCase().includes("goal") || title.toLowerCase().includes("metric")) {
          icon = <Target className="w-4 h-4 text-emerald-500" />;
        } else if (title.toLowerCase().includes("story")) {
          icon = <ListTodo className="w-4 h-4 text-blue-500" />;
        } else if (title.toLowerCase().includes("scope") || title.toLowerCase().includes("priorit")) {
          icon = <CheckCircle2 className="w-4 h-4 text-amber-500" />;
        }

        elements.push(
          <div
            key={`h2-${i}`}
            className="flex items-center gap-2 pt-6 pb-2 text-sm font-bold text-brand-headline border-b border-brand-border/60 mt-4"
          >
            {icon}
            <span>{title}</span>
          </div>
        );
        continue;
      }

      // H3 User Story Headers
      if (line.startsWith("### ")) {
        if (currentStory) {
          elements.push(renderUserStoryCard(currentStory, `story-${i}`));
        }
        currentStory = {
          title: line.replace("### ", "").trim(),
          lines: [],
        };
        continue;
      }

      // If we are accumulating lines inside a user story card
      if (currentStory) {
        currentStory.lines.push(line);
        continue;
      }

      // Acceptance criteria check-item
      if (line.trim().startsWith("- [ ]") || line.trim().startsWith("- [x]")) {
        const isChecked = line.trim().startsWith("- [x]");
        const text = line.replace(/- \[[ x]\]/, "").trim();
        elements.push(
          <div
            key={`chk-${i}`}
            className="flex items-start gap-2.5 py-1 px-2.5 my-1 rounded-lg bg-brand-subtle/40 border border-brand-border/50 text-xs"
          >
            <div
              className={`w-3.5 h-3.5 rounded mt-0.5 flex items-center justify-center shrink-0 border ${
                isChecked
                  ? "bg-emerald-500 border-emerald-600 text-white"
                  : "border-brand-border bg-brand-card"
              }`}
            >
              {isChecked && <Check className="w-2.5 h-2.5" />}
            </div>
            <span className="text-brand-headline leading-relaxed">{text}</span>
          </div>
        );
        continue;
      }

      // Bullet items
      if (line.trim().startsWith("- ") || line.trim().startsWith("* ")) {
        const text = line.trim().substring(2);
        // Highlight Priority tags
        const isMustHave = text.includes("Must Have");
        const isShouldHave = text.includes("Should Have");
        const isCouldHave = text.includes("Could Have");
        const isOutOfScope = text.includes("Out of Scope") || text.includes("Won't Have");

        elements.push(
          <div key={`li-${i}`} className="flex items-start gap-2 py-1 text-xs pl-1">
            <span className="w-1.5 h-1.5 rounded-full bg-purple-500 shrink-0 mt-1.5" />
            <div className="flex-1 text-brand-body leading-relaxed">
              {formatInlineText(text)}
              {isMustHave && (
                <span className="ml-2 text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-rose-500/15 text-rose-600 dark:text-rose-400 font-bold border border-rose-500/30">
                  Must Have
                </span>
              )}
              {isShouldHave && (
                <span className="ml-2 text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-600 dark:text-amber-400 font-bold border border-amber-500/30">
                  Should Have
                </span>
              )}
              {isCouldHave && (
                <span className="ml-2 text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-sky-500/15 text-sky-600 dark:text-sky-400 font-bold border border-sky-500/30">
                  Could Have
                </span>
              )}
              {isOutOfScope && (
                <span className="ml-2 text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-slate-500/15 text-slate-600 dark:text-slate-400 font-bold border border-slate-500/30">
                  Deferred
                </span>
              )}
            </div>
          </div>
        );
        continue;
      }

      // Normal paragraph
      if (line.trim()) {
        elements.push(
          <p
            key={`p-${i}`}
            className="text-xs text-brand-body leading-relaxed my-1.5"
          >
            {formatInlineText(line)}
          </p>
        );
      }
    }

    if (currentStory) {
      elements.push(renderUserStoryCard(currentStory, "story-last"));
    }

    return elements;
  };

  const renderUserStoryCard = (
    story: { title: string; lines: string[] },
    key: string
  ) => {
    return (
      <div
        key={key}
        className="my-3 p-3.5 rounded-xl border border-purple-500/25 bg-purple-500/5 shadow-2xs space-y-2 transition-colors duration-150"
      >
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-bold text-purple-700 dark:text-purple-300 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-purple-500" />
            <span>{story.title}</span>
          </span>
          <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-purple-500/15 text-purple-600 dark:text-purple-300 font-semibold border border-purple-500/30">
            User Story
          </span>
        </div>

        <div className="space-y-1 text-xs text-brand-headline">
          {story.lines.map((l, idx) => {
            if (l.trim().startsWith("- [ ]") || l.trim().startsWith("- [x]")) {
              const isChecked = l.trim().startsWith("- [x]");
              const text = l.replace(/- \[[ x]\]/, "").trim();
              return (
                <div
                  key={`ac-${idx}`}
                  className="flex items-start gap-2 py-0.5 text-[11px] text-brand-body pl-2"
                >
                  <div
                    className={`w-3 h-3 rounded mt-0.5 flex items-center justify-center shrink-0 border ${
                      isChecked
                        ? "bg-emerald-500 border-emerald-600 text-white"
                        : "border-brand-border bg-brand-card"
                    }`}
                  >
                    {isChecked && <Check className="w-2 h-2" />}
                  </div>
                  <span>{formatInlineText(text)}</span>
                </div>
              );
            }
            if (l.trim().startsWith("- ") || l.trim().startsWith("* ")) {
              return (
                <div key={`s-li-${idx}`} className="text-xs text-brand-body pl-2">
                  {formatInlineText(l.trim().substring(2))}
                </div>
              );
            }
            if (l.trim()) {
              return (
                <p key={`s-p-${idx}`} className="text-xs text-brand-headline leading-relaxed">
                  {formatInlineText(l)}
                </p>
              );
            }
            return null;
          })}
        </div>
      </div>
    );
  };

  const formatInlineText = (text: string): React.ReactNode => {
    // Bold parsing
    const parts = text.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, idx) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return (
          <strong key={idx} className="font-semibold text-brand-headline">
            {part.slice(2, -2)}
          </strong>
        );
      }
      return part;
    });
  };

  return (
    <div className="h-full flex flex-col bg-brand-card rounded-2xl border border-brand-border shadow-card overflow-hidden">
      {/* Top Header & Actions Ribbon */}
      <div className="px-4 py-3 border-b border-brand-border/70 flex items-center justify-between gap-3 bg-brand-bg/40 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-7 h-7 rounded-lg bg-purple-500/15 border border-purple-500/30 text-purple-600 dark:text-purple-400 flex items-center justify-center shrink-0">
            <BookOpen className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-bold text-brand-headline truncate">
                Product Requirement Document
              </span>
              {isUpdating && (
                <span className="text-[9px] px-1.5 py-0.2 rounded-full bg-amber-500/20 text-amber-600 dark:text-amber-400 font-mono animate-pulse font-semibold">
                  updating...
                </span>
              )}
            </div>
            <span className="text-[10px] text-brand-body truncate block">
              Grounded in BA discovery • {projectName}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          <button
            type="button"
            onClick={() => setViewMode(viewMode === "formatted" ? "raw" : "formatted")}
            className="px-2.5 py-1 text-[11px] rounded-lg border border-brand-border bg-brand-card hover:bg-brand-subtle text-brand-body hover:text-brand-headline transition-colors cursor-pointer font-medium"
          >
            {viewMode === "formatted" ? "Raw Markdown" : "Rich View"}
          </button>

          <button
            type="button"
            onClick={handleCopy}
            className="p-1.5 text-brand-body hover:text-brand-headline hover:bg-brand-subtle rounded-lg border border-brand-border transition-colors cursor-pointer flex items-center gap-1 text-[11px]"
            title="Copy PRD to clipboard"
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
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-2">
        {viewMode === "formatted" ? (
          <div className="space-y-1">{renderFormattedSections()}</div>
        ) : (
          <pre className="text-xs font-mono whitespace-pre-wrap text-brand-headline bg-brand-bg/60 p-4 rounded-xl border border-brand-border leading-relaxed select-text">
            {content}
          </pre>
        )}
      </div>

      {/* Footer Info */}
      <div className="px-4 py-2 border-t border-brand-border/60 bg-brand-bg/30 text-[10px] font-mono text-brand-body flex items-center justify-between shrink-0">
        <span>Artifact: data/projects/.../prd.md</span>
        <span>Word count: {content.split(/\s+/).filter(Boolean).length}</span>
      </div>
    </div>
  );
};

export default PRDViewer;
