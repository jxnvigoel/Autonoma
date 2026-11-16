#!/usr/bin/env node
// Checks that this computer can run Autonoma and says exactly what to fix.
//
//   npm run doctor     full check, including a short test of the local model
//
// `npm run dev` runs it with --quick first: problems are printed, but the start is never blocked.
// Written in old-style JavaScript on purpose, so it can still report "Node is too old" on an old Node.

var childProcess = require("child_process");
var fs = require("fs");
var http = require("http");
var os = require("os");
var path = require("path");

var QUICK = process.argv.indexOf("--quick") !== -1;
var ROOT = path.join(__dirname, "..");
var IS_WIN = process.platform === "win32";
var ENGINE_MODULES = "fastapi, uvicorn, requests, dotenv, pydantic, yaml";
var MIN_NODE = [22, 12];

var fixes = [];
var notes = [];

function ok(text) {
  if (!QUICK) console.log("  OK    " + text);
}
function fix(text, how) {
  fixes.push({ text: text, how: how });
  if (!QUICK) console.log("  FIX   " + text + (how ? "\n        -> " + how : ""));
}
function note(text, how) {
  notes.push(text);
  if (!QUICK) console.log("  NOTE  " + text + (how ? "\n        -> " + how : ""));
}

function readJson(file, fallback) {
  try {
    return JSON.parse(fs.readFileSync(file, "utf-8"));
  } catch (e) {
    return fallback;
  }
}

function readEnvFile() {
  var out = {};
  try {
    fs.readFileSync(path.join(ROOT, ".env"), "utf-8")
      .split(/\r?\n/)
      .forEach(function (line) {
        var m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/);
        if (m) out[m[1]] = m[2].replace(/^["']|["']$/g, "");
      });
  } catch (e) {
    // no .env: fine, the app runs on Ollama without one
  }
  return out;
}

function run(bin, args, timeoutMs) {
  try {
    return childProcess.spawnSync(bin, args, { encoding: "utf-8", timeout: timeoutMs || 20000 });
  } catch (e) {
    return { status: 1, stdout: "", stderr: String(e) };
  }
}

function request(method, url, body, timeoutMs) {
  return new Promise(function (resolve) {
    var payload = body ? JSON.stringify(body) : null;
    var parsed;
    try {
      parsed = new URL(url);
    } catch (e) {
      return resolve({ error: "bad address " + url });
    }
    var req = http.request(
      {
        method: method,
        hostname: parsed.hostname,
        port: parsed.port || 80,
        path: parsed.pathname,
        headers: payload ? { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(payload) } : {},
        timeout: timeoutMs || 3000,
      },
      function (res) {
        var chunks = [];
        res.on("data", function (c) {
          chunks.push(c);
        });
        res.on("end", function () {
          var text = Buffer.concat(chunks).toString("utf-8");
          var json = null;
          try {
            json = JSON.parse(text);
          } catch (e) {
            // not JSON
          }
          resolve({ status: res.statusCode, json: json, text: text });
        });
      }
    );
    req.on("timeout", function () {
      req.destroy(new Error("timed out"));
    });
    req.on("error", function (e) {
      resolve({ error: e.message });
    });
    if (payload) req.write(payload);
    req.end();
  });
}

// ---------------------------------------------------------------- Node and packages

function checkNode() {
  var parts = process.versions.node.split(".").map(Number);
  var tooOld = parts[0] < MIN_NODE[0] || (parts[0] === MIN_NODE[0] && parts[1] < MIN_NODE[1]);
  if (tooOld) {
    fix(
      "Node.js " + process.versions.node + " is too old. The app window (Electron) needs Node " + MIN_NODE.join(".") + " or newer.",
      "Install the current LTS from https://nodejs.org , open a new terminal, then run: npm install"
    );
  } else {
    ok("Node.js " + process.versions.node);
  }

  var modules = path.join(ROOT, "node_modules");
  var missing = ["electron", "vite", "concurrently", "wait-on", "node-pty"].filter(function (name) {
    return !fs.existsSync(path.join(modules, name, "package.json"));
  });
  if (missing.length) {
    fix("The app's packages are not installed (" + missing.join(", ") + " missing).", "Run in this folder: npm install");
    return;
  }
  // Electron downloads its program file during `npm install`; a blocked download leaves the package empty.
  if (!fs.existsSync(path.join(modules, "electron", "path.txt"))) {
    fix("Electron's program file was not downloaded during npm install.", "Run: node node_modules/electron/install.js");
  } else {
    ok("App packages are installed");
  }
}

// ---------------------------------------------------------------- Python engine

function pythonCandidates() {
  if (process.env.PYTHON_PATH) return [process.env.PYTHON_PATH];
  // Same order as electron/main.ts, so this reports the Python the app will really use.
  return IS_WIN
    ? [path.join(ROOT, ".venv", "Scripts", "python.exe"), path.join(ROOT, "venv", "Scripts", "python.exe"), "python", "py"]
    : [
        path.join(ROOT, ".venv", "bin", "python3"),
        path.join(ROOT, "venv", "bin", "python3"),
        path.join(ROOT, "engine", "venv", "bin", "python3"),
        "python3",
        "/usr/local/bin/python3",
        "/opt/homebrew/bin/python3",
        "/Library/Frameworks/Python.framework/Versions/Current/bin/python3",
        "/usr/bin/python3",
      ];
}

function checkPython() {
  var firstWorking = null;
  var candidates = pythonCandidates();
  for (var i = 0; i < candidates.length; i++) {
    var bin = candidates[i];
    if (path.isAbsolute(bin) && !fs.existsSync(bin)) continue;
    var version = run(bin, ["-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"]);
    if (version.status !== 0) continue;
    var v = String(version.stdout).trim();
    var nums = v.split(".").map(Number);
    if (nums[0] < 3 || (nums[0] === 3 && nums[1] < 9)) continue;
    if (!firstWorking) firstWorking = { bin: bin, version: v };
    if (run(bin, ["-c", "import " + ENGINE_MODULES]).status === 0) {
      ok("Python " + v + " with the engine's packages (" + bin + ")");
      return;
    }
  }
  if (firstWorking) {
    fix(
      "Python " + firstWorking.version + " is installed, but the engine's packages are not.",
      'Run in this folder: "' + firstWorking.bin + '" -m pip install -r requirements.txt'
    );
  } else {
    fix(
      "Python 3.9 or newer was not found.",
      "Install Python from https://www.python.org/downloads/ " +
        (IS_WIN ? '(tick "Add python.exe to PATH" in the installer), ' : "") +
        "open a new terminal, then run: " + (IS_WIN ? "python" : "python3") + " -m pip install -r requirements.txt"
    );
  }
}

// ---------------------------------------------------------------- models

function localModelNames(router) {
  var names = [];
  ["high", "medium", "low"].forEach(function (tier) {
    ((router.tiers || {})[tier] || []).forEach(function (c) {
      if (c.provider === "ollama" && names.indexOf(c.model) === -1) names.push(c.model);
    });
  });
  if (router.local_default_model && names.indexOf(router.local_default_model) === -1) names.push(router.local_default_model);
  return names;
}

function installedMatch(installed, wanted) {
  for (var i = 0; i < installed.length; i++) {
    if (installed[i] === wanted || installed[i] === wanted + ":latest" || installed[i].replace(/:latest$/, "") === wanted) {
      return installed[i];
    }
  }
  return null;
}

function checkModels() {
  var router = readJson(path.join(ROOT, "config", "model_router.json"), {});
  var runtime = readJson(path.join(ROOT, "config", "runtime.json"), {});
  var env = readEnvFile();
  var key = (process.env.GROQ_API_KEY || env.GROQ_API_KEY || "").trim();
  var cloudWanted = runtime.cloud_enabled !== undefined ? !!runtime.cloud_enabled : !!router.cloud_enabled;
  var cloudOn = cloudWanted && key.length >= 10;
  var host = (process.env.OLLAMA_HOST || env.OLLAMA_HOST || "http://localhost:11434").replace(/\/+$/, "");
  var ramGb = os.totalmem() / 1073741824;
  var suggested = ramGb >= 15 ? "qwen2.5-coder:14b" : "qwen2.5-coder:7b";

  if (cloudWanted && !cloudOn) {
    fix("The cloud (Groq) is turned on in the settings, but there is no GROQ_API_KEY in the .env file.",
        'Add the key to .env, or set "cloud_enabled": false in config/model_router.json to use Ollama.');
  }
  if (cloudOn) ok("Cloud (Groq) is turned on and a key is present; Ollama is only the fallback");
  // With the cloud on, a missing Ollama is not a blocker.
  var problem = cloudOn ? note : fix;

  return request("GET", host + "/api/version", null, 3000).then(function (version) {
    if (version.error || version.status !== 200) {
      var hasBinary = run(IS_WIN ? "where" : "which", ["ollama"]).status === 0;
      problem(
        "Ollama is not running at " + host + (cloudOn ? " (only the fallback while the cloud is on)." : ". The agents cannot work without it."),
        hasBinary
          ? "Open the Ollama app (or run: ollama serve), then run this check again."
          : "Install Ollama from https://ollama.com/download , open it once, then run: ollama pull " + suggested
      );
      return;
    }
    ok("Ollama " + ((version.json || {}).version || "") + " is running at " + host);

    return request("GET", host + "/api/tags", null, 5000).then(function (tags) {
      var installed = (((tags.json || {}).models) || []).map(function (m) {
        return m.name;
      });
      var wanted = localModelNames(router);
      var usable = wanted
        .map(function (name) {
          return installedMatch(installed, name);
        })
        .filter(Boolean);
      if (!usable.length) {
        problem(
          "No model the app can use is installed in Ollama" + (installed.length ? " (installed: " + installed.join(", ") + ")." : "."),
          "Run once: ollama pull " + suggested + "   (this computer has " + Math.round(ramGb) + " GB of memory)"
        );
        return;
      }
      var model = usable[0];
      ok("Local model: " + model + " (used for every agent)");

      var size = Number((model.match(/(\d+(?:\.\d+)?)b\b/) || [])[1] || 0);
      if (size && size < 7) {
        note(model + " is a very small model. It can chat, but it is usually too weak to write a PRD, an architecture or " +
             "working code that passes the checks. Install a larger one: ollama pull " + suggested);
      }
      var needGb = size >= 30 ? 32 : size >= 14 ? 16 : size >= 7 ? 8 : 4;
      if (ramGb < needGb - 0.6) {
        note(model + " needs about " + needGb + " GB of memory and this computer has " + Math.round(ramGb) +
             " GB. It will be very slow. Use: ollama pull " + (ramGb >= 7.4 ? "qwen2.5-coder:7b" : "llama3.2:3b"));
      } else if (ramGb < 15) {
        note("This computer has " + Math.round(ramGb) + " GB of memory. Close browsers and other heavy apps while the agents work.");
      }
      if (QUICK) return;

      console.log("\n  Testing the model with one short question (the first answer loads the model and can take a minute)...");
      var started = Date.now();
      return request(
        "POST",
        host + "/api/generate",
        { model: model, prompt: "Write three short sentences about what a to-do list app does.", stream: false,
          keep_alive: "5m", options: { num_ctx: 4096, num_predict: 120, temperature: 0.2 } },
        300000
      ).then(function (res) {
        var data = res.json || {};
        if (res.error || res.status !== 200 || !String(data.response || "").trim()) {
          fix("The model did not answer the test question (" + (res.error || "HTTP " + res.status + " " + String(res.text || "").slice(0, 160)) + ").",
              "Restart the Ollama app. If it still fails, run: ollama rm " + model + "   and then: ollama pull " + model);
          return;
        }
        var speed = data.eval_count && data.eval_duration ? data.eval_count / (data.eval_duration / 1e9) : 0;
        var total = Math.round((Date.now() - started) / 1000);
        if (!speed) {
          ok("The model answered in " + total + " s");
        } else if (speed >= 20) {
          ok("The model answers at about " + Math.round(speed) + " tokens a second (good)");
        } else if (speed >= 7) {
          ok("The model answers at about " + Math.round(speed) + " tokens a second");
          note("At this speed a long step (a PRD section, a code file) takes a few minutes, and a whole project takes many hours. That is normal for a laptop.");
        } else {
          note("The model answers at only about " + speed.toFixed(1) + " tokens a second. Long steps can take 10 minutes or more and may time out. " +
               "Close other apps, or use a smaller model (ollama pull qwen2.5-coder:7b).");
        }
      });
    });
  });
}

// ---------------------------------------------------------------- main

if (!QUICK) console.log("\nAutonoma check (" + os.platform() + " " + os.arch() + ", " + Math.round(os.totalmem() / 1073741824) + " GB memory)\n");

checkNode();
checkPython();
checkModels()
  .catch(function (e) {
    note("The model check could not finish: " + (e && e.message ? e.message : e));
  })
  .then(function () {
    if (QUICK) {
      if (!fixes.length) return process.exit(0);
      console.log("\n[check] " + fixes.length + " thing" + (fixes.length === 1 ? "" : "s") + " to fix before the agents can work:");
      fixes.forEach(function (f, i) {
        console.log("[check]  " + (i + 1) + ". " + f.text + (f.how ? "\n[check]     -> " + f.how : ""));
      });
      console.log("[check] The app will still open. Full check: npm run doctor\n");
      return process.exit(0); // never blocks `npm run dev`
    }
    console.log("");
    if (!fixes.length) {
      console.log("Everything needed is in place. Start the app with: npm run dev\n");
      return process.exit(0);
    }
    console.log(fixes.length + " thing" + (fixes.length === 1 ? "" : "s") + " to fix:");
    fixes.forEach(function (f, i) {
      console.log("  " + (i + 1) + ". " + f.text + (f.how ? "\n     -> " + f.how : ""));
    });
    console.log("\nFix them in this order, then run: npm run doctor\n");
    process.exit(1);
  });
