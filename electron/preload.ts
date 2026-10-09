import { contextBridge, ipcRenderer } from "electron";

export interface TreeNode {
  name: string;
  path: string;
  relativePath: string;
  isDirectory: boolean;
  children?: TreeNode[];
  size?: number;
}

export interface ReadDirectoryResult {
  rootPath: string;
  rootName: string;
  tree: TreeNode[];
}

export interface ElectronAPI {
  platform: string;
  getEngineUrl: () => Promise<string>;
  openFolderDialog: () => Promise<string | null>;
  openFileDialog: () => Promise<string | null>;
  readDirectory: (dirPath: string) => Promise<ReadDirectoryResult>;
  readFile: (filePath: string) => Promise<string>;
  writeFile: (filePath: string, content: string) => Promise<{ success: boolean; path: string }>;
  createFile: (filePath: string) => Promise<{ success: boolean; path: string }>;
  createFolder: (folderPath: string) => Promise<{ success: boolean; path: string }>;
  deleteEntry: (entryPath: string) => Promise<{ success: boolean }>;
  renameEntry: (oldPath: string, newPath: string) => Promise<{ success: boolean; newPath: string }>;
  uploadFile: (targetDirPath: string) => Promise<{ success: boolean; path: string; name: string } | null>;

  // Terminal PTY
  terminalCreate: (id: string, cwd?: string) => Promise<{ success: boolean; id: string }>;
  terminalWrite: (id: string, data: string) => Promise<boolean>;
  terminalResize: (id: string, cols: number, rows: number) => Promise<boolean>;
  terminalClose: (id: string) => Promise<boolean>;
  onTerminalData: (id: string, callback: (data: string) => void) => () => void;
  onTerminalExit: (id: string, callback: (code: number) => void) => () => void;
}

const electronAPI: ElectronAPI = {
  platform: process.platform,
  getEngineUrl: () => ipcRenderer.invoke("get-engine-url"),
  openFolderDialog: () => ipcRenderer.invoke("dialog:openFolder"),
  openFileDialog: () => ipcRenderer.invoke("dialog:openFile"),
  readDirectory: (dirPath: string) => ipcRenderer.invoke("fs:readDirectory", dirPath),
  readFile: (filePath: string) => ipcRenderer.invoke("fs:readFile", filePath),
  writeFile: (filePath: string, content: string) => ipcRenderer.invoke("fs:writeFile", filePath, content),
  createFile: (filePath: string) => ipcRenderer.invoke("fs:createFile", filePath),
  createFolder: (folderPath: string) => ipcRenderer.invoke("fs:createFolder", folderPath),
  deleteEntry: (entryPath: string) => ipcRenderer.invoke("fs:deleteEntry", entryPath),
  renameEntry: (oldPath: string, newPath: string) => ipcRenderer.invoke("fs:renameEntry", oldPath, newPath),
  uploadFile: (targetDirPath: string) => ipcRenderer.invoke("fs:uploadFile", targetDirPath),

  // Terminal PTY
  terminalCreate: (id: string, cwd?: string) => ipcRenderer.invoke("terminal:create", id, cwd),
  terminalWrite: (id: string, data: string) => ipcRenderer.invoke("terminal:write", id, data),
  terminalResize: (id: string, cols: number, rows: number) => ipcRenderer.invoke("terminal:resize", id, cols, rows),
  terminalClose: (id: string) => ipcRenderer.invoke("terminal:close", id),

  onTerminalData: (id: string, callback: (data: string) => void) => {
    const channel = `terminal:data:${id}`;
    const listener = (_: Electron.IpcRendererEvent, data: string) => callback(data);
    ipcRenderer.on(channel, listener);
    return () => {
      ipcRenderer.removeListener(channel, listener);
    };
  },

  onTerminalExit: (id: string, callback: (code: number) => void) => {
    const channel = `terminal:exit:${id}`;
    const listener = (_: Electron.IpcRendererEvent, code: number) => callback(code);
    ipcRenderer.on(channel, listener);
    return () => {
      ipcRenderer.removeListener(channel, listener);
    };
  },
};

contextBridge.exposeInMainWorld("electronAPI", electronAPI);
