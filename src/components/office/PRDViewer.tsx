import React, { useState } from "react";
import {
  FileText,
  Copy,
  Check,
  Layers,
  Target,
  CheckCircle2,
  ListTodo,
  BookOpen,
  Calculator,
  Coins,
  Cpu,
  ShieldAlert,
  Info,
} from "lucide-react";
import { PMEstimateData } from "../../lib/engine";

interface PRDViewerProps {
  content: string | null;
  projectName?: string;
  isUpdating?: boolean;
  estimateData?: PMEstimateData | null;
}

export const PRDViewer: React.FC<PRDViewerProps> = ({
  content,
  projectName = "Project",
  isUpdating = false,
  estimateData,
}) => {
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<"prd" | "estimate">("prd");
  const [viewMode, setViewMode] = useState<"formatted" | "raw">("formatted");

  const handleCopy = () => {
    const textToCopy =
      activeTab === "prd"
        ? content || ""
        : JSON.stringify(estimateData, null, 2);
    if (!textToCopy) return;
    navigator.clipboard.writeText(textToCopy);
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
          The Product Manager generates the structured PRD and token/cost estimate once started and updates it incrementally as you refine scope.
        </p>
      </div>
    );
  }

  const formatInlineText = (text: string) => {
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

  // Parse lines into sections for rich structured presentation including Markdown tables
  const renderFormattedSections = () => {
    const lines = content.split("\n");
    const elements: React.ReactNode[] = [];
    let i = 0;

    while (i < lines.length) {
      const line = lines[i];

      // H1 Header
      if (line.startsWith("# ")) {
        elements.push(
          <div key={`h1-${i}`} className="pb-3 mb-4 border-b border-brand-border">
            <span className="text-[10px] font-mono font-semibold tracking-wider text-purple-600 dark:text-purple-400 uppercase">
              Product Requirement Document • Appendix A.2
            </span>
            <h1 className="text-xl sm:text-2xl font-black text-brand-headline tracking-tight mt-0.5">
              {line.replace("# ", "")}
            </h1>
          </div>
        );
        i++;
        continue;
      }

      // H2 Section Headers
      if (line.startsWith("## ")) {
        const title = line.replace("## ", "").trim();
        let icon = <Layers className="w-4 h-4 text-purple-500" />;
        if (title.toLowerCase().includes("goal") || title.toLowerCase().includes("metric")) {
          icon = <Target className="w-4 h-4 text-emerald-500" />;
        } else if (title.toLowerCase().includes("feature") || title.toLowerCase().includes("story")) {
          icon = <ListTodo className="w-4 h-4 text-blue-500" />;
        } else if (title.toLowerCase().includes("scope") || title.toLowerCase().includes("change")) {
          icon = <CheckCircle2 className="w-4 h-4 text-amber-500" />;
        } else if (title.toLowerCase().includes("risk")) {
          icon = <ShieldAlert className="w-4 h-4 text-rose-500" />;
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
        i++;
        continue;
      }

      // H3 Feature / Subsection Headers
      if (line.startsWith("### ")) {
        elements.push(
          <h3
            key={`h3-${i}`}
            className="text-xs sm:text-sm font-bold text-purple-600 dark:text-purple-400 pt-3 pb-1"
          >
            {line.replace("### ", "").trim()}
          </h3>
        );
        i++;
        continue;
      }

      // Table parsing: detect consecutive lines starting with '|'
      if (line.trim().startsWith("|") && line.trim().endsWith("|")) {
        const tableLines: string[] = [];
        while (i < lines.length && lines[i].trim().startsWith("|") && lines[i].trim().endsWith("|")) {
          tableLines.push(lines[i].trim());
          i++;
        }

        if (tableLines.length >= 2) {
          const headerCells = tableLines[0]
            .split("|")
            .slice(1, -1)
            .map((c) => c.trim());
          const dataRows = tableLines.slice(2); // Skip separator row

          elements.push(
            <div key={`table-${i}`} className="my-3 overflow-x-auto rounded-xl border border-brand-border shadow-2xs">
              <table className="w-full text-xs text-left border-collapse">
                <thead className="bg-brand-subtle text-brand-headline font-semibold text-[11px] border-b border-brand-border">
                  <tr>
                    {headerCells.map((h, hIdx) => (
                      <th key={hIdx} className="px-3 py-2 whitespace-nowrap">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-brand-border/50 bg-brand-card">
                  {dataRows.map((rowStr, rIdx) => {
                    const cells = rowStr
                      .split("|")
                      .slice(1, -1)
                      .map((c) => c.trim());
                    return (
                      <tr key={rIdx} className="hover:bg-brand-subtle/50 transition-colors">
                        {cells.map((cell, cIdx) => (
                          <td key={cIdx} className="px-3 py-2 text-brand-body leading-relaxed">
                            {formatInlineText(cell)}
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          );
          continue;
        }
      }

      // Bullet items
      if (line.trim().startsWith("- ") || line.trim().startsWith("* ")) {
        const text = line.trim().substring(2);
        elements.push(
          <div key={`li-${i}`} className="flex items-start gap-2 py-1 text-xs pl-1">
            <span className="w-1.5 h-1.5 rounded-full bg-purple-500 shrink-0 mt-1.5" />
            <div className="flex-1 text-brand-body leading-relaxed">
              {formatInlineText(text)}
            </div>
          </div>
        );
        i++;
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
      i++;
    }

    return elements;
  };

  const renderEstimateView = () => {
    if (!estimateData) {
      return (
        <div className="p-8 text-center bg-brand-card rounded-xl border border-brand-border">
          <Calculator className="w-8 h-8 text-purple-500 mx-auto mb-2 opacity-50" />
          <p className="text-xs text-brand-headline font-semibold">
            Token & Cost Estimate Pending
          </p>
          <p className="text-[11px] text-brand-body mt-1">
            The Product Manager computes token and cost estimates using the token ledger once PRD generation starts.
          </p>
        </div>
      );
    }

    return (
      <div className="space-y-6">
        {/* Top Summary Metrics Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="p-4 rounded-xl bg-brand-card border border-brand-border shadow-xs">
            <div className="flex items-center gap-2 text-brand-body text-xs mb-1 font-medium">
              <Cpu className="w-4 h-4 text-purple-500" />
              <span>Total Estimated Tokens</span>
            </div>
            <div className="text-xl sm:text-2xl font-black text-brand-headline">
              {estimateData.total_estimated_tokens.toLocaleString()}
            </div>
            <p className="text-[10px] text-brand-body/70 mt-1">
              Includes {estimateData.subtotal_tokens.toLocaleString()} base + {estimateData.rework_buffer_percentage}% rework buffer
            </p>
          </div>

          <div className="p-4 rounded-xl bg-brand-card border border-brand-border shadow-xs">
            <div className="flex items-center gap-2 text-brand-body text-xs mb-1 font-medium">
              <Coins className="w-4 h-4 text-emerald-500" />
              <span>Estimated Cost</span>
            </div>
            <div className="text-xl sm:text-2xl font-black text-emerald-600 dark:text-emerald-400">
              ${estimateData.estimated_cost_usd.toFixed(2)} USD
            </div>
            <p className="text-[10px] text-emerald-700 dark:text-emerald-300 mt-1 font-medium">
              {estimateData.estimated_cost_usd > 0
                ? `At ${estimateData.model} list prices`
                : `No API charge (${estimateData.model})`}
            </p>
          </div>

          <div className="p-4 rounded-xl bg-brand-card border border-brand-border shadow-xs">
            <div className="flex items-center gap-2 text-brand-body text-xs mb-1 font-medium">
              <ListTodo className="w-4 h-4 text-blue-500" />
              <span>Planned User Stories</span>
            </div>
            <div className="text-xl sm:text-2xl font-black text-brand-headline">
              {estimateData.stories_by_size.total_stories}
            </div>
            <p className="text-[10px] text-brand-body/70 mt-1">
              {estimateData.stories_by_size.small} Small • {estimateData.stories_by_size.medium} Medium • {estimateData.stories_by_size.large} Large
            </p>
          </div>
        </div>

        {/* Formula & Ledger Metadata Banner */}
        <div className="p-4 rounded-xl bg-brand-subtle/70 border border-brand-border space-y-2 text-xs">
          <div className="flex items-center gap-2 font-bold text-brand-headline">
            <Calculator className="w-4 h-4 text-purple-500" />
            <span>Handbook Section 5.1.6 Estimation Formula</span>
          </div>
          <code className="block p-2 rounded-lg bg-brand-card text-[11px] font-mono text-brand-accent border border-brand-border/60">
            {estimateData.formula}
          </code>
          <div className="flex items-start gap-1.5 text-[11px] text-brand-body pt-1">
            <Info className="w-3.5 h-3.5 text-blue-500 shrink-0 mt-0.5" />
            <span>
              <strong>Ledger Source ({estimateData.ledger_metadata.source})</strong>: {estimateData.ledger_metadata.description}
            </span>
          </div>
        </div>

        {/* Detailed Stages Table */}
        <div className="space-y-2">
          <h4 className="text-xs font-bold text-brand-headline uppercase tracking-wider">
            Token Estimation Breakdown by Project Stage
          </h4>
          <div className="overflow-x-auto rounded-xl border border-brand-border shadow-2xs">
            <table className="w-full text-xs text-left border-collapse">
              <thead className="bg-brand-subtle text-brand-headline font-semibold text-[11px] border-b border-brand-border">
                <tr>
                  <th className="px-3 py-2.5">Stage & Role</th>
                  <th className="px-3 py-2.5">Planned Artifacts / Units</th>
                  <th className="px-3 py-2.5">Historical Rate</th>
                  <th className="px-3 py-2.5">Subtotal Tokens</th>
                  <th className="px-3 py-2.5">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-brand-border/50 bg-brand-card">
                {estimateData.stages.map((st) => (
                  <tr key={st.stage_id} className="hover:bg-brand-subtle/50 transition-colors">
                    <td className="px-3 py-2.5 font-medium text-brand-headline">
                      <div>{st.stage}</div>
                      <div className="text-[10px] text-brand-body">{st.role}</div>
                    </td>
                    <td className="px-3 py-2.5 text-brand-body">
                      {st.planned_artifacts.join(", ")}
                    </td>
                    <td className="px-3 py-2.5 font-mono text-brand-body">
                      {st.historical_rate_per_unit.toLocaleString()} / unit
                    </td>
                    <td className="px-3 py-2.5 font-mono font-semibold text-brand-headline">
                      {st.subtotal_tokens.toLocaleString()}
                    </td>
                    <td className="px-3 py-2.5 text-[10px] font-mono text-brand-body">
                      <span className="px-1.5 py-0.5 rounded bg-brand-subtle border border-brand-border">
                        {st.rate_source}
                      </span>
                    </td>
                  </tr>
                ))}
                {/* Rework Buffer Row */}
                <tr className="bg-purple-500/5 font-medium">
                  <td className="px-3 py-2.5 text-purple-700 dark:text-purple-300" colSpan={3}>
                    +20% Rework Buffer (Handbook 5.1.6)
                  </td>
                  <td className="px-3 py-2.5 font-mono font-bold text-purple-700 dark:text-purple-300">
                    +{estimateData.rework_buffer_tokens.toLocaleString()}
                  </td>
                  <td className="px-3 py-2.5 text-[10px] text-purple-600 dark:text-purple-400">
                    Formula buffer
                  </td>
                </tr>
                {/* Total Row */}
                <tr className="bg-brand-subtle font-bold text-brand-headline border-t-2 border-brand-border">
                  <td className="px-3 py-2.5" colSpan={3}>
                    TOTAL ESTIMATED TOKENS
                  </td>
                  <td className="px-3 py-2.5 font-mono text-sm text-brand-accent">
                    {estimateData.total_estimated_tokens.toLocaleString()}
                  </td>
                  <td className="px-3 py-2.5 text-[11px] text-emerald-600 dark:text-emerald-400">
                    $0.00 USD
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  };

  const extractProviderStamp = (text: string | null) => {
    if (!text) return null;
    const match = text.match(/<!--\s*ARTIFACT METADATA:\s*Produced by\s+([^\s(]+)\s*\(([^)]+)\)/i) ||
                  text.match(/\*\*Artifact Provenance\*\*:\s*Generated by\s+\*\*([^*]+)\*\*\s*\(`([^`]+)`\)/i);
    if (match) {
      return { provider: match[1].trim(), model: match[2].trim() };
    }
    return null;
  };
  const providerStamp = extractProviderStamp(content);

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
                Product Manager Workstation
              </span>
              {isUpdating && (
                <span className="text-[9px] px-1.5 py-0.2 rounded-full bg-amber-500/20 text-amber-600 dark:text-amber-400 font-mono animate-pulse font-semibold">
                  updating...
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-brand-body truncate block">
                Grounded in BA discovery • {projectName}
              </span>
              {providerStamp && (
                <span className="inline-flex items-center gap-1 px-1.5 py-0.2 rounded font-mono text-[9px] bg-purple-500/10 border border-purple-500/20 text-purple-700 dark:text-purple-300 shadow-2xs">
                  <Cpu className="w-2.5 h-2.5" />
                  <span>Provider: <strong>{providerStamp.provider}</strong> ({providerStamp.model})</span>
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Tab & View Mode Controls */}
        <div className="flex items-center gap-1.5 shrink-0">
          {/* Main Document / Estimate Tab Selector */}
          <div className="flex items-center bg-brand-subtle rounded-lg p-0.5 border border-brand-border text-xs">
            <button
              type="button"
              onClick={() => setActiveTab("prd")}
              className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-all cursor-pointer ${
                activeTab === "prd"
                  ? "bg-brand-card text-brand-headline shadow-2xs font-semibold"
                  : "text-brand-body hover:text-brand-headline"
              }`}
            >
              PRD (docs/prd.md)
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("estimate")}
              className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-all cursor-pointer flex items-center gap-1 ${
                activeTab === "estimate"
                  ? "bg-brand-card text-brand-headline shadow-2xs font-semibold"
                  : "text-brand-body hover:text-brand-headline"
              }`}
            >
              <Coins className="w-3 h-3 text-emerald-500" />
              <span>Estimate (5.1.6)</span>
            </button>
          </div>

          {activeTab === "prd" && (
            <button
              type="button"
              onClick={() => setViewMode(viewMode === "formatted" ? "raw" : "formatted")}
              className="px-2 py-1 text-[11px] rounded-lg border border-brand-border bg-brand-card hover:bg-brand-subtle text-brand-body hover:text-brand-headline transition-colors cursor-pointer font-medium"
            >
              {viewMode === "formatted" ? "Raw" : "Rich"}
            </button>
          )}

          <button
            type="button"
            onClick={handleCopy}
            className="p-1.5 text-brand-body hover:text-brand-headline hover:bg-brand-subtle rounded-lg border border-brand-border transition-colors cursor-pointer flex items-center gap-1 text-[11px]"
            title="Copy content to clipboard"
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
        {activeTab === "estimate" ? (
          renderEstimateView()
        ) : viewMode === "formatted" ? (
          <div className="space-y-1">{renderFormattedSections()}</div>
        ) : (
          <pre className="text-xs font-mono whitespace-pre-wrap text-brand-headline bg-brand-bg/60 p-4 rounded-xl border border-brand-border leading-relaxed select-text">
            {content}
          </pre>
        )}
      </div>

      {/* Footer Info */}
      <div className="px-4 py-2 border-t border-brand-border/60 bg-brand-bg/30 text-[10px] font-mono text-brand-body flex items-center justify-between shrink-0">
        <span>Artifact: data/projects/.../docs/{activeTab === "prd" ? "prd.md" : "estimate.json"}</span>
        <span>
          {activeTab === "prd"
            ? `Word count: ${content.split(/\s+/).filter(Boolean).length}`
            : `Tokens: ${estimateData?.total_estimated_tokens.toLocaleString() || "pending"}`}
        </span>
      </div>
    </div>
  );
};

export default PRDViewer;
