import React, { useState, useEffect } from "react";
import { useEscapeToClose } from "../../lib/utils";
import { motion } from "framer-motion";
import {
  X,
  BookOpen,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Plus,
  RefreshCw,
  Search,
  Wrench,
  Ban,
  FileText,
  ShieldCheck,
} from "lucide-react";
import {
  fetchSkillPacks,
  detectSpecialistNeeds,
  attachSkillPack,
  SpecialistSkillPack,
  SpecialistDetectionResult,
} from "../../lib/engine";

interface SkillLibraryModalProps {
  isOpen: boolean;
  onClose: () => void;
  sessionId?: string;
  onSkillAttached?: () => void;
}

export const SkillLibraryModal: React.FC<SkillLibraryModalProps> = ({
  isOpen,
  onClose,
  sessionId,
  onSkillAttached,
}) => {
  useEscapeToClose(isOpen, onClose);
  const [packs, setPacks] = useState<SpecialistSkillPack[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [detectionResult, setDetectionResult] = useState<SpecialistDetectionResult | null>(null);
  const [isDetecting, setIsDetecting] = useState(false);
  const [actionMessage, setActionMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  const loadPacks = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSkillPacks();
      setPacks(data.packs || []);
    } catch (err: any) {
      setError(err?.message || "Failed to load skill packs");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadPacks();
    }
  }, [isOpen]);

  const handleRunDetection = async () => {
    if (!sessionId) return;
    setIsDetecting(true);
    setActionMessage(null);
    try {
      const result = await detectSpecialistNeeds(sessionId);
      setDetectionResult(result);
      setActionMessage({
        text: `Detection complete: ${result.specialist_needs.length} specialist need(s) recommended, ${result.open_questions.length} open question(s) raised.`,
        type: "success",
      });
    } catch (err: any) {
      setActionMessage({
        text: err?.message || "Detection failed",
        type: "error",
      });
    } finally {
      setIsDetecting(false);
    }
  };

  const handleAttach = async (packId: string, role: string = "backend") => {
    if (!sessionId) return;
    setActionMessage(null);
    try {
      const res = await attachSkillPack(sessionId, role, packId);
      if (res.status === "blocked") {
        setActionMessage({
          text: `Blocked: ${res.error}`,
          type: "error",
        });
      } else {
        setActionMessage({
          text: `Successfully attached ${packId} to ${role} agent profile!`,
          type: "success",
        });
        if (onSkillAttached) onSkillAttached();
      }
    } catch (err: any) {
      setActionMessage({
        text: err?.message || `Failed to attach ${packId}`,
        type: "error",
      });
    }
  };

  const filteredPacks = packs.filter((p) => {
    const q = searchQuery.toLowerCase();
    return (
      p.id.toLowerCase().includes(q) ||
      p.name.toLowerCase().includes(q) ||
      p.description.toLowerCase().includes(q) ||
      p.triggers.keywords.some((k) => k.toLowerCase().includes(q))
    );
  });

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs select-none">
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.96 }}
        transition={{ duration: 0.15 }}
        className="w-full max-w-4xl max-h-[90vh] bg-brand-card text-brand-headline rounded-2xl border border-brand-border shadow-2xl flex flex-col overflow-hidden"
      >
        {/* Header */}
        <header className="px-6 py-4 border-b border-brand-border flex items-center justify-between shrink-0 bg-brand-subtle/30">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-accent/10 border border-brand-accent/20 flex items-center justify-center text-brand-accent">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-brand-headline flex items-center gap-2">
                <span>Specialist Skill Library</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-brand-subtle border border-brand-border text-brand-body">
                  Registry v1.0
                </span>
              </h2>
              <p className="text-xs text-brand-body">
                Pluggable specialist packs with manifest, instructions, standards, and rubrics
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {sessionId && (
              <button
                type="button"
                onClick={handleRunDetection}
                disabled={isDetecting}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-accent text-brand-accent-text text-xs font-semibold hover:opacity-90 shadow-xs transition-all cursor-pointer disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isDetecting ? "animate-spin" : ""}`} />
                <span>{isDetecting ? "Detecting..." : "Detect Needs (0 Tokens)"}</span>
              </button>
            )}

            <button
              type="button"
              onClick={onClose}
              className="p-1.5 text-brand-body hover:text-brand-headline hover:bg-brand-subtle rounded-lg transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </header>

        {/* Action message banner */}
        {actionMessage && (
          <div
            className={`px-6 py-2.5 text-xs font-medium flex items-center gap-2 border-b ${
              actionMessage.type === "success"
                ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/20"
                : "bg-rose-500/10 text-rose-700 dark:text-rose-300 border-rose-500/20"
            }`}
          >
            {actionMessage.type === "success" ? (
              <CheckCircle2 className="w-4 h-4 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 shrink-0" />
            )}
            <span>{actionMessage.text}</span>
          </div>
        )}

        {/* Search Bar & Stats */}
        <div className="px-6 py-3 border-b border-brand-border bg-brand-card flex flex-col sm:flex-row items-center justify-between gap-3 shrink-0">
          <div className="relative w-full sm:w-80">
            <Search className="w-4 h-4 text-brand-body absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search packs, triggers, or roles..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-brand-subtle border border-brand-border text-xs text-brand-headline focus:outline-hidden focus:border-brand-accent"
            />
          </div>

          <div className="flex items-center gap-3 text-xs text-brand-body w-full sm:w-auto justify-end">
            <span>
              Showing <strong className="text-brand-headline">{filteredPacks.length}</strong> of {packs.length} packs
            </span>
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Deterministic Detection Results (if available) */}
          {detectionResult && (
            <div className="p-4 rounded-xl border border-brand-accent/30 bg-brand-accent/5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-brand-accent flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4" />
                  <span>Deterministic Specialist Needs for Active Project</span>
                </span>
                <span className="text-[10px] font-mono bg-brand-accent/20 text-brand-accent px-2 py-0.5 rounded">
                  0 LLM Tokens Consumed
                </span>
              </div>

              {detectionResult.specialist_needs.length === 0 && detectionResult.weak_matches.length === 0 && (
                <p className="text-xs text-brand-body">
                  No specialist skill packs triggered by current PRD, requirements, or architecture. Standard role skills are sufficient.
                </p>
              )}

              {/* Recommended Needs */}
              {detectionResult.specialist_needs.map((need) => (
                <div
                  key={need.pack_id}
                  className="p-3 rounded-lg bg-brand-card border border-brand-border text-xs space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-brand-headline">{need.name}</span>
                      <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-bold border border-emerald-500/20">
                        HIGH CONFIDENCE ({need.evidence_count} signals)
                      </span>
                    </div>

                    <button
                      type="button"
                      onClick={() => handleAttach(need.pack_id, "backend")}
                      className="flex items-center gap-1 px-2.5 py-1 rounded bg-brand-accent text-brand-accent-text text-[11px] font-semibold hover:opacity-90 shadow-2xs cursor-pointer"
                    >
                      <Plus className="w-3 h-3" />
                      <span>Attach to Backend</span>
                    </button>
                  </div>

                  <p className="text-[11px] text-brand-body font-mono bg-brand-subtle p-2 rounded border border-brand-border">
                    {need.adr_recommendation}
                  </p>

                  <div className="space-y-1">
                    <span className="text-[10px] font-bold text-brand-body">Evidence Citations:</span>
                    <div className="space-y-1">
                      {need.evidence.map((ev, idx) => (
                        <div
                          key={idx}
                          className="text-[11px] text-brand-body flex items-start gap-1.5 pl-2 border-l-2 border-brand-accent"
                        >
                          <strong className="font-mono text-brand-headline shrink-0">[{ev.id}]</strong>
                          <span>matched trigger <em>'{ev.trigger}'</em> in {ev.source}: "{ev.snippet}"</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ))}

              {/* Weak matches -> Open Questions */}
              {detectionResult.open_questions.map((oq) => (
                <div
                  key={oq.id}
                  className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-xs space-y-1"
                >
                  <div className="flex items-center gap-2 font-bold text-amber-700 dark:text-amber-300">
                    <HelpCircle className="w-3.5 h-3.5" />
                    <span>{oq.id}: Open Question Raised (Weak Detection Evidence)</span>
                  </div>
                  <p className="text-[11px] text-brand-body">{oq.text}</p>
                </div>
              ))}
            </div>
          )}

          {/* Loading or Error states */}
          {loading && (
            <div className="flex items-center justify-center py-12 text-xs text-brand-body gap-2">
              <RefreshCw className="w-4 h-4 animate-spin text-brand-accent" />
              <span>Scanning skills/ and skills/specialists/ manifests...</span>
            </div>
          )}

          {error && (
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-600 dark:text-rose-400">
              {error}
            </div>
          )}

          {/* Packs Grid */}
          {!loading && !error && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filteredPacks.map((pack) => (
                <div
                  key={pack.id}
                  className="p-4 rounded-xl border border-brand-border bg-brand-card hover:border-brand-accent/40 transition-all flex flex-col justify-between space-y-3"
                >
                  <div className="space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="text-sm font-bold text-brand-headline">{pack.name}</h3>
                          <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-brand-subtle text-brand-body border border-brand-border">
                            v{pack.version}
                          </span>
                        </div>
                        <span className="text-[10px] font-mono text-brand-accent font-semibold">
                          id: {pack.id}
                        </span>
                      </div>

                      {sessionId && (
                        <button
                          type="button"
                          onClick={() => handleAttach(pack.id, "backend")}
                          className="text-[10px] font-semibold px-2 py-1 rounded bg-brand-subtle hover:bg-brand-accent hover:text-brand-accent-text border border-brand-border text-brand-body transition-colors cursor-pointer shrink-0"
                          title={`Attach ${pack.id} to Backend Agent`}
                        >
                          Attach to Role
                        </button>
                      )}
                    </div>

                    <p className="text-xs text-brand-body leading-relaxed">{pack.description}</p>

                    {/* Compatible Roles */}
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="text-[10px] font-bold text-brand-body">Roles:</span>
                      {pack.compatible_roles.map((r) => (
                        <span
                          key={r}
                          className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-brand-subtle text-brand-body border border-brand-border"
                        >
                          {r}
                        </span>
                      ))}
                    </div>

                    {/* Triggers */}
                    <div className="space-y-1">
                      <span className="text-[10px] font-bold text-brand-body">Triggers:</span>
                      <div className="flex items-center gap-1 flex-wrap">
                        {pack.triggers.keywords.slice(0, 6).map((kw) => (
                          <span
                            key={kw}
                            className="text-[9px] font-mono px-1 py-0.2 rounded bg-purple-500/10 text-purple-700 dark:text-purple-300 border border-purple-500/20"
                          >
                            {kw}
                          </span>
                        ))}
                        {pack.triggers.keywords.length > 6 && (
                          <span className="text-[9px] text-brand-body">
                            +{pack.triggers.keywords.length - 6} more
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Tools */}
                    <div className="flex items-center justify-between text-[10px] text-brand-body pt-1">
                      <div className="flex items-center gap-1">
                        <Wrench className="w-3 h-3 text-emerald-500" />
                        <span>Requires: {pack.required_tools.join(", ") || "none"}</span>
                      </div>
                      {pack.forbidden_tools.length > 0 && (
                        <div className="flex items-center gap-1 text-rose-500">
                          <Ban className="w-3 h-3" />
                          <span>Forbids: {pack.forbidden_tools.join(", ")}</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Manifest Artifacts Bar */}
                  <div className="pt-2 border-t border-brand-border/60 flex items-center justify-between text-[10px] text-brand-body">
                    <span className="flex items-center gap-1">
                      <FileText className="w-3 h-3" />
                      <span>Pack Artifacts:</span>
                    </span>
                    <div className="flex items-center gap-2">
                      <span className={pack.has_instructions ? "text-emerald-500 font-bold" : "opacity-40"}>
                        instructions.md
                      </span>
                      <span>•</span>
                      <span className={pack.has_standards ? "text-emerald-500 font-bold" : "opacity-40"}>
                        standards.md
                      </span>
                      <span>•</span>
                      <span className={pack.has_checklist ? "text-emerald-500 font-bold" : "opacity-40"}>
                        checklist.md
                      </span>
                      <span>•</span>
                      <span className={pack.has_rubric ? "text-emerald-500 font-bold" : "opacity-40"}>
                        rubric.json
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <footer className="px-6 py-3 border-t border-brand-border bg-brand-subtle/30 flex items-center justify-between shrink-0 text-xs text-brand-body">
          <span>Adding a new specialist pack only requires adding a folder with manifest.json</span>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-brand-card hover:bg-brand-subtle border border-brand-border text-brand-headline font-semibold transition-colors cursor-pointer"
          >
            Close
          </button>
        </footer>
      </motion.div>
    </div>
  );
};
