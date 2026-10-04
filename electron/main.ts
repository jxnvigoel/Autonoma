import { app, BrowserWindow, ipcMain } from "electron";
import { spawn, ChildProcess } from "child_process";
import path from "path";
import fs from "fs";

let mainWindow: BrowserWindow | null = null;
let pythonProcess: ChildProcess | null = null;
const ENGINE_PORT = 8765;
const ENGINE_URL = `http://127.0.0.1:${ENGINE_PORT}`;

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

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1060,
    height: 780,
    minWidth: 840,
    minHeight: 600,
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

  // IPC handlers
  ipcMain.handle("get-engine-url", () => ENGINE_URL);

  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  stopPythonEngine();
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  stopPythonEngine();
});

process.on("exit", () => {
  stopPythonEngine();
});
