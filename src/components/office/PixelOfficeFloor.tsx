import React from "react";
import { AgentDesk } from "./AgentDesk";
import { AgentRoleKey } from "./AgentAvatars";
import { AgentLiveStatus } from "../../lib/engine";
import { Sparkles, Coffee, Cpu, ShieldCheck } from "lucide-react";

interface OfficeDeskData {
  roleKey: AgentRoleKey;
  roleName: string;
  roleAbbr: string;
  status: AgentLiveStatus;
  hasOutput: boolean;
  outputName?: string;
  messageCount?: number;
  isUnlocked: boolean;
}

interface PixelOfficeFloorProps {
  desks: OfficeDeskData[];
  selectedAgentId: AgentRoleKey | null;
  onSelectAgent: (roleKey: AgentRoleKey) => void;
  projectName?: string;
}

export const PixelOfficeFloor: React.FC<PixelOfficeFloorProps> = ({
  desks,
  selectedAgentId,
  onSelectAgent,
  projectName = "Active Project",
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

          {/* Quick Environment Perks */}
          <div className="flex items-center gap-2 text-xs text-brand-body">
            <span className="flex items-center gap-1 bg-brand-subtle/70 px-2.5 py-1 rounded-lg border border-brand-border text-[11px]">
              <Coffee className="w-3.5 h-3.5 text-amber-600" />
              <span>Studio Breakroom</span>
            </span>
            <span className="flex items-center gap-1 bg-brand-subtle/70 px-2.5 py-1 rounded-lg border border-brand-border text-[11px]">
              <Cpu className="w-3.5 h-3.5 text-blue-500" />
              <span>100% Local Multi-Agent</span>
            </span>
          </div>
        </div>

        {/* Phase 1 Primary Active Pod (BA & PM Workstations) */}
        <div className="w-full space-y-3">
          <div className="flex items-center justify-between px-1">
            <span className="text-xs font-bold uppercase tracking-wider text-brand-accent flex items-center gap-1.5 font-mono">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Discovery & Product Planning Pod (Active)</span>
            </span>
            <span className="text-[10px] text-brand-body font-mono">
              Click desk to open Command Center
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
                  onClick={() => onSelectAgent(desk.roleKey)}
                />
              ))}
          </div>
        </div>

        {/* Phase 2 Engineering & Quality Pod (Architect, Engineer, QA) */}
        <div className="w-full space-y-3 pt-4">
          <div className="flex items-center justify-between px-1">
            <span className="text-xs font-bold uppercase tracking-wider text-brand-body/80 flex items-center gap-1.5 font-mono">
              <ShieldCheck className="w-3.5 h-3.5 text-brand-body" />
              <span>Engineering & QA Pod (Pipeline)</span>
            </span>
            <span className="text-[10px] text-brand-body/60 font-mono">
              Unlocks after PRD sign-off
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 w-full">
            {desks
              .filter((d) => d.roleKey !== "ba" && d.roleKey !== "pm")
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
