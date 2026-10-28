"""
DevOps / SRE code layer (Handbook 16.2, 23.4.1, 2.7.9-2.7.10, 18.7).

The DevOps agent writes Dockerfile / CI / runbook prose as a story like any other; this module
is the deterministic part that must never be simulated in text:
- command allowlist: proposed from the architecture's stack, validated, approved by the client
- CI: lint -> typecheck -> test from the allowlist; nothing merges on red
- preview: one command brings up the app on 127.0.0.1 with seed data; health-checked;
  runtime errors captured from its log
- release drills: rollback (previous release still builds and runs) and backup/restore
- runbook: rendered only from commands that were actually run, with their results
- Dockerfile checks: pinned base image, non-root user, HEALTHCHECK, no secrets
"""

import os
import re
import json
import time
import shlex
import socket
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

try:
    from sandbox import Sandbox, validate_allowlist, scrubbed_env
    import workspace
except ImportError:
    from engine.sandbox import Sandbox, validate_allowlist, scrubbed_env
    from engine import workspace

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PROJECTS_DIR = os.path.join(PROJECT_ROOT, "data", "projects")

CI_STEPS = ["lint", "typecheck", "test"]

STACK_ALLOWLISTS: Dict[str, Dict[str, str]] = {
    # Standard-library Python needs no package install, so it builds fully offline.
    "python": {
        "lint": "python3 -m compileall -q src tests",
        "test": "python3 -m unittest discover -s tests -t . -q",
        "seed": "python3 -m src.seed",
        "preview": "python3 -m src.server",
        "backup": "python3 -m src.backup",
        "restore": "python3 -m src.restore",
    },
    "node": {
        "install": "npm ci",
        "lint": "npm run lint --if-present",
        "typecheck": "npx tsc --noEmit",
        "test": "npm test --silent",
        "build": "npm run build --if-present",
        "seed": "npm run seed --if-present",
        "preview": "npm start",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_dir(session_id: str, projects_dir: str = DATA_PROJECTS_DIR) -> str:
    return os.path.join(projects_dir, session_id)


def _load(path: str, default: Any) -> Any:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def _save(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ------------------------------------------------------------------ allowlist

def detect_stack(architecture_text: str) -> Dict[str, str]:
    """Picks the allowlist family from the architecture's stack decisions."""
    t = (architecture_text or "").lower()
    node_hits = sum(t.count(w) for w in ("node.js", "nodejs", "express", "typescript", "react", "next.js", "npm"))
    py_hits = sum(t.count(w) for w in ("python", "fastapi", "flask", "django", "sqlite3"))
    if node_hits > py_hits:
        return {"stack": "node", "reason": f"architecture mentions Node/TypeScript tooling {node_hits}x vs Python {py_hits}x"}
    if py_hits:
        return {"stack": "python", "reason": f"architecture mentions Python tooling {py_hits}x vs Node {node_hits}x"}
    return {"stack": "python", "reason": "no stack named in architecture; ASM: Python standard library (builds offline)"}


def allowlist_path(session_id: str, projects_dir: str = DATA_PROJECTS_DIR) -> str:
    return os.path.join(_project_dir(session_id, projects_dir), "command_allowlist.json")


def propose_allowlist(session_id: str, projects_dir: str = DATA_PROJECTS_DIR) -> Dict[str, Any]:
    pdir = _project_dir(session_id, projects_dir)
    arch = ""
    arch_path = os.path.join(pdir, "docs", "architecture.md")
    if os.path.exists(arch_path):
        with open(arch_path, "r", encoding="utf-8") as f:
            arch = f.read()
    existing = _load(allowlist_path(session_id, projects_dir), None)
    if existing and existing.get("approved"):
        return existing
    stack = detect_stack(arch)
    commands = dict(STACK_ALLOWLISTS[stack["stack"]])
    record = {
        "session_id": session_id,
        "stack": stack["stack"],
        "stack_reason": stack["reason"],
        "commands": commands,
        "problems": validate_allowlist(commands),
        "network_allowed": False,
        "approved": False,
        "proposed_at": _now(),
        "note": "Agents call run(<id>) only. Commands needing network ('install') stay disabled unless network is approved.",
    }
    _save(allowlist_path(session_id, projects_dir), record)
    return record


def approve_allowlist(session_id: str, commands: Optional[Dict[str, str]] = None, network_allowed: bool = False,
                      projects_dir: str = DATA_PROJECTS_DIR) -> Dict[str, Any]:
    record = _load(allowlist_path(session_id, projects_dir), None) or propose_allowlist(session_id, projects_dir)
    if commands is not None:
        record["commands"] = commands
    problems = validate_allowlist(record["commands"])
    if problems:
        record.update({"approved": False, "problems": problems})
        _save(allowlist_path(session_id, projects_dir), record)
        raise ValueError("allowlist rejected: " + "; ".join(problems))
    record.update({"approved": True, "approved_at": _now(), "problems": [], "network_allowed": bool(network_allowed)})
    _save(allowlist_path(session_id, projects_dir), record)
    return record


def get_allowlist(session_id: str, projects_dir: str = DATA_PROJECTS_DIR) -> Dict[str, Any]:
    return _load(allowlist_path(session_id, projects_dir), {"approved": False, "commands": {}})


# ------------------------------------------------------------------ CI

def run_ci(sandbox: Sandbox) -> Dict[str, Any]:
    """Runs the CI steps present in the allowlist, in order. Green only if every step passed."""
    steps = []
    for step in CI_STEPS:
        if step not in sandbox.allowlist:
            continue
        res = sandbox.run(step)
        steps.append(res)
        if not res["ok"]:
            break
    green = bool(steps) and all(s["ok"] for s in steps) and any(s["command_id"] == "test" for s in steps)
    if not any(s["command_id"] == "test" for s in steps) and all(s["ok"] for s in steps):
        reason = "no test step ran (CI needs a 'test' command)"
    else:
        reason = "" if green else f"step '{steps[-1]['command_id']}' failed"
    return {"green": green, "steps": steps, "reason": reason, "at": _now()}


def ci_feedback(ci: Dict[str, Any]) -> str:
    lines = [f"CI is RED: {ci['reason']}"]
    for s in ci["steps"]:
        lines.append(f"- {s['command_id']} ({s['command']}): exit {s['exit_code']}")
        if not s["ok"]:
            for k in ("failing_tests", "first_error"):
                if s.get(k):
                    lines.append(f"  {k}: {s[k] if isinstance(s[k], str) else ', '.join(s[k])}")
    return "\n".join(lines)


# ------------------------------------------------------------------ preview

def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _preview_state_path(session_id: str, projects_dir: str) -> str:
    return os.path.join(_project_dir(session_id, projects_dir), "preview_state.json")


def capture_runtime_errors(log_path: str) -> List[str]:
    """Stage 8: runtime errors are captured automatically from the preview log."""
    if not os.path.exists(log_path):
        return []
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    errors = re.findall(r"Traceback \(most recent call last\):[\s\S]*?\n(?=\S)[^\n]*", text)
    errors += [l for l in text.splitlines() if re.search(r"\b(ERROR|Unhandled|Exception)\b", l) and "Traceback" not in l]
    return [e.strip()[:1500] for e in errors][:20]


def health_check(url: str, paths: Optional[List[str]] = None, timeout_s: float = 20.0) -> Dict[str, Any]:
    deadline = time.time() + timeout_s
    paths = paths or ["/health", "/api/v1/health", "/healthz", "/"]
    last = ""
    while time.time() < deadline:
        for p in paths:
            try:
                r = requests.get(url + p, timeout=2)
                if r.status_code == 200:
                    return {"ok": True, "path": p, "status": r.status_code, "body": r.text[:300]}
                last = f"{p}: HTTP {r.status_code}"
            except requests.RequestException as e:
                last = f"{p}: {type(e).__name__}"
        time.sleep(0.5)
    return {"ok": False, "detail": last or "no response"}


def start_preview(session_id: str, cwd: Optional[str] = None, projects_dir: str = DATA_PROJECTS_DIR,
                  label: str = "preview") -> Dict[str, Any]:
    """Brings up the app from the main repo (or `cwd`) on 127.0.0.1 with seed data."""
    stop_preview(session_id, projects_dir)
    allow = get_allowlist(session_id, projects_dir)
    if not allow.get("approved"):
        return {"ok": False, "error": "command allowlist not approved"}
    if "preview" not in allow["commands"]:
        return {"ok": False, "error": "no 'preview' command in the allowlist"}
    repo = cwd or workspace.repo_path(session_id, projects_dir)
    pdir = _project_dir(session_id, projects_dir)
    log_dir = os.path.join(pdir, ".virtualoffice", "logs")
    os.makedirs(log_dir, exist_ok=True)
    port = _free_port()
    env = scrubbed_env(os.path.join(pdir, ".virtualoffice", ".sandbox-home"), allow.get("network_allowed", False))
    env.update({"PORT": str(port), "HOST": "127.0.0.1", "APP_DATA_DIR": os.path.join(pdir, ".virtualoffice", f"{label}-data")})
    os.makedirs(env["APP_DATA_DIR"], exist_ok=True)
    os.makedirs(env["HOME"], exist_ok=True)

    seed = None
    if "seed" in allow["commands"]:
        proc = subprocess.run(shlex.split(allow["commands"]["seed"]), cwd=repo, env=env,
                              capture_output=True, text=True, timeout=120)
        seed = {"command": allow["commands"]["seed"], "exit_code": proc.returncode,
                "output": ((proc.stdout or "") + (proc.stderr or ""))[-1500:]}

    log_path = os.path.join(log_dir, f"{label}-{int(time.time())}.log")
    log_f = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(shlex.split(allow["commands"]["preview"]), cwd=repo, env=env,
                            stdout=log_f, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}"
    health = health_check(url)
    state = {"session_id": session_id, "pid": proc.pid, "port": port, "url": url, "cwd": repo, "label": label,
             "command": allow["commands"]["preview"], "started_at": _now(), "health": health, "seed": seed,
             "log_path": log_path, "running": proc.poll() is None,
             "runtime_errors": capture_runtime_errors(log_path)}
    if not health["ok"]:
        proc.terminate()
        state["running"] = False
        time.sleep(0.3)
        state["runtime_errors"] = capture_runtime_errors(log_path)
    _save(_preview_state_path(session_id, projects_dir), state)
    state["ok"] = health["ok"]
    return state


def stop_preview(session_id: str, projects_dir: str = DATA_PROJECTS_DIR) -> None:
    state = _load(_preview_state_path(session_id, projects_dir), None)
    if not state or not state.get("pid"):
        return
    try:
        os.kill(int(state["pid"]), 15)
    except (ProcessLookupError, PermissionError, OSError):
        pass
    state["running"] = False
    state["stopped_at"] = _now()
    _save(_preview_state_path(session_id, projects_dir), state)


def get_preview_state(session_id: str, projects_dir: str = DATA_PROJECTS_DIR) -> Dict[str, Any]:
    state = _load(_preview_state_path(session_id, projects_dir), {"running": False})
    if state.get("log_path"):
        state["runtime_errors"] = capture_runtime_errors(state["log_path"])
    return state


# ------------------------------------------------------------------ release drills

def _run_recorded(cmd_id: str, allow: Dict[str, Any], cwd: str, env_extra: Optional[Dict[str, str]],
                  pdir: str) -> Dict[str, Any]:
    env = scrubbed_env(os.path.join(pdir, ".virtualoffice", ".sandbox-home"), allow.get("network_allowed", False))
    env.update(env_extra or {})
    os.makedirs(env["HOME"], exist_ok=True)
    t0 = time.time()
    proc = subprocess.run(shlex.split(allow["commands"][cmd_id]), cwd=cwd, env=env, capture_output=True,
                          text=True, timeout=300)
    return {"command_id": cmd_id, "command": allow["commands"][cmd_id], "cwd": os.path.relpath(cwd, pdir),
            "exit_code": proc.returncode, "duration_ms": int((time.time() - t0) * 1000),
            "output": ((proc.stdout or "") + (proc.stderr or ""))[-1200:], "at": _now()}


def rollback_drill(session_id: str, release_tag: str, previous_ref: str,
                   projects_dir: str = DATA_PROJECTS_DIR) -> Dict[str, Any]:
    """Rolls back once in preview: the previous release must still pass tests and start healthy."""
    repo = workspace.repo_path(session_id, projects_dir)
    allow = get_allowlist(session_id, projects_dir)
    pdir = _project_dir(session_id, projects_dir)
    wt = workspace.create_worktree(repo, f"rollback/{release_tag}", base=previous_ref)
    record: Dict[str, Any] = {"release": release_tag, "rolled_back_to": previous_ref, "steps": [], "at": _now()}
    try:
        if "test" in allow["commands"]:
            record["steps"].append(_run_recorded("test", allow, wt, None, pdir))
        prev = start_preview(session_id, cwd=wt, projects_dir=projects_dir, label="rollback")
        record["previous_health"] = prev.get("health")
        stop_preview(session_id, projects_dir)
        cur = start_preview(session_id, projects_dir=projects_dir, label="preview")
        record["restored_health"] = cur.get("health")
        record["ok"] = bool(prev.get("ok")) and bool(cur.get("ok")) and all(s["exit_code"] == 0 for s in record["steps"])
    finally:
        workspace.remove_worktree(repo, wt)
        workspace.git(["branch", "-D", f"rollback/{release_tag}"], repo, check=False)
    return record


def backup_restore_drill(session_id: str, projects_dir: str = DATA_PROJECTS_DIR) -> Dict[str, Any]:
    """A backup that has never been restored is not a backup (18.7): run both, then health-check."""
    allow = get_allowlist(session_id, projects_dir)
    if "backup" not in allow.get("commands", {}) or "restore" not in allow.get("commands", {}):
        return {"ok": False, "not_run": True, "reason": "allowlist has no 'backup' and 'restore' commands"}
    repo = workspace.repo_path(session_id, projects_dir)
    pdir = _project_dir(session_id, projects_dir)
    preview = get_preview_state(session_id, projects_dir)
    data_dir = os.path.join(pdir, ".virtualoffice", "preview-data")
    extra = {"APP_DATA_DIR": data_dir, "BACKUP_DIR": os.path.join(pdir, ".virtualoffice", "backups")}
    os.makedirs(extra["BACKUP_DIR"], exist_ok=True)
    steps = [_run_recorded("backup", allow, repo, extra, pdir), _run_recorded("restore", allow, repo, extra, pdir)]
    health = health_check(preview["url"]) if preview.get("running") and preview.get("url") else {"ok": False, "detail": "preview not running"}
    return {"ok": all(s["exit_code"] == 0 for s in steps) and health["ok"], "steps": steps, "health_after": health, "at": _now()}


# ------------------------------------------------------------------ Dockerfile checks & image

def check_dockerfile(text: str) -> List[str]:
    problems = []
    froms = re.findall(r"^\s*FROM\s+(\S+)", text, re.MULTILINE | re.IGNORECASE)
    if not froms:
        problems.append("no FROM line")
    for img in froms:
        if img.lower() == "scratch":
            continue
        if "@sha256:" not in img and (":" not in img.split("/")[-1] or img.endswith(":latest")):
            problems.append(f"base image '{img}' is not pinned (use an exact tag or digest, never latest)")
    users = re.findall(r"^\s*USER\s+(\S+)", text, re.MULTILINE | re.IGNORECASE)
    if not users or users[-1] in ("root", "0"):
        problems.append("container must run as a non-root USER")
    if not re.search(r"^\s*HEALTHCHECK\s", text, re.MULTILINE | re.IGNORECASE):
        problems.append("no HEALTHCHECK")
    if re.search(r"^\s*(ENV|ARG)\s+\S*(SECRET|TOKEN|PASSWORD|API_KEY)\S*\s*=?\s*\S+", text, re.MULTILINE | re.IGNORECASE):
        problems.append("secret-like value baked into the image")
    return problems


def build_image(session_id: str, tag: str, projects_dir: str = DATA_PROJECTS_DIR) -> Dict[str, Any]:
    """Builds the release image only from locally present base images (never pulls)."""
    repo = workspace.repo_path(session_id, projects_dir)
    dockerfile = os.path.join(repo, "Dockerfile")
    if not os.path.exists(dockerfile):
        return {"ok": False, "skipped": True, "reason": "no Dockerfile in the repository"}
    with open(dockerfile, "r", encoding="utf-8") as f:
        text = f.read()
    problems = check_dockerfile(text)
    if problems:
        return {"ok": False, "problems": problems}
    if not os.environ.get("AUTONOMA_DOCKER", "").lower() in ("1", "true", "yes"):
        return {"ok": False, "skipped": True, "dockerfile_checks": "passed",
                "reason": "Docker builds are disabled (set AUTONOMA_DOCKER=1); Dockerfile checks passed"}
    for img in re.findall(r"^\s*FROM\s+(\S+)", text, re.MULTILINE | re.IGNORECASE):
        code = subprocess.run(["docker", "image", "inspect", img], capture_output=True).returncode
        if code != 0:
            return {"ok": False, "skipped": True, "reason": f"base image {img} is not present locally; not pulling"}
    proc = subprocess.run(["docker", "build", "--network", "none", "-t", tag, "."], cwd=repo,
                          capture_output=True, text=True, timeout=900)
    return {"ok": proc.returncode == 0, "tag": tag, "output": ((proc.stdout or "") + (proc.stderr or ""))[-2000:]}


# ------------------------------------------------------------------ runbook

def render_runbook(session_id: str, ci: Optional[Dict[str, Any]], preview: Dict[str, Any],
                   rollback: Optional[Dict[str, Any]], restore: Optional[Dict[str, Any]],
                   image: Optional[Dict[str, Any]], projects_dir: str = DATA_PROJECTS_DIR) -> str:
    """Runbook built only from commands that were actually run, with their recorded results."""
    allow = get_allowlist(session_id, projects_dir)
    lines = ["# Runbook", "", f"Generated by code at {_now()} from recorded runs. Every command below was run.", "",
             f"Stack: {allow.get('stack', 'unknown')} ({allow.get('stack_reason', '')})", "",
             "## Commands (approved allowlist)", "", "| ID | Command |", "|---|---|"]
    lines += [f"| {k} | `{v}` |" for k, v in sorted(allow.get("commands", {}).items())]
    lines += ["", "## CI (last run on main)", ""]
    for s in (ci or {}).get("steps", []):
        lines.append(f"- `{s['command']}` → exit {s['exit_code']} ({s['duration_ms']} ms)")
    if not ci:
        lines.append("- not run")
    lines += ["", "## Start the preview", ""]
    if preview.get("command"):
        lines.append(f"- `{preview['command']}` with `PORT`/`HOST` set → {preview.get('url')} "
                     f"health {'OK' if (preview.get('health') or {}).get('ok') else 'FAILED'} "
                     f"at `{(preview.get('health') or {}).get('path', '-')}`")
        if preview.get("seed"):
            lines.append(f"- seed: `{preview['seed']['command']}` → exit {preview['seed']['exit_code']}")
    lines += ["", "## Read the logs", "", f"- Preview log: `{preview.get('log_path', '-')}`",
              "- Runtime errors captured from the log: " + (str(len(preview.get('runtime_errors') or [])))]
    lines += ["", "## Roll back", ""]
    if rollback:
        for s in rollback.get("steps", []):
            lines.append(f"- in `{s['cwd']}`: `{s['command']}` → exit {s['exit_code']}")
        lines.append(f"- previous release `{rollback['rolled_back_to']}` health: "
                     f"{'OK' if (rollback.get('previous_health') or {}).get('ok') else 'FAILED'}; "
                     f"restored current health: {'OK' if (rollback.get('restored_health') or {}).get('ok') else 'FAILED'}")
    else:
        lines.append("- not run")
    lines += ["", "## Restore a backup", ""]
    if restore and not restore.get("not_run"):
        for s in restore.get("steps", []):
            lines.append(f"- `{s['command']}` → exit {s['exit_code']}")
        lines.append(f"- health after restore: {'OK' if restore['health_after'].get('ok') else 'FAILED'}")
    else:
        lines.append(f"- not run: {(restore or {}).get('reason', 'no drill recorded')}")
    lines += ["", "## Release image", ""]
    if image:
        if image.get("ok"):
            lines.append(f"- built `{image['tag']}`")
        else:
            lines.append(f"- not built: {image.get('reason') or '; '.join(image.get('problems', []))}")
    return "\n".join(lines) + "\n"
