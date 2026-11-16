// Starts Electron for `npm run dev`.
// ELECTRON_RUN_AS_NODE is set in terminals opened by VS Code-family editors and their extensions;
// with it Electron runs as plain Node, so the app crashes at startup instead of opening a window.
const { spawn } = require("child_process");
const electronPath = require("electron");

const env = { ...process.env };
delete env.ELECTRON_RUN_AS_NODE;
if (!env.VITE_DEV_SERVER_URL && !process.argv.includes("--built")) {
  env.VITE_DEV_SERVER_URL = "http://localhost:5173";
}

const child = spawn(electronPath, ["."], { stdio: "inherit", env });
child.on("close", (code) => process.exit(code === null ? 1 : code));
for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => {
    if (!child.killed) child.kill(signal);
  });
}
