import { app, BrowserWindow, ipcMain, dialog, shell } from "electron";
import { spawn, spawnSync, execSync, ChildProcess } from "child_process";
import http from "http";
import path from "path";
import fs from "fs";
import * as pty from "node-pty";

let mainWindow: BrowserWindow | null = null;
let pythonProcess: ChildProcess | null = null;
const ENGINE_PORT = 8765;
const ENGINE_URL = `http://127.0.0.1:${ENGINE_PORT}`;

// Engine supervision: the app is useless without the engine, so it is restarted if it dies
// and only stopped on purpose when the app quits.
let engineStopping = false;
let engineStartedAt = 0;
let engineRestarts = 0;
let cachedPython: string | null = null;
const ENGINE_MODULES = "fastapi, uvicorn, requests, dotenv, pydantic, yaml";

// Map of active terminal PTY sessions
const ptySessions = new Map<string, pty.IPty>();

function pythonHasEngineModules(bin: string): boolean {
  try {
    const probe = spawnSync(bin, ["-c", `import ${ENGINE_MODULES}`], { stdio: "ignore", timeout: 20000 });
    return probe.status === 0;
  } catch {
    return false;
  }
}

// Picks the first Python that can actually import the engine's packages. Several Pythons are usually
// installed (system, Homebrew, python.org) and only one of them has the requirements, so taking
// whichever "python3" is first on PATH made the engine start in one terminal and fail in another.
function getPythonExecutable(): string {
  if (process.env.PYTHON_PATH) {
    return process.env.PYTHON_PATH;
  }
  if (cachedPython) return cachedPython;

  const rootDir = app.isPackaged
    ? process.resourcesPath
    : app.getAppPath();

  const isWin = process.platform === "win32";
  const candidates = isWin
    ? [
        path.join(rootDir, ".venv", "Scripts", "python.exe"),
        path.join(rootDir, "venv", "Scripts", "python.exe"),
        "python",
        "py",
      ]
    : [
        path.join(rootDir, ".venv", "bin", "python3"),
        path.join(rootDir, "venv", "bin", "python3"),
        path.join(rootDir, "engine", "venv", "bin", "python3"),
        "python3",
        "/usr/local/bin/python3",
        "/opt/homebrew/bin/python3",
        "/Library/Frameworks/Python.framework/Versions/Current/bin/python3",
        "/usr/bin/python3",
      ];

  for (const candidate of candidates) {
    if (path.isAbsolute(candidate) && !fs.existsSync(candidate)) continue;
    if (pythonHasEngineModules(candidate)) {
      cachedPython = candidate;
      return candidate;
    }
  }

  console.error(
    `[Electron] No Python with the engine packages (${ENGINE_MODULES}) was found. ` +
      `Run: python3 -m pip install -r requirements.txt`
  );
  return isWin ? "python" : "python3";
}

// A previous run that was force-quit can leave its engine holding the port; the new engine then fails
// to bind and the app silently talks to the stale one. Such an orphan (its parent is gone) is stopped.
// An engine whose parent is still alive belongs to someone (`npm run engine` in a terminal, or another
// open Autonoma window): that one is used as it is, never fought over. Returns true in that case.
function freeEnginePort(): boolean {
  if (process.platform === "win32") return false;
  let pids: string[] = [];
  try {
    pids = execSync(`lsof -nP -tiTCP:${ENGINE_PORT} -sTCP:LISTEN`, {
      encoding: "utf-8",
      stdio: ["ignore", "pipe", "ignore"],
    })
      .split(/\s+/)
      .filter(Boolean);
  } catch {
    return false; // nothing is listening
  }
  let adopted = false;
  for (const pid of pids) {
    if (Number(pid) === pythonProcess?.pid) continue;
    try {
      const info = execSync(`ps -p ${pid} -o ppid=,command=`, { encoding: "utf-8" }).trim();
      const match = info.match(/^(\d+)\s+([\s\S]*)$/);
      const parentPid = match ? Number(match[1]) : 0;
      const command = match ? match[2] : info;
      if (!/engine[\\/]main\.py/.test(command)) {
        console.error(`[Electron] Port ${ENGINE_PORT} is in use by another program: ${command}`);
      } else if (parentPid === 1) {
        console.log(`[Electron] Stopping a leftover engine from an earlier run (pid ${pid})`);
        process.kill(Number(pid), "SIGKILL");
      } else {
        console.log(`[Electron] An engine is already running on port ${ENGINE_PORT} (pid ${pid}); using it`);
        adopted = true;
      }
    } catch {
      // already gone
    }
  }
  return adopted;
}

function pingEngine(timeoutMs = 1500): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.get(`${ENGINE_URL}/auth/me`, { timeout: timeoutMs }, (res) => {
      res.resume();
      resolve((res.statusCode ?? 500) < 500);
    });
    req.on("timeout", () => {
      req.destroy();
      resolve(false);
    });
    req.on("error", () => resolve(false));
  });
}

// Resolves once the engine answers, or after maxMs so the window still opens and shows the problem.
async function waitForEngine(maxMs = 30000): Promise<boolean> {
  const deadline = Date.now() + maxMs;
  while (Date.now() < deadline) {
    if (await pingEngine()) return true;
    await new Promise((r) => setTimeout(r, 250));
  }
  console.error(`[Electron] Engine did not answer on ${ENGINE_URL} within ${maxMs / 1000}s`);
  return false;
}

function startPythonEngine() {
  if (pythonProcess) return;
  engineStopping = false;
  if (freeEnginePort()) return; // someone else's live engine already serves the port

  const pythonBin = getPythonExecutable();
  const rootDir = app.isPackaged
    ? path.join(process.resourcesPath, "engine")
    : path.join(app.getAppPath(), "engine");

  const scriptPath = path.join(rootDir, "main.py");
  const workingDir = app.isPackaged ? process.resourcesPath : app.getAppPath();

  console.log(`[Electron] Starting Python engine: ${pythonBin} ${scriptPath}`);

  try {
    const child = spawn(pythonBin, [scriptPath], {
      cwd: workingDir,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: "1",
        ENGINE_PORT: String(ENGINE_PORT),
      },
    });
    pythonProcess = child;
    engineStartedAt = Date.now();

    child.stdout?.on("data", (data) => {
      console.log(`[Python Engine] ${data.toString().trim()}`);
    });

    child.stderr?.on("data", (data) => {
      console.log(`[Python Engine] ${data.toString().trim()}`);
    });

    child.on("error", (err) => {
      console.error("[Electron] Failed to start Python engine:", err);
      if (pythonProcess === child) pythonProcess = null;
    });

    child.on("exit", (code, signal) => {
      console.log(`[Electron] Python engine exited (code: ${code}, signal: ${signal})`);
      if (pythonProcess === child) pythonProcess = null;
      if (engineStopping) return;

      // Unexpected exit: bring it back, unless it keeps dying right after start.
      if (Date.now() - engineStartedAt > 60000) engineRestarts = 0;
      if (engineRestarts < 5) {
        engineRestarts += 1;
        console.log(`[Electron] Restarting Python engine (attempt ${engineRestarts} of 5)...`);
        setTimeout(() => {
          if (!engineStopping) startPythonEngine();
        }, 1000);
      } else {
        console.error("[Electron] Python engine keeps exiting; not restarting it again.");
      }
    });
  } catch (err) {
    console.error("[Electron] Exception launching Python process:", err);
  }
}

function stopPythonEngine() {
  engineStopping = true;
  const child = pythonProcess;
  if (!child) return;
  console.log("[Electron] Terminating Python engine process...");
  try {
    child.kill("SIGTERM");
    // `killed` only means a signal was sent, so check that it really exited before escalating.
    setTimeout(() => {
      if (child.exitCode === null && child.signalCode === null) {
        try {
          child.kill("SIGKILL");
        } catch {
          // already gone
        }
      }
    }, 2000);
  } catch (e) {
    console.error("[Electron] Error terminating Python process:", e);
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

// ---------------------------------------------------------------------------
// Filesystem scope (Handbook 29.1 threats 1-2): the renderer may only touch
// folders the user explicitly opened via the folder dialog, plus the app's own
// data/projects folder. Real paths are resolved (symlinks too) before checking.
// ---------------------------------------------------------------------------
const approvedRoots = new Set<string>();

function approvedRootsFile(): string {
  return path.join(app.getPath("userData"), "approved-roots.json");
}

function loadApprovedRoots() {
  const appRoot = app.isPackaged ? process.resourcesPath : app.getAppPath();
  approvedRoots.add(resolveReal(path.join(appRoot, "data", "projects")));
  try {
    const saved = JSON.parse(fs.readFileSync(approvedRootsFile(), "utf-8"));
    if (Array.isArray(saved)) saved.forEach((r: string) => approvedRoots.add(resolveReal(r)));
  } catch {
    // no saved roots yet
  }
}

function approveRoot(dirPath: string) {
  approvedRoots.add(resolveReal(dirPath));
  try {
    fs.writeFileSync(approvedRootsFile(), JSON.stringify([...approvedRoots], null, 2), "utf-8");
  } catch (err) {
    console.warn("[Electron] Could not persist approved roots:", err);
  }
}

// realpath of the longest existing prefix, so not-yet-created paths are checked too.
function resolveReal(p: string): string {
  let current = path.resolve(p);
  const rest: string[] = [];
  while (!fs.existsSync(current)) {
    const parent = path.dirname(current);
    if (parent === current) break;
    rest.unshift(path.basename(current));
    current = parent;
  }
  let real = current;
  try {
    real = fs.realpathSync(current);
  } catch {
    // keep resolved path
  }
  return path.join(real, ...rest);
}

function assertInScope(p: string): string {
  if (!p || typeof p !== "string") throw new Error("Invalid path");
  const real = resolveReal(p);
  for (const root of approvedRoots) {
    if (real === root || real.startsWith(root + path.sep)) return real;
  }
  throw new Error(`Path is outside the opened project folders: ${p}`);
}

function registerIpcHandlers() {
  // Engine URL
  ipcMain.handle("get-engine-url", () => ENGINE_URL);

  // Open a URL in the system browser: only Google's sign-in page (used by "Continue with Google").
  ipcMain.handle("shell:openExternal", async (_event, url: string) => {
    if (typeof url !== "string" || !url.startsWith("https://accounts.google.com/")) {
      throw new Error("Only the Google sign-in page may be opened externally");
    }
    await shell.openExternal(url);
    return true;
  });

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
    approveRoot(result.filePaths[0]);
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
    assertInScope(dirPath);
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
    assertInScope(filePath);
    if (!filePath || !fs.existsSync(filePath)) {
      throw new Error(`File does not exist: ${filePath}`);
    }
    const content = await fs.promises.readFile(filePath, "utf-8");
    return content;
  });

  // File System: Write File Content
  ipcMain.handle("fs:writeFile", async (_event, filePath: string, content: string) => {
    assertInScope(filePath);
    const parentDir = path.dirname(filePath);
    if (!fs.existsSync(parentDir)) {
      await fs.promises.mkdir(parentDir, { recursive: true });
    }
    await fs.promises.writeFile(filePath, content, "utf-8");
    return { success: true, path: filePath };
  });

  // File System: Create New File
  ipcMain.handle("fs:createFile", async (_event, targetPath: string) => {
    assertInScope(targetPath);
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
    assertInScope(targetPath);
    if (fs.existsSync(targetPath)) {
      throw new Error(`Folder already exists: ${path.basename(targetPath)}`);
    }
    await fs.promises.mkdir(targetPath, { recursive: true });
    return { success: true, path: targetPath };
  });

  // File System: Delete Entry
  ipcMain.handle("fs:deleteEntry", async (_event, targetPath: string) => {
    const real = assertInScope(targetPath);
    if (approvedRoots.has(real)) {
      throw new Error("Refusing to delete an opened project root folder");
    }
    if (!fs.existsSync(targetPath)) {
      throw new Error(`Entry does not exist: ${targetPath}`);
    }
    await fs.promises.rm(targetPath, { recursive: true, force: true });
    return { success: true };
  });

  // File System: Rename Entry
  ipcMain.handle("fs:renameEntry", async (_event, oldPath: string, newPath: string) => {
    assertInScope(oldPath);
    assertInScope(newPath);
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
    assertInScope(targetDirPath);
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
app.whenReady().then(async () => {
  // Register all file system, dialog, and PTY terminal IPC handlers
  loadApprovedRoots();
  registerIpcHandlers();

  // Spawn the Python FastAPI engine and open the window only once it answers, so the first
  // screen never races the engine's startup (it used to load first and show "cannot reach engine").
  startPythonEngine();
  await waitForEngine();
  createWindow();

  app.on("activate", async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      startPythonEngine(); // no-op while it is running
      await waitForEngine();
      if (BrowserWindow.getAllWindows().length === 0) createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  closeAllPtySessions();
  if (process.platform !== "darwin") {
    app.quit(); // before-quit stops the engine
  }
  // On macOS the app stays in the Dock and reopens a window on click, so the engine keeps running.
});

app.on("before-quit", () => {
  stopPythonEngine();
  closeAllPtySessions();
});

process.on("exit", () => {
  stopPythonEngine();
  closeAllPtySessions();
});
