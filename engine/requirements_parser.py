"""
Requirements Parser and LLM Extractor
Per Virtual Office Handbook Section 2.7.3 (Step 6), Chapter 3 (Grounding),
Chapter 4 (Business Analyst), Chapter 5 (PM), and Appendix A.1.

Rule: LLM writes, code validates.
- LLM extracts structured requirements JSON from intake.json and qa_log.json.
- Every extracted item must cite its supporting Q-### ID.
- Code strictly validates: schema, Q- existence, substantive answers (no non-answers),
  uniqueness, no chat filler, sentence quality.
- Retry loop (max 3) with fed-back errors; fail loudly if validation cannot pass.
- Code handles ID numbering (P-01, FR-001, NFR-001) and Markdown layout only.
"""

import os
import re
import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Set

try:
    from llm_client import query_llm_with_meta, default_llm_client
except ImportError:
    try:
        from engine.llm_client import query_llm_with_meta, default_llm_client
    except ImportError:
        query_llm_with_meta = None
        default_llm_client = None

logger = logging.getLogger("autonoma-engine.requirements_parser")


NON_ANSWER_PHRASES = {
    "yes", "no", "sure", "ok", "okay", "proceed",
    "yes please proceed", "please proceed", "go ahead",
    "yes lets begin", "lets begin", "sounds good",
    "continue", "looks good", "start", "yes go ahead",
    "yes proceed", "yes start", "yep", "yeah", "agree",
    "ready", "im ready", "i am ready", "let us begin",
    "sounds good please proceed", "yes please", "sure thing",
    "yes please proceed with the prd", "proceed with prd",
    "yes please proceed to the next step"
}


def is_non_answer(text: str) -> bool:
    """Detects conversational non-answers, chat filler, or affirmations without substantive content."""
    clean = re.sub(r"[^\w\s]", "", text.strip()).lower()
    if clean in NON_ANSWER_PHRASES:
        return True
    words = clean.split()
    if len(words) <= 5 and any(w in words for w in ["proceed", "begin", "start", "continue", "ahead", "agree"]):
        return True
    return False


def validate_asm_oq_text(text: str) -> Tuple[bool, str]:
    """
    Validates that an ASM or OQ text row is a single, complete, specific sentence.
    Rejects placeholders (x, y), fragments ('Reason: ...', 'Risk: ...'), and short items (< 30 chars).
    """
    t = text.strip()
    if len(t) < 30:
        return False, f"Too short ({len(t)} characters, minimum 30 required)"

    placeholder_patterns = [
        r"\bis\s+[xyz]\b",
        r"\b[xyz]\s*$",
        r"\[[xyz]\]",
        r"\b(?:tbd|todo|placeholder|dummy)\b",
        r"<[^>]+>",
        r"\{[^\}]+\}"
    ]
    for p in placeholder_patterns:
        if re.search(p, t, re.IGNORECASE):
            return False, f"Contains placeholder matching pattern '{p}'"

    fragment_prefixes = ["reason:", "risk:", "source:", "status:", "note:", "because:", "mitigation:"]
    for fp in fragment_prefixes:
        if t.lower().startswith(fp):
            return False, f"Fragment starting with '{fp}'"

    if not (t.endswith(".") or t.endswith("?") or t.endswith("]")):
        return False, "Not a complete sentence (must end with punctuation)"

    return True, ""


def validate_extracted_requirements_json(
    data: Dict[str, Any],
    qa_map: Dict[str, Dict[str, Any]]
) -> Tuple[bool, List[str]]:
    """
    Strict deterministic code validator for extracted requirements JSON.
    Errors are fed back to the LLM for retry (max 3).
    """
    errors: List[str] = []

    if not isinstance(data, dict):
        return False, ["Root output must be a JSON object"]

    # Shape check first: a string where an object belongs is an error to feed back, not a crash.
    for key in ("personas", "functional_requirements", "non_functional_requirements", "entities", "goals",
                "non_goals", "success_metrics", "assumptions", "open_questions"):
        items = data.get(key, [])
        if not isinstance(items, list):
            errors.append(f"'{key}' must be a list of objects")
            continue
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(f"{key}[{i}] must be an object with named fields, got {type(item).__name__}")
    for key in ("app_overview", "problem"):
        if key in data and not isinstance(data[key], dict):
            errors.append(f"'{key}' must be an object")
    if errors:
        return False, errors

    # 1. Required top-level keys
    req_keys = [
        "app_overview", "problem", "personas", "functional_requirements",
        "non_functional_requirements", "goals", "non_goals", "success_metrics"
    ]
    for rk in req_keys:
        if rk not in data:
            errors.append(f"Missing required top-level key: '{rk}'")

    if errors:
        return False, errors

    # Helper for Q- validation
    def _check_qid(qid: str, field_desc: str):
        if not qid:
            errors.append(f"{field_desc} is missing supporting source Q-### citation")
            return
        clean_qid = qid.strip("[] ")
        if clean_qid not in qa_map:
            errors.append(f"{field_desc} cites non-existent discovery turn '{clean_qid}'")
        else:
            ans = qa_map[clean_qid].get("answer", "")
            if is_non_answer(ans):
                errors.append(f"{field_desc} cites discovery turn '{clean_qid}' which contains a non-answer ('{ans}')")

    # 2. App overview
    overview = data.get("app_overview", {})
    if not isinstance(overview, dict):
        errors.append("app_overview must be a JSON object")
    else:
        for field in ["app_name", "description", "category", "platforms"]:
            val = str(overview.get(field, "")).strip()
            if not val or len(val) < 3:
                errors.append(f"app_overview.{field} must be a non-empty descriptive string")
        _check_qid(overview.get("source_qid", ""), "app_overview")

    # 3. Problem statement
    prob = data.get("problem", {})
    if not isinstance(prob, dict):
        errors.append("problem must be a JSON object")
    else:
        for field in ["today", "core_problem", "shortcomings"]:
            val = str(prob.get(field, "")).strip()
            if not val or len(val) < 25:
                errors.append(f"problem.{field} must be a substantive statement (at least 25 characters)")
            if is_non_answer(val):
                errors.append(f"problem.{field} contains chat filler or a non-answer: '{val}'")
            _check_qid(prob.get(f"{field}_source_qid", "") or prob.get("source_qid", ""), f"problem.{field}")

    # 4. Personas (unique names, valid Q- citations, distinct contexts)
    personas = data.get("personas", [])
    if not isinstance(personas, list) or len(personas) < 1:
        errors.append("personas must be a non-empty array with at least 1 persona")
    else:
        seen_persona_names: Set[str] = set()
        for idx, p in enumerate(personas):
            prefix = f"personas[{idx}]"
            name = str(p.get("name", "")).strip()
            if not name:
                errors.append(f"{prefix}.name is required")
            elif name.lower() in seen_persona_names:
                errors.append(f"Duplicate persona name: '{name}'")
            else:
                seen_persona_names.add(name.lower())

            goal = str(p.get("goal", "")).strip()
            if not goal or len(goal) < 15:
                errors.append(f"{prefix}.goal must be a descriptive sentence")

            pain = str(p.get("pain_point", "")).strip()
            if not pain or len(pain) < 15:
                errors.append(f"{prefix}.pain_point must be a descriptive sentence")

            _check_qid(p.get("source_qid", ""), f"{prefix} ('{name}')")

    # 5. Functional requirements (unique titles, valid priorities, substantive descriptions)
    frs = data.get("functional_requirements", [])
    if not isinstance(frs, list) or len(frs) < 1:
        errors.append("functional_requirements must be a non-empty array")
    else:
        seen_titles: Set[str] = set()
        seen_descs: Set[str] = set()
        for idx, fr in enumerate(frs):
            prefix = f"functional_requirements[{idx}]"
            title = str(fr.get("title", "")).strip()
            if not title:
                errors.append(f"{prefix}.title is required")
            elif title.lower() in seen_titles:
                errors.append(f"Duplicate feature title in FR: '{title}'")
            else:
                seen_titles.add(title.lower())

            desc = str(fr.get("description", "")).strip()
            if not desc or len(desc) < 20:
                errors.append(f"{prefix}.description must be at least 20 characters")
            elif desc.lower() in seen_descs:
                errors.append(f"Duplicate feature description in FR: '{desc[:40]}...'")
            else:
                seen_descs.add(desc.lower())

            priority = str(fr.get("priority", "Must")).strip().capitalize()
            if priority not in {"Must", "Should", "Could", "Wont", "Won't"}:
                errors.append(f"{prefix}.priority must be MoSCoW (Must, Should, Could, or Won't)")

            _check_qid(fr.get("source_qid", ""), f"{prefix} ('{title}')")

    # 6. Non-functional requirements (valid categories, concrete targets)
    nfrs = data.get("non_functional_requirements", [])
    if not isinstance(nfrs, list) or len(nfrs) < 2:
        errors.append("non_functional_requirements must contain at least 2 constraints")
    else:
        for idx, nfr in enumerate(nfrs):
            prefix = f"non_functional_requirements[{idx}]"
            cat = str(nfr.get("category", "")).strip()
            target = str(nfr.get("target", "")).strip()
            if not cat or not target:
                errors.append(f"{prefix} must include both 'category' and 'target'")
            _check_qid(nfr.get("source_qid", ""), f"{prefix} ('{cat}')")

    # 7. Goals and Non-Goals
    goals = data.get("goals", [])
    if not isinstance(goals, list) or len(goals) < 1:
        errors.append("goals must be an array with at least 1 goal")
    else:
        for idx, g in enumerate(goals):
            prefix = f"goals[{idx}]"
            if not str(g.get("goal", "")).strip():
                errors.append(f"{prefix}.goal is required")
            _check_qid(g.get("source_qid", ""), prefix)

    non_goals = data.get("non_goals", [])
    if not isinstance(non_goals, list) or len(non_goals) < 1:
        errors.append("non_goals must be an array with at least 1 non-goal (required to prevent scope creep per Handbook 5.2.4)")
    else:
        seen_ng: Set[str] = set()
        for idx, ng in enumerate(non_goals):
            prefix = f"non_goals[{idx}]"
            ng_text = str(ng.get("non_goal", "")).strip()
            if not ng_text:
                errors.append(f"{prefix}.non_goal is required")
            elif ng_text.lower() in seen_ng:
                errors.append(f"Duplicate non-goal: '{ng_text}'")
            else:
                seen_ng.add(ng_text.lower())

            if not str(ng.get("why", "")).strip():
                errors.append(f"{prefix}.why is required (reason why deferred)")
            _check_qid(ng.get("source_qid", ""), prefix)

    # 8. Success metrics
    metrics = data.get("success_metrics", [])
    if not isinstance(metrics, list) or len(metrics) < 1:
        errors.append("success_metrics must be an array with at least 1 metric")
    else:
        seen_metrics: Set[str] = set()
        for idx, m in enumerate(metrics):
            prefix = f"success_metrics[{idx}]"
            m_name = str(m.get("metric", "")).strip()
            if not m_name:
                errors.append(f"{prefix}.metric is required")
            elif m_name.lower() in seen_metrics:
                errors.append(f"Duplicate metric name: '{m_name}'")
            else:
                seen_metrics.add(m_name.lower())

            if not str(m.get("target", "")).strip():
                errors.append(f"{prefix}.target is required")
            if not str(m.get("how_measured", "")).strip():
                errors.append(f"{prefix}.how_measured is required")
            _check_qid(m.get("source_qid", ""), prefix)

    # 9. Assumptions and Open Questions sentence checks
    for idx, asm in enumerate(data.get("assumptions", [])):
        txt = str(asm.get("text", "")).strip()
        is_val, err_msg = validate_asm_oq_text(txt)
        if not is_val:
            errors.append(f"assumptions[{idx}] text invalid: {err_msg}")

    for idx, oq in enumerate(data.get("open_questions", [])):
        txt = str(oq.get("text", "")).strip()
        is_val, err_msg = validate_asm_oq_text(txt)
        if not is_val:
            errors.append(f"open_questions[{idx}] text invalid: {err_msg}")

    return len(errors) == 0, errors


def extract_requirements_with_llm(
    intake_data: Dict[str, Any],
    qa_log: List[Dict[str, Any]],
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    LLM extraction step:
    Extracts structured requirements JSON from intake.json and qa_log.json.
    Validates strictly with code validator.
    Retries up to 3 times feeding back errors.
    Fails loudly if invalid (NO CANNED FALLBACK).
    """
    if not query_llm_with_meta:
        raise RuntimeError("LLM client query_llm_with_meta is unavailable")

    qa_map: Dict[str, Dict[str, Any]] = {}
    for idx, item in enumerate(qa_log):
        qid = item.get("id") or f"Q-{idx+1:03d}"
        qa_map[qid] = {
            "id": qid,
            "question": item.get("question", "").strip(),
            "answer": item.get("answer", "").strip(),
        }

    system_prompt = (
        "You are the Virtual Office Lead Business Analyst. "
        "Your task is to analyze the client intake and full interview Q&A log, "
        "and extract a complete, grounded, structured requirements JSON document. "
        "CRITICAL RULES (Handbook Chapter 3 & 4):\n"
        "1. Every extracted item MUST cite its exact supporting source Q-### ID.\n"
        "2. NEVER cite a turn where the client gave a non-answer (e.g. 'Yes, please proceed').\n"
        "3. Problem fields ('today', 'core_problem', 'shortcomings') must be substantive sentences describing the real domain workflow.\n"
        "4. Feature titles and descriptions must be unique and specific to this project.\n"
        "5. Separate FRs (user actions and workflows) from NFRs (latency, offline, platform, privacy, accessibility).\n"
        "6. Return ONLY valid JSON with no markdown wrapping or preamble."
    )

    template: Dict[str, Any] = {
        "app_overview": {"app_name": "Project Name", "description": "One-line description",
                         "category": "Domain Category", "platforms": "Target Platforms / Offline Desktop",
                         "source_qid": "Q-001"},
        "problem": {"today": "What users do today and their workarounds", "today_source_qid": "Q-001",
                    "core_problem": "The single biggest pain and consequence", "core_problem_source_qid": "Q-002",
                    "shortcomings": "Why existing tools fall short", "shortcomings_source_qid": "Q-002"},
        "personas": [{"name": "Persona Role Title", "context": "Context of operations", "goal": "Primary operational goal",
                      "pain_point": "Biggest pain point", "source_qid": "Q-001"}],
        "functional_requirements": [{"title": "Clear Feature Title", "description": "Substantive feature description",
                                     "priority": "Must", "source_qid": "Q-003"}],
        "non_functional_requirements": [{"category": "Latency / Storage / Platform / Accessibility",
                                         "target": "Verifiable target metric", "source_qid": "Q-004"}],
        "entities": [{"name": "Entity Name", "description": "What it represents", "source_qid": "Q-003"}],
        "goals": [{"goal": "Verifiable MVP Goal", "source_qid": "Q-001"}],
        "non_goals": [{"non_goal": "Explicitly deferred capability", "why": "Reason why deferred to v2",
                       "source_qid": "Q-002"}],
        "success_metrics": [{"metric": "Metric Name", "target": "Measurable threshold",
                             "how_measured": "Query or audit check", "source_qid": "Q-001"}],
        "assumptions": [{"text": "Specific assumption sentence pending client confirmation at Gate 1.",
                         "status": "awaiting client at Gate 1"}],
        "open_questions": [{"text": "Specific open question sent to client via BA.", "to": "client"}],
    }
    # Extracted in parts so each reply stays well under provider output caps (e.g. 1,000 output
    # tokens per minute on Groq's free tier); the merged document is validated as a whole.
    chunks = [
        ["app_overview", "problem", "personas"],
        ["functional_requirements", "non_functional_requirements", "entities"],
        ["goals", "non_goals", "success_metrics", "assumptions", "open_questions"],
    ]
    context_block = f"""CLIENT INTAKE:
{json.dumps(intake_data, indent=2)}

DISCOVERY Q&A LOG:
{json.dumps(qa_log, indent=2)}
"""

    def _parse(raw: str) -> Dict[str, Any]:
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\n", "", text)
            text = re.sub(r"\n```$", "", text).strip()
        return json.loads(text)

    max_attempts = 3
    last_errors: List[str] = []
    feedback = ""
    for attempt in range(1, max_attempts + 1):
        logger.info(f"Extracting requirements with LLM (attempt {attempt}/{max_attempts})...")
        extracted_json: Dict[str, Any] = {}
        parse_errors: List[str] = []
        for part, keys in enumerate(chunks, 1):
            subset = {k: template[k] for k in keys}
            prompt = (f"{context_block}\nOutput a valid JSON object with exactly these keys, matching this structure "
                      f"(part {part} of {len(chunks)} of the requirements document; keep sentences short):\n"
                      f"{json.dumps(subset, indent=2)}" + (f"\n\n{feedback}" if feedback else ""))
            raw_text, meta = query_llm_with_meta(
                prompt=prompt,
                system=system_prompt,
                role="ba",
                session_id=session_id,
                task_id=f"extract_requirements_json_p{part}",
                max_tokens=1000,
            )
            try:
                part_json = _parse(raw_text)
            except Exception as e:
                cut = " (reply was cut off at the output token limit; be more concise)" if meta.get("stop") == "max_tokens" else ""
                parse_errors.append(f"part {part} ({', '.join(keys)}): JSON parse error: {e}{cut}")
                continue
            for k in keys:
                if k in part_json:
                    extracted_json[k] = part_json[k]
                else:
                    parse_errors.append(f"part {part}: missing key '{k}'")
        if parse_errors:
            last_errors = parse_errors
            feedback = (f"ERRORS ON ATTEMPT {attempt}:\n" + "\n".join(f"- {e}" for e in parse_errors) +
                        "\nReturn ONLY a strictly valid JSON object.")
            continue

        is_valid, errors = validate_extracted_requirements_json(extracted_json, qa_map)
        if is_valid:
            logger.info(f"Requirements LLM extraction passed code validation on attempt {attempt}.")
            return extracted_json

        logger.warning(f"Requirements extraction failed validation on attempt {attempt}: {errors}")
        last_errors = errors
        feedback = (f"ERRORS ON ATTEMPT {attempt} (whole document):\n" + "\n".join(f"- {err}" for err in errors) +
                    "\nFix every error that concerns the keys of this part and return the corrected JSON object.")

    # Fail loudly - NO canned fallback
    raise ValueError(
        f"Requirements LLM extraction failed validation after {max_attempts} attempts. "
        f"Errors: {json.dumps(last_errors, indent=2)}"
    )


def format_requirements_markdown(extracted: Dict[str, Any], qa_map: Dict[str, Any]) -> str:
    """
    Renders the verified extracted data into Appendix A.1 Markdown format.
    Assigns sequential standard IDs (P-01, FR-001, NFR-001, G-01, NG-01, M-01, ASM-01, OQ-01).
    Code handles formatting and ID numbering only.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    now_human = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    stamp = (
        f"<!-- ARTIFACT METADATA: Assembled by code at {now_iso} -->\n"
        f"> **Artifact Provenance**: Assembled by code | "
        f"Role: **Business Analyst** | Timestamp: `{now_human}`\n\n"
    )

    overview = extracted.get("app_overview", {})
    prob = extracted.get("problem", {})
    app_name = overview.get("app_name", "Untitled Project")

    md = f"{stamp}# Requirements Document: {app_name}\n\n"

    # 1. Problem Statement
    today_src = prob.get("today_source_qid", overview.get("source_qid", "Q-001"))
    prob_src = prob.get("core_problem_source_qid", today_src)
    short_src = prob.get("shortcomings_source_qid", prob_src)

    md += "## 1. Problem Statement\n"
    md += f"- **Today**: {prob.get('today', '')} [{today_src}]\n"
    md += f"- **Core Problem**: {prob.get('core_problem', '')} [{prob_src}]\n"
    md += f"- **Why Existing Tools Fall Short**: {prob.get('shortcomings', '')} [{short_src}]\n\n"

    # 2. Personas
    md += "## 2. Personas\n"
    for idx, p in enumerate(extracted.get("personas", []), start=1):
        pid = f"P-{idx:02d}"
        md += f"- **{pid}**: {p.get('name', 'Operator')} - Goal: {p.get('goal', '')} | Pain: {p.get('pain_point', '')} [{p.get('source_qid', 'Q-001')}]\n"
    md += "\n"

    # 3. Functional Requirements
    md += "## 3. Functional Requirements\n"
    for idx, fr in enumerate(extracted.get("functional_requirements", []), start=1):
        fid = f"FR-{idx:03d}"
        prio = fr.get("priority", "Must").capitalize()
        md += f"- **{fid}**: {fr.get('title', '')} ({prio}) - {fr.get('description', '')} [{fr.get('source_qid', 'Q-001')}]\n"
    md += "\n"

    # 4. Non-Functional Requirements
    md += "## 4. Non-Functional Requirements\n"
    for idx, nfr in enumerate(extracted.get("non_functional_requirements", []), start=1):
        nid = f"NFR-{idx:02d}"
        md += f"- **{nid}**: {nfr.get('category', '')} - Target: {nfr.get('target', '')} [{nfr.get('source_qid', 'Q-001')}]\n"
    md += "\n"

    # 5. Goals & Non-Goals
    md += "## 5. Goals & Non-Goals\n"
    md += "### Goals (v1 MVP)\n"
    for idx, g in enumerate(extracted.get("goals", []), start=1):
        gid = f"G-{idx:02d}"
        md += f"- **{gid}**: {g.get('goal', '')} [{g.get('source_qid', 'Q-001')}]\n"
    md += "\n### Non-Goals (Out of Scope for v1)\n"
    for idx, ng in enumerate(extracted.get("non_goals", []), start=1):
        ngid = f"NG-{idx:02d}"
        md += f"- **{ngid}**: {ng.get('non_goal', '')} - Why: {ng.get('why', '')} [{ng.get('source_qid', 'Q-001')}]\n"
    md += "\n"

    # 6. Success Metrics
    md += "## 6. Success Metrics\n"
    for idx, m in enumerate(extracted.get("success_metrics", []), start=1):
        mid = f"M-{idx:02d}"
        md += f"- **{mid}**: {m.get('metric', '')} - Target: {m.get('target', '')} (Measured by: {m.get('how_measured', '')}) [{m.get('source_qid', 'Q-001')}]\n"
    md += "\n"

    # 7. Assumptions & Open Questions
    assumptions = extracted.get("assumptions", [])
    if assumptions:
        md += "## 7. Assumptions\n"
        for idx, asm in enumerate(assumptions, start=1):
            asmid = f"ASM-{idx:02d}"
            md += f"- **{asmid}**: {asm.get('text', '')} ({asm.get('status', 'awaiting client at Gate 1')})\n"
        md += "\n"

    open_questions = extracted.get("open_questions", [])
    if open_questions:
        md += "## 8. Open Questions\n"
        for idx, oq in enumerate(open_questions, start=1):
            oqid = f"OQ-{idx:02d}"
            md += f"- **{oqid}**: {oq.get('text', '')} (to: {oq.get('to', 'client')})\n"
        md += "\n"

    return md


PROJECTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "projects")


def load_or_extract_requirements(intake_data: Dict[str, Any], qa_log: List[Dict[str, Any]],
                                 session_id: Optional[str]) -> Dict[str, Any]:
    """
    One validated extraction per project, reused by every later stage (PM, feasibility, Architect,
    Designer) so all of them see the same FR-/NFR- IDs. Re-extracted only when the intake or the
    Q&A log changes (content hash).
    """
    digest = hashlib.sha256(json.dumps({"intake": intake_data, "qa": qa_log}, sort_keys=True,
                                       default=str).encode()).hexdigest()
    cache = os.path.join(PROJECTS_DIR, session_id, "requirements_extraction.json") if session_id else None
    if cache and os.path.exists(cache):
        try:
            with open(cache, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if saved.get("source_sha256") == digest and isinstance(saved.get("extraction"), dict):
                return saved["extraction"]
        except (OSError, ValueError):
            pass
    extracted = extract_requirements_with_llm(intake_data, qa_log, session_id=session_id)
    if cache and os.path.isdir(os.path.dirname(cache)):
        with open(cache, "w", encoding="utf-8") as f:
            json.dump({"source_sha256": digest, "extracted_at": datetime.now(timezone.utc).isoformat(),
                       "extraction": extracted}, f, indent=2)
    return extracted


def parse_ba_data(
    intake_data: Dict[str, Any],
    qa_log: List[Dict[str, Any]],
    requirements_text: str = "",
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Entry point for downstream PM, Architect, and Designer agents.
    Uses LLM extraction validated by code.
    No regex heuristics, zero canned fallbacks.
    """
    extracted = load_or_extract_requirements(intake_data, qa_log, session_id)

    qa_map: Dict[str, Dict[str, Any]] = {}
    for idx, item in enumerate(qa_log):
        qid = item.get("id") or f"Q-{idx+1:03d}"
        qa_map[qid] = {
            "id": qid,
            "question": item.get("question", "").strip(),
            "answer": item.get("answer", "").strip(),
        }

    first_qid = list(qa_map.keys())[0] if qa_map else "Q-001"
    overview = extracted.get("app_overview", {})
    prob = extracted.get("problem", {})

    app_name = overview.get("app_name", intake_data.get("project_name", "Untitled Project"))
    description = overview.get("description", intake_data.get("description", ""))
    category = overview.get("category", "")
    platforms = overview.get("platforms", "")

    today_qid = prob.get("today_source_qid", first_qid)
    problem_qid = prob.get("core_problem_source_qid", first_qid)
    shortcomings_qid = prob.get("shortcomings_source_qid", first_qid)

    today_text = prob.get("today", "")
    problem_text = prob.get("core_problem", "")
    shortcomings_text = prob.get("shortcomings", "")

    # Personas
    personas = []
    for idx, p in enumerate(extracted.get("personas", []), start=1):
        personas.append({
            "id": f"P-{idx:02d}",
            "persona": p.get("name", "User"),
            "context": p.get("context", f"Operations in {app_name}"),
            "goal": p.get("goal", ""),
            "pain_point": p.get("pain_point", ""),
            "does": p.get("does", f"Execute operational workflows in {app_name}"),
            "can": "Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1",
            "cannot": "Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1",
            "source": p.get("source_qid", first_qid)
        })

    # Functional Requirements
    discovered_features = []
    for idx, fr in enumerate(extracted.get("functional_requirements", []), start=1):
        fid = f"FR-{idx:03d}"
        discovered_features.append({
            "id": fid,
            "feature": fr.get("title", ""),
            "description": fr.get("description", ""),
            "priority": fr.get("priority", "Must").capitalize(),
            "source": fr.get("source_qid", first_qid),
            "raw": fr.get("title", "")
        })

    # Non-functional requirements
    final_nfrs = []
    for idx, nfr in enumerate(extracted.get("non_functional_requirements", []), start=1):
        nid = f"NFR-{idx:02d}"
        final_nfrs.append({
            "id": nid,
            "nfr": nfr.get("category", ""),
            "target": nfr.get("target", ""),
            "source": f"[{nfr.get('source_qid', first_qid)}]"
        })

    # Goals and Non-goals
    discovered_goals = []
    for idx, g in enumerate(extracted.get("goals", []), start=1):
        discovered_goals.append({
            "id": f"G-{idx:02d}",
            "goal": g.get("goal", ""),
            "source": g.get("source_qid", first_qid)
        })

    discovered_non_goals = []
    for idx, ng in enumerate(extracted.get("non_goals", []), start=1):
        discovered_non_goals.append({
            "id": f"NG-{idx:02d}",
            "non_goal": ng.get("non_goal", ""),
            "why": ng.get("why", ""),
            "source": ng.get("source_qid", first_qid)
        })

    # Metrics
    discovered_metrics = []
    for idx, m in enumerate(extracted.get("success_metrics", []), start=1):
        discovered_metrics.append({
            "id": f"M-{idx:02d}",
            "metric": m.get("metric", ""),
            "target": m.get("target", ""),
            "measurement": m.get("how_measured", ""),
            "source": m.get("source_qid", first_qid)
        })

    # Assumptions
    assumptions = []
    for idx, asm in enumerate(extracted.get("assumptions", []), start=1):
        assumptions.append({
            "id": f"ASM-{idx:02d}",
            "text": asm.get("text", ""),
            "status": asm.get("status", "awaiting client at Gate 1")
        })

    # Open Questions
    open_questions = []
    for idx, oq in enumerate(extracted.get("open_questions", []), start=1):
        open_questions.append({
            "id": f"OQ-{idx:02d}",
            "text": oq.get("text", ""),
            "to": oq.get("to", "client"),
            "status": "sent via BA"
        })

    return {
        "app_name": app_name,
        "description": description,
        "category": category,
        "platforms": platforms,
        "first_qid": first_qid,
        "today_qid": today_qid,
        "problem_qid": problem_qid,
        "shortcomings_qid": shortcomings_qid,
        "today_text": today_text,
        "problem_text": problem_text,
        "shortcomings_text": shortcomings_text,
        "personas": personas,
        "discovered_features": discovered_features,
        "functional_reqs": discovered_features,
        "non_functional_reqs": final_nfrs,
        "discovered_goals": discovered_goals,
        "discovered_non_goals": discovered_non_goals,
        "discovered_metrics": discovered_metrics,
        "assumptions": assumptions,
        "open_questions": open_questions,
        "qa_map": qa_map,
        "intake": intake_data,
        "timeline": intake_data.get("timeline", ""),
        "budget": intake_data.get("budget", ""),
        "extracted_raw": extracted
    }


def render_requirements_markdown(parsed_ba: Dict[str, Any], intake_data: Dict[str, Any]) -> str:
    """
    requirements.md rendered by code from the BA's validated extraction (Appendix A.1), so the
    BA document, the PRD and every later citation share ONE set of IDs (FR-, NFR-, P-, ASM-, OQ-).
    """
    def src(q: str) -> str:
        q = str(q or parsed_ba.get("first_qid", "Q-001")).strip("[]")
        return f"[{q}]"

    lines = [f"# Requirements: {parsed_ba.get('app_name', intake_data.get('project_name', ''))}", "",
             "<!-- Rendered by code from the Business Analyst's validated requirements extraction; "
             "IDs here are the IDs every later document cites. -->", "",
             "## 1. Problem", "",
             f"- Today: {parsed_ba.get('today_text', '')} {src(parsed_ba.get('today_qid'))}",
             f"- Core problem: {parsed_ba.get('problem_text', '')} {src(parsed_ba.get('problem_qid'))}",
             f"- Why existing tools fall short: {parsed_ba.get('shortcomings_text', '')} {src(parsed_ba.get('shortcomings_qid'))}",
             "", "## 2. Personas", "", "| ID | Who | Context | Goal | Source |", "|---|---|---|---|---|"]
    lines += [f"| {p['id']} | {p.get('persona', '')} | {p.get('context', '')} | {p.get('goal', '')} | {src(p.get('source'))} |"
              for p in parsed_ba.get("personas", [])]
    lines += ["", "## 3. Functional requirements", "",
              "Format: - FR-###: <requirement> (<MoSCoW> Have) [Source: Q-###]", ""]
    for fr in parsed_ba.get("functional_reqs", []):
        desc = f" — {fr['description']}" if fr.get("description") else ""
        lines.append(f"- {fr['id']}: {fr.get('feature', '')}{desc} ({fr.get('priority', 'Must')} Have) "
                     f"[Source: {str(fr.get('source', '')).strip('[]')}]")
    lines += ["", "## 4. Non-functional requirements", "", "| ID | Category | Requirement | Source |", "|---|---|---|---|"]
    lines += [f"| {n['id']} | {n.get('nfr', '')} | {n.get('target', '')} | {n.get('source', '')} |"
              for n in parsed_ba.get("non_functional_reqs", [])]
    entities = (parsed_ba.get("extracted_raw") or {}).get("entities", [])
    lines += ["", "## 5. Data", "", "| What | Description | Source |", "|---|---|---|"]
    lines += [f"| {e.get('name', '')} | {e.get('description', '')} | {src(e.get('source_qid'))} |" for e in entities] or ["| - | - | - |"]
    lines += ["", "## 6. Constraints", "",
              f"- Timeline: {intake_data.get('timeline', '')} (intake)",
              f"- Budget: {intake_data.get('budget', '')} (intake)",
              "", "## 7. Goals and success", ""]
    lines += [f"- {g['id']}: {g.get('goal', '')} {src(g.get('source'))}" for g in parsed_ba.get("discovered_goals", [])]
    lines += [f"- {m['id']}: {m.get('metric', '')} — target {m.get('target', '')}; measured by {m.get('measurement', '')} "
              f"{src(m.get('source'))}" for m in parsed_ba.get("discovered_metrics", [])]
    lines += ["", "## 8. Won't (v1)", "", "| ID | Item | Reason | Source |", "|---|---|---|---|"]
    lines += [f"| {n['id']} | {n.get('non_goal', '')} | {n.get('why', '')} | {src(n.get('source'))} |"
              for n in parsed_ba.get("discovered_non_goals", [])] or ["| - | - | - | - |"]
    lines += ["", "## 9. Assumptions and open questions", "", "| ID | Type | Text | Status |", "|---|---|---|---|"]
    lines += [f"| {a['id']} | assumption | {a.get('text', '')} | {a.get('status', '')} |" for a in parsed_ba.get("assumptions", [])]
    lines += [f"| {q['id']} | open question | {q.get('text', '')} | {q.get('status', '')} |" for q in parsed_ba.get("open_questions", [])]
    return "\n".join(lines) + "\n"


def parse_prd_data(prd_text: str) -> Dict[str, Any]:
    """
    Parses an existing docs/prd.md document into structured sections.
    Used by downstream Architect and Designer validators.
    """
    app_name = "Untitled Project"
    app_name_m = re.search(r"#\s*Product Requirement Document\s*(?:\(PRD\))?:\s*([^\n]+)", prd_text, re.IGNORECASE)
    if app_name_m:
        app_name = app_name_m.group(1).strip()

    description = ""
    category = ""
    platforms = ""
    desc_m = re.search(r"\|\s*One-line description\s*\|\s*([^|]+)\s*\|", prd_text, re.IGNORECASE)
    if desc_m:
        description = desc_m.group(1).strip()
    cat_m = re.search(r"\|\s*Category\s*\|\s*([^|]+)\s*\|", prd_text, re.IGNORECASE)
    if cat_m:
        category = cat_m.group(1).strip()
    plat_m = re.search(r"\|\s*Platforms\s*\|\s*([^|]+)\s*\|", prd_text, re.IGNORECASE)
    if plat_m:
        platforms = plat_m.group(1).strip()

    # Personas
    personas = []
    p_rows = re.findall(r"\|\s*(P-\d+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*\[([^\]]+)\]\s*\|", prd_text)
    for p_id, p_name, p_ctx, p_goal, p_pain, p_src in p_rows:
        personas.append({
            "id": p_id.strip(),
            "persona": p_name.strip(),
            "context": p_ctx.strip(),
            "goal": p_goal.strip(),
            "pain_point": p_pain.strip(),
            "source": f"[{p_src.strip()}]"
        })

    # Goals, Non-goals, Metrics
    goals = []
    for g_id, g_text, g_src in re.findall(r"\|\s*(G-\d+)\s*\|\s*([^|]+)\s*\|\s*\[([^\]]+)\]\s*\|", prd_text):
        goals.append({"id": g_id.strip(), "goal": g_text.strip(), "source": f"[{g_src.strip()}]"})

    non_goals = []
    for ng_id, ng_text, ng_why, ng_src in re.findall(r"\|\s*(NG-\d+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*\[([^\]]+)\]\s*\|", prd_text):
        non_goals.append({"id": ng_id.strip(), "non_goal": ng_text.strip(), "why": ng_why.strip(), "source": f"[{ng_src.strip()}]"})

    metrics = []
    for m_id, m_name, m_tgt, m_meas, m_src in re.findall(r"\|\s*(M-\d+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*\[([^\]]+)\]\s*\|", prd_text):
        metrics.append({"id": m_id.strip(), "metric": m_name.strip(), "target": m_tgt.strip(), "measurement": m_meas.strip(), "source": f"[{m_src.strip()}]"})

    # Features
    features = []
    f_blocks = re.split(r"(?=###\s*Feature\s+F-\d+:|###\s*F-\d+:)", prd_text)
    for block in f_blocks:
        hdr_match = re.search(r"###\s*(?:Feature\s+)?(F-\d+):\s*(.+)", block)
        if not hdr_match:
            continue
        fid = hdr_match.group(1).strip()
        ftitle = hdr_match.group(2).strip()

        story_m = re.search(r"-\s*\*\*Story\*\*:\s*([^\n]+)", block)
        if not story_m:
            story_m = re.search(r"Story:\s*([^\n]+)", block)
        story = story_m.group(1).strip() if story_m else ""

        prio_m = re.search(r"-\s*\*\*Priority\*\*:\s*([^\n]+)", block)
        if not prio_m:
            prio_m = re.search(r"Priority:\s*([^\n]+)", block)
        priority = prio_m.group(1).strip() if prio_m else "Must"

        req_m = re.search(r"-\s*\*\*Requirements\*\*:\s*([^\n]+)", block)
        if not req_m:
            req_m = re.search(r"Requirements:\s*([^\n]+)", block)
        reqs = req_m.group(1).strip() if req_m else ""

        acs = []
        ac_rows = re.findall(r"\|\s*(AC-\d+)\s*\|\s*([^|]+)\s*\|", block)
        for ac_id, ac_text in ac_rows:
            acs.append({
                "id": ac_id.strip(),
                "text": ac_text.strip(),
                "is_unhappy": "(unhappy path)" in ac_text.lower()
            })

        features.append({
            "id": fid,
            "title": ftitle,
            "story": story,
            "priority": priority,
            "requirements": reqs,
            "acs": acs
        })

    # NFRs
    nfrs = []
    nfr_rows = re.findall(r"\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*\[(NFR-\d+)\]\s*\|", prd_text)
    for nfr_name, nfr_target, nfr_src in nfr_rows:
        if "NFR" in nfr_name and "Target" in nfr_target:
            continue
        nfrs.append({
            "id": nfr_src.strip(),
            "name": nfr_name.strip(),
            "target": nfr_target.strip(),
            "source": f"[{nfr_src.strip()}]"
        })

    # Risks
    risks = []
    r_rows = re.findall(r"\|\s*(R-\d+)\s*\|\s*([^|]+)\s*\|\s*([LMH])\s*\|\s*([LMH])\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|", prd_text)
    for r_id, r_name, r_like, r_imp, r_mit, r_owner in r_rows:
        risks.append({
            "id": r_id.strip(),
            "risk": r_name.strip(),
            "likelihood": r_like.strip(),
            "impact": r_imp.strip(),
            "mitigation": r_mit.strip(),
            "owner": r_owner.strip()
        })

    # Assumptions & Open Questions
    assumptions = []
    for asm_id, asm_text, asm_st in re.findall(r"\|\s*(ASM-\d+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|", prd_text):
        assumptions.append({"id": asm_id.strip(), "text": asm_text.strip(), "status": asm_st.strip()})

    open_questions = []
    for oq_id, oq_text, oq_st in re.findall(r"\|\s*(OQ-\d+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|", prd_text):
        open_questions.append({"id": oq_id.strip(), "text": oq_text.strip(), "status": oq_st.strip()})

    return {
        "app_name": app_name,
        "description": description,
        "category": category,
        "platforms": platforms,
        "personas": personas,
        "goals": goals,
        "non_goals": non_goals,
        "metrics": metrics,
        "features": features,
        "nfrs": nfrs,
        "risks": risks,
        "assumptions": assumptions,
        "open_questions": open_questions
    }
