import React, { useEffect } from "react";
import { Header } from "../components/Header";
import { PixelOfficeFloor } from "../components/office/PixelOfficeFloor";
import { AgentRoster, RosterAgentItem } from "../components/office/AgentRoster";
import { CommandCenter } from "../components/office/CommandCenter";
import { AgentRoleKey } from "../components/office/AgentAvatars";
import { useConversation } from "../context/ConversationContext";
import { EngineStatus } from "../lib/engine";
import { AnimatePresence } from "framer-motion";

interface VirtualOfficeProps {
  status: EngineStatus | null;
  isCheckingStatus: boolean;
  onRefreshStatus: () => void;
  onBackToLanding: () => void;
  onOpenProjects?: () => void;
  onOpenChat: () => void;
  onOpenEditor: () => void;
}

export const VirtualOffice: React.FC<VirtualOfficeProps> = ({
  status,
  isCheckingStatus,
  onRefreshStatus,
  onBackToLanding,
  onOpenProjects,
  onOpenChat,
  onOpenEditor,
}) => {
  const {
    sessionId,
    intakeData,
    officeStatus,
    readyForRequirements,
    requirementsContent,
    messages: baMessages,
    pmStarted,
    prdContent,
    pmMessages,
    activeOfficeAgent,
    setActiveOfficeAgent,
    refreshOfficeStatus,
    fetchPmSession,
  } = useConversation();

  // Poll office status periodically for real live updates
  useEffect(() => {
    if (sessionId) {
      refreshOfficeStatus(sessionId);
      fetchPmSession(sessionId);

      const interval = setInterval(() => {
        refreshOfficeStatus(sessionId);
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [sessionId, refreshOfficeStatus, fetchPmSession]);

  // Compute live desk data sourced from real backend session state
  const baStatus =
    officeStatus?.agents?.ba?.status ||
    (readyForRequirements
      ? "done"
      : baMessages.length > 0
      ? "waiting-on-you"
      : "idle");

  const pmStatus =
    officeStatus?.agents?.pm?.status ||
    (pmStarted
      ? "waiting-on-you"
      : "idle");

  const desksData = [
    {
      roleKey: "ba" as AgentRoleKey,
      roleName: "Business Analyst",
      roleAbbr: "BA",
      status: baStatus,
      hasOutput: Boolean(requirementsContent || readyForRequirements),
      outputName: "requirements.md",
      messageCount: baMessages.length,
      isUnlocked: true,
    },
    {
      roleKey: "pm" as AgentRoleKey,
      roleName: "Product Manager",
      roleAbbr: "PM",
      status: pmStatus,
      hasOutput: Boolean(prdContent && prdContent.length > 50),
      outputName: "prd.md",
      messageCount: pmMessages.length,
      isUnlocked: true,
    },
    {
      roleKey: "architect" as AgentRoleKey,
      roleName: "Software Architect",
      roleAbbr: "ARCH",
      status: "idle" as const,
      hasOutput: false,
      outputName: "architecture.md",
      messageCount: 0,
      isUnlocked: false,
    },
    {
      roleKey: "engineer" as AgentRoleKey,
      roleName: "Software Engineer",
      roleAbbr: "ENG",
      status: "idle" as const,
      hasOutput: false,
      outputName: "source_code",
      messageCount: 0,
      isUnlocked: false,
    },
    {
      roleKey: "qa" as AgentRoleKey,
      roleName: "Quality Assurance",
      roleAbbr: "QA",
      status: "idle" as const,
      hasOutput: false,
      outputName: "test_plan.md",
      messageCount: 0,
      isUnlocked: false,
    },
  ];

  const rosterAgents: RosterAgentItem[] = desksData.map((d) => ({
    id: d.roleKey,
    role: d.roleName,
    abbr: d.roleAbbr,
    status: d.status,
    hasOutput: d.hasOutput,
    outputName: d.outputName,
    isUnlocked: d.isUnlocked,
  }));

  const handleSelectAgent = (agentKey: AgentRoleKey) => {
    setActiveOfficeAgent(agentKey);
  };

  const handleCloseCommandCenter = () => {
    setActiveOfficeAgent(null);
  };

  return (
    <div className="h-screen bg-brand-bg text-brand-headline flex flex-col font-sans transition-colors duration-200 overflow-hidden">
      {/* Top Navigation Header */}
      <Header
        status={status}
        isChecking={isCheckingStatus}
        onRefreshStatus={onRefreshStatus}
        onBackToLanding={onBackToLanding}
        activeScreen="office"
        onOpenProjects={onOpenProjects}
        onOpenChat={onOpenChat}
        onOpenEditor={onOpenEditor}
      />

      {/* Main Floor View */}
      <main className="flex-1 flex flex-col overflow-hidden relative">
        <PixelOfficeFloor
          desks={desksData}
          selectedAgentId={activeOfficeAgent}
          onSelectAgent={handleSelectAgent}
          projectName={intakeData?.projectName || "Current Project"}
        />

        {/* Bottom Roster Bar */}
        <AgentRoster
          agents={rosterAgents}
          selectedAgentId={activeOfficeAgent}
          onSelectAgent={handleSelectAgent}
        />

        {/* Command Center Overlay/Panel */}
        <AnimatePresence>
          {activeOfficeAgent && (
            <CommandCenter
              activeAgent={activeOfficeAgent}
              onClose={handleCloseCommandCenter}
              onSwitchAgent={handleSelectAgent}
            />
          )}
        </AnimatePresence>
      </main>
    </div>
  );
};

export default VirtualOffice;
