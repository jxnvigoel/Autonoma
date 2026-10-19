import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  X,
  Cloud,
  HardDrive,
  Shield,
  Key,
  Cpu,
  Sliders,
  AlertTriangle,
  RefreshCw,
  CheckCircle2,
  Lock,
  Activity,
  Layers,
  Sparkles,
} from "lucide-react";
import {
  LLMSettings,
  RoleConfig,
  apiGetLLMSettings,
  apiUpdateLLMSettings,
  apiToggleLocalOnly,
} from "../../lib/engine";

interface LLMSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  sessionId?: string;
  projectName?: string;
  onSettingsChanged?: () => void;
}

export const LLMSettingsModal: React.FC<LLMSettingsModalProps> = ({
  isOpen,
  onClose,
  sessionId,
  projectName = "Current Project",
  onSettingsChanged,
}) => {
  const [settings, setSettings] = useState<LLMSettings | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"models" | "privacy" | "fallbacks">("models");

  const loadSettings = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiGetLLMSettings(sessionId);
      setSettings(data);
    } catch (err: any) {
      setError(err?.message || "Failed to load LLM settings from engine.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadSettings();
    }
  }, [isOpen, sessionId]);

  const handleRoleChange = async (
    role: string,
    updates: Partial<RoleConfig>
  ) => {
    if (!settings) return;
    setIsSaving(true);
    setSaveSuccess(null);
    try {
      const updated = await apiUpdateLLMSettings(role, updates);
      setSettings((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          role_configs: {
            ...prev.role_configs,
            [role]: updated.config || { ...prev.role_configs[role], ...updates },
          },
        };
      });
      setSaveSuccess(`Updated ${role.toUpperCase()} configuration.`);
      setTimeout(() => setSaveSuccess(null), 3000);
      onSettingsChanged?.();
    } catch (err: any) {
      setError(err?.message || `Failed to update ${role} configuration.`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleToggleLocalOnly = async (enabled: boolean) => {
    if (!sessionId) {
      setError("Please open an active project to configure per-project local-only mode.");
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      await apiToggleLocalOnly(sessionId, enabled);
      setSettings((prev) => (prev ? { ...prev, local_only: enabled } : prev));
      setSaveSuccess(
        enabled
          ? "Local-only mode enabled. Cloud requests disabled for this project."
          : "Cloud provider (Groq) enabled."
      );
      setTimeout(() => setSaveSuccess(null), 3000);
      onSettingsChanged?.();
    } catch (err: any) {
      setError(err?.message || "Failed to toggle local-only mode.");
    } finally {
      setIsSaving(false);
    }
  };

  if (!isOpen) return null;

  const roleMeta: Record<
    string,
    { title: string; desc: string; icon: React.ReactNode; isJudge?: boolean }
  > = {
    ba: {
      title: "Business Analyst (BA)",
      desc: "Client discovery dialog & requirements.md generation",
      icon: <Sparkles className="w-4 h-4 text-blue-500" />,
    },
    pm: {
      title: "Product Manager (PM)",
      desc: "Section-by-section PRD & user story generation",
      icon: <Layers className="w-4 h-4 text-purple-500" />,
    },
    architect: {
      title: "Solution Architect",
      desc: "Feasibility check, architecture.md, SQLite schema, OpenAPI 3.0",
      icon: <Cpu className="w-4 h-4 text-emerald-500" />,
    },
    designer: {
      title: "UI/UX Designer",
      desc: "app-flow.md, design-brief.md with WCAG contrast compliance",
      icon: <Sliders className="w-4 h-4 text-cyan-500" />,
    },
    judge: {
      title: "LLM Judge & Quality Auditor",
      desc: "Independent audit against rubrics with strict zero-hallucination bar",
      icon: <Shield className="w-4 h-4 text-amber-500" />,
      isJudge: true,
    },
    engineer: {
      title: "Software Engineer",
      desc: "Pipeline code generation and implementation",
      icon: <Cpu className="w-4 h-4 text-rose-500" />,
    },
    qa: {
      title: "Quality Assurance (QA)",
      desc: "Automated test suite generation and assertions",
      icon: <Shield className="w-4 h-4 text-amber-600" />,
    },
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/60 backdrop-blur-xs select-none">
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 10 }}
        transition={{ duration: 0.2 }}
        className="w-full max-w-4xl max-h-[90vh] bg-brand-card border border-brand-border rounded-2xl shadow-2xl flex flex-col overflow-hidden text-brand-headline"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-brand-border flex items-center justify-between bg-brand-subtle/40">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-brand-accent/15 text-brand-accent flex items-center justify-center">
              <Sliders className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-brand-headline">
                  LLM Provider & Model Routing
                </h2>
                {settings?.local_only ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-500/15 text-slate-700 dark:text-slate-300 text-[10px] font-mono font-bold border border-slate-500/30">
                    <HardDrive className="w-3 h-3 text-slate-500" />
                    Local-Only (Ollama)
                  </span>
                ) : settings?.groq_configured ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 text-[10px] font-mono font-bold border border-emerald-500/30">
                    <Cloud className="w-3 h-3 text-emerald-500" />
                    Groq Cloud Active
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-rose-500/15 text-rose-700 dark:text-rose-300 text-[10px] font-mono font-bold border border-rose-500/30">
                    <AlertTriangle className="w-3 h-3 text-rose-500" />
                    Key Missing
                  </span>
                )}
              </div>
              <p className="text-xs text-brand-body">
                Configure role model assignments, Groq cloud endpoint, rate pacing, and privacy overrides.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={loadSettings}
              disabled={isLoading}
              title="Refresh Models from Groq"
              className="p-2 rounded-lg hover:bg-brand-subtle text-brand-body hover:text-brand-headline transition-colors cursor-pointer"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-brand-subtle text-brand-body hover:text-brand-headline transition-colors cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="px-6 border-b border-brand-border flex items-center gap-4 bg-brand-card text-xs font-medium">
          <button
            onClick={() => setActiveTab("models")}
            className={`py-3 border-b-2 transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === "models"
                ? "border-brand-accent text-brand-accent font-semibold"
                : "border-transparent text-brand-body hover:text-brand-headline"
            }`}
          >
            <Cpu className="w-3.5 h-3.5" />
            <span>Role Routing & Models</span>
          </button>
          <button
            onClick={() => setActiveTab("privacy")}
            className={`py-3 border-b-2 transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === "privacy"
                ? "border-brand-accent text-brand-accent font-semibold"
                : "border-transparent text-brand-body hover:text-brand-headline"
            }`}
          >
            <Shield className="w-3.5 h-3.5" />
            <span>Privacy & Local-Only</span>
          </button>
          <button
            onClick={() => setActiveTab("fallbacks")}
            className={`py-3 border-b-2 transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === "fallbacks"
                ? "border-brand-accent text-brand-accent font-semibold"
                : "border-transparent text-brand-body hover:text-brand-headline"
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            <span>Rate Limits & Fallbacks ({settings?.fallback_count || 0})</span>
          </button>
        </div>

        {/* Feedback Alerts */}
        <div className="px-6 pt-3 space-y-2">
          {/* Missing Groq Key Alert */}
          {!settings?.groq_configured && !isLoading && (
            <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-start gap-3 text-xs text-rose-700 dark:text-rose-300">
              <AlertTriangle className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <p className="font-bold">GROQ_API_KEY Missing from Environment</p>
                <p className="opacity-90">
                  Groq is the default LLM provider for all agents. Please add{" "}
                  <code className="font-mono bg-rose-500/20 px-1 py-0.5 rounded">GROQ_API_KEY=gsk_...</code> to your{" "}
                  <code className="font-mono bg-rose-500/20 px-1 py-0.5 rounded">.env</code> file, or toggle Local-Only mode
                  below to run entirely on Ollama without cloud calls.
                </p>
              </div>
            </div>
          )}

          {error && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-600 dark:text-rose-400 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {saveSuccess && (
            <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400 text-xs flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{saveSuccess}</span>
            </div>
          )}
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto flex-1 space-y-6 text-xs">
          {activeTab === "models" && (
            <>
              {/* Credentials & Pacing Status Overview */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 p-4 rounded-xl bg-brand-subtle/50 border border-brand-border">
                <div>
                  <span className="text-[10px] uppercase font-mono text-brand-body">API Key (.env)</span>
                  <div className="flex items-center gap-1.5 mt-1 font-mono font-medium text-brand-headline">
                    <Key className="w-3.5 h-3.5 text-brand-accent" />
                    <span>{settings?.masked_api_key || "None configured"}</span>
                  </div>
                </div>

                <div>
                  <span className="text-[10px] uppercase font-mono text-brand-body">Default Base URL</span>
                  <div className="flex items-center gap-1.5 mt-1 font-mono font-medium text-brand-headline truncate">
                    <Cloud className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                    <span className="truncate">https://api.groq.com/openai/v1</span>
                  </div>
                </div>

                <div>
                  <span className="text-[10px] uppercase font-mono text-brand-body">Fallback Provider</span>
                  <div className="flex items-center gap-1.5 mt-1 font-mono font-medium text-brand-headline">
                    <HardDrive className="w-3.5 h-3.5 text-slate-500" />
                    <span>Ollama (llama3.2:3b)</span>
                  </div>
                </div>
              </div>

              {/* Role Configuration Table */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-brand-headline font-mono">
                    Agent Role Model Assignments
                  </h3>
                  <span className="text-[11px] text-brand-body">
                    {settings?.available_models?.length || 0} live Groq models discovered
                  </span>
                </div>

                <div className="border border-brand-border rounded-xl overflow-hidden divide-y divide-brand-border bg-brand-card">
                  {Object.entries(roleMeta).map(([roleKey, meta]) => {
                    const cfg = settings?.role_configs?.[roleKey] || {
                      provider: "groq",
                      model: meta.isJudge ? "openai/gpt-oss-20b" : "openai/gpt-oss-120b",
                      temperature: meta.isJudge ? 0.1 : 0.3,
                      max_tokens: 4096,
                    };

                    const isLocalOnly = settings?.local_only;

                    return (
                      <div
                        key={roleKey}
                        className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-brand-subtle/20 transition-colors"
                      >
                        {/* Role info */}
                        <div className="flex items-start gap-3 min-w-[200px]">
                          <div className="p-2 rounded-lg bg-brand-subtle border border-brand-border shrink-0 mt-0.5">
                            {meta.icon}
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-brand-headline text-xs">{meta.title}</span>
                              {meta.isJudge && (
                                <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-amber-500/15 text-amber-700 dark:text-amber-300 font-bold border border-amber-500/30">
                                  Model Separated
                                </span>
                              )}
                            </div>
                            <p className="text-[11px] text-brand-body mt-0.5">{meta.desc}</p>
                          </div>
                        </div>

                        {/* Controls: Provider, Model, Temperature */}
                        <div className="flex flex-wrap items-center gap-3">
                          {/* Provider */}
                          <div className="flex flex-col gap-1">
                            <span className="text-[10px] font-mono text-brand-body">Provider</span>
                            <select
                              disabled={isLocalOnly || isSaving}
                              value={isLocalOnly ? "ollama" : cfg.provider}
                              onChange={(e) =>
                                handleRoleChange(roleKey, {
                                  provider: e.target.value as "groq" | "ollama",
                                })
                              }
                              className="px-2.5 py-1.5 rounded-lg bg-brand-subtle border border-brand-border text-xs text-brand-headline focus:ring-1 focus:ring-brand-accent outline-hidden cursor-pointer"
                            >
                              <option value="groq">Groq (Cloud)</option>
                              <option value="ollama">Ollama (Local Fallback)</option>
                            </select>
                          </div>

                          {/* Model Dropdown */}
                          <div className="flex flex-col gap-1">
                            <span className="text-[10px] font-mono text-brand-body">Model</span>
                            {cfg.provider === "ollama" || isLocalOnly ? (
                              <div className="px-2.5 py-1.5 rounded-lg bg-brand-subtle/60 border border-brand-border text-xs text-brand-body font-mono">
                                llama3.2:3b (local)
                              </div>
                            ) : (
                              <select
                                disabled={isSaving}
                                value={cfg.model}
                                onChange={(e) => handleRoleChange(roleKey, { model: e.target.value })}
                                className="px-2.5 py-1.5 rounded-lg bg-brand-subtle border border-brand-border text-xs text-brand-headline focus:ring-1 focus:ring-brand-accent outline-hidden cursor-pointer max-w-[240px]"
                              >
                                {settings?.available_models && settings.available_models.length > 0 ? (
                                  settings.available_models.map((m) => (
                                    <option key={m.id} value={m.id}>
                                      {m.id} ({Math.round(m.context_window / 1024)}k ctx)
                                    </option>
                                  ))
                                ) : (
                                  <option value={cfg.model}>{cfg.model}</option>
                                )}
                              </select>
                            )}
                          </div>

                          {/* Temperature Slider */}
                          <div className="flex flex-col gap-1 w-24">
                            <div className="flex items-center justify-between text-[10px] font-mono text-brand-body">
                              <span>Temp</span>
                              <span className="font-bold text-brand-headline">{cfg.temperature}</span>
                            </div>
                            <input
                              type="range"
                              min="0"
                              max="1"
                              step="0.05"
                              value={cfg.temperature}
                              disabled={isSaving}
                              onChange={(e) =>
                                handleRoleChange(roleKey, {
                                  temperature: parseFloat(e.target.value),
                                })
                              }
                              className="w-full accent-brand-accent cursor-pointer"
                            />
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          )}

          {activeTab === "privacy" && (
            <div className="space-y-6">
              <div className="p-5 rounded-2xl bg-brand-subtle/40 border border-brand-border space-y-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <Shield className="w-5 h-5 text-emerald-500" />
                      <h3 className="text-sm font-bold text-brand-headline">
                        Per-Project Privacy: Force Local-Only (Ollama)
                      </h3>
                    </div>
                    <p className="text-xs text-brand-body leading-relaxed max-w-xl">
                      When enabled for project <strong className="text-brand-headline">{projectName}</strong>, all
                      client discovery Q&A, specifications, architecture schemas, and code stay 100% on this machine.
                      Prompts will NEVER leave your local network or touch Groq's cloud APIs.
                    </p>
                  </div>

                  <button
                    onClick={() => handleToggleLocalOnly(!settings?.local_only)}
                    disabled={isSaving}
                    className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-hidden ${
                      settings?.local_only ? "bg-brand-accent" : "bg-slate-300 dark:bg-slate-700"
                    }`}
                  >
                    <span
                      className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out ${
                        settings?.local_only ? "translate-x-5" : "translate-x-0"
                      }`}
                    />
                  </button>
                </div>

                <div className="pt-2 border-t border-brand-border/60 flex items-center gap-4 text-xs">
                  <span className="text-brand-body font-mono">Current Project Privacy Status:</span>
                  {settings?.local_only ? (
                    <span className="font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5">
                      <HardDrive className="w-3.5 h-3.5" />
                      Strict Local Only (Ollama llama3.2:3b active)
                    </span>
                  ) : (
                    <span className="font-bold text-blue-600 dark:text-blue-400 flex items-center gap-1.5">
                      <Cloud className="w-3.5 h-3.5" />
                      Cloud API Active (Groq high-speed inference)
                    </span>
                  )}
                </div>
              </div>

              {/* API Key Security Notice */}
              <div className="p-4 rounded-xl bg-brand-subtle/30 border border-brand-border space-y-2 text-brand-body">
                <div className="flex items-center gap-2 font-bold text-brand-headline text-xs">
                  <Lock className="w-4 h-4 text-brand-accent" />
                  <span>Zero-Leak Credential Guarantee</span>
                </div>
                <p className="text-[11px] leading-relaxed">
                  Your <code className="font-mono bg-brand-subtle px-1 py-0.5 rounded">GROQ_API_KEY</code> is loaded
                  strictly from <code className="font-mono bg-brand-subtle px-1 py-0.5 rounded">.env</code> on the backend.
                  It is NEVER hardcoded, NEVER committed into git (guaranteed by .gitignore), and is masked in all UI views.
                </p>
              </div>
            </div>
          )}

          {activeTab === "fallbacks" && (
            <div className="space-y-4">
              <div className="p-4 rounded-xl bg-brand-subtle/40 border border-brand-border space-y-1">
                <h3 className="font-bold text-brand-headline text-xs">Rate Limit Protection & Fallback Policy</h3>
                <p className="text-brand-body text-[11px] leading-relaxed">
                  The unified LLM client paces requests with a minimum 1.0s gap and implements exponential backoff
                  (2s, 4s, 8s) honoring HTTP 429 <code className="font-mono bg-brand-subtle px-1 py-0.5 rounded">retry-after</code> headers.
                  Ollama fallback is triggered ONLY when all cloud retries are exhausted, ensuring no run crashes.
                </p>
              </div>

              <div className="space-y-2">
                <span className="text-xs font-bold uppercase tracking-wider text-brand-headline font-mono">
                  Recent Fallback Events ({settings?.recent_fallbacks?.length || 0})
                </span>

                {settings?.recent_fallbacks && settings.recent_fallbacks.length > 0 ? (
                  <div className="border border-brand-border rounded-xl overflow-hidden divide-y divide-brand-border bg-brand-card">
                    {settings.recent_fallbacks.map((fb, idx) => (
                      <div key={idx} className="p-3 text-xs flex items-start justify-between gap-4">
                        <div>
                          <div className="flex items-center gap-2 font-mono text-[11px]">
                            <span className="font-bold text-brand-headline uppercase">{fb.role}</span>
                            <span className="text-brand-body">→ fallback to {fb.fallback_model}</span>
                            <span className="text-brand-body/60">{new Date(fb.timestamp).toLocaleTimeString()}</span>
                          </div>
                          <p className="text-[11px] text-rose-500 mt-1 font-mono">{fb.reason}</p>
                        </div>
                        <span className="text-[10px] font-mono bg-brand-subtle px-2 py-0.5 rounded">
                          {fb.duration_ms}ms
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-8 text-center text-brand-body border border-dashed border-brand-border rounded-xl">
                    <CheckCircle2 className="w-6 h-6 text-emerald-500 mx-auto mb-2" />
                    <p className="font-bold text-xs text-brand-headline">Zero Fallbacks Recorded</p>
                    <p className="text-[11px] text-brand-body mt-0.5">
                      All LLM requests succeeded on Groq Cloud without rate limit exhaustion.
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 border-t border-brand-border flex items-center justify-between bg-brand-subtle/30">
          <span className="text-[11px] text-brand-body">
            Default Generators: <strong className="text-brand-headline">openai/gpt-oss-120b</strong> • Judge:{" "}
            <strong className="text-brand-headline">openai/gpt-oss-20b</strong>
          </span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-brand-accent text-brand-accent-text font-bold text-xs hover:opacity-90 transition-opacity cursor-pointer shadow-xs"
          >
            Done
          </button>
        </div>
      </motion.div>
    </div>
  );
};

export default LLMSettingsModal;
