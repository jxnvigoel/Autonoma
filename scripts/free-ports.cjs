// Runs before `npm run dev`. A dev run that was force-quit can leave its Vite server (5173) or Python
// engine (8765) behind; the next run then fails to bind the port, or the window talks to the stale copy.
// Only this app's own leftovers are stopped. Anything else on those ports is reported, not touched.
const { execSync } = require("child_process");
const path = require("path");

if (process.platform === "win32") process.exit(0);

// An Autonoma window from an earlier run goes first: it supervises its own engine and would restart it
// on the port the new run needs. Starting the app again means replacing the old one.
const electronBin = path.join(__dirname, "..", "node_modules", "electron", "dist", "Electron.app", "Contents", "MacOS", "Electron");
try {
  const rows = execSync("ps -axo pid=,command=", { encoding: "utf-8", maxBuffer: 16 * 1024 * 1024 }).split("\n");
  for (const row of rows) {
    const match = row.trim().match(/^(\d+)\s+(.*)$/);
    if (!match || !match[2].startsWith(electronBin + " ")) continue;
    try {
      process.kill(Number(match[1]), "SIGKILL");
      console.log(`[dev] Closed an Autonoma window left open from an earlier run (pid ${match[1]}).`);
    } catch {
      // already gone
    }
  }
} catch {
  // ps unavailable: the port checks below still apply
}

const PORTS = [
  { port: 5173, name: "Vite dev server", ours: /[\\/]vite(\.js)?(\s|$)|node_modules[\\/]vite[\\/]/ },
  { port: 8765, name: "Python engine", ours: /engine[\\/]main\.py/ },
];

let blocked = false;
for (const { port, name, ours } of PORTS) {
  let pids = [];
  try {
    pids = execSync(`lsof -nP -tiTCP:${port} -sTCP:LISTEN`, { encoding: "utf-8", stdio: ["ignore", "pipe", "ignore"] })
      .split(/\s+/)
      .filter(Boolean);
  } catch {
    continue; // port is free
  }
  for (const pid of pids) {
    let command = "";
    try {
      command = execSync(`ps -p ${pid} -o command=`, { encoding: "utf-8" }).trim();
    } catch {
      continue; // exited in the meantime
    }
    if (ours.test(command)) {
      try {
        process.kill(Number(pid), "SIGKILL");
        console.log(`[dev] Stopped a leftover ${name} from an earlier run (pid ${pid}, port ${port}).`);
      } catch {
        // already gone
      }
    } else {
      blocked = true;
      console.error(`[dev] Port ${port} (${name}) is in use by another program:\n      ${command}\n      Quit it, or run: kill ${pid}`);
    }
  }
}

process.exit(blocked ? 1 : 0);
