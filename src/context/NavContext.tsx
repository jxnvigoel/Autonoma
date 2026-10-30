import { createContext, useContext } from "react";
import { EngineStatus } from "../lib/engine";
import { AccountUser } from "../lib/auth";

/** Screens reachable from the top navigation once signed in. */
export type NavScreen = "projects" | "office" | "chat" | "editor" | "intake" | "landing";

/**
 * One navigation for every screen after sign-in, so the same buttons are always in the same place.
 * Items that need an open project are shown disabled (with the reason) instead of disappearing.
 */
export interface NavState {
  go: (screen: NavScreen) => void;
  hasProject: boolean;
  status: EngineStatus | null;
  isChecking: boolean;
  refreshStatus: () => void;
  user: AccountUser | null;
  openProfile: () => void;
  openSettings: () => void;
  openSkills: () => void;
  openChecklist: () => void;
  signIn: () => void;
}

const NavContext = createContext<NavState | null>(null);

export const NavProvider = NavContext.Provider;

export const useNav = (): NavState | null => useContext(NavContext);
