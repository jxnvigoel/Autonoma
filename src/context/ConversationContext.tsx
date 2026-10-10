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
  startBaSession,
  sendBaMessage,
  getBaRequirements,
  getBaSessions,
  getBaSession,
  startPmSession,
  sendPmMessage,
  getPmSession,
  getOfficeStatus,
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
  pmStarted: boolean;
  isPmSending: boolean;
  pmError: string | null;

  // Virtual Office State
  officeStatus: OfficeStatusResponse | null;
  activeOfficeAgent: "ba" | "pm" | "architect" | "engineer" | "qa" | null;
  setActiveOfficeAgent: (agent: "ba" | "pm" | "architect" | "engineer" | "qa" | null) => void;
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
  const [pmStarted, setPmStarted] = useState<boolean>(false);
  const [isPmSending, setIsPmSending] = useState<boolean>(false);
  const [pmError, setPmError] = useState<string | null>(null);

  // Virtual Office State
  const [officeStatus, setOfficeStatus] = useState<OfficeStatusResponse | null>(null);
  const [activeOfficeAgent, setActiveOfficeAgent] = useState<
    "ba" | "pm" | "architect" | "engineer" | "qa" | null
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
      } catch {
        setPmStarted(false);
        setPmMessages([]);
        setPrdContent(null);
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
      setPmStarted(false);

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
        } catch {
          setPmStarted(false);
        }

        try {
          const officeData = await getOfficeStatus(targetSessionId);
          setOfficeStatus(officeData);
        } catch {
          // Ignore
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
      } finally {
        setIsLoadingSession(false);
      }
    },
    []
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

  const newSession = useCallback(() => {
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
        pmStarted,
        isPmSending,
        pmError,
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
