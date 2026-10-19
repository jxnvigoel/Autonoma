import React, { useState, useRef, useEffect } from "react";
import { motion } from "framer-motion";
import {
  X,
  Send,
  Loader2,
  Sparkles,
  ArrowRight,
  Maximize2,
  Minimize2,
  Briefcase,
  Layers,
  FileCheck,
  FileText,
  AlertCircle,
  CheckCircle2,
  Lock,
  Cpu,
  Palette,
} from "lucide-react";
import { AgentRoleKey, AgentPixelAvatar } from "./AgentAvatars";
import { AgentStatusBadge } from "./AgentStatusBadge";
import { MessageBubble, TypingDots } from "../chat/MessageBubble";
import { PRDViewer } from "./PRDViewer";
import { BAOutputViewer } from "./BAOutputViewer";
import { ArchitectOutputViewer } from "./ArchitectOutputViewer";
import { DesignerOutputViewer } from "./DesignerOutputViewer";
import { useConversation } from "../../context/ConversationContext";
import { AgentLiveStatus } from "../../lib/engine";

interface CommandCenterProps {
  activeAgent: AgentRoleKey;
  onClose: () => void;
  onSwitchAgent: (agent: AgentRoleKey) => void;
}

export const CommandCenter: React.FC<CommandCenterProps> = ({
  activeAgent,
  onClose,
  onSwitchAgent,
}) => {
  const {
    intakeData,
    messages: baMessages,
    qaLog,
    readyForRequirements,
    requirementsContent,
    isSending: isBaSending,
    sendMessage: sendBaMessage,
    pmMessages,
    prdContent,
    estimateData,
    pmStarted,
    isPmSending,
    pmError,
    architectureContent,
    schemaContent,
    openapiContent,
    architectState,
    gate1State,
    isArchitectGenerating,
    isGate1Approving,
    appFlowContent,
    designBriefContent,
    designerState,
    isDesignerGenerating,
    generateDesignerArtifacts,
    startPm,
    sendPm,
    approveGate1,
    requestGate1Changes,
    generateArchitectArtifacts,
    officeStatus,
  } = useConversation();

  const [inputMessage, setInputMessage] = useState("");
  const [isHandoffRunning, setIsHandoffRunning] = useState(false);
  const [isFullScreen, setIsFullScreen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const isBA = activeAgent === "ba";
  const isPM = activeAgent === "pm";
  const isArchitect = activeAgent === "architect";
  const isDesigner = activeAgent === "designer";
  const gate1Approved = Boolean(officeStatus?.gate1?.approved || gate1State?.approved);

  const currentMessages = isBA ? baMessages : pmMessages;
  const isAgentThinking = isBA ? isBaSending : isPmSending;

  // Agent meta
  const agentMeta = {
    ba: {
      role: "Business Analyst",
      abbr: "BA",
      status: (officeStatus?.agents?.ba?.status ||
        (readyForRequirements ? "done" : baMessages.length > 0 ? "waiting-on-you" : "idle")) as AgentLiveStatus,
      description: "Discovery interview, client requirements extraction, and requirements.md",
      outputTitle: "Requirements & Discovery Log",
    },
    pm: {
      role: "Product Manager",
      abbr: "PM",
      status: (officeStatus?.agents?.pm?.status ||
        (pmStarted ? "waiting-on-you" : "idle")) as AgentLiveStatus,
      description: "Translates requirements into structured PRD, user stories, and acceptance criteria",
      outputTitle: "Live Product Requirement Document",
    },
    architect: {
      role: "Solution Architect",
      abbr: "ARCH",
      status: (officeStatus?.agents?.architect?.status ||
        (architectureContent ? "done" : gate1Approved ? "waiting-on-you" : "idle")) as AgentLiveStatus,
      description: "System architecture, component diagrams, and API contracts",
      outputTitle: "Architecture Blueprint",
    },
    designer: {
      role: "UI/UX Designer",
      abbr: "DES",
      status: (officeStatus?.agents?.designer?.status ||
        (appFlowContent ? "done" : gate1Approved ? "waiting-on-you" : "idle")) as AgentLiveStatus,
      description: "App flow diagrams, screen states, user journeys, and WCAG 2.2 AA visual tokens",
      outputTitle: "App Flow & Design Brief",
    },
    engineer: {
      role: "Software Engineer",
      abbr: "ENG",
      status: "idle" as AgentLiveStatus,
      description: "Code generation, implementation, and module assembly",
      outputTitle: "Source Code",
    },
    qa: {
      role: "Quality Assurance",
      abbr: "QA",
      status: "idle" as AgentLiveStatus,
      description: "Acceptance criteria validation, test suites, and regression checks",
      outputTitle: "Test Plan & Results",
    },
  }[activeAgent];

  // Auto scroll messages to bottom on new turn
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [currentMessages, isAgentThinking]);

  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const trimmed = inputMessage.trim();
    if (!trimmed || isAgentThinking) return;

    setInputMessage("");

    if (isBA) {
      await sendBaMessage(trimmed);
    } else if (isPM) {
      await sendPm(trimmed);
    }
  };

  const handleSendToPM = async () => {
    setIsHandoffRunning(true);
    try {
      await startPm();
      onSwitchAgent("pm");
    } catch {
      // Error handled in context
    } finally {
      setIsHandoffRunning(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 16 }}
      transition={{ duration: 0.2 }}
      className={`fixed z-40 bg-brand-bg text-brand-headline flex flex-col shadow-2xl transition-all duration-200 border-t sm:border border-brand-border ${
        isFullScreen
          ? "inset-0"
          : "inset-x-0 bottom-0 top-14 sm:inset-4 sm:top-16 sm:rounded-2xl"
      }`}
    >
      {/* Top Command Bar */}
      <header className="px-4 py-3 border-b border-brand-border bg-brand-card flex items-center justify-between gap-3 shrink-0 rounded-t-2xl">
        {/* Left: Agent Info & Switcher */}
        <div className="flex items-center gap-3 min-w-0">
          <AgentPixelAvatar role={activeAgent} size="md" isWorking={isAgentThinking} />
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="text-sm sm:text-base font-bold text-brand-headline tracking-tight truncate">
                {agentMeta.role} Command Center
              </h2>
              <AgentStatusBadge status={agentMeta.status} size="sm" />
            </div>
            <p className="text-[11px] text-brand-body truncate max-w-xs sm:max-w-md">
              {intakeData?.projectName || "Active Project"} • {agentMeta.description}
            </p>
          </div>
        </div>

        {/* Center: Agent Quick Switcher Tabs */}
        <div className="hidden md:flex items-center p-1 rounded-xl bg-brand-subtle/80 border border-brand-border text-xs">
          <button
            type="button"
            onClick={() => onSwitchAgent("ba")}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg font-medium transition-all cursor-pointer ${
              isBA
                ? "bg-brand-card text-brand-headline shadow-2xs font-bold"
                : "text-brand-body hover:text-brand-headline"
            }`}
          >
            <FileCheck className="w-3.5 h-3.5 text-blue-500" />
            <span>BA</span>
          </button>

          <button
            type="button"
            onClick={() => onSwitchAgent("pm")}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg font-medium transition-all cursor-pointer ${
              isPM
                ? "bg-brand-card text-brand-headline shadow-2xs font-bold"
                : "text-brand-body hover:text-brand-headline"
            }`}
          >
            <FileText className="w-3.5 h-3.5 text-purple-500" />
            <span>PM</span>
          </button>

          <button
            type="button"
            onClick={() => onSwitchAgent("architect")}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg font-medium transition-all cursor-pointer ${
              isArchitect
                ? "bg-brand-card text-brand-headline shadow-2xs font-bold"
                : "text-brand-body hover:text-brand-headline"
            }`}
          >
            <Cpu className="w-3.5 h-3.5 text-emerald-500" />
            <span>Architect</span>
          </button>

          <button
            type="button"
            onClick={() => onSwitchAgent("designer")}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg font-medium transition-all cursor-pointer ${
              isDesigner
                ? "bg-brand-card text-brand-headline shadow-2xs font-bold"
                : "text-brand-body hover:text-brand-headline"
            }`}
          >
            <Palette className="w-3.5 h-3.5 text-cyan-500" />
            <span>Designer</span>
          </button>
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-1.5 shrink-0">
          {/* Send to PM button if in BA mode and requirements are ready */}
          {isBA && readyForRequirements && (
            <button
              type="button"
              onClick={handleSendToPM}
              disabled={isHandoffRunning}
              className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-700 text-white text-xs font-semibold shadow-xs active:scale-95 transition-all cursor-pointer disabled:opacity-50"
              title="Hand off requirements to Product Manager"
            >
              {isHandoffRunning ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Starting PM...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Send to PM</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </>
              )}
            </button>
          )}

          <button
            type="button"
            onClick={() => setIsFullScreen(!isFullScreen)}
            className="p-2 text-brand-body hover:text-brand-headline hover:bg-brand-subtle rounded-lg transition-colors cursor-pointer"
            title={isFullScreen ? "Exit Fullscreen" : "Fullscreen"}
          >
            {isFullScreen ? (
              <Minimize2 className="w-4 h-4" />
            ) : (
              <Maximize2 className="w-4 h-4" />
            )}
          </button>

          <button
            type="button"
            onClick={onClose}
            className="p-2 text-brand-body hover:text-brand-headline hover:bg-brand-subtle rounded-lg transition-colors cursor-pointer"
            title="Close Command Center (Back to Floor)"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </header>

      {/* Main Split Command Area: Left Chat Thread, Right Work Output */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-0 overflow-hidden divide-y lg:divide-y-0 lg:divide-x divide-brand-border">
        {/* LEFT COLUMN: Agent Conversation Thread */}
        <section className="flex flex-col h-full overflow-hidden bg-brand-bg/50">
          {/* Thread Header */}
          <div className="px-4 py-2 border-b border-brand-border/60 bg-brand-card/40 flex items-center justify-between text-xs text-brand-body shrink-0">
            <span className="font-semibold text-brand-headline flex items-center gap-1.5">
              <span>Conversation Thread</span>
              <span className="text-[10px] font-mono bg-brand-subtle px-1.5 rounded border border-brand-border">
                {currentMessages.length} msgs
              </span>
            </span>
            <span className="text-[10px] font-mono text-brand-body/70">
              Llama 3.2 3B • Local
            </span>
          </div>

          {/* PM Not Started Banner in PM view */}
          {isPM && !pmStarted && (
            <div className="p-4 m-4 rounded-xl border border-purple-500/30 bg-purple-500/10 text-xs space-y-2">
              <div className="flex items-center gap-2 font-bold text-purple-700 dark:text-purple-300">
                <Sparkles className="w-4 h-4" />
                <span>Ready to start Product Manager</span>
              </div>
              <p className="text-[11px] text-brand-body leading-relaxed">
                The PM will read the Business Analyst's completed Q&A discovery log and structure your initial Product Requirement Document (PRD).
              </p>
              <button
                type="button"
                onClick={handleSendToPM}
                disabled={isHandoffRunning || !readyForRequirements}
                className="px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-700 text-white font-semibold flex items-center gap-2 shadow-xs transition-all cursor-pointer disabled:opacity-50"
              >
                {isHandoffRunning ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Analyzing BA Requirements & Drafting PRD...</span>
                  </>
                ) : (
                  <>
                    <span>Initialize PM & Draft PRD</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </>
                )}
              </button>
            </div>
          )}

          {/* PM Gate 1 Action Banner */}
          {isPM && prdContent && (
            <div className={`mx-4 mt-3 p-3.5 rounded-xl border text-xs space-y-2 ${
              gate1Approved
                ? "border-emerald-500/30 bg-emerald-500/10"
                : "border-purple-500/30 bg-purple-500/10"
            }`}>
              <div className="flex items-center justify-between">
                <span className={`font-bold flex items-center gap-1.5 ${
                  gate1Approved
                    ? "text-emerald-700 dark:text-emerald-300"
                    : "text-purple-700 dark:text-purple-300"
                }`}>
                  {gate1Approved ? <CheckCircle2 className="w-4 h-4 text-emerald-500" /> : <Sparkles className="w-4 h-4" />}
                  <span>{gate1Approved ? "Gate 1 Approved: Client PRD Sign-off Complete" : "Gate 1: Client PRD Sign-off"}</span>
                </span>
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold ${
                  gate1Approved
                    ? "bg-emerald-500/20 text-emerald-700 dark:text-emerald-300"
                    : "bg-purple-500/20 text-purple-700 dark:text-purple-300"
                }`}>
                  {gate1Approved ? "UNLOCKED" : "ACTION REQUIRED"}
                </span>
              </div>
              <p className="text-[11px] text-brand-body leading-relaxed">
                {gate1Approved
                  ? "PRD scope, non-goals, and assumptions are approved. Solution Architecture design (Stage 3) is unlocked."
                  : "Review the PRD, scope, non-goals, and assumptions. Approve to unlock Solution Architecture design, or request changes via the BA."}
              </p>
              {!gate1Approved && (
                <div className="flex items-center gap-2 pt-1">
                  <button
                    type="button"
                    onClick={() => approveGate1()}
                    disabled={isGate1Approving}
                    className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs shadow-xs transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                  >
                    {isGate1Approving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                    <span>Approve PRD at Gate 1</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      const feedback = prompt("What changes or clarifications are needed?");
                      if (feedback) requestGate1Changes(feedback);
                    }}
                    className="px-3 py-1.5 rounded-lg border border-brand-border bg-brand-card hover:bg-brand-subtle text-brand-headline font-medium text-xs transition-colors cursor-pointer"
                  >
                    Request Changes
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Architect Workstation Banner */}
          {isArchitect && !gate1Approved && (
            <div className="m-4 p-4 rounded-xl border border-amber-500/30 bg-amber-500/10 text-xs space-y-2">
              <div className="flex items-center gap-2 font-bold text-amber-700 dark:text-amber-300">
                <Lock className="w-4 h-4" />
                <span>Stage 3 Locked: Gate 1 Client Approval Required</span>
              </div>
              <p className="text-[11px] text-brand-body leading-relaxed">
                Handbook rule: The client must approve the PRD, scope, non-goals, and assumptions at Gate 1 before the Solution Architect can start the technical design.
              </p>
              <button
                type="button"
                onClick={() => onSwitchAgent("pm")}
                className="px-3.5 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-semibold text-xs transition-all flex items-center gap-1.5 cursor-pointer"
              >
                <span>Open PM View to Review Gate 1</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {isArchitect && gate1Approved && !architectureContent && (
            <div className="m-4 p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-xs space-y-2">
              <div className="flex items-center gap-2 font-bold text-emerald-700 dark:text-emerald-300">
                <Sparkles className="w-4 h-4" />
                <span>Gate 1 Approved: Ready for Solution Architecture</span>
              </div>
              <p className="text-[11px] text-brand-body leading-relaxed">
                The PRD is signed off. The Architect will generate the Technical Requirements Document (TRD), ADRs, OpenAPI 3.0 contract, SQLite schema with DDL, and run code-level validators.
              </p>
              <button
                type="button"
                onClick={() => generateArchitectArtifacts()}
                disabled={isArchitectGenerating}
                className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs shadow-xs transition-all flex items-center gap-2 cursor-pointer disabled:opacity-50"
              >
                {isArchitectGenerating ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Designing Architecture & Running Validators...</span>
                  </>
                ) : (
                  <>
                    <Cpu className="w-3.5 h-3.5" />
                    <span>Generate Architecture Blueprints (Stage 3)</span>
                  </>
                )}
              </button>
            </div>
          )}

          {/* Designer Workstation Banner */}
          {isDesigner && !gate1Approved && (
            <div className="m-4 p-4 rounded-xl border border-amber-500/30 bg-amber-500/10 text-xs space-y-2">
              <div className="flex items-center gap-2 font-bold text-amber-700 dark:text-amber-300">
                <Lock className="w-4 h-4" />
                <span>Stage 3 Locked: Gate 1 Client Approval Required</span>
              </div>
              <p className="text-[11px] text-brand-body leading-relaxed">
                Handbook rule: The client must approve the PRD, scope, non-goals, and assumptions at Gate 1 before the UI/UX Designer can begin app flows and design briefs.
              </p>
              <button
                type="button"
                onClick={() => onSwitchAgent("pm")}
                className="px-3.5 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-semibold text-xs transition-all flex items-center gap-1.5 cursor-pointer"
              >
                <span>Open PM View to Review Gate 1</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {isDesigner && gate1Approved && !appFlowContent && (
            <div className="m-4 p-4 rounded-xl border border-cyan-500/30 bg-cyan-500/10 text-xs space-y-2">
              <div className="flex items-center gap-2 font-bold text-cyan-700 dark:text-cyan-300">
                <Sparkles className="w-4 h-4" />
                <span>Gate 1 Approved: Ready for UI/UX Design</span>
              </div>
              <p className="text-[11px] text-brand-body leading-relaxed">
                The PRD is signed off. The Designer will synthesize user journeys into screen state diagrams, comprehensive app flow (Appendix A.4), WCAG 2.2 AA design brief (Appendix A.5), and automated code validators.
              </p>
              <button
                type="button"
                onClick={() => generateDesignerArtifacts()}
                disabled={isDesignerGenerating}
                className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-xs shadow-xs transition-all flex items-center gap-2 cursor-pointer disabled:opacity-50"
              >
                {isDesignerGenerating ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Synthesizing Flows & Calculating WCAG Tokens...</span>
                  </>
                ) : (
                  <>
                    <Palette className="w-3.5 h-3.5" />
                    <span>Generate UI/UX Blueprints (Stage 3)</span>
                  </>
                )}
              </button>
            </div>
          )}

          {/* Error Banner */}
          {pmError && isPM && (
            <div className="m-4 p-3 rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300 text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{pmError}</span>
            </div>
          )}

          {/* Messages Stream */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {currentMessages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 text-brand-body">
                <Briefcase className="w-8 h-8 opacity-30 mb-2" />
                <p className="text-xs font-semibold text-brand-headline">
                  {isArchitect
                    ? "Solution Architecture Command Center"
                    : isDesigner
                    ? "UI/UX Design Studio Command Center"
                    : `No messages yet with ${agentMeta.role}`}
                </p>
                <p className="text-[11px] mt-1 max-w-xs">
                  {isArchitect
                    ? architectureContent
                      ? "Architecture blueprints and API contracts generated. Review documents in the right pane."
                      : "Gate 1 approved. Click 'Generate Architecture Blueprints' above to produce technical designs."
                    : isDesigner
                    ? appFlowContent
                      ? "App flows and design brief generated. Review documents and WCAG contrast audit in the right pane."
                      : "Gate 1 approved. Click 'Generate UI/UX Blueprints' above to produce user journeys and design brief."
                    : isPM
                    ? "Click 'Initialize PM & Draft PRD' or ask a question to begin."
                    : "Type a response below to talk with your Business Analyst."}
                </p>
              </div>
            ) : (
              currentMessages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))
            )}

            {/* In-stream typing indicator */}
            {isAgentThinking && (
              <div className="flex items-start">
                <div className="rounded-2xl rounded-tl-sm bg-brand-card border border-brand-border px-4 py-3 shadow-card">
                  <div className="flex items-center gap-2 text-xs text-brand-headline font-medium">
                    <span className="font-bold text-brand-accent flex items-center gap-1">
                      {agentMeta.role}
                    </span>
                    <span className="text-brand-body text-[11px]">• Generating response</span>
                    <TypingDots />
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Chat Input Box */}
          <form
            onSubmit={handleSendMessage}
            className="p-3 border-t border-brand-border bg-brand-card shrink-0"
          >
            <div className="relative flex items-center rounded-xl bg-brand-bg border border-brand-border focus-within:border-brand-accent transition-colors shadow-inner px-3 py-2">
              <textarea
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSendMessage();
                  }
                }}
                disabled={isAgentThinking || (isPM && !pmStarted) || ((isArchitect || isDesigner) && !gate1Approved)}
                placeholder={
                  (isArchitect || isDesigner) && !gate1Approved
                    ? "Approve Gate 1 before sending messages to Stage 3 agents..."
                    : isPM && !pmStarted
                    ? "Initialize PM first to start conversation..."
                    : `Message ${agentMeta.role}... (Enter to send, Shift+Enter for newline)`
                }
                rows={1}
                className="w-full bg-transparent border-none text-xs text-brand-headline placeholder:text-brand-body/50 focus:outline-none resize-none leading-relaxed"
              />

              <button
                type="submit"
                disabled={
                  isAgentThinking ||
                  !inputMessage.trim() ||
                  (isPM && !pmStarted) ||
                  ((isArchitect || isDesigner) && !gate1Approved)
                }
                className="ml-2 p-2 rounded-lg bg-brand-accent hover:bg-brand-accent-hover text-brand-accent-text transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
                title="Send Message"
              >
                {isAgentThinking ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Send className="w-3.5 h-3.5" />
                )}
              </button>
            </div>
          </form>
        </section>

        {/* RIGHT COLUMN: Agent Work Output */}
        <section className="flex flex-col h-full overflow-hidden p-3 sm:p-4 bg-brand-card/30">
          {isBA ? (
            <BAOutputViewer
              requirementsContent={requirementsContent}
              qaLog={qaLog}
              projectName={intakeData?.projectName}
              readyForRequirements={readyForRequirements}
              onSendToPM={handleSendToPM}
              isSendingToPM={isHandoffRunning}
            />
          ) : isPM ? (
            <PRDViewer
              content={prdContent}
              projectName={intakeData?.projectName}
              isUpdating={isPmSending}
              estimateData={estimateData}
            />
          ) : isArchitect ? (
            <ArchitectOutputViewer
              architectureContent={architectureContent || ""}
              schemaContent={schemaContent || ""}
              openapiContent={openapiContent || ""}
              validationResults={architectState?.validation}
              judgeVerdict={architectState?.judge_verdict}
              projectName={intakeData?.projectName}
              isGenerating={isArchitectGenerating}
              onGenerate={() => generateArchitectArtifacts()}
              canStart={gate1Approved && !architectureContent}
            />
          ) : isDesigner ? (
            <DesignerOutputViewer
              appFlowContent={appFlowContent || ""}
              designBriefContent={designBriefContent || ""}
              validationResults={designerState?.validation || designerState?.validation_results}
              judgeVerdict={designerState?.judge_verdict}
              projectName={intakeData?.projectName}
              isGenerating={isDesignerGenerating}
              onGenerate={() => generateDesignerArtifacts()}
              canStart={gate1Approved && !appFlowContent}
            />
          ) : (
            <div className="h-full flex flex-col items-center justify-center p-8 text-center bg-brand-card rounded-2xl border border-brand-border">
              <Layers className="w-8 h-8 text-brand-body/40 mb-2" />
              <h3 className="text-sm font-bold text-brand-headline">
                {agentMeta.outputTitle}
              </h3>
              <p className="text-xs text-brand-body mt-1 max-w-sm">
                This agent workstation will unlock in the next pipeline phase once the architecture is verified.
              </p>
            </div>
          )}
        </section>
      </div>
    </motion.div>
  );
};

export default CommandCenter;

