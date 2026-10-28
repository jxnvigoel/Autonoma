import React, { useEffect, useState } from "react";
import { ChevronLeft, Loader2, LogIn, UserPlus, AlertTriangle } from "lucide-react";
import { ThemeToggle } from "../components/ThemeToggle";
import { AccountUser, apiGoogleSignIn, apiLogin, apiMe, apiSignup } from "../lib/auth";

interface AuthPageProps {
  onSignedIn: (user: AccountUser, claimedProjects: string[]) => void;
  onBackToLanding: () => void;
}

// Log in brings back your projects; sign up starts a new, empty workspace.
export const AuthPage: React.FC<AuthPageProps> = ({ onSignedIn, onBackToLanding }) => {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [googleEnabled, setGoogleEnabled] = useState(false);

  useEffect(() => {
    apiMe()
      .then((me) => {
        setGoogleEnabled(me.google_enabled);
        if (!me.accounts_exist) setMode("signup");
      })
      .catch(() => undefined);
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = mode === "signup" ? await apiSignup(name, email, password) : await apiLogin(email, password);
      onSignedIn(r.user, r.claimed_existing_projects || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const google = async () => {
    setBusy(true);
    setError(null);
    try {
      const open = (url: string) =>
        window.electronAPI?.openExternal ? window.electronAPI.openExternal(url) : window.open(url, "_blank");
      const r = await apiGoogleSignIn((url) => void open(url));
      onSignedIn(r.user, r.claimed_existing_projects || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const input =
    "w-full rounded-lg border border-brand-border bg-brand-card px-3 py-2 text-sm text-brand-headline outline-none focus:ring-2 focus:ring-brand-accent";

  return (
    <div className="min-h-screen bg-brand-bg text-brand-headline flex flex-col transition-colors duration-200">
      <header className="border-b border-brand-border px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onBackToLanding}
              className="p-1.5 -ml-1 text-brand-body hover:text-brand-headline rounded-lg hover:bg-brand-subtle transition-colors cursor-pointer flex items-center gap-1 text-xs font-medium"
            >
              <ChevronLeft className="w-4 h-4" />
              <span className="hidden sm:inline">Overview</span>
            </button>
            <div className="h-4 w-px bg-brand-border" />
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-brand-accent text-brand-accent-text flex items-center justify-center font-bold text-xs shadow-sm">
                A
              </div>
              <span className="text-sm font-bold tracking-tight">Autonoma</span>
            </div>
          </div>
          <ThemeToggle />
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-sm rounded-2xl border border-brand-border bg-brand-card p-6 space-y-5">
          <div className="space-y-1">
            <h1 className="text-lg font-bold">{mode === "login" ? "Welcome back" : "Create your account"}</h1>
            <p className="text-xs text-brand-body">
              {mode === "login"
                ? "Log in to continue your projects."
                : "Sign up to start a new workspace. Your account stays on this computer."}
            </p>
          </div>

          <div className="grid grid-cols-2 p-1 rounded-lg bg-brand-subtle text-xs font-semibold">
            {(["login", "signup"] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => {
                  setMode(m);
                  setError(null);
                }}
                className={`py-1.5 rounded-md cursor-pointer ${mode === m ? "bg-brand-card shadow-xs" : "text-brand-body"}`}
              >
                {m === "login" ? "Log in" : "Sign up"}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="space-y-3">
            {mode === "signup" && (
              <label className="block space-y-1">
                <span className="text-[11px] font-medium text-brand-body">Name</span>
                <input className={input} value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" required />
              </label>
            )}
            <label className="block space-y-1">
              <span className="text-[11px] font-medium text-brand-body">Email</span>
              <input className={input} type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
            </label>
            <label className="block space-y-1">
              <span className="text-[11px] font-medium text-brand-body">Password</span>
              <input
                className={input}
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                minLength={mode === "signup" ? 8 : undefined}
                required
              />
              {mode === "signup" && <span className="text-[10px] text-brand-muted">At least 8 characters.</span>}
            </label>

            {error && (
              <p role="alert" className="flex items-start gap-1.5 text-[11px] text-red-600">
                <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={busy}
              className="w-full flex items-center justify-center gap-1.5 rounded-lg bg-brand-accent text-brand-accent-text py-2 text-sm font-semibold disabled:opacity-50 cursor-pointer"
            >
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : mode === "login" ? <LogIn className="w-4 h-4" /> : <UserPlus className="w-4 h-4" />}
              {mode === "login" ? "Log in" : "Create account"}
            </button>
          </form>

          <div className="flex items-center gap-3 text-[10px] text-brand-muted">
            <div className="h-px flex-1 bg-brand-border" />
            or
            <div className="h-px flex-1 bg-brand-border" />
          </div>

          <button
            type="button"
            onClick={google}
            disabled={busy || !googleEnabled}
            title={googleEnabled ? "" : "Google sign-in needs GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env"}
            className="w-full rounded-lg border border-brand-border py-2 text-sm font-medium hover:bg-brand-subtle disabled:opacity-50 cursor-pointer"
          >
            Continue with Google
          </button>
          {!googleEnabled && (
            <p className="text-[10px] text-brand-muted">
              Google sign-in is not set up on this computer yet (it needs a Google OAuth client ID in .env).
            </p>
          )}
        </div>
      </main>
    </div>
  );
};

export default AuthPage;
