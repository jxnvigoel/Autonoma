import React, { useEffect, useState, useCallback } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Header } from "./components/Header";
import { AnimatedAIChat } from "./components/ui/animated-ai-chat";
import { CodeEditor } from "./pages/CodeEditor";
import { Splash } from "./pages/Splash";
import { Landing } from "./pages/Landing";
import { checkEngineStatus, EngineStatus } from "./lib/engine";

export type AppScreen = "splash" | "landing" | "chat" | "editor";

export const App: React.FC = () => {
  const [currentScreen, setCurrentScreen] = useState<AppScreen>("splash");
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
    <AnimatePresence mode="wait">
      {currentScreen === "splash" && (
        <motion.div
          key="splash-screen"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
          className="w-full h-full"
        >
          <Splash onFinish={() => setCurrentScreen("landing")} />
        </motion.div>
      )}

      {currentScreen === "landing" && (
        <motion.div
          key="landing-screen"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25, ease: "easeOut" }}
          className="w-full h-full"
        >
          <Landing
            onStart={() => setCurrentScreen("chat")}
            status={status}
            isCheckingStatus={isChecking}
            onRefreshStatus={refreshStatus}
          />
        </motion.div>
      )}

      {currentScreen === "chat" && (
        <motion.div
          key="chat-screen"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25, ease: "easeOut" }}
          className="h-screen bg-brand-bg text-brand-headline flex flex-col font-sans transition-colors duration-200 overflow-hidden"
        >
          <Header
            status={status}
            isChecking={isChecking}
            onRefreshStatus={refreshStatus}
            onBackToLanding={() => setCurrentScreen("landing")}
            activeScreen="chat"
            onOpenChat={() => setCurrentScreen("chat")}
            onOpenEditor={() => setCurrentScreen("editor")}
          />
          <main className="flex-1 flex bg-brand-bg transition-colors duration-200 overflow-hidden">
            <AnimatedAIChat />
          </main>
        </motion.div>
      )}

      {currentScreen === "editor" && (
        <motion.div
          key="editor-screen"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25, ease: "easeOut" }}
          className="w-full h-full"
        >
          <CodeEditor
            status={status}
            isCheckingStatus={isChecking}
            onRefreshStatus={refreshStatus}
            onBackToLanding={() => setCurrentScreen("landing")}
            onOpenChat={() => setCurrentScreen("chat")}
          />
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default App;

