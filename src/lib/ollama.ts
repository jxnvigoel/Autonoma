/**
 * Ollama Client for Autonoma Desktop
 *
 * Targets local Ollama instance running at http://localhost:11434
 * Default model: llama3.2:3b (Metal accelerated on Apple M4)
 */

export const DEFAULT_OLLAMA_HOST = "http://localhost:11434";
export const DEFAULT_MODEL = "llama3.2:3b";

export interface GenerateOptions {
  model?: string;
  system?: string;
  temperature?: number;
  host?: string;
}

export interface OllamaGenerateResponse {
  model: string;
  created_at: string;
  response: string;
  done: boolean;
  done_reason?: string;
  total_duration?: number;
  load_duration?: number;
  prompt_eval_count?: number;
  prompt_eval_duration?: number;
  eval_count?: number;
  eval_duration?: number;
}

export interface OllamaStatus {
  online: boolean;
  message: string;
  version?: string;
}

/**
 * Standard fetch for Ollama API requests.
 */
async function fetchClient(url: string, init?: RequestInit): Promise<Response> {
  return await window.fetch(url, init);
}

/**
 * Check if the local Ollama daemon is reachable.
 */
export async function checkOllamaStatus(
  host: string = DEFAULT_OLLAMA_HOST
): Promise<OllamaStatus> {
  try {
    const res = await fetchClient(`${host}/api/version`, {
      method: "GET",
    });

    if (res.ok) {
      const data = (await res.json()) as { version?: string };
      return {
        online: true,
        message: "Ollama is running",
        version: data.version,
      };
    }

    return {
      online: false,
      message: `Ollama returned HTTP ${res.status}: ${res.statusText}`,
    };
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : String(err);
    return {
      online: false,
      message: `Cannot connect to Ollama at ${host}. (${errorMsg})`,
    };
  }
}

/**
 * Sends a non-streaming prompt to Ollama's /api/generate endpoint.
 *
 * @param prompt - The text prompt to send to the model
 * @param options - Configuration options (model, host, temperature, etc.)
 * @returns The generated response string from the model
 */
export async function generateText(
  prompt: string,
  options?: GenerateOptions
): Promise<string> {
  const result = await generateRaw(prompt, options);
  return result.response;
}

/**
 * Sends a non-streaming prompt to Ollama's /api/generate endpoint and returns the full response object.
 */
export async function generateRaw(
  prompt: string,
  options?: GenerateOptions
): Promise<OllamaGenerateResponse> {
  const host = options?.host ?? DEFAULT_OLLAMA_HOST;
  const model = options?.model ?? DEFAULT_MODEL;

  if (!prompt || !prompt.trim()) {
    throw new Error("Prompt cannot be empty");
  }

  try {
    const response = await fetchClient(`${host}/api/generate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model,
        prompt,
        stream: false,
        system: options?.system,
        options:
          options?.temperature !== undefined
            ? { temperature: options.temperature }
            : undefined,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text().catch(() => "");
      if (response.status === 404) {
        throw new Error(
          `Model "${model}" not found in Ollama. Make sure you have downloaded it by running:\n  ollama pull ${model}`
        );
      }
      throw new Error(
        `Ollama returned error ${response.status} (${response.statusText}): ${errorText || "No details provided"}`
      );
    }

    const data = (await response.json()) as OllamaGenerateResponse;
    return data;
  } catch (err: unknown) {
    // If it's already our friendly formatted error, rethrow as-is
    if (
      err instanceof Error &&
      (err.message.includes("Model \"") || err.message.includes("Ollama returned error"))
    ) {
      throw err;
    }

    // Network / connection failure
    const errorDetails = err instanceof Error ? err.message : String(err);
    throw new Error(
      `Unable to reach Ollama at ${host}. Please ensure the Ollama service is running.\n` +
      `You can start it in your terminal with:\n  ollama run ${model}\n` +
      `(Details: ${errorDetails})`
    );
  }
}
