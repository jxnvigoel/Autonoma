import React, { useState } from "react";
import { generateRaw, OllamaGenerateResponse } from "../lib/ollama";
import { Button } from "../components/Button";

interface TestChatProps {
  onCheckStatus?: () => void;
}

export const TestChat: React.FC<TestChatProps> = () => {
  const [prompt, setPrompt] = useState<string>("");
  const [response, setResponse] = useState<string | null>(null);
  const [rawMeta, setRawMeta] = useState<OllamaGenerateResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [lastPrompt, setLastPrompt] = useState<string>("");

  const handleSend = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!prompt.trim() || isLoading) return;

    const currentPrompt = prompt.trim();
    setLastPrompt(currentPrompt);
    setIsLoading(true);
    setError(null);
    setResponse(null);
    setRawMeta(null);

    try {
      const data = await generateRaw(currentPrompt);
      setResponse(data.response);
      setRawMeta(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Send with Enter (Shift+Enter for newline)
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSuggestion = (sample: string) => {
    setPrompt(sample);
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Chain Info Banner */}
      <div className="mb-6 p-4 rounded-xl border border-slate-800 bg-slate-900/50">
        <h2 className="text-sm font-semibold text-slate-200 mb-2">
          End-to-End Verification Pipeline
        </h2>
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
          <span className="px-2.5 py-1 rounded bg-slate-800 border border-slate-700/60 font-mono text-indigo-300">
            React UI
          </span>
          <span>→</span>
          <span className="px-2.5 py-1 rounded bg-slate-800 border border-slate-700/60 font-mono text-indigo-300">
            Tauri v2 Webview
          </span>
          <span>→</span>
          <span className="px-2.5 py-1 rounded bg-slate-800 border border-slate-700/60 font-mono text-indigo-300">
            HTTP Plugin (Capability: localhost:11434)
          </span>
          <span>→</span>
          <span className="px-2.5 py-1 rounded bg-slate-800 border border-slate-700/60 font-mono text-emerald-300">
            Ollama (llama3.2:3b • Apple Metal)
          </span>
        </div>
      </div>

      {/* Input Section */}
      <form onSubmit={handleSend} className="space-y-4">
        <div>
          <label
            htmlFor="prompt-input"
            className="block text-sm font-medium text-slate-300 mb-2"
          >
            Prompt
          </label>
          <div className="relative">
            <textarea
              id="prompt-input"
              rows={3}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
              placeholder="Type a test prompt here... (Press Enter to send, Shift+Enter for new line)"
              className="w-full rounded-xl border border-slate-700 bg-slate-900/90 px-4 py-3 text-sm text-slate-100 placeholder-slate-500 shadow-inner focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:opacity-50 resize-y"
            />
          </div>
        </div>

        {/* Action Row */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          {/* Quick Suggestions */}
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span className="hidden sm:inline">Try:</span>
            <button
              type="button"
              onClick={() => handleSuggestion("Say hello and confirm you are running locally on Apple Silicon!")}
              className="text-xs px-2.5 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700/60 transition-colors cursor-pointer"
            >
              "Confirm Apple Silicon"
            </button>
            <button
              type="button"
              onClick={() => handleSuggestion("Explain quantum computing in two sentences.")}
              className="text-xs px-2.5 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700/60 transition-colors cursor-pointer"
            >
              "Quantum computing"
            </button>
          </div>

          <div className="flex items-center gap-2">
            {response && (
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setResponse(null);
                  setError(null);
                  setRawMeta(null);
                }}
              >
                Clear
              </Button>
            )}
            <Button
              type="submit"
              isLoading={isLoading}
              disabled={!prompt.trim()}
            >
              {isLoading ? "Generating..." : "Send Prompt"}
            </Button>
          </div>
        </div>
      </form>

      {/* Error Alert */}
      {error && (
        <div className="mt-6 p-4 rounded-xl border border-rose-500/30 bg-rose-950/30 text-rose-200">
          <div className="flex items-start gap-3">
            <svg
              className="w-5 h-5 text-rose-400 mt-0.5 shrink-0"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
            <div className="flex-1 text-sm whitespace-pre-wrap font-mono">
              <p className="font-semibold mb-1 font-sans">Error reaching Ollama:</p>
              {error}
            </div>
          </div>
        </div>
      )}

      {/* Response Box */}
      <div className="mt-6">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-medium text-slate-300">
            Model Response {lastPrompt ? `for "${lastPrompt.length > 40 ? lastPrompt.slice(0, 40) + "..." : lastPrompt}"` : ""}
          </h3>
          {rawMeta?.total_duration && (
            <span className="text-xs text-slate-400 font-mono">
              Duration: {(rawMeta.total_duration / 1e9).toFixed(2)}s • Tokens: {rawMeta.eval_count ?? "N/A"}
            </span>
          )}
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-5 min-h-[180px] flex flex-col justify-center">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-6 text-slate-400 gap-3">
              <div className="relative flex h-8 w-8 items-center justify-center">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-6 w-6 bg-indigo-600"></span>
              </div>
              <p className="text-sm">
                Generating response with <span className="text-indigo-300 font-semibold">llama3.2:3b</span>...
              </p>
              <p className="text-xs text-slate-500">
                Running locally via Apple Metal GPU acceleration
              </p>
            </div>
          ) : response ? (
            <div className="text-slate-100 text-sm whitespace-pre-wrap leading-relaxed">
              {response}
            </div>
          ) : (
            <div className="text-center py-6 text-slate-500 text-sm">
              <p>Ready to test.</p>
              <p className="text-xs mt-1 text-slate-600">
                Enter a prompt above and click "Send Prompt" to verify the local AI pipeline.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
