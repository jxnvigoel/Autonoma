import React, { useState } from "react";
import {
  Folder,
  FolderOpen,
  ChevronRight,
  ChevronDown,
  FilePlus,
  FolderPlus,
  Upload,
  RefreshCw,
  Trash2,
  Edit2,
  Code2,
  Terminal,
  FileJson,
  Braces,
  FileText,
  MoreVertical,
  Check,
  X,
} from "lucide-react";
import { TreeNode } from "../../types/electron";
import {
  createNewFile,
  createNewFolder,
  deleteEntry,
  renameEntry,
  uploadFileToFolder,
} from "../../lib/fs";
import { cn } from "../../lib/utils";

interface FileTreeProps {
  tree: TreeNode[];
  rootPath: string;
  rootName: string;
  activeFilePath?: string;
  onSelectFile: (node: TreeNode) => void;
  onRefreshTree: () => void;
  onOpenFolder: () => void;
}

interface InlineCreationState {
  targetDirPath: string;
  type: "file" | "folder";
}

interface InlineRenameState {
  targetPath: string;
  currentName: string;
}

export const FileTree: React.FC<FileTreeProps> = ({
  tree,
  rootPath,
  rootName,
  activeFilePath,
  onSelectFile,
  onRefreshTree,
  onOpenFolder,
}) => {
  const [collapsedPaths, setCollapsedPaths] = useState<Set<string>>(new Set());
  const [creationState, setCreationState] = useState<InlineCreationState | null>(null);
  const [creationName, setCreationName] = useState<string>("");
  const [renameState, setRenameState] = useState<InlineRenameState | null>(null);
  const [renameName, setRenameName] = useState<string>("");
  const [contextMenuPath, setContextMenuPath] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const toggleCollapse = (path: string) => {
    setCollapsedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    setActionError(null);
    try {
      await onRefreshTree();
    } finally {
      setTimeout(() => setIsRefreshing(false), 300);
    }
  };

  const startCreation = (dirPath: string, type: "file" | "folder") => {
    setCreationState({ targetDirPath: dirPath, type });
    setCreationName("");
    setRenameState(null);
    setContextMenuPath(null);
    setActionError(null);
  };

  const submitCreation = async () => {
    if (!creationState || !creationName.trim()) {
      setCreationState(null);
      return;
    }

    const separator = creationState.targetDirPath.includes("\\") ? "\\" : "/";
    const fullTargetPath = `${creationState.targetDirPath}${separator}${creationName.trim()}`;

    try {
      if (creationState.type === "file") {
        await createNewFile(fullTargetPath);
      } else {
        await createNewFolder(fullTargetPath);
      }
      setCreationState(null);
      setCreationName("");
      onRefreshTree();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setActionError(msg);
    }
  };

  const startRename = (targetPath: string, currentName: string) => {
    setRenameState({ targetPath, currentName });
    setRenameName(currentName);
    setCreationState(null);
    setContextMenuPath(null);
    setActionError(null);
  };

  const submitRename = async () => {
    if (!renameState || !renameName.trim() || renameName === renameState.currentName) {
      setRenameState(null);
      return;
    }

    const parentDir = renameState.targetPath.substring(
      0,
      Math.max(
        renameState.targetPath.lastIndexOf("/"),
        renameState.targetPath.lastIndexOf("\\")
      )
    );
    const separator = renameState.targetPath.includes("\\") ? "\\" : "/";
    const newFullPath = `${parentDir}${separator}${renameName.trim()}`;

    try {
      await renameEntry(renameState.targetPath, newFullPath);
      setRenameState(null);
      setRenameName("");
      onRefreshTree();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setActionError(msg);
    }
  };

  const handleDelete = async (targetPath: string) => {
    setContextMenuPath(null);
    try {
      await deleteEntry(targetPath);
      onRefreshTree();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setActionError(msg);
    }
  };

  const handleUpload = async (targetDirPath: string) => {
    setContextMenuPath(null);
    try {
      const res = await uploadFileToFolder(targetDirPath);
      if (res) {
        onRefreshTree();
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setActionError(msg);
    }
  };

  const getFileIcon = (name: string) => {
    const ext = name.split(".").pop()?.toLowerCase();
    switch (ext) {
      case "ts":
      case "tsx":
      case "js":
      case "jsx":
        return <Code2 className="w-3.5 h-3.5 text-blue-400 shrink-0" />;
      case "py":
        return <Terminal className="w-3.5 h-3.5 text-emerald-400 shrink-0" />;
      case "json":
        return <FileJson className="w-3.5 h-3.5 text-amber-400 shrink-0" />;
      case "css":
      case "scss":
      case "html":
        return <Braces className="w-3.5 h-3.5 text-pink-400 shrink-0" />;
      case "md":
      case "txt":
        return <FileText className="w-3.5 h-3.5 text-slate-400 shrink-0" />;
      default:
        return <FileText className="w-3.5 h-3.5 text-indigo-400 shrink-0" />;
    }
  };

  const renderNode = (node: TreeNode, depth: number = 0) => {
    const isCollapsed = collapsedPaths.has(node.path);
    const isSelected = activeFilePath === node.path;
    const isRenaming = renameState?.targetPath === node.path;
    const isCreatingInside =
      creationState?.targetDirPath === node.path && node.isDirectory;

    if (node.isDirectory) {
      return (
        <div key={node.path} className="flex flex-col select-none">
          <div
            className={cn(
              "group/item flex items-center justify-between px-2 py-1 rounded-md text-xs transition-colors cursor-pointer relative",
              "hover:bg-brand-subtle/70 text-brand-headline font-medium"
            )}
            style={{ paddingLeft: `${depth * 14 + 8}px` }}
            onClick={() => toggleCollapse(node.path)}
          >
            <div className="flex items-center gap-1.5 min-w-0 flex-1">
              <span className="text-brand-body/70">
                {isCollapsed ? (
                  <ChevronRight className="w-3 h-3" />
                ) : (
                  <ChevronDown className="w-3 h-3" />
                )}
              </span>
              {isCollapsed ? (
                <Folder className="w-3.5 h-3.5 text-amber-500/80 fill-amber-500/20 shrink-0" />
              ) : (
                <FolderOpen className="w-3.5 h-3.5 text-amber-500 fill-amber-500/30 shrink-0" />
              )}

              {isRenaming ? (
                <div
                  className="flex items-center gap-1 flex-1"
                  onClick={(e) => e.stopPropagation()}
                >
                  <input
                    type="text"
                    value={renameName}
                    onChange={(e) => setRenameName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") submitRename();
                      if (e.key === "Escape") setRenameState(null);
                    }}
                    autoFocus
                    className="flex-1 bg-brand-bg px-1.5 py-0.5 rounded border border-brand-accent text-xs font-mono text-brand-headline focus:outline-none"
                  />
                  <button
                    onClick={submitRename}
                    className="text-emerald-500 hover:text-emerald-400"
                  >
                    <Check className="w-3 h-3" />
                  </button>
                  <button
                    onClick={() => setRenameState(null)}
                    className="text-brand-body hover:text-brand-headline"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ) : (
                <span className="truncate text-xs font-mono">{node.name}</span>
              )}
            </div>

            {/* Hover Actions for Folder */}
            {!isRenaming && (
              <div
                className="opacity-0 group-hover/item:opacity-100 flex items-center gap-0.5"
                onClick={(e) => e.stopPropagation()}
              >
                <button
                  type="button"
                  onClick={() => startCreation(node.path, "file")}
                  className="p-1 rounded hover:bg-brand-card text-brand-body hover:text-brand-headline transition-colors"
                  title="New File inside this folder"
                >
                  <FilePlus className="w-3 h-3" />
                </button>
                <button
                  type="button"
                  onClick={() => startCreation(node.path, "folder")}
                  className="p-1 rounded hover:bg-brand-card text-brand-body hover:text-brand-headline transition-colors"
                  title="New Folder inside this folder"
                >
                  <FolderPlus className="w-3 h-3" />
                </button>
                <button
                  type="button"
                  onClick={() => handleUpload(node.path)}
                  className="p-1 rounded hover:bg-brand-card text-brand-body hover:text-brand-headline transition-colors"
                  title="Upload / Copy file here"
                >
                  <Upload className="w-3 h-3" />
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setContextMenuPath(
                      contextMenuPath === node.path ? null : node.path
                    )
                  }
                  className="p-1 rounded hover:bg-brand-card text-brand-body hover:text-brand-headline transition-colors"
                  title="More actions"
                >
                  <MoreVertical className="w-3 h-3" />
                </button>
              </div>
            )}

            {/* Folder Context Menu Dropdown */}
            {contextMenuPath === node.path && (
              <div
                className="absolute right-2 top-7 z-30 bg-brand-card border border-brand-border rounded-lg shadow-lg p-1 min-w-[130px] flex flex-col gap-0.5 text-xs font-sans"
                onClick={(e) => e.stopPropagation()}
              >
                <button
                  onClick={() => startRename(node.path, node.name)}
                  className="w-full text-left px-2 py-1 rounded hover:bg-brand-subtle flex items-center gap-2 text-brand-headline"
                >
                  <Edit2 className="w-3 h-3 text-brand-body" />
                  <span>Rename</span>
                </button>
                <button
                  onClick={() => handleDelete(node.path)}
                  className="w-full text-left px-2 py-1 rounded hover:bg-rose-500/20 text-rose-500 flex items-center gap-2"
                >
                  <Trash2 className="w-3 h-3" />
                  <span>Delete</span>
                </button>
              </div>
            )}
          </div>

          {/* Children & Inline Creation */}
          {!isCollapsed && (
            <div className="flex flex-col">
              {isCreatingInside && (
                <div
                  className="flex items-center gap-1 py-1 pr-2 rounded"
                  style={{ paddingLeft: `${(depth + 1) * 14 + 8}px` }}
                >
                  {creationState.type === "file" ? (
                    <FilePlus className="w-3.5 h-3.5 text-brand-accent shrink-0" />
                  ) : (
                    <FolderPlus className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                  )}
                  <input
                    type="text"
                    placeholder={
                      creationState.type === "file" ? "filename.ts" : "folder-name"
                    }
                    value={creationName}
                    onChange={(e) => setCreationName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") submitCreation();
                      if (e.key === "Escape") setCreationState(null);
                    }}
                    autoFocus
                    className="flex-1 bg-brand-bg px-1.5 py-0.5 rounded border border-brand-accent text-xs font-mono text-brand-headline focus:outline-none"
                  />
                  <button
                    onClick={submitCreation}
                    className="text-emerald-500 hover:text-emerald-400"
                  >
                    <Check className="w-3 h-3" />
                  </button>
                  <button
                    onClick={() => setCreationState(null)}
                    className="text-brand-body hover:text-brand-headline"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              )}

              {node.children &&
                node.children.map((child) => renderNode(child, depth + 1))}
            </div>
          )}
        </div>
      );
    }

    // Render File Node
    return (
      <div
        key={node.path}
        className={cn(
          "group/item flex items-center justify-between px-2 py-1 rounded-md text-xs font-mono transition-all cursor-pointer relative",
          isSelected
            ? "bg-brand-accent/15 text-brand-accent font-semibold border-l-2 border-brand-accent"
            : "text-brand-body hover:text-brand-headline hover:bg-brand-subtle/60"
        )}
        style={{ paddingLeft: `${depth * 14 + 18}px` }}
        onClick={() => onSelectFile(node)}
      >
        <div className="flex items-center gap-1.5 min-w-0 flex-1">
          {getFileIcon(node.name)}
          {isRenaming ? (
            <div
              className="flex items-center gap-1 flex-1"
              onClick={(e) => e.stopPropagation()}
            >
              <input
                type="text"
                value={renameName}
                onChange={(e) => setRenameName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") submitRename();
                  if (e.key === "Escape") setRenameState(null);
                }}
                autoFocus
                className="flex-1 bg-brand-bg px-1.5 py-0.5 rounded border border-brand-accent text-xs font-mono text-brand-headline focus:outline-none"
              />
              <button
                onClick={submitRename}
                className="text-emerald-500 hover:text-emerald-400"
              >
                <Check className="w-3 h-3" />
              </button>
              <button
                onClick={() => setRenameState(null)}
                className="text-brand-body hover:text-brand-headline"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          ) : (
            <span className="truncate">{node.name}</span>
          )}
        </div>

        {/* Hover Actions for File */}
        {!isRenaming && (
          <div
            className="opacity-0 group-hover/item:opacity-100 flex items-center gap-0.5"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              onClick={() => startRename(node.path, node.name)}
              className="p-1 rounded hover:bg-brand-card text-brand-body hover:text-brand-headline transition-colors"
              title="Rename file"
            >
              <Edit2 className="w-3 h-3" />
            </button>
            <button
              type="button"
              onClick={() => handleDelete(node.path)}
              className="p-1 rounded hover:bg-brand-card text-brand-body hover:text-rose-500 transition-colors"
              title="Delete file"
            >
              <Trash2 className="w-3 h-3" />
            </button>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden select-none">
      {/* Explorer Top Toolbar */}
      <div className="p-2 border-b border-brand-border flex items-center justify-between text-xs font-semibold shrink-0 bg-brand-card/40">
        <div className="flex items-center gap-1.5 truncate">
          <span className="text-[10px] uppercase tracking-wider text-brand-body font-bold">
            Project
          </span>
          <span className="text-[11px] font-mono text-brand-headline truncate font-semibold">
            {rootName || "No folder open"}
          </span>
        </div>

        <div className="flex items-center gap-0.5">
          <button
            type="button"
            onClick={() => startCreation(rootPath, "file")}
            className="p-1 rounded hover:bg-brand-subtle text-brand-body hover:text-brand-headline transition-colors cursor-pointer"
            title="New File in root"
          >
            <FilePlus className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={() => startCreation(rootPath, "folder")}
            className="p-1 rounded hover:bg-brand-subtle text-brand-body hover:text-brand-headline transition-colors cursor-pointer"
            title="New Folder in root"
          >
            <FolderPlus className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={() => handleUpload(rootPath)}
            className="p-1 rounded hover:bg-brand-subtle text-brand-body hover:text-brand-headline transition-colors cursor-pointer"
            title="Upload / Copy file into root"
          >
            <Upload className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={handleRefresh}
            className="p-1 rounded hover:bg-brand-subtle text-brand-body hover:text-brand-headline transition-colors cursor-pointer"
            title="Refresh Explorer"
          >
            <RefreshCw
              className={cn("w-3.5 h-3.5", isRefreshing && "animate-spin")}
            />
          </button>
        </div>
      </div>

      {/* Action error notice */}
      {actionError && (
        <div className="p-2 bg-rose-500/10 border-b border-rose-500/30 text-rose-500 text-[11px] flex items-center justify-between">
          <span className="truncate">{actionError}</span>
          <button onClick={() => setActionError(null)}>
            <X className="w-3 h-3" />
          </button>
        </div>
      )}

      {/* Tree View Body */}
      <div className="flex-1 overflow-y-auto p-1.5 space-y-0.5">
        {/* Open Folder CTA Button */}
        <div className="px-1.5 pb-2">
          <button
            type="button"
            onClick={onOpenFolder}
            className="w-full flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-lg bg-brand-subtle hover:bg-brand-subtle-hover text-brand-headline border border-brand-border text-xs font-medium transition-all shadow-xs cursor-pointer active:scale-98"
          >
            <FolderOpen className="w-3.5 h-3.5 text-brand-accent" />
            <span>Open Folder...</span>
          </button>
        </div>

        {/* Root Inline Creation */}
        {creationState?.targetDirPath === rootPath && (
          <div className="flex items-center gap-1 py-1 px-2 rounded bg-brand-subtle/50 mb-1">
            {creationState.type === "file" ? (
              <FilePlus className="w-3.5 h-3.5 text-brand-accent shrink-0" />
            ) : (
              <FolderPlus className="w-3.5 h-3.5 text-amber-500 shrink-0" />
            )}
            <input
              type="text"
              placeholder={
                creationState.type === "file" ? "filename.ts" : "folder-name"
              }
              value={creationName}
              onChange={(e) => setCreationName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") submitCreation();
                if (e.key === "Escape") setCreationState(null);
              }}
              autoFocus
              className="flex-1 bg-brand-bg px-1.5 py-0.5 rounded border border-brand-accent text-xs font-mono text-brand-headline focus:outline-none"
            />
            <button
              onClick={submitCreation}
              className="text-emerald-500 hover:text-emerald-400"
            >
              <Check className="w-3 h-3" />
            </button>
            <button
              onClick={() => setCreationState(null)}
              className="text-brand-body hover:text-brand-headline"
            >
              <X className="w-3 h-3" />
            </button>
          </div>
        )}

        {tree.length === 0 ? (
          <div className="p-4 text-center text-xs text-brand-body space-y-2 my-auto">
            <p>No files loaded.</p>
            <p className="text-[11px] text-brand-body/70">
              Click "Open Folder..." above to browse your project files.
            </p>
          </div>
        ) : (
          tree.map((node) => renderNode(node, 0))
        )}
      </div>
    </div>
  );
};

export default FileTree;
