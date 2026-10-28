import React from "react";

export type AgentRoleKey = "ba" | "pm" | "architect" | "designer" | "hr" | "recruiter" | "scrum" | "tech-lead" | "engineer" | "qa";

interface AgentAvatarProps {
  role: AgentRoleKey;
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
  isWorking?: boolean;
}

export const AgentPixelAvatar: React.FC<AgentAvatarProps> = ({
  role,
  size = "md",
  className = "",
  isWorking = false,
}) => {
  const sizeMap = {
    sm: "w-8 h-8",
    md: "w-12 h-12",
    lg: "w-16 h-16",
    xl: "w-20 h-20",
  };

  // Color schemes for each role
  const roleColors = {
    ba: {
      hair: "#D97706",
      face: "#FCD34D",
      clothes: "#2563EB",
      accessory: "#60A5FA",
      accent: "#3B82F6",
      deskAccent: "bg-blue-500",
    },
    pm: {
      hair: "#4B5563",
      face: "#FDE68A",
      clothes: "#7C3AED",
      accessory: "#C084FC",
      accent: "#8B5CF6",
      deskAccent: "bg-purple-500",
    },
    architect: {
      hair: "#1F2937",
      face: "#FDE68A",
      clothes: "#059669",
      accessory: "#34D399",
      accent: "#10B981",
      deskAccent: "bg-emerald-500",
    },
    designer: {
      hair: "#0F766E",
      face: "#FDE68A",
      clothes: "#0284C7",
      accessory: "#38BDF8",
      accent: "#06B6D4",
      deskAccent: "bg-cyan-500",
    },
    hr: {
      hair: "#312E81",
      face: "#FDE68A",
      clothes: "#4F46E5",
      accessory: "#818CF8",
      accent: "#6366F1",
      deskAccent: "bg-indigo-500",
    },
    recruiter: {
      hair: "#1E1B4B",
      face: "#FCD34D",
      clothes: "#0D9488",
      accessory: "#2DD4BF",
      accent: "#14B8A6",
      deskAccent: "bg-teal-500",
    },
    scrum: {
      hair: "#C2410C",
      face: "#FDE68A",
      clothes: "#EA580C",
      accessory: "#FB923C",
      accent: "#F97316",
      deskAccent: "bg-orange-500",
    },
    "tech-lead": {
      hair: "#1E1B4B",
      face: "#FCD34D",
      clothes: "#7C2D12",
      accessory: "#A855F7",
      accent: "#9333EA",
      deskAccent: "bg-purple-600",
    },
    engineer: {
      hair: "#B45309",
      face: "#FCD34D",
      clothes: "#DC2626",
      accessory: "#F87171",
      accent: "#EF4444",
      deskAccent: "bg-rose-500",
    },
    qa: {
      hair: "#047857",
      face: "#FDE68A",
      clothes: "#D97706",
      accessory: "#FBBF24",
      accent: "#F59E0B",
      deskAccent: "bg-amber-500",
    },
  };

  const c = roleColors[role] || roleColors.ba;

  return (
    <div
      className={`relative inline-flex items-center justify-center shrink-0 ${sizeMap[size]} ${className}`}
    >
      <svg
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="w-full h-full drop-shadow-sm image-rendering-pixelated"
        style={{ shapeRendering: "crispEdges" }}
      >
        {/* Pixel Body / Backdrop */}
        <rect x="2" y="2" width="20" height="20" rx="3" fill="#1E293B" />
        <rect x="3" y="3" width="18" height="18" rx="2" fill="#0F172A" />

        {/* Pixel Hair Top */}
        <rect x="6" y="4" width="12" height="4" fill={c.hair} />
        <rect x="5" y="6" width="3" height="4" fill={c.hair} />
        <rect x="16" y="6" width="3" height="4" fill={c.hair} />

        {/* Pixel Face */}
        <rect x="7" y="7" width="10" height="7" fill={c.face} />

        {/* Eyes */}
        <rect x="8" y="9" width="2" height="2" fill="#0F172A" />
        <rect x="14" y="9" width="2" height="2" fill="#0F172A" />

        {/* Glasses / Headset / Features based on role */}
        {role === "ba" && (
          <>
            {/* Glasses frame */}
            <rect x="7" y="8" width="4" height="4" stroke="#1E3A8A" strokeWidth="1" fill="none" />
            <rect x="13" y="8" width="4" height="4" stroke="#1E3A8A" strokeWidth="1" fill="none" />
            <rect x="11" y="9" width="2" height="1" fill="#1E3A8A" />
          </>
        )}

        {role === "pm" && (
          <>
            {/* Headset */}
            <rect x="5" y="7" width="2" height="4" fill="#6B21A8" />
            <rect x="17" y="7" width="2" height="4" fill="#6B21A8" />
            <rect x="7" y="5" width="10" height="1" fill="#6B21A8" />
            <rect x="16" y="11" width="3" height="1" fill="#6B21A8" />
          </>
        )}

        {role === "architect" && (
          <>
            {/* Beard or tie */}
            <rect x="11" y="12" width="2" height="2" fill="#065F46" />
          </>
        )}

        {role === "hr" && (
          <>
            {/* Glasses & Clipboard pin */}
            <rect x="8" y="9" width="3" height="2" stroke="#312E81" strokeWidth="1" fill="none" />
            <rect x="13" y="9" width="3" height="2" stroke="#312E81" strokeWidth="1" fill="none" />
            <rect x="11" y="14" width="2" height="3" fill="#818CF8" />
          </>
        )}

        {role === "recruiter" && (
          <>
            {/* Headset & Talent badge */}
            <rect x="5" y="7" width="2" height="3" fill="#0D9488" />
            <rect x="17" y="7" width="2" height="3" fill="#0D9488" />
            <rect x="11" y="14" width="2" height="2" fill="#2DD4BF" />
          </>
        )}


        {role === "engineer" && (
          <>
            {/* Hoodie strings / headphones */}
            <rect x="5" y="8" width="2" height="3" fill="#991B1B" />
            <rect x="17" y="8" width="2" height="3" fill="#991B1B" />
          </>
        )}

        {role === "qa" && (
          <>
            {/* Cap or visor */}
            <rect x="6" y="6" width="12" height="2" fill="#B45309" />
          </>
        )}

        {/* Mouth */}
        <rect x="10" y="12" width="4" height="1" fill="#991B1B" />

        {/* Clothes / Torso */}
        <rect x="5" y="14" width="14" height="7" fill={c.clothes} />
        {/* Collar / Tie */}
        <rect x="10" y="14" width="4" height="4" fill={c.accessory} />

        {/* Computer Screen or Desk Glow in foreground */}
        <rect x="4" y="19" width="16" height="2" fill="#334155" />
        <rect x="6" y="18" width="12" height="1" fill={c.accent} />
      </svg>

      {/* Animated status spark when working */}
      {isWorking && (
        <span className="absolute -top-1 -right-1 flex h-3 w-3">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-3 w-3 bg-amber-500 border border-black"></span>
        </span>
      )}
    </div>
  );
};
