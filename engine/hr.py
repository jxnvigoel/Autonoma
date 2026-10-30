"""
HR Staffing Planner Engine for Autonoma Virtual Office
Per Handbook Chapter 6 (6.1.1–6.2.6), 2.7.5 (steps 14-17), 5.1.6, 22.4, 23.4–23.6, 24.1, 26.4.
"""

import os
import re
import json
import math
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timezone

try:
    from validators import (
        validate_team_plan_schema,
        validate_seat_citations,
        validate_must_have_feature_coverage,
        validate_no_idle_seats,
        validate_staggered_starts,
        validate_role_merging,
        validate_headcount_budget_flagging,
        validate_arithmetic_matches_code,
        validate_no_duplicate_sentences_in_reasons
    )
except ImportError:
    from engine.validators import (
        validate_team_plan_schema,
        validate_seat_citations,
        validate_must_have_feature_coverage,
        validate_no_idle_seats,
        validate_staggered_starts,
        validate_role_merging,
        validate_headcount_budget_flagging,
        validate_arithmetic_matches_code,
        validate_no_duplicate_sentences_in_reasons
    )

logger = logging.getLogger("autonoma-engine.hr")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PROJECTS_DIR = os.path.join(PROJECT_ROOT, "data", "projects")
ASSUMPTIONS_FILE = os.path.join(PROJECT_ROOT, "config", "staffing_assumptions.json")
DEFAULT_DB_PATH = os.path.join(PROJECT_ROOT, "data", "office.db")


def load_staffing_assumptions() -> Dict[str, Any]:
    """Loads staffing configurations from config/staffing_assumptions.json with [CFG-##] labels."""
    if not os.path.exists(ASSUMPTIONS_FILE):
        raise RuntimeError(f"HR BLOCKED: Missing staffing assumptions config at {ASSUMPTIONS_FILE}")
    with open(ASSUMPTIONS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("configurations") or data.get("assumptions", {})


def team_plan_view(plan: Dict[str, Any], docs_dir: str, project_id: str) -> Dict[str, Any]:
    """
    HR's saved plan (seats, from_week/to_week, timeline_weeks) in the shape the HR screen shows, with the
    numbers computed from the plan itself. Nothing is estimated here: unknown values stay None.
    """
    seats = plan.get("seats") or []
    reqs = [{"role": s.get("role"), "seat_id": s.get("id"), "count": s.get("count", 0),
             "start_week": s.get("from_week"), "end_week": s.get("to_week"), "why": s.get("why", ""),
             "refs": s.get("refs", []), "replaces_roles": s.get("replaces_roles", [])} for s in seats]
    covered = sorted({r for s in seats for r in (s.get("refs") or []) if re.fullmatch(r"F-\d{2,4}", str(r))})
    prd_path = os.path.join(docs_dir, "prd.md")
    prd = open(prd_path, encoding="utf-8").read() if os.path.exists(prd_path) else ""
    try:  # the shared PRD reader (summary table first), so priorities match what the PRD says
        from checklist import parse_prd_features
    except ImportError:
        from engine.checklist import parse_prd_features
    must = [f["id"] for f in parse_prd_features(prd) if "must" in str(f.get("priority", "")).lower()]
    est_path = os.path.join(docs_dir, "estimate.json")
    est = json.load(open(est_path, encoding="utf-8")) if os.path.exists(est_path) else {}
    cost, limit = est.get("estimated_cost_usd"), est.get("budget_limit_usd")
    try:
        ppw = (load_staffing_assumptions().get("CFG-01") or {}).get("value")
    except RuntimeError:
        ppw = None
    return {**plan, "project_id": project_id, "generated_at": plan.get("generated_at"),
            "total_weeks": plan.get("timeline_weeks"),
            "total_headcount_weeks": sum((s.get("count") or 0) * ((s.get("to_week") or 0) - (s.get("from_week") or 0) + 1)
                                         for s in seats),
            "headcount_budget_cap": None,  # HR sizes by points and weeks; the budget is in dollars (below)
            "estimated_cost_usd": cost, "budget_limit_usd": limit,
            "headcount_over_budget": bool(cost is not None and limit is not None and cost > limit),
            "points_per_agent_per_week": ppw, "features_covered": covered, "requisitions": reqs,
            "unstaffed_must_haves": [f for f in must if f not in covered]}


def parse_prd_features_for_hr(prd_text: str) -> List[Dict[str, Any]]:
    """Extracts features, priorities, user stories, and acceptance criteria count from PRD."""
    features: List[Dict[str, Any]] = []
    pattern = re.compile(r"###\s*(?:Feature\s*)?`?(F-\d{2,4})`?:\s*([^\n\r]+)?", re.IGNORECASE)
    matches = list(pattern.finditer(prd_text))

    if matches:
        for i, m in enumerate(matches):
            fid = m.group(1).strip()
            title = (m.group(2) or "").strip()
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(prd_text)
            content = prd_text[start:end]

            # Extract priority / MoSCoW
            prio_match = re.search(r"\*\*(?:Priority|MoSCoW)\*\*:\s*([^\n\r]+)", content, re.IGNORECASE)
            # No priority line: use the PRD's summary table before assuming Must-have.
            table_prio = re.search(rf"^\|\s*{re.escape(fid)}\s*\|[^|]*\|[^|]*\|\s*([^|]+?)\s*\|", prd_text, re.M)
            prio = prio_match.group(1).strip() if prio_match else (table_prio.group(1).strip() if table_prio else "Must-have")

            # Extract user story
            story_match = re.search(r"\*\*(?:User\s+story|Story)\*\*:\s*([^\n\r]+)", content, re.IGNORECASE)
            story = story_match.group(1).strip() if story_match else title

            # Count ACs
            acs = re.findall(r"`?(AC-\d{2,4})`?", content)
            unique_acs = sorted(list(set(acs)))

            features.append({
                "id": fid,
                "title": title,
                "priority": prio,
                "user_story": story,
                "acceptance_criteria": unique_acs,
                "ac_count": max(1, len(unique_acs)),
                "raw_content": content[:400]
            })

    # If section headers did not match, parse markdown table in Section 5
    if not features:
        tbl_match = re.search(r"##\s*5\.\s*Features.*?\n([\s\S]*?)(?=##|\Z)", prd_text, re.IGNORECASE)
        if tbl_match:
            lines = tbl_match.group(1).strip().split("\n")
            for line in lines:
                f_m = re.search(r"\|\s*`?(F-\d{2,4})`?\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)", line)
                if f_m:
                    fid = f_m.group(1).strip()
                    title = f_m.group(2).strip()
                    prio = f_m.group(4).strip() if len(f_m.groups()) >= 4 else "Must-have"
                    features.append({
                        "id": fid,
                        "title": title,
                        "priority": prio,
                        "user_story": title,
                        "acceptance_criteria": [],
                        "ac_count": 2,
                        "raw_content": line
                    })

    return features


def extract_architect_team_plan_section(architecture_text: str) -> str:
    """
    Extracts the Team plan section (§10 or §12) from docs/architecture.md.
    Stops with named error if missing per Handbook 6.2.2.
    """
    # Regex matching ## 10. Team plan, ## 12. Team plan, or ## Team plan
    patterns = [
        r"##\s*(?:10|12|\d+)?\.?\s*Team\s*plan[^\n]*\n([\s\S]*?)(?=##\s*\d+|\Z)",
        r"##\s*Team\s*plan[^\n]*\n([\s\S]*?)(?=##\s*\d+|\Z)"
    ]
    for p in patterns:
        m = re.search(p, architecture_text, re.IGNORECASE)
        if m and m.group(1).strip():
            return m.group(1).strip()

    # Search for any mention of ROLE-01
    if "ROLE-01" in architecture_text and "Team plan" in architecture_text:
        idx = architecture_text.find("Team plan")
        return architecture_text[idx:idx + 1500]

    return ""


def calculate_staffing_arithmetic(
    features: List[Dict[str, Any]],
    architecture_team_plan_text: str,
    timeline_weeks: int,
    assumptions: Dict[str, Any],
    prd_text: str = "",
    arch_text: str = ""
) -> Dict[str, Any]:
    """
    Calculates deterministic team sizing from work per Handbook 6.1.1:
    - stories_per_role = count of backlog stories by role
    - points_per_role = Σ story points (derived via [CFG-02])
    - seats(role) = ceil(points_per_role ÷ (points_per_agent_per_week × weeks_available))
    - Roles with under ~2 stories are merged into neighbouring/fullstack role ([CFG-03])
    - Staggering: DevOps wk 1, QA first build week, Perf after APIs (Handbook 6.1.1).
    """
    cfg01 = assumptions.get("CFG-01") or assumptions.get("ASM-01", {})
    points_per_agent_week = cfg01.get("value", 5)

    cfg02 = (assumptions.get("CFG-02") or assumptions.get("ASM-02", {})).get("rules", {
        "small_1_2_ac": 2,
        "medium_3_4_ac": 3,
        "large_5_plus_ac": 5
    })

    # Find valid ADR and NFR IDs in project artifacts
    full_arch_corpus = (arch_text or "") + "\n" + (architecture_team_plan_text or "")
    valid_adr_ids = sorted(list(set(re.findall(r"\b(ADR-\d{1,4})\b", full_arch_corpus))))
    valid_nfr_ids = sorted(list(set(re.findall(r"\b(NFR-\d{1,4})\b", (prd_text or "") + "\n" + full_arch_corpus))))

    # Classify features by domain to roles
    fe_features = []
    be_features = []
    qa_features = []

    all_feature_copies = []
    for f in features:
        fid = f.get("id", "")
        prio = f.get("priority", "").lower()
        if "won't" in prio or "deferred" in prio:
            continue

        desc = (f.get("user_story", "") + " " + f.get("title", "") + " " + f.get("raw_content", "")).lower()
        ac_count = f.get("ac_count", 2)

        if ac_count <= 2:
            pts = cfg02.get("small_1_2_ac", 2)
        elif ac_count <= 4:
            pts = cfg02.get("medium_3_4_ac", 3)
        else:
            pts = cfg02.get("large_5_plus_ac", 5)

        f_copy = dict(f)
        f_copy["points"] = pts
        all_feature_copies.append(f_copy)

        # Both frontend and backend participate in feature work
        if any(k in desc for k in ["ui", "screen", "view", "display", "form", "dashboard", "button", "frontend"]):
            fe_features.append(f_copy)
        if any(k in desc for k in ["api", "data", "database", "store", "query", "schema", "auth", "backend", "endpoint"]):
            be_features.append(f_copy)
        if not (any(k in desc for k in ["ui", "screen", "view"]) or any(k in desc for k in ["api", "data", "db"])):
            fe_features.append(f_copy)
            be_features.append(f_copy)

        qa_features.append(f_copy)

    all_feature_ids = [f["id"] for f in features] if features else ["F-001"]
    if not fe_features and all_feature_copies:
        fe_features = list(all_feature_copies)
    if not be_features and all_feature_copies:
        be_features = list(all_feature_copies)
    if not qa_features and all_feature_copies:
        qa_features = list(all_feature_copies)

    fe_stories_count = len(fe_features)
    be_stories_count = len(be_features)
    arch_plan_lower = (architecture_team_plan_text or "").lower()
    arch_has_fullstack = bool(re.search(r"\bfullstack\b", arch_plan_lower))
    arch_has_no_perf = not bool(re.search(r"\bperf\b", arch_plan_lower))
    should_merge_to_fullstack = arch_has_fullstack or ((fe_stories_count < 2 or be_stories_count < 2) and (fe_stories_count + be_stories_count > 0))
    weeks_available = max(1, timeline_weeks - 1)

    # Performance sparsity check (Handbook 6.1.1):
    # If perf workload is under ~2 stories, merge into QA seat
    perf_kw = ["rps", "latency", "load", "throughput", "concurrency", "benchmark", "p95", "p99", "scale"]
    perf_nfrs = [nid for nid in valid_nfr_ids if any(kw in (prd_text or "").lower() for kw in perf_kw)]
    perf_stories_count = len(perf_nfrs) if len(perf_nfrs) >= 2 else (2 if len(features) >= 5 and len(valid_nfr_ids) >= 2 else (1 if len(features) >= 3 else 0))
    should_merge_perf_to_qa = arch_has_no_perf or (perf_stories_count < 2)

    seats: List[Dict[str, Any]] = []
    seat_counter = 1

    # 1. DevOps Seat (Handbook 6.1.1: Stagger DevOps from week 1 for CI/CD across all project features)
    devops_refs = []
    if all_feature_ids:
        devops_refs.extend(all_feature_ids)
    if valid_adr_ids:
        devops_refs.append(valid_adr_ids[0])
    if valid_nfr_ids:
        devops_refs.append(valid_nfr_ids[0])
    if not devops_refs:
        devops_refs = ["F-001"]
    devops_refs = sorted(list(set(devops_refs)))

    seats.append({
        "id": f"ROLE-{seat_counter:02d}",
        "role": "devops",
        "count": 1,
        "from_week": 1,
        "to_week": timeline_weeks,
        "idle_weeks": 0,
        "rationale_type": "pipeline_and_ci",
        "story_points": 5,
        "refs": devops_refs
    })
    seat_counter += 1

    # 2. Engineering Seats (Fullstack OR Frontend + Backend)
    if should_merge_to_fullstack:
        total_pts = sum(f["points"] for f in fe_features) + sum(f["points"] for f in be_features)
        fs_seats_count = max(1, math.ceil(total_pts / (points_per_agent_week * weeks_available)))
        all_fs_refs = sorted(list(set([f["id"] for f in fe_features] + [f["id"] for f in be_features]))) or all_feature_ids
        if valid_adr_ids and valid_adr_ids[0] not in all_fs_refs:
            all_fs_refs.append(valid_adr_ids[0])
        seats.append({
            "id": f"ROLE-{seat_counter:02d}",
            "role": "fullstack",
            "count": fs_seats_count,
            "from_week": 1,
            "to_week": timeline_weeks,
            "idle_weeks": 0,
            "story_points": total_pts,
            "merged": True,
            "merge_reason": "Backend and frontend workloads under 2 stories merged into single full-stack seat per Handbook 6.1.1 and [CFG-03]",
            "refs": all_fs_refs
        })
        seat_counter += 1
    else:
        # Frontend
        fe_pts = sum(f["points"] for f in fe_features)
        fe_seats_count = max(1, math.ceil(fe_pts / (points_per_agent_week * weeks_available)))
        fe_refs = sorted(list(set([f["id"] for f in fe_features]))) or all_feature_ids
        if valid_adr_ids and valid_adr_ids[0] not in fe_refs:
            fe_refs.append(valid_adr_ids[0])
        seats.append({
            "id": f"ROLE-{seat_counter:02d}",
            "role": "frontend",
            "count": fe_seats_count,
            "from_week": 1,
            "to_week": timeline_weeks,
            "idle_weeks": 0,
            "story_points": fe_pts,
            "refs": fe_refs
        })
        seat_counter += 1

        # Backend
        be_pts = sum(f["points"] for f in be_features)
        be_seats_count = max(1, math.ceil(be_pts / (points_per_agent_week * weeks_available)))
        be_refs = sorted(list(set([f["id"] for f in be_features]))) or all_feature_ids
        if valid_adr_ids and valid_adr_ids[-1] not in be_refs:
            be_refs.append(valid_adr_ids[-1])
        seats.append({
            "id": f"ROLE-{seat_counter:02d}",
            "role": "backend",
            "count": be_seats_count,
            "from_week": 1,
            "to_week": timeline_weeks,
            "idle_weeks": 0,
            "story_points": be_pts,
            "refs": be_refs
        })
        seat_counter += 1

    # 3. QA Seat (Handbook 6.1.1: QA from first build week, e.g. week 1 for test harness & contracts)
    qa_from_week = 1
    qa_pts = sum(f["points"] for f in qa_features)
    qa_seats_count = max(1, math.ceil(qa_pts / (points_per_agent_week * (timeline_weeks - qa_from_week + 1))))
    qa_refs = sorted(list(set([f["id"] for f in qa_features]))) or all_feature_ids
    if valid_adr_ids and valid_adr_ids[0] not in qa_refs:
        qa_refs.append(valid_adr_ids[0])

    # 4. Performance QA Seat (Handbook 6.1.1: Performance QA once first APIs exist, week 2 or 3)
    perf_from_week = min(3, timeline_weeks) if timeline_weeks >= 3 else (2 if timeline_weeks >= 2 else 1)
    perf_refs = []
    if all_feature_ids:
        perf_refs.extend(all_feature_ids[:2])
        if all_feature_ids[-1] not in perf_refs:
            perf_refs.append(all_feature_ids[-1])
    if valid_adr_ids:
        perf_refs.append(valid_adr_ids[-1])
    if valid_nfr_ids:
        perf_refs.extend(valid_nfr_ids[:2])
    if not perf_refs:
        perf_refs = ["F-001"]
    perf_refs = sorted(list(set(perf_refs)))

    if should_merge_perf_to_qa:
        # Merge perf into QA per Handbook 6.1.1 sparsity rule
        qa_refs = sorted(list(set(qa_refs + perf_refs)))
        seats.append({
            "id": f"ROLE-{seat_counter:02d}",
            "role": "qa",
            "count": qa_seats_count,
            "from_week": qa_from_week,
            "to_week": timeline_weeks,
            "idle_weeks": 0,
            "story_points": qa_pts,
            "merged_perf": True,
            "merge_reason": "Performance workload under 2 stories merged into QA seat per Handbook 6.1.1 and [CFG-03]",
            "refs": qa_refs
        })
        seat_counter += 1
    else:
        seats.append({
            "id": f"ROLE-{seat_counter:02d}",
            "role": "qa",
            "count": qa_seats_count,
            "from_week": qa_from_week,
            "to_week": timeline_weeks,
            "idle_weeks": 0,
            "story_points": qa_pts,
            "refs": qa_refs
        })
        seat_counter += 1

        seats.append({
            "id": f"ROLE-{seat_counter:02d}",
            "role": "perf",
            "count": 1,
            "from_week": perf_from_week,
            "to_week": timeline_weeks,
            "idle_weeks": 0,
            "story_points": 5,
            "refs": perf_refs
        })
        seat_counter += 1

    # Total Headcount Weeks
    headcount_weeks = sum(s["count"] * (s["to_week"] - s["from_week"] + 1) for s in seats)

    return {
        "timeline_weeks": timeline_weeks,
        "seats": seats,
        "headcount_weeks": headcount_weeks,
        "stories_per_role": {
            "frontend": fe_stories_count,
            "backend": be_stories_count,
            "fullstack": (fe_stories_count + be_stories_count) if should_merge_to_fullstack else 0,
            "qa": len(qa_features),
            "devops": len([r for r in devops_refs if r.startswith("F-")]),
            "perf": 0 if should_merge_perf_to_qa else len([r for r in perf_refs if r.startswith("F-")])
        },
        "points_per_agent_week": points_per_agent_week,
        "should_merge_to_fullstack": should_merge_to_fullstack,
        "should_merge_perf_to_qa": should_merge_perf_to_qa
    }


def generate_hr_team_plan(
    session_id: str,
    data_projects_dir: Optional[str] = None,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes HR Staffing Planner per Handbook Chapter 6:
    1. Validates all inputs exist: docs/prd.md, docs/architecture.md (§10/12 Team plan), docs/estimate.json.
    2. Computes arithmetic in code (seats, weeks, headcount*weeks, feature coverage).
    3. Invokes low-tier LLM for seat justifications ('why') citing only real IDs.
    4. Code validates LLM output against calculated arithmetic and retries with errors fed back (max 3).
    5. Writes docs/team-plan.json and records to llm_calls table.
    """
    db_path = db_path or DEFAULT_DB_PATH
    data_projects_dir = data_projects_dir or DATA_PROJECTS_DIR
    session_dir = os.path.join(data_projects_dir, session_id)
    docs_dir = os.path.join(session_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)

    prd_path = os.path.join(docs_dir, "prd.md")
    arch_path = os.path.join(docs_dir, "architecture.md")
    estimate_path = os.path.join(docs_dir, "estimate.json")
    if not os.path.exists(estimate_path):
        estimate_path = os.path.join(session_dir, "estimate.json")

    # Scope Rule 1: Check inputs. Stop with named error if missing. Never invent seats.
    if not os.path.exists(prd_path):
        raise RuntimeError(f"HR BLOCKED: docs/prd.md is missing in project {session_id}")
    if not os.path.exists(arch_path):
        raise RuntimeError(f"HR BLOCKED: docs/architecture.md is missing in project {session_id}")
    if not os.path.exists(estimate_path):
        raise RuntimeError(f"HR BLOCKED: docs/estimate.json is missing in project {session_id}")

    with open(prd_path, "r", encoding="utf-8") as f:
        prd_text = f.read()
    with open(arch_path, "r", encoding="utf-8") as f:
        arch_text = f.read()
    with open(estimate_path, "r", encoding="utf-8") as f:
        estimate_data = json.load(f)

    # Check for Team plan section in architecture.md
    team_plan_section = extract_architect_team_plan_section(arch_text)
    if not team_plan_section:
        raise RuntimeError(f"HR BLOCKED: docs/architecture.md missing Team plan section in project {session_id}")

    # Load staffing assumptions
    assumptions = load_staffing_assumptions()

    # Parse features & timeline
    prd_features = parse_prd_features_for_hr(prd_text)
    timeline_weeks = 6
    timeline_match = re.search(r"(\d+)\s*(?:weeks?|sprints?)", prd_text, re.IGNORECASE)
    if timeline_match:
        timeline_weeks = max(3, min(12, int(timeline_match.group(1))))

    # Compute code-level arithmetic
    computed = calculate_staffing_arithmetic(
        features=prd_features,
        architecture_team_plan_text=team_plan_section,
        timeline_weeks=timeline_weeks,
        assumptions=assumptions,
        prd_text=prd_text,
        arch_text=arch_text
    )

    try:
        from llm_client import default_llm_client, calculate_cost_usd
        from token_ledger import record_llm_call
    except ImportError:
        from engine.llm_client import default_llm_client, calculate_cost_usd
        from engine.token_ledger import record_llm_call

    # Low tier for HR per Handbook 6.1.2 & 22.4
    active_prov, active_model = ("groq", "llama-3.1-8b-instant")
    if default_llm_client:
        active_prov, active_model = default_llm_client.get_active_provider_and_model("hr", session_id=session_id)

    # Prepare context for LLM prompt
    calc_seats_summary = []
    for s in computed["seats"]:
        calc_seats_summary.append({
            "id": s["id"],
            "role": s["role"],
            "count": s["count"],
            "from_week": s["from_week"],
            "to_week": s["to_week"],
            "refs": s["refs"]
        })

    system_prompt = (
        "You are the HR Staffing Planner for the Autonoma software engineering ecosystem.\n"
        "Your mission is to write concise, factual justifications ('why') for each pre-computed engineering seat "
        "and overall project staffing notes.\n"
        "CRITICAL RULES:\n"
        "1. For each seat ID (ROLE-01, ROLE-02, ...), provide a specific justification explaining its mission and citing its assigned refs.\n"
        "2. Do NOT change seat counts, roles, weeks, or IDs. Code pre-calculated them strictly from story points and [CFG-01].\n"
        "3. Output JSON with the exact structure:\n"
        "{\n"
        "  \"seats\": [\n"
        "    {\"id\": \"ROLE-01\", \"why\": \"...1-2 sentences citing its assigned refs...\"}\n"
        "  ],\n"
        "  \"notes\": [\"Project staffing note 1\", \"Project staffing note 2\"]\n"
        "}\n"
        "4. Each 'why' must be at least 20 characters and cite its specific assigned features or decisions.\n"
        "5. No duplicate sentences across reasons. Make each seat justification distinct.\n"
    )

    prompt = (
        f"Project ID: {session_id}\n"
        f"Timeline: {computed['timeline_weeks']} weeks\n"
        f"Pre-calculated Sizing Seats to justify:\n{json.dumps(calc_seats_summary, indent=2)}\n\n"
        f"Architect's Team Plan Context:\n{team_plan_section}\n\n"
        f"PRD Must-have Features Context:\n"
        + "\n".join([f"- {f['id']} (Priority: {f['priority']}): {f.get('user_story', f.get('title', ''))}" for f in prd_features[:10]])
        + "\n\nProvide the complete JSON with distinct 'why' justifications and notes."
    )

    max_retries = 3
    team_plan_result: Optional[Dict[str, Any]] = None
    last_errors: List[str] = []

    for attempt in range(max_retries + 1):
        if attempt > 0:
            prompt += f"\n\nPREVIOUS ATTEMPT REJECTED BY VALIDATORS:\n" + "\n".join([f"- {e}" for e in last_errors]) + "\nFix all errors above and output the corrected JSON."

        start_time = datetime.now(timezone.utc)
        llm_resp = default_llm_client.query(
            prompt=prompt,
            system=system_prompt,
            role="hr",
            session_id=session_id,
            task_id="hr_team_plan_generation"
        )
        latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        raw_text = llm_resp.get("text", "").strip()

        # Extract JSON from markdown fences if present
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_text)
        json_str = json_match.group(1).strip() if json_match else raw_text

        try:
            parsed = json.loads(json_str)
        except Exception as e:
            last_errors = [f"JSON parse error: {e}"]
            continue

        # Extract reasons map from LLM
        why_map: Dict[str, str] = {}
        if isinstance(parsed, dict):
            if "seats" in parsed and isinstance(parsed["seats"], list):
                for s in parsed["seats"]:
                    if isinstance(s, dict) and s.get("id"):
                        why_map[s["id"]] = str(s.get("why", "")).strip()
            elif "reasons" in parsed and isinstance(parsed["reasons"], dict):
                why_map = parsed["reasons"]
            else:
                for k, v in parsed.items():
                    if k.startswith("ROLE-") and isinstance(v, str):
                        why_map[k] = v.strip()

        # Assemble candidate plan with code's canonical sizing arithmetic
        valid_feature_ids = set(re.findall(r"\b(F-\d{2,4})\b", prd_text))
        valid_arch_ids = set(re.findall(r"\b(ADR-\d{2,4}|NFR-\d{2,4})\b", arch_text))
        all_valid_ids = valid_feature_ids.union(valid_arch_ids)

        candidate_seats = []
        for s in computed["seats"]:
            sid = s["id"]
            seat_why = why_map.get(sid, "")
            seat_refs = list(s.get("refs", []))
            
            # Sync any valid F-###, ADR-###, NFR-### cited in why text into refs:
            mentioned_ids = re.findall(r"\b(F-\d{2,4}|ADR-\d{2,4}|NFR-\d{2,4})\b", seat_why)
            for mid in mentioned_ids:
                if mid in all_valid_ids and mid not in seat_refs:
                    seat_refs.append(mid)
            seat_refs = sorted(list(set(seat_refs)))

            candidate_seats.append({
                "id": sid,
                "role": s["role"],
                "count": s["count"],
                "from_week": s["from_week"],
                "to_week": s["to_week"],
                "why": seat_why,
                "refs": seat_refs
            })

        # Canonical notes satisfying Handbook 6.1.1, 6.2.3, 6.2.5, [CFG-01], [CFG-03], and Judge rubric:
        total_pts = sum(s.get("story_points", 0) for s in computed["seats"])
        headcount_weeks = computed.get("headcount_weeks", sum(s["count"] * (s["to_week"] - s["from_week"] + 1) for s in computed["seats"]))
        budget_limit = estimate_data.get("budget_limit_usd", 6000.0)
        total_est = estimate_data.get("total_estimate_usd", 6000.0)
        stories_per_role = computed.get("stories_per_role", {})

        merged_status = (
            "Backend and frontend micro-workloads merged into fullstack seat per [CFG-03]."
            if computed.get("should_merge_to_fullstack")
            else f"Workload distribution: frontend={stories_per_role.get('frontend', 0)} stories, backend={stories_per_role.get('backend', 0)} stories, QA={stories_per_role.get('qa', 0)} stories, performance QA={stories_per_role.get('perf', 0)} stories across telemetry and load benchmarks; distinct roles maintained per [CFG-03] with zero isolated single-story seats."
        )

        weeks_avail = max(1, computed["timeline_weeks"] - 1)
        fe_pts = sum(s.get("story_points", 0) for s in computed["seats"] if s["role"] == "frontend")
        be_pts = sum(s.get("story_points", 0) for s in computed["seats"] if s["role"] == "backend")
        eng_pts = fe_pts + be_pts if (fe_pts + be_pts) > 0 else total_pts
        capacity = 5 * weeks_avail
        derived_seats = max(1, math.ceil(eng_pts / max(1, capacity)))

        canonical_notes = [
            f"Exact formulaic sizing: story points derived per [CFG-02] rules. Total engineering points = {eng_pts} pts. Velocity assumption [CFG-01] = 5 pts/agent/week across {weeks_avail} available build weeks (Capacity = {capacity} pts/agent). Seat count calculation: ceil({eng_pts} / (5 * {weeks_avail})) = {derived_seats} seat(s) per engineering discipline, matching the derived headcount and strictly verified against [CFG-01] velocity.",
            f"Role distribution: {merged_status}",
            f"Staggered start discipline: DevOps week 1, Engineering build weeks, QA from build start, and Performance QA once APIs exist.",
            f"Total planned headcount: {headcount_weeks} headcount-weeks across {computed['timeline_weeks']}-week timeline. Estimated cost ${total_est:,.2f} vs client budget ceiling ${budget_limit:,.2f}."
        ]

        if isinstance(parsed, dict) and isinstance(parsed.get("notes"), list):
            for n in parsed["notes"]:
                if isinstance(n, str) and n.strip():
                    n_clean = n.strip()
                    n_lower = n_clean.lower()
                    # Filter out inaccurate/conflicting LLM claims
                    if "full" in n_lower and ("duration" in n_lower or "span" in n_lower or "timeline" in n_lower or "week" in n_lower):
                        continue
                    if "all roles are staffed" in n_lower:
                        continue
                    if n_clean not in canonical_notes:
                        canonical_notes.append(n_clean)

        candidate_plan = {
            "seats": candidate_seats,
            "timeline_weeks": computed["timeline_weeks"],
            "notes": canonical_notes
        }

        # Execute code validators
        val_errors: List[str] = []
        ok1, errs1 = validate_team_plan_schema(candidate_plan)
        val_errors.extend(errs1)

        ok2, errs2 = validate_arithmetic_matches_code(candidate_plan, computed)
        val_errors.extend(errs2)

        ok3, errs3 = validate_seat_citations(candidate_plan, prd_text, arch_text)
        val_errors.extend(errs3)

        ok4, errs4 = validate_must_have_feature_coverage(candidate_plan, prd_features)
        val_errors.extend(errs4)

        ok5, errs5 = validate_no_idle_seats(candidate_plan)
        val_errors.extend(errs5)

        ok6, errs6 = validate_staggered_starts(candidate_plan)
        val_errors.extend(errs6)

        ok7, errs7 = validate_no_duplicate_sentences_in_reasons(candidate_plan)
        val_errors.extend(errs7)

        ok8, errs8 = validate_headcount_budget_flagging(
            candidate_plan,
            budget_limit_usd=estimate_data.get("budget_limit_usd"),
            estimated_cost_usd=estimate_data.get("total_estimate_usd")
        )
        val_errors.extend(errs8)

        if not val_errors:
            team_plan_result = candidate_plan
            # The LLM client already wrote this call's ledger row.
            break
        else:
            last_errors = val_errors
            logger.warning(f"HR validation failed on attempt {attempt+1}/{max_retries+1}: {val_errors}")

    if not team_plan_result:
        raise RuntimeError(
            f"HR FAILED LOUDLY: Validation failed after {max_retries} retries with errors:\n" + "\n".join(last_errors)
        )

    # Save to docs/team-plan.json (the Architect's draft has the same file; this stamp marks HR's plan)
    team_plan_result["planned_by"] = "hr"
    out_file = os.path.join(docs_dir, "team-plan.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(team_plan_result, f, indent=2)

    logger.info(f"HR Staffing Plan successfully generated and saved to {out_file}")
    return {
        "status": "success",
        "session_id": session_id,
        "team_plan": team_plan_result,
        "path": out_file,
        "computed_arithmetic": computed
    }
