import React from "react";
import { AgentPixelAvatar, AgentRoleKey } from "./AgentAvatars";
import { AgentStatusBadge } from "./AgentStatusBadge";
import { AgentLiveStatus } from "../../lib/engine";
import { Users, ChevronRight, Lock } from "lucide-react";

export interface RosterAgentItem {
  id: AgentRoleKey;
  role: string;
  abbr: string;
  status: AgentLiveStatus;
  hasOutput: boolean;
  outputName?: string;
  isUnlocked: boolean;
}

interface AgentRosterProps {
  agents: RosterAgentItem[];
  selectedAgentId: AgentRoleKey | null;
  onSelectAgent: (agentId: AgentRoleKey) => void;
}

export const AgentRoster: React.FC<AgentRosterProps> = ({
  agents,
  selectedAgentId,
  onSelectAgent,
}) => {
  return (
    <footer className="w-full bg-brand-card/90 backdrop-blur-md border-t border-brand-border px-4 py-3 shrink-0 shadow-lg select-none z-20">
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        {/* Roster Title */}
        <div className="flex items-center gap-2 text-xs font-bold text-brand-headline shrink-0">
          <div className="w-6 h-6 rounded-md bg-brand-subtle flex items-center justify-center text-brand-accent">
            <Users className="w-3.5 h-3.5" />
          </div>
          <span>Project Roster</span>
          <span className="text-[10px] font-mono text-brand-body bg-brand-subtle px-1.5 py-0.5 rounded border border-brand-border">
            {agents.filter((a) => a.isUnlocked).length}/{agents.length} Active
          </span>
        </div>

        {/* Agent Cards Row */}
        <div className="flex items-center gap-2 overflow-x-auto w-full sm:w-auto pb-1 sm:pb-0 scrollbar-none">
          {agents.map((agent) => {
            const isSelected = selectedAgentId === agent.id;

            return (
              <button
                key={agent.id}
                type="button"
                onClick={() => agent.isUnlocked && onSelectAgent(agent.id)}
                disabled={!agent.isUnlocked}
                className={`flex items-center gap-2.5 px-3 py-2 rounded-xl border text-left transition-all duration-150 shrink-0 ${
                  isSelected
                    ? "bg-brand-accent text-brand-accent-text border-brand-accent shadow-xs scale-102"
                    : agent.isUnlocked
                    ? "bg-brand-card hover:bg-brand-subtle border-brand-border text-brand-headline cursor-pointer hover:border-brand-accent/40"
                    : "bg-brand-subtle/30 border-brand-border/50 text-brand-body/60 opacity-60 cursor-not-allowed"
                }`}
              >
                <AgentPixelAvatar role={agent.id} size="sm" />

                <div className="flex flex-col min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span
                      className={`text-[9px] font-mono font-bold px-1 rounded uppercase ${
                        isSelected
                          ? "bg-white/20 text-white"
                          : "bg-brand-subtle text-brand-accent"
                      }`}
                    >
                      {agent.abbr}
                    </span>
                    <span
                      className={`text-xs font-bold truncate max-w-[90px] ${
                        isSelected ? "text-white" : "text-brand-headline"
                      }`}
                    >
                      {agent.role}
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5 mt-0.5">
                    {agent.isUnlocked ? (
                      <AgentStatusBadge status={agent.status} size="sm" />
                    ) : (
                      <span className="text-[9px] font-mono flex items-center gap-0.5 opacity-70">
                        <Lock className="w-2.5 h-2.5" />
                        <span>Locked</span>
                      </span>
                    )}
                  </div>
                </div>

                {agent.isUnlocked && (
                  <ChevronRight
                    className={`w-3.5 h-3.5 ml-1 transition-transform ${
                      isSelected ? "text-white" : "text-brand-body/40"
                    }`}
                  />
                )}
              </button>
            );
          })}
        </div>
      </div>
    </footer>
  );
};

export default AgentRoster;
