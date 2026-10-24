import React from "react";
import { AgentDesk } from "./AgentDesk";
import { AgentRoleKey } from "./AgentAvatars";
import { AgentLiveStatus } from "../../lib/engine";
import { Sparkles, Coffee, Cpu, ShieldCheck, Cloud, HardDrive, AlertTriangle, Sliders, Users } from "lucide-react";

export interface OfficeDeskData {
  roleKey: AgentRoleKey;
  roleName: string;
  roleAbbr: string;
  status: AgentLiveStatus;
  hasOutput: boolean;
  outputName?: string;
  messageCount?: number;
  isUnlocked: boolean;
  provider?: string;
  model?: string;
  attachedSkills?: string[];
}

interface PixelOfficeFloorProps {
  desks: OfficeDeskData[];
  selectedAgentId: AgentRoleKey | null;
  onSelectAgent: (roleKey: AgentRoleKey) => void;
  projectName?: string;
  onOpenSettings?: () => void;
  isLocalOnly?: boolean;
  isCloudActive?: boolean;
  groqConfigured?: boolean;
}

export const PixelOfficeFloor: React.FC<PixelOfficeFloorProps> = ({
  desks,
  selectedAgentId,
  onSelectAgent,
  projectName = "Active Project",
  onOpenSettings,
  isLocalOnly = false,
  isCloudActive = true,
  groqConfigured = true,
}) => {
  return (
    <div className="relative flex-1 w-full h-full overflow-y-auto p-4 sm:p-6 md:p-8 flex flex-col items-center justify-start select-none">
      {/* Retro Pixel Tile Pattern Background */}
      <div
        className="absolute inset-0 pointer-events-none opacity-40 dark:opacity-25"
        style={{
          backgroundImage: `
            linear-gradient(to right, rgba(120, 120, 140, 0.12) 1px, transparent 1px),
            linear-gradient(to bottom, rgba(120, 120, 140, 0.12) 1px, transparent 1px)
          `,
          backgroundSize: "24px 24px",
        }}
      />

      <div className="w-full max-w-6xl relative z-10 flex flex-col items-center space-y-6">
        {/* Office Top Welcome Banner / Whiteboard */}
        <div className="w-full flex flex-col sm:flex-row items-center justify-between gap-4 p-4 rounded-2xl bg-brand-card border border-brand-border shadow-card">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-accent text-brand-accent-text flex items-center justify-center font-bold text-base shadow-xs">
              🏢
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-extrabold text-brand-headline tracking-tight">
                  Virtual Studio Floor
                </h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-bold border border-emerald-500/30">
                  Live Project Space
                </span>
              </div>
              <p className="text-xs text-brand-body">
                Project: <strong className="text-brand-headline">{projectName}</strong> • Select any agent desk to inspect work output and chat.
              </p>
            </div>
          </div>

          {/* Quick Environment Perks & Privacy Status */}
          <div className="flex flex-wrap items-center gap-2 text-xs text-brand-body">
            {/* Privacy / Cloud Status Indicator */}
            {isLocalOnly ? (
              <span className="flex items-center gap-1.5 bg-slate-500/15 text-slate-700 dark:text-slate-300 px-2.5 py-1 rounded-lg border border-slate-500/30 text-[11px] font-mono font-medium">
                <HardDrive className="w-3.5 h-3.5 text-slate-500" />
                <span>Local-Only (Ollama)</span>
              </span>
            ) : isCloudActive && groqConfigured ? (
              <span className="flex items-center gap-1.5 bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 px-2.5 py-1 rounded-lg border border-emerald-500/30 text-[11px] font-mono font-medium">
                <Cloud className="w-3.5 h-3.5 text-emerald-500 animate-pulse" />
                <span>Cloud API (Groq) Active</span>
              </span>
            ) : (
              <span className="flex items-center gap-1.5 bg-rose-500/15 text-rose-700 dark:text-rose-300 px-2.5 py-1 rounded-lg border border-rose-500/30 text-[11px] font-mono font-medium">
                <AlertTriangle className="w-3.5 h-3.5 text-rose-500" />
                <span>Groq Key Missing</span>
              </span>
            )}

            {/* Settings Trigger Button */}
            {onOpenSettings && (
              <button
                type="button"
                onClick={onOpenSettings}
                className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-brand-subtle hover:bg-brand-card border border-brand-border text-xs font-semibold text-brand-headline transition-colors cursor-pointer shadow-xs"
              >
                <Sliders className="w-3.5 h-3.5 text-brand-accent" />
                <span>LLM Settings</span>
              </button>
            )}

            <span className="hidden sm:flex items-center gap-1 bg-brand-subtle/70 px-2.5 py-1 rounded-lg border border-brand-border text-[11px]">
              <Coffee className="w-3.5 h-3.5 text-amber-600" />
              <span>Studio Breakroom</span>
            </span>
          </div>
        </div>

        {/* Stage 1 & 2 Pod: Discovery & Product Planning (BA & PM) */}
        <div className="w-full space-y-3">
          <div className="flex items-center justify-between px-1">
            <span className="text-xs font-bold uppercase tracking-wider text-brand-accent flex items-center gap-1.5 font-mono">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Stage 1 & 2: Discovery & Product Planning Pod (Active)</span>
            </span>
            <span className="text-[10px] text-brand-body font-mono">
              Click desk to inspect outputs & chat
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 w-full">
            {desks
              .filter((d) => d.roleKey === "ba" || d.roleKey === "pm")
              .map((desk) => (
                <AgentDesk
                  key={desk.roleKey}
                  roleKey={desk.roleKey}
                  roleName={desk.roleName}
                  roleAbbr={desk.roleAbbr}
                  status={desk.status}
                  hasOutput={desk.hasOutput}
                  outputName={desk.outputName}
                  messageCount={desk.messageCount}
                  isSelected={selectedAgentId === desk.roleKey}
                  isUnlocked={desk.isUnlocked}
                  provider={desk.provider}
                  model={desk.model}
                  attachedSkills={desk.attachedSkills}
                  onClick={() => onSelectAgent(desk.roleKey)}
                />
              ))}
          </div>
        </div>

        {/* Stage 3 Pod: Technical Architecture & UX Design (Parallel per Handbook 2.7.4) */}
        <div className="w-full space-y-3 pt-4">
          <div className="flex items-center justify-between px-1">
            <span className="text-xs font-bold uppercase tracking-wider text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5 font-mono">
              <Cpu className="w-3.5 h-3.5" />
              <span>Stage 3: Technical Architecture & UI/UX Design Pod (Parallel)</span>
            </span>
            <span className="text-[10px] text-brand-body font-mono">
              Unlocks after Gate 1 PRD approval
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 w-full">
            {desks
              .filter((d) => d.roleKey === "architect" || d.roleKey === "designer")
              .map((desk) => (
                <AgentDesk
                  key={desk.roleKey}
                  roleKey={desk.roleKey}
                  roleName={desk.roleName}
                  roleAbbr={desk.roleAbbr}
                  status={desk.status}
                  hasOutput={desk.hasOutput}
                  outputName={desk.outputName}
                  messageCount={desk.messageCount}
                  isSelected={selectedAgentId === desk.roleKey}
                  isUnlocked={desk.isUnlocked}
                  provider={desk.provider}
                  model={desk.model}
                  attachedSkills={desk.attachedSkills}
                  onClick={() => onSelectAgent(desk.roleKey)}
                />
              ))}
          </div>
        </div>

        {/* Stage 4 Pod: Staffing & Talent Acquisition (HR & Recruiter per Handbook Ch 6) */}
        <div className="w-full space-y-3 pt-4">
          <div className="flex items-center justify-between px-1">
            <span className="text-xs font-bold uppercase tracking-wider text-indigo-600 dark:text-indigo-400 flex items-center gap-1.5 font-mono">
              <Users className="w-3.5 h-3.5" />
              <span>Stage 4: Staffing & Talent Acquisition Pod (HR & Recruiter)</span>
            </span>
            <span className="text-[10px] text-brand-body font-mono">
              Generates docs/team-plan.json & hires team for Gate 2
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 w-full">
            {desks
              .filter((d) => d.roleKey === "hr" || d.roleKey === "recruiter")
              .map((desk) => (
                <AgentDesk
                  key={desk.roleKey}
                  roleKey={desk.roleKey}
                  roleName={desk.roleName}
                  roleAbbr={desk.roleAbbr}
                  status={desk.status}
                  hasOutput={desk.hasOutput}
                  outputName={desk.outputName}
                  messageCount={desk.messageCount}
                  isSelected={selectedAgentId === desk.roleKey}
                  isUnlocked={desk.isUnlocked}
                  provider={desk.provider}
                  model={desk.model}
                  attachedSkills={desk.attachedSkills}
                  onClick={() => onSelectAgent(desk.roleKey)}
                />
              ))}
          </div>
        </div>

        {/* Stage 5 Pod: Implementation & Quality Assurance (Engineer & QA) */}
        <div className="w-full space-y-3 pt-4">
          <div className="flex items-center justify-between px-1">
            <span className="text-xs font-bold uppercase tracking-wider text-brand-body/80 flex items-center gap-1.5 font-mono">
              <ShieldCheck className="w-3.5 h-3.5 text-brand-body" />
              <span>Stage 5: Implementation & QA Pod (Pipeline)</span>
            </span>
            <span className="text-[10px] text-brand-body/60 font-mono">
              Unlocks after Gate 2 Staffing & Budget sign-off
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 w-full">
            {desks
              .filter((d) => d.roleKey === "engineer" || d.roleKey === "qa")
              .map((desk) => (
                <AgentDesk
                  key={desk.roleKey}
                  roleKey={desk.roleKey}
                  roleName={desk.roleName}
                  roleAbbr={desk.roleAbbr}
                  status={desk.status}
                  hasOutput={desk.hasOutput}
                  outputName={desk.outputName}
                  messageCount={desk.messageCount}
                  isSelected={selectedAgentId === desk.roleKey}
                  isUnlocked={desk.isUnlocked}
                  provider={desk.provider}
                  model={desk.model}
                  onClick={() => onSelectAgent(desk.roleKey)}
                />
              ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PixelOfficeFloor;
