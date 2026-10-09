import React, { useEffect, useRef, useState } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import {
  Terminal as TerminalIcon,
  X,
  ChevronDown,
  ChevronUp,
  RotateCcw,
  Trash2,
  Folder,
} from "lucide-react";
import { useTheme } from "../../context/ThemeContext";
import { cn } from "../../lib/utils";

interface TerminalPanelProps {
  isOpen: boolean;
  onToggle: () => void;
  cwd?: string;
}

export const TerminalPanel: React.FC<TerminalPanelProps> = ({
  isOpen,
  onToggle,
  cwd,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const terminalInstanceRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const sessionIdRef = useRef<string>(`term-${Date.now()}`);
  const { theme } = useTheme();
  const [isMaximized, setIsMaximized] = useState<boolean>(false);

  // Initialize xterm & pty session
  useEffect(() => {
    if (!isOpen || !containerRef.current) return;

    const termTheme =
      theme === "dark"
        ? {
            background: "#15151D",
            foreground: "#F0F0F0",
            cursor: "#7A7AC9",
            cursorAccent: "#15151D",
            selectionBackground: "rgba(122, 122, 201, 0.3)",
            black: "#15151D",
            red: "#F87171",
            green: "#4ADE80",
            yellow: "#FBBF24",
            blue: "#60A5FA",
            magenta: "#C084FC",
            cyan: "#38BDF8",
            white: "#F3F4F6",
          }
        : {
            background: "#FFFFFF",
            foreground: "#1A1A1A",
            cursor: "#2E2E5C",
            cursorAccent: "#FFFFFF",
            selectionBackground: "rgba(46, 46, 92, 0.2)",
            black: "#000000",
            red: "#DC2626",
            green: "#16A34A",
            yellow: "#D97706",
            blue: "#2563EB",
            magenta: "#9333EA",
            cyan: "#0891B2",
            white: "#FFFFFF",
          };

    // Dispose previous if any
    if (terminalInstanceRef.current) {
      terminalInstanceRef.current.dispose();
      terminalInstanceRef.current = null;
    }

    const term = new Terminal({
      cursorBlink: true,
      fontSize: 12,
      fontFamily: "Menlo, Monaco, 'Courier New', monospace",
      theme: termTheme,
      allowTransparency: true,
      lineHeight: 1.2,
      convertEol: true,
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);

    containerRef.current.innerHTML = "";
    term.open(containerRef.current);

    terminalInstanceRef.current = term;
    fitAddonRef.current = fitAddon;

    // Small delay to allow DOM to measure dimensions
    setTimeout(() => {
      try {
        fitAddon.fit();
      } catch {
        // ignore initial measurement glitch
      }
    }, 50);

    const sessionId = sessionIdRef.current;

    // Spawn PTY in electron main
    if (window.electronAPI?.terminalCreate) {
      window.electronAPI
        .terminalCreate(sessionId, cwd)
        .then(() => {
          if (term.cols && term.rows) {
            window.electronAPI?.terminalResize(sessionId, term.cols, term.rows);
          }
        })
        .catch((err) => {
          term.write(`\r\n\x1b[31mFailed to start terminal: ${err.message}\x1b[0m\r\n`);
        });

      // Handle user keypresses in terminal
      const onDataDisposable = term.onData((data) => {
        window.electronAPI?.terminalWrite(sessionId, data);
      });

      // Handle terminal output from PTY
      const unsubscribeData = window.electronAPI.onTerminalData(
        sessionId,
        (data) => {
          term.write(data);
        }
      );

      const unsubscribeExit = window.electronAPI.onTerminalExit(
        sessionId,
        (code) => {
          term.write(`\r\n\x1b[33m[Process exited with code ${code}]\x1b[0m\r\n`);
        }
      );

      return () => {
        onDataDisposable.dispose();
        unsubscribeData();
        unsubscribeExit();
        term.dispose();
        terminalInstanceRef.current = null;
        if (window.electronAPI?.terminalClose) {
          window.electronAPI.terminalClose(sessionId);
        }
      };
    } else {
      // Browser fallback demo
      term.write("\x1b[32mAutonoma Web Terminal Emulator (Connect to Electron for full shell)\x1b[0m\r\n");
      term.write(`\x1b[34mWorkspace: ${cwd || "/workspace"}\x1b[0m\r\n$ `);
      const onDataDisposable = term.onData((e) => {
        if (e === "\r") {
          term.write("\r\n$ ");
        } else if (e === "\u007F") {
          term.write("\b \b");
        } else {
          term.write(e);
        }
      });
      return () => {
        onDataDisposable.dispose();
        term.dispose();
        terminalInstanceRef.current = null;
      };
    }
  }, [isOpen, cwd, theme]);

  // Handle Resize
  useEffect(() => {
    if (!isOpen || !fitAddonRef.current || !terminalInstanceRef.current) return;

    const handleResize = () => {
      try {
        fitAddonRef.current?.fit();
        const term = terminalInstanceRef.current;
        if (term && window.electronAPI?.terminalResize) {
          window.electronAPI.terminalResize(
            sessionIdRef.current,
            term.cols,
            term.rows
          );
        }
      } catch {
        // ignore
      }
    };

    window.addEventListener("resize", handleResize);
    const timer = setTimeout(handleResize, 100);

    return () => {
      window.removeEventListener("resize", handleResize);
      clearTimeout(timer);
    };
  }, [isOpen, isMaximized]);

  const handleRestart = () => {
    if (terminalInstanceRef.current) {
      terminalInstanceRef.current.clear();
    }
    sessionIdRef.current = `term-${Date.now()}`;
    if (window.electronAPI?.terminalCreate) {
      window.electronAPI
        .terminalCreate(sessionIdRef.current, cwd)
        .then(() => {
          if (terminalInstanceRef.current?.cols && terminalInstanceRef.current?.rows) {
            window.electronAPI?.terminalResize(
              sessionIdRef.current,
              terminalInstanceRef.current.cols,
              terminalInstanceRef.current.rows
            );
          }
        });
    }
  };

  const handleClear = () => {
    terminalInstanceRef.current?.clear();
  };

  if (!isOpen) return null;

  return (
    <div
      className={cn(
        "border-t border-brand-border bg-brand-bg flex flex-col transition-all duration-200 shrink-0 z-20 shadow-lg select-none",
        isMaximized ? "h-[65vh]" : "h-64"
      )}
    >
      {/* Terminal Title Bar */}
      <div className="h-8 px-4 border-b border-brand-border bg-brand-card flex items-center justify-between text-xs text-brand-headline shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 font-semibold text-brand-headline">
            <TerminalIcon className="w-3.5 h-3.5 text-brand-accent" />
            <span>Terminal</span>
          </div>

          <div className="h-3 w-px bg-brand-border" />

          {cwd && (
            <div className="flex items-center gap-1 text-[11px] text-brand-body font-mono truncate max-w-[320px]">
              <Folder className="w-3 h-3 text-brand-accent/70 shrink-0" />
              <span className="truncate">{cwd}</span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={handleClear}
            className="p-1 rounded hover:bg-brand-subtle text-brand-body hover:text-brand-headline transition-colors cursor-pointer"
            title="Clear terminal"
          >
            <Trash2 className="w-3 h-3" />
          </button>
          <button
            type="button"
            onClick={handleRestart}
            className="p-1 rounded hover:bg-brand-subtle text-brand-body hover:text-brand-headline transition-colors cursor-pointer"
            title="Restart terminal session"
          >
            <RotateCcw className="w-3 h-3" />
          </button>
          <button
            type="button"
            onClick={() => setIsMaximized((prev) => !prev)}
            className="p-1 rounded hover:bg-brand-subtle text-brand-body hover:text-brand-headline transition-colors cursor-pointer"
            title={isMaximized ? "Restore size" : "Maximize terminal"}
          >
            {isMaximized ? (
              <ChevronDown className="w-3.5 h-3.5" />
            ) : (
              <ChevronUp className="w-3.5 h-3.5" />
            )}
          </button>
          <button
            type="button"
            onClick={onToggle}
            className="p-1 rounded hover:bg-brand-subtle text-brand-body hover:text-brand-headline transition-colors cursor-pointer"
            title="Close terminal"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* xterm container */}
      <div
        ref={containerRef}
        className="flex-1 p-2 bg-brand-bg overflow-hidden font-mono text-xs select-text"
      />
    </div>
  );
};

export default TerminalPanel;
