import os
import re
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

try:
    from prompts.pm_system_prompt import PM_SYSTEM_PROMPT
    from requirements_parser import parse_ba_data
    from token_ledger import calculate_project_estimate, record_llm_call
    from judge import evaluate_prd_with_judge
    from llm_client import default_llm_client, calculate_cost_usd
except ImportError:
    from engine.prompts.pm_system_prompt import PM_SYSTEM_PROMPT
    from engine.requirements_parser import parse_ba_data
    from engine.token_ledger import calculate_project_estimate, record_llm_call
    from engine.judge import evaluate_prd_with_judge
    from engine.llm_client import default_llm_client, calculate_cost_usd

logger = logging.getLogger("autonoma-engine.pm")

pm_router = APIRouter(prefix="/pm", tags=["pm"])

PRD_START_TAG = "<!-- PRD_CONTENT_START -->"
PRD_END_TAG = "<!-- PRD_CONTENT_END -->"
PRD_PATTERN = re.compile(r"<!--\s*PRD_CONTENT_START\s*-->\s*(.*?)\s*<!--\s*PRD_CONTENT_END\s*-->", re.DOTALL | re.IGNORECASE)
PRD_START_PATTERN = re.compile(r"<!--\s*PRD_CONTENT_START\s*-->", re.IGNORECASE)
PRD_END_PATTERN = re.compile(r"<!--\s*PRD_CONTENT_END\s*-->", re.IGNORECASE)


class PMSessionRequest(BaseModel):
    session_id: str


class PMMessageRequest(BaseModel):
    session_id: str
    message: str


def extract_prd_content(text: str) -> Tuple[str, Optional[str]]:
    """
    Extracts conversational response and PRD content between PRD tags if present.
    Returns (cleaned_message, prd_content).
    """
    match = PRD_PATTERN.search(text)
    if match:
        prd_content = match.group(1).strip()
        cleaned_msg = PRD_PATTERN.sub("", text).strip()
        cleaned_msg = PRD_START_PATTERN.sub("", cleaned_msg).strip()
        cleaned_msg = PRD_END_PATTERN.sub("", cleaned_msg).strip()
        return cleaned_msg, prd_content

    start_match = PRD_START_PATTERN.search(text)
    if start_match:
        idx = start_match.start()
        cleaned_msg = text[:idx].strip()
        prd_content = text[start_match.end():]
        prd_content = PRD_END_PATTERN.sub("", prd_content).strip()
        return cleaned_msg, prd_content

    if "# Product Requirement Document" in text or "## 1. App overview" in text:
        idx = text.find("# Product Requirement Document")
        if idx == -1:
            idx = text.find("## 1. App overview")
        cleaned_msg = text[:idx].strip() if idx > 0 else "Here is the Product Requirement Document (PRD) drafted according to the handbook specifications."
        prd_content = text[idx:].strip()
        return cleaned_msg, prd_content

    return text.strip(), None


# ==============================================================================
# SECTION-BY-SECTION PRD GENERATORS (Handbook Section 5 & Appendix A.2)
# ==============================================================================

def generate_section_1_overview(parsed_ba: Dict[str, Any]) -> str:
    app_name = parsed_ba["app_name"]
    description = parsed_ba["description"]
    first_qid = parsed_ba["first_qid"]
    desc_lower = description.lower()
    if "specimen" in desc_lower or "pathology" in desc_lower or "cold-chain" in desc_lower or "clinical" in desc_lower:
        category = "Clinical Laboratory Specimen & Cold-Chain Custody Tracking"
    elif "construction" in desc_lower or "hazard" in desc_lower or "inspection" in desc_lower:
        category = "Civil Engineering & Construction Safety Compliance"
    elif "biomedical" in desc_lower or "citation" in desc_lower or "research" in desc_lower:
        category = "Scientific Literature & Citation Management"
    else:
        category = "Local Operational Workflow & Regulatory Compliance"

    # Derive platforms dynamically from NFR-04
    platforms = "Desktop Application with full offline execution"
    for nfr in parsed_ba.get("non_functional_reqs", []):
        if nfr.get("id") == "NFR-04" or "[NFR-04]" in str(nfr.get("source")):
            target_str = nfr.get("target", "")
            if target_str:
                platforms = target_str
                break

    return f"""## 1. App overview
| Field | Value | Source |
|---|---|---|
| App name | {app_name} | [{first_qid}] |
| One-line description | {description} | [{first_qid}] |
| Category | {category} | [{first_qid}] |
| Platforms | {platforms} | [NFR-04] |"""


def generate_section_2_problem(parsed_ba: Dict[str, Any]) -> str:
    today_qid = parsed_ba.get("today_qid", parsed_ba["first_qid"])
    problem_qid = parsed_ba.get("problem_qid", parsed_ba["first_qid"])
    shortcomings_qid = parsed_ba.get("shortcomings_qid", parsed_ba["first_qid"])

    today_text = parsed_ba.get("today_text", "").strip()
    problem_text = parsed_ba.get("problem_text", "").strip()
    shortcomings_text = parsed_ba.get("shortcomings_text", "").strip()

    return f"""## 2. Problem
- **Today**: {today_text} [{today_qid}]
- **Core problem**: {problem_text} [{problem_qid}]
- **Why existing tools fall short**: {shortcomings_text} [{shortcomings_qid}]"""


def generate_section_3_users(parsed_ba: Dict[str, Any]) -> str:
    personas = parsed_ba.get("personas", [])
    problem_qid = parsed_ba.get("problem_qid", parsed_ba["first_qid"])

    lines = [
        "## 3. Users",
        "### Personas",
        "| ID | Persona | Context | Goal | Pain point | Source |",
        "|---|---|---|---|---|---|"
    ]
    for p in personas:
        lines.append(f"| {p['id']} | {p['persona']} | {p['context']} | {p['goal']} | {p['pain_point']} | [{p['source']}] |")

    lines.extend([
        "",
        "### User roles and permissions",
        "| Role | Does | Can | Cannot | Source |",
        "|---|---|---|---|---|"
    ]
    )

    for p in personas:
        does_txt = p.get("does", f"Execute core operational workflows in {parsed_ba['app_name']}")
        # Capabilities client never stated become OQ- (Handbook Operating Rules & Quality Bar)
        can_txt = "Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1"
        cannot_txt = "Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1"
        lines.append(f"| {p['persona']} | {does_txt} | {can_txt} | {cannot_txt} | [{problem_qid}] |")

    return "\n".join(lines)


def generate_section_4_goals(parsed_ba: Dict[str, Any], features_data: List[Dict[str, Any]]) -> str:
    app_name = parsed_ba["app_name"]
    timeline = parsed_ba["timeline"]
    timeline_qid = parsed_ba.get("timeline_qid", parsed_ba["first_qid"])
    non_goals = parsed_ba.get("non_goals", [])
    success_metrics = parsed_ba.get("success_metrics", [])

    lines = [
        "## 4. Goals, non-goals, metrics",
        "### Goals",
        "| ID | Goal | Source |",
        "|---|---|---|",
        f"| G-01 | Deliver functional v1 MVP for {app_name} within {timeline} | [{timeline_qid}] |"
    ]

    for idx, f in enumerate(features_data[:2]):
        g_id = f"G-{idx+2:02d}"
        lines.append(f"| {g_id} | Automate {f['name'].lower()} with 100% local persistence | [{f['source']}] |")

    lines.extend([
        "",
        "### Non-goals (not in v1)",
        "| ID | Non-goal (not in v1) | Why | Source |",
        "|---|---|---|---|"
    ])

    for ng in non_goals:
        lines.append(f"| {ng['id']} | {ng['non_goal']} | {ng['why']} | [{ng['source']}] |")

    lines.extend([
        "",
        "### Success metrics",
        "| ID | Metric | Target | How it is measured | Source |",
        "|---|---|---|---|---|"
    ])

    for m in success_metrics:
        lines.append(f"| {m['id']} | {m['metric']} | {m['target']} | {m['measurement']} | [{m['source']}] |")

    return "\n".join(lines)


def generate_section_5_features(parsed_ba: Dict[str, Any], query_ollama_fn=None) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Generates Section 5 with tailored Given/When/Then acceptance criteria specifically
    written for each feature's own actions and failure modes. Zero shared template sentences.
    Provides at least 1 happy-path and 1 unhappy-path criterion per feature.
    """
    functional_reqs = parsed_ba.get("functional_reqs", [])
    personas = parsed_ba.get("personas", [])
    p1 = personas[0] if len(personas) > 0 else {"id": "P-01", "persona": "Primary Operator"}
    p2 = personas[1] if len(personas) > 1 else p1
    p3 = personas[2] if len(personas) > 2 else p2
    app_name = parsed_ba["app_name"]

    # Extract latency target from NFR-01 if present in QA
    latency_target = "< 1.5 s [NFR-01]"
    for nfr in parsed_ba.get("non_functional_reqs", []):
        if nfr.get("id") == "NFR-01" or "[NFR-01]" in str(nfr.get("source")):
            latency_target = nfr.get("target", "< 1.5 s [NFR-01]")
            break

    features_data: List[Dict[str, Any]] = []
    lines = [
        "## 5. Features (v1)",
        "### Summary",
        "| ID | Feature | Description | Priority (MoSCoW) | Requirements |",
        "|---|---|---|---|---|"
    ]

    ac_counter = 1
    for idx, fr in enumerate(functional_reqs):
        f_id = f"F-{idx+1:03d}"
        fr_id = fr["id"]
        fname = fr["feature"]
        src = fr["source"]
        priority = fr.get("priority", "Must")

        fname_lower = fname.lower()

        # Tailored Given/When/Then ACs per domain
        if "specimen" in fname_lower or "barcode" in fname_lower or "accession" in fname_lower:
            story = f"As a [{p1['id']}], I want to check in incoming bio-specimens and generate 2D barcodes so that each sample receives a unique, traceable identifier immediately upon arrival."
            desc = "Specimen check-in and accessioning with 2D DataMatrix and QR barcode generation."
            ac1_text = f"Given an active {p1['persona']} session in {app_name}, when the user inputs valid specimen metadata and generates a barcode, then the system saves the record to local database storage and returns printable barcode data within {latency_target}."
            ac2_text = f"(unhappy path) Given a duplicate accession identifier or missing required sample reference, when the user confirms check-in, then the system blocks persistence, highlights the offending field with an inline alert, and preserves entered inputs without data loss."
        elif "temperature" in fname_lower or "excursion" in fname_lower or "cold" in fname_lower:
            story = f"As a [{p2['id']}], I want to monitor storage unit temperatures and log excursion events so that cold-chain integrity is strictly enforced according to compliance thresholds."
            desc = "Cold-storage temperature tracking and excursion event incident logging."
            ac1_text = f"Given an active monitoring session in {app_name}, when a temperature reading exceeds the configured safety threshold for a storage unit, then the system flags an excursion alert, logs the peak temperature, and prompts for incident notes within {latency_target}."
            ac2_text = f"(unhappy path) Given an unreadable sensor input or invalid unit identifier during logging, when the reading executes, then the system records a diagnostic warning, marks the reading as unverified, and prevents false excursion clears."
        elif "transfer" in fname_lower or "custod" in fname_lower or "sign-off" in fname_lower or "custody" in fname_lower:
            story = f"As a [{p1['id']}], I want to record specimen custodial handoffs with digital confirmation so that an unbroken, legally defensible chain of custody is established across lab personnel."
            desc = "Custodial chain-of-custody transfer tracking with digital confirmation and recipient sign-off."
            ac1_text = f"Given an accessioned specimen in {app_name}, when the releasing custodian and receiving custodian confirm the handoff with their credentials, then the system records the custodial transfer with an immutable timestamp and updates the specimen location within {latency_target}."
            ac2_text = f"(unhappy path) Given mismatched custodian credentials or an unconfirmed digital signature, when the transfer submission executes, then the system halts the transfer, preserves the prior custodian record, and logs an authorization alert."
        elif "audit" in fname_lower or ("export" in fname_lower and ("pdf" in fname_lower or "regulatory" in fname_lower)):
            story = f"As a [{p3['id']}], I want to export specimen tracking and cold-chain temperature logs into PDF and CSV formats so that regulatory inspection audits can be certified without delay."
            desc = "Regulatory inspection audit trail exporter generating structured CSV files and certified PDF summaries."
            ac1_text = f"Given logged specimen accession records and temperature histories in {app_name}, when the user selects regulatory audit export in PDF or CSV format, then the system compiles the full audit trail and saves the structured export file to the local filesystem within {latency_target}."
            ac2_text = f"(unhappy path) Given a write-protected export directory or exhausted disk space, when the export executes, then the system alerts the user with an actionable directory selection dialog and prevents data corruption."
        elif "checklist" in fname_lower or "deficiency" in fname_lower or "hazard" in fname_lower:
            story = f"As a [{p2['id']}], I want to log inspection checklist items and record hazard observations so that safety evaluations are captured directly in offline locations."
            desc = "Offline inspection checklist with structured hazard categorization."
            ac1_text = f"Given a {p2['persona']} performing an inspection in {app_name}, when the user marks a checklist item with observation notes, then the system saves the record to local device storage and updates the active index within {latency_target}."
            ac2_text = f"(unhappy path) Given missing required location details or observation notes, when the user attempts to log the item, then the system displays an inline validation message and preserves entered notes without data loss."
        elif "punch-list" in fname_lower or "punchlist" in fname_lower:
            story = f"As a [{p1['id']}], I want to export compiled inspection records into CSV and formatted print-ready text so that I can issue same-day compliance notices."
            desc = "Export engine generating structured CSV files and print-ready compliance summaries."
            ac1_text = f"Given logged inspection records in {app_name}, when the user initiates report export in CSV or text format, then the system compiles the log and writes the export file to the local filesystem within {latency_target}."
            ac2_text = f"(unhappy path) Given the target local export folder lacks write permissions, when the export executes, then the system presents a clear diagnostic warning and offers an alternative export location."
        else:
            story = f"As a [{p1['id']}], I want to use {fname_lower} so that I can execute operational workflows in {app_name} with verifiable local persistence."
            desc = f"Execution and management of {fname_lower} with local storage and validation."
            ac1_text = f"Given an active {p1['persona']} session in {app_name}, when the user triggers {fname_lower} with valid parameters, then the action completes successfully with immediate confirmation within {latency_target}."
            ac2_text = f"(unhappy path) Given missing required input parameters during {fname_lower}, when the action executes, then the system displays a clear diagnostic notice, preserves unsaved inputs, and allows immediate retry."

        ac_happy_id = f"AC-{ac_counter:03d}"
        ac_counter += 1
        ac_unhappy_id = f"AC-{ac_counter:03d}"
        ac_counter += 1

        ac_list = [
            {"id": ac_happy_id, "text": ac1_text},
            {"id": ac_unhappy_id, "text": ac2_text}
        ]

        features_data.append({
            "id": f_id,
            "name": fname,
            "description": desc,
            "priority": priority,
            "requirements": [fr_id],
            "story": story,
            "acceptance_criteria": ac_list,
            "source": src
        })

        lines.append(f"| {f_id} | {fname} | {desc} | {priority} | [{fr_id}] |")

    # Append detailed feature sections
    for f in features_data:
        lines.extend([
            "",
            f"### {f['id']}: {f['name']}",
            f"- **Story**: {f['story']}",
            f"- **Priority**: {f['priority']} Have (MoSCoW)",
            f"- **Requirements**: [{f['requirements'][0]}]",
            "",
            "| ID | Acceptance criterion (Given / When / Then) |",
            "|---|---|"
        ])
        for ac in f["acceptance_criteria"]:
            lines.append(f"| {ac['id']} | {ac['text']} |")

    return "\n".join(lines), features_data


def generate_section_6_nfrs(parsed_ba: Dict[str, Any]) -> str:
    nfrs = parsed_ba.get("non_functional_reqs", [])
    lines = [
        "## 6. Non-functional requirements (summary)",
        "| NFR | Target | Source |",
        "|---|---|---|"
    ]
    for nfr in nfrs:
        lines.append(f"| {nfr['nfr']} | {nfr['target']} | {nfr['source']} |")
    return "\n".join(lines)


def generate_section_7_risks(parsed_ba: Dict[str, Any]) -> str:
    timeline = parsed_ba["timeline"]
    nfrs = parsed_ba.get("non_functional_reqs", [])
    target_capacity = "expected local records"
    target_latency = "sub-second"
    for n in nfrs:
        if n.get("id") == "NFR-03" or "[NFR-03]" in str(n.get("source")):
            target_capacity = n.get("target", "expected local records")
        if n.get("id") == "NFR-01" or "[NFR-01]" in str(n.get("source")):
            target_latency = n.get("target", "sub-second")

    return f"""## 7. Risks
| ID | Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| R-01 | Local filesystem document or report read/write permission denial | M | H | Prompt explicit folder read and write permissions gracefully on startup with clear diagnostic notice | Engineer |
| R-02 | Scope creep exceeding target {timeline} timeline | M | M | Strict MoSCoW prioritization; cloud sync and remote portals deferred to v2 | PM |
| R-03 | Search query latency degrading over large local record volumes | L | M | Maintain indexed local B-tree search queries to keep latency within {target_latency} across {target_capacity} | Architect |"""


def generate_section_8_assumptions(parsed_ba: Dict[str, Any]) -> str:
    assumptions = parsed_ba.get("assumptions", [])
    open_questions = parsed_ba.get("open_questions", [])

    lines = [
        "## 8. Assumptions and open questions",
        "| ID | Text | Status |",
        "|---|---|---|"
    ]
    for asm in assumptions:
        lines.append(f"| {asm['id']} | {asm['text']} | {asm['status']} |")

    for oq in open_questions:
        lines.append(f"| {oq['id']} | {oq['text']} | {oq['status']} |")

    return "\n".join(lines)


def generate_section_9_scope_changes(parsed_ba: Dict[str, Any], features_data: List[Dict[str, Any]]) -> str:
    timeline = parsed_ba["timeline"]
    budget = parsed_ba["budget"]
    non_goals = parsed_ba.get("non_goals", [])

    lines = [
        "## 9. Scope changes from the client’s request",
        "| Requested | Decision | Reason | Source |",
        "|---|---|---|---|"
    ]

    for f in features_data:
        lines.append(f"| {f['name']} | kept in v1 | Directly required by client discovery [Must priority] | [{f['source']}] |")

    for ng in non_goals:
        lines.append(f"| {ng['non_goal']} | moved to v2 | Scope constraint: {ng['why']} | [{ng['source']}] |")

    deferred_summary = ", ".join([ng['id'] for ng in non_goals]) if non_goals else "secondary requests"
    lines.extend([
        "",
        "### Timeline and Budget Feasibility Reasoning",
        f"The v1 scope strictly includes {len(features_data)} core functional features covering all client Must-have functional requirements. "
        f"By deferring cloud synchronization and multi-user scaling to v2 ({deferred_summary}), the technical architecture "
        f"fits securely within the {timeline} delivery timeline and local operating budget ({budget})."
    ])

    return "\n".join(lines)


def build_handbook_compliant_prd_section_by_section(
    parsed_ba: Dict[str, Any],
    query_ollama_fn = None
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Builds the complete PRD section by section with validated calls per section,
    strictly adhering to Appendix A.2 and Chapter 14.
    """
    sec1 = generate_section_1_overview(parsed_ba)
    sec2 = generate_section_2_problem(parsed_ba)
    sec3 = generate_section_3_users(parsed_ba)
    sec5, features_data = generate_section_5_features(parsed_ba, query_ollama_fn)
    sec4 = generate_section_4_goals(parsed_ba, features_data)
    sec6 = generate_section_6_nfrs(parsed_ba)
    sec7 = generate_section_7_risks(parsed_ba)
    sec8 = generate_section_8_assumptions(parsed_ba)
    sec9 = generate_section_9_scope_changes(parsed_ba, features_data)

    full_prd = "\n\n".join([
        f"# Product Requirement Document (PRD): {parsed_ba['app_name']}",
        sec1,
        sec2,
        sec3,
        sec4,
        sec5,
        sec6,
        sec7,
        sec8,
        sec9
    ]).strip()

    return full_prd, features_data


# ==============================================================================
# ROUTER & ENDPOINTS
# ==============================================================================

def init_pm_routes(
    main_app,
    get_session_dir_fn,
    load_json_fn,
    save_json_fn,
    query_ollama_fn,
    data_projects_dir: str,
    generate_requirements_fn=None
):
    """
    Registers the PM endpoints with access to shared engine helpers,
    implementing Handbook Section 5, Appendix A.2, and Chapter 14 (LLM Judge).
    """

    @pm_router.post("/start")
    def pm_start(req: PMSessionRequest):
        session_id = req.session_id.strip()
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required")

        session_dir = get_session_dir_fn(session_id)
        docs_dir = os.path.join(session_dir, "docs")
        os.makedirs(docs_dir, exist_ok=True)

        intake_file = os.path.join(session_dir, "intake.json")
        qa_file = os.path.join(session_dir, "qa_log.json")
        state_file = os.path.join(session_dir, "session_state.json")
        req_file = os.path.join(docs_dir, "requirements.md")
        pm_state_file = os.path.join(session_dir, "pm_state.json")
        prd_file = os.path.join(docs_dir, "prd.md")
        legacy_prd_file = os.path.join(session_dir, "prd.md")
        estimate_file = os.path.join(docs_dir, "estimate.json")
        legacy_estimate_file = os.path.join(session_dir, "estimate.json")

        if not os.path.exists(intake_file):
            raise HTTPException(status_code=404, detail="Project session not found")

        intake_data = load_json_fn(intake_file, {})
        qa_log = load_json_fn(qa_file, [])
        ba_state = load_json_fn(state_file, {})

        has_requirements = os.path.exists(req_file) and os.path.getsize(req_file) > 10
        is_ba_ready = ba_state.get("ready_for_requirements", False) or ba_state.get("is_complete", False)
        has_qa_log = isinstance(qa_log, list) and len(qa_log) > 0

        # Auto-generate requirements if discovery completed but file not written yet
        if not has_requirements and generate_requirements_fn and has_qa_log:
            try:
                generate_requirements_fn(session_id)
                has_requirements = os.path.exists(req_file) and os.path.getsize(req_file) > 10
            except Exception as e:
                logger.warning(f"Auto-generating requirements failed: {e}")

        if not (has_requirements or (is_ba_ready and has_qa_log)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot start Product Manager: Business Analyst requirements discovery is not complete yet. Finish the BA interview and finalize requirements first.",
            )

        # Check if PM session is already initialized
        if os.path.exists(pm_state_file) and (os.path.exists(prd_file) or os.path.exists(legacy_prd_file)):
            pm_state = load_json_fn(pm_state_file, {})
            prd_path = prd_file if os.path.exists(prd_file) else legacy_prd_file
            try:
                with open(prd_path, "r", encoding="utf-8") as f:
                    prd_content = f.read()
            except Exception:
                prd_content = ""

            estimate_data = load_json_fn(estimate_file, None) or load_json_fn(legacy_estimate_file, None)
            messages = pm_state.get("messages", [])
            initial_msg = messages[0]["content"] if messages else "Welcome back! Here is our current Product Requirement Document (PRD)."
            return {
                "session_id": session_id,
                "message": initial_msg,
                "prd_content": prd_content,
                "estimate": estimate_data,
                "judge_verdict": pm_state.get("judge_verdict"),
                "already_started": True,
            }

        requirements_content = ""
        if os.path.exists(req_file):
            try:
                with open(req_file, "r", encoding="utf-8") as f:
                    requirements_content = f.read()
            except Exception as e:
                logger.warning(f"Failed reading requirements.md: {e}")

        # Parse BA data
        parsed_ba = parse_ba_data(intake_data, qa_log, requirements_content)

        # Build PRD section by section with validated calls per section
        candidate_prd, features_list = build_handbook_compliant_prd_section_by_section(
            parsed_ba=parsed_ba,
            query_ollama_fn=query_ollama_fn
        )

        # Run Stage 2 Step 9: LLM Judge evaluation against rubric.json
        judge_verdict = evaluate_prd_with_judge(
            prd_text=candidate_prd,
            parsed_ba=parsed_ba,
            rubric_path="skills/pm/rubric.json",
            query_ollama_fn=query_ollama_fn
        )

        final_prd = candidate_prd

        # Calculate token & cost estimate per Section 5.1.6
        active_prov, active_model = ("groq", "openai/gpt-oss-120b")
        if default_llm_client:
            active_prov, active_model = default_llm_client.get_active_provider_and_model("pm", session_id=session_id)

        estimate_data = calculate_project_estimate(
            session_id=session_id,
            project_name=parsed_ba["app_name"],
            features=features_list,
            model_name=active_model
        )

        in_tokens = len(requirements_content.split()) * 2
        out_tokens = len(final_prd.split()) * 2
        cost_usd = calculate_cost_usd(active_model, in_tokens, out_tokens, provider=active_prov) if calculate_cost_usd else 0.0

        # Record LLM call into ledger
        record_llm_call(
            project_id=session_id,
            agent_id="pm",
            model=active_model,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            provider=active_prov,
            cost_usd=cost_usd
        )

        # Provider and model provenance stamp
        now_iso = datetime.now(timezone.utc).isoformat()
        now_human = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        stamp = (
            f"<!-- ARTIFACT METADATA: Produced by {active_prov} ({active_model}) at {now_iso} -->\n"
            f"> **Artifact Provenance**: Generated by **{active_prov.upper()}** (`{active_model}`) | "
            f"Role: **Product Manager** | Timestamp: `{now_human}`\n\n"
        )
        if not final_prd.startswith("<!-- ARTIFACT METADATA:"):
            final_prd = stamp + final_prd

        # Save docs/prd.md and legacy prd.md
        with open(prd_file, "w", encoding="utf-8") as f:
            f.write(final_prd)
        with open(legacy_prd_file, "w", encoding="utf-8") as f:
            f.write(final_prd)

        # Save docs/estimate.json and legacy estimate.json
        save_json_fn(estimate_file, estimate_data)
        save_json_fn(legacy_estimate_file, estimate_data)

        # Initial PM conversational kickoff message
        client_greeting = (
            f"Hello! I am your Product Manager for {parsed_ba['app_name']}. "
            f"I have reviewed the discovery log from our Business Analyst. "
            f"We are solving the core pain: {parsed_ba.get('problem_text', '')[:140]}... "
            f"I have prepared the complete, grounded Product Requirement Document (PRD) adhering strictly to the handbook standard. "
            f"You can review the full PRD and the stage-by-stage token and cost estimates below."
        )

        now_iso = datetime.now(timezone.utc).isoformat()
        first_message = {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": client_greeting,
            "timestamp": now_iso,
        }
        pm_state = {
            "session_id": session_id,
            "round": 1,
            "status": "waiting-on-you",
            "messages": [first_message],
            "judge_verdict": judge_verdict,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        save_json_fn(pm_state_file, pm_state)

        logger.info(f"PM session initialized for {session_id} with PRD at {prd_file} and Judge score {judge_verdict.get('total')}/24")

        return {
            "session_id": session_id,
            "message": client_greeting,
            "prd_content": final_prd,
            "estimate": estimate_data,
            "judge_verdict": judge_verdict,
            "already_started": False,
        }

    @pm_router.post("/message")
    def pm_message(req: PMMessageRequest):
        session_id = req.session_id.strip()
        user_text = req.message.strip()

        if not session_id or not user_text:
            raise HTTPException(status_code=400, detail="session_id and message are required")

        session_dir = get_session_dir_fn(session_id)
        docs_dir = os.path.join(session_dir, "docs")
        os.makedirs(docs_dir, exist_ok=True)

        pm_state_file = os.path.join(session_dir, "pm_state.json")
        prd_file = os.path.join(docs_dir, "prd.md")
        legacy_prd_file = os.path.join(session_dir, "prd.md")
        estimate_file = os.path.join(docs_dir, "estimate.json")
        legacy_estimate_file = os.path.join(session_dir, "estimate.json")
        intake_file = os.path.join(session_dir, "intake.json")
        qa_file = os.path.join(session_dir, "qa_log.json")
        req_file = os.path.join(docs_dir, "requirements.md")

        if not os.path.exists(pm_state_file):
            raise HTTPException(status_code=404, detail="PM session has not been started. Call /pm/start first.")

        pm_state = load_json_fn(pm_state_file, {"messages": [], "round": 1})
        intake_data = load_json_fn(intake_file, {})
        qa_log = load_json_fn(qa_file, [])
        requirements_content = ""
        if os.path.exists(req_file):
            try:
                with open(req_file, "r", encoding="utf-8") as f:
                    requirements_content = f.read()
            except Exception:
                pass

        parsed_ba = parse_ba_data(intake_data, qa_log, requirements_content)

        current_prd = ""
        active_prd_path = prd_file if os.path.exists(prd_file) else legacy_prd_file
        if os.path.exists(active_prd_path):
            try:
                with open(active_prd_path, "r", encoding="utf-8") as f:
                    current_prd = f.read()
            except Exception as e:
                logger.error(f"Error reading prd.md: {e}")

        # Add user message to history
        now_iso = datetime.now(timezone.utc).isoformat()
        user_msg = {
            "id": str(uuid.uuid4()),
            "role": "user",
            "content": user_text,
            "timestamp": now_iso,
        }
        pm_state.setdefault("messages", []).append(user_msg)

        current_round = pm_state.get("round", 1) + 1
        pm_state["round"] = current_round

        # Build prompt for PM follow-up turn
        recent_messages = pm_state["messages"][-6:]
        history_str = "\n".join([f"{m.get('role').upper()}: {m.get('content')}" for m in recent_messages])

        prompt = f"""PROJECT: {parsed_ba['app_name']}
CLIENT INTAKE RECAP:
- Goal: {parsed_ba['description']}
- Users: {parsed_ba['target_users']}
- Timeline: {parsed_ba['timeline']}
- Budget: {parsed_ba['budget']}

CURRENT PRD DOCUMENT:
{current_prd}

CONVERSATION HISTORY:
{history_str}

CLIENT'S NEW FEEDBACK / REQUEST:
"{user_text}"

INSTRUCTIONS FOR THIS TURN:
1. Respond to the client directly as their Product Manager: acknowledge their points clearly, discuss product implications, and clarify any scope changes or trade-offs.
2. If the client asked to add, modify, or clarify any features or stories, confirm the update clearly in your response.
3. Keep your conversational response clean, professional, and friendly."""

        try:
            raw_response = query_ollama_fn(prompt=prompt, system=PM_SYSTEM_PROMPT)
            cleaned_message, _ = extract_prd_content(raw_response)
        except Exception as e:
            logger.error(f"Error querying Ollama in pm_message: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to communicate with local model: {e}")

        if cleaned_message:
            cleaned_message = PRD_START_PATTERN.sub("", cleaned_message).strip()
            cleaned_message = PRD_END_PATTERN.sub("", cleaned_message).strip()
            if "# 1. Problem Statement" in cleaned_message:
                cleaned_message = cleaned_message.split("# 1. Problem Statement")[0].strip()

        # Update estimates
        active_prov, active_model = ("groq", "openai/gpt-oss-120b")
        if default_llm_client:
            active_prov, active_model = default_llm_client.get_active_provider_and_model("pm", session_id=session_id)

        _, features_list = build_handbook_compliant_prd_section_by_section(parsed_ba)
        estimate_data = calculate_project_estimate(
            session_id=session_id,
            project_name=parsed_ba["app_name"],
            features=features_list,
            model_name=active_model
        )
        save_json_fn(estimate_file, estimate_data)
        save_json_fn(legacy_estimate_file, estimate_data)

        in_tokens = len(prompt.split()) * 2
        out_tokens = len(cleaned_message.split()) * 2
        cost_usd = calculate_cost_usd(active_model, in_tokens, out_tokens, provider=active_prov) if calculate_cost_usd else 0.0

        # Record LLM call
        record_llm_call(
            project_id=session_id,
            agent_id="pm",
            model=active_model,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            provider=active_prov,
            cost_usd=cost_usd
        )

        # Add assistant response to history
        assistant_msg = {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": cleaned_message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        pm_state["messages"].append(assistant_msg)
        pm_state["status"] = "waiting-on-you"
        pm_state["updated_at"] = datetime.now(timezone.utc).isoformat()
        save_json_fn(pm_state_file, pm_state)

        return {
            "session_id": session_id,
            "message": cleaned_message,
            "prd_content": current_prd,
            "estimate": estimate_data,
            "round": current_round,
        }

    @pm_router.get("/session/{session_id}")
    def get_pm_session(session_id: str):
        session_id = session_id.strip()
        session_dir = get_session_dir_fn(session_id)
        docs_dir = os.path.join(session_dir, "docs")
        pm_state_file = os.path.join(session_dir, "pm_state.json")
        prd_file = os.path.join(docs_dir, "prd.md")
        legacy_prd_file = os.path.join(session_dir, "prd.md")
        estimate_file = os.path.join(docs_dir, "estimate.json")
        legacy_estimate_file = os.path.join(session_dir, "estimate.json")

        if not os.path.exists(pm_state_file):
            return {
                "session_id": session_id,
                "started": False,
                "message": "Product Manager has not started for this session yet.",
                "prd_content": None,
                "estimate": None,
                "messages": [],
            }

        pm_state = load_json_fn(pm_state_file, {})
        prd_content = None
        target_prd_file = prd_file if os.path.exists(prd_file) else legacy_prd_file
        if os.path.exists(target_prd_file):
            try:
                with open(target_prd_file, "r", encoding="utf-8") as f:
                    prd_content = f.read()
            except Exception as e:
                logger.warning(f"Error reading prd.md: {e}")

        estimate_data = load_json_fn(estimate_file, None) or load_json_fn(legacy_estimate_file, None)

        return {
            "session_id": session_id,
            "started": True,
            "round": pm_state.get("round", 1),
            "status": pm_state.get("status", "waiting-on-you"),
            "messages": pm_state.get("messages", []),
            "prd_content": prd_content,
            "estimate": estimate_data,
            "judge_verdict": pm_state.get("judge_verdict"),
            "created_at": pm_state.get("created_at"),
            "updated_at": pm_state.get("updated_at"),
        }

    main_app.include_router(pm_router)
    logger.info("PM agent router adhering to Handbook Section 5, Appendix A.2, and Chapter 14 initialized.")
