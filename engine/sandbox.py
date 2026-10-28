"""
Tool sandbox for agents (Handbook 23.4, 23.5, 29.1).

- Folder scope: every path is resolved (symlinks too) and must stay inside the sandbox root;
  `.git` internals are never readable or writable.
- Write scope: each role may only write under its allowed prefixes (least privilege, 6.1.3).
- Commands: agents call `run(command_id)`; only ids in the approved allowlist run, argv is
  split without a shell, and the environment is scrubbed (no secrets, network blocked
  through dead proxies and offline package-manager flags unless network is approved).
- Output compaction (23.4.2): counts, failing test names and the first error with ~20 lines
  of context; the full log is saved to a file the agent can read.
"""

import os
import re
import time
import shlex
import fnmatch
import subprocess
from typing import Any, Dict, List, Optional, Tuple

SKIP_DIRS = {".git", "node_modules", ".virtualoffice", "__pycache__", ".venv", "venv", "dist", "build"}
OUTLINE_THRESHOLD_LINES = 400
MAX_READ_LINES = 400
MAX_SEARCH_HITS = 50

# Programs an allowlisted command may start. Anything else is rejected at approval time.
ALLOWED_PROGRAMS = {"python3", "python", "node", "npm", "npx", "pytest", "k6", "sqlite3", "docker"}
# Tokens that never belong in an allowlisted command (no shell is used, but reject them anyway).
FORBIDDEN_TOKENS = {"rm", "sudo", "curl", "wget", "ssh", "scp", "nc", "push", "--force", "chmod", "chown",
                    "|", "||", "&&", ";", ">", ">>", "<", "`", "$("}
# Command ids that need network access (package installs). They only run when network is approved.
NETWORK_COMMAND_IDS = {"install"}

# Write prefixes per role ("" = anywhere in the root).
ROLE_WRITE_SCOPE: Dict[str, List[str]] = {
    "backend": [""], "frontend": [""], "fullstack": [""], "engineer": [""], "devops": [""],
    "qa": ["tests/", "reports/qa/"],
    "perf": ["perf/", "reports/perf/"],
    "tech-lead": [],
    "judge": [],
}
DOC_ROLE_WRITE_SCOPE = ["docs/"]


class SandboxError(Exception):
    """A tool request outside the sandbox rules. Returned to the model as an error result."""
    pass


def validate_allowlist(allowlist: Dict[str, str]) -> List[str]:
    """Returns the problems with a proposed command allowlist (empty list = acceptable)."""
    problems = []
    for cid, cmd in allowlist.items():
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", cid):
            problems.append(f"{cid}: command id must be lowercase letters, digits, '-' or '_'")
            continue
        try:
            argv = shlex.split(cmd)
        except ValueError as e:
            problems.append(f"{cid}: cannot parse command ({e})")
            continue
        if not argv:
            problems.append(f"{cid}: empty command")
            continue
        if os.path.basename(argv[0]) not in ALLOWED_PROGRAMS:
            problems.append(f"{cid}: program '{argv[0]}' is not allowed")
        bad = [t for t in argv if t in FORBIDDEN_TOKENS or any(t.startswith(f) for f in ("$(", "`"))]
        if bad:
            problems.append(f"{cid}: forbidden token(s) {bad}")
    return problems


def scrubbed_env(home_dir: str, network_allowed: bool = False) -> Dict[str, str]:
    """Minimal environment for agent commands: no API keys, no inherited secrets."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin"),
        "HOME": home_dir,
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
        "CI": "1",
        "NO_COLOR": "1",
    }
    if not network_allowed:
        dead = "http://127.0.0.1:9"
        env.update({
            "HTTP_PROXY": dead, "HTTPS_PROXY": dead, "http_proxy": dead, "https_proxy": dead,
            "ALL_PROXY": dead, "NO_PROXY": "localhost,127.0.0.1", "no_proxy": "localhost,127.0.0.1",
            "PIP_NO_INDEX": "1", "npm_config_offline": "true", "YARN_ENABLE_OFFLINE_MODE": "1",
        })
    return env


def compact_output(output: str, exit_code: int, max_context: int = 20) -> Dict[str, Any]:
    """Summarises test/build output: counts, failing tests, first error with context."""
    lines = output.splitlines()
    summary: Dict[str, Any] = {"exit_code": exit_code, "lines": len(lines)}

    m = re.search(r"Ran (\d+) tests?", output)
    if m:
        summary["tests_run"] = int(m.group(1))
        fm = re.search(r"FAILED \(([^)]*)\)", output)
        if fm:
            for part in fm.group(1).split(","):
                k, _, v = part.strip().partition("=")
                if v.isdigit():
                    summary[k] = int(v)
    for key in ("passed", "failed", "errors", "error", "skipped"):
        pm = re.search(rf"(\d+) {key}\b", output)
        if pm and key not in summary:
            summary[key] = int(pm.group(1))

    failing = re.findall(r"^(?:FAIL|ERROR): (\S+) \(([^)]+)\)", output, re.MULTILINE)
    failing += [(n, "") for n in re.findall(r"^FAILED (\S+::\S+)", output, re.MULTILINE)]  # pytest, not unittest's summary
    if failing:
        summary["failing_tests"] = [f"{a} ({b})" if b else a for a, b in failing][:20]

    first_err = None
    for i, line in enumerate(lines):
        if re.search(r"(Traceback|Error\b|error:|FAIL:|ERROR:|AssertionError|SyntaxError)", line):
            first_err = i
            break
    if exit_code != 0:
        if first_err is not None:
            summary["first_error"] = "\n".join(lines[first_err:first_err + max_context])
        else:
            summary["first_error"] = "\n".join(lines[-max_context:])
    summary["tail"] = "\n".join(lines[-5:])
    return summary


class Sandbox:
    def __init__(self, root: str, role: str, allowlist: Optional[Dict[str, str]] = None,
                 log_dir: Optional[str] = None, network_allowed: bool = False,
                 write_scope: Optional[List[str]] = None, timeout_s: int = 300):
        self.root = os.path.realpath(root)
        self.role = role.lower()
        self.allowlist = dict(allowlist or {})
        self.network_allowed = network_allowed
        self.timeout_s = timeout_s
        if write_scope is not None:
            self.write_scope = write_scope
        else:
            self.write_scope = ROLE_WRITE_SCOPE.get(self.role, DOC_ROLE_WRITE_SCOPE)
        self.log_dir = log_dir or os.path.join(self.root, ".virtualoffice-logs")
        self.home_dir = os.path.join(os.path.dirname(self.log_dir), ".sandbox-home")

    # ------------------------------------------------------------- paths

    def resolve(self, rel_path: str) -> str:
        if not isinstance(rel_path, str) or not rel_path.strip():
            raise SandboxError("path is required")
        candidate = rel_path if os.path.isabs(rel_path) else os.path.join(self.root, rel_path)
        real = os.path.realpath(candidate)
        if real != self.root and not real.startswith(self.root + os.sep):
            raise SandboxError(f"path '{rel_path}' is outside the project folder")
        rel = os.path.relpath(real, self.root)
        if rel.split(os.sep)[0] == ".git" or f"{os.sep}.git{os.sep}" in f"{os.sep}{rel}{os.sep}":
            raise SandboxError("git internals are not accessible; use the git tools")
        return real

    def relpath(self, abs_path: str) -> str:
        return os.path.relpath(abs_path, self.root).replace(os.sep, "/")

    def _check_write(self, abs_path: str) -> None:
        rel = self.relpath(abs_path)
        if not any(prefix == "" or rel.startswith(prefix) for prefix in self.write_scope):
            raise SandboxError(f"role '{self.role}' may not write '{rel}' (allowed: {self.write_scope or 'read-only'})")

    # ------------------------------------------------------------- file tools

    def read_file(self, path: str, start: Optional[int] = None, end: Optional[int] = None) -> Dict[str, Any]:
        p = self.resolve(path)
        if not os.path.isfile(p):
            raise SandboxError(f"file not found: {path}")
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
        total = len(lines)
        if start is None and end is None and total > OUTLINE_THRESHOLD_LINES:
            outline = [f"{i + 1}: {l.strip()}" for i, l in enumerate(lines)
                       if re.match(r"\s*(def |class |function |export |async def |#{1,3} |interface |type )", l)]
            return {"path": self.relpath(p), "total_lines": total, "outline": outline[:200],
                    "note": f"File has {total} lines; read a range with start/end."}
        s = max(1, int(start or 1))
        e = min(total, int(end or total), s + MAX_READ_LINES - 1)
        body = "\n".join(f"{i}: {lines[i - 1]}" for i in range(s, e + 1)) if total else ""
        return {"path": self.relpath(p), "total_lines": total, "start": s, "end": e, "content": body}

    def list_files(self, glob: str = "**/*") -> Dict[str, Any]:
        out = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".virtualoffice"))
            for fn in sorted(filenames):
                rel = self.relpath(os.path.join(dirpath, fn))
                if fnmatch.fnmatch(rel, glob) or fnmatch.fnmatch(fn, glob):
                    out.append(rel)
                if len(out) >= 500:
                    return {"files": out, "truncated": True}
        return {"files": out, "truncated": False}

    def search(self, regex: str, glob: str = "**/*") -> Dict[str, Any]:
        try:
            pattern = re.compile(regex)
        except re.error as e:
            raise SandboxError(f"invalid regex: {e}")
        hits = []
        for rel in self.list_files(glob)["files"]:
            try:
                with open(os.path.join(self.root, rel), "r", encoding="utf-8", errors="ignore") as f:
                    for n, line in enumerate(f, 1):
                        if pattern.search(line):
                            hits.append(f"{rel}:{n}: {line.rstrip()[:200]}")
                            if len(hits) >= MAX_SEARCH_HITS:
                                return {"hits": hits, "truncated": True}
            except (OSError, UnicodeDecodeError):
                continue
        return {"hits": hits, "truncated": False}

    def write_file(self, path: str, content: str) -> Dict[str, Any]:
        p = self.resolve(path)
        self._check_write(p)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content if isinstance(content, str) else str(content))
        return {"path": self.relpath(p), "bytes": os.path.getsize(p)}

    def edit_file(self, path: str, old: str, new: str) -> Dict[str, Any]:
        p = self.resolve(path)
        self._check_write(p)
        if not os.path.isfile(p):
            raise SandboxError(f"file not found: {path}")
        with open(p, "r", encoding="utf-8") as f:
            text = f.read()
        count = text.count(old) if old else 0
        if count != 1:
            raise SandboxError(f"edit needs exactly one match of 'old'; found {count}")
        with open(p, "w", encoding="utf-8") as f:
            f.write(text.replace(old, new, 1))
        return {"path": self.relpath(p), "replaced": 1}

    # ------------------------------------------------------------- commands

    def run(self, command_id: str) -> Dict[str, Any]:
        if command_id not in self.allowlist:
            raise SandboxError(f"command '{command_id}' is not in the approved allowlist {sorted(self.allowlist)}")
        if command_id in NETWORK_COMMAND_IDS and not self.network_allowed:
            raise SandboxError(f"command '{command_id}' needs network access, which is not approved for this project")
        problems = validate_allowlist({command_id: self.allowlist[command_id]})
        if problems:
            raise SandboxError("; ".join(problems))
        argv = shlex.split(self.allowlist[command_id])
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.home_dir, exist_ok=True)
        log_path = os.path.join(self.log_dir, f"{command_id}-{int(time.time() * 1000)}.log")
        t0 = time.time()
        try:
            proc = subprocess.run(argv, cwd=self.root, env=scrubbed_env(self.home_dir, self.network_allowed),
                                  capture_output=True, text=True, timeout=self.timeout_s)
            output, code = (proc.stdout or "") + (proc.stderr or ""), proc.returncode
        except subprocess.TimeoutExpired as e:
            output = ((e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or ""))
            output += f"\nTIMEOUT after {self.timeout_s}s"
            code = 124
        except FileNotFoundError as e:
            output, code = f"program not found: {e}", 127
        duration_ms = int((time.time() - t0) * 1000)
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(output)
        summary = compact_output(output, code)
        summary.update({"command_id": command_id, "command": self.allowlist[command_id], "duration_ms": duration_ms,
                        "log_path": log_path, "ok": code == 0})
        return summary

    # ------------------------------------------------------------- dispatch

    def call(self, name: str, args: Dict[str, Any]) -> Tuple[bool, Any]:
        """Runs one tool by name. Returns (ok, result_or_error_message); never raises for tool errors."""
        args = args or {}
        try:
            if name == "read_file":
                return True, self.read_file(args.get("path", ""), args.get("start"), args.get("end"))
            if name == "list_files":
                return True, self.list_files(args.get("glob", "**/*"))
            if name == "search":
                return True, self.search(args.get("regex", ""), args.get("glob", "**/*"))
            if name == "write_file":
                return True, self.write_file(args.get("path", ""), args.get("content", ""))
            if name == "edit_file":
                return True, self.edit_file(args.get("path", ""), args.get("old", ""), args.get("new", ""))
            if name in ("run", "run_tests"):
                cid = args.get("command") or args.get("command_id") or ("test" if name == "run_tests" else "")
                return True, self.run(cid)
            return False, f"unknown tool '{name}'"
        except SandboxError as e:
            return False, str(e)
        except Exception as e:  # tool failures are reported to the model, never hidden
            return False, f"{type(e).__name__}: {e}"
