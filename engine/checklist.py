"""
Company checklist: every stage, every feature and every acceptance test of the project, with who owns it.

Nothing is ticked by hand. Each item's status is read from the project's own records (documents, gate
states, the backlog, the build state and QA's per-criterion results), so the checklist updates the moment
a task finishes, and it can never say "done" for work that is not. Owners come from the Scrum Master's
assignments in docs/backlog.json (story.owner) and the Recruiter's hires.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PROJECTS_DIR = os.path.join(PROJECT_ROOT, "data", "projects")

DONE, ACTIVE, TODO, BLOCKED, ATTENTION = "done", "in_progress", "todo", "blocked", "needs_attention"
STORY_DONE = {"done", "done_perf_not_run"}
STORY_BUILT = STORY_DONE | {"merged", "qa"}


def _load(path: str, default: Any = None) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _exists(*parts: str) -> bool:
    return os.path.exists(os.path.join(*parts))


def parse_prd_features(prd_md: str) -> List[Dict[str, Any]]:
    """
    Features (id, name, priority) and the acceptance criteria under each feature's section. Accepts every
    PRD layout the PM has written: "### Feature F-001: X" or "### F-001: X" headings, AC tables
    ("| AC-001 | ... |") or AC bullets ("- AC-001: ..."), and the summary table.
    """
    clean = lambda t: re.sub(r"\*+", "", t).strip()
    summary = {}
    for m in re.finditer(r"^\|\s*(F-\d{3})\s*\|\s*([^|]+?)\s*\|[^|]*\|\s*([^|]+?)\s*\|", prd_md, re.M):
        summary[m.group(1)] = {"name": clean(m.group(2)), "priority": clean(m.group(3))}
    feats = []
    sections = list(re.finditer(r"^###\s+(?:Feature\s+)?(F-\d{3})\s*[:\-\u2013\u2014]\s*(.+)$", prd_md, re.M))
    for i, sec in enumerate(sections):
        body = prd_md[sec.end(): sections[i + 1].start() if i + 1 < len(sections) else len(prd_md)]
        body = re.split(r"^##\s", body, maxsplit=1, flags=re.M)[0]
        acs, seen = [], set()
        for m in re.finditer(r"^(?:\|\s*\**(AC-\d{3})\**\s*\|\s*(.+?)\s*\|\s*$|\s*[-*]\s+\**(AC-\d{3})\**\s*[:\-]\s*(.+)$)",
                             body, re.M):
            ac_id, text = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
            if ac_id not in seen:
                seen.add(ac_id)
                acs.append({"id": ac_id, "text": re.sub(r"\s+", " ", clean(text))})
        prio = re.search(r"\*\*Priority\*\*:\s*(.+)", body)
        fid = sec.group(1)
        feats.append({"id": fid, "name": summary.get(fid, {}).get("name") or clean(sec.group(2)),
                      "priority": summary.get(fid, {}).get("priority") or (clean(prio.group(1)) if prio else ""),
                      "acs": acs})
    known = {f["id"] for f in feats}
    feats += [{"id": fid, **v, "acs": []} for fid, v in summary.items() if fid not in known]
    return sorted(feats, key=lambda f: f["id"])


def hr_planned(docs_dir: str) -> bool:
    """HR's plan, not the Architect's draft of the same file (older projects: hiring already happened)."""
    plan = _load(os.path.join(docs_dir, "team-plan.json"), {}) or {}
    return plan.get("planned_by") == "hr" or (bool(plan) and _exists(docs_dir, "staffing-report.md"))


def _agents(session_id: str) -> Dict[str, Dict[str, Any]]:
    try:
        from skill_registry import get_agents_by_project
    except ImportError:
        from engine.skill_registry import get_agents_by_project
    try:
        return {a["id"]: a for a in get_agents_by_project(session_id) or []}
    except Exception:
        return {}


def _item(id_: str, title: str, status: str, owner: str, detail: str = "", owner_agent: Optional[Dict[str, Any]] = None,
          refs: Optional[List[str]] = None) -> Dict[str, Any]:
    return {"id": id_, "title": title, "status": status, "owner_role": owner, "detail": detail,
            "owner_agent": {"id": owner_agent.get("id"), "name": owner_agent.get("name"), "role": owner_agent.get("role")}
            if owner_agent else None, "refs": refs or []}


def build_checklist(session_id: str, projects_dir: Optional[str] = None,
                    running_jobs: Optional[List[str]] = None) -> Dict[str, Any]:
    pdir = os.path.join(projects_dir or DATA_PROJECTS_DIR, session_id)
    docs = os.path.join(pdir, "docs")
    running = set(running_jobs or [])
    session_state = _load(os.path.join(pdir, "session_state.json"), {}) or {}
    pm_state = _load(os.path.join(pdir, "pm_state.json"), {}) or {}
    arch_state = _load(os.path.join(pdir, "architect_state.json"), {}) or {}
    gate2 = _load(os.path.join(pdir, "gate2_state.json"), {}) or {}
    readiness = _load(os.path.join(pdir, "readiness_state.json"), {}) or {}
    build = _load(os.path.join(pdir, "build_state.json"), {}) or {}
    backlog = _load(os.path.join(docs, "backlog.json"), {}) or {}
    stories = backlog.get("stories", []) if isinstance(backlog, dict) else []
    build_stories = build.get("stories", {}) or {}
    gate = {n: _load(os.path.join(pdir, f"gate{n}_state.json"), {}) or {} for n in (3, 4)}
    agents = _agents(session_id)
    # Scrum may record an owner as the hired agent's full id ("<project>_be-1") or its short id ("be-1").
    agents.update({k[len(session_id) + 1:]: v for k, v in list(agents.items()) if k.startswith(session_id + "_")})
    qa_log = _load(os.path.join(pdir, "qa_log.json"), []) or []
    delivered = os.path.isdir(os.path.join(pdir, "delivery"))

    def st(done: bool, active: bool = False, attention: bool = False) -> str:
        return DONE if done else ACTIVE if active else ATTENTION if attention else TODO

    prd_passed = bool((pm_state.get("judge_verdict") or {}).get("pass"))
    arch_passed = bool((arch_state.get("judge_verdict") or {}).get("pass")) or arch_state.get("status") == "review_passed"
    build_status = build.get("status", "not_started")
    final_reg = build.get("final_regression")
    counts: Dict[str, int] = {}
    for s in build_stories.values():
        counts[s.get("status", "todo")] = counts.get(s.get("status", "todo"), 0) + 1

    stages = [
        _item("CHK-01", "Discovery: client questions answered", st(_exists(docs, "requirements.md"), bool(qa_log)),
              "Business Analyst", f"{len(qa_log)} answers recorded"),
        _item("CHK-02", "PRD written and passed the Judge", st(_exists(docs, "prd.md") and prd_passed, "pm" in running,
              _exists(docs, "prd.md") and not prd_passed), "Product Manager",
              "Judge: " + (f"{pm_state['judge_verdict'].get('total')}/{pm_state['judge_verdict'].get('max')}"
                           if pm_state.get("judge_verdict") else "not reviewed yet")),
        _item("CHK-03", "Gate 1: client approved the PRD", st(bool(session_state.get("gate1_approved")),
              attention=session_state.get("gate1_status") == "changes_requested"), "Client",
              "changes requested" if session_state.get("gate1_status") == "changes_requested" else ""),
        _item("CHK-04", "Architecture, API and schema passed review", st(_exists(docs, "architecture.md") and arch_passed,
              bool({"architect", "feasibility"} & running), _exists(docs, "architecture.md") and not arch_passed),
              "Solution Architect", arch_state.get("status", "")),
        _item("CHK-05", "Screens and user flows designed", st(_exists(docs, "app-flow.md"), "designer" in running),
              "UI/UX Designer"),
        _item("CHK-06", "Team planned", st(hr_planned(docs), "hr" in running), "HR"),
        _item("CHK-07", "Agents hired", st(_exists(docs, "staffing-report.md"), "recruiter" in running), "Recruiter",
              f"{len(agents)} agents" if agents else ""),
        _item("CHK-08", "Gate 2: client approved team and budget", st(bool(gate2.get("approved"))), "Client"),
        _item("CHK-09", "Backlog written and stories assigned", st(bool(stories), "scrum" in running), "Scrum Master",
              f"{len(stories)} stories, {sum(1 for s in stories if s.get('owner'))} assigned" if stories else ""),
        _item("CHK-10", "Tech Lead: ready to build", st(readiness.get("verdict") == "ready", "readiness" in running,
              bool(readiness) and readiness.get("verdict") != "ready"), "Tech Lead", readiness.get("verdict", "")),
        _item("CHK-11", "Every story built, reviewed and QA-tested",
              st(build_status == "complete", build_status == "running" or bool(build.get("thread_alive")),
                 build_status in ("complete_with_issues", "failed") or build_status.startswith("paused")),
              "Engineers + QA", ", ".join(f"{v} {k}" for k, v in sorted(counts.items()))),
        _item("CHK-12", "Full regression of the whole app passed",
              st(bool(final_reg and final_reg.get("ok")), attention=bool(final_reg and not final_reg.get("ok"))), "QA",
              (f"{len(final_reg.get('failing_tests') or [])} failing" if final_reg and not final_reg.get("ok") else "")
              if final_reg else ""),
        _item("CHK-13", "Gate 3: client accepted the beta", st(bool(gate[3].get("approved")),
              gate[3].get("status") == "open"), "Client"),
        _item("CHK-14", "Gate 4: release approved", st(bool(gate[4].get("approved")), gate[4].get("status") == "open"),
              "Client"),
        _item("CHK-15", "Delivered to the client", st(delivered), "DevOps"),
    ]

    # Features: API designed -> stories planned -> built -> every acceptance criterion tested and passing.
    try:
        from architecture_model import parse_openapi
    except ImportError:
        from engine.architecture_model import parse_openapi
    openapi_text = open(os.path.join(docs, "openapi.yaml"), encoding="utf-8").read() if _exists(docs, "openapi.yaml") else ""
    endpoints = parse_openapi(openapi_text)
    prd_md = open(os.path.join(docs, "prd.md"), encoding="utf-8").read() if _exists(docs, "prd.md") else ""
    features_out = []
    for f in parse_prd_features(prd_md):
        fid = f["id"]
        f_stories = [s for s in stories if fid in ((s.get("refs") or {}).get("features") or [])]
        # An endpoint belongs to a feature when the API document tags it, or a story for the feature lists it.
        story_apis = {a for s in f_stories for a in ((s.get("refs") or {}).get("api") or [])}
        f_eps = [e for e in endpoints if fid in e["features"] or (e["api_id"] and e["api_id"] in story_apis)]
        f_build = [build_stories.get(s["id"], {}) for s in f_stories]
        owners = []
        for s in f_stories:
            a = agents.get(s.get("owner") or "")
            entry = {"id": s.get("owner"), "name": (a or {}).get("name"), "role": s.get("role")}
            if s.get("owner") and entry not in owners:
                owners.append(entry)
        built = bool(f_stories) and all(b.get("status") in STORY_BUILT for b in f_build)
        building = any(b.get("status") in ("building", "fixing", "qa") for b in f_build)

        acs_out = []
        for ac in f["acs"]:
            cov = [b.get("ac_coverage") for b in f_build if b.get("ac_coverage")]
            if not cov:
                ac_status = TODO
            elif any(ac["id"] in c.get("failing_acs", []) for c in cov):
                ac_status = ATTENTION
            elif any(ac["id"] in c.get("covered", []) and c.get("passed") for c in cov):
                ac_status = DONE
            elif any(ac["id"] in c.get("uncovered", []) for c in cov):
                ac_status = ATTENTION
            else:
                ac_status = ACTIVE
            tester = next((b.get("qa_agent") for b in f_build if b.get("qa_agent")), None)
            acs_out.append({"id": ac["id"], "text": ac["text"][:240], "status": ac_status,
                            "detail": {DONE: "test written and passing", ATTENTION: "test missing or failing",
                                       ACTIVE: "QA is testing", TODO: "not tested yet"}[ac_status],
                            "tester": tester})
        tests_done = bool(acs_out) and all(a["status"] == DONE for a in acs_out)
        items = [
            _item(f"{fid}-api", "API designed", st(bool(f_eps)), "Solution Architect",
                  ", ".join(f"{e['method']} {e['path']}" for e in f_eps[:4]) or "no endpoint yet"),
            _item(f"{fid}-plan", "Stories planned and assigned", st(bool(f_stories) and all(s.get("owner") for s in f_stories),
                  attention=bool(f_stories) and not all(s.get("owner") for s in f_stories)), "Scrum Master",
                  ", ".join(s["id"] for s in f_stories) or "not in the backlog yet"),
            _item(f"{fid}-build", "Built, reviewed and merged", st(built, building), "Engineers",
                  ", ".join(f"{s['id']} {build_stories.get(s['id'], {}).get('status', 'todo')}" for s in f_stories)),
            _item(f"{fid}-test", "Every acceptance criterion tested and passing", st(tests_done,
                  any(a["status"] == ACTIVE for a in acs_out), any(a["status"] == ATTENTION for a in acs_out)), "QA",
                  f"{sum(a['status'] == DONE for a in acs_out)}/{len(acs_out)} criteria passing"),
        ]
        done_n = sum(i["status"] == DONE for i in items)
        features_out.append({"id": fid, "name": f["name"], "priority": f["priority"], "owners": owners,
                             "status": DONE if done_n == len(items) else ACTIVE if done_n or building else TODO,
                             "items": items, "acceptance_tests": acs_out})

    # Per agent: what the Scrum Master gave them and how much is finished.
    per_agent: Dict[str, Dict[str, Any]] = {}
    for s in stories:
        owner = s.get("owner")
        if not owner:
            continue
        a = agents.get(owner, {})
        rec = per_agent.setdefault(owner, {"id": owner, "name": a.get("name"), "role": s.get("role") or a.get("role"),
                                           "stories": [], "done": 0})
        status = build_stories.get(s["id"], {}).get("status", "todo")
        rec["stories"].append({"id": s["id"], "title": s.get("title", ""), "status": status,
                               "features": (s.get("refs") or {}).get("features") or []})
        rec["done"] += status in STORY_DONE

    every = stages + [i for f in features_out for i in f["items"]] + [a for f in features_out for a in f["acceptance_tests"]]
    done = sum(1 for i in every if i["status"] == DONE)
    return {"session_id": session_id,
            "progress": {"done": done, "total": len(every), "percent": round(100 * done / len(every)) if every else 0,
                         "needs_attention": sum(1 for i in every if i["status"] == ATTENTION)},
            "stages": stages, "features": features_out, "agents": sorted(per_agent.values(), key=lambda a: a["id"])}
