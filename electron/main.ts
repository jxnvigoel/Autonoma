import { app, BrowserWindow, ipcMain, dialog } from "electron";
import { spawn, ChildProcess } from "child_process";
import path from "path";
import fs from "fs";
import * as pty from "node-pty";

let mainWindow: BrowserWindow | null = null;
let pythonProcess: ChildProcess | null = null;
const ENGINE_PORT = 8765;
const ENGINE_URL = `http://127.0.0.1:${ENGINE_PORT}`;

// Map of active terminal PTY sessions
const ptySessions = new Map<string, pty.IPty>();

function getPythonExecutable(): string {
  if (process.env.PYTHON_PATH) {
    return process.env.PYTHON_PATH;
  }

  const rootDir = app.isPackaged
    ? process.resourcesPath
    : app.getAppPath();

  const candidates = [
    path.join(rootDir, ".venv", "bin", "python3"),
    path.join(rootDir, "venv", "bin", "python3"),
    path.join(rootDir, "engine", "venv", "bin", "python3"),
    path.join(rootDir, ".venv", "Scripts", "python.exe"),
    path.join(rootDir, "venv", "Scripts", "python.exe"),
  ];

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }

  return process.platform === "win32" ? "python" : "python3";
}

function startPythonEngine() {
  const pythonBin = getPythonExecutable();
  const rootDir = app.isPackaged
    ? path.join(process.resourcesPath, "engine")
    : path.join(app.getAppPath(), "engine");

  const scriptPath = path.join(rootDir, "main.py");
  const workingDir = app.isPackaged ? process.resourcesPath : app.getAppPath();

  console.log(`[Electron] Starting Python engine: ${pythonBin} ${scriptPath}`);

  try {
    pythonProcess = spawn(pythonBin, [scriptPath], {
      cwd: workingDir,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: "1",
        ENGINE_PORT: String(ENGINE_PORT),
      },
    });

    pythonProcess.stdout?.on("data", (data) => {
      console.log(`[Python Engine] ${data.toString().trim()}`);
    });

    pythonProcess.stderr?.on("data", (data) => {
      console.log(`[Python Engine] ${data.toString().trim()}`);
    });

    pythonProcess.on("error", (err) => {
      console.error("[Electron] Failed to start Python engine:", err);
    });

    pythonProcess.on("exit", (code, signal) => {
      console.log(`[Electron] Python engine exited (code: ${code}, signal: ${signal})`);
      pythonProcess = null;
    });
  } catch (err) {
    console.error("[Electron] Exception launching Python process:", err);
  }
}

function stopPythonEngine() {
  if (pythonProcess && !pythonProcess.killed) {
    console.log("[Electron] Terminating Python engine process...");
    try {
      pythonProcess.kill("SIGTERM");
      setTimeout(() => {
        if (pythonProcess && !pythonProcess.killed) {
          pythonProcess.kill("SIGKILL");
        }
      }, 2000);
    } catch (e) {
      console.error("[Electron] Error terminating Python process:", e);
    }
  }
}

function closeAllPtySessions() {
  for (const [id, proc] of ptySessions.entries()) {
    try {
      proc.kill();
    } catch {
      // Ignore
    }
  }
  ptySessions.clear();
}

interface TreeNode {
  name: string;
  path: string;
  relativePath: string;
  isDirectory: boolean;
  children?: TreeNode[];
  size?: number;
}

const IGNORED_NAMES = new Set([
  "node_modules",
  ".git",
  "__pycache__",
  "dist",
  "dist-electron",
  ".DS_Store",
  ".venv",
  "venv",
  ".turbo",
  ".next",
  "build",
]);

async function readDirectoryRecursive(
  dirPath: string,
  rootPath: string,
  currentDepth: number = 0,
  maxDepth: number = 5
): Promise<TreeNode[]> {
  if (currentDepth > maxDepth) return [];

  try {
    const entries = await fs.promises.readdir(dirPath, { withFileTypes: true });
    const nodes: TreeNode[] = [];

    for (const entry of entries) {
      if (IGNORED_NAMES.has(entry.name)) {
        continue;
      }

      const fullPath = path.join(dirPath, entry.name);
      const relPath = path.relative(rootPath, fullPath);

      if (entry.isDirectory()) {
        const children = await readDirectoryRecursive(
          fullPath,
          rootPath,
          currentDepth + 1,
          maxDepth
        );
        nodes.push({
          name: entry.name,
          path: fullPath,
          relativePath: relPath,
          isDirectory: true,
          children,
        });
      } else if (entry.isFile()) {
        let size = 0;
        try {
          const stat = await fs.promises.stat(fullPath);
          size = stat.size;
        } catch {
          // ignore
        }
        nodes.push({
          name: entry.name,
          path: fullPath,
          relativePath: relPath,
          isDirectory: false,
          size,
        });
      }
    }

    // Sort: directories first, then alphabetical
    nodes.sort((a, b) => {
      if (a.isDirectory === b.isDirectory) {
        return a.name.localeCompare(b.name, undefined, { sensitivity: "base" });
      }
      return a.isDirectory ? -1 : 1;
    });

    return nodes;
  } catch (err) {
    console.error(`Error reading directory ${dirPath}:`, err);
    return [];
  }
}

function registerIpcHandlers() {
  // Engine URL
  ipcMain.handle("get-engine-url", () => ENGINE_URL);

  // Dialog: Open Folder
  ipcMain.handle("dialog:openFolder", async () => {
    if (!mainWindow) return null;
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ["openDirectory", "createDirectory"],
      title: "Select Project Folder",
    });
    if (result.canceled || result.filePaths.length === 0) {
      return null;
    }
    return result.filePaths[0];
  });

  // Dialog: Open File (for upload / picker)
  ipcMain.handle("dialog:openFile", async () => {
    if (!mainWindow) return null;
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ["openFile"],
      title: "Select File to Upload / Open",
    });
    if (result.canceled || result.filePaths.length === 0) {
      return null;
    }
    return result.filePaths[0];
  });

  // File System: Read Directory Tree
  ipcMain.handle("fs:readDirectory", async (_event, dirPath: string) => {
    if (!dirPath || !fs.existsSync(dirPath)) {
      throw new Error(`Directory does not exist: ${dirPath}`);
    }
    const tree = await readDirectoryRecursive(dirPath, dirPath);
    return {
      rootPath: dirPath,
      rootName: path.basename(dirPath),
      tree,
    };
  });

  // File System: Read File Content
  ipcMain.handle("fs:readFile", async (_event, filePath: string) => {
    if (!filePath || !fs.existsSync(filePath)) {
      throw new Error(`File does not exist: ${filePath}`);
    }
    const content = await fs.promises.readFile(filePath, "utf-8");
    return content;
  });

  // File System: Write File Content
  ipcMain.handle("fs:writeFile", async (_event, filePath: string, content: string) => {
    const parentDir = path.dirname(filePath);
    if (!fs.existsSync(parentDir)) {
      await fs.promises.mkdir(parentDir, { recursive: true });
    }
    await fs.promises.writeFile(filePath, content, "utf-8");
    return { success: true, path: filePath };
  });

  // File System: Create New File
  ipcMain.handle("fs:createFile", async (_event, targetPath: string) => {
    const parentDir = path.dirname(targetPath);
    if (!fs.existsSync(parentDir)) {
      await fs.promises.mkdir(parentDir, { recursive: true });
    }
    if (fs.existsSync(targetPath)) {
      throw new Error(`File already exists: ${path.basename(targetPath)}`);
    }
    await fs.promises.writeFile(targetPath, "", "utf-8");
    return { success: true, path: targetPath };
  });

  // File System: Create New Folder
  ipcMain.handle("fs:createFolder", async (_event, targetPath: string) => {
    if (fs.existsSync(targetPath)) {
      throw new Error(`Folder already exists: ${path.basename(targetPath)}`);
    }
    await fs.promises.mkdir(targetPath, { recursive: true });
    return { success: true, path: targetPath };
  });

  // File System: Delete Entry
  ipcMain.handle("fs:deleteEntry", async (_event, targetPath: string) => {
    if (!fs.existsSync(targetPath)) {
      throw new Error(`Entry does not exist: ${targetPath}`);
    }
    await fs.promises.rm(targetPath, { recursive: true, force: true });
    return { success: true };
  });

  // File System: Rename Entry
  ipcMain.handle("fs:renameEntry", async (_event, oldPath: string, newPath: string) => {
    if (!fs.existsSync(oldPath)) {
      throw new Error(`Source does not exist: ${oldPath}`);
    }
    if (fs.existsSync(newPath)) {
      throw new Error(`Target already exists: ${path.basename(newPath)}`);
    }
    await fs.promises.rename(oldPath, newPath);
    return { success: true, newPath };
  });

  // File System: Upload / Copy File from outside into folder
  ipcMain.handle("fs:uploadFile", async (_event, targetDirPath: string) => {
    if (!mainWindow) return null;
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ["openFile"],
      title: "Select File to Copy into Project",
    });
    if (result.canceled || result.filePaths.length === 0) {
      return null;
    }
    const sourceFile = result.filePaths[0];
    const fileName = path.basename(sourceFile);
    const destPath = path.join(targetDirPath, fileName);

    await fs.promises.copyFile(sourceFile, destPath);
    return { success: true, path: destPath, name: fileName };
  });

  // Terminal PTY: Spawn Process
  ipcMain.handle("terminal:create", (_event, id: string, cwd?: string) => {
    // Kill existing if reusing id
    if (ptySessions.has(id)) {
      try {
        ptySessions.get(id)?.kill();
      } catch {
        // ignore
      }
      ptySessions.delete(id);
    }

    const defaultShell =
      process.platform === "win32"
        ? process.env.COMSPEC || "powershell.exe"
        : process.env.SHELL || "/bin/zsh";

    const workingDir =
      cwd && fs.existsSync(cwd)
        ? cwd
        : app.getAppPath();

    console.log(`[Electron] Spawning PTY session (${id}) in ${workingDir} with ${defaultShell}`);

    try {
      const ptyProcess = pty.spawn(defaultShell, [], {
        name: "xterm-256color",
        cols: 80,
        rows: 24,
        cwd: workingDir,
        env: process.env as Record<string, string>,
      });

      ptyProcess.onData((data: string) => {
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send(`terminal:data:${id}`, data);
        }
      });

      ptyProcess.onExit(({ exitCode }) => {
        console.log(`[Electron] PTY session (${id}) exited with code ${exitCode}`);
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send(`terminal:exit:${id}`, exitCode);
        }
        ptySessions.delete(id);
      });

      ptySessions.set(id, ptyProcess);
      return { success: true, id };
    } catch (err) {
      console.error(`[Electron] Failed to spawn PTY session:`, err);
      throw err;
    }
  });

  // Terminal PTY: Write data
  ipcMain.handle("terminal:write", (_event, id: string, data: string) => {
    const proc = ptySessions.get(id);
    if (proc) {
      proc.write(data);
      return true;
    }
    return false;
  });

  // Terminal PTY: Resize
  ipcMain.handle("terminal:resize", (_event, id: string, cols: number, rows: number) => {
    const proc = ptySessions.get(id);
    if (proc && cols > 0 && rows > 0) {
      try {
        proc.resize(cols, rows);
        return true;
      } catch {
        return false;
      }
    }
    return false;
  });

  // Terminal PTY: Close
  ipcMain.handle("terminal:close", (_event, id: string) => {
    const proc = ptySessions.get(id);
    if (proc) {
      try {
        proc.kill();
      } catch {
        // ignore
      }
      ptySessions.delete(id);
      return true;
    }
    return false;
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 850,
    minWidth: 900,
    minHeight: 650,
    title: "Autonoma",
    backgroundColor: "#020617", // slate-950
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.once("ready-to-show", () => {
    mainWindow?.show();
  });

  const devServerUrl = process.env.VITE_DEV_SERVER_URL;
  if (devServerUrl) {
    mainWindow.loadURL(devServerUrl);
  } else {
    mainWindow.loadFile(path.join(app.getAppPath(), "dist", "index.html"));
  }

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

// App lifecycle
app.whenReady().then(() => {
  // Spawn Python FastAPI engine
  startPythonEngine();

  // Register all file system, dialog, and PTY terminal IPC handlers
  registerIpcHandlers();

  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  stopPythonEngine();
  closeAllPtySessions();
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  stopPythonEngine();
  closeAllPtySessions();
});

process.on("exit", () => {
  stopPythonEngine();
  closeAllPtySessions();
});
