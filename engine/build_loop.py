"""
Stage 6-7 build loop and Alpha (Handbook 2.7.7, 2.7.8, 9.1.2, 10, 13, 14, 15, 32 BuildStory).

Per story, in its own git worktree on story/ST-###:
  dev agent writes code + tests  ->  [code] CI (lint, types, tests)  ->  Tech Lead review (only on green)
  -> changes go back to the same dev, max 3 rounds, then escalate  ->  [code] merge
  -> QA writes tests per AC; [code] runs the full regression suite (tools decide, not prose)
  -> bugs go back to the same dev with evidence, max 3 rounds  ->  Performance QA if needs_perf
  -> Judge scores the story against its ACs and rubric (skipped for trivial stories)  ->  done.

Code (not agents) decides every pass/fail: CI exit codes, AC-to-test coverage, contract-file
changes, review severities, the regression run, rubric arithmetic. Reports are written by code
from those records. Budget exhaustion pauses the build; it resumes from build_state.json.
"""

import os
import re
import json
import shutil
import sqlite3
import logging
import threading
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    from llm_client import BudgetExhaustedError
    from sandbox import Sandbox
    from agent_runtime import AgentRunner, RunResult
    from retriever import index_project, retrieve, ID_RE
    import workspace
    import events
    import devops
except ImportError:
    from engine.llm_client import BudgetExhaustedError
    from engine.sandbox import Sandbox
    from engine.agent_runtime import AgentRunner, RunResult
    from engine.retriever import index_project, retrieve, ID_RE
    from engine import workspace, events, devops

logger = logging.getLogger("autonoma-engine.build_loop")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PROJECTS_DIR = os.path.join(PROJECT_ROOT, "data", "projects")
DEFAULT_DB_PATH = os.path.join(PROJECT_ROOT, "data", "office.db")
SKILLS_DIR = os.path.join(PROJECT_ROOT, "skills")

MAX_ROUNDS = 3
DONE_STATUSES = {"done", "done_perf_not_run"}
TERMINAL_STATUSES = DONE_STATUSES | {"escalated", "blocked"}
CONTRACT_FILES = ("docs/openapi.yaml", "docs/schema.md", "docs/adr/")
SECRET_RE = re.compile(r"(-----BEGIN [A-Z ]*PRIVATE KEY-----|(?:api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"\s]{8,}['\"])", re.I)

_active_builds: Dict[str, threading.Thread] = {}
_active_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ac_pattern(ac_id: str) -> re.Pattern:
    prefix, num = ac_id.split("-", 1)
    return re.compile(rf"\b{prefix}[-_]0*{int(num)}\b", re.I) if num.isdigit() else re.compile(re.escape(ac_id), re.I)


def init_test_runs_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS test_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                task_id TEXT,
                kind TEXT NOT NULL,
                passed INTEGER NOT NULL,
                total INTEGER NOT NULL,
                failed INTEGER NOT NULL,
                summary TEXT NOT NULL,
                log_path TEXT NOT NULL,
                at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


class BuildLoop:
    def __init__(self, session_id: str, projects_dir: str = DATA_PROJECTS_DIR, db_path: str = DEFAULT_DB_PATH,
                 parallelism: Optional[int] = None, max_rounds: int = MAX_ROUNDS):
        self.session_id = session_id
        self.projects_dir = projects_dir
        self.db_path = db_path
        if parallelism is None:
            # Local GPUs run one model at a time; cloud models have separate per-model quotas.
            try:
                from llm_client import default_llm_client
            except ImportError:
                from engine.llm_client import default_llm_client
            parallelism = (int(default_llm_client.router.get("build_parallelism_cloud", 2))
                           if default_llm_client.cloud_allowed(session_id) else 1)
        self.parallelism = max(1, parallelism)
        self.max_rounds = max_rounds
        self.pdir = os.path.join(projects_dir, session_id)
        self.docs_dir = os.path.join(self.pdir, "docs")
        self.state_path = os.path.join(self.pdir, "build_state.json")
        self.log_root = os.path.join(self.pdir, ".virtualoffice", "logs")
        self._state_lock = threading.RLock()
        self._merge_lock = threading.Lock()
        self.repo = ""
        self.allow: Dict[str, Any] = {}
        self.items: Dict[str, Dict[str, str]] = {}
        self.roster: List[Dict[str, Any]] = []
        self.state: Dict[str, Any] = {}

    # ------------------------------------------------------------ state & records

    def _load_json(self, path: str, default: Any) -> Any:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return default

    def save_state(self) -> None:
        with self._state_lock:
            self.state["updated_at"] = _now()
            tmp = self.state_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, default=str)
            os.replace(tmp, self.state_path)

    def emit(self, type_: str, actor: Optional[str] = None, task_id: Optional[str] = None,
             data: Optional[Dict[str, Any]] = None) -> None:
        events.emit(self.session_id, type_, actor=actor, task_id=task_id, data=data, db_path=self.db_path)

    def story_state(self, sid: str) -> Dict[str, Any]:
        return self.state["stories"][sid]

    def set_story(self, sid: str, **fields: Any) -> None:
        with self._state_lock:
            self.state["stories"][sid].update(fields)
            self.save_state()
        cols = {k: fields[k] for k in ("stage", "status", "rounds", "branch", "builder") if k in fields}
        if fields.get("status") in DONE_STATUSES:
            cols["done_at"] = _now()
        if cols:
            conn = sqlite3.connect(self.db_path, timeout=30)
            try:
                conn.execute(f"UPDATE tasks SET {', '.join(f'{k} = ?' for k in cols)} WHERE project_id = ? AND id = ?",
                             [*cols.values(), self.session_id, sid])
                conn.commit()
            finally:
                conn.close()

    def next_id(self, prefix: str) -> str:
        """IDs are never reused or renumbered (Handbook 3.4)."""
        with self._state_lock:
            counters = self.state.setdefault("id_counters", {})
            counters[prefix] = counters.get(prefix, 0) + 1
            self.save_state()
            return f"{prefix}-{counters[prefix]:03d}"

    def record_review(self, target: str, reviewer: str, kind: str, passed: bool, body: Dict[str, Any],
                      score: Optional[float] = None, max_score: Optional[float] = None) -> None:
        try:
            from readiness import init_reviews_db
        except ImportError:
            from engine.readiness import init_reviews_db
        init_reviews_db(self.db_path)
        conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            conn.execute("INSERT INTO reviews (project_id, target, reviewer, kind, passed, score, max_score, body) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                         (self.session_id, target, reviewer, kind, int(passed), score, max_score, json.dumps(body, default=str)))
            conn.commit()
        finally:
            conn.close()

    def record_test_run(self, task_id: str, kind: str, run: Dict[str, Any]) -> None:
        init_test_runs_db(self.db_path)
        total = int(run.get("tests_run") or run.get("passed", 0) + run.get("failed", 0) or 0)
        failed = int(run.get("failures", 0) + run.get("errors", 0) + run.get("failed", 0))
        conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            conn.execute("INSERT INTO test_runs (project_id, task_id, kind, passed, total, failed, summary, log_path) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                         (self.session_id, task_id, kind, int(bool(run.get("ok"))), total, failed,
                          json.dumps({k: v for k, v in run.items() if k != "tail"}, default=str)[:4000],
                          run.get("log_path", "")))
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------ setup

    def prepare(self) -> None:
        backlog = self._load_json(os.path.join(self.docs_dir, "backlog.json"), None)
        if not backlog or not backlog.get("stories"):
            raise RuntimeError("docs/backlog.json has no stories; run the Scrum Master first")
        # Gate 3 UAT bugs re-enter Stage 6 as extra stories (kept apart so the readiness hash stays valid).
        uat = self._load_json(os.path.join(self.pdir, "uat_stories.json"), {"stories": []})
        backlog = {**backlog, "stories": list(backlog["stories"]) + list(uat.get("stories", []))}
        self.allow = devops.get_allowlist(self.session_id, self.projects_dir)
        if not self.allow.get("approved"):
            raise RuntimeError("command allowlist is not approved (Handbook 23.4.1); approve it before building")
        self.repo = workspace.ensure_repo(self.session_id, self.projects_dir)
        qa_log = self._load_json(os.path.join(self.pdir, "qa_log.json"), [])
        self.items = index_project(self.docs_dir, qa_log, backlog)
        try:
            from skill_registry import get_agents_by_project
        except ImportError:
            from engine.skill_registry import get_agents_by_project
        try:
            self.roster = get_agents_by_project(self.session_id, db_path=self.db_path)
        except Exception:
            self.roster = []

        try:
            from scrum import sync_stories_to_tasks
        except ImportError:
            from engine.scrum import sync_stories_to_tasks
        sync_stories_to_tasks(self.session_id, backlog["stories"], db_path=self.db_path)

        existing = self._load_json(self.state_path, {})
        stories = existing.get("stories", {})
        for st in backlog["stories"]:
            if st["id"] not in stories:
                stories[st["id"]] = {"id": st["id"], "status": "todo", "stage": "todo", "rounds": 0,
                                     "qa_rounds": 0, "history": []}
            stories[st["id"]]["story"] = st
        # Resume after a crash or pause: unfinished stories restart; merged ones resume at Alpha.
        for s in stories.values():
            if s["status"] in TERMINAL_STATUSES or s["status"] == "todo":
                continue
            s["resume_from"] = "alpha" if s.get("merged_sha") else "build"
            s["status"], s["stage"] = "todo", "resumed"
        self.state = {**existing, "session_id": self.session_id, "stories": stories,
                      "status": existing.get("status", "idle"), "parallelism": self.parallelism}
        self.save_state()

    def agent_for(self, role: str, preferred: Optional[str] = None) -> Dict[str, Any]:
        if preferred and preferred.startswith(f"{self.session_id}_"):
            preferred = preferred[len(self.session_id) + 1:]  # backlog owners may carry the project prefix
        for a in self.roster:
            if preferred and a.get("agent_id") == preferred:
                return a
        for a in self.roster:
            if (a.get("role") or "").lower() == role.lower():
                return a
        return {"agent_id": preferred or f"{role}-1", "role": role, "token_cap": 120_000}

    def story_context(self, story: Dict[str, Any], budget_chars: int = 16000) -> str:
        refs = story.get("refs", {}) or {}
        ids = [story["id"]]
        for key in ("ac", "features", "api", "tables", "adr", "nfr"):
            ids += refs.get(key, []) or []
        ctx = retrieve(self.items, ids, budget_chars=budget_chars)
        missing = f"\n\nNot found in project docs (do not guess them): {', '.join(ctx['missing'])}" if ctx["missing"] else ""
        return ctx["text"] + missing

    def sandbox_for(self, root: str, role: str, sid: str) -> Sandbox:
        return Sandbox(root, role, self.allow["commands"], log_dir=os.path.join(self.log_root, sid),
                       network_allowed=bool(self.allow.get("network_allowed")))

    def runner(self, sid: str, agent: Dict[str, Any], role: str, sandbox: Sandbox, branch: Optional[str]) -> AgentRunner:
        def _emit(type_: str, data: Optional[Dict[str, Any]] = None) -> None:
            self.emit(type_, actor=agent["agent_id"], task_id=sid, data=data)
        cap = int(agent.get("token_cap") or 120_000)
        return AgentRunner(self.session_id, agent["agent_id"], role, sandbox, branch=branch,
                           token_cap=min(cap, 400_000), emit=_emit)

    # ------------------------------------------------------------ main loop

    def ready_stories(self) -> List[str]:
        out = []
        for sid, s in self.state["stories"].items():
            if s["status"] != "todo":
                continue
            deps = s["story"].get("depends_on", []) or []
            if all(self.state["stories"].get(d, {}).get("status") in DONE_STATUSES for d in deps):
                out.append(sid)
        return sorted(out)

    def run(self) -> Dict[str, Any]:
        self.prepare()
        self.state["status"] = "running"
        self.state.setdefault("started_at", _now())
        self.save_state()
        self.emit("phase.entered", actor="system", data={"phase": "build"})
        try:
            while True:
                ready = self.ready_stories()
                if not ready:
                    break
                batch = ready[:self.parallelism]
                if self.parallelism == 1:
                    for sid in batch:
                        self.build_story(sid)
                else:
                    with ThreadPoolExecutor(max_workers=self.parallelism) as pool:
                        list(pool.map(self.build_story, batch))
        except BudgetExhaustedError as e:
            for sid, s in self.state["stories"].items():
                if s["status"] not in TERMINAL_STATUSES and s["status"] != "todo":
                    self.set_story(sid, status="todo", stage="paused")
            self.state.update({"status": "paused_budget", "message": str(e)})
            self.save_state()
            self.emit("budget.paused", actor="system", data={"message": str(e)})
            return self.summary()

        # Stories whose dependencies can never finish are blocked, with the reason.
        for sid, s in self.state["stories"].items():
            if s["status"] == "todo":
                bad = [d for d in s["story"].get("depends_on", []) or []
                       if self.state["stories"].get(d, {}).get("status") not in DONE_STATUSES]
                self.set_story(sid, status="blocked", stage="blocked", blocked_reason=f"dependencies not done: {bad}")
                self.emit("task.blocked", actor="system", task_id=sid, data={"dependencies": bad})

        statuses = [s["status"] for s in self.state["stories"].values()]
        self.state["status"] = "complete" if all(x in DONE_STATUSES for x in statuses) else "complete_with_issues"
        self.state["finished_at"] = _now()
        self.save_state()
        self.write_daily_report()
        self.emit("phase.completed", actor="system", data={"phase": "build", "status": self.state["status"]})
        return self.summary()

    def summary(self) -> Dict[str, Any]:
        counts: Dict[str, int] = {}
        for s in self.state["stories"].values():
            counts[s["status"]] = counts.get(s["status"], 0) + 1
        return {"session_id": self.session_id, "status": self.state.get("status"), "counts": counts,
                "stories": {sid: {k: v for k, v in s.items() if k != "story"} for sid, s in self.state["stories"].items()}}

    # ------------------------------------------------------------ one story

    def build_story(self, sid: str) -> None:
        story = self.story_state(sid)["story"]
        role = (story.get("role") or "fullstack").lower()
        dev = self.agent_for(role, story.get("owner"))
        resume_alpha = self.story_state(sid).pop("resume_from", "build") == "alpha"
        self.set_story(sid, status="building", stage="build", builder=dev["agent_id"], branch=f"story/{sid}")
        self.emit("task.assigned", actor="system", task_id=sid,
                  data={"to": dev["agent_id"], "role": role, "resumed_at": "alpha" if resume_alpha else None})

        if resume_alpha:
            merged_diff = self.story_state(sid).get("merged_diff", "")
        else:
            cycle = self.dev_cycle(story, dev, f"story/{sid}", "main", purpose="build", feedback="")
            if not cycle["approved"]:
                self.escalate(sid, cycle["escalate_to"], cycle["reason"], cycle.get("last_feedback", ""))
                return
            merged_diff = cycle["diff"]
            if not self.merge(sid, cycle["branch"], cycle["wt"], f"Merge {cycle['branch']}: {story.get('title', '')}"):
                return
            self.set_story(sid, merged_diff=merged_diff[:60000])

        # Alpha: QA (and fix rounds), then perf, then Judge.
        judge_feedback = ""
        for qa_round in range(1, self.max_rounds + 1):
            self.set_story(sid, status="qa", stage="qa", qa_rounds=qa_round)
            qa = self.qa_cycle(story, qa_round, extra_feedback=judge_feedback)
            if qa.get("escalate"):
                self.escalate(sid, "tech-lead", qa["reason"], qa.get("report", ""))
                return
            if qa["passed"]:
                judge = self.judge_story(story, merged_diff, qa)
                if judge["pass"]:
                    break
                if judge.get("escalate"):
                    self.escalate(sid, "client", judge["reason"], json.dumps(judge.get("verdict", {}))[:2000])
                    return
                judge_feedback = judge["feedback"]
                fix_base = "main"
                feedback = f"The LLM Judge failed this story against its acceptance criteria:\n{judge['feedback']}"
            else:
                fix_base = qa["branch"]
                feedback = qa["feedback"]
            if qa_round == self.max_rounds:
                self.escalate(sid, "tech-lead", f"story failed Alpha {self.max_rounds} times", feedback)
                return
            self.set_story(sid, status="fixing", stage="build")
            fix = self.dev_cycle(story, dev, f"fix/{sid}-r{qa_round}", fix_base, purpose="fix", feedback=feedback)
            if not fix["approved"]:
                self.escalate(sid, fix["escalate_to"], fix["reason"], fix.get("last_feedback", ""))
                return
            merged_diff += "\n" + fix["diff"]
            if not self.merge(sid, fix["branch"], fix["wt"], f"Merge {fix['branch']}: fixes for {sid}"):
                return
        else:
            return

        perf = self.perf_check(story)
        status = "done" if perf["status"] in ("passed", "not_needed") else "done_perf_not_run"
        if perf["status"] == "failed":
            self.escalate(sid, "architect", "performance SLOs not met", json.dumps(perf)[:2000])
            return
        self.set_story(sid, status=status, stage="done", perf=perf)
        self.emit("task.done", actor="system", task_id=sid, data={"status": status, "perf": perf["status"]})
        self.write_daily_report()

    def merge(self, sid: str, branch: str, wt: str, message: str) -> bool:
        with self._merge_lock:
            ok, info = workspace.merge_branch(self.repo, branch, message)
        if not ok:
            self.escalate(sid, "tech-lead", f"merge conflict merging {branch} into main", info)
            return False
        workspace.remove_worktree(self.repo, wt)
        self.set_story(sid, status="merged", stage="merged", merged_sha=info)
        self.emit("task.merged", actor="system", task_id=sid, data={"branch": branch, "sha": info})
        return True

    def escalate(self, sid: str, to: str, reason: str, detail: str = "") -> None:
        """Escalation path dev -> Tech Lead -> Architect -> client (Handbook 2.5), with the reviewer's comments."""
        record = {"story": sid, "to": to, "reason": reason, "detail": detail[:4000], "at": _now()}
        with self._state_lock:
            self.state.setdefault("escalations", []).append(record)
        self.set_story(sid, status="escalated", stage="escalated", escalation=record)
        self.emit("task.escalated", actor="system", task_id=sid, data=record)

    # ------------------------------------------------------------ dev + CI + review

    def dev_task_text(self, story: Dict[str, Any], branch: str, purpose: str, feedback: str) -> str:
        acs = (story.get("refs", {}) or {}).get("ac", []) or []
        stack = self.allow.get("stack", "python")
        stack_rules = ("Python standard library only: package installs are disabled (network is off). "
                       "App code in src/ (a package with __init__.py), tests in tests/ using unittest."
                       if stack == "python" else
                       "Use only dependencies already in package.json; installs need network approval.")
        commands = ", ".join(f"{k} = `{v}`" for k, v in sorted(self.allow["commands"].items()))
        lines = [
            f"{'Implement' if purpose == 'build' else 'Fix'} story {story['id']}: {story.get('title', '')}",
            f"Your worktree is on branch {branch}. Points: {story.get('points')}.",
            f"Acceptance criteria to satisfy: {', '.join(acs) or 'none listed (see definition of done)'}",
            "Definition of done:", *[f"- {d}" for d in story.get("definition_of_done", [])],
            f"Stack rules: {stack_rules}",
            f"The orchestrator runs these approved commands: {commands}.",
            "If a 'preview' command exists, the app must start an HTTP server on the HOST and PORT environment "
            "variables and answer GET /health with 200. Persistent data goes under APP_DATA_DIR.",
            "Every test must name the AC id it proves in its name or a comment (for example `# AC-001`).",
            "Do not edit docs/openapi.yaml, docs/schema.md or docs/adr/ (contract changes need an Architect ADR).",
            "Run run_tests before you finish. Finish with a final envelope whose handoff_note lists the ACs covered.",
        ]
        if feedback:
            lines += ["", "# FEEDBACK TO ADDRESS (from CI / Tech Lead / QA / Judge)", feedback]
        return "\n".join(lines)

    def dev_cycle(self, story: Dict[str, Any], dev: Dict[str, Any], branch: str, base: str,
                  purpose: str, feedback: str) -> Dict[str, Any]:
        sid = story["id"]
        role = (story.get("role") or "fullstack").lower()
        wt = workspace.create_worktree(self.repo, branch, base=base)
        context = self.story_context(story)
        last_feedback = feedback
        for round_no in range(1, self.max_rounds + 1):
            rounds_total = self.story_state(sid).get("rounds", 0) + 1
            self.set_story(sid, stage="build", rounds=rounds_total)
            sandbox = self.sandbox_for(wt, role, sid)
            run = self.runner(sid, dev, role, sandbox, branch).run(
                self.dev_task_text(story, branch, purpose, last_feedback), context,
                task_id=f"{sid}:{purpose}:dev{round_no}")
            sha = workspace.commit_all(wt, f"{'feat' if purpose == 'build' else 'fix'}({sid}): round {round_no}",
                                       expected_branch=branch)
            self.emit("task.handoff", actor=dev["agent_id"], task_id=sid,
                      data={"to": "ci", "commit": sha, "run_status": run.status, "rounds": run.rounds,
                            "note": (run.envelope or {}).get("handoff_note", "")[:400]})
            self._history(sid, {"kind": "dev_run", "round": round_no, "purpose": purpose, "status": run.status,
                                "commit": sha, "tool_calls": len(run.tool_log), "error": run.error})
            if run.envelope.get("status") == "needs_input" and run.envelope.get("questions"):
                return {"approved": False, "escalate_to": "client", "wt": wt, "branch": branch,
                        "reason": "developer needs client input", "last_feedback": json.dumps(run.envelope["questions"])}
            if not workspace.changed_files(wt, base=base):
                last_feedback = (f"No changes were committed on your branch. Your run ended with status "
                                 f"'{run.status}' ({run.error or 'no error'}). Write the code and tests with write_file.")
                continue

            ci = devops.run_ci(sandbox)
            for step in ci["steps"]:
                if step["command_id"] == "test":
                    self.record_test_run(sid, "unit", step)
            self.emit("ci.completed", actor="ci", task_id=sid,
                      data={"green": ci["green"], "reason": ci["reason"],
                            "steps": [{k: s.get(k) for k in ("command_id", "exit_code", "tests_run", "failing_tests")} for s in ci["steps"]]})
            self._history(sid, {"kind": "ci", "round": round_no, "green": ci["green"], "reason": ci["reason"]})
            if not ci["green"]:
                last_feedback = devops.ci_feedback(ci)
                continue  # red code is never reviewed; output goes back to the dev

            self.set_story(sid, stage="review")
            review = self.tech_lead_review(story, wt, ci)
            if review.get("unavailable"):
                return {"approved": False, "escalate_to": "architect", "wt": wt, "branch": branch,
                        "reason": "Tech Lead review could not be completed", "last_feedback": review.get("error", "")}
            if review["decision"] == "approve":
                return {"approved": True, "wt": wt, "branch": branch, "diff": workspace.diff_against(wt), "ci": ci,
                        "review": review}
            last_feedback = "Tech Lead requested changes:\n" + "\n".join(
                f"- {c['id']} [{c['severity']}] {c['file']}:{c['line']} ({c['rule']}): {c['issue']} -> fix: {c['fix']}"
                for c in review["comments"] if c["severity"] in ("blocker", "major"))
        return {"approved": False, "escalate_to": "architect", "wt": wt, "branch": branch,
                "reason": f"not approved after {self.max_rounds} rounds", "last_feedback": last_feedback}

    def _history(self, sid: str, entry: Dict[str, Any]) -> None:
        with self._state_lock:
            entry["at"] = _now()
            self.state["stories"][sid].setdefault("history", []).append(entry)
            self.save_state()

    def code_review_checks(self, story: Dict[str, Any], wt: str) -> List[Dict[str, Any]]:
        """Deterministic review rules: AC test coverage, contract files, secrets."""
        comments = []
        acs = (story.get("refs", {}) or {}).get("ac", []) or []
        test_text = ""
        for dirpath, dirnames, filenames in os.walk(os.path.join(wt, "tests")):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for fn in filenames:
                try:
                    with open(os.path.join(dirpath, fn), "r", encoding="utf-8", errors="ignore") as f:
                        test_text += f.read() + "\n"
                except OSError:
                    pass
        for ac in acs:
            if not _ac_pattern(ac).search(test_text):
                comments.append({"file": "tests/", "line": 1, "severity": "blocker", "rule": "checklist:tests.ac_coverage",
                                 "issue": f"{ac} has no test that names it", "fix": f"add a test for {ac} that cites `{ac}`",
                                 "source": "code"})
        for path in workspace.changed_files(wt):
            if path.startswith(CONTRACT_FILES):
                comments.append({"file": path, "line": 1, "severity": "blocker", "rule": "contract.change_needs_adr",
                                 "issue": "API contract / schema / ADR changed by a developer",
                                 "fix": "revert the change and raise it with the Architect", "source": "code"})
        diff = workspace.diff_against(wt)
        current_file = ""
        for line in diff.splitlines():
            if line.startswith("+++ b/"):
                current_file = line[6:]
            elif line.startswith("+") and SECRET_RE.search(line):
                comments.append({"file": current_file, "line": 1, "severity": "blocker", "rule": "security.secrets",
                                 "issue": "secret-like value committed", "fix": "read it from the environment instead",
                                 "source": "code"})
        return comments

    def tech_lead_review(self, story: Dict[str, Any], wt: str, ci: Dict[str, Any]) -> Dict[str, Any]:
        sid = story["id"]
        tl = self.agent_for("tech-lead", "tech-lead-1")
        sandbox = Sandbox(wt, "tech-lead", {}, log_dir=os.path.join(self.log_root, sid), write_scope=[])
        diff = workspace.diff_against(wt, max_chars=24000)
        task = "\n".join([
            f"Review story {sid}: {story.get('title', '')}. CI is GREEN (lint, types, tests passed).",
            "Check in order: correctness against each AC, contract and design (openapi.yaml, schema, ADRs), security "
            "(validation, authorization, secrets, safe queries), performance (N+1, indexes, unbounded lists), tests "
            "(behaviour, failure cases), readability.",
            "Every comment: file, line, severity (blocker | major | nit), rule, issue and a concrete fix. Nits never block.",
            'Finish with {"final": {"status": "done", "decision": "approve | changes_requested", "comments": [...], '
            '"handoff_note": "..."}}.',
            "", "# DIFF", diff,
        ])
        model_comments: List[Dict[str, Any]] = []
        result: Optional[RunResult] = None
        for attempt in range(2):
            result = self.runner(sid, tl, "tech-lead", sandbox, None).run(task, self.story_context(story, 8000),
                                                                           task_id=f"{sid}:review{attempt + 1}")
            if result.status == "done" and isinstance(result.envelope.get("comments", []), list):
                model_comments = result.envelope.get("comments", []) or []
                break
        else:
            return {"unavailable": True, "error": (result.error if result else "") or "invalid review envelope"}

        comments: List[Dict[str, Any]] = []
        dropped = 0
        for c in model_comments:
            if not isinstance(c, dict):
                dropped += 1
                continue
            sev = str(c.get("severity", "")).lower()
            if sev not in ("blocker", "major", "nit") or not c.get("file") or not c.get("issue") or not c.get("fix"):
                dropped += 1  # not specific and actionable: not a valid review comment (10.2.5)
                continue
            try:
                line = int(c.get("line", 1))
            except (TypeError, ValueError):
                line = 1
            comments.append({"file": str(c["file"]), "line": line, "severity": sev,
                             "rule": str(c.get("rule", "review")), "issue": str(c["issue"]), "fix": str(c["fix"]),
                             "source": "tech-lead"})
        comments += self.code_review_checks(story, wt)
        for c in comments:
            c["id"] = self.next_id("REV")
        blocking = [c for c in comments if c["severity"] in ("blocker", "major")]
        decision = "changes_requested" if blocking else "approve"
        model_decision = str(result.envelope.get("decision", "")).lower() if result else ""
        review = {"story": sid, "decision": decision, "model_decision": model_decision, "comments": comments,
                  "dropped_invalid_comments": dropped, "ci_green": ci["green"], "degraded": bool(result and result.degraded)}
        self.record_review(sid, tl["agent_id"], "code_review", decision == "approve", review)
        self.emit("review.completed", actor=tl["agent_id"], task_id=sid,
                  data={"decision": decision, "blocking": len(blocking), "comments": len(comments)})
        self._history(sid, {"kind": "review", "decision": decision, "blocking": len(blocking)})
        return review

    # ------------------------------------------------------------ QA

    def qa_cycle(self, story: Dict[str, Any], qa_round: int, extra_feedback: str = "") -> Dict[str, Any]:
        sid = story["id"]
        qa_agent = self.agent_for("qa", "qa-1")
        branch = f"qa/{sid}-r{qa_round}"
        wt = workspace.create_worktree(self.repo, branch, base="main")
        sandbox = self.sandbox_for(wt, "qa", sid)
        acs = (story.get("refs", {}) or {}).get("ac", []) or []
        task = "\n".join([
            f"QA for story {sid}: {story.get('title', '')}. The story is merged on main (your worktree, branch {branch}).",
            f"Acceptance criteria: {', '.join(acs) or 'see definition of done'}.",
            "For each AC write at least one test that fails if the criterion is not met. Name the AC id and a TC id "
            "in each test (for example `# TC-014 AC-003`). Add boundary and negative cases: empty, maximum length, "
            "zero, negative, duplicates, wrong permission, expired session, concurrent actions where relevant.",
            "Write tests under tests/ only. Then run the FULL regression suite with run_tests.",
            "Report a bug only with evidence from a real run (failing test name and output). No evidence, no bug.",
            'Finish with {"final": {"status": "done", "tests": [{"id": "TC-..", "ac": "AC-..", "file": "tests/.."}], '
            '"bugs": [{"ac": "AC-..", "severity": "blocker|major|minor", "steps": [], "expected": "", "actual": "", '
            '"evidence": "<failing test name>"}], "handoff_note": "..."}}.',
            extra_feedback and f"\nThe Judge flagged: {extra_feedback}",
        ])
        run = self.runner(sid, qa_agent, "qa", sandbox, branch).run(task, self.story_context(story, 10000),
                                                                   task_id=f"{sid}:qa{qa_round}")
        ran_tests_itself = any(e["name"] in ("run_tests", "run") and e["ok"] and
                               isinstance(e["result"], dict) and e["result"].get("command_id") == "test"
                               for e in run.tool_log)

        # Tools decide: the orchestrator runs the full regression suite itself.
        regression = sandbox.run("test") if "test" in self.allow["commands"] else {"ok": False, "exit_code": -1,
                                                                                   "first_error": "no test command"}
        self.record_test_run(sid, "regression", regression)

        test_text = ""
        tests_dir = os.path.join(wt, "tests")
        for dirpath, dirnames, filenames in os.walk(tests_dir):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for fn in filenames:
                with open(os.path.join(dirpath, fn), "r", encoding="utf-8", errors="ignore") as f:
                    test_text += f.read() + "\n"
        uncovered = [ac for ac in acs if not _ac_pattern(ac).search(test_text)]

        failing = regression.get("failing_tests", []) or []
        claimed_bugs = [b for b in (run.envelope.get("bugs") or []) if isinstance(b, dict)]
        bugs, discarded = [], []
        for b in claimed_bugs:
            ev = str(b.get("evidence", ""))
            if ev and any(ev.split(" ")[0] in f or f.split(" ")[0] in ev for f in failing):
                bugs.append(b)
            else:
                discarded.append(b)
        # Failing tests are bugs even if QA did not file them; evidence is the run itself.
        for f in failing:
            if not any(f.split(" ")[0] in str(b.get("evidence", "")) for b in bugs):
                ac_match = ID_RE.search(f.replace("_", "-").upper())
                bugs.append({"ac": ac_match.group(1) if ac_match and ac_match.group(1).startswith("AC") else "",
                             "severity": "blocker", "steps": [f"run `{self.allow['commands'].get('test')}`"],
                             "expected": "test passes", "actual": "test fails", "evidence": f})
        if not regression.get("ok") and not failing:
            bugs.append({"ac": "", "severity": "blocker", "steps": [f"run `{self.allow['commands'].get('test')}`"],
                         "expected": "suite runs", "actual": f"exit {regression.get('exit_code')}",
                         "evidence": (regression.get("first_error") or "")[:500]})
        for b in bugs:
            b["id"] = self.next_id("BUG")
            b["story"] = sid

        passed = bool(regression.get("ok")) and not uncovered and not any(
            b.get("severity") in ("blocker", "major") for b in bugs)
        report = self.render_qa_report(story, qa_round, run, regression, uncovered, bugs, discarded, ran_tests_itself)
        os.makedirs(os.path.join(wt, "reports", "qa"), exist_ok=True)
        with open(os.path.join(wt, "reports", "qa", f"{sid}.md"), "w", encoding="utf-8") as f:
            f.write(report)
        workspace.commit_all(wt, f"test({sid}): QA round {qa_round}", expected_branch=branch)
        self.record_review(sid, qa_agent["agent_id"], "qa", passed,
                           {"round": qa_round, "uncovered": uncovered, "bugs": bugs, "discarded_bugs": discarded,
                            "regression_ok": regression.get("ok")})
        self.emit("qa.completed", actor=qa_agent["agent_id"], task_id=sid,
                  data={"round": qa_round, "passed": passed, "bugs": len(bugs), "uncovered": uncovered})
        self._history(sid, {"kind": "qa", "round": qa_round, "passed": passed, "bugs": [b["id"] for b in bugs]})
        with self._state_lock:
            self.state.setdefault("bugs", []).extend(bugs)
            self.save_state()

        if passed:
            with self._merge_lock:
                ok, info = workspace.merge_branch(self.repo, branch, f"Merge {branch}: QA tests and report for {sid}")
            workspace.remove_worktree(self.repo, wt)
            if not ok:
                return {"passed": False, "escalate": True, "reason": f"merge conflict merging {branch}", "report": info}
            return {"passed": True, "branch": branch, "report": report, "regression": regression}

        if uncovered and regression.get("ok") and not bugs:
            # QA's own coverage gap, not a product bug: QA must finish its job.
            if qa_round >= self.max_rounds:
                return {"passed": False, "escalate": True, "reason": f"QA left ACs without tests: {uncovered}", "report": report}
        feedback_lines = [f"QA round {qa_round} failed. Bugs (with evidence from a real run):"]
        feedback_lines += [f"- {b['id']} [{b.get('severity')}] {b.get('ac', '')}: expected {b.get('expected')}, "
                           f"actual {b.get('actual')}; evidence: {b.get('evidence')}" for b in bugs]
        if uncovered:
            feedback_lines.append(f"ACs with no test naming them: {', '.join(uncovered)}")
        if regression.get("first_error"):
            feedback_lines.append(f"First error:\n{regression['first_error']}")
        workspace.remove_worktree(self.repo, wt)
        return {"passed": False, "branch": branch, "feedback": "\n".join(feedback_lines), "report": report,
                "bugs": bugs}

    def render_qa_report(self, story: Dict[str, Any], qa_round: int, run: RunResult, regression: Dict[str, Any],
                         uncovered: List[str], bugs: List[Dict[str, Any]], discarded: List[Dict[str, Any]],
                         ran_tests_itself: bool) -> str:
        tests = [t for t in (run.envelope.get("tests") or []) if isinstance(t, dict)]
        lines = [f"# QA report: {story['id']} (round {qa_round})", "",
                 "Written by code from recorded runs (Handbook 13.2.3).", "",
                 "## What ran",
                 f"- Full regression suite: `{regression.get('command', '-')}` → exit {regression.get('exit_code')}"
                 f" ({regression.get('tests_run', '?')} tests, log `{os.path.basename(regression.get('log_path', '-'))}`)",
                 f"- QA agent ran the suite itself: {'yes' if ran_tests_itself else 'no'}",
                 f"- QA agent run status: {run.status}{' (' + run.error + ')' if run.error else ''}", "",
                 "## Test cases claimed by QA", "", "| TC | AC | File |", "|---|---|---|"]
        lines += [f"| {t.get('id', '-')} | {t.get('ac', '-')} | {t.get('file', '-')} |" for t in tests] or ["| - | - | - |"]
        lines += ["", "## AC coverage", "",
                  f"- ACs without a test naming them: {', '.join(uncovered) if uncovered else 'none'}", "",
                  "## Bugs", ""]
        lines += [f"- {b['id']} [{b.get('severity')}] {b.get('ac', '')}: {b.get('actual')} — evidence: {b.get('evidence')}"
                  for b in bugs] or ["- none"]
        if discarded:
            lines += ["", "## Bug claims discarded (no evidence in the run)", ""]
            lines += [f"- {b.get('ac', '')}: {b.get('actual', '')}" for b in discarded]
        lines += ["", f"## Result: {'PASS' if regression.get('ok') and not uncovered and not bugs else 'FAIL'}"]
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------ perf

    def perf_check(self, story: Dict[str, Any]) -> Dict[str, Any]:
        if not story.get("needs_perf"):
            return {"status": "not_needed"}
        sid = story["id"]
        if shutil.which("k6") is None:
            res = {"status": "not_run", "reason": "k6 is not installed locally; performance SLOs are unverified"}
            self.emit("perf.skipped", actor="perf-1", task_id=sid, data=res)
            return res
        preview = devops.start_preview(self.session_id, projects_dir=self.projects_dir)
        if not preview.get("ok"):
            res = {"status": "not_run", "reason": f"preview did not start: {preview.get('error') or preview.get('health')}"}
            self.emit("perf.skipped", actor="perf-1", task_id=sid, data=res)
            return res
        perf_agent = self.agent_for("perf", "perf-1")
        branch = f"perf/{sid}"
        wt = workspace.create_worktree(self.repo, branch, base="main")
        pt_id = self.next_id("PT")
        sandbox = self.sandbox_for(wt, "perf", sid)
        task = (f"Write a k6 script perf/{pt_id}.js for story {sid} (open model, ramping-arrival-rate) with thresholds "
                f"for the SLOs in the context. Read the base URL from __ENV.BASE. Load numbers must cite their NFR- "
                f"source; if none is given, use a smoke profile (1-5 VUs, 1 minute) and say so. Do not run it.")
        run = self.runner(sid, perf_agent, "perf", sandbox, branch).run(task, self.story_context(story, 8000),
                                                                       task_id=f"{sid}:perf")
        script = os.path.join(wt, "perf", f"{pt_id}.js")
        if not os.path.exists(script):
            workspace.remove_worktree(self.repo, wt)
            return {"status": "failed", "reason": f"perf agent did not write {pt_id}.js ({run.error or run.status})"}
        summary_path = os.path.join(self.log_root, sid, f"{pt_id}-summary.json")
        os.makedirs(os.path.dirname(summary_path), exist_ok=True)
        proc = subprocess.run(["k6", "run", "--quiet", "--summary-export", summary_path, "-e", f"BASE={preview['url']}",
                               script], cwd=wt, capture_output=True, text=True, timeout=3600)
        workspace.commit_all(wt, f"perf({sid}): {pt_id}", expected_branch=branch)
        with self._merge_lock:
            workspace.merge_branch(self.repo, branch, f"Merge {branch}: {pt_id}")
        workspace.remove_worktree(self.repo, wt)
        res = {"status": "passed" if proc.returncode == 0 else "failed", "pt": pt_id, "exit_code": proc.returncode,
               "summary": self._load_json(summary_path, {}), "output": ((proc.stdout or "") + (proc.stderr or ""))[-1500:]}
        self.emit("perf.completed", actor=perf_agent["agent_id"], task_id=sid,
                  data={"pt": pt_id, "status": res["status"], "exit_code": proc.returncode})
        return res

    # ------------------------------------------------------------ judge

    def judge_story(self, story: Dict[str, Any], diff: str, qa: Dict[str, Any]) -> Dict[str, Any]:
        sid = story["id"]
        if int(story.get("points") or 0) <= 1:
            return {"pass": True, "skipped": True, "reason": "trivial story (<= 1 point, CI green)"}
        role = (story.get("role") or "fullstack").lower()
        rubric = self._load_json(os.path.join(SKILLS_DIR, role, "rubric.json"), None) or \
            self._load_json(os.path.join(SKILLS_DIR, "fullstack", "rubric.json"), {"criteria": []})
        criteria = rubric.get("criteria", [])
        judge_agent = self.agent_for("judge", "judge-1")
        sandbox = Sandbox(self.repo, "judge", {}, log_dir=os.path.join(self.log_root, sid), write_scope=[])
        crit_text = "\n".join(f"- {c['id']} (max {c.get('max', 3)}{', must_pass' if c.get('must_pass') else ''}): "
                              f"{c.get('description', '')}" for c in criteria)
        task = "\n".join([
            f"Score story {sid} against the {role} rubric. Tool results come first: CI is green and the QA regression "
            f"suite passed ({qa.get('regression', {}).get('tests_run', '?')} tests).",
            "Score each criterion separately on its scale, quote or point to evidence in the diff, and give a concrete "
            "fix for every lost point. List every unsupported claim (cites nothing, or an ID that does not say that).",
            "Criteria:", crit_text,
            'Finish with {"final": {"status": "done", "scores": [{"criterion": "<id>", "score": 0, "max": 3, '
            '"evidence": "...", "fix": "..."}], "unsupported_claims": [], "handoff_note": "..."}}.',
            "", "# STORY DIFF", diff[:20000],
        ])
        result: Optional[RunResult] = None
        for attempt in range(2):
            result = self.runner(sid, judge_agent, "judge", sandbox, None).run(task, self.story_context(story, 8000),
                                                                              task_id=f"{sid}:judge{attempt + 1}")
            if result.status == "done" and isinstance(result.envelope.get("scores"), list):
                break
        else:
            return {"pass": False, "escalate": True, "reason": "LLM Judge unavailable or returned an invalid verdict"}

        by_id = {c["id"]: c for c in criteria}
        scores, total, max_total, must_fail = [], 0, 0, []
        given = {str(s.get("criterion")): s for s in result.envelope["scores"] if isinstance(s, dict)}
        for cid, c in by_id.items():
            s = given.get(cid)
            cmax = int(c.get("max", 3))
            try:
                val = max(0, min(cmax, int(s.get("score", 0)))) if s else 0
            except (TypeError, ValueError):
                val = 0
            if s and not str(s.get("evidence", "")).strip():
                val = 0  # every score needs evidence
            scores.append({"criterion": cid, "score": val, "max": cmax, "evidence": (s or {}).get("evidence", ""),
                           "fix": (s or {}).get("fix", "" if s else "criterion not scored")})
            total += val
            max_total += cmax
            if c.get("must_pass") and val < cmax:
                must_fail.append(cid)
        unsupported = [u for u in (result.envelope.get("unsupported_claims") or []) if u]
        threshold = rubric.get("pass_threshold")
        if threshold and rubric.get("max_total") and rubric["max_total"] != max_total:
            threshold = round(threshold * max_total / rubric["max_total"])
        threshold = threshold if threshold is not None else round(0.8 * max_total)
        passed = total >= threshold and not must_fail and not unsupported and not result.degraded
        verdict = {"story": sid, "rubric": f"skills/{role}/rubric.json", "scores": scores, "total": total,
                   "max": max_total, "threshold": threshold, "must_pass_failed": must_fail,
                   "unsupported_claims": unsupported, "degraded": result.degraded, "pass": passed}
        self.record_review(sid, judge_agent["agent_id"], "judge", passed, verdict, score=total, max_score=max_total)
        self.emit("judge.completed", actor=judge_agent["agent_id"], task_id=sid,
                  data={"pass": passed, "total": total, "max": max_total, "must_pass_failed": must_fail})
        self._history(sid, {"kind": "judge", "pass": passed, "total": total, "max": max_total})
        feedback = "\n".join([f"- {s['criterion']}: {s['score']}/{s['max']} — fix: {s['fix']}" for s in scores
                              if s["score"] < s["max"]] + [f"- unsupported claim: {u}" for u in unsupported])
        if result.degraded:
            feedback += "\n- Judge was degraded (weaker than the author); a degraded Judge cannot pass a story."
        return {"pass": passed, "verdict": verdict, "feedback": feedback or "Judge failed the story."}

    # ------------------------------------------------------------ reporting

    def write_daily_report(self) -> str:
        """Daily report from task records and events only (Handbook 9.1.5): blockers first."""
        stories = self.state["stories"]
        conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            rows = conn.execute("SELECT agent_id, SUM(input_tokens + output_tokens), SUM(cost_usd) FROM llm_calls "
                                "WHERE project_id = ? GROUP BY agent_id ORDER BY agent_id", (self.session_id,)).fetchall()
        finally:
            conn.close()
        blocked = [s for s in stories.values() if s["status"] in ("escalated", "blocked")]
        done = [s for s in stories.values() if s["status"] in DONE_STATUSES]
        points_total = sum(int(s["story"].get("points") or 0) for s in stories.values())
        points_done = sum(int(s["story"].get("points") or 0) for s in done)
        bugs = self.state.get("bugs", [])
        lines = [f"# Daily report — {self.session_id}", "", f"Generated by code at {_now()} from task records.", "",
                 "## Blockers", ""]
        lines += [f"- {s['id']} ({s['status']}): {(s.get('escalation') or {}).get('reason') or s.get('blocked_reason', '')}"
                  f" → {(s.get('escalation') or {}).get('to', '-')}" for s in blocked] or ["- none"]
        lines += ["", "## Stories", "", "| Story | Status | Stage | Review rounds | QA rounds |", "|---|---|---|---|---|"]
        lines += [f"| {sid} | {s['status']} | {s.get('stage')} | {s.get('rounds', 0)} | {s.get('qa_rounds', 0)} |"
                  for sid, s in sorted(stories.items())]
        lines += ["", "## Metrics", "", f"- Points done: {points_done} / {points_total}",
                  f"- Bugs filed (with evidence): {len(bugs)}",
                  f"- Stories done without a performance run: {sum(1 for s in stories.values() if s['status'] == 'done_perf_not_run')}",
                  "", "## Tokens used (ledger)", "", "| Agent | Tokens | Cost (USD) |", "|---|---|---|"]
        lines += [f"| {a} | {int(t or 0):,} | {float(c or 0):.4f} |" for a, t, c in rows] or ["| - | 0 | 0 |"]
        needs_client = [e for e in self.state.get("escalations", []) if e.get("to") == "client"]
        lines += ["", "## What needs the client", ""]
        lines += [f"- {e['story']}: {e['reason']}" for e in needs_client] or ["- nothing at the moment"]
        text = "\n".join(lines) + "\n"
        reports = os.path.join(self.pdir, "reports")
        os.makedirs(reports, exist_ok=True)
        with open(os.path.join(reports, "build-daily.md"), "w", encoding="utf-8") as f:
            f.write(text)
        return text


# ---------------------------------------------------------------- background control

def start_build_in_background(session_id: str, **kwargs: Any) -> Dict[str, Any]:
    with _active_lock:
        t = _active_builds.get(session_id)
        if t and t.is_alive():
            return {"status": "already_running", "session_id": session_id}
        loop = BuildLoop(session_id, **kwargs)
        loop.prepare()

        def _run() -> None:
            try:
                loop.run()
            except Exception as e:
                logger.exception(f"build loop crashed for {session_id}")
                loop.state.update({"status": "failed", "message": f"{type(e).__name__}: {e}"})
                loop.save_state()
                loop.emit("build.failed", actor="system", data={"error": str(e)})

        thread = threading.Thread(target=_run, name=f"build-{session_id}", daemon=True)
        _active_builds[session_id] = thread
        thread.start()
    return {"status": "started", "session_id": session_id, "stories": len(loop.state["stories"])}


def get_build_state(session_id: str, projects_dir: str = DATA_PROJECTS_DIR) -> Dict[str, Any]:
    path = os.path.join(projects_dir, session_id, "build_state.json")
    if not os.path.exists(path):
        return {"session_id": session_id, "status": "not_started", "stories": {}}
    with open(path, "r", encoding="utf-8") as f:
        state = json.load(f)
    t = _active_builds.get(session_id)
    state["thread_alive"] = bool(t and t.is_alive())
    return state
