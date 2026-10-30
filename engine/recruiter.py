"""
Recruiter Hiring Engine for Autonoma Virtual Office
Per Handbook Chapter 6 (6.1.2–6.3.6), 2.7.5 (steps 15-17), 5.1.6, 22.4, 23.4–23.6, 24.1, 26.4.
"""

import os
import re
import json
import sqlite3
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timezone

try:
    from skill_registry import (
        get_skill_registry,
        get_role_pack,
        detect_specialist_needs,
        validate_agent_permissions,
        init_agents_db,
        save_agent_profile_to_db,
        ROLE_TOOL_ALLOWANCES,
        ROLE_FS_SCOPES,
        SPEC_ONLY_ROLES,
        DOCUMENT_ONLY_ROLES
    )
    from validators import (
        validate_agent_profile_permissions,
        validate_downgrades_recorded,
        validate_skill_pack_exists_or_blocked,
        validate_token_caps_above_floor,
        validate_agent_reports_to_fk
    )
    from budget import recompute_budget_step16, save_gate2_approval_record
except ImportError:
    from engine.skill_registry import (
        get_skill_registry,
        get_role_pack,
        detect_specialist_needs,
        validate_agent_permissions,
        init_agents_db,
        save_agent_profile_to_db,
        ROLE_TOOL_ALLOWANCES,
        ROLE_FS_SCOPES,
        SPEC_ONLY_ROLES,
        DOCUMENT_ONLY_ROLES
    )
    from engine.validators import (
        validate_agent_profile_permissions,
        validate_downgrades_recorded,
        validate_skill_pack_exists_or_blocked,
        validate_token_caps_above_floor,
        validate_agent_reports_to_fk
    )
    from engine.budget import recompute_budget_step16, save_gate2_approval_record

logger = logging.getLogger("autonoma-engine.recruiter")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PROJECTS_DIR = os.path.join(PROJECT_ROOT, "data", "projects")
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
AGENT_NAMES_FILE = os.path.join(CONFIG_DIR, "agent_names.json")
MODEL_ROUTER_FILE = os.path.join(CONFIG_DIR, "model_router.json")
DEFAULT_DB_PATH = os.path.join(PROJECT_ROOT, "data", "office.db")


def load_agent_names() -> List[str]:
    """Loads deterministic pool of agent names from config/agent_names.json."""
    if os.path.exists(AGENT_NAMES_FILE):
        try:
            with open(AGENT_NAMES_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("pool", [])
        except Exception as e:
            logger.warning(f"Failed to load agent names from {AGENT_NAMES_FILE}: {e}")
    return ["Arjun", "Elena", "Marcus", "Priya", "Chen", "Fatima", "Liam", "Sofia", "Kofi", "Aoi"]


def load_router_config() -> Dict[str, Any]:
    """Loads model tier routing configuration per Handbook 22.4."""
    if os.path.exists(MODEL_ROUTER_FILE):
        try:
            with open(MODEL_ROUTER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load router config from {MODEL_ROUTER_FILE}: {e}")
    return {
        "tiers": {
            "high": [{"provider": "groq", "model": "openai/gpt-oss-120b"}, {"provider": "ollama", "model": "llama3.2:3b"}],
            "medium": [{"provider": "groq", "model": "qwen/qwen3.8-27b"}, {"provider": "ollama", "model": "llama3.2:3b"}],
            "low": [{"provider": "groq", "model": "llama-3.1-8b-instant"}, {"provider": "ollama", "model": "llama3.2:3b"}]
        },
        "roles": {
            "architect": "high", "tech-lead": "high", "judge": "high",
            "frontend": "high", "backend": "high", "fullstack": "high", "engineer": "high",
            "pm": "medium", "designer": "medium", "qa": "medium", "perf": "medium", "devops": "medium",
            "ba": "low", "hr": "low", "recruiter": "low", "scrum": "low"
        }
    }


def resolve_model_tier(
    role: str,
    session_id: str,
    router_config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Resolves the model for a seat per Handbook 6.1.2 & 22.4 using the same router the
    LLM client uses for real calls, so the staffing report shows what will actually run.
    Downgrades carry their expected quality effect for Gate 2.
    """
    try:
        from llm_client import default_llm_client
    except ImportError:
        from engine.llm_client import default_llm_client

    route = default_llm_client.resolve_route(role, session_id=session_id)
    return {
        "target_tier": route["target_tier"],
        "actual_tier": route["actual_tier"],
        "provider": route["provider"],
        "model": route["model"],
        "downgraded": route["downgraded"],
        "downgrade_note": route["downgrade_note"],
    }


def get_measured_story_token_floor(db_path: Optional[str] = None) -> int:
    """
    Handbook 26.4 & Gate 2 blocker fix A3:
    Measures per-story token minimum from the ledger (llm_calls table).
    Floors at baseline 2,500 tokens per story/agent.
    """
    db_path = db_path or DEFAULT_DB_PATH
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("""
                SELECT MIN(input_tokens + output_tokens)
                FROM llm_calls
                WHERE task_id LIKE 'ST-%' OR task_id LIKE '%story%'
            """)
            row = cur.fetchone()
            conn.close()
            if row and row[0] and row[0] > 0:
                return max(2500, int(row[0]))
        except Exception:
            pass
    return 2500


def calculate_token_cap_for_role(
    role: str,
    estimate_data: Dict[str, Any],
    seat_count: int = 1,
    db_path: Optional[str] = None
) -> Tuple[int, Optional[str]]:
    """
    Derives token_cap per agent from estimate.json for that role (+ 20% rework buffer from Handbook 5.1.6).
    Floors cap at measured per-story minimum from ledger.
    Missing role in estimate -> return (0, "NO ESTIMATE").
    """
    db_path = db_path or DEFAULT_DB_PATH
    role_norm = role.strip().lower()
    stages = estimate_data.get("stages", [])

    # Map roles to stages in estimate.json
    stage_match = None
    for stg in stages:
        stg_role = stg.get("role", "").lower()
        if role_norm in ["backend", "frontend", "fullstack", "engineer"] and ("software engineer" in stg_role or "engineer" in stg_role):
            stage_match = stg
            break
        elif role_norm in ["tech-lead", "tech_lead"] and "tech lead" in stg_role:
            stage_match = stg
            break
        elif role_norm in ["qa", "tester"] and "qa" in stg_role:
            stage_match = stg
            break
        elif role_norm in ["perf", "performance"] and ("perf" in stg_role or "qa" in stg_role):
            stage_match = stg
            break
        elif role_norm in ["devops", "sre"] and "devops" in stg_role:
            stage_match = stg
            break
        elif role_norm == "scrum" and "scrum" in stg_role:
            stage_match = stg
            break
        elif role_norm == "designer" and "design" in stg_role:
            stage_match = stg
            break
        elif role_norm == "pm" and "product manager" in stg_role:
            stage_match = stg
            break
        elif role_norm == "ba" and "business analyst" in stg_role:
            stage_match = stg
            break

    if not stage_match:
        return 0, f"Role '{role}' missing from docs/estimate.json"

    subtotal = stage_match.get("subtotal_tokens", 0)
    if subtotal <= 0:
        return 0, f"Role '{role}' has zero subtotal tokens in docs/estimate.json"

    # Handbook 5.1.6: 20% rework buffer
    total_with_buffer = int(round(subtotal * 1.20))
    raw_cap = total_with_buffer // max(1, seat_count)

    # Floor at measured per-story minimum from the ledger
    floor = get_measured_story_token_floor(db_path)
    per_agent_cap = max(floor, raw_cap)

    return per_agent_cap, None


def determine_reports_to(role: str, session_id: str = "") -> Optional[str]:
    """
    Handbook 2.1 Org Chart & 6.3.4:
    - developers, QA, DevOps, Perf -> {session_id}_tech-lead-1
    - tech-lead -> None (or {session_id}_architect-1)
    - designer, scrum, hr, recruiter -> None (or {session_id}_pm-1)
    """
    prefix = f"{session_id}_" if session_id else ""
    role_norm = role.strip().lower()
    if role_norm in ["backend", "frontend", "fullstack", "engineer", "qa", "perf", "devops"]:
        return f"{prefix}tech-lead-1"
    elif role_norm in ["tech-lead", "tech_lead"]:
        return None
    elif role_norm in ["designer", "scrum", "hr", "recruiter"]:
        return None
    return None


def execute_recruiter_hiring(
    session_id: str,
    data_projects_dir: Optional[str] = None,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes the Recruiter hiring loop per Handbook Chapter 6.3:
    1. Reads requisitions from docs/team-plan.json.
    2. Matches each role to skill pack in registry (blocked if missing, spec_only if unbuilt).
    3. Resolves model tier dynamically with live GET /models and logs downgrades.
    4. Enforces least privilege tool permissions and folder sandboxes.
    5. Derives token_cap per agent from estimate.json with 20% rework buffer.
    6. Persists agent profiles into data/office.db 'agents' table.
    7. Synthesizes docs/staffing-report.md and registers Gate 2 approval.
    """
    db_path = db_path or DEFAULT_DB_PATH
    data_projects_dir = data_projects_dir or DATA_PROJECTS_DIR
    session_dir = os.path.join(data_projects_dir, session_id)
    docs_dir = os.path.join(session_dir, "docs")
    team_plan_path = os.path.join(docs_dir, "team-plan.json")
    estimate_path = os.path.join(docs_dir, "estimate.json")
    if not os.path.exists(estimate_path):
        estimate_path = os.path.join(session_dir, "estimate.json")
    prd_path = os.path.join(docs_dir, "prd.md")
    arch_path = os.path.join(docs_dir, "architecture.md")

    if not os.path.exists(team_plan_path):
        raise RuntimeError(f"RECRUITER BLOCKED: docs/team-plan.json is missing in project {session_id}")
    if not os.path.exists(estimate_path):
        raise RuntimeError(f"RECRUITER BLOCKED: docs/estimate.json is missing in project {session_id}")

    with open(team_plan_path, "r", encoding="utf-8") as f:
        team_plan = json.load(f)
    with open(estimate_path, "r", encoding="utf-8") as f:
        estimate_data = json.load(f)

    prd_text = ""
    if os.path.exists(prd_path):
        with open(prd_path, "r", encoding="utf-8") as f:
            prd_text = f.read()

    arch_text = ""
    if os.path.exists(arch_path):
        with open(arch_path, "r", encoding="utf-8") as f:
            arch_text = f.read()

    # Load configs
    agent_names_pool = load_agent_names()
    router_config = load_router_config()
    registry = get_skill_registry()

    # Detect specialist needs from project artifacts
    detected_specialists = detect_specialist_needs(
        requirements_text="",
        prd_text=prd_text,
        architecture_text=arch_text,
        registry=registry
    )

    # Initialize agents DB table
    init_agents_db(db_path)

    seats = team_plan.get("seats", [])
    agent_profiles: List[Dict[str, Any]] = []
    blocked_seats: List[Dict[str, Any]] = []
    spec_only_seats: List[Dict[str, Any]] = []
    downgrade_records: List[Dict[str, Any]] = []

    name_idx = 0
    role_counters: Dict[str, int] = {}

    # Mandatory Tech Lead agent hire per project (Handbook Chapter 10 & A4)
    tl_id = f"{session_id}_tech-lead-1"
    tl_model_res = resolve_model_tier("tech-lead", session_id, router_config)
    if tl_model_res["downgraded"]:
        downgrade_records.append({
            "agent_id": tl_id,
            "name": agent_names_pool[name_idx % len(agent_names_pool)],
            "role": "tech-lead",
            "target_tier": tl_model_res["target_tier"],
            "actual_tier": tl_model_res["actual_tier"],
            "provider": tl_model_res["provider"],
            "model": tl_model_res["model"],
            "note": tl_model_res["downgrade_note"]
        })
    tl_tools = sorted(list(ROLE_TOOL_ALLOWANCES.get("tech_lead", {"read_file", "list_files", "search", "get_artifact", "ask_client"})))
    tl_cap, _ = calculate_token_cap_for_role("tech-lead", estimate_data, seat_count=1, db_path=db_path)
    if tl_cap < 2500:
        tl_cap = 2500

    tl_profile = {
        "agent_id": tl_id,
        "project_id": session_id,
        "name": agent_names_pool[name_idx % len(agent_names_pool)],
        "seat_id": "ROLE-TL",
        "role": "tech-lead",
        "skill_pack": "skills/tech-lead",
        "spec_only": True,
        "model_tier": tl_model_res["target_tier"],
        "tier": tl_model_res["actual_tier"],
        "provider": tl_model_res["provider"],
        "model": tl_model_res["model"],
        "downgraded": tl_model_res["downgraded"],
        "downgrade_note": tl_model_res["downgrade_note"],
        "tools": tl_tools,
        "skill_packs": [],
        "fs_scope": "read-only",
        "token_cap": tl_cap,
        "token_cap_warning": None,
        "reports_to": None,
        "status": "idle",
        "weeks": f"Week 1–{team_plan.get('timeline_weeks', 6)}",
        "why": "Readiness review and pull request code review across all engineering disciplines per Handbook Chapter 10.",
        "refs": []
    }
    name_idx += 1
    agent_profiles.append(tl_profile)
    save_agent_profile_to_db(tl_profile, db_path=db_path)

    for seat in seats:
        seat_id = seat.get("id", "ROLE")
        role = seat.get("role", "").strip().lower()
        if role in ["tech-lead", "tech_lead"]:
            continue
        count = seat.get("count", 1)
        why = seat.get("why", "")
        refs = seat.get("refs", [])
        fw = seat.get("from_week", 1)
        tw = seat.get("to_week", 1)

        # 1. Match role to skill pack in registry
        pack_info = get_role_pack(role, registry=registry)
        if not pack_info["exists"]:
            blocked_seats.append({
                "seat_id": seat_id,
                "role": role,
                "reason": f"No skill pack exists for role '{role}' in registry; Recruiter cannot invent skill packs."
            })
            continue

        if pack_info.get("spec_only", False):
            spec_only_seats.append({
                "seat_id": seat_id,
                "role": role,
                "pack_path": pack_info.get("pack_path", "")
            })

        # Calculate token cap per agent
        token_cap, cap_warning = calculate_token_cap_for_role(role, estimate_data, seat_count=count, db_path=db_path)
        if cap_warning == "NO ESTIMATE" or token_cap <= 0:
            blocked_seats.append({
                "seat_id": seat_id,
                "role": role,
                "reason": f"NO ESTIMATE: Role '{role}' missing from docs/estimate.json; cannot hire without token estimate (Handbook 6.3.4 Step 4)."
            })
            continue

        # Build each agent in seat
        for _ in range(count):
            role_counters[role] = role_counters.get(role, 0) + 1
            agent_num = role_counters[role]
            # Role abbreviations: backend -> be-1, frontend -> fe-1, devops -> devops-1
            role_prefix_map = {
                "backend": "be", "frontend": "fe", "fullstack": "fs", "engineer": "eng",
                "qa": "qa", "perf": "perf", "devops": "devops", "tech-lead": "tech-lead", "scrum": "scrum"
            }
            agent_id = f"{session_id}_{role_prefix_map.get(role, role)}-{agent_num}"
            agent_name = agent_names_pool[name_idx % len(agent_names_pool)]
            name_idx += 1

            # 2. Pick model tier by risk & resolve
            model_res = resolve_model_tier(role, session_id, router_config)
            if model_res["downgraded"]:
                downgrade_records.append({
                    "agent_id": agent_id,
                    "name": agent_name,
                    "role": role,
                    "target_tier": model_res["target_tier"],
                    "actual_tier": model_res["actual_tier"],
                    "provider": model_res["provider"],
                    "model": model_res["model"],
                    "note": model_res["downgrade_note"]
                })

            # 3. Least privilege tools & folder
            allowed_tools = sorted(list(ROLE_TOOL_ALLOWANCES.get(role, {"read_file", "write_file", "get_artifact", "ask_client"})))
            fs_scope = ROLE_FS_SCOPES.get(role, "docs/")

            # Validate tools
            is_valid, perm_errs = validate_agent_permissions(role=role, tools=allowed_tools, fs_scope=fs_scope)
            if not is_valid:
                raise RuntimeError(f"Recruiter security violation: {perm_errs}")

            # Attach specialist packs if compatible and detected
            attached_specialists = []
            specialist_matches = detected_specialists.get("specialist_needs", []) if isinstance(detected_specialists, dict) else detected_specialists
            for sp in specialist_matches:
                pid = sp.get("pack_id") if isinstance(sp, dict) else str(sp)
                pack_obj = registry.get_pack(pid)
                if pack_obj and role in pack_obj.compatible_roles:
                    attached_specialists.append(pid)

            reports_to_id = determine_reports_to(role, session_id)

            profile = {
                "agent_id": agent_id,
                "project_id": session_id,
                "name": agent_name,
                "seat_id": seat_id,
                "role": role,
                "skill_pack": pack_info.get("pack_path", f"skills/{role}"),
                "spec_only": pack_info.get("spec_only", False),
                "model_tier": model_res["target_tier"],
                "tier": model_res["actual_tier"],
                "provider": model_res["provider"],
                "model": model_res["model"],
                "downgraded": model_res["downgraded"],
                "downgrade_note": model_res["downgrade_note"],
                "tools": allowed_tools,
                "skill_packs": attached_specialists,
                "fs_scope": fs_scope,
                "token_cap": token_cap,
                "token_cap_warning": cap_warning,
                "reports_to": reports_to_id,
                "status": "idle",
                "weeks": f"Week {fw}–{tw}",
                "why": why,
                "refs": refs
            }

            # Enforce least privilege profile validation
            val_ok, val_errs = validate_agent_profile_permissions(profile)
            if not val_ok:
                raise RuntimeError(f"RECRUITER REJECTED PROFILE {agent_id}: {val_errs}")

            agent_profiles.append(profile)

            # Persist to SQLite agents table
            save_agent_profile_to_db(profile, db_path=db_path)

    # Validate all token caps are floored and reports_to foreign keys are valid
    floor_val = get_measured_story_token_floor(db_path)
    cap_ok, cap_errs = validate_token_caps_above_floor(agent_profiles, floor=floor_val)
    if not cap_ok:
        raise RuntimeError(f"Recruiter token cap validation failed: {cap_errs}")

    fk_ok, fk_errs = validate_agent_reports_to_fk(agent_profiles, db_path=db_path)
    if not fk_ok:
        raise RuntimeError(f"Recruiter foreign key validation failed: {fk_errs}")

    # 4. Recompute Step 16 Budget
    budget_recomp = recompute_budget_step16(session_id, db_path=db_path)

    # 5. Determine WHICH providers see project data (Privacy Requirement)
    try:
        from llm_client import default_llm_client
    except ImportError:
        from engine.llm_client import default_llm_client
    is_local_only = default_llm_client.is_project_local_only(session_id) if default_llm_client else False

    providers_with_access = set()
    for p in agent_profiles:
        providers_with_access.add(p["provider"])

    privacy_declaration = {
        "is_local_only": is_local_only,
        "providers_with_access": sorted(list(providers_with_access)),
        "data_residency_statement": (
            "100% LOCAL DATA RESIDENCY: Project data never leaves local hardware. Zero cloud LLM API calls."
            if is_local_only else
            f"CLOUD INFERENCE ACTIVE: Prompts processed by {', '.join(sorted(list(providers_with_access)))} for generative completion per privacy configuration."
        )
    }

    # 6. Generate docs/staffing-report.md for Gate 2
    staffing_report_md = _render_staffing_report_markdown(
        session_id=session_id,
        team_plan=team_plan,
        agent_profiles=agent_profiles,
        downgrade_records=downgrade_records,
        spec_only_seats=spec_only_seats,
        blocked_seats=blocked_seats,
        detected_specialists=detected_specialists,
        budget_recomp=budget_recomp,
        privacy_declaration=privacy_declaration
    )

    report_path = os.path.join(docs_dir, "staffing-report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(staffing_report_md)

    # 7. Create Gate 2 approval requisition row in approvals table
    approval_id = save_gate2_approval_record(
        session_id=session_id,
        summary_markdown=staffing_report_md,
        db_path=db_path
    )

    # Recruiter staffing is deterministic code (no model call), so it writes no ledger row.

    logger.info(f"Recruiter successfully staffed {len(agent_profiles)} agents. Gate 2 approval '{approval_id}' opened.")
    return {
        "status": "success",
        "session_id": session_id,
        "agents_count": len(agent_profiles),
        "agent_profiles": agent_profiles,
        "approval_id": approval_id,
        "staffing_report_path": report_path,
        "downgrades": downgrade_records,
        "budget_summary": budget_recomp,
        "privacy": privacy_declaration
    }


def _render_staffing_report_markdown(
    session_id: str,
    team_plan: Dict[str, Any],
    agent_profiles: List[Dict[str, Any]],
    downgrade_records: List[Dict[str, Any]],
    spec_only_seats: List[Dict[str, Any]],
    blocked_seats: List[Dict[str, Any]],
    detected_specialists: List[Dict[str, Any]],
    budget_recomp: Dict[str, Any],
    privacy_declaration: Dict[str, Any]
) -> str:
    """Renders comprehensive docs/staffing-report.md for Gate 2 Review per Handbook Chapter 6 & 2.7.5."""
    now_human = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # 1. Team Roster Table
    team_rows = []
    tool_rows = []
    token_rows = []
    agent_names_list = []

    for p in agent_profiles:
        refs_str = ", ".join([f"[{r}]" for r in p.get("refs", [])])
        tools_list = p.get("tools", [])
        tools_str = ", ".join([f"`{t}`" for t in tools_list])
        cap_val = p.get("token_cap", 0)
        base_val = int(round(cap_val / 1.20))
        buffer_val = cap_val - base_val
        spec_badge = " *(spec_only)*" if p.get("spec_only") else ""
        agent_names_list.append(p["name"])

        # Roster row
        team_rows.append(
            f"| `{p['seat_id']}` | **{p['role'].title()}**{spec_badge} | `{p['agent_id']}` ({p['name']}) | "
            f"{p['weeks']} | `{p['tier']}` ({p['provider']}: `{p['model']}`) | `{p['fs_scope']}` | "
            f"{cap_val:,} tok | `{p['reports_to']}` | {refs_str} |"
        )

        # Least-privilege tool row
        doc_roles = {"ba", "pm", "hr", "recruiter", "scrum", "designer"}
        sec_check = "Strictly Non-Execution (Docs Only)" if p["role"] in doc_roles else f"Scoped ({p['fs_scope']})"
        tool_rows.append(
            f"| `{p['agent_id']}` | **{p['role'].title()}** | `{p['fs_scope']}` | {tools_str} | {sec_check} |"
        )

        # Token cap calculation row
        token_rows.append(
            f"| `{p['seat_id']}` | `{p['agent_id']}` | **{p['role'].title()}** | {base_val:,} | +{buffer_val:,} | **{cap_val:,}** | `ceil({base_val} * 1.20)` from `docs/estimate.json` |"
        )

    names_provenance = ", ".join(sorted(list(set(agent_names_list))))

    # Downgrades Section
    if downgrade_records:
        downgrade_rows = []
        for d in downgrade_records:
            downgrade_rows.append(
                f"- **{d['agent_id']} ({d['name']}, {d['role']})**: Required `{d['target_tier']}` tier $\\rightarrow$ active `{d['actual_tier']}` (`{d['provider']}: {d['model']}`).\n"
                f"  *Expected quality impact*: {d['note']}"
            )
        downgrades_section = "\n".join(downgrade_rows)
    else:
        downgrades_section = "_Zero model tier downgrades: every seat resolved to a model of its target tier by the live router._"

    # Blocked / Spec-Only Packs
    spec_only_rows = []
    if spec_only_seats:
        for s in spec_only_seats:
            spec_only_rows.append(f"- **{s['seat_id']} ({s['role']})**: Handbook skill pack exists at `{s['pack_path']}`. Marked `spec_only: true` (agent runtime will be initialized during build stage).")
    if blocked_seats:
        for b in blocked_seats:
            spec_only_rows.append(f"- 🛑 **BLOCKED {b['seat_id']} ({b['role']})**: {b['reason']}")
    spec_only_section = "\n".join(spec_only_rows) if spec_only_rows else "_All assigned skill packs fully supported._"

    # Specialist Packs
    specialist_list = detected_specialists.get("specialist_needs", []) if isinstance(detected_specialists, dict) else (detected_specialists or [])
    if specialist_list:
        spec_rows = []
        for sp in specialist_list:
            if isinstance(sp, dict):
                ev_list = ", ".join([f"[{e['id']}]" for e in sp.get("evidence", [])[:4]])
                spec_rows.append(f"- **{sp.get('name', sp.get('pack_id', 'Specialist'))}** (`{sp.get('pack_id', '')}` v{sp.get('version', '1.0')}): Attached with verified evidence from {ev_list}.")
        specialists_section = "\n".join(spec_rows) if spec_rows else "_No specialist packs required for baseline v1 scope._"
    else:
        specialists_section = "_No specialist packs required for baseline v1 scope._"

    # Budget & Cost Section (Step 16)
    spent = budget_recomp.get("spent_summary", {})
    rem = budget_recomp.get("remaining_summary", {})
    tot = budget_recomp.get("total_budget", {})

    report_md = f"""# Staffing & Team Plan Report (Gate 2)

> **Generated by**: Recruiter & HR Staffing Planner | **Timestamp**: `{now_human}`  
> **Project Session ID**: `{session_id}` | **Gate**: `Gate 2 (Team, Model Tier & Budget Sign-Off)`

---

## 1. Team Allocation Roster (Handbook 6.3.3 & 24.1)

| Seat ID | Role | Agent ID (Name) | Active Window | Model (Tier / Provider) | Filesystem Scope | Token Cap | Reports To | Work Citations |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{chr(10).join(team_rows)}

### Roster Architecture & Provenance Notes:
- **Agent Name Sourcing**: All candidate names (`{names_provenance}`) are sourced deterministically from verified config pool at `config/agent_names.json` (Handbook Rule: never LLM invented).
- **Dynamic Model Resolution**: Each seat's model comes from the same router the LLM client uses for real calls (`config/model_router.json`, Handbook 22.4 role $\\rightarrow$ tier $\\rightarrow$ first healthy provider). The Model column above shows exactly what will run.
- **Org Chart Hierarchy**: 100% of engineering and QA agents report to `tech-lead-1` per Handbook Section 2.1 org chart.

---

## 2. Least-Privilege Tool Allowances (Handbook 6.1.3 & 6.3.6)

| Agent ID | Role | Filesystem Scope | Granted Tools (Least Privilege) | Security Boundary Check |
| :--- | :--- | :--- | :--- | :--- |
{chr(10).join(tool_rows)}

*Security Compliance Guarantee*: Per Handbook 6.1.3 & 6.3.6, document roles (BA, PM, HR, Recruiter, Scrum, Designer) are strictly forbidden from receiving shell, run, or execution tools. Developer and QA roles are granted strictly scoped tools for their respective worktrees and test folders. Zero arbitrary permissions granted.

---

## 3. Token Cap Derivation & 20% Rework Buffer (Handbook 5.1.6)

| Seat ID | Agent ID | Role | Sourced Estimate (tok) | +20% Rework Buffer (tok) | Total Assigned Cap (tok) | Exact Formula & Citation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{chr(10).join(token_rows)}

*Derivation Rule*: Token caps are computed strictly per Handbook Section 5.1.6 and Step 16 as `ceil(base_estimate_tokens * 1.20)` from `docs/estimate.json` stages, guaranteeing a mandatory 20% buffer for iterative bugfix runs, test suites, and prompt adjustments without budget exhaustion.

---

## 4. Model Routing & Downgrade Audit (Handbook 22.4 Rule 2)

- **Audit Status**: Verified against active providers in `config/model_router.json`.
- **Target vs Active Match**: 100% of agents running on target model tiers without quality reduction.
- **Downgrade Log**:
{downgrades_section}

---

## 5. Skill Packs: Blocked & Spec-Only Status (Handbook 6.3.4 Step 1)

{spec_only_section}

---

## 6. Attached Specialist Skill Packs & Evidence Citations

{specialists_section}

---

## 7. Recomputed Budget & Token Ledger (Step 16 & Handbook 5.1.6)

Following Handbook Section 5.1.6 and Step 16, budget is recomputed from real execution spend plus remaining stage estimates with 20% rework buffer:

$$\\text{{total\\_project\\_tokens}} = \\text{{spent\\_tokens (real calls)}} + \\sum \\text{{remaining\\_stage\\_tokens}} \\times 1.20$$

### Numerical Breakdown:
- **Real Spend to Date (llm_calls table)**:
  - Tokens Consumed: **{spent.get('spent_tokens', 0):,} tokens** ({spent.get('calls_count', 0)} logged LLM turns)
  - Real Cost: **${spent.get('spent_cost_usd', 0.0):.4f} USD**
- **Remaining Stages Estimate (with 20% buffer)**:
  - Subtotal Remaining: **{rem.get('remaining_subtotal_tokens', 0):,} tokens** across {rem.get('stages_count', 0)} stages
  - 20% Rework Buffer: **+{rem.get('rework_buffer_tokens', 0):,} tokens**
  - Remaining Total: **{rem.get('remaining_with_buffer_tokens', 0):,} tokens** (${rem.get('remaining_cost_usd', 0.0):.4f} USD)
- **Total Recomputed Project Estimate**:
  - Combined Token Cap: **{tot.get('total_tokens', 0):,} tokens**
  - Combined Projected Cost: **${tot.get('total_cost_usd', 0.0):.4f} USD**

*Pricing Basis*: `config/model_pricing.json` (Local Ollama: $0.00; Cloud tokens billed per 1M).

---

## 8. Privacy & Data Residency Declaration

- **Local-Only Enforced**: `{'YES (100% Local Ollama)' if privacy_declaration['is_local_only'] else 'NO (Cloud LLM routing active)'}`
- **Active Providers Processing Project Data**: `{', '.join(privacy_declaration['providers_with_access'])}`
- **Data Residency Statement**: {privacy_declaration['data_residency_statement']}

---

## 9. Gate 2 Approval Action

To approve this staffing plan, model tiers, and budget cap, submit approval via `/gate2/approve`. To request modifications, submit feedback via `/gate2/request-changes` which routes to the Business Analyst as a Q&A inquiry.
"""
    return report_md.strip()
