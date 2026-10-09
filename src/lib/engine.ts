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
