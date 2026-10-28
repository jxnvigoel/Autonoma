import { ENGINE_BASE_URL } from "./engine";

// Local accounts (engine/auth.py). The session token stays on this machine in localStorage.
const TOKEN_KEY = "autonoma.session";

export interface AccountUser {
  id: string;
  email: string;
  name: string;
  title?: string;
  organization?: string;
  auth_method?: "password" | "google";
  created_at: string;
  project_count?: number;
}

export interface AuthResult {
  token: string;
  user: AccountUser;
  claimed_existing_projects?: string[];
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // storage unavailable: the session lasts for this window only
  }
}

export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function authJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${ENGINE_BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...authHeaders(), ...(init?.headers || {}) },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(typeof data.detail === "string" ? data.detail : `Request failed (${res.status})`);
  }
  return data as T;
}

export async function apiSignup(name: string, email: string, password: string): Promise<AuthResult> {
  const r = await authJson<AuthResult>("/auth/signup", { method: "POST", body: JSON.stringify({ name, email, password }) });
  setToken(r.token);
  return r;
}

export async function apiLogin(email: string, password: string): Promise<AuthResult> {
  const r = await authJson<AuthResult>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
  setToken(r.token);
  return r;
}

export async function apiMe(): Promise<{ user: AccountUser | null; accounts_exist: boolean; google_enabled: boolean }> {
  return authJson("/auth/me");
}

export async function apiLogout(): Promise<void> {
  try {
    await authJson("/auth/logout", { method: "POST" });
  } finally {
    setToken(null);
  }
}

export const apiGetProfile = () => authJson<AccountUser>("/auth/profile");

export const apiUpdateProfile = (fields: { name?: string; title?: string; organization?: string }) =>
  authJson<AccountUser>("/auth/profile", { method: "PUT", body: JSON.stringify(fields) });

/** Google sign-in: opens Google in the browser, then waits for the engine to finish the exchange. */
export async function apiGoogleSignIn(openExternal: (url: string) => void, timeoutMs = 300_000): Promise<AuthResult> {
  const { auth_url, state } = await authJson<{ auth_url: string; state: string }>("/auth/google/start");
  openExternal(auth_url);
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, 1500));
    const r = await authJson<{ status: string; detail?: string } & Partial<AuthResult>>(`/auth/google/result/${state}`);
    if (r.status === "done" && r.token && r.user) {
      setToken(r.token);
      return { token: r.token, user: r.user, claimed_existing_projects: r.claimed_existing_projects };
    }
    if (r.status === "error") throw new Error(r.detail || "Google sign-in failed");
  }
  throw new Error("Google sign-in timed out; try again");
}
