import React, { useEffect, useState, useCallback } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Header } from "./components/Header";
import { AnimatedAIChat } from "./components/ui/animated-ai-chat";
import { VirtualOffice } from "./pages/VirtualOffice";
import { CodeEditor } from "./pages/CodeEditor";
import { Splash } from "./pages/Splash";
import { Landing } from "./pages/Landing";
import { ProjectSelector } from "./pages/ProjectSelector";
import { AuthPage } from "./pages/Auth";
import { ProfileModal } from "./components/ProfileModal";
import { AccountUser, apiLogout, apiMe } from "./lib/auth";
import { IntakeForm } from "./components/chat/IntakeForm";
import { checkEngineStatus, EngineStatus } from "./lib/engine";
import { useConversation } from "./context/ConversationContext";

export type AppScreen =
  | "splash"
  | "landing"
  | "auth"
  | "projects"
  | "intake"
  | "office"
  | "chat"
  | "editor";

export const App: React.FC = () => {
  const [currentScreen, setCurrentScreen] = useState<AppScreen>("splash");
  const [status, setStatus] = useState<EngineStatus | null>(null);
  const [isChecking, setIsChecking] = useState<boolean>(true);
  const {
    sessionId,
    selectSession,
    newSession,
    startSession,
    isSending,
    error: contextError,
  } = useConversation();

  // Signed-in account (local). Once any account exists, projects are per user.
  const [user, setUser] = useState<AccountUser | null>(null);
  const [accountsExist, setAccountsExist] = useState(false);
  const [showProfile, setShowProfile] = useState(false);

  useEffect(() => {
    apiMe()
      .then((me) => {
        setUser(me.user);
        setAccountsExist(me.accounts_exist);
      })
      .catch(() => undefined);
  }, []);

  // "Get Started": signed in -> your projects; otherwise log in / sign up first.
  const handleStartFromLanding = useCallback(() => {
    setCurrentScreen(user ? "projects" : "auth");
  }, [user]);

  const handleLogout = useCallback(async () => {
    await apiLogout().catch(() => undefined);
    setUser(null);
    setAccountsExist(true);
    setShowProfile(false);
    newSession();
    setCurrentScreen("auth");
  }, [newSession]);

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
            onStart={handleStartFromLanding}
            status={status}
            isCheckingStatus={isChecking}
            onRefreshStatus={refreshStatus}
          />
        </motion.div>
      )}

      {currentScreen === "auth" && (
        <motion.div
          key="auth-screen"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25, ease: "easeOut" }}
          className="w-full h-full"
        >
          <AuthPage
            onSignedIn={(signedIn) => {
              setUser(signedIn);
              setAccountsExist(true);
              newSession();
              setCurrentScreen("projects");
            }}
            onBackToLanding={() => setCurrentScreen("landing")}
          />
        </motion.div>
      )}

      {showProfile && user && (
        <ProfileModal onClose={() => setShowProfile(false)} onLogout={handleLogout} onUpdated={setUser} />
      )}

      {currentScreen === "projects" && (
        <motion.div
          key="projects-screen"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25, ease: "easeOut" }}
          className="w-full h-full"
        >
          <ProjectSelector
            onSelectProject={async (targetSessionId) => {
              await selectSession(targetSessionId);
              setCurrentScreen("office");
            }}
            onNewProject={() => {
              newSession();
              setCurrentScreen("intake");
            }}
            onBackToLanding={() => setCurrentScreen("landing")}
            status={status}
            isCheckingStatus={isChecking}
            onRefreshStatus={refreshStatus}
            user={user}
            onOpenProfile={() => setShowProfile(true)}
            onSignIn={accountsExist || !user ? () => setCurrentScreen("auth") : undefined}
          />
        </motion.div>
      )}

      {currentScreen === "intake" && (
        <motion.div
          key="intake-screen"
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
            activeScreen="intake"
            onOpenProjects={() => setCurrentScreen("projects")}
            onOpenOffice={sessionId ? () => setCurrentScreen("office") : undefined}
            onOpenChat={sessionId ? () => setCurrentScreen("chat") : undefined}
            onOpenEditor={sessionId ? () => setCurrentScreen("editor") : undefined}
          />
          <main className="flex-1 flex flex-col overflow-y-auto bg-brand-bg transition-colors duration-200">
            <IntakeForm
              onSubmit={async (data) => {
                await startSession(data);
                setCurrentScreen("office");
              }}
              onSelectSession={async (targetSessionId) => {
                await selectSession(targetSessionId);
                setCurrentScreen("office");
              }}
              isLoading={isSending}
              error={contextError}
            />
          </main>
        </motion.div>
      )}

      {currentScreen === "office" && (
        <motion.div
          key="office-screen"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25, ease: "easeOut" }}
          className="w-full h-full"
        >
          <VirtualOffice
            status={status}
            isCheckingStatus={isChecking}
            onRefreshStatus={refreshStatus}
            onBackToLanding={() => setCurrentScreen("landing")}
            onOpenProjects={() => setCurrentScreen("projects")}
            onOpenChat={() => setCurrentScreen("chat")}
            onOpenEditor={() => setCurrentScreen("editor")}
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
            onOpenProjects={() => setCurrentScreen("projects")}
            onOpenOffice={sessionId ? () => setCurrentScreen("office") : undefined}
            onOpenChat={() => setCurrentScreen("chat")}
            onOpenEditor={() => setCurrentScreen("editor")}
          />
          <main className="flex-1 flex bg-brand-bg transition-colors duration-200 overflow-hidden">
            <AnimatedAIChat
              onNavigateToOffice={() => setCurrentScreen("office")}
              onNavigateToProjects={() => setCurrentScreen("projects")}
              onNavigateToIntake={() => {
                newSession();
                setCurrentScreen("intake");
              }}
            />
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
            onOpenProjects={() => setCurrentScreen("projects")}
            onOpenOffice={sessionId ? () => setCurrentScreen("office") : undefined}
            onOpenChat={() => setCurrentScreen("chat")}
          />
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default App;
