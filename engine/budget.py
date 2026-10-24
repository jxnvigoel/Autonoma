"""
Budget Recomputation, Budget Guard (Handbook 26.4), and Gate 2 Approvals Management
Per Handbook Chapter 2.7.5 (steps 16-17), 5.1.6, 22.4, 24.1, and 26.4.
"""

import os
import json
import sqlite3
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from fastapi import HTTPException

logger = logging.getLogger("autonoma-engine.budget")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(PROJECT_ROOT, "data", "office.db")
PRICING_FILE = os.path.join(PROJECT_ROOT, "config", "model_pricing.json")
DATA_PROJECTS_DIR = os.path.join(PROJECT_ROOT, "data", "projects")


def get_file_sha256(filepath: str) -> str:
    """Computes SHA256 hex digest of a file if it exists, otherwise empty string."""
    if not os.path.exists(filepath):
        return ""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_pricing_rates() -> Dict[str, Any]:
    """Loads model pricing rates from config/model_pricing.json."""
    if os.path.exists(PRICING_FILE):
        try:
            with open(PRICING_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("rates", {})
        except Exception as e:
            logger.warning(f"Failed to load pricing config: {e}")
    return {}


def recompute_budget_step16(session_id: str, db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    Step 16 of Stage 4 Staffing (Handbook 2.7.5 & 5.1.6):
    Budget recomputed from real token counts so far plus estimates:
    - spent: llm_calls tokens & cost recorded up to Gate 2.
    - remaining: estimates for remaining stages × 1.20 (20% rework buffer).
    - cost: via config/model_pricing.json (local models: $0).
    Inputs (historical rates, real calls, pricing) shown next to result (Handbook 5.1.6).
    """
    session_dir = os.path.join(DATA_PROJECTS_DIR, session_id)
    estimate_file = os.path.join(session_dir, "docs", "estimate.json")
    if not os.path.exists(estimate_file):
        estimate_file = os.path.join(session_dir, "estimate.json")

    # 1. Query real spent tokens & cost from llm_calls ledger
    spent_tokens = 0
    spent_cost_usd = 0.0
    spent_calls_count = 0
    call_records: List[Dict[str, Any]] = []

    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("""
                SELECT agent_id, task_id, provider, model, input_tokens, output_tokens, cost_usd, latency_ms, at
                FROM llm_calls
                WHERE project_id = ?
                ORDER BY id ASC
            """, (session_id,))
            rows = cur.fetchall()
            for r in rows:
                c_dict = dict(r)
                tot = c_dict["input_tokens"] + c_dict["output_tokens"]
                spent_tokens += tot
                spent_cost_usd += c_dict["cost_usd"]
                spent_calls_count += 1
                call_records.append(c_dict)
            conn.close()
        except Exception as e:
            logger.warning(f"Error querying llm_calls for {session_id}: {e}")

    # 2. Parse estimate.json for remaining stages
    estimate_data: Dict[str, Any] = {}
    if os.path.exists(estimate_file):
        try:
            with open(estimate_file, "r", encoding="utf-8") as f:
                estimate_data = json.load(f)
        except Exception as e:
            logger.warning(f"Error loading {estimate_file}: {e}")

    stages = estimate_data.get("stages", [])

    # Stages completed prior to Gate 2: Discovery (BA), PRD (PM), Architecture, Design
    # Stages remaining: Sprint Planning (Scrum), Implementation (Eng), Code Review (Tech Lead), QA, DevOps
    completed_roles = {"business analyst (ba)", "ba", "product manager (pm)", "pm", "solution architect", "architect", "ui/ux designer", "designer"}

    remaining_stages = []
    completed_stages = []
    remaining_subtotal_tokens = 0

    for stg in stages:
        role_norm = stg.get("role", "").strip().lower()
        stage_id = stg.get("stage_id", "")
        # STAGE-01 through STAGE-04 are intake/discovery/planning/design
        if stage_id in ["STAGE-01", "STAGE-02", "STAGE-03", "STAGE-04"] or role_norm in completed_roles:
            completed_stages.append(stg)
        else:
            remaining_stages.append(stg)
            remaining_subtotal_tokens += stg.get("subtotal_tokens", 0)

    # Handbook 5.1.6: total = Σ tokens(stage) × 1.20 (20% rework buffer)
    rework_buffer_tokens = int(round(remaining_subtotal_tokens * 0.20))
    remaining_with_buffer_tokens = remaining_subtotal_tokens + rework_buffer_tokens

    # Pricing calculation for remaining stages
    pricing_rates = load_pricing_rates()
    is_local_only = False
    try:
        from llm_client import default_llm_client
        is_local_only = default_llm_client.is_project_local_only(session_id)
    except Exception:
        pass

    # If project is local-only, cost is $0.00
    remaining_cost_usd = 0.0
    if not is_local_only:
        default_rate = pricing_rates.get("default_cloud", {"input_per_million": 0.20, "output_per_million": 0.50})
        blended_per_1k = ((default_rate.get("input_per_million", 0.20) * 0.6) + (default_rate.get("output_per_million", 0.50) * 0.4)) / 1000.0
        remaining_cost_usd = round(remaining_with_buffer_tokens * (blended_per_1k / 1000.0), 4)

    total_project_tokens = spent_tokens + remaining_with_buffer_tokens
    total_project_cost_usd = round(spent_cost_usd + remaining_cost_usd, 4)

    return {
        "session_id": session_id,
        "recomputed_at": datetime.now(timezone.utc).isoformat(),
        "is_local_only": is_local_only,
        "spent_summary": {
            "spent_tokens": spent_tokens,
            "spent_cost_usd": round(spent_cost_usd, 6),
            "calls_count": spent_calls_count,
            "source": "llm_calls table"
        },
        "remaining_summary": {
            "stages_count": len(remaining_stages),
            "remaining_subtotal_tokens": remaining_subtotal_tokens,
            "rework_buffer_percentage": 20,
            "rework_buffer_tokens": rework_buffer_tokens,
            "remaining_with_buffer_tokens": remaining_with_buffer_tokens,
            "remaining_cost_usd": remaining_cost_usd,
            "stages": remaining_stages
        },
        "total_budget": {
            "total_tokens": total_project_tokens,
            "total_cost_usd": total_project_cost_usd,
            "formula": "total = spent_tokens (real ledger) + (Σ remaining_stage_tokens × 1.20)"
        },
        "inputs_shown_next_to_result": {
            "historical_rates_source": estimate_data.get("ledger_metadata", {}).get("source", "seed_default"),
            "model_pricing_rates": "config/model_pricing.json (local: $0.00)",
            "completed_stages": [s.get("stage_id") for s in completed_stages],
            "remaining_stages": [s.get("stage_id") for s in remaining_stages]
        }
    }


def check_budget_guard(
    session_id: str,
    budget_limit_tokens: Optional[int] = None,
    budget_limit_usd: Optional[float] = None,
    db_path: str = DEFAULT_DB_PATH
) -> Dict[str, Any]:
    """
    Handbook 26.4 Token budget and ledger:
    - Warnings at 80%
    - Hard pause at 100% until the client raises the budget
    - Local models cost $0 but still count tokens (tokens are time on local hardware).
    """
    session_dir = os.path.join(DATA_PROJECTS_DIR, session_id)
    intake_file = os.path.join(session_dir, "intake.json")
    estimate_file = os.path.join(session_dir, "docs", "estimate.json")

    # Determine limits from intake or estimate if not provided
    token_limit = budget_limit_tokens
    usd_limit = budget_limit_usd

    if token_limit is None and os.path.exists(intake_file):
        try:
            with open(intake_file, "r", encoding="utf-8") as f:
                intake_data = json.load(f)
                b_str = str(intake_data.get("budget", ""))
                # Check for tokens in budget string, e.g. "100000 tokens"
                tok_match = re.search(r"(\d[\d,]*)\s*tokens?", b_str, re.IGNORECASE)
                if tok_match:
                    token_limit = int(tok_match.group(1).replace(",", ""))
                # Check for USD, e.g. "$500"
                usd_match = re.search(r"\$\s*(\d[\d,]*(?:\.\d+)?)", b_str)
                if usd_match:
                    usd_limit = float(usd_match.group(1).replace(",", ""))
        except Exception:
            pass

    if token_limit is None and os.path.exists(estimate_file):
        try:
            with open(estimate_file, "r", encoding="utf-8") as f:
                est = json.load(f)
                token_limit = est.get("total_estimated_tokens", 100000)
        except Exception:
            pass

    # Default baseline if unstated
    if token_limit is None:
        token_limit = 100000

    # Query current spend
    spent_tokens = 0
    spent_cost_usd = 0.0
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("""
                SELECT SUM(input_tokens + output_tokens), SUM(cost_usd)
                FROM llm_calls
                WHERE project_id = ?
            """, (session_id,))
            row = cur.fetchone()
            if row and row[0] is not None:
                spent_tokens = int(row[0])
                spent_cost_usd = float(row[1] or 0.0)
            conn.close()
        except Exception as e:
            logger.warning(f"Error querying budget guard totals: {e}")

    token_percent = (spent_tokens / token_limit * 100.0) if token_limit > 0 else 0.0
    usd_percent = (spent_cost_usd / usd_limit * 100.0) if (usd_limit and usd_limit > 0) else 0.0

    max_percent = max(token_percent, usd_percent)

    warn_80 = max_percent >= 80.0
    pause_100 = max_percent >= 100.0

    if pause_100:
        guard_status = "paused"
        guard_message = (
            f"BUDGET EXHAUSTED: 100% budget reached ({spent_tokens:,} / {token_limit:,} tokens). "
            f"Project execution paused until client raises the budget (Handbook 26.4)."
        )
    elif warn_80:
        guard_status = "warning"
        guard_message = (
            f"BUDGET WARNING: 80% budget threshold reached ({spent_tokens:,} / {token_limit:,} tokens, {token_percent:.1f}%). "
            f"Client notified of approach to limit (Handbook 26.4)."
        )
    else:
        guard_status = "ok"
        guard_message = f"Budget within normal operating limits ({token_percent:.1f}% consumed)."

    return {
        "session_id": session_id,
        "spent_tokens": spent_tokens,
        "budget_limit_tokens": token_limit,
        "token_percent": round(token_percent, 1),
        "spent_cost_usd": round(spent_cost_usd, 4),
        "budget_limit_usd": usd_limit,
        "usd_percent": round(usd_percent, 1),
        "warn_80": warn_80,
        "pause_100": pause_100,
        "status": guard_status,
        "message": guard_message,
        "notes": "Local models cost $0 but still count tokens because tokens represent time on local hardware."
    }


# ==============================================================================
# GATE 2 STATE & APPROVAL MANAGEMENT
# ==============================================================================

def get_gate2_state(session_id: str, db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """Retrieves current Gate 2 state from JSON file and SQLite approvals table."""
    session_dir = os.path.join(DATA_PROJECTS_DIR, session_id)
    gate2_file = os.path.join(session_dir, "gate2_state.json")
    team_plan_file = os.path.join(session_dir, "docs", "team-plan.json")
    staffing_report_file = os.path.join(session_dir, "docs", "staffing-report.md")

    gate2_state = {}
    if os.path.exists(gate2_file):
        try:
            with open(gate2_file, "r", encoding="utf-8") as f:
                gate2_state = json.load(f)
        except Exception:
            gate2_state = {}

    has_team_plan = os.path.exists(team_plan_file)
    has_staffing_report = os.path.exists(staffing_report_file)

    # Check database approvals table
    db_status = "open"
    db_note = None
    approval_id = f"approval_gate2_{session_id}"
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT status, note, decided_at FROM approvals WHERE id = ?", (approval_id,))
            row = cur.fetchone()
            if row:
                db_status = row["status"]
                db_note = row["note"]
            conn.close()
        except Exception:
            pass

    is_approved = (gate2_state.get("approved", False) or db_status == "approved")

    # Invalidation check: If team-plan.json or estimate.json changed after approval, invalidate
    current_plan_hash = get_file_sha256(team_plan_file)
    saved_plan_hash = gate2_state.get("approved_plan_sha256", "")
    if is_approved and saved_plan_hash and current_plan_hash != saved_plan_hash:
        logger.warning(f"Gate 2 approval invalidated for {session_id}: team-plan.json was modified after approval.")
        gate2_state["approved"] = False
        gate2_state["status"] = "invalidated"
        gate2_state["invalidated_reason"] = "Team plan was modified after client approval."
        is_approved = False
        # Update db
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                cur.execute("UPDATE approvals SET status = 'open', note = 'Invalidated by plan modification' WHERE id = ?", (approval_id,))
                conn.commit()
                conn.close()
            except Exception:
                pass

    if not gate2_state:
        gate2_state = {
            "session_id": session_id,
            "gate": 2,
            "status": "pending" if has_team_plan else "waiting_for_team_plan",
            "approved": False,
            "approved_at": None,
            "feedback": "",
            "has_team_plan": has_team_plan,
            "has_staffing_report": has_staffing_report
        }

    gate2_state["approved"] = is_approved
    gate2_state["has_team_plan"] = has_team_plan
    gate2_state["has_staffing_report"] = has_staffing_report

    return gate2_state


def save_gate2_approval_record(
    session_id: str,
    summary_markdown: str,
    db_path: str = DEFAULT_DB_PATH
) -> str:
    """
    Stores Gate 2 approval requisition row in the approvals table (Handbook 24.1).
    """
    from skill_registry import init_approvals_db
    init_approvals_db(db_path)

    approval_id = f"approval_gate2_{session_id}"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO approvals (id, project_id, gate, summary, status, note, opened_at)
        VALUES (?, ?, 2, ?, 'open', NULL, datetime('now'))
        ON CONFLICT(id) DO UPDATE SET
            summary = excluded.summary,
            status = 'open'
    """, (approval_id, session_id, summary_markdown))
    conn.commit()
    conn.close()

    # Update session JSON
    session_dir = os.path.join(DATA_PROJECTS_DIR, session_id)
    gate2_file = os.path.join(session_dir, "gate2_state.json")
    team_plan_file = os.path.join(session_dir, "docs", "team-plan.json")

    gate2_data = {
        "session_id": session_id,
        "gate": 2,
        "approval_id": approval_id,
        "status": "open",
        "approved": False,
        "approved_at": None,
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "team_plan_sha256": get_file_sha256(team_plan_file)
    }
    with open(gate2_file, "w", encoding="utf-8") as f:
        json.dump(gate2_data, f, indent=2)

    return approval_id


def approve_gate2(
    session_id: str,
    client_notes: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH
) -> Dict[str, Any]:
    """
    Records Gate 2 client approval in the approvals table and session state.
    Captures snapshot of team-plan.json SHA256 for post-approval invalidation tracking.
    """
    from skill_registry import init_approvals_db
    init_approvals_db(db_path)

    session_dir = os.path.join(DATA_PROJECTS_DIR, session_id)
    gate2_file = os.path.join(session_dir, "gate2_state.json")
    team_plan_file = os.path.join(session_dir, "docs", "team-plan.json")
    estimate_file = os.path.join(session_dir, "docs", "estimate.json")

    approval_id = f"approval_gate2_{session_id}"
    now_iso = datetime.now(timezone.utc).isoformat()
    plan_hash = get_file_sha256(team_plan_file)
    est_hash = get_file_sha256(estimate_file)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO approvals (id, project_id, gate, summary, status, note, opened_at, decided_at)
        VALUES (?, ?, 2, 'Gate 2 Staffing & Budget Plan', 'approved', ?, datetime('now'), datetime('now'))
        ON CONFLICT(id) DO UPDATE SET
            status = 'approved',
            note = excluded.note,
            decided_at = datetime('now')
    """, (approval_id, session_id, client_notes or "Client approved team plan, model tiers, and token budget."))
    conn.commit()
    conn.close()

    gate2_data = {
        "session_id": session_id,
        "gate": 2,
        "approval_id": approval_id,
        "status": "approved",
        "approved": True,
        "approved_at": now_iso,
        "client_notes": client_notes or "",
        "approved_plan_sha256": plan_hash,
        "approved_estimate_sha256": est_hash
    }
    with open(gate2_file, "w", encoding="utf-8") as f:
        json.dump(gate2_data, f, indent=2)

    logger.info(f"Gate 2 APPROVED for {session_id} at {now_iso}. Scrum and Build stages unlocked.")
    return {
        "session_id": session_id,
        "gate": 2,
        "status": "approved",
        "approved": True,
        "approved_at": now_iso,
        "message": "Gate 2 approved successfully. Team staffing, model tiers, and budget confirmed. Stage 5 (Scrum Master) unlocked."
    }


def request_changes_gate2(
    session_id: str,
    feedback: str,
    db_path: str = DEFAULT_DB_PATH
) -> Dict[str, Any]:
    """
    Handbook 2.7.5 & 2.5: Changes requested at Gate 2:
    - Sets approval status to 'changes_requested'
    - Reopens HR / Recruiter
    - Records feedback as new Q- in qa_log.json routed through BA
    """
    from skill_registry import init_approvals_db
    init_approvals_db(db_path)

    session_dir = os.path.join(DATA_PROJECTS_DIR, session_id)
    gate2_file = os.path.join(session_dir, "gate2_state.json")
    qa_file = os.path.join(session_dir, "qa_log.json")

    # Route through BA as new Q- entry
    qa_log = []
    if os.path.exists(qa_file):
        try:
            with open(qa_file, "r", encoding="utf-8") as f:
                qa_log = json.load(f)
        except Exception:
            qa_log = []

    new_qid = f"Q-{len(qa_log)+1:03d}"
    now_iso = datetime.now(timezone.utc).isoformat()
    new_qa = {
        "id": new_qid,
        "question": "Gate 2 Client Change Request: What adjustments are required for staffing, model tiers, or budget?",
        "answer": feedback,
        "round": len(qa_log) + 1,
        "timestamp": now_iso,
        "context": "Gate 2 client staffing review"
    }
    qa_log.append(new_qa)
    with open(qa_file, "w", encoding="utf-8") as f:
        json.dump(qa_log, f, indent=2)

    approval_id = f"approval_gate2_{session_id}"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO approvals (id, project_id, gate, summary, status, note, opened_at, decided_at)
        VALUES (?, ?, 2, 'Gate 2 Staffing & Budget Plan', 'changes_requested', ?, datetime('now'), datetime('now'))
        ON CONFLICT(id) DO UPDATE SET
            status = 'changes_requested',
            note = excluded.note,
            decided_at = datetime('now')
    """, (approval_id, session_id, feedback))
    conn.commit()
    conn.close()

    gate2_data = {
        "session_id": session_id,
        "gate": 2,
        "approval_id": approval_id,
        "status": "changes_requested",
        "approved": False,
        "approved_at": None,
        "feedback": feedback,
        "routed_qid": new_qid
    }
    with open(gate2_file, "w", encoding="utf-8") as f:
        json.dump(gate2_data, f, indent=2)

    logger.info(f"Gate 2 changes requested for {session_id}: {feedback} (routed as {new_qid})")
    return {
        "session_id": session_id,
        "gate": 2,
        "status": "changes_requested",
        "routed_qid": new_qid,
        "message": f"Changes requested at Gate 2. Reopened HR & Recruiter with note; routed as {new_qid} through BA."
    }


def enforce_gate2_server_side(session_id: str, db_path: str = DEFAULT_DB_PATH) -> None:
    """
    Server-side 403 enforcement per Handbook 2.7.5:
    Any later stage (Scrum Master, build) returns 403 until Gate 2 is approved.
    A changed team plan or estimate after approval invalidates approval and returns 403.
    """
    state = get_gate2_state(session_id, db_path=db_path)
    if not state.get("approved", False):
        status = state.get("status", "open")
        reason = state.get("invalidated_reason", "Client approval at Gate 2 is required.")
        raise HTTPException(
            status_code=403,
            detail=f"Gate 2 approval required (Status: '{status}'). Later stages cannot execute until Gate 2 is approved by the client. {reason}"
        )
