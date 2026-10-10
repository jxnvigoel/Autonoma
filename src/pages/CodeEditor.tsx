import React, { useState, useEffect, useCallback } from "react";
import {
  Bot,
  MessageSquare,
  Sparkles,
  Save,
  Check,
  PanelLeftClose,
  PanelLeftOpen,
  Terminal as TerminalIcon,
  Code2,
  FileJson,
  Braces,
  Terminal as TerminalFileIcon,
  FileText,
} from "lucide-react";
import { Header } from "../components/Header";
import { AgentPanel } from "../components/editor/AgentPanel";
import { TerminalPanel } from "../components/editor/TerminalPanel";
import { FileTree } from "../components/editor/FileTree";
import { EngineStatus } from "../lib/engine";
import { TreeNode } from "../types/electron";
import {
  openFolderDialog,
  readDirectoryTree,
  readFileContent,
  saveFileContent,
} from "../lib/fs";
import { cn } from "../lib/utils";

interface CodeEditorProps {
  status: EngineStatus | null;
  isCheckingStatus: boolean;
  onRefreshStatus: () => void;
  onBackToLanding: () => void;
  onOpenProjects?: () => void;
  onOpenOffice?: () => void;
  onOpenChat: () => void;
}

interface OpenTab {
  id: string;
  path: string;
  name: string;
  language: string;
  content: string;
  isDirty?: boolean;
}

function detectLanguage(filePath: string): string {
  const ext = filePath.split(".").pop()?.toLowerCase() || "";
  switch (ext) {
    case "ts":
    case "tsx":
      return "typescript";
    case "js":
    case "jsx":
      return "javascript";
    case "py":
      return "python";
    case "json":
      return "json";
    case "css":
    case "scss":
      return "css";
    case "html":
      return "html";
    case "md":
      return "markdown";
    default:
      return "plaintext";
  }
}

export const CodeEditor: React.FC<CodeEditorProps> = ({
  status,
  isCheckingStatus,
  onRefreshStatus,
  onBackToLanding,
  onOpenProjects,
  onOpenOffice,
  onOpenChat,
}) => {
  const [rootFolderPath, setRootFolderPath] = useState<string>("");
  const [rootFolderName, setRootFolderName] = useState<string>("");
  const [fileTree, setFileTree] = useState<TreeNode[]>([]);
  const [openTabs, setOpenTabs] = useState<OpenTab[]>([]);
  const [activeTabId, setActiveTabId] = useState<string>("");
  const [isAgentPanelOpen, setIsAgentPanelOpen] = useState<boolean>(true);
  const [isExplorerOpen, setIsExplorerOpen] = useState<boolean>(true);
  const [isTerminalOpen, setIsTerminalOpen] = useState<boolean>(true);
  const [savedStatus, setSavedStatus] = useState<boolean>(false);

  // Load directory tree
  const loadDirectory = useCallback(async (dirPath: string) => {
    try {
      const result = await readDirectoryTree(dirPath);
      setRootFolderPath(result.rootPath);
      setRootFolderName(result.rootName);
      setFileTree(result.tree);
    } catch (err) {
      console.warn("Could not read directory tree:", err);
    }
  }, []);

  // On mount: try to load initial folder
  useEffect(() => {
    // If in Electron, we can try to read current directory
    if (window.electronAPI?.readDirectory) {
      // Default initial load
      loadDirectory(".");
    } else {
      // Browser fallback initial files
      const defaultTab: OpenTab = {
        id: "app-tsx",
        path: "src/App.tsx",
        name: "App.tsx",
        language: "typescript",
        content: `import React from "react";
import { Header } from "./components/Header";
import { CodeEditor } from "./pages/CodeEditor";

export const App: React.FC = () => {
  return (
    <div className="min-h-screen bg-brand-bg text-brand-headline">
      <CodeEditor />
    </div>
  );
};

export default App;`,
      };
      setOpenTabs([defaultTab]);
      setActiveTabId("app-tsx");
    }
  }, [loadDirectory]);

  const handleOpenFolder = async () => {
    try {
      const selectedPath = await openFolderDialog();
      if (selectedPath) {
        await loadDirectory(selectedPath);
      }
    } catch (err) {
      console.error("Failed to open folder:", err);
    }
  };

  const handleSelectFile = async (node: TreeNode) => {
    if (node.isDirectory) return;

    // Check if already open
    const existing = openTabs.find((tab) => tab.path === node.path);
    if (existing) {
      setActiveTabId(existing.id);
      return;
    }

    // Read real file content
    try {
      let content = "";
      if (window.electronAPI?.readFile) {
        content = await readFileContent(node.path);
      }
      const newTab: OpenTab = {
        id: node.path,
        path: node.path,
        name: node.name,
        language: detectLanguage(node.name),
        content,
      };

      setOpenTabs((prev) => [...prev, newTab]);
      setActiveTabId(newTab.id);
    } catch (err) {
      console.error(`Failed to read file ${node.path}:`, err);
    }
  };

  const handleContentChange = (newContent: string) => {
    setOpenTabs((prev) =>
      prev.map((tab) =>
        tab.id === activeTabId
          ? { ...tab, content: newContent, isDirty: true }
          : tab
      )
    );
  };

  const handleSave = async () => {
    const current = openTabs.find((t) => t.id === activeTabId);
    if (!current) return;

    try {
      if (window.electronAPI?.writeFile) {
        await saveFileContent(current.path, current.content);
      }
      setOpenTabs((prev) =>
        prev.map((tab) =>
          tab.id === activeTabId ? { ...tab, isDirty: false } : tab
        )
      );
      setSavedStatus(true);
      setTimeout(() => setSavedStatus(false), 2000);
    } catch (err) {
      console.error("Save failed:", err);
    }
  };

  const handleCloseTab = (e: React.MouseEvent, tabId: string) => {
    e.stopPropagation();
    const remaining = openTabs.filter((tab) => tab.id !== tabId);
    setOpenTabs(remaining);
    if (activeTabId === tabId && remaining.length > 0) {
      setActiveTabId(remaining[remaining.length - 1].id);
    }
  };

  // Keyboard shortcut Cmd/Ctrl + S
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        handleSave();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeTabId, openTabs]);

  const activeTab =
    openTabs.find((t) => t.id === activeTabId) ||
    openTabs[0] || {
      id: "empty",
      path: "untitled.txt",
      name: "untitled.txt",
      language: "plaintext",
      content: "// No file open. Select a file from the explorer on the left or click 'Open Folder'.",
    };

  const lines = activeTab.content.split("\n");

  const getFileIcon = (name: string) => {
    const ext = name.split(".").pop()?.toLowerCase();
    switch (ext) {
      case "ts":
      case "tsx":
      case "js":
      case "jsx":
        return <Code2 className="w-3.5 h-3.5 text-blue-400 shrink-0" />;
      case "py":
        return <TerminalFileIcon className="w-3.5 h-3.5 text-emerald-400 shrink-0" />;
      case "json":
        return <FileJson className="w-3.5 h-3.5 text-amber-400 shrink-0" />;
      case "css":
      case "scss":
      case "html":
        return <Braces className="w-3.5 h-3.5 text-pink-400 shrink-0" />;
      default:
        return <FileText className="w-3.5 h-3.5 text-slate-400 shrink-0" />;
    }
  };

  return (
    <div className="h-screen w-screen flex flex-col bg-brand-bg text-brand-headline font-sans overflow-hidden transition-colors duration-200">
      {/* Top Header */}
      <Header
        status={status}
        isChecking={isCheckingStatus}
        onRefreshStatus={onRefreshStatus}
        onBackToLanding={onBackToLanding}
        activeScreen="editor"
        onOpenProjects={onOpenProjects}
        onOpenOffice={onOpenOffice}
        onOpenChat={onOpenChat}
        onOpenEditor={() => {}}
      />

      {/* Editor Sub-Header Toolbar */}
      <div className="h-10 border-b border-brand-border bg-brand-card flex items-center justify-between px-3 text-xs shrink-0 select-none transition-colors duration-200">
        <div className="flex items-center gap-2 overflow-x-auto no-scrollbar">
          <button
            type="button"
            onClick={() => setIsExplorerOpen((prev) => !prev)}
            className="p-1.5 rounded hover:bg-brand-subtle text-brand-body hover:text-brand-headline transition-colors cursor-pointer"
            title={isExplorerOpen ? "Collapse Explorer" : "Expand Explorer"}
          >
            {isExplorerOpen ? (
              <PanelLeftClose className="w-4 h-4" />
            ) : (
              <PanelLeftOpen className="w-4 h-4" />
            )}
          </button>

          <div className="h-4 w-px bg-brand-border mx-1" />

          {/* Open Tabs */}
          {openTabs.map((tab) => {
            const isActive = tab.id === activeTabId;
            return (
              <div
                key={tab.id}
                onClick={() => setActiveTabId(tab.id)}
                className={cn(
                  "flex items-center gap-2 px-3 py-1 rounded-md text-xs font-mono cursor-pointer transition-all border",
                  isActive
                    ? "bg-brand-bg text-brand-headline border-brand-border font-semibold shadow-xs"
                    : "text-brand-body hover:text-brand-headline hover:bg-brand-subtle/60 border-transparent"
                )}
              >
                {getFileIcon(tab.name)}
                <span className="truncate max-w-[140px]">{tab.name}</span>
                {tab.isDirty && (
                  <span className="w-1.5 h-1.5 rounded-full bg-brand-accent inline-block" />
                )}
                <span
                  onClick={(e) => handleCloseTab(e, tab.id)}
                  className="hover:bg-brand-subtle rounded px-1 py-0.5 text-[10px] text-brand-body hover:text-brand-headline"
                >
                  ×
                </span>
              </div>
            );
          })}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={handleSave}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-brand-subtle hover:bg-brand-subtle-hover text-brand-headline font-medium text-xs border border-brand-border transition-colors cursor-pointer shadow-xs"
            title="Save file (Cmd/Ctrl + S)"
          >
            {savedStatus ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-500" />
                <span>Saved</span>
              </>
            ) : (
              <>
                <Save className="w-3.5 h-3.5 text-brand-body" />
                <span>Save</span>
              </>
            )}
          </button>

          <button
            type="button"
            onClick={() => setIsTerminalOpen((prev) => !prev)}
            className={cn(
              "flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-xs transition-colors cursor-pointer",
              isTerminalOpen
                ? "bg-brand-accent/10 border-brand-accent/30 text-brand-accent font-semibold"
                : "bg-brand-card hover:bg-brand-subtle border-brand-border text-brand-body hover:text-brand-headline"
            )}
            title="Toggle Terminal Panel"
          >
            <TerminalIcon className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Terminal</span>
          </button>

          <button
            type="button"
            onClick={onOpenChat}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-brand-card hover:bg-brand-subtle text-brand-body hover:text-brand-headline border border-brand-border text-xs transition-colors cursor-pointer"
            title="Switch to full Chat screen"
          >
            <MessageSquare className="w-3.5 h-3.5 text-brand-accent" />
            <span className="hidden sm:inline">Full Chat</span>
          </button>

          <button
            type="button"
            onClick={() => setIsAgentPanelOpen((prev) => !prev)}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1 rounded-md font-semibold text-xs border transition-all cursor-pointer shadow-xs",
              isAgentPanelOpen
                ? "bg-brand-accent text-brand-accent-text border-brand-accent"
                : "bg-brand-card text-brand-headline hover:bg-brand-subtle border-brand-border"
            )}
            title="Toggle AI Agent Side Panel"
          >
            <Bot className="w-3.5 h-3.5" />
            <span>AI Agent</span>
            <Sparkles className="w-3 h-3 opacity-80" />
          </button>
        </div>
      </div>

      {/* Main Workspace Body */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Left Real File Tree Explorer */}
        {isExplorerOpen && (
          <aside className="w-64 border-r border-brand-border bg-brand-card/70 flex flex-col shrink-0 select-none transition-colors duration-200">
            <FileTree
              tree={fileTree}
              rootPath={rootFolderPath}
              rootName={rootFolderName}
              activeFilePath={activeTab.path}
              onSelectFile={handleSelectFile}
              onRefreshTree={() => loadDirectory(rootFolderPath || ".")}
              onOpenFolder={handleOpenFolder}
            />
          </aside>
        )}

        {/* Center Editor + Bottom Terminal Layout */}
        <div className="flex-1 flex flex-col bg-brand-bg overflow-hidden min-w-0">
          {/* Breadcrumb Bar */}
          <div className="px-4 py-2 border-b border-brand-border/60 bg-brand-subtle/20 flex items-center justify-between text-xs text-brand-body font-mono shrink-0">
            <div className="flex items-center gap-1.5 truncate">
              <span className="text-brand-headline font-medium truncate">
                {activeTab.path}
              </span>
              {activeTab.isDirty && (
                <span className="text-[10px] text-amber-500 font-sans font-semibold">
                  (Modified)
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 text-[11px] text-brand-body shrink-0">
              <span>{lines.length} lines</span>
              <span>•</span>
              <span className="uppercase">{activeTab.language}</span>
              <span>•</span>
              <span>UTF-8</span>
            </div>
          </div>

          {/* Editable Code Workspace */}
          <div className="flex-1 flex overflow-hidden relative font-mono text-xs">
            {/* Line Numbers Gutter */}
            <div className="w-12 py-3 bg-brand-subtle/30 text-brand-body/60 text-right pr-3 select-none border-r border-brand-border/60 overflow-hidden shrink-0 font-mono leading-6">
              {lines.map((_, i) => (
                <div key={i}>{i + 1}</div>
              ))}
            </div>

            {/* Editable Code Buffer */}
            <textarea
              value={activeTab.content}
              onChange={(e) => handleContentChange(e.target.value)}
              spellCheck={false}
              className="flex-1 h-full p-3 bg-transparent text-brand-headline resize-none focus:outline-none leading-6 font-mono selection:bg-brand-accent selection:text-brand-accent-text overflow-y-auto whitespace-pre tab-size-2"
              style={{
                tabSize: 2,
              }}
            />
          </div>

          {/* Status Bar */}
          <div className="h-6 px-4 bg-brand-card border-t border-brand-border flex items-center justify-between text-[11px] text-brand-body font-mono shrink-0 select-none">
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-1 text-emerald-500 font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block" />
                Ready
              </span>
              <span className="truncate max-w-[200px]">{activeTab.name}</span>
            </div>
            <div className="flex items-center gap-3">
              <span>Ln {lines.length}, Col 1</span>
              <span>Spaces: 2</span>
              <span>{activeTab.language}</span>
            </div>
          </div>

          {/* Bottom Terminal Panel */}
          <TerminalPanel
            isOpen={isTerminalOpen}
            onToggle={() => setIsTerminalOpen((prev) => !prev)}
            cwd={rootFolderPath || undefined}
          />
        </div>

        {/* Right Collapsible AI Agent Side Panel */}
        <AgentPanel
          isOpen={isAgentPanelOpen}
          onToggle={() => setIsAgentPanelOpen((prev) => !prev)}
          activeFile={{
            path: activeTab.path,
            name: activeTab.name,
            language: activeTab.language,
            content: activeTab.content,
          }}
        />
      </div>
    </div>
  );
};

export default CodeEditor;
