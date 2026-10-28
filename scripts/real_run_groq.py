#!/usr/bin/env python3
"""
Real end-to-end run: idea -> delivery through the engine's own API, with real model calls
(Groq primary, Ollama fallback, per config/model_router.json).

The operator plays the client: a fixed brief answers the BA (Handbook 30.2.1 scripted client
answers), and each gate is approved only when that stage's own checks passed. The run stops at
the first stage that fails and writes everything to data/projects/<id>/real_run_report.json.

Usage: python3 scripts/real_run_groq.py [--session ID]
"""

import os
import sys
import json
import time
import argparse
import traceback
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "engine"))
os.chdir(os.path.join(REPO_ROOT, "engine"))

INTAKE = {
    "project_name": "TaskNest",
    "description": "A simple to-do web app with login: people sign up, sign in, and keep a private list of to-dos "
                   "they can add, complete and delete.",
    "target_users": "Individual office staff at a 20-person accounting firm who track their own daily tasks",
    "timeline": "4 weeks for v1",
    "budget": "$2,000 build budget, under $20/month running cost; approved token budget 3000000 tokens",
}

CLIENT_ANSWER = """Here is everything I can tell you:
- Problem: our staff track daily tasks on paper and sticky notes, things get lost. Each person needs a private to-do list.
- Users: one kind of user, an office staff member (about 20 people). There is no admin role in v1.
- Main journey: sign up with email and password, sign in, add a to-do with a title, see my list, mark a to-do done, delete a to-do, sign out.
- Must have: sign up, sign in, sign out, add to-do, list my to-dos, mark done, delete. A user must never see another user's to-dos.
- Rules: a to-do title is required, 1 to 200 characters. Wrong password shows an error and does not sign in. Email must be unique.
- Won't have in v1: sharing lists, due dates, reminders, mobile app, password reset by email.
- Load: about 20 users, at most 10 at the same time, each user has fewer than 500 to-dos.
- Performance: pages and actions should respond in under 1 second on our office network.
- Data: email, password (must be stored securely, never in plain text), to-do titles. Keep data until the user deletes it. Nothing is especially sensitive beyond passwords.
- Hosting constraint: it must run on one office computer without internet access; Python is already installed there and nothing else can be installed.
- Integrations: none. No email, no payments, no outside login.
- Availability: office hours only; a restart is fine.
- Accessibility: should work with keyboard only and be readable (normal contrast).
- Platforms: desktop web browser only, English only.
- Timeline 4 weeks, budget $2,000, running cost under $20/month.
- Success after 3 months: every staff member uses it daily and nobody uses paper lists any more.
If anything is still unclear, choose a sensible option and record it as an assumption."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", help="resume an existing session id")
    args = ap.parse_args()

    import main as engine
    from fastapi.testclient import TestClient
    from llm_client import default_llm_client

    client = TestClient(engine.app)
    report = {"started_at": now(), "cloud_enabled": default_llm_client.cloud_enabled(), "stages": []}
    sid = args.session

    def save():
        if sid:
            path = os.path.join(engine.DATA_PROJECTS_DIR, sid, "real_run_report.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, default=str)

    def stage(name, method, path, body=None, ok_check=None, timeout_note=""):
        t0 = time.time()
        print(f"\n=== {name}: {method.upper()} {path}", flush=True)
        try:
            r = client.post(path, json=body) if method == "post" else client.get(path)
            data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"text": r.text}
        except Exception as e:
            data, r = {"exception": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-2000:]}, None
        status = r.status_code if r is not None else -1
        passed = status == 200 and (ok_check(data) if ok_check else True)
        entry = {"stage": name, "path": path, "http": status, "passed": passed,
                 "seconds": round(time.time() - t0, 1), "at": now(),
                 "result": json.loads(json.dumps(data, default=str))}
        report["stages"].append(entry)
        save()
        summary = json.dumps(data, default=str)
        print(f"--> HTTP {status} passed={passed} in {entry['seconds']}s :: {summary[:600]}", flush=True)
        return passed, data

    def stop(reason):
        report["stopped_at"] = now()
        report["stopped_reason"] = reason
        save()
        print(f"\nSTOPPED: {reason}", flush=True)
        return 1

    # ---------------------------------------------------------------- Stage 1: BA
    if not sid:
        ok, data = stage("ba.start", "post", "/ba/start", INTAKE)
        if not ok:
            return stop("BA intake failed")
        sid = data["session_id"]
        report["session_id"] = sid
        save()
        print(f"SESSION: {sid}", flush=True)
        for rnd in range(1, 8):
            ok, data = stage(f"ba.message.{rnd}", "post", "/ba/message", {"session_id": sid, "message": CLIENT_ANSWER})
            if not ok:
                return stop(f"BA round {rnd} failed")
            if data.get("ready_for_requirements"):
                break
        ok, data = stage("ba.requirements", "get", f"/ba/requirements/{sid}")
        if not ok:
            return stop("requirements.md not produced")

    report["session_id"] = sid
    pdir = os.path.join(engine.DATA_PROJECTS_DIR, sid)

    # One run per project at a time: two runs would compete for quota and overwrite each other's files.
    import fcntl
    lock_file = open(os.path.join(pdir, ".real_run.lock"), "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(f"Another real run is already working on {sid}; not starting a second one.", flush=True)
        return 2

    def load_state(name):
        path = os.path.join(pdir, name)
        return json.load(open(path)) if os.path.exists(path) else {}

    # Resume: never redo a stage whose result already passed (an approved PRD must not change under the client).
    pm_done = (load_state("pm_state.json").get("judge_verdict") or {}).get("pass") and \
        load_state("session_state.json").get("gate1_approved")
    arch_state0 = load_state("architect_state.json")
    arch_done = arch_state0.get("status") == "done"
    # Documents exist but did not pass: re-judge them (the re-judge rebuilds only failing parts).
    # A full regeneration happens only when the documents are missing or marked stale.
    arch_rejudge_only = arch_state0.get("status") == "review_failed"
    report.setdefault("resumed", {})["skipped"] = [n for n, d in (("pm+gate1", pm_done), ("architect", arch_done)) if d]
    save()
    # ---------------------------------------------------------------- Stage 2: PM, feasibility, Gate 1
    # A stage counts as passed only when its own Judge passed it (Handbook 2.7.3 step 9).
    pm_ok = lambda d: bool(d.get("prd_content")) and bool((d.get("judge_verdict") or {}).get("pass"))
    if not pm_done:
        for pm_try in (1, 2):
            ok, data = stage(f"pm.start.{pm_try}", "post", "/pm/start", {"session_id": sid}, ok_check=pm_ok)
            if ok:
                break
        if not ok:
            verdict = (data.get("judge_verdict") or {}) if isinstance(data, dict) else {}
            return stop(f"PM / PRD not passed: {verdict.get('verdict_summary') or data.get('exception', '')[:300]}")
        ok, data = stage("architect.feasibility", "post", "/feasibility/start", {"session_id": sid})
        if not ok:
            return stop("feasibility check failed")
        ok, data = stage("gate1.approve", "post", "/gate1/approve",
                         {"session_id": sid, "client_notes": "Real run: operator approved the PRD as the client."})
        if not ok:
            return stop("Gate 1 not approved")

    # ---------------------------------------------------------------- Stage 3: Architect, Designer
    if not arch_done and not arch_rejudge_only:
        ok, data = stage("architect.start", "post", "/architect/start", {"session_id": sid})
        if not ok:
            return stop("Architect failed")
    arch_state = json.load(open(os.path.join(engine.DATA_PROJECTS_DIR, sid, "architect_state.json")))
    arch_verdict = arch_state.get("judge_verdict", {}) or {}
    if not arch_verdict.get("pass"):
        # Re-judge the existing documents; failing parts are rebuilt with the findings inside the endpoint.
        ok, data = stage("architect.rejudge", "post", "/architect/rejudge", {"session_id": sid})
        arch_verdict = (data.get("judge_verdict") or {}) if ok else arch_verdict
    report["architect_verdict"] = {k: arch_verdict.get(k) for k in ("pass", "total", "max", "verdict_summary")}
    save()
    if not arch_verdict.get("pass"):
        return stop(f"Architecture not passed by the Judge: {arch_verdict.get('verdict_summary')}")
    ok, data = stage("designer.generate", "post", f"/designer/generate/{sid}", None)
    if not ok:
        return stop("Designer failed")
    design_state = json.load(open(os.path.join(engine.DATA_PROJECTS_DIR, sid, "designer_state.json")))
    report["designer_verdict"] = {"validation_passed": design_state.get("validation", {}).get("all_passed"),
                                  "judge_pass": design_state.get("judge_verdict", {}).get("pass"),
                                  "errors": design_state.get("validation", {}).get("errors", [])[:10]}
    save()
    if not (report["designer_verdict"]["validation_passed"] and report["designer_verdict"]["judge_pass"]):
        return stop(f"Design not passed: {report['designer_verdict']}")

    # ---------------------------------------------------------------- Stage 4: HR, Recruiter, Gate 2
    ok, data = stage("hr.plan", "post", f"/hr/plan/{sid}")
    if not ok:
        return stop("HR team plan failed")
    ok, data = stage("recruiter.hire", "post", f"/recruiter/hire/{sid}")
    if not ok:
        return stop("Recruiter failed")
    ok, data = stage("gate2.approve", "post", "/gate2/approve",
                     {"session_id": sid, "client_notes": "Real run: operator approved team, tiers and budget."})
    if not ok:
        return stop("Gate 2 not approved")

    # ---------------------------------------------------------------- Stage 5: Scrum, readiness
    ok, data = stage("scrum.start", "post", f"/scrum/start/{sid}")
    if not ok:
        return stop("Scrum backlog failed")
    ok, data = stage("readiness", "post", f"/readiness/{sid}", ok_check=lambda d: d.get("verdict") == "ready")
    if not ok:
        return stop("readiness verdict is not ready")

    # ---------------------------------------------------------------- Stage 6-7: build
    ok, data = stage("allowlist.get", "get", f"/build/allowlist/{sid}")
    ok, data = stage("allowlist.approve", "post", "/build/allowlist/approve", {"session_id": sid})
    if not ok:
        return stop("allowlist rejected")
    ok, data = stage("build.start", "post", f"/build/start/{sid}")
    if not ok:
        return stop("build did not start")
    last = None
    while True:
        st = client.get(f"/build/status/{sid}").json()
        line = {k: v.get("status") for k, v in st.get("stories", {}).items()}
        if line != last:
            print(f"[{now()}] build {st.get('status')}: {line}", flush=True)
            last = line
        if not st.get("thread_alive") and st.get("status") != "running":
            break
        time.sleep(10)
    report["build"] = {"status": st.get("status"), "message": st.get("message"),
                       "stories": {k: {x: v.get(x) for x in ("status", "rounds", "qa_rounds", "escalation", "perf")}
                                   for k, v in st.get("stories", {}).items()},
                       "bugs": st.get("bugs", [])}
    save()
    if st.get("status") not in ("complete", "complete_with_issues"):
        return stop(f"build ended with status {st.get('status')}: {st.get('message')}")

    # ---------------------------------------------------------------- Stage 8-9
    ok, data = stage("beta.start", "post", f"/beta/start/{sid}")
    if not ok:
        return stop("Beta / Gate 3 could not open")
    if not (data.get("details", {}).get("preview", {}) or {}).get("ok"):
        return stop("preview is not healthy; Gate 3 left open for review")
    ok, data = stage("gate3.approve", "post", "/gate3/approve", {"session_id": sid, "note": "Real run: preview checked"})
    ok, data = stage("release.prepare", "post", f"/release/prepare/{sid}")
    if not ok:
        return stop("release preparation failed")
    ok, data = stage("gate4.approve", "post", "/gate4/approve", {"session_id": sid, "note": "Real run: go live"})
    ok, data = stage("deliver", "post", f"/deliver/{sid}")
    report["finished_at"] = now()
    save()
    print("\nREAL RUN FINISHED", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
