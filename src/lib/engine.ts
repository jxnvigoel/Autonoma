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
 * Sends a chat prompt to the Python engine at http://localhost:8765/chat
 */
export async function sendChatMessage(prompt: string): Promise<ChatResponse> {
  if (!prompt || !prompt.trim()) {
    throw new Error("Prompt cannot be empty");
  }

  try {
    const res = await fetch(`${ENGINE_BASE_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ prompt: prompt.trim() }),
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
