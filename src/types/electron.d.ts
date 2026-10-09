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

  // Terminal
  terminalCreate: (id: string, cwd?: string) => Promise<{ success: boolean; id: string }>;
  terminalWrite: (id: string, data: string) => Promise<boolean>;
  terminalResize: (id: string, cols: number, rows: number) => Promise<boolean>;
  terminalClose: (id: string) => Promise<boolean>;
  onTerminalData: (id: string, callback: (data: string) => void) => () => void;
  onTerminalExit: (id: string, callback: (code: number) => void) => () => void;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}
