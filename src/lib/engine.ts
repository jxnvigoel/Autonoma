export const ENGINE_BASE_URL = "http://127.0.0.1:8765";

export interface EngineStatus {
  status: "ready" | "error" | "starting";
  ollama_online: boolean;
  model_ready: boolean;
  version?: string;
  message: string;
}

export interface ChatResponse {
  response: string;
  duration: number; // nanoseconds matching Ollama total_duration
  token_count: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
  createdAt?: Date;
  meta?: {
    duration?: number;
    token_count?: number;
  };
}

export interface IntakeFormData {
  projectName: string;
  description: string;
  targetUsers: string;
  timeline: string;
  budget: string;
}

export interface BAStartResponse {
  session_id: string;
  message: string;
}

export interface BAMessageResponse {
  session_id?: string;
  message: string;
  ready_for_requirements: boolean;
}

export interface BARequirementsResponse {
  session_id: string;
  content: string;
}

export type AgentLiveStatus = "idle" | "working" | "waiting-on-you" | "done";

export interface PMStartResponse {
  session_id: string;
  message: string;
  prd_content: string;
  already_started?: boolean;
}

export interface PMMessageResponse {
  session_id: string;
  message: string;
  prd_content: string;
  round: number;
}

export interface PMSessionDetail {
  session_id: string;
  project_name: string;
  started: boolean;
  status: AgentLiveStatus;
  messages: ChatMessage[];
  prd_content?: string | null;
  round: number;
  can_start: boolean;
}

export interface OfficeAgentInfo {
  id: "ba" | "pm" | "architect" | "engineer" | "qa";
  role: string;
  abbr: string;
  status: AgentLiveStatus;
  has_output: boolean;
  output_name: string;
  output_type: string;
  message_count: number;
  qa_count?: number;
  ready_for_handoff?: boolean;
  can_start?: boolean;
}

export interface OfficeStatusResponse {
  session_id: string;
  project_name: string;
  description: string;
  target_users: string;
  timeline: string;
  budget: string;
  agents: {
    ba: OfficeAgentInfo;
    pm: OfficeAgentInfo;
    architect: OfficeAgentInfo;
    engineer: OfficeAgentInfo;
    qa: OfficeAgentInfo;
  };
}

export interface BASessionSummary {
  session_id: string;
  project_name: string;
  description: string;
  created_at: string;
  updated_at: string;
  ready_for_requirements: boolean;
  has_requirements: boolean;
  round: number;
}

export interface BASessionDetail {
  session_id: string;
  intake: {
    project_name: string;
    description: string;
    target_users: string;
    timeline: string;
    budget: string;
    created_at?: string;
  };
  state: {
    checklist_covered?: string[];
    checklist_missing?: string[];
    round?: number;
    ready_for_requirements?: boolean;
    messages?: ChatMessage[];
  };
  qa_log: Array<{
    id: string;
    question: string;
    answer: string;
    round: number;
    timestamp: string;
  }>;
  messages: ChatMessage[];
  ready_for_requirements: boolean;
  has_requirements: boolean;
  requirements_content?: string | null;
}

/**
 * Pings the Python engine at http://localhost:8765/status
 */
export async function checkEngineStatus(): Promise<EngineStatus> {
  try {
    const res = await fetch(`${ENGINE_BASE_URL}/status`, {
      method: "GET",
      signal: AbortSignal.timeout(4000),
    });

    if (!res.ok) {
      return {
        status: "error",
        ollama_online: false,
        model_ready: false,
        message: `Python engine returned HTTP ${res.status}: ${res.statusText}`,
      };
    }

    const data: EngineStatus = await res.json();
    return data;
  } catch (err: unknown) {
    const details = err instanceof Error ? err.message : String(err);
    return {
      status: "starting",
      ollama_online: false,
      model_ready: false,
      message: `Connecting to Python engine at ${ENGINE_BASE_URL}... (${details})`,
    };
  }
}

/**
 * Starts a new BA intake session on the Python engine
 */
export async function startBaSession(intake: IntakeFormData): Promise<BAStartResponse> {
  const payload = {
    project_name: intake.projectName.trim(),
    description: intake.description.trim(),
    target_users: intake.targetUsers.trim(),
    timeline: intake.timeline.trim(),
    budget: intake.budget.trim(),
  };

  const res = await fetch(`${ENGINE_BASE_URL}/ba/start`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    const detail = errData?.detail || `Python engine error HTTP ${res.status}: ${res.statusText}`;
    throw new Error(detail);
  }

  const data: BAStartResponse = await res.json();
  return data;
}

/**
 * Sends a message in an existing BA session
 */
export async function sendBaMessage(
  sessionId: string,
  message: string
): Promise<BAMessageResponse> {
  if (!message || !message.trim()) {
    throw new Error("Message cannot be empty");
  }

  const res = await fetch(`${ENGINE_BASE_URL}/ba/message`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      session_id: sessionId,
      message: message.trim(),
    }),
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    const detail = errData?.detail || `Python engine error HTTP ${res.status}: ${res.statusText}`;
    throw new Error(detail);
  }

  const data: BAMessageResponse = await res.json();
  return data;
}

/**
 * Fetches the generated requirements.md for a BA session
 */
export async function getBaRequirements(
  sessionId: string
): Promise<BARequirementsResponse> {
  const res = await fetch(`${ENGINE_BASE_URL}/ba/requirements/${sessionId}`, {
    method: "GET",
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    const detail = errData?.detail || `HTTP ${res.status}: ${res.statusText}`;
    throw new Error(detail);
  }

  const data: BARequirementsResponse = await res.json();
  return data;
}

/**
  * Fetches all past BA sessions from http://localhost:8765/ba/sessions
  */
export async function getBaSessions(): Promise<BASessionSummary[]> {
  const res = await fetch(`${ENGINE_BASE_URL}/ba/sessions`, {
    method: "GET",
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    const detail = errData?.detail || `HTTP ${res.status}: ${res.statusText}`;
    throw new Error(detail);
  }

  const data: BASessionSummary[] = await res.json();
  return data;
}

/**
  * Fetches full history and metadata for a specific BA session
  */
export async function getBaSession(
  sessionId: string
): Promise<BASessionDetail> {
  const res = await fetch(`${ENGINE_BASE_URL}/ba/session/${sessionId}`, {
    method: "GET",
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    const detail = errData?.detail || `HTTP ${res.status}: ${res.statusText}`;
    throw new Error(detail);
  }

  const data: BASessionDetail = await res.json();
  return data;
}

/**
 * Fetches the full persistent shared conversation from http://localhost:8765/conversation
 */
export async function getConversation(): Promise<ChatMessage[]> {
  try {
    const res = await fetch(`${ENGINE_BASE_URL}/conversation`, {
      method: "GET",
      signal: AbortSignal.timeout(6000),
    });

    if (!res.ok) {
      throw new Error(`Failed to get conversation: HTTP ${res.status}`);
    }

    const data: ChatMessage[] = await res.json();
    return data;
  } catch (err: unknown) {
    console.error("Error fetching conversation:", err);
    throw err;
  }
}

/**
 * Clears the conversation history on the Python engine
 */
export async function clearConversation(): Promise<void> {
  try {
    const res = await fetch(`${ENGINE_BASE_URL}/conversation`, {
      method: "DELETE",
      signal: AbortSignal.timeout(6000),
    });

    if (!res.ok) {
      throw new Error(`Failed to clear conversation: HTTP ${res.status}`);
    }
  } catch (err: unknown) {
    console.error("Error clearing conversation:", err);
    throw err;
  }
}

/**
 * Sends a chat prompt to the Python engine at http://localhost:8765/chat
 */
export async function sendChatMessage(prompt: string, model?: string): Promise<ChatResponse> {
  if (!prompt || !prompt.trim()) {
    throw new Error("Prompt cannot be empty");
  }

  try {
    const res = await fetch(`${ENGINE_BASE_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ prompt: prompt.trim(), model }),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => null);
      const detail =
        errData?.detail || `Python engine error HTTP ${res.status}: ${res.statusText}`;
      throw new Error(detail);
    }

    const data: ChatResponse = await res.json();
    return data;
  } catch (err: unknown) {
    if (err instanceof Error) {
      throw err;
    }
    throw new Error(`Failed to send message to Python engine: ${String(err)}`);
  }
}

/**
 * Starts a new PM session for a completed BA session
 */
export async function startPmSession(sessionId: string): Promise<PMStartResponse> {
  if (!sessionId) {
    throw new Error("sessionId is required to start PM session");
  }

  const res = await fetch(`${ENGINE_BASE_URL}/pm/start`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ session_id: sessionId.trim() }),
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    const detail = errData?.detail || `HTTP ${res.status}: ${res.statusText}`;
    throw new Error(detail);
  }

  const data: PMStartResponse = await res.json();
  return data;
}

/**
 * Sends a message in an active PM session
 */
export async function sendPmMessage(
  sessionId: string,
  message: string
): Promise<PMMessageResponse> {
  if (!sessionId) {
    throw new Error("sessionId is required");
  }
  if (!message || !message.trim()) {
    throw new Error("Message cannot be empty");
  }

  const res = await fetch(`${ENGINE_BASE_URL}/pm/message`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      session_id: sessionId.trim(),
      message: message.trim(),
    }),
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    const detail = errData?.detail || `HTTP ${res.status}: ${res.statusText}`;
    throw new Error(detail);
  }

  const data: PMMessageResponse = await res.json();
  return data;
}

/**
 * Fetches current PM session state, conversation history, and PRD content
 */
export async function getPmSession(sessionId: string): Promise<PMSessionDetail> {
  if (!sessionId) {
    throw new Error("sessionId is required");
  }

  const res = await fetch(`${ENGINE_BASE_URL}/pm/session/${sessionId.trim()}`, {
    method: "GET",
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    const detail = errData?.detail || `HTTP ${res.status}: ${res.statusText}`;
    throw new Error(detail);
  }

  const data: PMSessionDetail = await res.json();
  return data;
}

/**
 * Fetches real live status for all project agents in a given session
 */
export async function getOfficeStatus(sessionId: string): Promise<OfficeStatusResponse> {
  if (!sessionId) {
    throw new Error("sessionId is required");
  }

  const res = await fetch(`${ENGINE_BASE_URL}/office/status/${sessionId.trim()}`, {
    method: "GET",
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    const detail = errData?.detail || `HTTP ${res.status}: ${res.statusText}`;
    throw new Error(detail);
  }

  const data: OfficeStatusResponse = await res.json();
  return data;
}

