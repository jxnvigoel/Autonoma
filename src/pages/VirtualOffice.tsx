import React, { useEffect, useState } from "react";
import { Header } from "../components/Header";
import { PixelOfficeFloor } from "../components/office/PixelOfficeFloor";
import { AgentRoster, RosterAgentItem } from "../components/office/AgentRoster";
import { CommandCenter } from "../components/office/CommandCenter";
import { AgentRoleKey } from "../components/office/AgentAvatars";
import { useNav } from "../context/NavContext";
import { useConversation } from "../context/ConversationContext";
import { EngineStatus, LLMSettings, apiGetLLMSettings } from "../lib/engine";
import { useModelRoutes } from "../lib/modelRoutes";
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
    teamPlanData,
    staffingReportContent,
    gate2State,
    activeOfficeAgent,
    setActiveOfficeAgent,
    refreshOfficeStatus,
    fetchPmSession,
    fetchArchitectSession,
    fetchDesignerSession,
    isPrdGenerating,
    isFeasibilityRunning,
    isArchitectGenerating,
    isDesignerGenerating,
    isHrGenerating,
    isRecruiterGenerating,
    isScrumGenerating,
    isReadinessGenerating,
  } = useConversation();
  const modelRoutes = useModelRoutes();

  const [llmSettings, setLlmSettings] = useState<LLMSettings | null>(null);
  const nav = useNav();

  const loadLLMSettings = async () => {
    try {
      const data = await apiGetLLMSettings(sessionId || undefined);
      setLlmSettings(data);
    } catch (err) {
      console.warn("Could not load LLM settings:", err);
    }
  };

  // Settings live in the shared navigation now; reload when they change.
  useEffect(() => {
    const onChange = () => loadLLMSettings();
    window.addEventListener("autonoma:llm-settings-changed", onChange);
    return () => window.removeEventListener("autonoma:llm-settings-changed", onChange);
  });

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

  const pmStatus = isPrdGenerating ? "working" :
    officeStatus?.agents?.pm?.status ||
    (pmStarted
      ? "waiting-on-you"
      : "idle");

  const gate1Approved = officeStatus?.gate1?.approved || gate1State?.approved;
  const archStatus = isArchitectGenerating || isFeasibilityRunning ? "working" :
    officeStatus?.agents?.architect?.status ||
    (architectureContent
      ? "done"
      : gate1Approved
      ? "waiting-on-you"
      : "idle");
  const isArchUnlocked = Boolean(gate1Approved || architectureContent);

  const desStatus = isDesignerGenerating ? "working" :
    officeStatus?.agents?.designer?.status ||
    (appFlowContent
      ? "done"
      : gate1Approved
      ? "waiting-on-you"
      : "idle");
  const isDesUnlocked = Boolean(gate1Approved || appFlowContent);

  const hrStatus = isHrGenerating ? "working" :
    officeStatus?.agents?.hr?.status ||
    (teamPlanData ? "done" : architectureContent ? "waiting-on-you" : "idle");
  const isHrUnlocked = Boolean(architectureContent);

  const recStatus = isRecruiterGenerating ? "working" :
    officeStatus?.agents?.recruiter?.status ||
    (staffingReportContent ? "done" : teamPlanData ? "waiting-on-you" : "idle");
  const isRecUnlocked = Boolean(teamPlanData);

  const gate2Approved = Boolean(gate2State?.approved);
  const scrumStatus = isScrumGenerating ? "working" :
    officeStatus?.agents?.scrum?.status ||
    (gate2Approved ? "waiting-on-you" : "idle");
  const isScrumUnlocked = Boolean(gate2Approved);

  const tlStatus = isReadinessGenerating ? "working" :
    officeStatus?.agents?.["tech-lead"]?.status ||
    (gate2Approved ? "waiting-on-you" : "idle");
  const isTlUnlocked = Boolean(gate2Approved);

  const isLocal = Boolean(llmSettings?.local_only);

  // What the engine's router actually resolves for each role right now (Groq first, Ollama fallback).
  const getRoleModelAndProvider = (role: string) => {
    if (isLocal) {
      return { provider: "ollama", model: modelRoutes?.localDefaultModel || llmSettings?.local_default_model || "local model" };
    }
    const route = modelRoutes?.roles[role];
    return { provider: route?.provider || "unknown", model: route?.model || "checking…" };
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
      roleKey: "hr" as AgentRoleKey,
      roleName: "Staffing Planner",
      roleAbbr: "HR",
      status: hrStatus,
      hasOutput: Boolean(teamPlanData),
      outputName: "team-plan.json",
      messageCount: teamPlanData ? 1 : 0,
      isUnlocked: isHrUnlocked,
      provider: getRoleModelAndProvider("hr").provider,
      model: getRoleModelAndProvider("hr").model,
    },
    {
      roleKey: "recruiter" as AgentRoleKey,
      roleName: "Technical Recruiter",
      roleAbbr: "REC",
      status: recStatus,
      hasOutput: Boolean(staffingReportContent),
      outputName: "staffing-report.md",
      messageCount: staffingReportContent ? 1 : 0,
      isUnlocked: isRecUnlocked,
      provider: getRoleModelAndProvider("recruiter").provider,
      model: getRoleModelAndProvider("recruiter").model,
    },
    {
      roleKey: "scrum" as AgentRoleKey,
      roleName: "Scrum Master",
      roleAbbr: "SCRUM",
      status: scrumStatus,
      hasOutput: Boolean(officeStatus?.agents?.scrum?.has_output),
      outputName: "backlog.json",
      messageCount: 0,
      isUnlocked: isScrumUnlocked,
      provider: getRoleModelAndProvider("scrum").provider,
      model: getRoleModelAndProvider("scrum").model,
    },
    {
      roleKey: "tech-lead" as AgentRoleKey,
      roleName: "Tech Lead",
      roleAbbr: "TL",
      status: tlStatus,
      hasOutput: Boolean(officeStatus?.agents?.["tech-lead"]?.has_output),
      outputName: "readiness.md",
      messageCount: 0,
      isUnlocked: isTlUnlocked,
      provider: getRoleModelAndProvider("tech-lead").provider,
      model: getRoleModelAndProvider("tech-lead").model,
    },
    {
      roleKey: "engineer" as AgentRoleKey,
      roleName: "Software Engineer",
      roleAbbr: "ENG",
      // Engineers and QA work during the build (Stage 6-7); their desks follow the live build state.
      status: officeStatus?.agents?.engineer?.status || ("idle" as const),
      hasOutput: Boolean(officeStatus?.agents?.engineer?.has_output),
      outputName: "repo/",
      messageCount: 0,
      isUnlocked: Boolean(officeStatus?.agents?.engineer?.can_start),
      provider: getRoleModelAndProvider("backend").provider,
      model: getRoleModelAndProvider("backend").model,
    },
    {
      roleKey: "qa" as AgentRoleKey,
      roleName: "Quality Assurance",
      roleAbbr: "QA",
      status: officeStatus?.agents?.qa?.status || ("idle" as const),
      hasOutput: Boolean(officeStatus?.agents?.qa?.has_output),
      outputName: "test results",
      messageCount: 0,
      isUnlocked: Boolean(officeStatus?.agents?.qa?.can_start),
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
    attachedSkills: officeStatus?.agents?.[d.roleKey]?.attached_skills || [],
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
            onClick={() => nav?.openSettings()}
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
          onOpenSettings={() => nav?.openSettings()}
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

      </main>
    </div>
  );
};

export default VirtualOffice;
