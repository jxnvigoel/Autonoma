import React, { useEffect, useState } from "react";
import { Header } from "../components/Header";
import { PixelOfficeFloor } from "../components/office/PixelOfficeFloor";
import { AgentRoster, RosterAgentItem } from "../components/office/AgentRoster";
import { CommandCenter } from "../components/office/CommandCenter";
import { AgentRoleKey } from "../components/office/AgentAvatars";
import { LLMSettingsModal } from "../components/office/LLMSettingsModal";
import { useConversation } from "../context/ConversationContext";
import { EngineStatus, LLMSettings, apiGetLLMSettings } from "../lib/engine";
import { AnimatePresence } from "framer-motion";
import { AlertTriangle } from "lucide-react";

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
    architectureContent,
    gate1State,
    appFlowContent,
    activeOfficeAgent,
    setActiveOfficeAgent,
    refreshOfficeStatus,
    fetchPmSession,
    fetchArchitectSession,
    fetchDesignerSession,
  } = useConversation();

  const [llmSettings, setLlmSettings] = useState<LLMSettings | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  const loadLLMSettings = async () => {
    try {
      const data = await apiGetLLMSettings(sessionId || undefined);
      setLlmSettings(data);
    } catch (err) {
      console.warn("Could not load LLM settings:", err);
    }
  };

  // Poll office status periodically for real live updates
  useEffect(() => {
    loadLLMSettings();
    if (sessionId) {
      refreshOfficeStatus(sessionId);
      fetchPmSession(sessionId);
      fetchArchitectSession(sessionId);
      fetchDesignerSession(sessionId);

      const interval = setInterval(() => {
        refreshOfficeStatus(sessionId);
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [sessionId, refreshOfficeStatus, fetchPmSession, fetchArchitectSession, fetchDesignerSession]);

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

  const gate1Approved = officeStatus?.gate1?.approved || gate1State?.approved;
  const archStatus =
    officeStatus?.agents?.architect?.status ||
    (architectureContent
      ? "done"
      : gate1Approved
      ? "waiting-on-you"
      : "idle");
  const isArchUnlocked = Boolean(gate1Approved || architectureContent);

  const desStatus =
    officeStatus?.agents?.designer?.status ||
    (appFlowContent
      ? "done"
      : gate1Approved
      ? "waiting-on-you"
      : "idle");
  const isDesUnlocked = Boolean(gate1Approved || appFlowContent);

  const isLocal = Boolean(llmSettings?.local_only);

  const getRoleModelAndProvider = (role: string) => {
    if (isLocal) {
      return { provider: "ollama", model: "llama3.2:3b" };
    }
    const cfg = llmSettings?.role_configs?.[role];
    return {
      provider: cfg?.provider || "groq",
      model: cfg?.model || "openai/gpt-oss-120b",
    };
  };

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
      provider: getRoleModelAndProvider("ba").provider,
      model: getRoleModelAndProvider("ba").model,
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
      provider: getRoleModelAndProvider("pm").provider,
      model: getRoleModelAndProvider("pm").model,
    },
    {
      roleKey: "architect" as AgentRoleKey,
      roleName: "Solution Architect",
      roleAbbr: "ARCH",
      status: archStatus,
      hasOutput: Boolean(architectureContent && architectureContent.length > 50),
      outputName: "architecture.md",
      messageCount: architectureContent ? 1 : 0,
      isUnlocked: isArchUnlocked,
      provider: getRoleModelAndProvider("architect").provider,
      model: getRoleModelAndProvider("architect").model,
    },
    {
      roleKey: "designer" as AgentRoleKey,
      roleName: "UI/UX Designer",
      roleAbbr: "DES",
      status: desStatus,
      hasOutput: Boolean(appFlowContent && appFlowContent.length > 50),
      outputName: "app-flow.md",
      messageCount: appFlowContent ? 1 : 0,
      isUnlocked: isDesUnlocked,
      provider: getRoleModelAndProvider("designer").provider,
      model: getRoleModelAndProvider("designer").model,
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
      provider: getRoleModelAndProvider("engineer").provider,
      model: getRoleModelAndProvider("engineer").model,
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
      provider: getRoleModelAndProvider("qa").provider,
      model: getRoleModelAndProvider("qa").model,
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

  const isGroqMissing =
    status?.groq_configured === false ||
    (llmSettings !== null && llmSettings.groq_configured === false);

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
        onOpenSettings={() => setIsSettingsOpen(true)}
      />

      {/* Prominent Missing Key Warning Banner (Never silent) */}
      {isGroqMissing && !isLocal && (
        <div className="bg-rose-500/15 border-b border-rose-500/30 px-6 py-2.5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs text-rose-800 dark:text-rose-200">
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="w-4 h-4 text-rose-500 shrink-0" />
            <div>
              <span className="font-bold">GROQ_API_KEY Missing: </span>
              <span>
                Groq is the default provider for all agents. Add your key to <code className="font-mono bg-rose-500/20 px-1 py-0.5 rounded">.env</code> or switch to Local-Only mode.
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setIsSettingsOpen(true)}
            className="px-3 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded-lg font-bold text-xs transition-colors shrink-0 cursor-pointer shadow-xs"
          >
            Configure LLM & Routing
          </button>
        </div>
      )}

      {/* Main Floor View */}
      <main className="flex-1 flex flex-col overflow-hidden relative">
        <PixelOfficeFloor
          desks={desksData}
          selectedAgentId={activeOfficeAgent}
          onSelectAgent={handleSelectAgent}
          projectName={intakeData?.projectName || "Current Project"}
          onOpenSettings={() => setIsSettingsOpen(true)}
          isLocalOnly={isLocal}
          isCloudActive={!isLocal && Boolean(llmSettings?.groq_configured ?? status?.groq_configured)}
          groqConfigured={Boolean(llmSettings?.groq_configured ?? status?.groq_configured)}
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

        {/* LLM Settings Modal */}
        <LLMSettingsModal
          isOpen={isSettingsOpen}
          onClose={() => setIsSettingsOpen(false)}
          sessionId={sessionId || undefined}
          projectName={intakeData?.projectName}
          onSettingsChanged={loadLLMSettings}
        />
      </main>
    </div>
  );
};

export default VirtualOffice;
