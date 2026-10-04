import React, { useEffect, useState, useCallback } from "react";
import { Header } from "./components/Header";
import { AnimatedAIChat } from "./components/ui/animated-ai-chat";
// import { TestChat } from "./pages/TestChat"; // Kept for reference, removed from active render path
import { checkEngineStatus, EngineStatus } from "./lib/engine";

export const App: React.FC = () => {
  const [status, setStatus] = useState<EngineStatus | null>(null);
  const [isChecking, setIsChecking] = useState<boolean>(true);

  const refreshStatus = useCallback(async () => {
    setIsChecking(true);
    try {
      const res = await checkEngineStatus();
      setStatus(res);
    } catch {
      setStatus({
        status: "error",
        ollama_online: false,
        model_ready: false,
        message: "Unable to reach Python engine at http://127.0.0.1:8765",
      });
    } finally {
      setIsChecking(false);
    }
  }, []);

  useEffect(() => {
    refreshStatus();
  }, [refreshStatus]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Header
        status={status}
        isChecking={isChecking}
        onRefreshStatus={refreshStatus}
      />
      <main className="flex-1 flex flex-col">
        {/* Animated AI Chat interface from 21st.dev wired to Python FastAPI engine */}
        <AnimatedAIChat />
        {/* <TestChat onCheckStatus={refreshStatus} /> */}
      </main>
    </div>
  );
};

export default App;
