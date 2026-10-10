import React from "react";
import { AgentLiveStatus } from "../../lib/engine";

interface AgentStatusBadgeProps {
  status: AgentLiveStatus;
  size?: "sm" | "md";
  className?: string;
}

export const AgentStatusBadge: React.FC<AgentStatusBadgeProps> = ({
  status,
  size = "md",
  className = "",
}) => {
  const configs: Record<
    AgentLiveStatus,
    {
      label: string;
      bg: string;
      text: string;
      border: string;
      dot: string;
      pulse?: boolean;
    }
  > = {
    idle: {
      label: "IDLE",
      bg: "bg-slate-100 dark:bg-slate-800/80",
      text: "text-slate-600 dark:text-slate-300",
      border: "border-slate-300 dark:border-slate-700",
      dot: "bg-slate-400 dark:bg-slate-500",
      pulse: false,
    },
    working: {
      label: "WORKING",
      bg: "bg-amber-100 dark:bg-amber-950/70",
      text: "text-amber-700 dark:text-amber-300",
      border: "border-amber-300 dark:border-amber-700/80",
      dot: "bg-amber-500",
      pulse: true,
    },
    "waiting-on-you": {
      label: "WAITING ON YOU",
      bg: "bg-sky-100 dark:bg-sky-950/70",
      text: "text-sky-700 dark:text-sky-300",
      border: "border-sky-300 dark:border-sky-700/80",
      dot: "bg-sky-500",
      pulse: true,
    },
    done: {
      label: "DONE",
      bg: "bg-emerald-100 dark:bg-emerald-950/70",
      text: "text-emerald-700 dark:text-emerald-300",
      border: "border-emerald-300 dark:border-emerald-700/80",
      dot: "bg-emerald-500",
      pulse: false,
    },
  };

  const c = configs[status] || configs.idle;

  const sizeClasses =
    size === "sm"
      ? "text-[9px] px-1.5 py-0.5 tracking-wider gap-1"
      : "text-[10px] px-2 py-0.5 tracking-wide gap-1.5";

  return (
    <span
      className={`inline-flex items-center font-mono font-bold rounded-md border shadow-2xs transition-colors duration-150 uppercase select-none ${c.bg} ${c.text} ${c.border} ${sizeClasses} ${className}`}
    >
      <span className="relative flex h-1.5 w-1.5">
        {c.pulse && (
          <span
            className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${c.dot}`}
          />
        )}
        <span className={`relative inline-flex rounded-full h-1.5 w-1.5 ${c.dot}`} />
      </span>
      <span>{c.label}</span>
    </span>
  );
};
