"""
Agent runtime: prompt assembly and the tool loop (Handbook 23.1-23.3, 32 runAgent).

Prompt order (23.2), stable parts first so they can be cached:
  1. skills/_shared/operating-rules.md   2. skills/<role>/role.md   3. tool protocol + tool list
  -- everything above is identical for every run of the role --
  4. retrieved context (only the items the task cites)   5. the task   6. transcript so far

Tool protocol: local models are unreliable at native tool calling, so every reply must be one
JSON object, either {"tool_calls": [{"name": ..., "input": {...}}, ...]} or {"final": {<envelope>}}.
An unparseable reply gets one retry with the parse error (22.3.1); a second failure ends the run.
Failed tools return an error result to the model; failures are never hidden (23.3).
"""

import os
import re
import json
import logging
import importlib.util
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from llm_client import default_llm_client, BudgetExhaustedError
    from sandbox import Sandbox
    import workspace
    import events
except ImportError:
    from engine.llm_client import default_llm_client, BudgetExhaustedError
    from engine.sandbox import Sandbox
    from engine import workspace, events

logger = logging.getLogger("autonoma-engine.agent_runtime")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(PROJECT_ROOT, "skills")

DEV_ROLES = {"backend", "frontend", "fullstack", "engineer", "devops"}
MAX_TOOL_ROUNDS = {"dev": 25, "default": 8}
DEFAULT_RUN_TOKEN_CAP = 120_000
KEEP_FULL_TOOL_RESULTS = 8

TOOL_DEFS: Dict[str, str] = {
    "read_file": '{"path": "src/app.py", "start": 1, "end": 120}  read lines (files over 400 lines return an outline first)',
    "list_files": '{"glob": "src/**/*.py"}  list files (skips .git, node_modules)',
    "search": '{"regex": "def create_", "glob": "**/*.py"}  search file contents',
    "write_file": '{"path": "src/app.py", "content": "..."}  create or replace a file',
    "edit_file": '{"path": "src/app.py", "old": "exact text", "new": "replacement"}  replace one exact, unique match',
    "run": '{"command": "lint"}  run an approved command id (see APPROVED COMMANDS)',
    "run_tests": '{"command": "test"}  run the test suite; returns a compact summary, full log saved',
    "git_status": '{}  changed files on your branch',
    "git_diff": '{}  your branch diff against main',
    "check_package": '{"name": "requests", "ecosystem": "python"}  is a dependency installed locally (no network)',
}

ROLE_TOOLS: Dict[str, List[str]] = {
    "dev": ["read_file", "list_files", "search", "write_file", "edit_file", "run", "run_tests",
            "git_status", "git_diff", "check_package"],
    "tech-lead": ["read_file", "list_files", "search", "git_diff"],
    "qa": ["read_file", "list_files", "search", "write_file", "edit_file", "run_tests", "run"],
    "perf": ["read_file", "list_files", "search", "write_file", "run"],
    "judge": ["read_file", "list_files", "search", "git_diff"],
}


def tools_for_role(role: str) -> List[str]:
    r = role.lower()
    return ROLE_TOOLS["dev"] if r in DEV_ROLES else ROLE_TOOLS.get(r, ["read_file", "list_files", "search"])


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def stable_prefix(role: str, allowlist: Dict[str, str]) -> str:
    """Parts 1-3 of the prompt. Byte-identical across runs of the same role and allowlist."""
    rules = _read(os.path.join(SKILLS_DIR, "_shared", "operating-rules.md"))
    role_md = _read(os.path.join(SKILLS_DIR, role.lower(), "role.md")) or f"# Role: {role}"
    tools = tools_for_role(role)
    tool_lines = "\n".join(f"- {t}: {TOOL_DEFS[t]}" for t in tools)
    cmds = "\n".join(f"- {k}: {v}" for k, v in sorted(allowlist.items())) or "- (none)"
    protocol = f"""# Tool protocol
Reply with exactly ONE JSON object and nothing else. Two forms:
1. Use tools (several calls run together):
{{"tool_calls": [{{"name": "<tool>", "input": {{...}}}}]}}
2. Finish the run:
{{"final": {{"status": "done | needs_input | blocked", "artifact": "<path or branch>", "questions": [], "assumptions": [], "need_context": [], "handoff_note": "<= 60 words"}}}}
Facts about code and test results come from tool results only. Never claim a test passed unless a run_tests result shows it.

## Tools
{tool_lines}

## APPROVED COMMANDS (for run / run_tests)
{cmds}
"""
    return f"{rules}\n\n{role_md}\n\n{protocol}"


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """First top-level JSON object in a reply (code fences allowed)."""
    if not text:
        return None

    def _load(candidate: str) -> Optional[Dict[str, Any]]:
        try:
            obj = json.loads(candidate)
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None

    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", text)
    if fenced and _load(fenced.group(1)) is not None:
        return _load(fenced.group(1))
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    obj = _load(text[start:i + 1])
                    if obj is not None:
                        return obj
                    break
        start = text.find("{", start + 1)
    return None


def normalize_reply(obj: Optional[Dict[str, Any]], allowed_tools: List[str],
                    command_ids: List[str]) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """
    Maps unambiguous variants onto the protocol so small local models are not failed on form alone:
    a single call ({"tool"/"name": ..., "input"/"arguments": ...}), OpenAI-style "arguments" strings,
    and an approved command id used as a tool name (-> run). Every mapping is reported.
    """
    notes: List[str] = []
    if not isinstance(obj, dict) or "final" in obj:
        return obj, notes
    calls = obj.get("tool_calls")
    if calls is None and (obj.get("tool") or obj.get("name")):
        calls = [obj]
        notes.append("single tool call wrapped into tool_calls")
    if not isinstance(calls, list):
        return obj, notes
    fixed = []
    for c in calls:
        if not isinstance(c, dict):
            fixed.append(c)
            continue
        fn = c.get("function") if isinstance(c.get("function"), dict) else {}
        name = c.get("name") or c.get("tool") or fn.get("name")
        args = c.get("input", c.get("arguments", fn.get("arguments", {})))
        if isinstance(args, str):
            try:
                args = json.loads(args) if args.strip() else {}
                notes.append(f"{name}: arguments string parsed as JSON")
            except json.JSONDecodeError:
                args = {"_unparsed": args}
        if name not in allowed_tools and name in command_ids and "run" in allowed_tools:
            notes.append(f"approved command '{name}' used as a tool name; mapped to run")
            name, args = ("run_tests" if name == "test" and "run_tests" in allowed_tools else "run"), {"command": name}
        fixed.append({"name": name, "input": args if isinstance(args, dict) else {}})
    return {"tool_calls": fixed}, notes


def validate_reply(obj: Optional[Dict[str, Any]], allowed_tools: List[str]) -> Optional[str]:
    """Returns an error message, or None when the reply follows the protocol."""
    if obj is None:
        return "reply is not a JSON object"
    if "final" in obj:
        env = obj["final"]
        if not isinstance(env, dict):
            return "'final' must be an object"
        if env.get("status") not in ("done", "needs_input", "blocked"):
            return "'final.status' must be one of done, needs_input, blocked"
        return None
    calls = obj.get("tool_calls")
    if not isinstance(calls, list) or not calls:
        return "reply must contain a non-empty 'tool_calls' list or a 'final' envelope"
    for c in calls:
        if not isinstance(c, dict) or c.get("name") not in allowed_tools:
            return f"unknown or disallowed tool {c.get('name') if isinstance(c, dict) else c!r}; allowed: {allowed_tools}"
        if not isinstance(c.get("input", {}), dict):
            return f"tool '{c.get('name')}' input must be an object"
    return None


@dataclass
class RunResult:
    status: str
    envelope: Dict[str, Any]
    rounds: int = 0
    tool_log: List[Dict[str, Any]] = field(default_factory=list)
    usage: Dict[str, int] = field(default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0})
    degraded: bool = False
    error: str = ""


def check_package_locally(name: str, ecosystem: str, root: str) -> Dict[str, Any]:
    eco = (ecosystem or "python").lower()
    if eco in ("python", "pip", "pypi"):
        found = importlib.util.find_spec(name) is not None
    elif eco in ("node", "npm", "js"):
        found = os.path.isdir(os.path.join(root, "node_modules", name))
    else:
        return {"name": name, "ecosystem": eco, "installed": False, "note": "unknown ecosystem"}
    return {"name": name, "ecosystem": eco, "installed": found,
            "note": "Checked locally only; registry lookups need network, which is off. "
                    "Mark any dependency that is not installed as UNVERIFIED and prefer the standard library."}


class AgentRunner:
    def __init__(self, session_id: str, agent_id: str, role: str, sandbox: Sandbox,
                 branch: Optional[str] = None, token_cap: int = DEFAULT_RUN_TOKEN_CAP,
                 max_rounds: Optional[int] = None, emit: Optional[Callable[..., Any]] = None):
        self.session_id = session_id
        self.agent_id = agent_id
        self.role = role.lower()
        self.sandbox = sandbox
        self.branch = branch
        self.token_cap = token_cap
        self.max_rounds = max_rounds or (MAX_TOOL_ROUNDS["dev"] if self.role in DEV_ROLES else MAX_TOOL_ROUNDS["default"])
        self.allowed_tools = tools_for_role(self.role)
        self.emit = emit or (lambda *a, **k: None)

    def _execute_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if name == "git_status":
            ok, res = True, {"branch": workspace.current_branch(self.sandbox.root),
                             "changed": workspace.changed_files(self.sandbox.root)}
        elif name == "git_diff":
            ok, res = True, {"diff": workspace.diff_against(self.sandbox.root, max_chars=20000)}
        elif name == "check_package":
            ok, res = True, check_package_locally(args.get("name", ""), args.get("ecosystem", "python"), self.sandbox.root)
        else:
            ok, res = self.sandbox.call(name, args)
        return {"name": name, "input": args, "ok": ok, "result": res}

    @staticmethod
    def _render_tool_result(entry: Dict[str, Any], full: bool) -> str:
        args = dict(entry["input"])
        if "content" in args and isinstance(args["content"], str):
            args["content"] = f"<{len(args['content'])} chars>"
        head = f"TOOL {entry['name']} {json.dumps(args)[:300]} -> {'OK' if entry['ok'] else 'ERROR'}"
        if not full:
            return head + " (older result dropped to save context)"
        body = json.dumps(entry["result"], default=str)
        return f"{head}\n{body[:6000]}"

    def run(self, task: str, context: str, task_id: str, max_tokens: int = 4096) -> RunResult:
        system = stable_prefix(self.role, self.sandbox.allowlist)
        transcript: List[Dict[str, Any]] = []  # {"kind": "reply"|"tool"|"error", ...}
        result = RunResult(status="blocked", envelope={})
        parse_retry_used = False
        self.emit("agent.status", data={"status": "working"})

        for round_no in range(1, self.max_rounds + 1):
            result.rounds = round_no
            tool_entries = [t for t in transcript if t["kind"] == "tool"]
            keep_from = max(0, len(tool_entries) - KEEP_FULL_TOOL_RESULTS)
            rendered, tool_idx = [], 0
            for t in transcript:
                if t["kind"] == "tool":
                    rendered.append(self._render_tool_result(t["entry"], tool_idx >= keep_from))
                    tool_idx += 1
                elif t["kind"] == "reply":
                    rendered.append(f"YOUR REPLY: {t['text'][:1500]}")
                else:
                    rendered.append(f"PROTOCOL ERROR: {t['text']}")
            prompt = (f"# CONTEXT (cited items only)\n{context}\n\n# TASK\n{task}\n\n"
                      f"# TRANSCRIPT\n" + ("\n\n".join(rendered) if rendered else "(start)") +
                      f"\n\nRound {round_no} of {self.max_rounds}. Reply with one JSON object.")
            try:
                res = default_llm_client.query(prompt=prompt, system=system, role=self.role, session_id=self.session_id,
                                               task_id=f"{task_id}:r{round_no}", max_tokens=max_tokens)
            except BudgetExhaustedError:
                raise
            except Exception as e:
                result.error = f"model call failed: {e}"
                result.envelope = {"status": "blocked", "handoff_note": result.error}
                break
            result.usage["prompt_tokens"] += res["usage"].get("prompt_tokens", 0)
            result.usage["completion_tokens"] += res["usage"].get("completion_tokens", 0)
            result.degraded = result.degraded or bool(res.get("is_degraded"))
            text = res.get("text", "")

            if sum(result.usage.values()) > self.token_cap:
                result.error = f"token cap {self.token_cap} exceeded"
                result.envelope = {"status": "blocked", "handoff_note": result.error}
                break

            obj, notes = normalize_reply(extract_json_object(text), self.allowed_tools, list(self.sandbox.allowlist))
            problem = validate_reply(obj, self.allowed_tools)
            transcript.append({"kind": "reply", "text": text})
            if notes:
                self.emit("protocol.normalized", data={"notes": notes})
            if problem:
                if parse_retry_used:
                    result.error = f"invalid reply twice: {problem}"
                    result.envelope = {"status": "blocked", "handoff_note": result.error}
                    break
                parse_retry_used = True
                transcript.append({"kind": "error", "text": problem + ". Follow the tool protocol exactly."})
                continue
            parse_retry_used = False

            if "final" in obj:
                result.envelope = obj["final"]
                result.status = obj["final"]["status"]
                break

            for call in obj["tool_calls"]:
                entry = self._execute_tool(call["name"], call.get("input", {}) or {})
                result.tool_log.append(entry)
                transcript.append({"kind": "tool", "entry": entry})
                self.emit("tool.call", data={"tool": entry["name"], "ok": entry["ok"],
                                             "input": {k: (v if k != "content" else f"<{len(str(v))} chars>")
                                                       for k, v in entry["input"].items()}})
        else:
            result.error = "tool round limit"
            result.envelope = {"status": "blocked", "handoff_note": f"tool round limit ({self.max_rounds}) reached"}

        self.emit("agent.status", data={"status": "idle", "run_status": result.status})
        return result
