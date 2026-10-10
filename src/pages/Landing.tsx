import React, { useRef } from "react";
import {
  ArrowRight,
  ChevronDown,
  ShieldCheck,
  Cpu,
  Layers,
  Users,
  CheckCircle2,
  Lock,
  Briefcase,
  FileCheck,
  Code2,
} from "lucide-react";
import { EngineStatus } from "../lib/engine";
import { StatusBadge } from "../components/StatusBadge";
import { ThemeToggle } from "../components/ThemeToggle";

interface LandingProps {
  onStart: () => void;
  status?: EngineStatus | null;
  isCheckingStatus?: boolean;
  onRefreshStatus?: () => void;
}

const pipelineSteps = [
  {
    step: "01",
    role: "Business Analyst",
    abbr: "BA",
    icon: FileCheck,
    desc: "Dissects the client brief, clarifies requirements, and structures clear user stories and project milestones.",
  },
  {
    step: "02",
    role: "Product Manager",
    abbr: "PM",
    icon: Briefcase,
    desc: "Translates requirements into actionable specs, sprint roadmaps, and prioritized task backlogs.",
  },
  {
    step: "03",
    role: "Team Coordinator",
    abbr: "HR",
    icon: Users,
    desc: "Aligns role specializations and prepares agent prompts tailored specifically to your project requirements.",
  },
  {
    step: "04",
    role: "Software Architect",
    abbr: "ARCH",
    icon: Layers,
    desc: "Designs system architecture blueprints, database schemas, component hierarchies, and API contracts.",
  },
  {
    step: "05",
    role: "Software Engineer",
    abbr: "ENG",
    icon: Code2,
    desc: "Writes clean, modular, and functional production code to implement the planned features.",
  },
  {
    step: "06",
    role: "Quality Assurance",
    abbr: "QA",
    icon: ShieldCheck,
    desc: "Validates acceptance criteria, stress-tests edge cases, and verifies stability before project delivery.",
  },
];

export const Landing: React.FC<LandingProps> = ({
  onStart,
  status,
  isCheckingStatus = false,
  onRefreshStatus,
}) => {
  const learnMoreRef = useRef<HTMLDivElement>(null);

  const scrollToLearnMore = () => {
    learnMoreRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <div className="min-h-screen bg-brand-bg text-brand-headline flex flex-col selection:bg-brand-accent selection:text-brand-accent-text transition-colors duration-200">
      {/* Clean Navigation Bar */}
      <header className="sticky top-0 z-40 bg-brand-bg/90 backdrop-blur-sm border-b border-brand-border px-6 py-4 transition-colors duration-200">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-brand-accent text-brand-accent-text flex items-center justify-center font-bold text-sm shadow-sm transition-colors duration-200">
              A
            </div>
            <div className="flex items-center gap-2">
              <span className="text-base font-bold text-brand-headline tracking-tight transition-colors duration-200">
                Autonoma
              </span>
              <span className="hidden sm:inline-block text-[11px] font-medium text-brand-body bg-brand-subtle px-2.5 py-0.5 rounded-full transition-colors duration-200">
                Local Desktop
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {status !== undefined && onRefreshStatus && (
              <div className="hidden md:block">
                <StatusBadge
                  status={status}
                  isChecking={isCheckingStatus}
                  onRefresh={onRefreshStatus}
                />
              </div>
            )}
            <ThemeToggle />
            <button
              onClick={onStart}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-accent hover:bg-brand-accent-hover text-brand-accent-text text-xs font-semibold shadow-sm transition-all duration-150 active:scale-95 cursor-pointer"
            >
              <span>Get Started</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex flex-col">
        {/* HERO SECTION */}
        <section className="px-6 pt-20 pb-20 md:pt-28 md:pb-28 flex flex-col items-center text-center">
          <div className="max-w-3xl mx-auto space-y-6">
            {/* Top Pill */}
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-card border border-brand-border text-xs font-medium text-brand-accent shadow-sm transition-colors duration-200">
              <span className="w-2 h-2 rounded-full bg-brand-accent inline-block" />
              <span>Virtual AI Company</span>
            </div>

            {/* Confident, High-Contrast Headline */}
            <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold tracking-tight text-brand-headline leading-[1.1] transition-colors duration-200">
              Welcome to Autonoma
            </h1>

            {/* Concise Product Description */}
            <p className="text-base sm:text-lg text-brand-body leading-relaxed max-w-2xl mx-auto transition-colors duration-200">
              Autonoma is a virtual AI company that takes a client's project from
              brief to delivery with AI agents handling planning, design, coding,
              and testing, with human approval at key checkpoints.
            </p>

            {/* Action Buttons */}
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-4">
              <button
                onClick={onStart}
                className="w-full sm:w-auto px-6 py-3 rounded-lg bg-brand-accent hover:bg-brand-accent-hover text-brand-accent-text font-semibold text-sm shadow-sm flex items-center justify-center gap-2 active:scale-[0.98] transition-all cursor-pointer"
              >
                <span>Get Started</span>
                <ArrowRight className="w-4 h-4" />
              </button>

              <button
                onClick={scrollToLearnMore}
                className="w-full sm:w-auto px-6 py-3 rounded-lg bg-brand-card hover:bg-brand-subtle text-brand-headline border border-brand-border font-medium text-sm flex items-center justify-center gap-2 active:scale-[0.98] transition-all cursor-pointer shadow-sm"
              >
                <span>Learn More</span>
                <ChevronDown className="w-4 h-4 text-brand-body" />
              </button>
            </div>

            {/* Value Highlights */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-12 text-left">
              <div className="p-4 rounded-xl bg-brand-card border border-brand-border shadow-card transition-colors duration-200">
                <div className="flex items-center gap-2.5 text-brand-headline font-semibold text-sm">
                  <Cpu className="w-4 h-4 text-brand-accent" />
                  <span>100% Local</span>
                </div>
                <p className="text-xs text-brand-body mt-1">
                  Runs on your hardware via local Ollama models.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-brand-card border border-brand-border shadow-card transition-colors duration-200">
                <div className="flex items-center gap-2.5 text-brand-headline font-semibold text-sm">
                  <ShieldCheck className="w-4 h-4 text-brand-accent" />
                  <span>Human Checkpoints</span>
                </div>
                <p className="text-xs text-brand-body mt-1">
                  You review and approve each major stage.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-brand-card border border-brand-border shadow-card transition-colors duration-200">
                <div className="flex items-center gap-2.5 text-brand-headline font-semibold text-sm">
                  <Users className="w-4 h-4 text-brand-accent" />
                  <span>Full Team Flow</span>
                </div>
                <p className="text-xs text-brand-body mt-1">
                  6 coordinated roles handling end-to-end tasks.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* HOW IT WORKS SECTION */}
        <section
          ref={learnMoreRef}
          id="how-it-works"
          className="px-6 py-20 bg-brand-subtle/30 border-t border-brand-border transition-colors duration-200"
        >
          <div className="max-w-5xl mx-auto space-y-12">
            {/* Section Heading */}
            <div className="max-w-2xl">
              <span className="text-xs font-bold uppercase tracking-wider text-brand-accent">
                Workflow
              </span>
              <h2 className="text-2xl sm:text-3xl font-bold text-brand-headline mt-1 transition-colors duration-200">
                How It Works
              </h2>
              <p className="text-sm text-brand-body mt-2 transition-colors duration-200">
                A simple sequence of specialized AI roles working together to
                deliver your project.
              </p>
            </div>

            {/* Steps Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {pipelineSteps.map((item) => {
                const Icon = item.icon;
                return (
                  <div
                    key={item.role}
                    className="p-5 rounded-xl bg-brand-card border border-brand-border shadow-card flex flex-col justify-between transition-colors duration-200"
                  >
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="w-9 h-9 rounded-lg bg-brand-subtle border border-brand-border flex items-center justify-center text-brand-accent transition-colors duration-200">
                          <Icon className="w-4 h-4" />
                        </div>
                        <span className="text-xs font-mono font-bold text-brand-body">
                          {item.step}
                        </span>
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-brand-headline transition-colors duration-200">
                          {item.role}
                        </h3>
                        <p className="text-xs text-brand-body leading-relaxed mt-1 transition-colors duration-200">
                          {item.desc}
                        </p>
                      </div>
                    </div>

                    <div className="mt-4 pt-3 border-t border-brand-border/60 flex items-center gap-1.5 text-[11px] font-medium text-brand-body">
                      <CheckCircle2 className="w-3.5 h-3.5 text-brand-accent" />
                      <span>{item.abbr} Agent Role</span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Human Gate Callout */}
            <div className="p-6 rounded-xl bg-brand-card border border-brand-border shadow-card flex flex-col md:flex-row items-start md:items-center justify-between gap-6 transition-colors duration-200">
              <div className="space-y-1.5 max-w-2xl">
                <div className="flex items-center gap-2 text-brand-accent text-xs font-bold uppercase tracking-wider">
                  <ShieldCheck className="w-4 h-4" />
                  <span>Human-in-the-Loop Checkpoints</span>
                </div>
                <h3 className="text-base font-bold text-brand-headline transition-colors duration-200">
                  You stay in control at every key milestone
                </h3>
                <p className="text-xs sm:text-sm text-brand-body leading-relaxed transition-colors duration-200">
                  Agents handle the heavy lifting, but requirements, architecture
                  choices, and test results await your approval before code moves
                  forward.
                </p>
              </div>

              <button
                onClick={onStart}
                className="shrink-0 px-5 py-2.5 rounded-lg bg-brand-accent hover:bg-brand-accent-hover text-brand-accent-text font-semibold text-xs transition-all cursor-pointer flex items-center gap-2 shadow-sm"
              >
                <span>Launch Workspace</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </section>

        {/* WHY USE AUTONOMA */}
        <section className="px-6 py-20 bg-brand-bg border-t border-brand-border transition-colors duration-200">
          <div className="max-w-5xl mx-auto space-y-10">
            <div className="max-w-xl">
              <span className="text-xs font-bold uppercase tracking-wider text-brand-accent">
                Value
              </span>
              <h2 className="text-2xl sm:text-3xl font-bold text-brand-headline mt-1 transition-colors duration-200">
                Why Autonoma
              </h2>
              <p className="text-sm text-brand-body mt-2 transition-colors duration-200">
                Built for founders and early-stage startups without the budget or
                time to hire a full engineering team.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div className="p-6 rounded-xl bg-brand-card border border-brand-border shadow-card space-y-2.5 transition-colors duration-200">
                <h3 className="text-base font-bold text-brand-headline transition-colors duration-200">
                  The Problem
                </h3>
                <p className="text-xs sm:text-sm text-brand-body leading-relaxed transition-colors duration-200">
                  Building software traditionally requires hiring a business
                  analyst, product manager, architect, engineers, and QA. Most
                  early-stage founders can't afford to hire that team, and don't
                  have time to recruit and manage one before validating their idea.
                </p>
              </div>

              <div className="p-6 rounded-xl bg-brand-card border border-brand-border shadow-card space-y-2.5 transition-colors duration-200">
                <h3 className="text-base font-bold text-brand-headline transition-colors duration-200">
                  The Solution
                </h3>
                <p className="text-xs sm:text-sm text-brand-body leading-relaxed transition-colors duration-200">
                  Autonoma replaces the cost and friction of hiring with local AI
                  agents. You describe what you want, and the agent team handles
                  execution while you retain oversight, giving you the capacity of a
                  full team as a solo builder.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* TERMS OF USE & DISCLAIMER */}
        <section className="px-6 py-16 bg-brand-subtle/30 border-t border-brand-border transition-colors duration-200">
          <div className="max-w-5xl mx-auto space-y-6">
            <div className="flex items-center gap-2 text-brand-accent text-xs font-bold uppercase tracking-wider">
              <Lock className="w-4 h-4" />
              <span>Terms of Use & Disclaimer</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs text-brand-body leading-relaxed">
              <div className="p-4 rounded-xl bg-brand-card border border-brand-border shadow-card transition-colors duration-200">
                <span className="font-bold text-brand-headline block mb-1 transition-colors duration-200">
                  Student / Portfolio Project
                </span>
                <p>
                  Autonoma is developed as an experimental student and portfolio
                  project exploring local multi-agent software development.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-brand-card border border-brand-border shadow-card transition-colors duration-200">
                <span className="font-bold text-brand-headline block mb-1 transition-colors duration-200">
                  100% Local & Private
                </span>
                <p>
                  Runs fully locally via Ollama. No data, project briefs, or source
                  code ever leaves your computer.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-brand-card border border-brand-border shadow-card transition-colors duration-200">
                <span className="font-bold text-brand-headline block mb-1 transition-colors duration-200">
                  Work in Progress
                </span>
                <p>
                  Provided as-is with no warranty or guarantee of output quality.
                  Always verify and test generated code before production use.
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Clean Minimal Footer */}
      <footer className="border-t border-brand-border bg-brand-bg px-6 py-6 text-xs text-brand-body transition-colors duration-200">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-brand-headline">Autonoma</span>
            <span>•</span>
            <span>Local AI Desktop Application</span>
          </div>
          <button
            onClick={onStart}
            className="text-brand-accent hover:underline font-semibold transition-colors cursor-pointer flex items-center gap-1"
          >
            <span>Get Started</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </footer>
    </div>
  );
};

export default Landing;
