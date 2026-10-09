import { TreeNode, ReadDirectoryResult } from "../types/electron";

export type { TreeNode, ReadDirectoryResult };

export async function openFolderDialog(): Promise<string | null> {
  if (window.electronAPI?.openFolderDialog) {
    return await window.electronAPI.openFolderDialog();
  }
  return null;
}

export async function readDirectoryTree(dirPath: string): Promise<ReadDirectoryResult> {
  if (window.electronAPI?.readDirectory) {
    return await window.electronAPI.readDirectory(dirPath);
  }
  throw new Error("Electron API is not available in browser mode");
}

export async function readFileContent(filePath: string): Promise<string> {
  if (window.electronAPI?.readFile) {
    return await window.electronAPI.readFile(filePath);
  }
  throw new Error("Electron API is not available in browser mode");
}

export async function saveFileContent(filePath: string, content: string): Promise<{ success: boolean; path: string }> {
  if (window.electronAPI?.writeFile) {
    return await window.electronAPI.writeFile(filePath, content);
  }
  throw new Error("Electron API is not available in browser mode");
}

export async function createNewFile(filePath: string): Promise<{ success: boolean; path: string }> {
  if (window.electronAPI?.createFile) {
    return await window.electronAPI.createFile(filePath);
  }
  throw new Error("Electron API is not available in browser mode");
}

export async function createNewFolder(folderPath: string): Promise<{ success: boolean; path: string }> {
  if (window.electronAPI?.createFolder) {
    return await window.electronAPI.createFolder(folderPath);
  }
  throw new Error("Electron API is not available in browser mode");
}

export async function deleteEntry(entryPath: string): Promise<{ success: boolean }> {
  if (window.electronAPI?.deleteEntry) {
    return await window.electronAPI.deleteEntry(entryPath);
  }
  throw new Error("Electron API is not available in browser mode");
}

export async function renameEntry(oldPath: string, newPath: string): Promise<{ success: boolean; newPath: string }> {
  if (window.electronAPI?.renameEntry) {
    return await window.electronAPI.renameEntry(oldPath, newPath);
  }
  throw new Error("Electron API is not available in browser mode");
}

export async function uploadFileToFolder(targetDirPath: string): Promise<{ success: boolean; path: string; name: string } | null> {
  if (window.electronAPI?.uploadFile) {
    return await window.electronAPI.uploadFile(targetDirPath);
  }
  return null;
}
