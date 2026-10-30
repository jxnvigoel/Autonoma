"""
Stage 8 Beta, Stage 9 Release and Delivery (Handbook 2.6, 2.7.9-2.7.10, 16.2, 32 steps 28-32).

  Beta:     [code] preview with seed data, runtime errors captured  ->  Gate 3 (client UAT)
            UAT feedback goes through the BA as new Q- entries; bugs re-enter Stage 6 as UAT stories.
  Release:  [code] CI on main, release tag, rollback drill, backup/restore drill, image, runbook
            ->  Gate 4 (go live)
  Deliver:  [code] repo bundle, docs, runbook, final report (scope, tests, SLOs, tokens and cost).

Everything shown at a gate comes from recorded runs; nothing is restated by a model.
"""

import os
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

try:
    import workspace
    import devops
    import events
    from sandbox import Sandbox
    from build_loop import get_build_state, DONE_STATUSES
except ImportError:
    from engine import workspace, devops, events
    from engine.sandbox import Sandbox
    from engine.build_loop import get_build_state, DONE_STATUSES

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PROJECTS_DIR = os.path.join(PROJECT_ROOT, "data", "projects")
DEFAULT_DB_PATH = os.path.join(PROJECT_ROOT, "data", "office.db")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pdir(session_id: str, projects_dir: str) -> str:
    return os.path.join(projects_dir, session_id)


def _load(path: str, default: Any) -> Any:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def _save(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


# ------------------------------------------------------------------ gates

def gate_state(session_id: str, gate: int, projects_dir: Optional[str] = None) -> Dict[str, Any]:
    projects_dir = projects_dir or DATA_PROJECTS_DIR
    return _load(os.path.join(_pdir(session_id, projects_dir), f"gate{gate}_state.json"),
                 {"session_id": session_id, "gate": gate, "status": "not_open", "approved": False})


def open_gate(session_id: str, gate: int, summary_md: str, details: Dict[str, Any],
              projects_dir: Optional[str] = None, db_path: Optional[str] = None) -> Dict[str, Any]:
    db_path = db_path or DEFAULT_DB_PATH
    projects_dir = projects_dir or DATA_PROJECTS_DIR
    try:
        from skill_registry import init_approvals_db
    except ImportError:
        from engine.skill_registry import init_approvals_db
    init_approvals_db(db_path)
    approval_id = f"GATE-{gate}-{session_id[:8]}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        conn.execute("INSERT INTO approvals (id, project_id, gate, summary, status) VALUES (?, ?, ?, ?, 'open')",
                     (approval_id, session_id, gate, summary_md))
        conn.commit()
    finally:
        conn.close()
    state = {"session_id": session_id, "gate": gate, "status": "open", "approved": False, "approval_id": approval_id,
             "opened_at": _now(), "summary": summary_md, "details": details}
    _save(os.path.join(_pdir(session_id, projects_dir), f"gate{gate}_state.json"), state)
    events.emit(session_id, "gate.opened", actor="system", data={"gate": gate, "approval_id": approval_id}, db_path=db_path)
    return state


def decide_gate(session_id: str, gate: int, approved: bool, note: str = "",
                projects_dir: Optional[str] = None, db_path: Optional[str] = None) -> Dict[str, Any]:
    db_path = db_path or DEFAULT_DB_PATH
    projects_dir = projects_dir or DATA_PROJECTS_DIR
    state = gate_state(session_id, gate, projects_dir)
    if state.get("status") != "open":
        raise HTTPException(status_code=409, detail=f"Gate {gate} is not open (status: {state.get('status')})")
    status = "approved" if approved else "changes_requested"
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        conn.execute("UPDATE approvals SET status = ?, note = ?, decided_at = datetime('now') WHERE id = ?",
                     (status, note, state["approval_id"]))
        conn.commit()
    finally:
        conn.close()
    state.update({"status": status, "approved": approved, "decided_at": _now(), "note": note})
    _save(os.path.join(_pdir(session_id, projects_dir), f"gate{gate}_state.json"), state)
    events.emit(session_id, f"gate.{status}", actor="client", data={"gate": gate, "note": note}, db_path=db_path)
    return state


def require_gate(session_id: str, gate: int, projects_dir: Optional[str] = None) -> None:
    projects_dir = projects_dir or DATA_PROJECTS_DIR
    if not gate_state(session_id, gate, projects_dir).get("approved"):
        raise HTTPException(status_code=403, detail={"error": f"GATE_{gate}_LOCKED", "session_id": session_id,
                                                     "rule": f"Handbook 2.6: Gate {gate} must be approved by the client first."})


# ------------------------------------------------------------------ Stage 8: Beta

def _latest_test_runs(session_id: str, db_path: str) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT task_id, kind, passed, total, failed, log_path, at FROM test_runs WHERE project_id = ? "
                            "AND id IN (SELECT MAX(id) FROM test_runs WHERE project_id = ? GROUP BY task_id, kind) "
                            "ORDER BY task_id, kind", (session_id, session_id)).fetchall()
    except sqlite3.OperationalError:
        rows = []
    finally:
        conn.close()
    return [dict(r) for r in rows]


def known_issues(build: Dict[str, Any], preview: Optional[Dict[str, Any]] = None) -> List[str]:
    issues = []
    for sid, s in sorted(build.get("stories", {}).items()):
        if s["status"] == "escalated":
            e = s.get("escalation") or {}
            issues.append(f"{sid} escalated to {e.get('to')}: {e.get('reason')}")
        elif s["status"] == "blocked":
            issues.append(f"{sid} blocked: {s.get('blocked_reason', '')}")
        elif s["status"] == "done_perf_not_run":
            issues.append(f"{sid}: performance not verified ({(s.get('perf') or {}).get('reason', '')})")
    for err in (preview or {}).get("runtime_errors", []) or []:
        issues.append(f"runtime error in preview: {err.splitlines()[-1][:200] if err else ''}")
    return issues


def start_beta(session_id: str, projects_dir: Optional[str] = None, db_path: Optional[str] = None) -> Dict[str, Any]:
    db_path = db_path or DEFAULT_DB_PATH
    projects_dir = projects_dir or DATA_PROJECTS_DIR
    build = get_build_state(session_id, projects_dir)
    if build.get("status") not in ("complete", "complete_with_issues"):
        raise HTTPException(status_code=409, detail=f"Build is not finished (status: {build.get('status')})")
    done = [sid for sid, s in build["stories"].items() if s["status"] in DONE_STATUSES]
    if not done:
        raise HTTPException(status_code=409, detail="No story is done; there is nothing to preview")
    repo = workspace.repo_path(session_id, projects_dir)
    beta_tags = workspace.git(["tag", "--list", "beta-*"], repo)[1].split()
    beta_tag = workspace.tag(repo, f"beta-{len(beta_tags) + 1}", "Build shown to the client at Gate 3")
    preview = devops.start_preview(session_id, projects_dir=projects_dir)
    tests = _latest_test_runs(session_id, db_path)
    issues = known_issues(build, preview)
    if not preview.get("ok"):
        issues.insert(0, f"preview did not start: {preview.get('error') or preview.get('health')}")
    lines = ["# Gate 3: Beta / UAT", "",
             f"- Build: `{beta_tag}` ({workspace.head_sha(repo)})",
             f"- Preview URL: {preview.get('url', '-') if preview.get('ok') else 'not running'}",
             f"- Health: {'OK' if preview.get('ok') else 'FAILED'} ({(preview.get('health') or {}).get('path', '-')})",
             f"- Seed data: {('exit ' + str(preview['seed']['exit_code'])) if preview.get('seed') else 'no seed command'}",
             f"- Stories done: {len(done)} / {len(build['stories'])}", "", "## Test report (latest run per story)", "",
             "| Story | Kind | Passed | Total | Failed |", "|---|---|---|---|---|"]
    lines += [f"| {t['task_id']} | {t['kind']} | {'yes' if t['passed'] else 'no'} | {t['total']} | {t['failed']} |" for t in tests]
    lines += ["", "## Known issues", ""] + ([f"- {i}" for i in issues] or ["- none"])
    events.emit(session_id, "phase.entered", actor="system", data={"phase": "beta"}, db_path=db_path)
    return open_gate(session_id, 3, "\n".join(lines) + "\n",
                     {"preview": {k: preview.get(k) for k in ("url", "ok", "health", "log_path")},
                      "tests": tests, "known_issues": issues}, projects_dir, db_path)


def uat_feedback(session_id: str, feedback: str, kind: str = "bug", projects_dir: Optional[str] = None,
                 db_path: Optional[str] = None) -> Dict[str, Any]:
    """Client UAT feedback goes through the BA as a Q-; a bug re-enters Stage 6 as a UAT story."""
    db_path = db_path or DEFAULT_DB_PATH
    projects_dir = projects_dir or DATA_PROJECTS_DIR
    pdir = _pdir(session_id, projects_dir)
    qa_log_path = os.path.join(pdir, "qa_log.json")
    qa_log = _load(qa_log_path, [])
    nums = [int(q["id"].split("-")[1]) for q in qa_log if str(q.get("id", "")).startswith("Q-") and q["id"].split("-")[1].isdigit()]
    q_id = f"Q-{(max(nums) + 1) if nums else 1:03d}"
    qa_log.append({"id": q_id, "question": "Gate 3 UAT feedback from the client (relayed by the BA)",
                   "answer": feedback, "source": "uat", "kind": kind, "at": _now()})
    _save(qa_log_path, qa_log)
    created: Dict[str, Any] = {"q_id": q_id}
    if kind == "bug":
        uat_path = os.path.join(pdir, "uat_stories.json")
        uat = _load(uat_path, {"stories": []})
        backlog = _load(os.path.join(pdir, "docs", "backlog.json"), {"stories": []})
        all_ids = [s["id"] for s in backlog.get("stories", []) + uat["stories"]]
        nums = [int(i.split("-")[1]) for i in all_ids if i.split("-")[1].isdigit()]
        st_id = f"ST-{(max(nums) + 1) if nums else 1:03d}"
        story = {"id": st_id, "title": f"UAT fix: {feedback[:70]}", "role": "fullstack", "points": 2,
                 "refs": {"features": [], "ac": [], "api": [], "tables": [], "q": [q_id]}, "depends_on": [],
                 "needs_perf": False, "source": "uat",
                 "definition_of_done": [f"Client feedback {q_id} is addressed", "A regression test reproduces the report",
                                        "Tech Lead approved", "Full regression suite green"]}
        uat["stories"].append(story)
        _save(uat_path, uat)
        created["story"] = story
    else:
        created["open_question"] = (f"{q_id} asks for a scope change; it needs PM re-planning and a new Gate 1 decision "
                                    f"before it is built.")
    if gate_state(session_id, 3, projects_dir).get("status") == "open":
        decide_gate(session_id, 3, False, f"UAT feedback {q_id}: {feedback[:200]}", projects_dir, db_path)
    events.emit(session_id, "question.answered", actor="client", data={"id": q_id, "kind": kind}, db_path=db_path)
    return created


# ------------------------------------------------------------------ Stage 9: Release

def rollback_target(repo: str, version: str) -> str:
    """
    What a rollback goes back to: the previous release if there is one, else the last build the
    client tested at Gate 3 that differs from the release candidate, else main's previous commit.
    """
    _, head = workspace.git(["rev-parse", "HEAD"], repo)
    head = head.strip()
    releases = [t for t in workspace.git(["tag", "--list", "v*", "--sort=creatordate"], repo)[1].split()
                if t not in (version, f"{version}-rc")]
    if releases:
        return releases[-1]
    for t in reversed(workspace.git(["tag", "--list", "beta-*", "--sort=creatordate"], repo)[1].split()):
        if workspace.git(["rev-list", "-n", "1", t], repo)[1].strip() != head:
            return t
    return workspace.git(["rev-parse", "HEAD~1"], repo)[1].strip()


def prepare_release(session_id: str, version: str = "v1.0.0", projects_dir: Optional[str] = None,
                    db_path: Optional[str] = None) -> Dict[str, Any]:
    db_path = db_path or DEFAULT_DB_PATH
    projects_dir = projects_dir or DATA_PROJECTS_DIR
    require_gate(session_id, 3, projects_dir)
    repo = workspace.repo_path(session_id, projects_dir)
    pdir = _pdir(session_id, projects_dir)
    allow = devops.get_allowlist(session_id, projects_dir)
    workspace.assert_no_remote(repo)

    ci = devops.run_ci(Sandbox(repo, "devops", allow["commands"], log_dir=os.path.join(pdir, ".virtualoffice", "logs", "release"),
                               network_allowed=bool(allow.get("network_allowed"))))
    previous_ref = rollback_target(repo, version)
    workspace.tag(repo, f"{version}-rc", f"Release candidate {version}")

    rollback = devops.rollback_drill(session_id, f"{version}-rc", previous_ref, projects_dir)
    restore = devops.backup_restore_drill(session_id, projects_dir)
    image = devops.build_image(session_id, f"autonoma/{session_id[:12]}:{version}", projects_dir)
    preview = devops.get_preview_state(session_id, projects_dir)
    runbook = devops.render_runbook(session_id, ci, preview, rollback, restore, image, projects_dir)
    with open(os.path.join(repo, "docs", "runbook.md"), "w", encoding="utf-8") as f:
        f.write(runbook)
    workspace.commit_all(repo, f"docs: runbook for {version} (rendered from recorded runs)", expected_branch="main")

    build = get_build_state(session_id, projects_dir)
    perf = {sid: s.get("perf", {"status": "not_needed"}) for sid, s in build.get("stories", {}).items()}
    checks = {"ci_green": ci["green"], "rollback_tested": bool(rollback.get("ok")),
              "restore_tested": bool(restore.get("ok")), "image_built": bool(image.get("ok"))}
    record = {"version": version, "at": _now(), "ci": ci, "rollback": rollback, "restore": restore, "image": image,
              "perf": perf, "checks": checks, "previous_ref": previous_ref}
    _save(os.path.join(pdir, "release_state.json"), record)

    lines = [f"# Gate 4: Go live — {version}", "", "## Release checks (recorded runs)", "",
             "| Check | Result |", "|---|---|"]
    lines += [f"| {k.replace('_', ' ')} | {'PASS' if v else 'NOT MET'} |" for k, v in checks.items()]
    if not image.get("ok"):
        lines.append(f"\nImage: {image.get('reason') or '; '.join(image.get('problems', []))}")
    if restore.get("not_run"):
        lines.append(f"\nBackup/restore: {restore.get('reason')}")
    lines += ["", "## Performance", ""]
    lines += [f"- {sid}: {p.get('status')}{' — ' + p.get('reason', '') if p.get('reason') else ''}"
              for sid, p in sorted(perf.items()) if p.get("status") != "not_needed"] or ["- no story needed a performance test"]
    lines += ["", "## Release notes", ""]
    lines += [f"- {c['sha']} {c['subject']}" for c in workspace.log(repo, 40) if c["subject"].startswith("Merge ")]
    lines += ["", "## Known issues", ""] + ([f"- {i}" for i in known_issues(build, preview)] or ["- none"])
    lines += ["", "Runbook: docs/runbook.md (every command in it was run)."]
    events.emit(session_id, "phase.entered", actor="system", data={"phase": "release", "version": version}, db_path=db_path)
    return open_gate(session_id, 4, "\n".join(lines) + "\n", {"checks": checks, "version": version}, projects_dir, db_path)


def deliver(session_id: str, projects_dir: Optional[str] = None, db_path: Optional[str] = None) -> Dict[str, Any]:
    db_path = db_path or DEFAULT_DB_PATH
    projects_dir = projects_dir or DATA_PROJECTS_DIR
    require_gate(session_id, 4, projects_dir)
    pdir = _pdir(session_id, projects_dir)
    repo = workspace.repo_path(session_id, projects_dir)
    release = _load(os.path.join(pdir, "release_state.json"), {})
    version = release.get("version", "v1.0.0")
    workspace.tag(repo, version, f"Release {version} (Gate 4 approved)")
    out = os.path.join(pdir, "delivery", version)
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    workspace.git(["bundle", "create", os.path.join(out, "repo.bundle"), "--all"], repo)
    shutil.copytree(os.path.join(repo, "docs"), os.path.join(out, "docs"))
    report = render_final_report(session_id, release, projects_dir, db_path)
    with open(os.path.join(out, "final-report.md"), "w", encoding="utf-8") as f:
        f.write(report)
    devops.stop_preview(session_id, projects_dir)
    events.emit(session_id, "project.delivered", actor="system", data={"version": version, "path": out}, db_path=db_path)
    return {"status": "delivered", "version": version, "path": out,
            "files": sorted(os.listdir(out)), "report": report}


def render_final_report(session_id: str, release: Dict[str, Any], projects_dir: str, db_path: str) -> str:
    """Scope delivered, tests, SLOs, tokens and cost — all from records (Handbook 2.7.10 step 32)."""
    build = get_build_state(session_id, projects_dir)
    stories = build.get("stories", {})
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        by_role = conn.execute("SELECT agent_id, provider, model, COUNT(*), SUM(input_tokens), SUM(output_tokens), "
                               "SUM(cost_usd) FROM llm_calls WHERE project_id = ? GROUP BY agent_id, provider, model "
                               "ORDER BY agent_id", (session_id,)).fetchall()
        gates = conn.execute("SELECT gate, status, opened_at, decided_at, note FROM approvals WHERE project_id = ? "
                             "ORDER BY opened_at", (session_id,)).fetchall()
    finally:
        conn.close()
    tests = _latest_test_runs(session_id, db_path)
    lines = [f"# Final report — {session_id}", "", f"Release {release.get('version')} · generated by code at {_now()}", "",
             "## Scope delivered", "", "| Story | Title | Status | Review rounds | QA rounds |", "|---|---|---|---|---|"]
    for sid, s in sorted(stories.items()):
        lines.append(f"| {sid} | {s['story'].get('title', '')[:60]} | {s['status']} | {s.get('rounds', 0)} | {s.get('qa_rounds', 0)} |")
    done = sum(1 for s in stories.values() if s["status"] in DONE_STATUSES)
    lines += ["", f"Done: {done} / {len(stories)} stories.", "", "## Tests (latest run per story)", "",
              "| Story | Kind | Passed | Total | Failed |", "|---|---|---|---|---|"]
    lines += [f"| {t['task_id']} | {t['kind']} | {'yes' if t['passed'] else 'no'} | {t['total']} | {t['failed']} |" for t in tests]
    lines += ["", "## Release checks", ""]
    lines += [f"- {k.replace('_', ' ')}: {'PASS' if v else 'NOT MET'}" for k, v in (release.get("checks") or {}).items()]
    lines += ["", "## SLOs / performance", ""]
    lines += [f"- {sid}: {p.get('status')}{' — ' + p['reason'] if p.get('reason') else ''}"
              for sid, p in sorted((release.get("perf") or {}).items()) if p.get("status") != "not_needed"] or ["- none required"]
    lines += ["", "## Tokens and cost (ledger)", "", "| Agent | Provider | Model | Calls | Input | Output | Cost (USD) |",
              "|---|---|---|---|---|---|---|"]
    tot_in = tot_out = 0
    tot_cost = 0.0
    for agent, prov, model, n, i, o, c in by_role:
        tot_in, tot_out, tot_cost = tot_in + (i or 0), tot_out + (o or 0), tot_cost + (c or 0.0)
        lines.append(f"| {agent} | {prov} | {model} | {n} | {int(i or 0):,} | {int(o or 0):,} | {float(c or 0):.4f} |")
    lines += [f"| **total** | | | | {tot_in:,} | {tot_out:,} | {tot_cost:.4f} |", "", "## Gates", ""]
    lines += [f"- Gate {g}: {st} (opened {o}, decided {d or '-'}){' — ' + n if n else ''}" for g, st, o, d, n in gates]
    lines += ["", "## Known issues", ""] + ([f"- {i}" for i in known_issues(build)] or ["- none"])
    return "\n".join(lines) + "\n"
