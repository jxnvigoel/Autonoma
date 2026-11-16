"""
Scrum Master Engine: Backlog Generation, Critical Path, Sizing, Scheduling,
Implementation Plan, Gantt Chart, and Daily Reporting
Per Handbook Chapter 9 (Scrum Master, 9.1-9.2.6), 2.7.6 (Stage 5 Planning, steps 18-19),
22.4 (Model router: low tier), 24.1 (Data model: tasks, llm_calls), and 26.3 (Token minimisation).
"""

import os
import re
import json
import sqlite3
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Set

try:
    from llm_client import query_llm_with_meta
    from validators import (
        validate_backlog_schema,
        validate_backlog_points,
        validate_backlog_must_have_ac_coverage,
        validate_backlog_dependency_cycles,
        validate_backlog_walking_skeleton,
        validate_backlog_owners_in_roster,
        validate_backlog_refs_exist,
    )
except ImportError:
    from engine.llm_client import query_llm_with_meta
    from engine.validators import (
        validate_backlog_schema,
        validate_backlog_points,
        validate_backlog_must_have_ac_coverage,
        validate_backlog_dependency_cycles,
        validate_backlog_walking_skeleton,
        validate_backlog_owners_in_roster,
        validate_backlog_refs_exist,
    )

logger = logging.getLogger("autonoma-engine.scrum")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(PROJECT_ROOT, "data", "office.db")
DATA_PROJECTS_DIR = os.path.join(PROJECT_ROOT, "data", "projects")
DAILY_REPORT_TEMPLATE = os.path.join(PROJECT_ROOT, "templates", "daily-report.md")


def init_tasks_db(db_path: Optional[str] = None) -> None:
    """
    Initializes the tasks table in SQLite per Handbook Chapter 24.1:
    CREATE TABLE tasks (
      id TEXT NOT NULL,
      project_id TEXT NOT NULL,
      kind TEXT NOT NULL,
      title TEXT NOT NULL,
      phase TEXT NOT NULL,
      role TEXT NOT NULL,
      owner TEXT,
      builder TEXT,
      stage TEXT,
      depends_on TEXT NOT NULL DEFAULT '[]',
      refs TEXT NOT NULL DEFAULT '[]',
      points INTEGER DEFAULT 1,
      branch TEXT,
      rounds INTEGER NOT NULL DEFAULT 0,
      status TEXT NOT NULL DEFAULT 'todo',
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      done_at TEXT,
      PRIMARY KEY (project_id, id)
    );
    """
    db_path = db_path or DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            kind TEXT NOT NULL DEFAULT 'story',
            title TEXT NOT NULL,
            phase TEXT NOT NULL DEFAULT 'Stage 5 Planning',
            role TEXT NOT NULL,
            owner TEXT,
            builder TEXT,
            stage TEXT DEFAULT 'todo',
            depends_on TEXT NOT NULL DEFAULT '[]',
            refs TEXT NOT NULL DEFAULT '{}',
            points INTEGER DEFAULT 1,
            branch TEXT,
            rounds INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'todo',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            done_at TEXT,
            PRIMARY KEY (project_id, id)
        );
        """
    )
    conn.commit()
    conn.close()


# ==============================================================================
# DETERMINISTIC CODE LAYER (Handbook 9.1.3, 9.1.4, 26.3)
# Scheduling, dates, critical path, Gantt chart, and plan rendering done by code.
# ==============================================================================

def calculate_critical_path(stories: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculates the critical path (longest chain of dependent stories by points)
    and earliest start / finish dates in agent-days.
    Handbook 9.1.4:
    The critical path (longest chain of dependent stories) sets the earliest finish date.
    Work off the critical path is scheduled around it.
    """
    if not stories:
        return {
            "critical_path_story_ids": [],
            "total_critical_points": 0,
            "estimated_days": 0,
            "story_schedules": {}
        }

    story_map = {s["id"]: s for s in stories}
    story_ids = [s["id"] for s in stories]

    # In-degree and adjacency
    in_degree = {sid: 0 for sid in story_ids}
    adj = {sid: set() for sid in story_ids}

    for s in stories:
        sid = s["id"]
        for dep in s.get("depends_on", []):
            if dep in story_map:
                adj[dep].add(sid)
                in_degree[sid] += 1

    # Topological order via Kahn's algorithm
    queue = [sid for sid, deg in in_degree.items() if deg == 0]
    topo_order = []

    while queue:
        node = queue.pop(0)
        topo_order.append(node)
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # Longest path dynamic programming (Earliest Start / Earliest Finish)
    earliest_start: Dict[str, int] = {sid: 0 for sid in story_ids}
    earliest_finish: Dict[str, int] = {}
    predecessor: Dict[str, Optional[str]] = {sid: None for sid in story_ids}

    for sid in topo_order:
        pts = story_map[sid].get("points", 1)
        deps = story_map[sid].get("depends_on", [])
        if deps:
            max_dep_finish = 0
            best_pred = None
            for dep in deps:
                if dep in earliest_finish:
                    dep_f = earliest_finish[dep]
                    if dep_f > max_dep_finish:
                        max_dep_finish = dep_f
                        best_pred = dep
            earliest_start[sid] = max_dep_finish
            predecessor[sid] = best_pred
        else:
            earliest_start[sid] = 0

        earliest_finish[sid] = earliest_start[sid] + pts

    # Find the story that finished latest
    if not earliest_finish:
        return {
            "critical_path_story_ids": [],
            "total_critical_points": 0,
            "estimated_days": 0,
            "story_schedules": {}
        }

    max_finish_sid = max(earliest_finish, key=earliest_finish.get)
    max_duration = earliest_finish[max_finish_sid]

    # Trace back critical path
    critical_path = []
    curr = max_finish_sid
    while curr:
        critical_path.append(curr)
        curr = predecessor[curr]
    critical_path.reverse()

    critical_points = sum(story_map[sid].get("points", 1) for sid in critical_path)

    story_schedules = {}
    for sid in story_ids:
        story_schedules[sid] = {
            "start_day": earliest_start.get(sid, 0) + 1,
            "finish_day": earliest_finish.get(sid, 1),
            "duration_days": story_map[sid].get("points", 1),
            "is_critical": (sid in critical_path)
        }

    return {
        "critical_path_story_ids": critical_path,
        "total_critical_points": critical_points,
        "estimated_days": max_duration,
        "story_schedules": story_schedules
    }


def calculate_load_balance(stories: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Computes story count and total points assigned per owner and per role.
    Handbook 9.2.4 rule 5:
    Assign owners from the roster by role. Balance load; the orchestrator will check it.
    """
    by_owner: Dict[str, Dict[str, Any]] = {}
    by_role: Dict[str, Dict[str, Any]] = {}

    for s in stories:
        owner = s.get("owner", "unassigned")
        role = s.get("role", "general")
        pts = s.get("points", 1)

        if owner not in by_owner:
            by_owner[owner] = {"owner": owner, "role": role, "points": 0, "story_count": 0, "stories": []}
        by_owner[owner]["points"] += pts
        by_owner[owner]["story_count"] += 1
        by_owner[owner]["stories"].append(s.get("id"))

        if role not in by_role:
            by_role[role] = {"role": role, "points": 0, "story_count": 0}
        by_role[role]["points"] += pts
        by_role[role]["story_count"] += 1

    return {
        "by_owner": by_owner,
        "by_role": by_role,
        "total_points": sum(s.get("points", 1) for s in stories),
        "total_stories": len(stories)
    }


def generate_gantt_chart_data(
    stories: List[Dict[str, Any]],
    critical_path_info: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Renders Gantt chart data and a GitHub-compatible Mermaid Gantt diagram.
    Handbook 8.1.4 & 9.1.5:
    The Gantt chart and implementation plan are rendered by code from backlog.json.
    """
    schedules = critical_path_info.get("story_schedules", {})
    tasks_gantt = []

    mermaid_lines = [
        "```mermaid",
        "gantt",
        "    title Project Implementation Plan & Critical Path",
        "    dateFormat  X",
        "    axisFormat Day %d",
        "    section Walking Skeleton"
    ]

    in_skeleton_section = True
    for s in stories:
        sid = s["id"]
        sched = schedules.get(sid, {"start_day": 1, "finish_day": 1, "is_critical": False})
        title_safe = s.get("title", sid).replace(":", " - ").replace('"', "'")
        is_crit = sched.get("is_critical", False)
        crit_tag = "crit, " if is_crit else ""

        start_day = sched.get("start_day", 1)
        finish_day = sched.get("finish_day", 1)

        if sid != "ST-001" and in_skeleton_section:
            mermaid_lines.append("    section Core Features")
            in_skeleton_section = False

        mermaid_lines.append(
            f"    {sid} - {title_safe} :{crit_tag}{sid}, {start_day}, {finish_day}"
        )

        tasks_gantt.append({
            "id": sid,
            "title": s.get("title"),
            "owner": s.get("owner"),
            "role": s.get("role"),
            "start_day": start_day,
            "finish_day": finish_day,
            "points": s.get("points", 1),
            "is_critical": is_crit,
            "depends_on": s.get("depends_on", [])
        })

    mermaid_lines.append("```")
    mermaid_diagram = "\n".join(mermaid_lines)

    return {
        "tasks": tasks_gantt,
        "mermaid_diagram": mermaid_diagram,
        "total_days": critical_path_info.get("estimated_days", 1)
    }


def render_implementation_plan(
    session_id: str,
    backlog: Dict[str, Any],
    critical_path_info: Dict[str, Any],
    load_info: Dict[str, Any],
    gantt_data: Dict[str, Any]
) -> str:
    """
    Renders docs/implementation-plan.md deterministically by code.
    Handbook 2.7.6 step 19 & 9.1.5:
    Render implementation plan.md and the Gantt chart.
    """
    stories = backlog.get("stories", [])
    crit_ids = set(critical_path_info.get("critical_path_story_ids", []))
    schedules = critical_path_info.get("story_schedules", {})

    lines = [
        f"# Implementation Plan: {session_id}",
        "",
        "> Assembled by code deterministically from `docs/backlog.json` per Handbook Chapter 9.1.4 & 26.3.",
        "",
        "## 1. Executive Summary & Milestones",
        f"- **Total Stories**: {len(stories)}",
        f"- **Total Story Points**: {load_info.get('total_points', 0)}",
        f"- **Critical Path Duration**: {critical_path_info.get('estimated_days', 0)} agent-days ({critical_path_info.get('total_critical_points', 0)} critical points)",
        f"- **WIP Limit**: 1 active story per agent; review columns capped (Handbook 9.1.4).",
        "",
        "### Milestone Progression",
        "1. **Milestone 1 (Walking Skeleton)**: `ST-001` - One thin slice through UI → API → database → deploy proving the architecture.",
        "2. **Milestone 2 (Core User Journeys)**: Foundation and primary business entities, API contracts, and core screens.",
        "3. **Milestone 3 (Edge Cases, Verification & Alpha)**: Secondary flows, performance testing on `needs_perf` stories, integration and QA passes.",
        "",
        "## 2. Story Schedule & Dependency Graph",
        "| ID | Title | Role | Owner | Points | Days | Dependencies | Critical? |",
        "|---|---|---|---|---|---|---|---|"
    ]

    for s in stories:
        sid = s["id"]
        sched = schedules.get(sid, {"start_day": 1, "finish_day": 1})
        crit_str = "**YES** (Critical Path)" if sid in crit_ids else "No"
        deps_str = ", ".join(s.get("depends_on", [])) if s.get("depends_on") else "*None*"
        lines.append(
            f"| `{sid}` | {s.get('title')} | `{s.get('role')}` | `{s.get('owner')}` | {s.get('points')} | Day {sched.get('start_day')}-{sched.get('finish_day')} | {deps_str} | {crit_str} |"
        )

    lines.extend([
        "",
        "## 3. Critical Path Chain",
        f"The longest chain of dependent stories setting earliest completion date is:",
        " -> ".join([f"`{cid}`" for cid in critical_path_info.get("critical_path_story_ids", [])]),
        "",
        "## 4. Load Balancing & Resource Allocation",
        "| Owner | Role | Assigned Stories | Total Points | Story IDs |",
        "|---|---|---|---|---|"
    ])

    for owner_id, oinfo in load_info.get("by_owner", {}).items():
        sids = ", ".join([f"`{x}`" for x in oinfo.get("stories", [])])
        lines.append(
            f"| `{owner_id}` | `{oinfo.get('role')}` | {oinfo.get('story_count')} | {oinfo.get('points')} | {sids} |"
        )

    lines.extend([
        "",
        "## 5. Gantt Chart",
        gantt_data.get("mermaid_diagram", "")
    ])

    return "\n".join(lines)


def sync_stories_to_tasks(
    session_id: str,
    stories: List[Dict[str, Any]],
    db_path: Optional[str] = None
) -> None:
    """
    Syncs backlog stories into SQLite tasks table.
    Handbook Chapter 24.1:
    One row per story in tasks table.
    """
    db_path = db_path or DEFAULT_DB_PATH
    init_tasks_db(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    for s in stories:
        sid = s["id"]
        title = s.get("title", "")
        role = s.get("role", "general")
        owner = s.get("owner", "")
        points = s.get("points", 1)
        deps_json = json.dumps(s.get("depends_on", []))
        refs_json = json.dumps(s.get("refs", {}))

        cur.execute(
            """
            INSERT INTO tasks (
                id, project_id, kind, title, phase, role, owner, builder,
                stage, depends_on, refs, points, rounds, status
            )
            VALUES (?, ?, 'story', ?, 'Stage 5 Planning', ?, ?, ?, 'todo', ?, ?, ?, 0, 'todo')
            ON CONFLICT(project_id, id) DO UPDATE SET
                title = excluded.title,
                role = excluded.role,
                owner = excluded.owner,
                builder = excluded.builder,
                depends_on = excluded.depends_on,
                refs = excluded.refs,
                points = excluded.points;
            """,
            (sid, session_id, title, role, owner, owner, deps_json, refs_json, points)
        )

    conn.commit()
    conn.close()


def generate_daily_report(
    session_id: str,
    day: int = 1,
    db_path: Optional[str] = None
) -> str:
    """
    Assembles daily report (reports/day-NN.md) from task records and token ledger.
    Handbook 9.1.5, 9.2.4 rule 6, 9.2.5:
    The daily report states facts from task records, lists blockers first, and ends with what needs the client.
    Every report number matches the task records.
    """
    db_path = db_path or DEFAULT_DB_PATH
    init_tasks_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        from token_ledger import init_token_ledger_db
    except ImportError:
        from engine.token_ledger import init_token_ledger_db
    init_token_ledger_db(db_path)
    conn.commit()

    # 1. Fetch tasks
    cur.execute(
        "SELECT id, title, role, owner, stage, status, points, rounds, created_at, done_at FROM tasks WHERE project_id = ? ORDER BY id ASC",
        (session_id,)
    )
    tasks = cur.fetchall()

    # 2. Fetch token ledger spend
    token_rows = []
    try:
        cur.execute(
            """
            SELECT agent_id, SUM(input_tokens + output_tokens) as total_tokens, SUM(cost_usd) as total_cost
            FROM llm_calls
            WHERE project_id = ?
            GROUP BY agent_id
            """,
            (session_id,)
        )
        token_rows = cur.fetchall()
    except Exception:
        token_rows = []
    finally:
        conn.close()

    # Read estimate.json for budget comparison
    session_dir = os.path.join(DATA_PROJECTS_DIR, session_id)
    estimate_file = os.path.join(session_dir, "docs", "estimate.json")
    if not os.path.exists(estimate_file):
        estimate_file = os.path.join(session_dir, "estimate.json")

    role_budgets: Dict[str, int] = {}
    total_token_budget = 400000
    if os.path.exists(estimate_file):
        try:
            with open(estimate_file, "r", encoding="utf-8") as f:
                est_data = json.load(f)
                role_budgets = est_data.get("role_tokens", {})
                total_token_budget = est_data.get("total_tokens", 400000)
        except Exception:
            pass

    # Assemble metrics
    total_points = sum(r["points"] for r in tasks) if tasks else 0
    done_statuses = ("done", "done_perf_not_run")
    points_completed = sum(r["points"] for r in tasks if r["status"] in done_statuses)
    points_remaining = total_points - points_completed
    blockers = [r for r in tasks if r["status"] in ("blocked", "escalated")]
    review_rounds = sum(r["rounds"] for r in tasks)

    # Facts from the build loop's records (bugs filed with evidence, escalations with reasons)
    build_state: Dict[str, Any] = {}
    build_state_file = os.path.join(DATA_PROJECTS_DIR, session_id, "build_state.json")
    if os.path.exists(build_state_file):
        try:
            with open(build_state_file, "r", encoding="utf-8") as f:
                build_state = json.load(f)
        except Exception:
            build_state = {}
    bugs_found = len(build_state.get("bugs", []))
    story_states = build_state.get("stories", {})
    cycle_hours = []
    for r in tasks:
        if r["status"] in done_statuses and r["done_at"] and r["created_at"]:
            try:
                start = datetime.fromisoformat(str(r["created_at"]).replace(" ", "T")).replace(tzinfo=timezone.utc)
                end = datetime.fromisoformat(str(r["done_at"]))
                end = end if end.tzinfo else end.replace(tzinfo=timezone.utc)
                cycle_hours.append((end - start).total_seconds() / 3600.0)
            except ValueError:
                pass
    cycle_text = (f"{sum(cycle_hours) / len(cycle_hours):.2f} hours over {len(cycle_hours)} finished stories"
                  if cycle_hours else "not measured yet (no story finished)")
    client_needs = [e for e in build_state.get("escalations", []) if e.get("to") == "client"]

    # Token calculations
    role_tokens_used: Dict[str, int] = {}
    total_cost_usd = 0.0
    total_tokens_used = 0

    for tr in token_rows:
        aid = tr["agent_id"]
        toks = tr["total_tokens"] or 0
        cost = tr["total_cost"] or 0.0
        total_tokens_used += toks
        total_cost_usd += cost

        # Extract role from agent_id (e.g. session_backend-1 -> backend)
        role = aid.split("_")[-1].split("-")[0] if "_" in aid else aid
        role_tokens_used[role] = role_tokens_used.get(role, 0) + toks

    # Render report lines
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    report_lines = [
        f"# Daily Report: Day {day:02d}",
        f"**Project**: `{session_id}`  ",
        f"**Date**: {now_str}  ",
        f"**Sprint Status**: {'BLOCKED' if blockers else 'ACTIVE'}  ",
        "",
        "## 1. Blockers",
    ]

    if blockers:
        report_lines.extend([
            "| Story | Owner | Blocker Description | Why / Root Cause | Action Required |",
            "|---|---|---|---|---|"
        ])
        for b in blockers:
            st = story_states.get(b["id"], {})
            esc = st.get("escalation") or {}
            reason = esc.get("reason") or st.get("blocked_reason") or "status recorded without a reason"
            action = f"escalated to {esc['to']}" if esc.get("to") else "finish the stories it depends on"
            report_lines.append(f"| `{b['id']}` | `{b['owner']}` | {b['status']} | {reason} | {action} |")
    else:
        report_lines.append("*No blockers today. Zero blocked stories in task records.*")

    report_lines.extend([
        "",
        "## 2. Progress & What Moved",
        "| Story | Title | Owner | Points | Stage | Status |",
        "|---|---|---|---|---|---|"
    ])

    for t in tasks:
        report_lines.append(
            f"| `{t['id']}` | {t['title']} | `{t['owner']}` | {t['points']} | `{t['stage']}` | `{t['status']}` |"
        )

    report_lines.extend([
        "",
        "## 3. Metrics & Burndown",
        f"- **Total Points Planned**: {total_points}",
        f"- **Points Completed**: {points_completed}",
        f"- **Points Remaining**: {points_remaining}",
        f"- **Bugs Found**: {bugs_found}",
        f"- **Review Rounds**: {review_rounds}",
        f"- **Average Cycle Time**: {cycle_text}",
        "",
        "## 4. Token Spend vs Budget (from Ledger)",
        "| Role | Tokens Used | Token Budget | % Used | Status |",
        "|---|---|---|---|---|"
    ])

    for role, budget in role_budgets.items():
        used = role_tokens_used.get(role, 0)
        pct = (used / budget * 100.0) if budget > 0 else 0.0
        r_status = "WARNING" if pct >= 80.0 else "OK"
        report_lines.append(f"| `{role}` | {used:,} | {budget:,} | {pct:.1f}% | {r_status} |")

    tot_pct = (total_tokens_used / total_token_budget * 100.0) if total_token_budget > 0 else 0.0
    report_lines.extend([
        f"- **Total Tokens Used**: {total_tokens_used:,} / {total_token_budget:,} ({tot_pct:.1f}%)",
        f"- **Total Cost (USD)**: ${total_cost_usd:.4f}",
        "",
        "## 5. What Needs the Client",
    ])
    if client_needs:
        report_lines.extend(f"- `{e['story']}`: {e['reason']}" for e in client_needs)
    else:
        report_lines.append("*Nothing in the task records needs the client right now.*")

    return "\n".join(report_lines)


# ==============================================================================
# SCRUM MASTER LLM AGENT (Handbook 9.2)
# Low-tier model writes docs/backlog.json from PRD, Architecture, and Team Plan.
# ==============================================================================

SCRUM_MASTER_SYSTEM_PROMPT = """You are the Scrum Master agent in Autonoma.
Source: skills/scrum/role.md (Handbook Section 9.2).

Mission:
Break the design into small, testable stories, give each one an owner, and keep an honest record of where every story stands.
The orchestrator (code, not you) does the scheduling, the dates, the Gantt chart and the token counts. You write the stories and the reports.

Procedure:
1. First story ST-001 is the walking skeleton from the architecture: one thin slice through UI -> API -> database -> deploy proving architecture.
2. Split features into INVEST stories: independent, small (<= 5 points, one day of agent work), testable. Split by user-visible slice, not by layer, where possible.
3. Every story cites the AC-s it satisfies. Every AC- of a Must-have feature lands in some story.
4. Record dependencies. No cycles.
5. Assign owners from the roster by role. Balance load.
6. Story points strictly on a Fibonacci scale: 1, 2, 3, or 5. NEVER assign more than 5 points; split larger work into smaller user-visible slices.
7. Set needs_perf: true if the story touches high-throughput endpoints or latency-sensitive APIs.

JSON Schema output:
{
  "stories": [
    {
      "id": "ST-001",
      "title": "Walking skeleton: App initialization, DB connection, health check, deployment pipeline",
      "role": "devops",
      "owner": "devops-1",
      "points": 2,
      "refs": {
        "features": ["F-001"],
        "ac": ["AC-001"],
        "api": ["API-001"],
        "tables": ["TBL-01"]
      },
      "depends_on": [],
      "needs_perf": false,
      "definition_of_done": [
        "AC-001 has passing automated tests",
        "Tech Lead approved",
        "API matches openapi.yaml"
      ]
    }
  ]
}

Return ONLY valid JSON matching this schema. Do not enclose in backticks or markdown preamble.
"""


def _parse_json_object(raw_text: str) -> Optional[Dict[str, Any]]:
    """The first complete JSON object in a model answer: reasoning, fences and prose around it are ignored."""
    try:
        from llm_client import strip_reasoning
    except ImportError:
        from engine.llm_client import strip_reasoning
    text = strip_reasoning(raw_text or "")
    text = re.sub(r"```(?:json)?", "", text)
    decoder = json.JSONDecoder()
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = decoder.raw_decode(text[m.start():])
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


MUST_HAVE_RE = re.compile(r"\*\*(?:Priority|MoSCoW)\*\*:\s*Must[- ]?have", re.I)


def prd_features(prd_text: str) -> List[Dict[str, Any]]:
    """Feature blocks of the PRD (### Feature F-###: Title) with their priority and acceptance criteria."""
    out: List[Dict[str, Any]] = []
    for sec in re.split(r"(?=^###\s*(?:Feature\s*)?`?F-\d+)", prd_text, flags=re.M):
        m = re.match(r"###\s*(?:Feature\s*)?`?(F-\d+)`?\s*[:\-–]?\s*([^\n]*)", sec)
        if not m:
            continue
        body = re.split(r"^##\s", sec, maxsplit=1, flags=re.M)[0]  # stop at the next top-level section
        acs: List[Dict[str, str]] = []
        for am in re.finditer(r"\b(AC-\d{2,4})\b\s*\|?\s*([^\n|]*)", body):
            if am.group(1) not in {a["id"] for a in acs}:
                acs.append({"id": am.group(1), "text": am.group(2).strip()})
        out.append({"id": m.group(1), "title": m.group(2).strip().strip("`*") or m.group(1),
                    "must_have": bool(MUST_HAVE_RE.search(body)), "body": body.strip(), "acs": acs})
    return out


def feature_trace(arch_text: str, openapi_text: str) -> Dict[str, Dict[str, List[str]]]:
    """Feature -> endpoints and tables, from the architecture's traceability table, else openapi summaries."""
    trace: Dict[str, Dict[str, List[str]]] = {}
    for line in arch_text.splitlines():
        m = re.match(r"\|\s*\[?(F-\d+)\]?\s*\|([^|]*)\|([^|]*)\|", line)
        if m:
            t = trace.setdefault(m.group(1), {"api": [], "tables": []})
            t["api"] += [a for a in re.findall(r"API-\d+", m.group(2)) if a not in t["api"]]
            t["tables"] += [x for x in re.findall(r"TBL-\d+", m.group(3)) if x not in t["tables"]]
    for line in openapi_text.splitlines():
        if "summary:" in line:
            fids, apis = re.findall(r"F-\d+", line), re.findall(r"API-\d+", line)
            for fid in fids:
                t = trace.setdefault(fid, {"api": [], "tables": []})
                t["api"] += [a for a in apis if a not in t["api"]]
    return trace


def _api_lines(openapi_text: str) -> Dict[str, str]:
    """API-### -> 'METHOD /path: summary' from openapi.yaml."""
    out: Dict[str, str] = {}
    path, method = "", ""
    for line in openapi_text.splitlines():
        pm = re.match(r"^  (/\S*):\s*$", line)
        if pm:
            path = pm.group(1)
            continue
        mm = re.match(r"^    (get|post|put|patch|delete):\s*$", line)
        if mm:
            method = mm.group(1).upper()
            continue
        if "summary:" in line and path:
            for api in re.findall(r"API-\d+", line):
                out[api] = f"{method} {path}: {line.split('summary:', 1)[1].strip()}"
    return out


_ROLE_SYNONYMS = {"ui": "frontend", "fe": "frontend", "web": "frontend", "client": "frontend",
                  "be": "backend", "api": "backend", "server": "backend", "fullstack": "backend",
                  "ops": "devops", "infra": "devops", "test": "qa", "tester": "qa"}


class _Owners:
    """Hands each story to the least-loaded hired agent of its role (Handbook 9.2.4 rule 5)."""

    def __init__(self, roster: List[Dict[str, Any]]):
        self.by_role: Dict[str, List[str]] = {}
        for a in roster:
            self.by_role.setdefault((a.get("role") or "").lower(), []).append(a["id"])
        self.load: Dict[str, int] = {}

    def role(self, wanted: str, default: str = "backend") -> str:
        r = (wanted or "").lower().strip()
        r = _ROLE_SYNONYMS.get(r, r)
        if r in self.by_role:
            return r
        for fallback in (default, "backend", "fullstack", "frontend"):
            if fallback in self.by_role:
                return fallback
        return next(iter(self.by_role), default)

    def assign(self, role: str, points: int) -> str:
        ids = self.by_role.get(role) or [f"{role}-1"]
        owner = min(ids, key=lambda i: (self.load.get(i, 0), ids.index(i)))
        self.load[owner] = self.load.get(owner, 0) + points
        return owner


def _snap_points(p: Any) -> int:
    try:
        n = int(round(float(p)))
    except (TypeError, ValueError):
        return 3
    return 1 if n <= 1 else 2 if n == 2 else 3 if n <= 3 else 5


FEATURE_STORIES_SYSTEM = """You are the Scrum Master. Split ONE feature into INVEST stories: each one a small
user-visible slice an agent finishes in a day, testable through the acceptance criteria it cites.
Return ONLY a JSON object, no prose:
{"stories": [{"title": "...", "role": "backend|frontend", "points": 1|2|3|5, "ac": ["AC-001"],
  "api": ["API-001"], "tables": ["TBL-01"], "after": [0], "needs_perf": false}]}
Rules: 1 to 4 stories. Cite only the AC-, API- and TBL- ids listed for this feature. Every listed AC- lands in
at least one story. "after" lists the indexes (0-based) of earlier stories in YOUR list that must finish first.
Points are 1, 2, 3 or 5; split anything bigger. needs_perf is true only for a story with a latency target."""


def _feature_prompt(feature: Dict[str, Any], apis: List[str], tables: List[str], api_lines: Dict[str, str],
                    roles: List[str]) -> str:
    ac_lines = "\n".join(f"- {a['id']}: {a['text'][:300]}" for a in feature["acs"]) or "- (none listed)"
    api_txt = "\n".join(f"- {a}: {api_lines.get(a, '')}" for a in apis) or "- (none)"
    return (f"FEATURE {feature['id']}: {feature['title']}\n\n{feature['body'][:2500]}\n\n"
            f"ACCEPTANCE CRITERIA:\n{ac_lines}\n\nENDPOINTS:\n{api_txt}\n\nTABLES: {', '.join(tables) or '(none)'}\n"
            f"ROLES ON THE TEAM: {', '.join(roles)}\n")


def _fallback_feature_stories(feature: Dict[str, Any], apis: List[str], tables: List[str],
                              roles: List[str]) -> List[Dict[str, Any]]:
    """Stories straight from the PRD entry when the model's split is unusable: API + storage, then the screen."""
    acs = [a["id"] for a in feature["acs"]]
    out = [{"title": f"{feature['title']}: endpoint and storage", "role": "backend", "points": 3,
            "ac": acs, "api": apis, "tables": tables, "after": [], "needs_perf": False}]
    if "frontend" in roles:
        out.append({"title": f"{feature['title']}: screen and client validation", "role": "frontend", "points": 2,
                    "ac": acs, "api": apis, "tables": [], "after": [0], "needs_perf": False})
    return out


def build_backlog(session_id: str, prd_text: str, arch_text: str, openapi_text: str,
                  roster: List[Dict[str, Any]], force_provider: Optional[str] = None,
                  force_model: Optional[str] = None) -> Tuple[Dict[str, Any], List[str]]:
    """
    docs/backlog.json, one feature at a time (Handbook 9.2.4). The model splits each feature into stories with
    a small JSON answer; code numbers them, gives owners by load, records dependencies, checks every citation
    and makes sure every acceptance criterion lands in a story. ST-001 is the walking skeleton (rule 1).
    """
    features = prd_features(prd_text)
    if not features:
        raise ValueError("docs/prd.md has no '### Feature F-###' sections to split into stories.")
    trace = feature_trace(arch_text, openapi_text)
    api_lines = _api_lines(openapi_text)
    known_apis = set(re.findall(r"API-\d+", arch_text + "\n" + openapi_text))
    known_tables = set(re.findall(r"TBL-\d+", arch_text))
    owners = _Owners(roster)
    roles = sorted(owners.by_role) or ["backend"]
    notes: List[str] = []

    all_tables = sorted(known_tables)
    first_api = next(iter(trace.get(features[0]["id"], {}).get("api", [])), None)
    skel_role = owners.role("devops" if "devops" in owners.by_role else "backend")
    stories: List[Dict[str, Any]] = [{
        "id": "ST-001",
        "title": "Walking skeleton: app scaffold, database migrations, health check and one request from the UI "
                 "through the API to the database, with CI running",
        "role": skel_role, "owner": owners.assign(skel_role, 3), "points": 3,
        "refs": {"features": [], "ac": [], "api": [first_api] if first_api else [], "tables": all_tables},
        "depends_on": [], "needs_perf": False,
        "definition_of_done": ["App starts and the health check answers", "Migrations create every table in docs/schema.md",
                               "CI runs lint, type checks and tests green", "Tech Lead approved"],
    }]

    for feature in features:
        fid = feature["id"]
        apis = [a for a in trace.get(fid, {}).get("api", []) if a in known_apis or not known_apis]
        tables = [t for t in trace.get(fid, {}).get("tables", []) if t in known_tables or not known_tables]
        feature_acs = [a["id"] for a in feature["acs"]]
        drafts: Optional[List[Dict[str, Any]]] = None
        for attempt in range(2):
            try:
                raw, _meta = query_llm_with_meta(
                    prompt=_feature_prompt(feature, apis, tables, api_lines, roles)
                    + ("\nYour previous answer was not a JSON object with a 'stories' array. Return only that JSON."
                       if attempt else ""),
                    system=FEATURE_STORIES_SYSTEM, role="scrum", session_id=session_id,
                    task_id=f"scrum_backlog_{fid}", temperature=0.2, max_tokens=1500,
                    force_provider=force_provider, force_model=force_model)
            except Exception as e:  # quota, network: this feature falls back to the PRD-shaped split below
                logger.warning(f"Scrum Master call for {fid} failed: {e}")
                break
            data = _parse_json_object(raw)
            if data and isinstance(data.get("stories"), list) and data["stories"]:
                drafts = [d for d in data["stories"] if isinstance(d, dict) and str(d.get("title") or "").strip()]
                if drafts:
                    break
        if not drafts:
            drafts = _fallback_feature_stories(feature, apis, tables, roles)
            notes.append(f"{fid}: the model's split could not be read, so its stories were built from the PRD entry.")

        base = len(stories)
        made: List[Dict[str, Any]] = []
        for i, d in enumerate(drafts[:6]):
            role = owners.role(str(d.get("role") or "backend"))
            points = _snap_points(d.get("points"))
            ac = [a for a in (d.get("ac") or []) if a in feature_acs]
            api = [a for a in (d.get("api") or []) if a in apis]
            tbl = [t for t in (d.get("tables") or []) if t in tables]
            after = [int(x) for x in (d.get("after") or []) if str(x).isdigit() and int(x) < i]
            sid = f"ST-{base + i + 1:03d}"
            made.append({
                "id": sid, "title": str(d["title"]).strip()[:160], "role": role, "owner": "", "points": points,
                "refs": {"features": [fid], "ac": ac, "api": api, "tables": tbl},
                "depends_on": ["ST-001"] + [f"ST-{base + j + 1:03d}" for j in after],
                "needs_perf": bool(d.get("needs_perf")),
            })
        # Endpoints and tables are written by a backend seat (the frontend's write scope excludes them): a
        # feature with endpoints but no backend story gets one, and its screens wait for it.
        if (apis or tables) and not any(st["role"] != "frontend" for st in made):
            be_role = owners.role("backend")
            if be_role != "frontend":
                sid = f"ST-{base + len(made) + 1:03d}"
                made.insert(0, {"id": sid, "title": f"{feature['title']}: endpoint and storage", "role": be_role,
                                "owner": "", "points": 3,
                                "refs": {"features": [fid], "ac": list(feature_acs), "api": list(apis),
                                         "tables": list(tables)},
                                "depends_on": ["ST-001"], "needs_perf": False})
                for st in made[1:]:
                    st["depends_on"].append(sid)
                # Renumber so ids follow list order (validators and the plan read them in order).
                remap = {st["id"]: f"ST-{base + k + 1:03d}" for k, st in enumerate(made)}
                for st in made:
                    st["id"] = remap[st["id"]]
                    st["depends_on"] = [remap.get(d, d) for d in st["depends_on"]]
        # Every acceptance criterion of the feature lands in some story (rule 3).
        covered = {a for st in made for a in st["refs"]["ac"]}
        for ac in feature_acs:
            if ac not in covered:
                target = next((st for st in made if st["role"] != "frontend"), made[0])
                target["refs"]["ac"].append(ac)
        # A feature's endpoints are built by some story too.
        used_api = {a for st in made for a in st["refs"]["api"]}
        for api in apis:
            if api not in used_api:
                next((st for st in made if st["role"] != "frontend"), made[0])["refs"]["api"].append(api)
        for st in made:
            refs = st["refs"]
            if not refs["ac"]:  # a story with no criterion cannot be tested: it serves the feature's criteria
                refs["ac"] = list(feature_acs)
            if not refs["api"] and st["role"] in ("frontend", "backend"):
                refs["api"] = list(apis)
            if not refs["tables"] and st["role"] == "backend":
                refs["tables"] = list(tables)
            st["owner"] = owners.assign(st["role"], st["points"])
            st["definition_of_done"] = ([f"{a} has a passing automated test" for a in st["refs"]["ac"]]
                                        + ["Tech Lead approved"]
                                        + (["API matches docs/openapi.yaml"] if st["refs"]["api"] else []))
        stories.extend(made)

    return {"project": session_id, "generated_at": datetime.now(timezone.utc).isoformat(), "stories": stories}, notes


def generate_backlog_and_plan(
    session_id: str,
    force_provider: Optional[str] = None,
    force_model: Optional[str] = None,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Stage 5 Planning: Generates docs/backlog.json, runs deterministic checks,
    creates docs/implementation-plan.md, syncs tasks table, and writes initial daily report.
    Handbook 2.7.6 steps 18-19.
    """
    db_path = db_path or DEFAULT_DB_PATH
    session_dir = os.path.join(DATA_PROJECTS_DIR, session_id)
    docs_dir = os.path.join(session_dir, "docs")
    reports_dir = os.path.join(session_dir, "reports")
    os.makedirs(docs_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)

    prd_path = os.path.join(docs_dir, "prd.md")
    arch_path = os.path.join(docs_dir, "architecture.md")
    team_plan_path = os.path.join(docs_dir, "team-plan.json")

    prd_text = ""
    if os.path.exists(prd_path):
        with open(prd_path, "r", encoding="utf-8") as f:
            prd_text = f.read()

    arch_text = ""
    if os.path.exists(arch_path):
        with open(arch_path, "r", encoding="utf-8") as f:
            arch_text = f.read()

    team_plan: Dict[str, Any] = {"seats": []}
    if os.path.exists(team_plan_path):
        with open(team_plan_path, "r", encoding="utf-8") as f:
            team_plan = json.load(f)

    # Query hired agents from SQLite
    init_tasks_db(db_path)
    agents_roster = []
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT id, name, role, seat_id FROM agents WHERE project_id = ?", (session_id,))
            agents_roster = [dict(r) for r in cur.fetchall()]
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to query agents roster: {e}")

    # Fallback roster if DB empty
    if not agents_roster:
        for s in team_plan.get("seats", []):
            sid = s.get("id")
            role = s.get("role")
            count = s.get("count", 1)
            for i in range(1, count + 1):
                agents_roster.append({
                    "id": f"{session_id}_{role}-{i}",
                    "name": f"{role.capitalize()} Agent {i}",
                    "role": role,
                    "seat_id": sid
                })

    openapi_text = ""
    openapi_path = os.path.join(docs_dir, "openapi.yaml")
    if os.path.exists(openapi_path):
        with open(openapi_path, "r", encoding="utf-8") as f:
            openapi_text = f.read()

    backlog_data, notes = build_backlog(session_id, prd_text, arch_text, openapi_text, agents_roster,
                                        force_provider=force_provider, force_model=force_model)

    v_errors: List[str] = []
    for check in (validate_backlog_schema, validate_backlog_points, validate_backlog_dependency_cycles,
                  validate_backlog_walking_skeleton):
        ok, errs = check(backlog_data)
        v_errors.extend(errs)
    for check, arg in ((validate_backlog_must_have_ac_coverage, prd_text),
                       (validate_backlog_owners_in_roster, agents_roster)):
        ok, errs = check(backlog_data, arg)
        v_errors.extend(errs)
    ok, errs = validate_backlog_refs_exist(backlog_data, prd_text, arch_text + "\n" + openapi_text)
    v_errors.extend(errs)
    if v_errors:
        raise ValueError(f"Scrum Master backlog failed the code checks: {v_errors[:8]}")
    if notes:
        backlog_data["notes"] = notes

    # 1. Save docs/backlog.json
    backlog_file = os.path.join(docs_dir, "backlog.json")
    with open(backlog_file, "w", encoding="utf-8") as f:
        json.dump(backlog_data, f, indent=2)

    # 2. Deterministic Code: Critical Path & Load Balance
    stories = backlog_data.get("stories", [])
    crit_info = calculate_critical_path(stories)
    load_info = calculate_load_balance(stories)
    gantt_info = generate_gantt_chart_data(stories, crit_info)

    # 3. Deterministic Code: Render docs/implementation-plan.md
    plan_md = render_implementation_plan(session_id, backlog_data, crit_info, load_info, gantt_info)
    plan_file = os.path.join(docs_dir, "implementation-plan.md")
    with open(plan_file, "w", encoding="utf-8") as f:
        f.write(plan_md)

    # 4. Sync stories to tasks SQLite table
    sync_stories_to_tasks(session_id, stories, db_path)

    # 5. Generate initial reports/day-01.md
    daily_report_md = generate_daily_report(session_id, day=1, db_path=db_path)
    daily_report_file = os.path.join(reports_dir, "day-01.md")
    with open(daily_report_file, "w", encoding="utf-8") as f:
        f.write(daily_report_md)

    return {
        "status": "success",
        "session_id": session_id,
        "backlog": backlog_data,
        "critical_path": crit_info,
        "load_balance": load_info,
        "gantt": gantt_info,
        "implementation_plan_path": plan_file,
        "backlog_path": backlog_file,
        "daily_report_path": daily_report_file
    }
