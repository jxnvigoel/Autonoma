import React from "react";
import { motion } from "framer-motion";
import {
  AgentPixelAvatar,
  AgentRoleKey,
} from "./AgentAvatars";
import { AgentStatusBadge } from "./AgentStatusBadge";
import { AgentLiveStatus } from "../../lib/engine";
import {
  FileText,
  FileCheck,
  Code2,
  Layers,
  ShieldCheck,
  Lock,
} from "lucide-react";

interface AgentDeskProps {
  roleKey: AgentRoleKey;
  roleName: string;
  roleAbbr: string;
  status: AgentLiveStatus;
  hasOutput: boolean;
  outputName?: string;
  messageCount?: number;
  isSelected?: boolean;
  isUnlocked?: boolean;
  onClick: () => void;
}

export const AgentDesk: React.FC<AgentDeskProps> = ({
  roleKey,
  roleName,
  roleAbbr,
  status,
  hasOutput,
  outputName,
  isSelected = false,
  isUnlocked = true,
  onClick,
}) => {
  const isWorking = status === "working";

  // Role visual colors
  const roleStyles: Record<
    AgentRoleKey,
    {
      glow: string;
      monitorColor: string;
      icon: React.ReactNode;
      deskAccent: string;
    }
  > = {
    ba: {
      glow: "hover:border-blue-500/80 group-hover:shadow-[0_0_20px_rgba(59,130,246,0.3)]",
      monitorColor: "#3B82F6",
      icon: <FileCheck className="w-3.5 h-3.5 text-blue-500" />,
      deskAccent: "bg-blue-500/20 text-blue-600 dark:text-blue-400 border-blue-500/30",
    },
    pm: {
      glow: "hover:border-purple-500/80 group-hover:shadow-[0_0_20px_rgba(168,85,247,0.3)]",
      monitorColor: "#A855F7",
      icon: <FileText className="w-3.5 h-3.5 text-purple-500" />,
      deskAccent: "bg-purple-500/20 text-purple-600 dark:text-purple-400 border-purple-500/30",
    },
    architect: {
      glow: "hover:border-emerald-500/80 group-hover:shadow-[0_0_20px_rgba(16,185,129,0.3)]",
      monitorColor: "#10B981",
      icon: <Layers className="w-3.5 h-3.5 text-emerald-500" />,
      deskAccent: "bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border-emerald-500/30",
    },
    engineer: {
      glow: "hover:border-rose-500/80 group-hover:shadow-[0_0_20px_rgba(239,68,68,0.3)]",
      monitorColor: "#EF4444",
      icon: <Code2 className="w-3.5 h-3.5 text-rose-500" />,
      deskAccent: "bg-rose-500/20 text-rose-600 dark:text-rose-400 border-rose-500/30",
    },
    qa: {
      glow: "hover:border-amber-500/80 group-hover:shadow-[0_0_20px_rgba(245,158,11,0.3)]",
      monitorColor: "#F59E0B",
      icon: <ShieldCheck className="w-3.5 h-3.5 text-amber-500" />,
      deskAccent: "bg-amber-500/20 text-amber-600 dark:text-amber-400 border-amber-500/30",
    },
  };

  const style = roleStyles[roleKey] || roleStyles.ba;

  return (
    <motion.div
      whileHover={{ scale: isUnlocked ? 1.02 : 1, y: isUnlocked ? -2 : 0 }}
      whileTap={{ scale: isUnlocked ? 0.98 : 1 }}
      onClick={isUnlocked ? onClick : undefined}
      className={`group relative flex flex-col items-center justify-between p-4 rounded-2xl border-2 transition-all duration-200 select-none ${
        isSelected
          ? "border-brand-accent bg-brand-card shadow-lg ring-2 ring-brand-accent/20"
          : isUnlocked
          ? `border-brand-border bg-brand-card/90 hover:bg-brand-card shadow-card cursor-pointer ${style.glow}`
          : "border-brand-border/60 bg-brand-subtle/30 opacity-60 cursor-not-allowed"
      }`}
      style={{ minWidth: "210px" }}
    >
      {/* Top Header: Role & Live Status Badge */}
      <div className="w-full flex items-center justify-between gap-1 pb-3 mb-2 border-b border-brand-border/60">
        <div className="flex items-center gap-1.5 min-w-0">
          <span
            className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded border uppercase ${style.deskAccent}`}
          >
            {roleAbbr}
          </span>
          <span className="text-xs font-bold text-brand-headline truncate">
            {roleName}
          </span>
        </div>

        {isUnlocked ? (
          <AgentStatusBadge status={status} size="sm" />
        ) : (
          <span className="inline-flex items-center gap-1 text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-brand-subtle text-brand-body border border-brand-border">
            <Lock className="w-2.5 h-2.5" />
            <span>Pipeline</span>
          </span>
        )}
      </div>

      {/* Desk Visual Scene */}
      <div className="relative my-2 flex flex-col items-center justify-center w-full py-2">
        {/* Agent Avatar sitting behind desk */}
        <div className="relative z-10 transition-transform duration-200 group-hover:-translate-y-1">
          <AgentPixelAvatar role={roleKey} size="lg" isWorking={isWorking} />
        </div>

        {/* Pixel Desk Surface */}
        <div className="relative -mt-3 z-20 w-44 h-16 bg-[#2B231D] dark:bg-[#1E1916] rounded-xl border border-[#45362E] dark:border-[#382C24] shadow-md flex items-center justify-between px-3 overflow-hidden">
          {/* Desk Wood Texture subtle stripes */}
          <div className="absolute inset-0 opacity-15 pointer-events-none bg-[repeating-linear-gradient(90deg,transparent,transparent_10px,#000_10px,#000_12px)]" />

          {/* Left: Pixel Coffee Cup */}
          <div className="flex flex-col items-center">
            <span className="w-3 h-3 rounded-xs bg-amber-100 border border-amber-900 shadow-2xs relative flex items-center justify-center">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-800" />
            </span>
            <span className="w-4 h-0.5 bg-black/40 rounded-full mt-0.5" />
          </div>

          {/* Center: Dual Monitor Display */}
          <div className="flex flex-col items-center">
            {/* Monitor Screen */}
            <div className="w-16 h-10 rounded-md bg-[#0F172A] border border-[#334155] p-1 flex flex-col justify-between shadow-inner relative overflow-hidden">
              {/* Screen Glow */}
              <div
                className="absolute inset-0 opacity-20"
                style={{ backgroundColor: style.monitorColor }}
              />

              {/* Monitor code/spec scanlines */}
              <div className="space-y-0.5 z-10">
                <div
                  className="h-1 rounded-xs w-3/4 opacity-90 animate-pulse"
                  style={{ backgroundColor: style.monitorColor }}
                />
                <div className="h-0.5 rounded-xs w-1/2 bg-slate-400 opacity-60" />
                <div className="h-0.5 rounded-xs w-5/6 bg-slate-400 opacity-60" />
              </div>

              {/* Keyboard in front */}
              <div className="w-12 h-1.5 rounded-xs bg-[#1E293B] border border-[#475569] self-center mt-1 z-10" />
            </div>

            {/* Monitor Stand */}
            <div className="w-3 h-1 bg-[#475569] -mt-0.5" />
            <div className="w-7 h-0.5 bg-[#334155] rounded-full" />
          </div>

          {/* Right: Desk Plant / Notebook */}
          <div className="flex flex-col items-center">
            <span className="w-3 h-2.5 rounded-t-sm bg-emerald-600 border border-emerald-900 shadow-2xs" />
            <span className="w-2.5 h-2 rounded-b-sm bg-amber-800 border border-amber-950" />
          </div>
        </div>
      </div>

      {/* Bottom Desk Meta & Interaction CTA */}
      <div className="w-full mt-2 pt-2.5 border-t border-brand-border/60 flex items-center justify-between text-[11px]">
        <div className="flex items-center gap-1.5 text-brand-body">
          {style.icon}
          <span className="truncate max-w-[110px] font-mono text-[10px]">
            {hasOutput ? outputName || "output.md" : "No output yet"}
          </span>
        </div>

        {isUnlocked ? (
          <span className="text-[10px] font-bold text-brand-accent group-hover:underline flex items-center gap-0.5">
            <span>Open</span>
            <span>→</span>
          </span>
        ) : (
          <span className="text-[9px] font-mono text-brand-body/60">Stage 2</span>
        )}
      </div>

      {/* Selected Indicator Pill */}
      {isSelected && (
        <div className="absolute -top-2.5 left-1/2 -translate-x-1/2 px-2.5 py-0.5 rounded-full bg-brand-accent text-brand-accent-text text-[9px] font-mono font-bold shadow-xs">
          ACTIVE COMMAND
        </div>
      )}
    </motion.div>
  );
};

export default AgentDesk;
