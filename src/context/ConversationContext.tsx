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
  getConversation,
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

const SESSION_STORAGE_KEY = "autonoma_ba_session_id";
const INTAKE_STORAGE_KEY = "autonoma_ba_intake";

export const ConversationProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [sessionId, setSessionId] = useState<string | null>(() => {
    return localStorage.getItem(SESSION_STORAGE_KEY) || null;
  });

  const [intakeData, setIntakeData] = useState<IntakeFormData | null>(() => {
    const raw = localStorage.getItem(INTAKE_STORAGE_KEY);
    if (raw) {
      try {
        return JSON.parse(raw);
      } catch {
        return null;
      }
    }
    return null;
  });

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessions, setSessions] = useState<BASessionSummary[]>([]);
  const [isLoadingSessions, setIsLoadingSessions] = useState<boolean>(false);
  const [isLoadingSession, setIsLoadingSession] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSending, setIsSending] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [readyForRequirements, setReadyForRequirements] =
    useState<boolean>(false);
  const [requirementsContent, setRequirementsContent] = useState<string | null>(
    null
  );
  const [isFetchingRequirements, setIsFetchingRequirements] =
    useState<boolean>(false);

  // Sync session ID to localStorage
  useEffect(() => {
    if (sessionId) {
      localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
    } else {
      localStorage.removeItem(SESSION_STORAGE_KEY);
    }
  }, [sessionId]);

  // Sync intake data to localStorage
  useEffect(() => {
    if (intakeData) {
      localStorage.setItem(INTAKE_STORAGE_KEY, JSON.stringify(intakeData));
    } else {
      localStorage.removeItem(INTAKE_STORAGE_KEY);
    }
  }, [intakeData]);

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
    setIsLoadingSession(true);
    setError(null);
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

  // Initial load of sessions list and current session data
  useEffect(() => {
    refreshSessions();
    if (sessionId) {
      selectSession(sessionId);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const startSession = useCallback(
    async (intake: IntakeFormData) => {
      setIsSending(true);
      setError(null);
      setReadyForRequirements(false);
      setRequirementsContent(null);

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
    localStorage.removeItem(SESSION_STORAGE_KEY);
    localStorage.removeItem(INTAKE_STORAGE_KEY);
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
    if (!sessionId) {
      setIsLoading(true);
      try {
        const history = await getConversation();
        setMessages(history);
      } catch {
        // Backend starting or offline
      } finally {
        setIsLoading(false);
      }
    } else {
      refreshSessions();
    }
  }, [sessionId, refreshSessions]);

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
