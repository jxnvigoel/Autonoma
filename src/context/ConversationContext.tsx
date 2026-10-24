import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";
import {
  ChatMessage,
  IntakeFormData,
  BASessionSummary,
  OfficeStatusResponse,
  PMEstimateData,
  Gate1State,
  Gate2State,
  TeamPlanData,
  AgentProfile,
  BudgetGuardStatus,
  startBaSession,
  sendBaMessage,
  getBaRequirements,
  getBaSessions,
  getBaSession,
  startPmSession,
  sendPmMessage,
  getPmSession,
  getOfficeStatus,
  apiApproveGate1,
  apiRequestGate1Changes,
  apiGetArchitectSession,
  apiGenerateArchitectArtifacts,
  apiGetDesignerSession,
  apiGenerateDesignerArtifacts,
  apiRunFeasibility,
  apiRunHrPlan,
  apiGetHrTeamPlan,
  apiRunRecruiterHire,
  apiGetRecruiterAgents,
  apiGetRecruiterReport,
  apiGetGate2Status,
  apiApproveGate2,
  apiRequestGate2Changes,
  apiGetBudgetStatus,
  clearConversation as apiClearConversation,
  sendChatMessage as apiSendChatMessage,
} from "../lib/engine";



export interface QALogEntry {
  id: string;
  question: string;
  answer: string;
  round: number;
  timestamp: string;
}

interface ConversationContextType {
  sessionId: string | null;
  intakeData: IntakeFormData | null;
  messages: ChatMessage[];
  qaLog: QALogEntry[];
  sessions: BASessionSummary[];
  isLoadingSessions: boolean;
  isLoadingSession: boolean;
  isLoading: boolean;
  isSending: boolean;
  error: string | null;
  readyForRequirements: boolean;
  requirementsContent: string | null;
  isFetchingRequirements: boolean;

  // PM Agent State
  pmMessages: ChatMessage[];
  prdContent: string | null;
  estimateData: PMEstimateData | null;
  pmStarted: boolean;
  isPmSending: boolean;
  pmError: string | null;

  // Architect Agent & Gate 1 State
  architectureContent: string | null;
  schemaContent: string | null;
  openapiContent: string | null;
  architectState: any | null;
  gate1State: Gate1State | null;
  isArchitectGenerating: boolean;
  isGate1Approving: boolean;

  // Designer Agent State
  appFlowContent: string | null;
  designBriefContent: string | null;
  designerState: any | null;
  isDesignerGenerating: boolean;

  // Stage 4 HR & Recruiter & Gate 2 State
  teamPlanData: TeamPlanData | null;
  staffingReportContent: string | null;
  hiredAgents: AgentProfile[];
  gate2State: Gate2State | null;
  budgetGuard: BudgetGuardStatus | null;
  isHrGenerating: boolean;
  isRecruiterGenerating: boolean;
  isGate2Approving: boolean;

  // Virtual Office State
  officeStatus: OfficeStatusResponse | null;
  activeOfficeAgent: "ba" | "pm" | "architect" | "designer" | "hr" | "recruiter" | "engineer" | "qa" | null;
  setActiveOfficeAgent: (agent: "ba" | "pm" | "architect" | "designer" | "hr" | "recruiter" | "engineer" | "qa" | null) => void;
  refreshOfficeStatus: (targetSessionId?: string) => Promise<void>;


  // Actions
  startSession: (intake: IntakeFormData) => Promise<string>;
  selectSession: (sessionId: string) => Promise<void>;
  refreshSessions: () => Promise<void>;
  sendMessage: (
    prompt: string,
    fileContext?: { path: string; content: string }
  ) => Promise<void>;
  fetchRequirements: () => Promise<string | null>;
  startPm: (targetSessionId?: string) => Promise<void>;
  sendPm: (prompt: string) => Promise<void>;
  fetchPmSession: (targetSessionId?: string) => Promise<void>;
  fetchArchitectSession: (targetSessionId?: string) => Promise<void>;
  generateArchitectArtifacts: (targetSessionId?: string) => Promise<void>;
  fetchDesignerSession: (targetSessionId?: string) => Promise<void>;
  generateDesignerArtifacts: (targetSessionId?: string) => Promise<void>;
  approveGate1: (notes?: string) => Promise<void>;
  requestGate1Changes: (feedback: string) => Promise<void>;
  runFeasibility: () => Promise<void>;
  fetchStage4Session: (targetSessionId?: string) => Promise<void>;
  generateHrPlan: (targetSessionId?: string) => Promise<void>;
  executeRecruiterHiring: (targetSessionId?: string) => Promise<void>;
  approveGate2: (notes?: string) => Promise<void>;
  requestGate2Changes: (feedback: string) => Promise<void>;
  newSession: () => void;

  clearHistory: () => Promise<void>;
  refreshHistory: () => Promise<void>;
  setError: (err: string | null) => void;
  setPmError: (err: string | null) => void;
}

const ConversationContext = createContext<ConversationContextType | undefined>(
  undefined
);

export const ConversationProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [intakeData, setIntakeData] = useState<IntakeFormData | null>(null);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [qaLog, setQaLog] = useState<QALogEntry[]>([]);
  const [sessions, setSessions] = useState<BASessionSummary[]>([]);
  const [isLoadingSessions, setIsLoadingSessions] = useState<boolean>(false);
  const [isLoadingSession, setIsLoadingSession] = useState<boolean>(false);
  const [isSending, setIsSending] = useState<boolean>(false);
  const isLoading = isLoadingSessions || isLoadingSession || isSending;
  const [error, setError] = useState<string | null>(null);
  const [readyForRequirements, setReadyForRequirements] =
    useState<boolean>(false);
  const [requirementsContent, setRequirementsContent] = useState<string | null>(
    null
  );
  const [isFetchingRequirements, setIsFetchingRequirements] =
    useState<boolean>(false);

  // PM Agent State
  const [pmMessages, setPmMessages] = useState<ChatMessage[]>([]);
  const [prdContent, setPrdContent] = useState<string | null>(null);
  const [estimateData, setEstimateData] = useState<PMEstimateData | null>(null);
  const [pmStarted, setPmStarted] = useState<boolean>(false);
  const [isPmSending, setIsPmSending] = useState<boolean>(false);
  const [pmError, setPmError] = useState<string | null>(null);

  // Architect Agent & Gate 1 State
  const [architectureContent, setArchitectureContent] = useState<string | null>(null);
  const [schemaContent, setSchemaContent] = useState<string | null>(null);
  const [openapiContent, setOpenapiContent] = useState<string | null>(null);
  const [architectState, setArchitectState] = useState<any | null>(null);
  const [gate1State, setGate1State] = useState<Gate1State | null>(null);
  const [isArchitectGenerating, setIsArchitectGenerating] = useState<boolean>(false);
  const [isGate1Approving, setIsGate1Approving] = useState<boolean>(false);

  // Designer Agent State
  const [appFlowContent, setAppFlowContent] = useState<string | null>(null);
  const [designBriefContent, setDesignBriefContent] = useState<string | null>(null);
  const [designerState, setDesignerState] = useState<any | null>(null);
  const [isDesignerGenerating, setIsDesignerGenerating] = useState<boolean>(false);

  // Stage 4 HR & Recruiter & Gate 2 State
  const [teamPlanData, setTeamPlanData] = useState<TeamPlanData | null>(null);
  const [staffingReportContent, setStaffingReportContent] = useState<string | null>(null);
  const [hiredAgents, setHiredAgents] = useState<AgentProfile[]>([]);
  const [gate2State, setGate2State] = useState<Gate2State | null>(null);
  const [budgetGuard, setBudgetGuard] = useState<BudgetGuardStatus | null>(null);
  const [isHrGenerating, setIsHrGenerating] = useState<boolean>(false);
  const [isRecruiterGenerating, setIsRecruiterGenerating] = useState<boolean>(false);
  const [isGate2Approving, setIsGate2Approving] = useState<boolean>(false);

  // Virtual Office State
  const [officeStatus, setOfficeStatus] = useState<OfficeStatusResponse | null>(null);
  const [activeOfficeAgent, setActiveOfficeAgent] = useState<
    "ba" | "pm" | "architect" | "designer" | "hr" | "recruiter" | "engineer" | "qa" | null
  >(null);


  const refreshSessions = useCallback(async () => {
    setIsLoadingSessions(true);
    try {
      const list = await getBaSessions();
      setSessions(list);
    } catch {
      // Backend offline or starting
    } finally {
      setIsLoadingSessions(false);
    }
  }, []);

  const refreshOfficeStatus = useCallback(
    async (targetSessionId?: string) => {
      const target = targetSessionId || sessionId;
      if (!target) return;
      try {
        const data = await getOfficeStatus(target);
        setOfficeStatus(data);
      } catch {
        // Silently catch if not yet available
      }
    },
    [sessionId]
  );

  const fetchPmSession = useCallback(
    async (targetSessionId?: string) => {
      const target = targetSessionId || sessionId;
      if (!target) return;
      try {
        const pmData = await getPmSession(target);
        setPmStarted(pmData.started);
        setPmMessages(pmData.messages || []);
        setPrdContent(pmData.prd_content || null);
        setEstimateData(pmData.estimate || null);
      } catch {
        setPmStarted(false);
        setPmMessages([]);
        setPrdContent(null);
        setEstimateData(null);
      }
    },
    [sessionId]
  );

  const fetchArchitectSession = useCallback(
    async (targetSessionId?: string) => {
      const target = targetSessionId || sessionId;
      if (!target) return;
      try {
        const data = await apiGetArchitectSession(target);
        setArchitectureContent(data.architecture_content || null);
        setSchemaContent(data.schema_content || null);
        setOpenapiContent(data.openapi_content || null);
        setArchitectState(data.state || null);
      } catch {
        setArchitectureContent(null);
        setSchemaContent(null);
        setOpenapiContent(null);
        setArchitectState(null);
      }
    },
    [sessionId]
  );

  const fetchDesignerSession = useCallback(
    async (targetSessionId?: string) => {
      const target = targetSessionId || sessionId;
      if (!target) return;
      try {
        const data = await apiGetDesignerSession(target);
        setAppFlowContent(data.app_flow_content || null);
        setDesignBriefContent(data.design_brief_content || null);
        setDesignerState(data.state || null);
      } catch {
        setAppFlowContent(null);
        setDesignBriefContent(null);
        setDesignerState(null);
      }
    },
    [sessionId]
  );

  const fetchStage4Session = useCallback(
    async (targetSessionId?: string) => {
      const target = targetSessionId || sessionId;
      if (!target) return;
      try {
        const [planRes, reportRes, agentsRes, gate2Res, budgetRes] = await Promise.allSettled([
          apiGetHrTeamPlan(target),
          apiGetRecruiterReport(target),
          apiGetRecruiterAgents(target),
          apiGetGate2Status(target),
          apiGetBudgetStatus(target),
        ]);
        if (planRes.status === "fulfilled") setTeamPlanData(planRes.value);
        else setTeamPlanData(null);

        if (reportRes.status === "fulfilled") setStaffingReportContent(reportRes.value.content);
        else setStaffingReportContent(null);

        if (agentsRes.status === "fulfilled") setHiredAgents(agentsRes.value.agents || []);
        else setHiredAgents([]);

        if (gate2Res.status === "fulfilled") setGate2State(gate2Res.value);
        else setGate2State(null);

        if (budgetRes.status === "fulfilled") setBudgetGuard(budgetRes.value.guard);
        else setBudgetGuard(null);
      } catch {
        // Silently catch
      }
    },
    [sessionId]
  );

  const selectSession = useCallback(

    async (targetSessionId: string) => {
      if (!targetSessionId) return;
      setIsLoadingSession(true);
      setError(null);
      setPmError(null);

      // Reset previous messages, qaLog, and requirements immediately
      setMessages([]);
      setQaLog([]);
      setReadyForRequirements(false);
      setRequirementsContent(null);
      setPmMessages([]);
      setPrdContent(null);
      setEstimateData(null);
      setPmStarted(false);
      setTeamPlanData(null);
      setStaffingReportContent(null);
      setHiredAgents([]);
      setGate2State(null);
      setBudgetGuard(null);

      try {
        const data = await getBaSession(targetSessionId);
        setSessionId(data.session_id);
        setIntakeData({
          projectName: data.intake.project_name || "Project",
          description: data.intake.description || "",
          targetUsers: data.intake.target_users || "",
          timeline: data.intake.timeline || "",
          budget: data.intake.budget || "",
        });
        setMessages(data.messages || []);
        setQaLog(data.qa_log || []);
        setReadyForRequirements(
          data.ready_for_requirements || data.has_requirements
        );
        setRequirementsContent(data.requirements_content || null);

        // Fetch PM session and Office status concurrently
        try {
          const pmData = await getPmSession(targetSessionId);
          setPmStarted(pmData.started);
          setPmMessages(pmData.messages || []);
          setPrdContent(pmData.prd_content || null);
          setEstimateData(pmData.estimate || null);
        } catch {
          setPmStarted(false);
          setEstimateData(null);
        }

        try {
          const officeData = await getOfficeStatus(targetSessionId);
          setOfficeStatus(officeData);
        } catch {
          // Ignore
        }

        await fetchArchitectSession(targetSessionId);
        await fetchDesignerSession(targetSessionId);
        await fetchStage4Session(targetSessionId);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
      } finally {
        setIsLoadingSession(false);
      }
    },
    [fetchArchitectSession, fetchDesignerSession, fetchStage4Session]
  );


  // Initial load of sessions list on startup
  useEffect(() => {
    try {
      localStorage.removeItem("autonoma_ba_session_id");
      localStorage.removeItem("autonoma_ba_intake");
    } catch {
      // Ignore
    }
    refreshSessions();
  }, [refreshSessions]);

  const startSession = useCallback(
    async (intake: IntakeFormData): Promise<string> => {
      // Immediately reset all session state
      setSessionId(null);
      setIntakeData(null);
      setMessages([]);
      setQaLog([]);
      setReadyForRequirements(false);
      setRequirementsContent(null);
      setPmMessages([]);
      setPrdContent(null);
      setPmStarted(false);
      setOfficeStatus(null);

      setIsSending(true);
      setError(null);

      try {
        const res = await startBaSession(intake);
        setSessionId(res.session_id);
        setIntakeData(intake);

        const assistantMsg: ChatMessage = {
          id: crypto.randomUUID(),
          role: "assistant",
          content: res.message,
          timestamp: new Date().toISOString(),
        };
        setMessages([assistantMsg]);
        refreshSessions();
        refreshOfficeStatus(res.session_id);
        return res.session_id;
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
        throw err;
      } finally {
        setIsSending(false);
      }
    },
    [refreshSessions, refreshOfficeStatus]
  );

  const fetchRequirements = useCallback(async (): Promise<string | null> => {
    if (!sessionId) return null;
    setIsFetchingRequirements(true);
    try {
      const data = await getBaRequirements(sessionId);
      setRequirementsContent(data.content);
      return data.content;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      return null;
    } finally {
      setIsFetchingRequirements(false);
    }
  }, [sessionId]);

  const sendMessage = useCallback(
    async (
      prompt: string,
      fileContext?: { path: string; content: string }
    ) => {
      const trimmed = prompt.trim();
      if (!trimmed || isSending) return;

      let payloadPrompt = trimmed;
      if (fileContext && fileContext.path) {
        payloadPrompt = `Current file: ${fileContext.path}\n\n${fileContext.content}\n\n---\nUser: ${trimmed}`;
      }

      const tempUserMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: payloadPrompt,
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, tempUserMsg]);
      setIsSending(true);
      setError(null);

      try {
        if (sessionId) {
          // Route to BA message endpoint
          const res = await sendBaMessage(sessionId, payloadPrompt);
          const assistantMsg: ChatMessage = {
            id: crypto.randomUUID(),
            role: "assistant",
            content: res.message,
            timestamp: new Date().toISOString(),
          };
          setMessages((prev) => [...prev, assistantMsg]);

          if (res.ready_for_requirements) {
            setReadyForRequirements(true);
            try {
              const reqData = await getBaRequirements(sessionId);
              setRequirementsContent(reqData.content);
            } catch {
              // May still be writing
            }
          }

          // Update full session detail to keep qaLog in sync
          try {
            const freshSession = await getBaSession(sessionId);
            setQaLog(freshSession.qa_log || []);
          } catch {
            // Ignore
          }

          refreshSessions();
          refreshOfficeStatus(sessionId);
        } else {
          // Generic chat fallback
          const data = await apiSendChatMessage(payloadPrompt);
          const assistantMsg: ChatMessage = {
            id: crypto.randomUUID(),
            role: "assistant",
            content: data.response,
            timestamp: new Date().toISOString(),
            meta: {
              duration: data.duration,
              token_count: data.token_count,
            },
          };
          setMessages((prev) => [...prev, assistantMsg]);
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
        throw err;
      } finally {
        setIsSending(false);
      }
    },
    [sessionId, isSending, refreshSessions, refreshOfficeStatus]
  );

  const startPm = useCallback(
    async (targetSessionId?: string) => {
      const target = targetSessionId || sessionId;
      if (!target) {
        throw new Error("No active session to start PM");
      }

      setIsPmSending(true);
      setPmError(null);

      try {
        const res = await startPmSession(target);
        setPmStarted(true);
        setPrdContent(res.prd_content);
        if (res.estimate) {
          setEstimateData(res.estimate);
        }

        const pmMsg: ChatMessage = {
          id: crypto.randomUUID(),
          role: "assistant",
          content: res.message,
          timestamp: new Date().toISOString(),
        };
        setPmMessages([pmMsg]);

        // Refresh office status and session list
        refreshOfficeStatus(target);
        refreshSessions();
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        setPmError(msg);
        throw err;
      } finally {
        setIsPmSending(false);
      }
    },
    [sessionId, refreshOfficeStatus, refreshSessions]
  );

  const sendPm = useCallback(
    async (prompt: string) => {
      const trimmed = prompt.trim();
      if (!trimmed || isPmSending || !sessionId) return;

      const tempUserMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: trimmed,
        timestamp: new Date().toISOString(),
      };

      setPmMessages((prev) => [...prev, tempUserMsg]);
      setIsPmSending(true);
      setPmError(null);

      try {
        const res = await sendPmMessage(sessionId, trimmed);
        const assistantMsg: ChatMessage = {
          id: crypto.randomUUID(),
          role: "assistant",
          content: res.message,
          timestamp: new Date().toISOString(),
        };
        setPmMessages((prev) => [...prev, assistantMsg]);
        if (res.prd_content) {
          setPrdContent(res.prd_content);
        }
        if (res.estimate) {
          setEstimateData(res.estimate);
        }
        refreshOfficeStatus(sessionId);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        setPmError(msg);
        throw err;
      } finally {
        setIsPmSending(false);
      }
    },
    [sessionId, isPmSending, refreshOfficeStatus]
  );

  const generateArchitectArtifacts = useCallback(
    async (targetSessionId?: string) => {
      const target = targetSessionId || sessionId;
      if (!target) return;
      setIsArchitectGenerating(true);
      try {
        const data = await apiGenerateArchitectArtifacts(target);
        setArchitectState(data);
        await fetchArchitectSession(target);
        await refreshOfficeStatus(target);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
      } finally {
        setIsArchitectGenerating(false);
      }
    },
    [sessionId, fetchArchitectSession, refreshOfficeStatus]
  );

  const generateDesignerArtifacts = useCallback(
    async (targetSessionId?: string) => {
      const target = targetSessionId || sessionId;
      if (!target) return;
      setIsDesignerGenerating(true);
      try {
        const data = await apiGenerateDesignerArtifacts(target);
        setDesignerState(data);
        await fetchDesignerSession(target);
        await refreshOfficeStatus(target);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
      } finally {
        setIsDesignerGenerating(false);
      }
    },
    [sessionId, fetchDesignerSession, refreshOfficeStatus]
  );

  const approveGate1 = useCallback(
    async (notes?: string) => {
      if (!sessionId) return;
      setIsGate1Approving(true);
      try {
        await apiApproveGate1(sessionId, notes);
        await refreshOfficeStatus(sessionId);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
      } finally {
        setIsGate1Approving(false);
      }
    },
    [sessionId, refreshOfficeStatus]
  );

  const requestGate1Changes = useCallback(
    async (feedback: string) => {
      if (!sessionId) return;
      try {
        await apiRequestGate1Changes(sessionId, feedback);
        await refreshOfficeStatus(sessionId);
        await selectSession(sessionId);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
      }
    },
    [sessionId, refreshOfficeStatus, selectSession]
  );

  const runFeasibility = useCallback(
    async () => {
      if (!sessionId) return;
      try {
        await apiRunFeasibility(sessionId);
        await refreshOfficeStatus(sessionId);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
      }
    },
    [sessionId, refreshOfficeStatus]
  );

  const generateHrPlan = useCallback(
    async (targetSessionId?: string) => {
      const target = targetSessionId || sessionId;
      if (!target) return;
      setIsHrGenerating(true);
      setError(null);
      try {
        const plan = await apiRunHrPlan(target);
        setTeamPlanData(plan);
        await refreshOfficeStatus(target);
        await fetchStage4Session(target);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
        throw err;
      } finally {
        setIsHrGenerating(false);
      }
    },
    [sessionId, refreshOfficeStatus, fetchStage4Session]
  );

  const executeRecruiterHiring = useCallback(
    async (targetSessionId?: string) => {
      const target = targetSessionId || sessionId;
      if (!target) return;
      setIsRecruiterGenerating(true);
      setError(null);
      try {
        await apiRunRecruiterHire(target);
        await refreshOfficeStatus(target);
        await fetchStage4Session(target);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
        throw err;
      } finally {
        setIsRecruiterGenerating(false);
      }
    },
    [sessionId, refreshOfficeStatus, fetchStage4Session]
  );

  const approveGate2 = useCallback(
    async (notes?: string) => {
      if (!sessionId) return;
      setIsGate2Approving(true);
      try {
        await apiApproveGate2(sessionId, notes);
        await refreshOfficeStatus(sessionId);
        await fetchStage4Session(sessionId);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
      } finally {
        setIsGate2Approving(false);
      }
    },
    [sessionId, refreshOfficeStatus, fetchStage4Session]
  );

  const requestGate2Changes = useCallback(
    async (feedback: string) => {
      if (!sessionId) return;
      setIsGate2Approving(true);
      try {
        await apiRequestGate2Changes(sessionId, feedback);
        await refreshOfficeStatus(sessionId);
        await fetchStage4Session(sessionId);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
      } finally {
        setIsGate2Approving(false);
      }
    },
    [sessionId, refreshOfficeStatus, fetchStage4Session]
  );

  const newSession = useCallback(() => {
    setSessionId(null);
    setIntakeData(null);
    setMessages([]);
    setQaLog([]);
    setReadyForRequirements(false);
    setRequirementsContent(null);
    setPmMessages([]);
    setPrdContent(null);
    setEstimateData(null);
    setPmStarted(false);
    setArchitectureContent(null);
    setSchemaContent(null);
    setOpenapiContent(null);
    setArchitectState(null);
    setAppFlowContent(null);
    setDesignBriefContent(null);
    setDesignerState(null);
    setGate1State(null);
    setTeamPlanData(null);
    setStaffingReportContent(null);
    setHiredAgents([]);
    setGate2State(null);
    setBudgetGuard(null);
    setOfficeStatus(null);
    setActiveOfficeAgent(null);
    setError(null);
    setPmError(null);
    refreshSessions();
  }, [refreshSessions]);

  const clearHistory = useCallback(async () => {
    try {
      if (!sessionId) {
        await apiClearConversation();
      }
      setMessages([]);
      setError(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    }
  }, [sessionId]);

  const refreshHistory = useCallback(async () => {
    await refreshSessions();
  }, [refreshSessions]);

  return (
    <ConversationContext.Provider
      value={{
        sessionId,
        intakeData,
        messages,
        qaLog,
        sessions,
        isLoadingSessions,
        isLoadingSession,
        isLoading,
        isSending,
        error,
        readyForRequirements,
        requirementsContent,
        isFetchingRequirements,
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
        teamPlanData,
        staffingReportContent,
        hiredAgents,
        gate2State,
        budgetGuard,
        isHrGenerating,
        isRecruiterGenerating,
        isGate2Approving,
        officeStatus,
        activeOfficeAgent,
        setActiveOfficeAgent,
        refreshOfficeStatus,
        startSession,
        selectSession,
        refreshSessions,
        sendMessage,
        fetchRequirements,
        startPm,
        sendPm,
        fetchPmSession,
        fetchArchitectSession,
        generateArchitectArtifacts,
        fetchDesignerSession,
        generateDesignerArtifacts,
        approveGate1,
        requestGate1Changes,
        runFeasibility,
        fetchStage4Session,
        generateHrPlan,
        executeRecruiterHiring,
        approveGate2,
        requestGate2Changes,
        newSession,
        clearHistory,
        refreshHistory,
        setError,
        setPmError,
      }}
    >
      {children}
    </ConversationContext.Provider>
  );

};

export const useConversation = (): ConversationContextType => {
  const context = useContext(ConversationContext);
  if (!context) {
    throw new Error(
      "useConversation must be used within a ConversationProvider"
    );
  }
  return context;
};

export default ConversationContext;
