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


def _parse_backlog_json(raw_text: str) -> Optional[Dict[str, Any]]:
    """Robustly parses backlog JSON from LLM output."""
    clean = raw_text.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?\s*", "", clean)
        clean = re.sub(r"\s*```$", "", clean)
    clean = clean.strip()

    try:
        data = json.loads(clean)
        if isinstance(data, dict) and "stories" in data:
            return data
    except Exception:
        pass

    # Regex search for {"stories": [...]}
    match = re.search(r"(\{[\s\S]*\"stories\"[\s\S]*\})", raw_text)
    if match:
        try:
            data = json.loads(match.group(1))
            if isinstance(data, dict) and "stories" in data:
                return data
        except Exception:
            pass

    return None


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

    # Prepare Prompt for Scrum Master
    roster_summary = "\n".join([f"- Agent `{a['id']}` (Role: `{a['role']}`, Seat: `{a.get('seat_id')}`)" for a in agents_roster])
    seats_summary = json.dumps(team_plan.get("seats", []), indent=2)

    prompt = f"""Generate the comprehensive project backlog for project '{session_id}'.

INPUT ARTIFACTS:
1. PRD (Features, MoSCoW priorities, Acceptance Criteria AC-###):
{prd_text[:6000]}

2. Architecture (Build order, Walking skeleton, APIs, Tables):
{arch_text[:5000]}

3. Team Plan Seats:
{seats_summary}

4. Hired Agent Roster:
{roster_summary}

INSTRUCTIONS:
1. Story ST-001 MUST be the walking skeleton proving the architecture (no dependencies).
2. Every Must-have AC-### from PRD MUST be covered by at least one story.
3. Size each story with Fibonacci points <= 5 (1, 2, 3, or 5).
4. Assign owners from the Hired Agent Roster matching the role.
5. Record clean DAG dependencies without cycles.
6. Set needs_perf: true on performance-critical stories.
7. Return ONLY valid JSON matching the schema.
"""

    max_retries = 3
    last_errors = []
    backlog_data = None

    for attempt in range(1, max_retries + 1):
        attempt_prompt = prompt
        if last_errors:
            err_text = "\n".join([f"- {e}" for e in last_errors])
            attempt_prompt += f"\n\nPREVIOUS ATTEMPT REJECTED BY CODE VALIDATORS:\n{err_text}\nFix ALL validation errors in your new output!"

        logger.info(f"Running Scrum Master LLM generation for {session_id} (Attempt {attempt}/{max_retries})...")

        raw_resp, meta = query_llm_with_meta(
            prompt=attempt_prompt,
            system=SCRUM_MASTER_SYSTEM_PROMPT,
            role="scrum",
            session_id=session_id,
            task_id="scrum_backlog_generation",
            temperature=0.2,
            max_tokens=4000,
            force_provider=force_provider,
            force_model=force_model
        )

        parsed = _parse_backlog_json(raw_resp)
        if not parsed:
            last_errors = ["Scrum Master output could not be parsed as valid JSON with a 'stories' array."]
            continue

        # Run full validation suite
        v_errors = []
        ok, errs = validate_backlog_schema(parsed)
        if not ok:
            v_errors.extend(errs)

        ok, errs = validate_backlog_points(parsed)
        if not ok:
            v_errors.extend(errs)

        ok, errs = validate_backlog_must_have_ac_coverage(parsed, prd_text)
        if not ok:
            v_errors.extend(errs)

        ok, errs = validate_backlog_dependency_cycles(parsed)
        if not ok:
            v_errors.extend(errs)

        ok, errs = validate_backlog_walking_skeleton(parsed)
        if not ok:
            v_errors.extend(errs)

        ok, errs = validate_backlog_owners_in_roster(parsed, agents_roster)
        if not ok:
            v_errors.extend(errs)

        ok, errs = validate_backlog_refs_exist(parsed, prd_text, arch_text)
        if not ok:
            v_errors.extend(errs)

        if not v_errors:
            backlog_data = parsed
            logger.info(f"Scrum Master backlog validation PASSED on attempt {attempt}.")
            break
        else:
            last_errors = v_errors
            logger.warning(f"Scrum Master backlog validation failed on attempt {attempt}: {v_errors}")

    if not backlog_data:
        raise ValueError(
            f"Scrum Master failed to produce a valid backlog after {max_retries} attempts. Errors: {last_errors}"
        )

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
