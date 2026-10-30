import { MessageSquare, Code2, Building2, FolderOpen, Sliders, BookOpen, UserCircle2, LogIn, ListChecks } from "lucide-react";
import { useChecklist } from "./office/CompanyChecklist";
import { StatusBadge } from "./StatusBadge";
import { ThemeToggle } from "./ThemeToggle";
import { EngineStatus } from "../lib/engine";
import { cn } from "../lib/utils";
import { useNav } from "../context/NavContext";
import { routeLabel, useModelRoutes } from "../lib/modelRoutes";
import { useConversation } from "../context/ConversationContext";

interface HeaderProps {
  activeScreen?: "office" | "chat" | "editor" | "landing" | "projects" | "intake";
  // The props below are kept for screens that still pass them; the shared navigation wins when present.
  status?: EngineStatus | null;
  isChecking?: boolean;
  onRefreshStatus?: () => void;
  onBackToLanding?: () => void;
  onOpenProjects?: () => void;
  onOpenOffice?: () => void;
  onOpenChat?: () => void;
  onOpenEditor?: () => void;
  onOpenSettings?: () => void;
  onOpenSkillLibrary?: () => void;
}

const tab = (active: boolean, disabled: boolean) =>
  cn(
    "flex items-center gap-1.5 px-3 py-1 rounded-lg transition-all",
    disabled
      ? "text-brand-body/40 cursor-not-allowed"
      : active
      ? "bg-brand-card text-brand-accent font-semibold shadow-xs cursor-pointer"
      : "text-brand-body hover:text-brand-headline cursor-pointer"
  );

const chip =
  "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-brand-card hover:bg-brand-subtle border border-brand-border text-xs text-brand-headline font-medium shadow-xs transition-colors cursor-pointer";

export const Header: React.FC<HeaderProps> = (props) => {
  const nav = useNav();
  const { intakeData, sessionId } = useConversation();
  const { data: checklist } = useChecklist(nav?.hasProject ? sessionId : null);
  const routes = useModelRoutes();
  const { activeScreen } = props;

  const status = nav?.status ?? props.status ?? null;
  const isChecking = nav?.isChecking ?? props.isChecking ?? false;
  const refresh = nav?.refreshStatus ?? props.onRefreshStatus ?? (() => undefined);
  const hasProject = nav ? nav.hasProject : Boolean(props.onOpenOffice || props.onOpenEditor);
  const go = (screen: "projects" | "office" | "chat" | "editor" | "landing", fallback?: () => void) =>
    nav ? () => nav.go(screen) : fallback;

  const items: { key: "office" | "chat" | "editor"; label: string; icon: JSX.Element; onClick?: () => void }[] = [
    { key: "office", label: "Virtual Office", icon: <Building2 className="w-3.5 h-3.5" />, onClick: go("office", props.onOpenOffice) },
    { key: "chat", label: "BA Discovery", icon: <MessageSquare className="w-3.5 h-3.5" />, onClick: go("chat", props.onOpenChat) },
    { key: "editor", label: "Code Editor", icon: <Code2 className="w-3.5 h-3.5" />, onClick: go("editor", props.onOpenEditor) },
  ];
  const needsProject = "Open or create a project first";
  const openSettings = nav?.openSettings ?? props.onOpenSettings;
  const openSkills = nav?.openSkills ?? props.onOpenSkillLibrary;
  const onLanding = go("landing", props.onBackToLanding);
  const onProjects = go("projects", props.onOpenProjects);

  return (
    <header className="border-b border-brand-border bg-brand-bg/95 backdrop-blur-sm px-4 lg:px-6 py-3 flex items-center justify-between gap-3 sticky top-0 z-30 transition-colors duration-200">
      <div className="flex items-center gap-4 min-w-0">
        <button
          type="button"
          onClick={onLanding}
          className="flex items-center gap-3 cursor-pointer group select-none shrink-0"
          title="Back to the overview page"
        >
          <div className="w-8 h-8 rounded-lg bg-brand-accent text-brand-accent-text flex items-center justify-center font-bold text-sm group-hover:scale-105 transition-all shadow-sm">
            A
          </div>
          <div className="text-left hidden lg:block">
            <h1 className="text-base font-bold text-brand-headline tracking-tight group-hover:text-brand-accent transition-colors duration-200">
              Autonoma
            </h1>
            <p className="text-[11px] text-brand-body truncate max-w-[180px]">
              {intakeData?.projectName ? `Project: ${intakeData.projectName}` : "No project open"}
            </p>
          </div>
        </button>

        {/* Same tabs on every screen; project-only tabs are disabled, never hidden. */}
        <nav className="flex items-center p-1 rounded-xl bg-brand-subtle/70 border border-brand-border text-xs font-medium">
          <button type="button" onClick={onProjects} className={tab(activeScreen === "projects", false)}>
            <FolderOpen className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Projects</span>
          </button>
          {items.map((it) => {
            const disabled = !hasProject || !it.onClick;
            return (
              <button
                key={it.key}
                type="button"
                disabled={disabled}
                onClick={disabled ? undefined : it.onClick}
                title={disabled ? needsProject : it.label}
                className={tab(activeScreen === it.key, disabled)}
              >
                {it.icon}
                <span className="hidden md:inline">{it.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <div
          className="hidden xl:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-brand-card border border-brand-border text-xs text-brand-body font-medium"
          title="Model the PM uses right now (each agent's model is on its desk)"
        >
          <span>Model:</span>
          <span className="font-semibold text-brand-headline">{routeLabel(routes?.roles["pm"])}</span>
        </div>
        <button
          type="button"
          onClick={nav?.openChecklist}
          disabled={!nav || !hasProject}
          className={cn(chip, (!nav || !hasProject) && "opacity-40 cursor-not-allowed")}
          title={hasProject ? "Company checklist: every stage, feature and test with its owner" : needsProject}
        >
          <ListChecks className="w-3.5 h-3.5 text-emerald-500" />
          <span className="hidden md:inline">Checklist</span>
          {checklist && <span className="font-mono text-[10px] text-brand-body">{checklist.progress.percent}%</span>}
        </button>
        <button type="button" onClick={openSkills} disabled={!openSkills} className={chip} title="Specialist skill library">
          <BookOpen className="w-3.5 h-3.5 text-purple-500" />
          <span className="hidden md:inline">Skills</span>
        </button>
        <button type="button" onClick={openSettings} disabled={!openSettings} className={chip} title="LLM providers and model routing">
          <Sliders className="w-3.5 h-3.5 text-brand-accent" />
          <span className="hidden md:inline">LLM</span>
        </button>
        <StatusBadge status={status} isChecking={isChecking} onRefresh={refresh} />
        <ThemeToggle />
        {nav &&
          (nav.user ? (
            <button type="button" onClick={nav.openProfile} className={chip} title={`Signed in as ${nav.user.email}`}>
              <UserCircle2 className="w-4 h-4 text-brand-accent" />
              <span className="hidden lg:inline max-w-[110px] truncate">{nav.user.name}</span>
            </button>
          ) : (
            <button type="button" onClick={nav.signIn} className={chip} title="Log in or sign up">
              <LogIn className="w-3.5 h-3.5" />
              <span className="hidden lg:inline">Sign in</span>
            </button>
          ))}
      </div>
    </header>
  );
};

export default Header;
