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
  startBaSession,
  sendBaMessage,
  getBaRequirements,
  getBaSessions,
  getBaSession,
  clearConversation as apiClearConversation,
  sendChatMessage as apiSendChatMessage,
} from "../lib/engine";

interface ConversationContextType {
  sessionId: string | null;
  intakeData: IntakeFormData | null;
  messages: ChatMessage[];
  sessions: BASessionSummary[];
  isLoadingSessions: boolean;
  isLoadingSession: boolean;
  isLoading: boolean;
  isSending: boolean;
  error: string | null;
  readyForRequirements: boolean;
  requirementsContent: string | null;
  isFetchingRequirements: boolean;
  startSession: (intake: IntakeFormData) => Promise<void>;
  selectSession: (sessionId: string) => Promise<void>;
  refreshSessions: () => Promise<void>;
  sendMessage: (
    prompt: string,
    fileContext?: { path: string; content: string }
  ) => Promise<void>;
  fetchRequirements: () => Promise<string | null>;
  newSession: () => void;
  clearHistory: () => Promise<void>;
  refreshHistory: () => Promise<void>;
  setError: (err: string | null) => void;
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

  const selectSession = useCallback(async (targetSessionId: string) => {
    if (!targetSessionId) return;
    setIsLoadingSession(true);
    setError(null);
    // Reset previous messages and requirements immediately
    setMessages([]);
    setReadyForRequirements(false);
    setRequirementsContent(null);

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
      setReadyForRequirements(data.ready_for_requirements || data.has_requirements);
      setRequirementsContent(data.requirements_content || null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    } finally {
      setIsLoadingSession(false);
    }
  }, []);

  // Initial load of sessions list on startup
  useEffect(() => {
    try {
      localStorage.removeItem("autonoma_ba_session_id");
      localStorage.removeItem("autonoma_ba_intake");
    } catch {
      // Ignore
    }
    refreshSessions();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const startSession = useCallback(
    async (intake: IntakeFormData) => {
      // Immediately reset all session state so no previous session data bleeds in
      setSessionId(null);
      setIntakeData(null);
      setMessages([]);
      setReadyForRequirements(false);
      setRequirementsContent(null);

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
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
        throw err;
      } finally {
        setIsSending(false);
      }
    },
    [refreshSessions]
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
              // May still be writing or available on manual click
            }
          }
          refreshSessions();
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
    [sessionId, isSending, refreshSessions]
  );

  const newSession = useCallback(() => {
    setSessionId(null);
    setIntakeData(null);
    setMessages([]);
    setReadyForRequirements(false);
    setRequirementsContent(null);
    setError(null);
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
        sessions,
        isLoadingSessions,
        isLoadingSession,
        isLoading,
        isSending,
        error,
        readyForRequirements,
        requirementsContent,
        isFetchingRequirements,
        startSession,
        selectSession,
        refreshSessions,
        sendMessage,
        fetchRequirements,
        newSession,
        clearHistory,
        refreshHistory,
        setError,
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
