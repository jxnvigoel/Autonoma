"""
Tech Lead Readiness Review Engine (Stage 5 Step 19b)
Per Handbook Chapter 10 (Tech Lead, 10.1.4, 10.2), 2.7.6 step 19b, 22.4 (Model router: high tier),
24.1 (reviews table), and Appendix A.9 (Pre-build readiness review).

Inputs: prd.md, app-flow.md, design-brief.md, architecture.md, schema.md, openapi.yaml, backlog.json.
Code computes the traceability matrix; high-tier LLM reviews and produces docs/readiness.md.
Verdict ('ready' or 'not_ready') is stored in SQLite reviews table.
Server-side gate: HTTP 403 on build/dev endpoints until verdict is ready.
Invalidation: modifying backlog.json, architecture.md, or prd.md invalidates the verdict.
"""

import os
import re
import json
import sqlite3
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Set
from fastapi import HTTPException

try:
    from llm_client import query_llm_with_meta
    from validators import validate_readiness_review_verdict
except ImportError:
    from engine.llm_client import query_llm_with_meta
    from engine.validators import validate_readiness_review_verdict

logger = logging.getLogger("autonoma-engine.readiness")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(PROJECT_ROOT, "data", "office.db")
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


def init_reviews_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """
    Initializes SQLite reviews table per Handbook Chapter 24.1:
    CREATE TABLE reviews (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      project_id TEXT NOT NULL,
      target TEXT NOT NULL,
      reviewer TEXT NOT NULL,
      kind TEXT NOT NULL,
      passed INTEGER NOT NULL,
      score REAL,
      max_score REAL,
      body TEXT NOT NULL,
      at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            target TEXT NOT NULL,
            reviewer TEXT NOT NULL,
            kind TEXT NOT NULL,
            passed INTEGER NOT NULL,
            score REAL,
            max_score REAL,
            body TEXT NOT NULL,
            at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    conn.commit()
    conn.close()


# ==============================================================================
# DETERMINISTIC CODE LAYER: TRACEABILITY MATRIX & GAPS COMPUTATION
# ==============================================================================

def compute_traceability_matrix(
    session_id: str,
    prd_text: str,
    app_flow_text: str,
    arch_text: str,
    schema_text: str,
    openapi_text: str,
    backlog_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Orchestrator computes traceability per Handbook Appendix A.9:
    - every Must-have F- -> journey (J-) -> endpoint (API-) -> table (TBL-) -> story (ST-)
    - every AC- -> story -> planned test
    - every NFR- -> mechanism or SLO
    """
    # 1. Parse PRD Features and ACs
    features = []
    feature_sections = re.split(r"(?=###\s*(?:Feature\s*)?`?F-\d+)", prd_text)
    for sec in feature_sections:
        if not sec.strip().startswith("###"):
            continue
        f_match = re.search(r"\b(F-\d{2,4})\b", sec)
        if not f_match:
            continue
        fid = f_match.group(1)
        title_match = re.search(r"###\s*(?:Feature\s*)?`?F-\d+`?:\s*([^\n\r]+)", sec)
        title = title_match.group(1).strip() if title_match else fid
        is_must_have = bool(re.search(r"\*\*(?:Priority|MoSCoW)\*\*:\s*Must-have", sec, re.IGNORECASE))
        acs = re.findall(r"\b(AC-\d{2,4})\b", sec)
        features.append({
            "id": fid,
            "title": title,
            "must_have": is_must_have,
            "acs": acs
        })

    # If no features parsed, fallback to finding F-### in PRD
    if not features:
        all_fids = sorted(list(set(re.findall(r"\b(F-\d{2,4})\b", prd_text))))
        for fid in all_fids:
            features.append({"id": fid, "title": fid, "must_have": True, "acs": []})

    # 2. Parse Journeys J-###
    journeys = sorted(list(set(re.findall(r"\b(J-\d{2,4})\b", prd_text + "\n" + app_flow_text))))

    # 3. Parse APIs API-###
    apis = sorted(list(set(re.findall(r"\b(API-\d{2,4})\b", arch_text + "\n" + openapi_text))))

    # 4. Parse Tables TBL-###
    tables = sorted(list(set(re.findall(r"\b(TBL-\d{2,4})\b", arch_text + "\n" + schema_text))))

    # 5. Parse Stories ST-###
    stories = backlog_data.get("stories", [])
    story_map = {s.get("id"): s for s in stories}

    # Map story coverage
    covered_acs: Dict[str, List[str]] = {}
    covered_features: Dict[str, List[str]] = {}
    covered_apis: Dict[str, List[str]] = {}
    covered_tables: Dict[str, List[str]] = {}

    for s in stories:
        sid = s.get("id")
        refs = s.get("refs", {})
        for ac in refs.get("ac", []):
            covered_acs.setdefault(str(ac), []).append(sid)
        for f in refs.get("features", []):
            covered_features.setdefault(str(f), []).append(sid)
        for api in refs.get("api", []):
            covered_apis.setdefault(str(api), []).append(sid)
        for tbl in refs.get("tables", []):
            covered_tables.setdefault(str(tbl), []).append(sid)

    # 6. Evaluate Traceability Chains & Detect Gaps
    feature_matrix = []
    gaps = []
    contradictions = []

    for f in features:
        fid = f["id"]
        must = f["must_have"]
        # Associated stories
        st_ids = covered_features.get(fid, [])

        # Associated journeys (linkage via text or convention)
        j_links = [j for j in journeys if j.endswith(fid.replace("F-", ""))] or (journeys[:1] if journeys else [])
        api_links = [api for api in apis if any(api in s.get("refs", {}).get("api", []) for s in stories if fid in s.get("refs", {}).get("features", []))]
        tbl_links = [tbl for tbl in tables if any(tbl in s.get("refs", {}).get("tables", []) for s in stories if fid in s.get("refs", {}).get("features", []))]

        row = {
            "feature_id": fid,
            "title": f["title"],
            "must_have": must,
            "journeys": j_links,
            "apis": api_links,
            "tables": tbl_links,
            "stories": st_ids,
            "planned_tests": [f"test_{sid.lower()}" for sid in st_ids]
        }
        feature_matrix.append(row)

        if must and not st_ids:
            gaps.append(f"Must-have Feature '{fid}' has no mapped stories in docs/backlog.json (Blocks development).")
        if must and not api_links and apis:
            gaps.append(f"Must-have Feature '{fid}' has no mapped API endpoint.")

    # Check all ACs are covered
    for f in features:
        for ac in f["acs"]:
            if ac not in covered_acs:
                gaps.append(f"Acceptance criteria '{ac}' for {f['id']} is not covered by any story in backlog.")

    # Check for contradictions: story citing an API that doesn't exist in openapi/arch
    for s in stories:
        sid = s.get("id")
        for api in s.get("refs", {}).get("api", []):
            if apis and api not in apis:
                contradictions.append(f"Story '{sid}' cites endpoint '{api}' not defined in architecture or openapi.yaml.")
        for tbl in s.get("refs", {}).get("tables", []):
            if tables and tbl not in tables:
                contradictions.append(f"Story '{sid}' cites table '{tbl}' not defined in schema.md.")

    return {
        "features": feature_matrix,
        "total_features": len(features),
        "total_stories": len(stories),
        "covered_acs_count": len(covered_acs),
        "gaps": gaps,
        "contradictions": contradictions
    }


# ==============================================================================
# TECH LEAD LLM AGENT (Handbook 10.1.4, 10.2, Appendix A.9)
# High-tier model writes docs/readiness.md
# ==============================================================================

TECH_LEAD_READINESS_SYSTEM_PROMPT = """You are the Tech Lead agent in Autonoma.
Source: skills/tech-lead/role.md (Handbook Section 10.1.4, 10.2, Appendix A.9).

Mission:
Keep the codebase correct, readable and consistent with the architecture.
No code is written before the Tech Lead's readiness review says ready.

Produce docs/readiness.md following the exact seven handbook sections:
1. What we are building: 5–7 bullets, each citing IDs (F-###, AC-###, API-###, TBL-###).
2. Gaps: anything an engineer would have to guess. Each one names the missing item and the story it blocks. If none, explicitly state "None".
3. Contradictions: pairs of IDs that disagree (e.g. AC-014 vs API-006). If none, explicitly state "None".
4. Traceability check (the orchestrator computed these; you explain the findings):
   - every Must-have F- -> journey (J-) -> endpoint (API-) -> table (TBL-) -> story (ST-)
   - every AC- -> story -> planned test
   - every NFR- -> mechanism or SLO
5. Stack confirmation: the chosen stack, with its ADR-s.
6. Start point: the first milestone and its stories (ST-001 walking skeleton).
7. Verdict: ready or not_ready.
Rule: Verdict MUST be 'ready' if zero blocking gaps and zero contradictions exist.
If any blocking gap or contradiction exists, verdict MUST be 'not_ready'.

Output must be in clear GitHub-flavored markdown with the heading '# Pre-Build Readiness Review'.
At the very end of your review, include a JSON block with the machine-readable verdict:
```json
{
  "verdict": "ready",
  "first_milestone": "Milestone 1: Walking Skeleton (ST-001)",
  "gaps_count": 0,
  "contradictions_count": 0
}
```
"""


def run_readiness_review(
    session_id: str,
    force_provider: Optional[str] = None,
    force_model: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH
) -> Dict[str, Any]:
    """
    Executes Tech Lead readiness review (Stage 5 Step 19b).
    Orchestrator calculates traceability matrix; high-tier LLM reviews and writes docs/readiness.md.
    Stores verdict in SQLite reviews table.
    """
    session_dir = os.path.join(DATA_PROJECTS_DIR, session_id)
    docs_dir = os.path.join(session_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)

    # 1. Load inputs
    def _read_doc(name: str) -> str:
        p = os.path.join(docs_dir, name)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    prd_text = _read_doc("prd.md")
    app_flow_text = _read_doc("app-flow.md")
    design_brief_text = _read_doc("design-brief.md")
    arch_text = _read_doc("architecture.md")
    schema_text = _read_doc("schema.md")
    openapi_text = _read_doc("openapi.yaml")

    backlog_file = os.path.join(docs_dir, "backlog.json")
    backlog_data = {"stories": []}
    if os.path.exists(backlog_file):
        with open(backlog_file, "r", encoding="utf-8") as f:
            backlog_data = json.load(f)

    # 2. Code calculates Traceability Matrix
    matrix_info = compute_traceability_matrix(
        session_id=session_id,
        prd_text=prd_text,
        app_flow_text=app_flow_text,
        arch_text=arch_text,
        schema_text=schema_text,
        openapi_text=openapi_text,
        backlog_data=backlog_data
    )

    computed_gaps = matrix_info.get("gaps", [])
    computed_contradictions = matrix_info.get("contradictions", [])

    # Hash tracking for invalidation
    plan_hash = get_file_sha256(backlog_file)
    arch_hash = get_file_sha256(os.path.join(docs_dir, "architecture.md"))
    prd_hash = get_file_sha256(os.path.join(docs_dir, "prd.md"))

    # 3. LLM Review (High-tier model per Handbook 22.4)
    matrix_summary_json = json.dumps({
        "total_features": matrix_info["total_features"],
        "total_stories": matrix_info["total_stories"],
        "gaps_found": computed_gaps,
        "contradictions_found": computed_contradictions,
        "sample_chains": matrix_info["features"][:4]
    }, indent=2)

    prompt = f"""Conduct the pre-build readiness review for project '{session_id}'.

INPUT DIGESTS:
1. PRD Core:
{prd_text[:4000]}

2. Architecture Overview & ADRs:
{arch_text[:4000]}

3. Backlog Stories:
{json.dumps(backlog_data.get('stories', [])[:10], indent=2)}

4. Orchestrator-Computed Traceability & Gaps:
{matrix_summary_json}

Follow the seven handbook sections. Be thorough, cite specific IDs, and render your verdict ('ready' or 'not_ready').
"""

    logger.info(f"Running Tech Lead high-tier LLM readiness review for {session_id}...")

    raw_resp, meta = query_llm_with_meta(
        prompt=prompt,
        system=TECH_LEAD_READINESS_SYSTEM_PROMPT,
        role="tech-lead",
        session_id=session_id,
        task_id="tech_lead_readiness_review",
        temperature=0.1,
        max_tokens=4000,
        force_provider=force_provider,
        force_model=force_model
    )

    # Parse verdict from LLM output. Fail closed: no explicit "ready" means not ready.
    verdict = "not_ready"
    if re.search(r'"verdict":\s*"not_ready"', raw_resp, re.IGNORECASE) or "verdict: not_ready" in raw_resp.lower():
        verdict = "not_ready"
    elif re.search(r'"verdict":\s*"ready"', raw_resp, re.IGNORECASE) or "verdict: ready" in raw_resp.lower():
        verdict = "ready"
    if meta.get("is_degraded"):
        verdict = "not_ready"  # a degraded reviewer cannot unlock the build

    # Enforce deterministic validator rule: If gaps or contradictions exist, verdict CANNOT be ready
    ok, v_errs = validate_readiness_review_verdict(verdict, computed_gaps, computed_contradictions)
    if not ok:
        logger.warning(f"Tech Lead LLM returned '{verdict}' but code detected unresolved gaps: {v_errs}")
        verdict = "not_ready"

    is_passed = 1 if verdict == "ready" else 0
    score = 1.0 if verdict == "ready" else 0.0

    # 4. Save docs/readiness.md
    readiness_file = os.path.join(docs_dir, "readiness.md")
    stamp = f"\n\n<!-- Assembled by Tech Lead LLM ({meta.get('provider', 'cloud')}:{meta.get('model', 'high-tier')}) at {datetime.now(timezone.utc).isoformat()} -->\n"
    with open(readiness_file, "w", encoding="utf-8") as f:
        f.write(raw_resp.strip() + stamp)

    # 5. Persist to SQLite reviews table (Handbook 24.1)
    init_reviews_db(db_path)
    review_body = {
        "verdict": verdict,
        "gaps": computed_gaps,
        "contradictions": computed_contradictions,
        "traceability": {
            "total_features": matrix_info["total_features"],
            "total_stories": matrix_info["total_stories"],
            "chains": matrix_info["features"]
        },
        "hashes": {
            "backlog_sha256": plan_hash,
            "architecture_sha256": arch_hash,
            "prd_sha256": prd_hash
        },
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "provider": meta.get("provider"),
        "model": meta.get("model")
    }

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO reviews (project_id, target, reviewer, kind, passed, score, max_score, body, at)
        VALUES (?, 'docs/readiness.md', ?, 'readiness', ?, ?, 1.0, ?, datetime('now'))
        """,
        (session_id, f"{session_id}_tech-lead-1", is_passed, score, json.dumps(review_body))
    )
    conn.commit()
    conn.close()

    # Also save readiness_state.json in session directory for instant caching
    state_file = os.path.join(session_dir, "readiness_state.json")
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(review_body, f, indent=2)

    logger.info(f"Tech Lead readiness review complete for {session_id}. Verdict: {verdict.upper()}.")

    return {
        "status": "success",
        "session_id": session_id,
        "verdict": verdict,
        "passed": bool(is_passed),
        "gaps": computed_gaps,
        "contradictions": computed_contradictions,
        "traceability_matrix": matrix_info,
        "readiness_file": readiness_file
    }


def get_readiness_state(session_id: str, db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    Queries current readiness state and validates whether it was invalidated
    by modifications to backlog.json, architecture.md, or prd.md.
    """
    session_dir = os.path.join(DATA_PROJECTS_DIR, session_id)
    docs_dir = os.path.join(session_dir, "docs")
    state_file = os.path.join(session_dir, "readiness_state.json")

    init_reviews_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT passed, score, body, at FROM reviews WHERE project_id = ? AND kind = 'readiness' ORDER BY id DESC LIMIT 1",
        (session_id,)
    )
    row = cur.fetchone()
    conn.close()

    if not row and not os.path.exists(state_file):
        return {
            "session_id": session_id,
            "status": "not_conducted",
            "verdict": "not_ready",
            "passed": False,
            "message": "Tech Lead readiness review has not yet been executed."
        }

    data = {}
    if row:
        try:
            data = json.loads(row["body"])
        except Exception:
            pass
    elif os.path.exists(state_file):
        with open(state_file, "r", encoding="utf-8") as f:
            data = json.load(f)

    verdict = data.get("verdict", "not_ready")
    hashes = data.get("hashes", {})
    saved_backlog_hash = hashes.get("backlog_sha256", "")
    saved_arch_hash = hashes.get("architecture_sha256", "")
    saved_prd_hash = hashes.get("prd_sha256", "")

    curr_backlog_hash = get_file_sha256(os.path.join(docs_dir, "backlog.json"))
    curr_arch_hash = get_file_sha256(os.path.join(docs_dir, "architecture.md"))
    curr_prd_hash = get_file_sha256(os.path.join(docs_dir, "prd.md"))

    # Invalidation check: handbook 10.1.4, 2.7.6 step 19b
    is_invalidated = False
    invalidation_reasons = []

    if saved_backlog_hash and curr_backlog_hash != saved_backlog_hash:
        is_invalidated = True
        invalidation_reasons.append("docs/backlog.json was modified after the readiness review.")

    if saved_arch_hash and curr_arch_hash != saved_arch_hash:
        is_invalidated = True
        invalidation_reasons.append("docs/architecture.md was modified after the readiness review.")

    if saved_prd_hash and curr_prd_hash != saved_prd_hash:
        is_invalidated = True
        invalidation_reasons.append("docs/prd.md was modified after the readiness review.")

    if is_invalidated:
        logger.warning(f"Readiness review invalidated for {session_id}: {invalidation_reasons}")
        return {
            "session_id": session_id,
            "status": "invalidated",
            "verdict": "not_ready",
            "passed": False,
            "invalidation_reasons": invalidation_reasons,
            "message": "Readiness review invalidated due to changes in backlog, architecture, or PRD. Re-run required."
        }

    return {
        "session_id": session_id,
        "status": "ready" if verdict == "ready" else "not_ready",
        "verdict": verdict,
        "passed": (verdict == "ready"),
        "gaps": data.get("gaps", []),
        "contradictions": data.get("contradictions", []),
        "traceability": data.get("traceability", {}),
        "reviewed_at": data.get("reviewed_at")
    }


def enforce_readiness_server_side(session_id: str, db_path: str = DEFAULT_DB_PATH) -> None:
    """
    Server-side gate per Handbook Chapter 10.1.4 & 2.7.6 step 19b:
    No code is written until the verdict is ready.
    Returns HTTP 403 Forbidden with detailed reasons if not ready or invalidated.
    """
    state = get_readiness_state(session_id, db_path)
    if not state.get("passed", False):
        status_name = state.get("status", "not_ready")
        reasons = state.get("invalidation_reasons") or state.get("gaps") or [state.get("message", "Readiness review not passed.")]
        raise HTTPException(
            status_code=403,
            detail={
                "error": "READINESS_GATE_LOCKED",
                "session_id": session_id,
                "status": status_name,
                "verdict": state.get("verdict", "not_ready"),
                "reasons": reasons,
                "rule": "Handbook 10.1.4 & 2.7.6 step 19b: No code is written before the Tech Lead's readiness review says ready."
            }
        )
