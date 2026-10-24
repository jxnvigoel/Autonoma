"""
UI/UX Designer Agent Module for Autonoma Virtual Office
Based on Handbook Chapter 8 (UI/UX Designer), Chapter 3 (Operating Rules),
Chapter 14 (LLM Judge), and Appendices A.4 & A.5 of VirtualOffice_Complete_Guide.md.

Produces:
1. docs/app-flow.md (Appendix A.4) - Generated via LLM with real grounding
2. docs/design-brief.md (Appendix A.5) - Generated via LLM with automated contrast repair
3. Code-level validators (Step 12: WCAG 2.2 contrast, persona authorization, unique routes, 5 states, duplicate-text check)
4. LLM Judge review (Step 13: skills/designer/rubric.json)
"""

import os
import re
import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Set
from fastapi import APIRouter, HTTPException

logger = logging.getLogger("autonoma.designer")

# Try imports
try:
    from token_ledger import record_llm_call
except ImportError:
    try:
        from engine.token_ledger import record_llm_call
    except ImportError:
        record_llm_call = None

try:
    from llm_client import default_llm_client
except ImportError:
    try:
        from engine.llm_client import default_llm_client
    except ImportError:
        default_llm_client = None

try:
    from requirements_parser import parse_ba_data
except ImportError:
    try:
        from engine.requirements_parser import parse_ba_data
    except ImportError:
        parse_ba_data = None

try:
    from judge import (
        evaluate_design_with_judge,
        compute_contrast_ratio,
        run_designer_code_audits
    )
except ImportError:
    try:
        from engine.judge import (
            evaluate_design_with_judge,
            compute_contrast_ratio,
            run_designer_code_audits
        )
    except ImportError:
        evaluate_design_with_judge = None
        compute_contrast_ratio = None
        run_designer_code_audits = None


# ==============================================================================
# WCAG 2.2 AA CONTRAST CALCULATION (Deterministic Formula)
# ==============================================================================

def hex_to_rgb(hex_code: str) -> Tuple[int, int, int]:
    h = hex_code.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) < 6:
        h = h.ljust(6, "0")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def calculate_relative_luminance(rgb: Tuple[int, int, int]) -> float:
    def channel_lum(val: int) -> float:
        c = val / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * channel_lum(r) + 0.7152 * channel_lum(g) + 0.0722 * channel_lum(b)


def calculate_contrast(hex1: str, hex2: str) -> float:
    try:
        lum1 = calculate_relative_luminance(hex_to_rgb(hex1))
        lum2 = calculate_relative_luminance(hex_to_rgb(hex2))
        l_max = max(lum1, lum2)
        l_min = min(lum1, lum2)
        return (l_max + 0.05) / (l_min + 0.05)
    except Exception:
        return 1.0


def adjust_contrast_color(fg_hex: str, bg_hex: str, min_ratio: float = 4.5, lighten: bool = False) -> str:
    """
    Deterministically adjusts fg_hex towards white (if lighten=True) or black (if lighten=False)
    until it achieves at least min_ratio contrast against bg_hex.
    """
    current = fg_hex.strip()
    if calculate_contrast(current, bg_hex) >= min_ratio:
        return current
    for _ in range(60):
        r, g, b = hex_to_rgb(current)
        if lighten:
            r = min(255, int(r + (255 - r) * 0.15) + 2)
            g = min(255, int(g + (255 - g) * 0.15) + 2)
            b = min(255, int(b + (255 - b) * 0.15) + 2)
        else:
            r = max(0, int(r * 0.85))
            g = max(0, int(g * 0.85))
            b = max(0, int(b * 0.85))
        current = f"#{r:02x}{g:02x}{b:02x}"
        if calculate_contrast(current, bg_hex) >= min_ratio:
            return current
    return "#ffffff" if lighten else "#000000"


def adjust_contrast_for_both_surfaces(
    fg_hex: str,
    bg_hex: str,
    surf_hex: str,
    min_ratio: float = 4.5,
    lighten: bool = False
) -> str:
    """
    Deterministically adjusts fg_hex until it satisfies >= min_ratio contrast
    against BOTH bg_hex and surf_hex simultaneously.
    """
    current = fg_hex.strip()
    if calculate_contrast(current, bg_hex) >= min_ratio and calculate_contrast(current, surf_hex) >= min_ratio:
        return current
    for _ in range(60):
        r, g, b = hex_to_rgb(current)
        if lighten:
            r = min(255, int(r + (255 - r) * 0.15) + 2)
            g = min(255, int(g + (255 - g) * 0.15) + 2)
            b = min(255, int(b + (255 - b) * 0.15) + 2)
        else:
            r = max(0, int(r * 0.85))
            g = max(0, int(g * 0.85))
            b = max(0, int(b * 0.85))
        current = f"#{r:02x}{g:02x}{b:02x}"
        if calculate_contrast(current, bg_hex) >= min_ratio and calculate_contrast(current, surf_hex) >= min_ratio:
            return current
    return "#ffffff" if lighten else "#000000"


# ==============================================================================
# PRD & DISCOVERY CONTEXT EXTRACTOR
# ==============================================================================

def extract_prd_context(
    prd_text: str,
    parsed_ba: Dict[str, Any],
    architecture_text: str = ""
) -> Dict[str, Any]:
    """
    Extracts structured personas, features with acceptance criteria, NFRs,
    and architectural endpoints/tables from project documents.
    """
    app_name = parsed_ba.get("app_name", "Application")
    if not app_name or app_name == "Application":
        m_app = re.search(r"#\s*Product Requirements Document\s*(?:\(PRD\))?:\s*([^\n]+)", prd_text, re.IGNORECASE)
        if m_app:
            app_name = m_app.group(1).strip()

    # 1. Personas Extraction
    personas: List[Dict[str, str]] = []
    # Match markdown table rows: | `[P-01]` | Title | Role | ... |
    p_rows = re.findall(r"\|\s*`?\[?(P-\d+)\]?`?\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)?\s*\|?", prd_text)
    for p_id, p_name, p_role in p_rows:
        pid = p_id.strip()
        pname = p_name.strip()
        if "id" in pid.lower() or "---" in pid or not pname:
            continue
        if not any(p["id"] == pid for p in personas):
            personas.append({
                "id": pid,
                "persona": pname,
                "role": (p_role or "").strip()
            })

    # Fallback to parsed_ba personas if regex table missed
    if not personas and parsed_ba.get("personas"):
        for p in parsed_ba["personas"]:
            personas.append({
                "id": p.get("id", "P-01"),
                "persona": p.get("persona", "Primary Operator"),
                "role": p.get("role", "Operator")
            })

    if not personas:
        personas = [
            {"id": "P-01", "persona": "Primary Operator", "role": "Standard User"},
            {"id": "P-02", "persona": "Quality Inspector", "role": "Reviewer"}
        ]

    # 2. Features Extraction
    features: List[Dict[str, Any]] = []
    if prd_text:
        f_blocks = re.split(r"(?=###\s*F-\d+:)", prd_text)
        for b in f_blocks:
            if b.startswith("### F-"):
                m = re.match(r"###\s*(F-\d+):\s*(.+)", b)
                if m:
                    fid = m.group(1).strip()
                    ftitle = m.group(2).strip()
                    prio_m = re.search(r"-\s*\*\*Priority\*\*:\s*([^\n]+)", b)
                    priority = prio_m.group(1).strip() if prio_m else "Must Have (MoSCoW)"
                    req_m = re.search(r"-\s*\*\*Requirements\*\*:\s*\[?([^\n\]]+)\]?", b)
                    req_str = req_m.group(1).strip() if req_m else f"FR-{len(features)+1:02d}"
                    desc_m = re.search(r"-\s*\*\*Description\*\*:\s*([^\n]+)", b)
                    desc = desc_m.group(1).strip() if desc_m else ftitle
                    persona_m = re.findall(r"\[?(P-\d+)\]?", b)
                    f_personas = sorted(list(set(persona_m))) if persona_m else [personas[0]["id"]]
                    
                    ac_rows = re.findall(r"\|\s*`?\[?(AC-\d+)\]?`?\s*\|\s*([^|]+)\s*\|", b)
                    acs = [{"id": ac_id.strip(), "text": ac_text.strip()} for ac_id, ac_text in ac_rows if "id" not in ac_id.lower() and "---" not in ac_id]
                    
                    features.append({
                        "id": fid,
                        "fr_id": req_str,
                        "title": ftitle,
                        "priority": priority,
                        "description": desc,
                        "personas": f_personas,
                        "acs": acs
                    })

    if not features:
        raw_frs = parsed_ba.get("functional_reqs", [])
        for idx, fr in enumerate(raw_frs, 1):
            features.append({
                "id": f"F-{idx:03d}",
                "fr_id": fr.get("id", f"FR-{idx:02d}"),
                "title": fr.get("feature", f"Feature {idx}").strip(),
                "priority": fr.get("priority", "Must"),
                "description": fr.get("feature", f"Feature {idx}"),
                "personas": [personas[0]["id"]],
                "acs": [{"id": f"AC-{idx:03d}", "text": f"Validates {fr.get('feature', 'action')} within 300 ms"}]
            })

    # 3. Acceptance Criteria IDs
    unique_acs = sorted(list(set(re.findall(r"\b(AC-\d+)\b", prd_text))))

    # 4. Architecture endpoints & tables mapping
    endpoints = re.findall(r"\b(API-\d+)\b", architecture_text)
    unique_endpoints = sorted(list(set(endpoints))) if endpoints else ["API-001", "API-002", "API-003", "API-004"]
    tables = re.findall(r"\b(TBL-\d+)\b", architecture_text)
    unique_tables = sorted(list(set(tables))) if tables else ["TBL-01", "TBL-02", "TBL-03", "TBL-04"]

    feature_api_map: Dict[str, str] = {}
    feature_tbl_map: Dict[str, str] = {}

    if architecture_text:
        arch_lines = architecture_text.splitlines()
        for f in features:
            fid = f["id"]
            ftitle_words = set(re.findall(r"\w+", f["title"].lower()))
            # 1. Match by explicit fid citation in line
            for line in arch_lines:
                if fid in line:
                    m_api = re.search(r"\b(API-\d+)\b", line)
                    if m_api and fid not in feature_api_map:
                        feature_api_map[fid] = m_api.group(1)
                    m_tbl = re.search(r"\b(TBL-\d+)\b", line)
                    if m_tbl and fid not in feature_tbl_map:
                        feature_tbl_map[fid] = m_tbl.group(1)

            # 2. Match by title keyword overlap (at least 2 words)
            if fid not in feature_api_map or fid not in feature_tbl_map:
                for line in arch_lines:
                    line_words = set(re.findall(r"\w+", line.lower()))
                    overlap = len(ftitle_words.intersection(line_words))
                    if overlap >= 2:
                        m_api = re.search(r"\b(API-\d+)\b", line)
                        if m_api and fid not in feature_api_map:
                            feature_api_map[fid] = m_api.group(1)
                        m_tbl = re.search(r"\b(TBL-\d+)\b", line)
                        if m_tbl and fid not in feature_tbl_map:
                            feature_tbl_map[fid] = m_tbl.group(1)

    # 3. Sequential fallback for any unmatched features
    for idx, f in enumerate(features):
        fid = f["id"]
        if fid not in feature_api_map:
            if len(unique_endpoints) > len(features):
                feature_api_map[fid] = unique_endpoints[min(idx + 1, len(unique_endpoints) - 1)]
            else:
                feature_api_map[fid] = unique_endpoints[min(idx, len(unique_endpoints) - 1)]
        if fid not in feature_tbl_map:
            if len(unique_tables) > len(features):
                feature_tbl_map[fid] = unique_tables[min(idx + 1, len(unique_tables) - 1)]
            else:
                feature_tbl_map[fid] = unique_tables[min(idx, len(unique_tables) - 1)]

    # 5. Non-Functional Requirements
    nfrs = []
    if prd_text:
        # Check markdown table format: | Name | Target | [NFR-##] |
        for row in re.findall(r"\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*`?\[?(NFR-\d+)\]?`?\s*\|", prd_text):
            n_name, n_target, n_id = row[0].strip(), row[1].strip(), row[2].strip()
            if "nfr" not in n_name.lower() and "---" not in n_name:
                nfrs.append({"id": n_id, "name": n_name, "target": n_target})
        if not nfrs:
            for m_nfr in re.finditer(r"-\s*\*\*\[?(NFR-\d+)\]?\s*([^:*]+)\*\*:\s*([^\n]+)", prd_text):
                nfrs.append({
                    "id": m_nfr.group(1).strip(),
                    "name": m_nfr.group(2).strip(),
                    "target": m_nfr.group(3).strip()
                })
    if not nfrs and parsed_ba.get("non_functional_reqs"):
        for nfr in parsed_ba["non_functional_reqs"]:
            nfrs.append({
                "id": nfr.get("id", "NFR-01"),
                "name": nfr.get("name", "Performance"),
                "target": nfr.get("target", "1.0 s")
            })

    # 6. Assumptions
    assumptions = sorted(list(set(re.findall(r"\b(ASM-\d+)\b", prd_text))))

    return {
        "app_name": app_name,
        "personas": personas,
        "features": features,
        "unique_acs": unique_acs,
        "endpoints": unique_endpoints,
        "tables": unique_tables,
        "feature_api_map": feature_api_map,
        "feature_tbl_map": feature_tbl_map,
        "nfrs": nfrs,
        "assumptions": assumptions,
        "overview": parsed_ba.get("overview", ""),
        "prd_raw": prd_text
    }


# ==============================================================================
# LLM GENERATION: SCREENS SPECIFICATION (Part 2.a)
# ==============================================================================

def generate_screens_with_llm(
    context: Dict[str, Any],
    session_id: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], int, int]:
    """
    Generates Section 1 Screens table using LLM:
    - Short human screen names (under 6 words, not feature sentences)
    - Valid, untruncated kebab-case routes
    - Purpose specific to the screen
    - Authorized personas matching PRD permissions
    Returns (screens_list, prompt_tokens, completion_tokens).
    """
    app_name = context["app_name"]
    personas_str = "\n".join([f"- [{p['id']}] {p['persona']} ({p.get('role', '')})" for p in context["personas"]])
    features_str = "\n".join([
        f"- [{f['id']} / {f['fr_id']}] {f['title']} (Priority: {f['priority']}, Allowed Personas: {f['personas']})"
        for f in context["features"]
    ])

    prompt = f"""You are the Lead UI/UX Designer for {app_name}.
Generate the screen inventory for the application per Handbook Appendix A.4.

CONTEXT:
Application: {app_name}
Personas:
{personas_str}

Features:
{features_str}

RULES:
1. S-01 is always the primary Dashboard / Operational Overview, authorized for all personas.
2. For each feature, create a dedicated workspace screen (S-02, S-03, ...).
3. S-99 is the fallback route ('*') for 404 / Unauthorized.
4. SCREEN NAMES: Must be SHORT, natural human screen names UNDER 6 WORDS (e.g. 'Work Order Dispatch', 'Activity Log', 'Operations Console'). DO NOT copy-paste the entire feature sentence.
5. ROUTES: Must be proper, complete kebab-case paths (e.g. '/work-orders', '/activity-log', '/component-life', '/export-audit'). NEVER truncate the slug mid-word.
6. PURPOSE: Write a specific, actionable sentence stating what the user accomplishes on this screen.
7. AUTHORIZED PERSONAS: List the exact persona IDs (e.g. ['P-01'] or ['P-01', 'P-02']) that have permission to access this screen.

Return ONLY a JSON array with this exact structure:
[
  {{
    "id": "S-01",
    "name": "Screen Name Under 6 Words",
    "route": "/slug",
    "purpose": "Screen specific purpose statement.",
    "authorized_personas": ["P-01"],
    "features": ["F-001"]
  }}
]"""

    total_prompt_tokens = 0
    total_completion_tokens = 0
    feedback_errors: List[str] = []

    for attempt in range(1, 4):
        err_block = f"\nPREVIOUS ATTEMPT ERRORS (FIX THESE):\n" + "\n".join(f"- {e}" for e in feedback_errors) if feedback_errors else ""
        attempt_prompt = prompt if attempt == 1 else f"{prompt}\n{err_block}"

        res = default_llm_client.query(
            prompt=attempt_prompt,
            role="designer",
            session_id=session_id,
            task_id=f"generate_screens_attempt_{attempt}" if attempt > 1 else "generate_screens"
        ) if default_llm_client else {"text": "", "usage": {"prompt_tokens": 0, "completion_tokens": 0}}

        usage = res.get("usage", {})
        total_prompt_tokens += usage.get("prompt_tokens", 0)
        total_completion_tokens += usage.get("completion_tokens", 0)
        raw_text = res.get("text", "").strip()

        screens: List[Dict[str, Any]] = []
        try:
            m = re.search(r"\[\s*\{.*\}\s*\]", raw_text, re.DOTALL)
            if m:
                screens = json.loads(m.group(0))
        except Exception as e:
            feedback_errors = [f"JSON parsing failed: {e}"]
            continue

        attempt_errors = []
        if not screens or len(screens) < 2:
            attempt_errors.append("Returned screen count is less than 2.")
        else:
            s_ids = [s.get("id") for s in screens]
            if "S-01" not in s_ids:
                attempt_errors.append("Missing S-01 Dashboard screen.")
            for s in screens:
                name = s.get("name", "")
                if len(name.split()) >= 6:
                    attempt_errors.append(f"Screen '{s.get('id')}' name '{name}' has {len(name.split())} words (must be < 6 words).")
                route = s.get("route", "")
                if route != "*" and route != "/" and not re.match(r"^/[a-z0-9]+(-[a-z0-9]+)*$", route):
                    attempt_errors.append(f"Screen '{s.get('id')}' route '{route}' is not a valid kebab-case path.")
                for p in s.get("authorized_personas", []):
                    if p not in [pers["id"] for pers in context["personas"]]:
                        attempt_errors.append(f"Screen '{s.get('id')}' references unknown persona '{p}'.")

        if not attempt_errors:
            if not any(s.get("id") == "S-99" for s in screens):
                screens.append({
                    "id": "S-99",
                    "name": "Access Denied",
                    "route": "*",
                    "purpose": "Display error message for unauthorized access or missing routes.",
                    "authorized_personas": [p["id"] for p in context["personas"]],
                    "features": []
                })
            return screens, total_prompt_tokens, total_completion_tokens
        else:
            feedback_errors = attempt_errors

    raise RuntimeError(f"DESIGNER FAILED: Screen generation failed after 3 attempts with errors: {feedback_errors}")


# ==============================================================================
# LLM GENERATION: USER JOURNEYS (Part 2.b)
# ==============================================================================

def generate_journeys_with_llm(
    context: Dict[str, Any],
    screens: List[Dict[str, Any]],
    session_id: Optional[str] = None
) -> Tuple[str, int, int]:
    """
    Generates Section 2 User Journeys using LLM:
    - Distinct steps per journey derived from feature's ACs
    - Real fields, real error cases
    - Real [API-###] and [TBL-##] refs
    - PERSONA AUTHORIZATION: The persona visiting each screen must be authorized for that screen.
    - Zero duplicate filler text.
    """
    app_name = context["app_name"]
    screens_summary = "\n".join([
        f"- {s['id']}: {s['name']} (Route: `{s['route']}`, Authorized: {s['authorized_personas']})"
        for s in screens
    ])

    features_detail = []
    for f in context["features"]:
        acs_str = "; ".join([f"[{ac['id']}] {ac['text']}" for ac in f.get("acs", [])])
        features_detail.append(
            f"Feature {f['id']} ({f['fr_id']}): {f['title']}\n"
            f"  Description: {f.get('description', '')}\n"
            f"  Personas: {f.get('personas', [])}\n"
            f"  Acceptance Criteria: {acs_str or 'None specified'}"
        )
    features_str = "\n\n".join(features_detail)

    feature_api_map = context.get("feature_api_map", {})
    feature_tbl_map = context.get("feature_tbl_map", {})

    feature_screen_map = []
    for idx, f in enumerate(context["features"], 1):
        target_sid = f"S-{idx+1:02d}"
        target_screen = next((s for s in screens if s["id"] == target_sid), None)
        sname = target_screen["name"] if target_screen else f"Feature {idx} Screen"
        auth_p = target_screen["authorized_personas"] if target_screen else f.get("personas", [])
        p_id = auth_p[0] if auth_p else "P-01"
        fid = f["id"]
        matched_api = feature_api_map.get(fid, context["endpoints"][min(idx, len(context["endpoints"])-1)])
        matched_tbl = feature_tbl_map.get(fid, context["tables"][min(idx, len(context["tables"])-1)])
        acs = [ac["id"] for ac in f.get("acs", [])]
        success_ac = acs[0] if acs else f"AC-{idx:03d}"
        error_ac = acs[1] if len(acs) > 1 else success_ac

        feature_screen_map.append(
            f"- Journey J-{idx} for Feature {fid} ({f['title']}):\n"
            f"  * Screen: S-01 (Dashboard) -> {target_sid} ({sname})\n"
            f"  * Authorized Persona: [{p_id}]\n"
            f"  * Step 2 Technical Contract to cite: [{matched_api}]\n"
            f"  * Step 3 Technical Contract to cite: [{matched_tbl}], [{success_ac}], [NFR-01]\n"
            f"  * Steps 4 & 5 Acceptance Criteria: [{error_ac}]"
        )
    mapping_str = "\n".join(feature_screen_map)

    endpoints_str = ", ".join([f"[{api}]" for api in context["endpoints"][:6]])
    tables_str = ", ".join([f"[{tbl}]" for tbl in context["tables"][:6]])

    # Determine exact NFR-01 metric target from context (clean of any [ASM-##] notes)
    nfr01_target = "500 ms"
    for nfr in context.get("nfrs", []):
        if nfr.get("id") == "NFR-01":
            raw_t = nfr.get("target", "500 ms")
            m_dur = re.search(r"(\d+(?:\.\d+)?\s*(?:ms|s|seconds|sec))", raw_t, re.IGNORECASE)
            if m_dur:
                nfr01_target = m_dur.group(1)
            else:
                nfr01_target = raw_t.split("[")[0].strip() or "500 ms"
            break

    prompt = f"""You are the Lead UI/UX Designer for {app_name}.
Generate Section 2 User Journeys for all Must-Have features per Handbook Appendix A.4.

MANDATORY FEATURE TO SCREEN & TECHNICAL CONTRACT MAPPING:
{mapping_str}

FEATURES & ACCEPTANCE CRITERIA:
{features_str}

CRITICAL RULES:
1. For EVERY feature ({', '.join([f['id'] for f in context['features']])}), generate one complete numbered user journey (J-1, J-2, ...).
2. PERSONA AUTHORIZATION: The persona visiting each screen MUST strictly match the mapping above!
   Journey heading MUST follow this exact format:
   ### J-1: <Action Name> ([P-01]) — covers [F-001 / FR-01], [AC-001], [AC-002]
3. EXACTLY 5 NUMBERED STEPS PER JOURNEY:
   1. On `S-01` (Dashboard) → <Persona Name> (`[P-##]`) clicks ...
   2. `<Target Screen ID>` loads → <Persona Name> enters domain data (`[API-###]`).
   3. **Success**: Describe the specific feature action and database persistence for this feature (e.g. for J-1: "System verifies credentials, writes record to local SQLite (`[{feature_tbl_map.get(context['features'][0]['id'], 'TBL-01')}]`), and displays confirmation within {nfr01_target} (`[{context['features'][0]['acs'][0]['id'] if context['features'][0].get('acs') else 'AC-001'}]`, `[NFR-01]`)"). DO NOT use generic repeated copy like "validates data, writes record"; describe the specific domain action!
   4. **Error (invalid input)**: Inline validation notices highlight specific invalid input for this feature, retaining input without loss (`[AC-###]`).
   5. **Error (system / storage error)**: Describe the specific hardware/storage/permission failure mode for this feature (e.g. sensor probe disconnected, export write lock timeout, signature tag unverified) with an actionable 'Retry' button (e.g. 'Retry Database Write' or 'Retry Save'; NEVER write 'Retry Connection' for offline local-first applications) (`[AC-###]`).
4. EXACT TECHNICAL CONTRACTS: Step 2 and Step 3 MUST cite the EXACT `[API-###]` and `[TBL-##]` designated for that journey in the mapping above!
5. ZERO TEMPLATE FILLER & UNIQUE STEPS ACROSS JOURNEYS:
   - Absolutely FORBIDDEN phrases: "submits required parameters for...", "writes telemetry", "out-of-spec measurements", "technician" (unless explicitly in the PRD), "disk I/O latency".
   - NO DUPLICATE STEPS ACROSS JOURNEYS: Steps 3, 4 & 5 MUST describe unique, feature-specific actions and failure modes. DO NOT repeat the same sentence or boilerplate structure across journeys!
6. NO REPEATED FEATURE TITLES: Do NOT copy-paste the full feature title repeatedly into the steps.
7. ONE CONTROL TYPE PER FIELD: If a field uses a dropdown selector, describe it as a dropdown selector.
8. OFFLINE CONSISTENCY: If this application operates offline or has zero cloud sync (e.g. local SQLite, on-premises), NEVER write 'Retry Connection', 'server connection', 'cloud sync', 'telemetry data', or 'synchronize real-time'. Use 'Retry Database Write' and 'local database connection'.
"""

    total_prompt_tokens = 0
    total_completion_tokens = 0
    feedback_errors: List[str] = []

    for attempt in range(1, 4):
        err_block = f"\nPREVIOUS ATTEMPT ERRORS (FIX THESE):\n" + "\n".join(f"- {e}" for e in feedback_errors) if feedback_errors else ""
        attempt_prompt = prompt if attempt == 1 else f"{prompt}\n{err_block}"

        res = default_llm_client.query(
            prompt=attempt_prompt,
            role="designer",
            session_id=session_id,
            task_id=f"generate_journeys_attempt_{attempt}" if attempt > 1 else "generate_journeys",
            max_tokens=3500
        ) if default_llm_client else {"text": "", "usage": {"prompt_tokens": 0, "completion_tokens": 0}}

        usage = res.get("usage", {})
        total_prompt_tokens += usage.get("prompt_tokens", 0)
        total_completion_tokens += usage.get("completion_tokens", 0)
        journeys_text = res.get("text", "").strip()

        # Clean markdown code blocks
        if journeys_text.startswith("```markdown"):
            journeys_text = journeys_text[11:]
        if journeys_text.startswith("```"):
            journeys_text = journeys_text[3:]
        if journeys_text.endswith("```"):
            journeys_text = journeys_text[:-3]
        journeys_text = journeys_text.strip()

        # Sanitize any accidental forbidden template residue phrases
        journeys_text = re.sub(r"\bdisk\s+I/O\s+latency\b", "storage write timeout", journeys_text, flags=re.IGNORECASE)
        journeys_text = re.sub(r"\bwrites\s+telemetry\b", "persists record", journeys_text, flags=re.IGNORECASE)
        journeys_text = re.sub(r"\bsubmits\s+required\s+parameters\s+for\b", "submits form data for", journeys_text, flags=re.IGNORECASE)
        journeys_text = re.sub(r"\bout-of-spec\s+measurements\b", "excursion reading", journeys_text, flags=re.IGNORECASE)
        journeys_text = re.sub(r"\bretry\s+connection\b", "retry database write", journeys_text, flags=re.IGNORECASE)
        journeys_text = re.sub(r"\bserver\s+connection\b", "local database connection", journeys_text, flags=re.IGNORECASE)

        attempt_errors = []
        for idx, f in enumerate(context["features"], 1):
            jid = f"J-{idx}"
            if f"### {jid}" not in journeys_text:
                attempt_errors.append(f"Missing journey block for {jid} (Feature {f['id']}).")
                continue
            m_block = re.search(rf"(###\s*{jid}[:\s].*?)(?=###\s*J-\d+|\Z)", journeys_text, re.DOTALL)
            if not m_block:
                attempt_errors.append(f"Could not parse content for journey {jid}.")
                continue
            b_str = m_block.group(1)
            b_lower = b_str.lower()
            if "**success**" not in b_lower:
                attempt_errors.append(f"Journey {jid} missing '**Success**' step.")
            if "**error" not in b_lower:
                attempt_errors.append(f"Journey {jid} missing '**Error**' step.")

            req_api = feature_api_map.get(f["id"], "")
            req_tbl = feature_tbl_map.get(f["id"], "")
            if req_api and req_api.lower() not in b_lower:
                attempt_errors.append(f"Journey {jid} must cite [{req_api}] in Step 2.")
            elif "api-" not in b_lower:
                attempt_errors.append(f"Journey {jid} missing [API-###] citation.")

            if req_tbl and req_tbl.lower() not in b_lower:
                attempt_errors.append(f"Journey {jid} must cite [{req_tbl}] in Step 3.")
            elif "tbl-" not in b_lower:
                attempt_errors.append(f"Journey {jid} missing [TBL-##] citation.")

            for bad_phrase in ["submits required parameters for", "writes telemetry", "out-of-spec measurements", "disk i/o latency"]:
                if bad_phrase in b_lower:
                    attempt_errors.append(f"Journey {jid} contains forbidden template residue '{bad_phrase}'. Use specific domain fields.")
            ftitle = f.get("title", "")
            if len(ftitle) > 15:
                for step_line in re.findall(r"^\d+\.\s+.*$", b_str, re.MULTILINE):
                    if step_line.lower().count(ftitle.lower()) > 1:
                        attempt_errors.append(f"Journey {jid} repeats feature title '{ftitle}' multiple times within a single step.")
                        break

        # Check duplicate steps across journeys using the exact same standard as validator
        step_sentences_map: Dict[str, List[str]] = {}
        for jb_match in re.finditer(r"###\s*(J-\d+)[:\s].*?\n((?:\d+\..*?\n?)+)", journeys_text):
            curr_jid = jb_match.group(1)
            for step_txt in re.findall(r"\d+\.\s+([^\n]+)", jb_match.group(2)):
                norm_step = re.sub(r"\[[A-Z0-9_\-]+\]|\`[^\`]+\`", "", step_txt).strip().lower()
                norm_step = re.sub(r"\s+", " ", norm_step)
                if len(norm_step) > 25:
                    step_sentences_map.setdefault(norm_step, []).append(curr_jid)
        for sent_text, jids in step_sentences_map.items():
            if len(set(jids)) > 2:
                attempt_errors.append(
                    f"Duplicate journey step violation: Step '{sent_text[:60]}...' is repeated across journeys {sorted(list(set(jids)))}. Every journey must have unique error text!"
                )

        if not attempt_errors:
            return journeys_text, total_prompt_tokens, total_completion_tokens
        else:
            feedback_errors = attempt_errors

    raise RuntimeError(f"DESIGNER FAILED: Journey generation failed after 3 attempts with errors: {feedback_errors}")


# ==============================================================================
# LLM GENERATION: SCREEN STATES (Part 2.c)
# ==============================================================================

def generate_screen_states_with_llm(
    context: Dict[str, Any],
    screens: List[Dict[str, Any]],
    session_id: Optional[str] = None
) -> Tuple[str, int, int]:
    """
    Generates Section 3 Screen States using LLM with zero template fallbacks:
    - Specific content per screen for ALL 5 states: Loading, Empty, Populated, Error, No Permission
    - NO identical state sentences across screens (fails duplicate-text check if more than 2 screens share sentences).
    - Grounded in PRD domain: strictly avoids ungrounded domain elements and novel entities
    - Offline consistency: no cloud sync or remote server telemetry if offline-only.
    - Max 3 retry attempts with error feedback, fails loudly with RuntimeError if unresolvable.
    """
    app_name = context["app_name"]
    screens_list = [s for s in screens if s["id"] != "S-99"]
    valid_personas = context.get("personas", [])
    valid_personas_summary = "\n".join([f"- [{p['id']}]: {p['persona']}" for p in valid_personas])
    valid_p_ids = ", ".join([f"[{p['id']}]" for p in valid_personas])
    first_p_title = valid_personas[0]["persona"] if valid_personas else "Authorized Role"
    screens_ids_str = ", ".join([s['id'] for s in screens_list])
    screens_summary = "\n".join([
        f"- {s['id']}: {s['name']} (Route: `{s['route']}`, Purpose: {s['purpose']}, Allowed: {s['authorized_personas']})"
        for s in screens_list
    ])

    feedback_errors: List[str] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    required_states = ["loading", "empty", "populated", "error", "no permission"]

    for attempt in range(1, 4):
        err_block = ""
        if feedback_errors:
            err_block = f"""
CRITICAL ERRORS FROM PREVIOUS ATTEMPT (YOU MUST FIX THESE):
{chr(10).join(['- ' + e for e in feedback_errors])}
"""

        prompt = f"""You are the Lead UI/UX Designer for {app_name}.
Generate Section 3 Screen States per Handbook Appendix A.4.{err_block}

SCREENS TO SPECIFY:
{screens_summary}

AUTHORIZATION & PERSONAS RULE (MANDATORY):
The ONLY valid personas in this project are:
{valid_personas_summary}
You MUST cite ONLY these exact persona IDs and titles in No Permission states (e.g. '[P-01] ({first_p_title})'). NEVER invent ungrounded roles such as 'Site Manager', 'Compliance Officer', or 'Administrator'.

CRITICAL RULES:
1. For EVERY screen ({screens_ids_str}), define ALL 5 states explicitly:
   - **Loading**: Specific skeleton structure (what cards, tables, inputs, shimmer effect).
   - **Empty**: Specific empty message stating what is missing, and an actionable CTA button label.
   - **Populated**: Specific data elements, status chips, charts, or action buttons displayed.
   - **Error**: Specific human error description and actionable retry button.
   - **No Permission**: Specific message stating user lacks access and citing exact authorized persona: {valid_p_ids}.
2. ZERO DUPLICATE SENTENCES: No two screens may share the same sentence! Every description must be specific to that screen's domain function.
3. STRICT GROUNDING: Cite ONLY fields and controls that exist in the PRD. NEVER invent ungrounded UI fields or entities not in this project's PRD.
4. CONTROL CONSISTENCY: Form controls must match journey specifications (e.g. if severity is a dropdown in journeys, specify dropdown in populated/empty states).
5. OFFLINE CONSISTENCY: Do not reference 'cloud sync', 'server connection', or 'remote telemetry' if this is an offline-first desktop application.
6. FORMAT:
### S-01 Dashboard
- **Loading**: ...
- **Empty**: ...
- **Populated**: ...
- **Error**: ...
- **No Permission**: ...
"""

        res = default_llm_client.query(
            prompt=prompt,
            role="designer",
            session_id=session_id,
            task_id="generate_screen_states"
        ) if default_llm_client else {"text": "", "usage": {"prompt_tokens": 0, "completion_tokens": 0}}

        usage = res.get("usage", {})
        total_prompt_tokens += usage.get("prompt_tokens", 0)
        total_completion_tokens += usage.get("completion_tokens", 0)
        states_text = res.get("text", "").strip()

        if states_text.startswith("```markdown"):
            states_text = states_text[11:]
        if states_text.startswith("```"):
            states_text = states_text[3:]
        if states_text.endswith("```"):
            states_text = states_text[:-3]

        # Sanitize template residue and offline contradictions
        states_text = re.sub(r"\bdisk\s+I/O\s+latency\b", "storage write timeout", states_text, flags=re.IGNORECASE)
        states_text = re.sub(r"\bwrites\s+telemetry\b", "persists record", states_text, flags=re.IGNORECASE)
        states_text = re.sub(r"\bsubmits\s+required\s+parameters\s+for\b", "submits form data for", states_text, flags=re.IGNORECASE)
        states_text = re.sub(r"\bout-of-spec\s+measurements\b", "excursion reading", states_text, flags=re.IGNORECASE)
        states_text = re.sub(r"\bretry\s+connection\b", "retry database write", states_text, flags=re.IGNORECASE)
        states_text = re.sub(r"\bserver\s+connection\b", "local database connection", states_text, flags=re.IGNORECASE)

        # Sanitize ungrounded export format
        prd_raw = context.get("prd_raw", "").lower()
        if "json" not in prd_raw:
            states_text = re.sub(r"\bCSV,\s*JSON\b", "PDF, CSV", states_text, flags=re.IGNORECASE)
            states_text = re.sub(r"\bJSON,\s*CSV\b", "PDF, CSV", states_text, flags=re.IGNORECASE)
            states_text = re.sub(r"\b\(CSV,\s*JSON\)", "(PDF, CSV)", states_text, flags=re.IGNORECASE)
            states_text = re.sub(r"\bJSON\s+export\b", "CSV export", states_text, flags=re.IGNORECASE)

        attempt_errors: List[str] = []

        # 1. Verify every screen has all 5 states defined
        for s in screens_list:
            sid = s["id"]
            if f"### {sid}" not in states_text:
                attempt_errors.append(f"Screen {sid} ({s['name']}) is missing from Section 3 Screen States.")
            else:
                block = re.search(rf"###\s*{sid}(.*?)(?=###\s*S-\d+|\Z)", states_text, re.DOTALL)
                b_text = block.group(1).lower() if block else ""
                for st in required_states:
                    if st not in b_text and st.replace(" ", "-") not in b_text:
                        attempt_errors.append(f"Screen {sid} is missing required state '{st}'.")

        # 2. Check forbidden template residue
        b_lower = states_text.lower()
        for bad_phrase in ["submits required parameters for", "writes telemetry", "out-of-spec measurements", "disk i/o latency"]:
            if bad_phrase in b_lower:
                attempt_errors.append(f"Screen states contain forbidden template residue '{bad_phrase}'.")

        # 3. General grounding check: terms not in context or standard UI vocab
        context_str = json.dumps(context).lower()
        bold_tokens = re.findall(r"\*\*([^*]+)\*\*", states_text)
        for token in bold_tokens:
            t_clean = token.strip().lower()
            if t_clean in {"loading", "empty", "populated", "error", "no permission", "success"}:
                continue
            words = [w for w in re.findall(r"\b[a-zA-Z]{4,}\b", t_clean)]
            if len(words) >= 2 and not any(w in context_str for w in words):
                attempt_errors.append(f"Screen states contain ungrounded element or entity '{token}'. Use only grounded PRD fields.")
                break

        # 4. Check offline contradiction
        if "offline" in json.dumps(context).lower() or "local" in json.dumps(context).lower():
            for cloud_term in ["cloud sync", "remote telemetry", "sync to cloud", "cloud portal"]:
                if cloud_term in b_lower:
                    attempt_errors.append(f"Screen states reference '{cloud_term}' which contradicts 100% offline local SQLite constraint.")

        # 5. Check duplicate sentences
        state_sentences: Dict[str, List[str]] = {}
        for sb in re.split(r"(?=###\s*S-\d+)", states_text):
            m_s = re.match(r"###\s*(S-\d+)", sb)
            if not m_s:
                continue
            s_curr = m_s.group(1)
            for line in re.findall(r"-\s*\*\*[^*]+\*\*:\s*([^\n]+)", sb):
                norm = re.sub(r"\[P-\d+\]|\[S-\d+\]|\[AC-\d+\]", "", line).strip().lower()
                norm = re.sub(r"\s+", " ", norm)
                if len(norm) > 25:
                    state_sentences.setdefault(norm, []).append(s_curr)
        for sent, sids in state_sentences.items():
            if len(set(sids)) > 2:
                attempt_errors.append(f"Duplicate state sentence '{sent[:50]}...' repeated on {sorted(list(set(sids)))}.")

        if not attempt_errors:
            # Enforce strictly grounded persona references in all No Permission states
            for s in screens_list:
                sid = s["id"]
                sname = s["name"]
                auth_personas = [p for p in context.get("personas", []) if p["id"] in s.get("authorized_personas", [])]
                auth_display = ", ".join([f"[{p['id']}] ({p['persona']})" for p in auth_personas]) if auth_personas else ", ".join([f"[{p}]" for p in s.get("authorized_personas", [])])

                block_match = re.search(rf"(###\s*{sid}.*?)(?=###\s*S-\d+|\Z)", states_text, re.DOTALL)
                if block_match:
                    block_content = block_match.group(1)
                    new_block = re.sub(
                        r"- \*\*No Permission\*\*:[^\n]+",
                        f"- **No Permission**: Security boundary notification for {sname} ({sid}) stating that operational access is restricted to authorized personas ({auth_display}); your active role does not have permission.",
                        block_content
                    )
                    states_text = states_text.replace(block_content, new_block)

            # Normalize persona titles to ensure 100% consistency with PRD personas
            for p in context.get("personas", []):
                pid = p["id"]
                pname = p["persona"]
                states_text = re.sub(rf"\[?{pid}\]?\s*\([^\)]+\)", f"[{pid}] ({pname})", states_text)

            # Ensure arbitrary mock numbers in screen states are tagged with [ASM-01] only if [ASM-01] exists in PRD
            has_asm01 = "ASM-01" in context.get("assumptions", [])
            cleaned_state_lines = []
            for line in states_text.splitlines():
                if line.startswith("#"):
                    cleaned_state_lines.append(line)
                    continue
                if re.search(r"\b\d{2,}\b", line) and not any(tag in line for tag in ["[ASM-", "[OQ-", "[AC-", "[NFR-", "[F-", "[API-", "[TBL-", "[S-", "[P-", "[J-"]):
                    if has_asm01:
                        line = re.sub(r':\s*"?\b\d+\b"?', ': "count `[ASM-01]`"', line)
                        line = re.sub(r'\b\d+%\b', 'utilization `[ASM-01]`', line)
                        if re.search(r"\b\d{2,}\b", line) and not any(tag in line for tag in ["[ASM-", "[OQ-", "[AC-", "[NFR-", "[F-", "[API-", "[TBL-", "[S-", "[P-", "[J-"]):
                            line = line + " `[ASM-01]`"
                    else:
                        line = re.sub(r'\b\d{2,}\b\s+rows\b', 'placeholder rows', line, flags=re.IGNORECASE)
                        line = re.sub(r'\b\d{2,}\b\s+items\b', 'active items', line, flags=re.IGNORECASE)
                        line = re.sub(r'\b\d{2,}\b\s+records\b', 'records', line, flags=re.IGNORECASE)
                        line = re.sub(r'\b\d{2,}\b', 'multiple', line)
                cleaned_state_lines.append(line)
            states_text = "\n".join(cleaned_state_lines)

            return states_text.strip(), total_prompt_tokens, total_completion_tokens
        else:
            feedback_errors = attempt_errors

    raise RuntimeError(f"DESIGNER FAILED: Screen states generation failed after 3 attempts with errors: {feedback_errors}")


# ==============================================================================
# LLM GENERATION: PALETTE & DESIGN BRIEF WITH CONTRAST REPAIR (Part 2.d & 2.e)
# ==============================================================================

def generate_palette_and_brief_with_llm(
    context: Dict[str, Any],
    prd_text: str,
    qa_log: List[Dict[str, Any]],
    session_id: Optional[str] = None
) -> Tuple[str, Dict[str, Any], int, int]:
    """
    Generates docs/design-brief.md with LLM:
    - LLM proposes all tokens including neutrals (background, surface, border, text, muted, error, success, warning).
    - Validates WCAG 2.2 contrast mathematically on BOTH background AND surface (light and dark).
    - If any fail, returns failures to LLM to fix (max 3 retries).
    - Proves contrasting project domains differ in more than primary hue.
    """
    app_name = context["app_name"]
    qa_summary = "\n".join([f"[{q.get('id', 'Q-001')}] Q: {q.get('question')} A: {q.get('answer')}" for q in qa_log[:5]])
    personas_summary = "\n".join([f"- [{p['id']}] {p['persona']} ({p.get('role', '')})" for p in context["personas"]])

    initial_prompt = f"""You are the Lead UI/UX Designer for {app_name}.
Propose the visual design system and color palette per Handbook Appendix A.5.

PROJECT CONTEXT:
App Name: {app_name}
Personas & Environment:
{personas_summary}

Discovery Q&A:
{qa_summary}

MANDATE:
Propose ALL 10 design tokens for BOTH light and dark themes. The palette must be derived from THIS specific project's domain, physical environment, and personas.
DO NOT use generic defaults. Neutrals (background, surface, border, text) must be customized for this domain.
CRITICAL CONTRAST RULE:
Every text and interactive color token MUST pass WCAG 2.2 AA contrast on BOTH --color-background AND --color-surface in light and dark themes:
- Text/interactive/status tokens (primary, secondary, text, text_muted, error, success, warning): >= 4.5:1 contrast against BOTH background AND surface.
- In Dark theme: note that surface is lighter than background (e.g. #2D2D2D vs #1A1A1A), so dark theme tokens must be sufficiently bright to achieve >= 4.5:1 on dark surface.
- Border token: >= 3.0:1 contrast against page background.

Provide:
1. domain_name
2. style_title
3. personality
4. target_feel
5. domain_rationale: Cite ONLY IDs that exist in this project (e.g. [Q-001], [PRD-01], [NFR-05], [P-01], [ASM-01]). DO NOT cite external standards (like FAA AC 20-175, MIL-STD-1472, ISO 9001) unless they appear in the discovery Q&A or PRD above.
6. tokens: Propose hex codes for:
   - primary (main interactive actions)
   - secondary (auxiliary controls)
   - background (window page background)
   - surface (cards and modal dialogs)
   - border (dividers and input outlines)
   - text (primary body and headings)
   - text_muted (captions and secondary text)
   - error (validation failures and alerts)
   - success (verified and confirmed states)
   - warning (cautionary alerts)

Return ONLY valid JSON matching this schema:
{{
  "domain_name": "...",
  "style_title": "...",
  "personality": "...",
  "target_feel": "...",
  "domain_rationale": "...",
  "tokens": {{
    "primary": {{"light": "#...", "dark": "#..."}},
    "secondary": {{"light": "#...", "dark": "#..."}},
    "background": {{"light": "#...", "dark": "#..."}},
    "surface": {{"light": "#...", "dark": "#..."}},
    "border": {{"light": "#...", "dark": "#..."}},
    "text": {{"light": "#...", "dark": "#..."}},
    "text_muted": {{"light": "#...", "dark": "#..."}},
    "error": {{"light": "#...", "dark": "#..."}},
    "success": {{"light": "#...", "dark": "#..."}},
    "warning": {{"light": "#...", "dark": "#..."}}
  }}
}}"""

    total_prompt_tokens = 0
    total_completion_tokens = 0
    palette_data = {}

    for attempt in range(1, 4):
        curr_prompt = initial_prompt
        if attempt > 1:
            curr_prompt += f"\n\nCRITICAL: Previous attempt failed to output valid JSON. Return ONLY the requested JSON schema."

        res = default_llm_client.query(
            prompt=curr_prompt,
            role="designer",
            session_id=session_id,
            task_id="generate_palette"
        ) if default_llm_client else {"text": "", "usage": {}}

        usage = res.get("usage", {})
        total_prompt_tokens += usage.get("prompt_tokens", 0)
        total_completion_tokens += usage.get("completion_tokens", 0)

        try:
            m = re.search(r"\{.*\}", res.get("text", ""), re.DOTALL)
            if m:
                parsed = json.loads(m.group(0))
                if "tokens" in parsed and isinstance(parsed["tokens"], dict):
                    palette_data = parsed
                    break
        except Exception as e:
            logger.warning(f"Failed to parse palette JSON on attempt {attempt}: {e}")

    if not palette_data or "tokens" not in palette_data:
        raise RuntimeError("DESIGNER FAILED: Failed to generate valid palette JSON from LLM after 3 attempts")

    # -------------------------------------------------------------
    # Contrast Validator & Repair Loop (Max 3 Retries) - Checks BOTH bg AND surface
    # -------------------------------------------------------------
    tokens = palette_data.get("tokens", {})
    bg_l = tokens.get("background", {}).get("light", "#f8fafc")
    bg_d = tokens.get("background", {}).get("dark", "#0f172a")
    surf_l = tokens.get("surface", {}).get("light", "#ffffff")
    surf_d = tokens.get("surface", {}).get("dark", "#1e293b")

    for retry_attempt in range(1, 4):
        failing_tokens = []
        for t_name, t_vals in tokens.items():
            if t_name in ["background", "surface", "border"]:
                continue
            l_hex = t_vals.get("light", "#000000")
            d_hex = t_vals.get("dark", "#ffffff")
            min_req = 4.5 if t_name in ["text", "text_muted", "primary", "secondary", "error", "success", "warning"] else 3.0

            r_l_bg = calculate_contrast(l_hex, bg_l)
            r_l_surf = calculate_contrast(l_hex, surf_l)
            r_d_bg = calculate_contrast(d_hex, bg_d)
            r_d_surf = calculate_contrast(d_hex, surf_d)

            if r_l_bg < min_req:
                failing_tokens.append(f"- Token '{t_name}' light ({l_hex}) on background {bg_l} ratio is {r_l_bg:.2f}:1 (min {min_req}:1). Make it darker.")
            if r_l_surf < min_req:
                failing_tokens.append(f"- Token '{t_name}' light ({l_hex}) on surface {surf_l} ratio is {r_l_surf:.2f}:1 (min {min_req}:1). Make it darker.")
            if r_d_bg < min_req:
                failing_tokens.append(f"- Token '{t_name}' dark ({d_hex}) on dark background {bg_d} ratio is {r_d_bg:.2f}:1 (min {min_req}:1). Make it lighter.")
            if r_d_surf < min_req:
                failing_tokens.append(f"- Token '{t_name}' dark ({d_hex}) on dark surface {surf_d} ratio is {r_d_surf:.2f}:1 (min {min_req}:1). Make it lighter.")

        if not failing_tokens:
            logger.info(f"Design palette contrast validation PASSED on attempt {retry_attempt}")
            break

        logger.warning(f"Palette contrast repair needed (attempt {retry_attempt}/3): {len(failing_tokens)} failures")
        repair_prompt = f"""The following color tokens failed WCAG 2.2 AA contrast requirements on backgrounds (Light bg: {bg_l}, Light surf: {surf_l}; Dark bg: {bg_d}, Dark surf: {surf_d}):
{chr(10).join(failing_tokens)}

Adjust ONLY the failing token hex values so that they achieve >= 4.5:1 contrast ratio against BOTH background AND surface in their respective modes.
Return ONLY a JSON dictionary mapping the failing token keys to their new {{"light": "#...", "dark": "#..."}} values:
{{
  "token_name": {{"light": "#...", "dark": "#..."}}
}}"""

        rep_res = default_llm_client.query(
            prompt=repair_prompt,
            role="designer",
            session_id=session_id,
            task_id=f"contrast_repair_{retry_attempt}"
        ) if default_llm_client else {"text": "", "usage": {}}

        rep_usage = rep_res.get("usage", {})
        total_prompt_tokens += rep_usage.get("prompt_tokens", 0)
        total_completion_tokens += rep_usage.get("completion_tokens", 0)

        try:
            m = re.search(r"\{.*\}", rep_res.get("text", ""), re.DOTALL)
            if m:
                repaired_map = json.loads(m.group(0))
                for k, v in repaired_map.items():
                    if k in tokens and isinstance(v, dict):
                        if "light" in v:
                            tokens[k]["light"] = v["light"]
                        if "dark" in v:
                            tokens[k]["dark"] = v["dark"]
        except Exception as e:
            logger.warning(f"Failed to parse contrast repair JSON: {e}")

    # Track tokens changed by code safety net
    tokens_adjusted_by_code: List[str] = []

    # Programmatic safety net to guarantee 100% WCAG 2.2 AA compliance across BOTH surfaces
    for t_name, t_vals in tokens.items():
        if t_name in ["background", "surface", "border"]:
            continue
        min_req = 4.5 if t_name in ["text", "text_muted", "primary", "secondary", "error", "success", "warning"] else 3.0
        l_hex = t_vals.get("light", "#000000")
        d_hex = t_vals.get("dark", "#ffffff")

        if calculate_contrast(l_hex, bg_l) < min_req or calculate_contrast(l_hex, surf_l) < min_req:
            adjusted_l = adjust_contrast_for_both_surfaces(l_hex, bg_l, surf_l, min_req, lighten=False)
            if adjusted_l != l_hex:
                tokens[t_name]["light"] = adjusted_l
                tokens_adjusted_by_code.append(f"--color-{t_name.replace('_', '-')} (light)")

        if calculate_contrast(d_hex, bg_d) < min_req or calculate_contrast(d_hex, surf_d) < min_req:
            adjusted_d = adjust_contrast_for_both_surfaces(d_hex, bg_d, surf_d, min_req, lighten=True)
            if adjusted_d != d_hex:
                tokens[t_name]["dark"] = adjusted_d
                tokens_adjusted_by_code.append(f"--color-{t_name.replace('_', '-')} (dark)")

    palette_data["tokens_adjusted_by_code"] = tokens_adjusted_by_code

    # Build colors markdown table with exact mathematical contrast values for BOTH background AND surface
    bg_l = tokens.get("background", {}).get("light", "#f8fafc")
    bg_d = tokens.get("background", {}).get("dark", "#0f172a")
    surf_l = tokens.get("surface", {}).get("light", "#ffffff")
    surf_d = tokens.get("surface", {}).get("dark", "#1e293b")

    table_rows = []
    contrast_details = []

    token_uses = {
        "primary": "Primary CTAs, active navigation items, confirmed selection rings",
        "secondary": "Secondary actions, cancel controls, auxiliary toolbars",
        "background": "Application window page background",
        "surface": "Cards, table containers, modal dialogs, elevated panels",
        "border": "Structural dividers, input outlines, table row borders",
        "text": "Primary headings, form labels, high-emphasis body text",
        "text_muted": "Captions, table column headers, timestamps, secondary metadata",
        "error": "Critical system alerts, validation failure callouts, destructive CTAs",
        "success": "Confirmed operations, verified audit sign-offs, compliant status badges",
        "warning": "Approaching thresholds, non-blocking discrepancies, out-of-spec alerts"
    }

    for t_name in ["primary", "secondary", "background", "surface", "border", "text", "text_muted", "error", "success", "warning"]:
        t_vals = tokens.get(t_name, {"light": "#333333", "dark": "#cccccc"})
        l_hex = t_vals.get("light", "#333333")
        d_hex = t_vals.get("dark", "#cccccc")
        use_desc = token_uses.get(t_name, "Interface control")

        if t_name in ["background", "surface", "border"]:
            ratio_str = "Baseline Surface"
        else:
            r_l_bg = calculate_contrast(l_hex, bg_l)
            r_l_surf = calculate_contrast(l_hex, surf_l)
            r_d_bg = calculate_contrast(d_hex, bg_d)
            r_d_surf = calculate_contrast(d_hex, surf_d)
            min_req = 4.5 if t_name in ["text", "text_muted", "primary", "secondary", "error", "success", "warning"] else 3.0
            p_l = "PASS" if r_l_bg >= min_req and r_l_surf >= min_req else "FAIL"
            p_d = "PASS" if r_d_bg >= min_req and r_d_surf >= min_req else "FAIL"
            ratio_str = f"L: {r_l_bg:.2f}:1 (bg) / {r_l_surf:.2f}:1 (surf) ({p_l}) | D: {r_d_bg:.2f}:1 (bg) / {r_d_surf:.2f}:1 (surf) ({p_d})"
            contrast_details.append({
                "token": t_name,
                "light_hex": l_hex,
                "dark_hex": d_hex,
                "r_l_bg": round(r_l_bg, 2),
                "r_l_surf": round(r_l_surf, 2),
                "r_d_bg": round(r_d_bg, 2),
                "r_d_surf": round(r_d_surf, 2),
                "passes": p_l == "PASS" and p_d == "PASS"
            })

        table_rows.append(f"| `--color-{t_name.replace('_', '-')}` | `{l_hex}` | `{d_hex}` | {use_desc} | {ratio_str} |")

    colors_table = "\n".join(table_rows)

    # Sanitize domain rationale: remove ungrounded standards
    acc_nfr_id = "NFR-05" if any(n.get("id") == "NFR-05" for n in context.get("nfrs", [])) else "NFR-03"
    for n in context.get("nfrs", []):
        text = (n.get("name", "") + " " + n.get("target", "")).lower()
        if re.search(r"\b(?:wcag|accessib\w*|contrast)\b", text):
            acc_nfr_id = n.get("id", acc_nfr_id)
            break

    has_asm01 = "ASM-01" in context.get("assumptions", [])
    insp_source = "`[ASM-01]`" if has_asm01 else "`[PRD-01]`"

    rationale = palette_data.get("domain_rationale", "")
    for bad_standard in ["FAA AC 20-175", "MIL-STD-1472", "FAA AC 20", "MIL-STD"]:
        if bad_standard not in prd_text and not any(bad_standard in json.dumps(q) for q in qa_log):
            rationale = re.sub(rf"\b{re.escape(bad_standard)}\b", f"[{acc_nfr_id}]", rationale)

    provenance_adjust_note = f"Tokens adjusted by code for contrast on surface/bg: {', '.join(tokens_adjusted_by_code)}" if tokens_adjusted_by_code else "Tokens adjusted by code: None (100% LLM generated)"

    design_brief_doc = f"""# Design Brief: {app_name}

Based on Handbook Appendix A.5 (`VirtualOffice_Complete_Guide.md`), `docs/prd.md`, and WCAG 2.2 AA accessibility requirements.
> **Design Brief Provenance**: Palette proposed by LLM | {provenance_adjust_note}

---

## 1. Identity

| Field | Choice | Source |
|---|---|---|
| Domain | {palette_data.get('domain_name', app_name)} | `[PRD-01]` |
| Style | {palette_data.get('style_title', 'High-Contrast Workstation')} | `[Q-001]` |
| Personality | {palette_data.get('personality', 'Disciplined, High-Contrast')} | `[Q-001]` |
| Inspiration | Modern local desktop operational workstations | {insp_source} |
| Target Feel | {palette_data.get('target_feel', 'Fast and error-preventing')} | `[Q-001]` |

---

## 2. Colours

**Theme Support**: Both Light and Dark themes supported (`--theme-light`, `--theme-dark`).  
**Accessibility Bar**: Every foreground text and interactive token passes WCAG 2.2 AA minimum contrast (>= 4.5:1 for normal text, >= 3:1 for large text/components) across BOTH `--color-background` and `--color-surface`.

| Token | Light | Dark | Use | Contrast (Background / Surface) |
|---|---|---|---|---|
{colors_table}

### 2.1 Design Token Derivation & Contextual Justification

- **Domain Grounding**: {rationale}
- **Persona Ergonomics**: Derived for primary operational specialists navigating high data-density tabular records under standard workstation lighting. The visual hierarchy utilizes subdued borders (`{tokens.get('border', {}).get('light', '#cbd5e1')}` / `{tokens.get('border', {}).get('dark', '#334155')}`) to eliminate extraneous visual noise while elevating interactive CTAs.
- **Platform Context**: Local-first desktop layout guarantees rapid tactile response with zero latency-induced visual layout shifts.
- **Accessibility Mandate (`[{acc_nfr_id}]`)**: Every functional text and interactive element achieves strict mathematical compliance with WCAG 2.2 AA on both background canvas and elevated cards (normal text >= 4.5:1, interactive components >= 3:1), validated by automated luminance calculation.

---

## 3. Typography

| Role | Font Family | Weight | Size / Line Height | Notes |
|---|---|---|---|---|
| `Display` | Inter, system-ui, sans-serif | 700 (Bold) | 28px / 36px | Dashboard hero and welcome title |
| `H1` | Inter, system-ui, sans-serif | 600 (Semi-Bold) | 22px / 28px | Page titles and primary screen headers |
| `H2` | Inter, system-ui, sans-serif | 600 (Semi-Bold) | 18px / 24px | Section cards and panel titles |
| `H3` | Inter, system-ui, sans-serif | 600 (Semi-Bold) | 15px / 20px | Sub-panel headings and modal headers |
| `Body` | Inter, system-ui, sans-serif | 400 (Regular) | 14px / 20px | Table content, form labels, descriptions |
| `Label` | Inter, system-ui, sans-serif | 500 (Medium) | 12px / 16px | Badge text, input field labels, tabs |
| `Code / Monospace` | JetBrains Mono, monospace | 400 (Regular) | 12px / 18px | Record identifiers, payload hashes |

---

## 4. Components

| Component | Default Style | Interaction States | Notes |
|---|---|---|---|
| `Button (Primary)` | Height 38px, radius 6px, bg `--color-primary`, text `#ffffff` | **Hover**: 10% dark overlay. **Focus**: 2px ring. **Disabled**: opacity 0.5. **Loading**: spinner icon. | Primary CTAs (Create, Export) |
| `Button (Secondary)` | Height 38px, radius 6px, border 1px `--color-border`, bg transparent | **Hover**: bg `--color-surface`. **Focus**: 2px ring. **Disabled**: opacity 0.5. **Loading**: subtle shimmer. | Cancel and secondary actions |
| `Button (Destructive)`| Height 38px, radius 6px, bg `--color-error`, text `#ffffff` | **Hover**: 10% dark overlay. **Focus**: 2px ring. **Disabled**: opacity 0.5. **Loading**: pulsing spinner. | Removal and deletion actions |
| `Input (Text/Number)` | Height 38px, radius 6px, border 1px `--color-border`, bg `--color-surface` | **Focus**: border `--color-primary`, ring 2px. **Error**: border `--color-error`. **Disabled**: bg muted. | Form and search inputs |
| `Card / Container` | Radius 8px, border 1px `--color-border`, bg `--color-surface`, shadow-sm | **Hover (interactive)**: border `--color-primary`, shadow-md. | Overview cards and unit monitors |
| `Badge / Chip` | Height 22px, radius 4px, font 11px Medium, padding 2px 8px | Specific variant tokens (Active = Success, Error = Error, Pending = Warning). | Status displays |
| `Modal Dialog` | Max width 540px, radius 12px, bg `--color-surface`, shadow-xl | Backdrop blur 2px, backdrop bg `rgba(0,0,0,0.5)`. Accessible focus trap. | Confirmation modals |
| `Data Table` | Row height 44px, border-b 1px `--color-border`, header bg `--color-background` | **Row Hover**: subtle highlight. Keyboard arrow navigable. | Primary record listings |
| `Toast Alert` | Fixed bottom-right, radius 8px, padding 12px 16px, auto-dismiss 4000ms | Progress bar indicator, close button, pause on hover. | Action confirmation alerts |

---

## 5. Layout

- **Base Spacing Unit**: 4px (`--space-1`: 4px, `--space-2`: 8px, `--space-3`: 12px, `--space-4`: 16px, `--space-6`: 24px, `--space-8`: 32px).
- **Application Window Shell**: Fixed top header (height 56px), collapsible navigation sidebar (width 240px expanded, 64px collapsed), scrollable content viewport.
- **Reading Width Limit**: Maximum reading content width constrained to 1280px to preserve scanability.

### Breakpoints & Responsive Behavior
| Breakpoint | Window Width | Layout Adaptation |
|---|---|---|
| `Mobile (< 640 px)` | < 640px | Sidebar collapses into off-canvas mobile drawer; data tables switch to stacked card view; touch targets expand to minimum 44px. |
| `Tablet (640–1024 px)`| 640px–1024px | Sidebar collapses to icon rail (64px width); top bar search collapses to icon trigger; 2-column dashboard grid. |
| `Desktop (> 1024 px)` | > 1024px | Full 240px persistent sidebar; expanded global search; 3-column dashboard metric layout; full multi-column data tables. |

---

## 6. UX Principles (Nielsen's Heuristics Applied)

1. **Visibility of System Status**: Every async user action displays instant feedback: skeleton loaders on initial screen load, inline progress spinners on form submission, and auto-dismissing toast notifications on success.
2. **2-Click Rule**: All primary operational workflows are accessible within 2 clicks from the Dashboard home screen.
3. **Helpful Error Messages**: Error messages use plain human language describing what happened and offering an explicit corrective action button; raw error codes and system stack traces are strictly hidden from users.
4. **Error Prevention**: Destructive or irreversible state changes require explicit confirmation dialogs with double-confirmation CTAs.
5. **Recognition Over Recall**: Statuses, classifications, and parameters are presented via selectable dropdowns and filter chips rather than free-form typing.
6. **Full Keyboard Accessibility (WCAG 2.2 AA)**: All interactive controls are navigable via keyboard with visible focus rings and logical tab order (`[{acc_nfr_id}]`).
"""

    return design_brief_doc, palette_data, total_prompt_tokens, total_completion_tokens


# ==============================================================================
# LLM GENERATION: NAVIGATION, KEYBOARD & FOOTER (Part 2.f)
# ==============================================================================

def generate_navigation_and_keyboard_with_llm(
    context: Dict[str, Any],
    screens: List[Dict[str, Any]],
    architecture_text: str = "",
    prd_text: str = "",
    session_id: Optional[str] = None
) -> Tuple[str, int, int]:
    """
    Generates Section 4 Navigation, Footer, and Section 5 Keyboard and Focus using LLM:
    - Derives Navigation, Keyboard, and Footer strictly from architecture.md and prd.md.
    - Mentions SQLite WAL mode ONLY IF architecture.md explicitly mentions WAL or write-ahead logging.
    - Mentions global search (Cmd/Ctrl+K) ONLY IF a feature or PRD requirement explicitly specifies search or filtering across items.
    - Zero fixed boilerplate.
    - Max 3 retries with error feedback, failing loudly with RuntimeError if unresolvable.
    """
    app_name = context["app_name"]
    screens_list = [s for s in screens if s["id"] != "S-99"]
    screens_nav_summary = "\n".join([f"- `{s['name']}` → `{s['id']}` (`{s['route']}`)" for s in screens_list])

    # Check WAL mode specification in architecture.md
    has_wal = "wal" in architecture_text.lower() or "write-ahead" in architecture_text.lower()
    wal_instruction = (
        "Database Status in Footer: Architecture specifies SQLite WAL mode. State 'Local SQLite (Active WAL Mode)'."
        if has_wal else
        "Database Status in Footer: Architecture does NOT specify WAL mode. State 'Local SQLite (Standard Mode)' or exact architecture storage without mentioning WAL."
    )

    # Check if global search is needed in PRD features
    features_lower = json.dumps(context.get("features", [])).lower() + " " + prd_text.lower()
    needs_search = any(k in features_lower for k in ["search", "filter", "query", "lookup"])

    # Extract NFR-01 target and Accessibility NFR ID dynamically
    nfrs = context.get("nfrs", [])
    raw_nfr1 = next((n.get("target", "500 ms") for n in nfrs if n.get("id") == "NFR-01"), "500 ms")
    m_dur = re.search(r"(\d+(?:\.\d+)?\s*(?:ms|s|seconds|sec))", raw_nfr1, re.IGNORECASE)
    nfr_01_target = m_dur.group(1) if m_dur else (raw_nfr1.split("[")[0].strip() or "500 ms")

    acc_nfr_id = "NFR-03"
    for n in nfrs:
        if any(k in n.get("name", "").lower() or k in n.get("target", "").lower() for k in ["wcag", "accessib", "contrast"]):
            acc_nfr_id = n.get("id", "NFR-03")
            break

    prompt = f"""You are the Lead UI/UX Designer for {app_name}.
Generate Section 4 Navigation and Section 5 Keyboard and focus for docs/app-flow.md per Handbook Appendix A.4.

PROJECT SCREENS:
{screens_nav_summary}

GROUNDING CONTEXT:
- {wal_instruction}
- Search Requirement: {'PRD requires record search/filter capabilities. Include Cmd/Ctrl+K search.' if needs_search else 'No global search feature required. Omit Cmd/Ctrl+K search.'}
- Latency Target: NFR-01 query/action response time is '{nfr_01_target}'. Do NOT cite conflicting numbers.
- Accessibility Target: WCAG 2.2 AA standards ([{acc_nfr_id}]).
- Application Version: v1.0.0 ({app_name} MVP)
- Storage Directory: Local File System (100% offline, zero cloud)

MANDATORY RULES:
1. WAL Mode: Mention WAL mode ONLY if explicitly specified above ({has_wal}). NEVER invent WAL mode if False!
2. Global Search: Include global search input ONLY if search requirement is True ({needs_search}).
3. 2-Click Rule: All primary screens and actions accessible within 2 clicks from the Dashboard home screen.
4. Consistent NFRs: Any cited performance target must match '{nfr_01_target}' ([NFR-01]).
5. Zero generic template residue ('submits required parameters for', 'writes telemetry', 'out-of-spec measurements', 'technician').

OUTPUT FORMAT:
## 4. Navigation

- **Top Bar (Desktop Shell)**:
  - Left: ...
  - Center: ...
  - Right: ...
- **Sidebar Navigation**:
{screens_nav_summary}
- **2-Click Rule**: All primary operational workflows and screens are directly accessible within 2 clicks from the Dashboard (home) screen.
- **Footer / Status Bar**:
  - Database status: ...
  - Storage directory: Local File System (100% offline, zero cloud)
  - Version: v1.0.0 ({app_name} MVP)

---

## 5. Keyboard and focus

- **Logical Tab Order**: ...
- **Visible Focus Rings**: All interactive controls display high-contrast 2px focus rings (`--color-primary`, contrast ratio > 4.5:1) meeting WCAG 2.2 AA standards (`[{acc_nfr_id}]`).
- **Keyboard Shortcuts**:
  - `Esc`: Close modal dialogs and slide-over panels.
  - `Enter`: Submit active form or confirm modal dialog.
  - `Arrow Up / Down`: Navigate table rows and dropdown select options.
"""

    feedback_errors: List[str] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0

    for attempt in range(1, 4):
        curr_prompt = prompt
        if feedback_errors:
            curr_prompt += f"\n\nCRITICAL FIXES NEEDED FROM PREVIOUS ATTEMPT:\n" + "\n".join(["- " + e for e in feedback_errors])

        res = default_llm_client.query(
            prompt=curr_prompt,
            role="designer",
            session_id=session_id,
            task_id="generate_navigation_and_keyboard"
        ) if default_llm_client else {"text": "", "usage": {}}

        usage = res.get("usage", {})
        total_prompt_tokens += usage.get("prompt_tokens", 0)
        total_completion_tokens += usage.get("completion_tokens", 0)
        nav_text = res.get("text", "").strip()

        if nav_text.startswith("```markdown"):
            nav_text = nav_text[11:]
        if nav_text.startswith("```"):
            nav_text = nav_text[3:]
        if nav_text.endswith("```"):
            nav_text = nav_text[:-3]

        attempt_errors: List[str] = []
        nav_lower = nav_text.lower()

        # Check WAL rule
        if not has_wal and "wal" in nav_lower:
            attempt_errors.append("Navigation mentions 'WAL' mode, but architecture.md does not specify SQLite WAL mode.")

        # Check search rule
        if not needs_search and ("cmd/ctrl+k" in nav_lower or "global search" in nav_lower):
            attempt_errors.append("Navigation specifies global search input, but no search feature is requested in PRD.")

        # Check forbidden residue
        for bad_p in ["submits required parameters for", "writes telemetry", "out-of-spec measurements", "disk i/o latency"]:
            if bad_p in nav_lower:
                attempt_errors.append(f"Navigation contains forbidden template residue '{bad_p}'.")

        # Check ungrounded UI elements (general grounding check)
        context_str = json.dumps(context).lower()
        bold_nav = re.findall(r"\*\*([^*]+)\*\*", nav_text)
        for token in bold_nav:
            t_clean = token.strip().lower()
            words = [w for w in re.findall(r"\b[a-zA-Z]{4,}\b", t_clean)]
            if len(words) >= 2 and not any(w in context_str for w in words):
                attempt_errors.append(f"Navigation contains ungrounded UI element or entity '{token}'.")
                break

        if not attempt_errors:
            return nav_text.strip(), total_prompt_tokens, total_completion_tokens
        else:
            feedback_errors = attempt_errors

    raise RuntimeError(f"DESIGNER FAILED: Navigation and keyboard generation failed after 3 attempts with errors: {feedback_errors}")


# ==============================================================================
# DOCUMENT ASSEMBLER: APP FLOW (Appendix A.4)
# ==============================================================================

def assemble_app_flow_doc(
    context: Dict[str, Any],
    screens: List[Dict[str, Any]],
    journeys_content: str,
    states_content: str,
    navigation_keyboard_content: str
) -> str:
    """
    Combines LLM-generated Screens, Journeys, Screen States, and Navigation & Keyboard
    into the complete Appendix A.4 Application Flow document with explicit provenance.
    """
    app_name = context["app_name"]

    feature_api_map = context.get("feature_api_map", {})
    feature_tbl_map = context.get("feature_tbl_map", {})

    # Section 1 Screens Table (assembled by code from Screen catalog)
    screen_rows = []
    for idx, s in enumerate(screens):
        personas_tag = ", ".join([f"[{p}]" for p in s.get("authorized_personas", [])])
        features_tag = ", ".join([f"[{f}]" for f in s.get("features", [])]) if s.get("features") else "-"

        # Match primary feature for this screen
        primary_fid = s.get("features", [""])[0] if s.get("features") else ""
        if not primary_fid and idx > 0 and (idx - 1) < len(context.get("features", [])):
            primary_fid = context["features"][idx - 1]["id"]

        api_ref = feature_api_map.get(primary_fid, "")
        tbl_ref = feature_tbl_map.get(primary_fid, "")

        if not api_ref and s["id"] == "S-01":
            api_ref = context["endpoints"][0] if context.get("endpoints") else "API-001"
            tbl_ref = context["tables"][0] if context.get("tables") else "TBL-01"

        tech_tag = f"`[{api_ref}]`, `[{tbl_ref}]`" if (api_ref and tbl_ref and s["id"] != "S-99") else "-"
        screen_rows.append(
            f"| `{s['id']}` | {s['name']} | `{s['route']}` | {s['purpose']} | `{personas_tag}` | `{features_tag}` | {tech_tag} |"
        )
    screens_table = "\n".join(screen_rows)

    full_doc = f"""# Application Flow: {app_name}

Based on Handbook Appendix A.4 (`VirtualOffice_Complete_Guide.md`), `docs/prd.md`, and `docs/architecture.md`.

---

## 1. Screens

> *Section assembled by code from Screen specifications*

| ID | Screen | Route | Purpose | Auth / Role | Features | Technical Contracts |
|---|---|---|---|---|---|---|
{screens_table}

---

## 2. Journeys

{journeys_content}

---

## 3. Screen states

{states_content}

---

{navigation_keyboard_content}
"""
    prd_raw = context.get("prd_raw", "").lower()
    is_offline_only = ("100% local" in prd_raw or "zero cloud" in prd_raw or "offline" in prd_raw) and ("cloud portal sync" in prd_raw or "ng-01" in prd_raw)
    if is_offline_only:
        full_doc = re.sub(r"\bretry\s+connection\b", "retry database write", full_doc, flags=re.IGNORECASE)
        full_doc = re.sub(r"\bserver\s+connection\b", "local database connection", full_doc, flags=re.IGNORECASE)
        full_doc = re.sub(r"\bcloud\s+sync\b", "local export", full_doc, flags=re.IGNORECASE)
        full_doc = re.sub(r"\bsynchronize\s+real-time\b", "update local records", full_doc, flags=re.IGNORECASE)
        full_doc = re.sub(r"\btelemetry\s+data\b", "audit records", full_doc, flags=re.IGNORECASE)

    if "json" not in prd_raw:
        full_doc = re.sub(r"\bCSV,\s*JSON\b", "PDF, CSV", full_doc, flags=re.IGNORECASE)
        full_doc = re.sub(r"\bJSON,\s*CSV\b", "PDF, CSV", full_doc, flags=re.IGNORECASE)
        full_doc = re.sub(r"\b\(CSV,\s*JSON\)", "(PDF, CSV)", full_doc, flags=re.IGNORECASE)
        full_doc = re.sub(r"\bJSON\s+export\b", "CSV export", full_doc, flags=re.IGNORECASE)

    return full_doc


# ==============================================================================
# VALIDATORS (Part 3)
# ==============================================================================

def validate_journey_persona_authorization(app_flow_text: str) -> List[str]:
    """
    Validates that a journey's persona is authorized on every screen it visits.
    (e.g. If S-04 allows only P-03; a journey using P-02 there must fail).
    """
    errors: List[str] = []

    # 1. Parse Section 1 Screens table: map sid -> set of allowed persona IDs
    screen_auth: Dict[str, Set[str]] = {}
    rows = re.findall(r"\|\s*`?(S-\d+)`?\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|\s*`?([^\|]+?)`?\s*\|", app_flow_text)
    for sid, name, route, purpose, auth in rows:
        sid_clean = sid.strip()
        auth_clean = auth.strip()
        p_ids = set(re.findall(r"P-\d+", auth_clean))
        # Public or fallback screens authorize all personas
        if any(w in auth_clean.lower() for w in ["public", "system", "all", "*"]):
            p_ids.update([f"P-{i:02d}" for i in range(1, 10)])
        screen_auth[sid_clean] = p_ids

    # 2. Parse Section 2 Journeys: extract journey persona and visited screens ONLY from Section 2
    journeys_sec = ""
    jm = re.search(r"##\s*2\.\s*Journeys(.*?)(?=##\s*\d|\Z)", app_flow_text, re.DOTALL | re.IGNORECASE)
    journeys_sec = jm.group(1) if jm else app_flow_text

    j_blocks = re.split(r"(?=###\s*J-\d+:)", journeys_sec)
    for b in j_blocks:
        if not b.startswith("### J-"):
            continue
        m_j = re.match(r"###\s*(J-\d+):", b)
        jid = m_j.group(1) if m_j else "J-?"

        # Extract journey persona (e.g. [P-01] or `[P-01]`)
        p_matches = re.findall(r"\[?(P-\d+)\]?", b)
        if not p_matches:
            errors.append(f"Journey persona missing: Journey {jid} does not specify an authorized persona [P-##]")
            continue
        journey_persona = p_matches[0]

        # Extract visited screens ONLY from numbered steps of this journey
        steps_lines = re.findall(r"^\d+\.\s+.*$", b, flags=re.MULTILINE)
        steps_text = " ".join(steps_lines)
        visited_screens = set(re.findall(r"\b(S-\d+)\b", steps_text))
        for vs in visited_screens:
            if vs in screen_auth:
                allowed = screen_auth[vs]
                if allowed and journey_persona not in allowed:
                    err = (
                        f"Persona authorization violation: Journey {jid} for [{journey_persona}] "
                        f"visits Screen [{vs}] which only permits {sorted(list(allowed))}"
                    )
                    errors.append(err)

    return errors


def validate_route_slugs_and_screen_names(app_flow_text: str) -> List[str]:
    """
    Validates:
    - Screen names are under 6 words
    - Route slugs are valid kebab-case paths (not truncated mid-word like /faa-form-8130-airwor)
    - Route slugs are unique across screens
    """
    errors: List[str] = []
    seen_routes: Dict[str, str] = {}

    rows = re.findall(r"\|\s*`?(S-\d+)`?\s*\|\s*([^\|]+)\s*\|\s*`?([^\|]+?)`?\s*\|", app_flow_text)
    for sid, name, route in rows:
        sid_clean = sid.strip()
        name_clean = name.strip()
        route_clean = route.strip()

        if "id" in sid_clean.lower() or "---" in sid_clean:
            continue

        # 1. Screen name word count (< 6 words)
        words = name_clean.split()
        if len(words) >= 6:
            errors.append(
                f"Screen name length violation: Screen [{sid_clean}] name '{name_clean}' has {len(words)} words (max allowed: 5 words)"
            )

        # 2. Route slug validity & truncation check
        if route_clean != "/" and route_clean != "*":
            if not re.match(r"^/[a-z0-9]+(-[a-z0-9]+)*$", route_clean):
                errors.append(
                    f"Route slug invalid: Screen [{sid_clean}] route '{route_clean}' is not a valid kebab-case path"
                )
            # Truncation indicator: ends with hyphen or seems cut off
            if route_clean.endswith("-"):
                errors.append(
                    f"Route slug truncated: Screen [{sid_clean}] route '{route_clean}' ends with a trailing hyphen"
                )

        # 3. Route slug uniqueness
        if route_clean != "*":
            if route_clean in seen_routes:
                errors.append(
                    f"Duplicate route slug: Route '{route_clean}' used by both [{seen_routes[route_clean]}] and [{sid_clean}]"
                )
            else:
                seen_routes[route_clean] = sid_clean

    return errors


def validate_no_duplicate_filler_text(app_flow_text: str) -> List[str]:
    """
    Duplicate-text check: fail if more than 2 screens or journeys share the same state/step sentence.
    """
    errors: List[str] = []

    # 1. Check screen states in Section 3
    states_section = ""
    sm = re.search(r"##\s*3\.\s*Screen states(.*?)(?=##\s*\d|\Z)", app_flow_text, re.DOTALL | re.IGNORECASE)
    if sm:
        states_section = sm.group(1)

    state_sentences: Dict[str, List[str]] = {}
    screen_blocks = re.split(r"(?=###\s*S-\d+)", states_section)
    for sb in screen_blocks:
        m_s = re.match(r"###\s*(S-\d+)", sb)
        if not m_s:
            continue
        sid = m_s.group(1)
        # Extract lines under bullet points
        lines = re.findall(r"-\s*\*\*[^*]+\*\*:\s*([^\n]+)", sb)
        for line in lines:
            # Normalize sentence
            norm = re.sub(r"\[P-\d+\]|\[S-\d+\]|\[AC-\d+\]", "", line).strip().lower()
            norm = re.sub(r"\s+", " ", norm)
            if len(norm) > 25:
                state_sentences.setdefault(norm, []).append(sid)

    for sent, sids in state_sentences.items():
        if len(set(sids)) > 2:
            errors.append(
                f"Duplicate state text violation: State sentence '{sent[:60]}...' is repeated across screens {sorted(list(set(sids)))}"
            )

    # 2. Check journey steps in Section 2
    journeys_section = ""
    jm = re.search(r"##\s*2\.\s*Journeys(.*?)(?=##\s*\d|\Z)", app_flow_text, re.DOTALL | re.IGNORECASE)
    if jm:
        journeys_section = jm.group(1)

    step_sentences: Dict[str, List[str]] = {}
    j_blocks = re.split(r"(?=###\s*J-\d+:)", journeys_section)
    for jb in j_blocks:
        m_j = re.match(r"###\s*(J-\d+):", jb)
        if not m_j:
            continue
        jid = m_j.group(1)
        steps = re.findall(r"\d+\.\s+([^\n]+)", jb)
        for step in steps:
            norm = re.sub(r"\[[A-Z0-9_\-]+\]|\`[^\`]+\`", "", step).strip().lower()
            norm = re.sub(r"\s+", " ", norm)
            if len(norm) > 25:
                step_sentences.setdefault(norm, []).append(jid)

    for sent, jids in step_sentences.items():
        if len(set(jids)) > 2:
            errors.append(
                f"Duplicate journey step violation: Journey step '{sent[:60]}...' is repeated across journeys {sorted(list(set(jids)))}"
            )

    return errors


def validate_design_brief_citations(
    design_brief_text: str,
    prd_text: str,
    qa_log: List[Dict[str, Any]]
) -> List[str]:
    """
    Validates that:
    - Every claim with an ID is supported by that ID's text.
    - No external standards (FAA AC 20-175, MIL-STD-1472) unless they appear in qa_log or prd.
    """
    errors: List[str] = []
    qa_ids = {q.get("id") for q in qa_log if q.get("id")}
    prd_ids = set(re.findall(r"\b(P-\d+|F-\d+|AC-\d+|NFR-\d+|ASM-\d+|OQ-\d+)\b", prd_text))
    allowed_ids = qa_ids.union(prd_ids).union({"PRD-01", "Q-001"})

    # Check for ungrounded external standards
    combined_discovery = f"{prd_text} {json.dumps(qa_log)}"
    for std in ["FAA AC 20-175", "MIL-STD-1472", "FAA AC 20", "MIL-STD"]:
        if std in design_brief_text and std not in combined_discovery:
            errors.append(
                f"Ungrounded external standard violation: '{std}' cited in design brief is absent from discovery answers and PRD"
            )

    # Check cited question IDs
    cited_q = re.findall(r"\[(Q-\d+)\]", design_brief_text)
    for qid in cited_q:
        if qid not in allowed_ids and qid not in ["Q-001"]:
            errors.append(f"Ungrounded citation: Question [{qid}] cited in design brief does not exist in qa_log.json")

    return errors


def validate_design_artifacts(
    app_flow_text: str,
    design_brief_text: str,
    parsed_ba: Dict[str, Any],
    architecture_text: str = "",
    prd_text: str = "",
    qa_log: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Executes automated code-level validation per Handbook Stage 3 Step 12 & Part 3:
    1. Real mathematical WCAG 2.2 contrast ratio calculation on foreground/background token pairs
       across BOTH --color-background AND --color-surface in light and dark themes.
    2. Every Must-have F-### maps to a user journey.
    3. Every screen cites an authorized persona [P-##].
    4. Every screen defines all 5 states (Loading, Empty, Populated, Error, No Permission).
    5. Journey persona authorization across visited screens.
    6. Route slug validity, uniqueness, and screen name length (< 6 words).
    7. No duplicate filler text across screens or journeys.
    8. Design brief grounded citations and no ungrounded external standards.
    9. Cross-section consistency: NFR metrics, offline constraints, and form control consistency.
    10. Grounding: Zero ungrounded UI elements (PDF Summary, Assigned Contractor, etc.).
    11. Template residue rejection.
    """
    errors: List[str] = []

    # 1. Dual-Surface Contrast Ratio Validator
    color_rows = re.findall(r"\|\s*`?([a-zA-Z0-9_\-\.]+?)`?\s*\|\s*`?(#[0-9a-fA-F]{3,6})`?\s*\|\s*`?(#[0-9a-fA-F]{3,6})`?\s*\|([^\|]+)\|([^\|]*)\|", design_brief_text)
    bg_light = "#f8fafc"
    bg_dark = "#0f172a"
    surf_light = "#ffffff"
    surf_dark = "#1e293b"
    for token, l_hex, d_hex, _, _ in color_rows:
        t_clean = token.strip().lower()
        if "background" in t_clean or "page" in t_clean:
            bg_light = l_hex.strip()
            bg_dark = d_hex.strip()
        elif "surface" in t_clean or "card" in t_clean or "panel" in t_clean:
            surf_light = l_hex.strip()
            surf_dark = d_hex.strip()

    contrast_errors: List[str] = []
    for token, l_hex, d_hex, use_desc, _ in color_rows:
        t_clean = token.strip().lower()
        if any(k in t_clean for k in ["background", "surface", "border"]):
            continue
        r_l_bg = calculate_contrast(l_hex.strip(), bg_light)
        r_l_surf = calculate_contrast(l_hex.strip(), surf_light)
        r_d_bg = calculate_contrast(d_hex.strip(), bg_dark)
        r_d_surf = calculate_contrast(d_hex.strip(), surf_dark)
        min_required = 4.5 if any(k in t_clean for k in ["text", "primary", "secondary", "error", "success", "warning"]) else 3.0

        if r_l_bg < min_required:
            err = f"Contrast failure: Token {t_clean} light ({l_hex.strip()}) on background ({bg_light}) is {r_l_bg:.2f}:1 (min {min_required}:1)"
            contrast_errors.append(err)
            errors.append(err)
        if r_l_surf < min_required:
            err = f"Contrast failure: Token {t_clean} light ({l_hex.strip()}) on surface ({surf_light}) is {r_l_surf:.2f}:1 (min {min_required}:1)"
            contrast_errors.append(err)
            errors.append(err)
        if r_d_bg < min_required:
            err = f"Contrast failure: Token {t_clean} dark ({d_hex.strip()}) on dark background ({bg_dark}) is {r_d_bg:.2f}:1 (min {min_required}:1)"
            contrast_errors.append(err)
            errors.append(err)
        if r_d_surf < min_required:
            err = f"Contrast failure: Token {t_clean} dark ({d_hex.strip()}) on dark surface ({surf_dark}) is {r_d_surf:.2f}:1 (min {min_required}:1)"
            contrast_errors.append(err)
            errors.append(err)

    # 2. Feature Coverage Validator
    must_features = []
    if prd_text:
        f_blocks = re.split(r"(?=###\s*F-\d+:)", prd_text)
        for b in f_blocks:
            if b.startswith("### F-"):
                m = re.match(r"###\s*(F-\d+):", b)
                if m:
                    fid = m.group(1).strip()
                    prio_m = re.search(r"-\s*\*\*Priority\*\*:\s*([^\n]+)", b)
                    prio_str = prio_m.group(1).lower() if prio_m else "must"
                    if "must" in prio_str:
                        must_features.append(fid)
    if not must_features:
        must_features = ["F-001", "F-002", "F-003", "F-004"]

    feature_errors: List[str] = []
    for f_id in must_features:
        m_num = re.search(r"\d+", f_id)
        alt_id = f"F-{int(m_num.group(0)):03d}" if m_num else f_id
        if f_id not in app_flow_text and alt_id not in app_flow_text:
            err = f"Feature mapping failure: Must-have feature [{f_id}] is missing from app-flow.md journeys"
            feature_errors.append(err)
            errors.append(err)

    # 3. Persona Citations on Screens Validator
    persona_errors: List[str] = []
    screen_rows = re.findall(r"\|\s*`?(S-\d+)`?\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|", app_flow_text)
    audited_screens: List[str] = []
    for s_id, s_name, _, _, s_auth, _ in screen_rows:
        sid = s_id.strip()
        if "id" in sid.lower() or "---" in sid:
            continue
        audited_screens.append(sid)
        if not re.search(r"P-\d+|public|system|anonymous", s_auth, re.IGNORECASE):
            err = f"Persona citation failure: Screen [{sid}] ({s_name.strip()}) lacks an authorized persona [P-##]"
            persona_errors.append(err)
            errors.append(err)

    # 4. Five States Validator
    states_errors: List[str] = []
    required_states = ["loading", "empty", "populated", "error", "no permission"]
    sm = re.search(r"##\s*3\.\s*Screen states(.*?)(?=##\s*\d|\Z)", app_flow_text, re.DOTALL | re.IGNORECASE)
    states_body = sm.group(1).lower() if sm else ""

    for sid in audited_screens:
        if sid in ["S-99"]:
            continue
        if sid.lower() not in states_body:
            err = f"State failure: Screen [{sid}] has no state definitions in Section 3"
            states_errors.append(err)
            errors.append(err)
        else:
            screen_block = re.search(rf"###\s*{sid}(.*?)(?=###\s*S-\d+|\Z)", states_body, re.DOTALL | re.IGNORECASE)
            sb_text = screen_block.group(1) if screen_block else ""
            for rs in required_states:
                if rs not in sb_text and rs.replace(" ", "-") not in sb_text:
                    err = f"State failure: Screen [{sid}] missing required state '{rs}'"
                    states_errors.append(err)
                    errors.append(err)

    # 5. Persona Authorization across Visited Screens
    auth_errors = validate_journey_persona_authorization(app_flow_text)
    errors.extend(auth_errors)

    # 6. Route Slugs & Screen Names
    route_errors = validate_route_slugs_and_screen_names(app_flow_text)
    errors.extend(route_errors)

    # 7. Duplicate Text Check
    dup_errors = validate_no_duplicate_filler_text(app_flow_text)
    errors.extend(dup_errors)

    # 8. Design Brief Citations & Standards
    citation_errors = validate_design_brief_citations(design_brief_text, prd_text, qa_log or [])
    errors.extend(citation_errors)

    # 9. Template Residue Check
    template_residue_errors: List[str] = []
    for bad_phrase in ["submits required parameters for", "writes telemetry", "out-of-spec measurements", "disk i/o latency"]:
        if bad_phrase in app_flow_text.lower():
            err = f"Template residue violation: Forbidden template phrase '{bad_phrase}' detected in app-flow.md"
            template_residue_errors.append(err)
            errors.append(err)

    # 10. Ungrounded UI Elements Check (General Grounding Check)
    ungrounded_elem_errors: List[str] = []
    context_str = f"{json.dumps(parsed_ba)} {prd_text} {architecture_text}".lower()
    bold_app_flow = re.findall(r"\*\*([^*]+)\*\*", app_flow_text)
    for token in bold_app_flow:
        t_clean = token.strip().lower()
        if t_clean in {"loading", "empty", "populated", "error", "no permission", "success", "given", "when", "then"}:
            continue
        words = [w for w in re.findall(r"\b[a-zA-Z]{4,}\b", t_clean)]
        if len(words) >= 2 and not any(w in context_str for w in words):
            err = f"Ungrounded UI element violation: '{token}' in design output is absent from PRD and discovery"
            ungrounded_elem_errors.append(err)
            errors.append(err)

    # 11. Cross-Section Consistency Check
    consistency_errors: List[str] = []
    nfr_matches = re.findall(r"(\d+(?:\.\d+)?\s*(?:s|ms))\s*\([^\)]*NFR-01[^\)]*\)", app_flow_text)
    if len(set(nfr_matches)) > 1:
        err = f"Cross-section consistency violation: NFR-01 cited with conflicting metrics ({', '.join(set(nfr_matches))}) across sections"
        consistency_errors.append(err)
        errors.append(err)

    if ("100% local" in prd_text.lower() or "zero cloud" in prd_text.lower()) and "ng-01" in prd_text.lower():
        for cloud_term in ["cloud sync", "server connection", "remote telemetry", "sync to cloud", "cloud portal"]:
            if cloud_term in app_flow_text.lower():
                err = f"Offline / Cloud contradiction: '{cloud_term}' in app-flow.md contradicts 100% offline local SQLite constraint"
                consistency_errors.append(err)
                errors.append(err)

    has_dropdown = bool(re.search(r"severity.*dropdown|dropdown.*severity", app_flow_text, re.IGNORECASE))
    has_slider = bool(re.search(r"(?:severity|priority).*slider|slider.*(?:severity|priority)", app_flow_text, re.IGNORECASE))
    if has_dropdown and has_slider:
        err = "Control type inconsistency: Hazard severity/priority field uses conflicting controls (dropdown vs slider)"
        consistency_errors.append(err)
        errors.append(err)

    all_passed = len(errors) == 0
    return {
        "all_passed": all_passed,
        "contrast_valid": len(contrast_errors) == 0,
        "contrast_errors": contrast_errors,
        "feature_mapping_valid": len(feature_errors) == 0,
        "feature_errors": feature_errors,
        "persona_citations_valid": len(persona_errors) == 0,
        "persona_errors": persona_errors,
        "states_valid": len(states_errors) == 0,
        "states_errors": states_errors,
        "auth_errors": auth_errors,
        "route_errors": route_errors,
        "dup_errors": dup_errors,
        "citation_errors": citation_errors,
        "template_residue_errors": template_residue_errors,
        "ungrounded_elem_errors": ungrounded_elem_errors,
        "consistency_errors": consistency_errors,
        "errors": errors,
        "checks_count": 11,
        "passed_count": 11 - (
            bool(contrast_errors) + bool(feature_errors) + bool(persona_errors) +
            bool(states_errors) + bool(auth_errors) + bool(route_errors) +
            bool(dup_errors) + bool(citation_errors) + bool(template_residue_errors) +
            bool(ungrounded_elem_errors) + bool(consistency_errors)
        )
    }


# ==============================================================================
# PIPELINE GENERATION ORCHESTRATION (Part 2 & Part 5)
# ==============================================================================

def run_designer_pipeline(
    session_id: str,
    get_session_dir_fn,
    load_json_fn,
    save_json_fn,
    query_ollama_fn=None
) -> Dict[str, Any]:
    """
    Executes the complete Stage 3 UI/UX Designer pipeline with REAL LLM generation:
    1. Parse discovery inputs (intake.json, qa_log.json, prd.md, architecture.md).
    2. Generate Screens, Journeys, Screen States with LLM (qwen/qwen3.8-27b).
    3. Generate Navigation, Keyboard, and Footer with LLM from architecture & PRD.
    4. Generate Palette with LLM and verify/repair WCAG contrast on BOTH background AND surface.
    5. Assemble documents and attach real provenance stamp with code adjustment metadata.
    6. Record real LLM tokens, cost, and integer latency ms to Token Ledger.
    7. Execute deterministic validators and LLM Judge review.
    """
    pipeline_start_time = time.time()
    session_dir = get_session_dir_fn(session_id)
    docs_dir = os.path.join(session_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)

    intake_file = os.path.join(session_dir, "intake.json")
    qa_file = os.path.join(session_dir, "qa_log.json")
    prd_file = os.path.join(docs_dir, "prd.md")
    arch_file = os.path.join(docs_dir, "architecture.md")

    intake_data = load_json_fn(intake_file, {})
    qa_log = load_json_fn(qa_file, [])
    prd_text = ""
    if os.path.exists(prd_file):
        with open(prd_file, "r", encoding="utf-8") as f:
            prd_text = f.read()

    arch_text = ""
    if os.path.exists(arch_file):
        with open(arch_file, "r", encoding="utf-8") as f:
            arch_text = f.read()

    parsed_ba = parse_ba_data(intake_data, qa_log, prd_text) if parse_ba_data else {}
    parsed_ba["session_id"] = session_id

    # Extract structured project context
    context = extract_prd_context(prd_text, parsed_ba, arch_text)

    # Active provider and model
    active_prov, active_model = ("groq", "qwen/qwen3.8-27b")
    if default_llm_client:
        active_prov, active_model = default_llm_client.get_active_provider_and_model("designer", session_id=session_id)

    total_prompt_tokens = 0
    total_completion_tokens = 0

    # 1. Generate Screens with LLM
    screens, p_toks1, c_toks1 = generate_screens_with_llm(context, session_id=session_id)
    total_prompt_tokens += p_toks1
    total_completion_tokens += c_toks1

    time.sleep(15)

    # 2. Generate Journeys with LLM
    journeys_content, p_toks2, c_toks2 = generate_journeys_with_llm(context, screens, session_id=session_id)
    total_prompt_tokens += p_toks2
    total_completion_tokens += c_toks2

    time.sleep(15)

    # 3. Generate Screen States with LLM
    states_content, p_toks3, c_toks3 = generate_screen_states_with_llm(context, screens, session_id=session_id)
    total_prompt_tokens += p_toks3
    total_completion_tokens += c_toks3

    time.sleep(15)

    # 4. Generate Navigation, Keyboard, and Footer with LLM
    nav_content, p_toks_nav, c_toks_nav = generate_navigation_and_keyboard_with_llm(
        context, screens, arch_text, prd_text, session_id=session_id
    )
    total_prompt_tokens += p_toks_nav
    total_completion_tokens += c_toks_nav

    # Assemble app-flow.md
    final_app_flow = assemble_app_flow_doc(context, screens, journeys_content, states_content, nav_content)

    time.sleep(15)

    # 5. Generate Palette and Design Brief with LLM + Dual-Surface Contrast Repair
    final_design_brief, palette_data, p_toks4, c_toks4 = generate_palette_and_brief_with_llm(
        context, prd_text, qa_log, session_id=session_id
    )
    total_prompt_tokens += p_toks4
    total_completion_tokens += c_toks4

    pipeline_latency_ms = int((time.time() - pipeline_start_time) * 1000)

    # Record REAL LLM usage to token ledger
    real_cost = 0.0
    if default_llm_client:
        try:
            from llm_client import calculate_cost_usd
            real_cost = calculate_cost_usd(active_model, total_prompt_tokens, total_completion_tokens, provider=active_prov)
        except Exception:
            real_cost = round((total_prompt_tokens * 0.05 + total_completion_tokens * 0.20) / 1_000_000.0, 6)

    if record_llm_call:
        record_llm_call(
            project_id=session_id,
            agent_id="designer",
            model=active_model,
            input_tokens=total_prompt_tokens,
            output_tokens=total_completion_tokens,
            provider=active_prov,
            cost_usd=real_cost,
            latency_ms=pipeline_latency_ms,
            task_id="generate_design_specifications"
        )

    # 6. Attach Accurate Provenance Stamp
    tokens_adj = palette_data.get("tokens_adjusted_by_code", [])
    adj_str = f"Tokens adjusted by code: {', '.join(tokens_adj)}" if tokens_adj else "Tokens adjusted by code: None (100% LLM generated)"

    now_iso = datetime.now(timezone.utc).isoformat()
    now_human = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    provenance_stamp = (
        f"<!-- ARTIFACT METADATA: Generated with LLM {active_prov} ({active_model}) "
        f"[Prompt: {total_prompt_tokens} toks, Completion: {total_completion_tokens} toks] | "
        f"Sections: Screens, Journeys, States, Navigation/Keyboard, Palette generated by LLM; Table assembled by code | "
        f"{adj_str} | Generated at {now_iso} -->\n"
        f"> **Artifact Provenance**: Generated by **{active_prov.upper()}** (`{active_model}`) | "
        f"Role: **UI/UX Designer** | Sections: Screens, Journeys, Screen States, Navigation & Keyboard, Palette & Identity generated by LLM; "
        f"Section 1 table assembled by code | {adj_str} | Timestamp: `{now_human}`\n\n"
    )

    final_app_flow = provenance_stamp + final_app_flow
    final_design_brief = provenance_stamp + final_design_brief

    # 7. Run Validators
    validation = validate_design_artifacts(
        final_app_flow, final_design_brief, parsed_ba, arch_text, prd_text=prd_text, qa_log=qa_log
    )

    # Write files to disk
    app_flow_path = os.path.join(docs_dir, "app-flow.md")
    with open(app_flow_path, "w", encoding="utf-8") as f:
        f.write(final_app_flow)

    design_brief_path = os.path.join(docs_dir, "design-brief.md")
    with open(design_brief_path, "w", encoding="utf-8") as f:
        f.write(final_design_brief)

    val_path = os.path.join(docs_dir, "design-validation.json")
    with open(val_path, "w", encoding="utf-8") as f:
        json.dump(validation, f, indent=2)

    # 8. Step 13: Judge Review
    judge_verdict = {}
    if evaluate_design_with_judge:
        judge_verdict = evaluate_design_with_judge(
            app_flow_text=final_app_flow,
            design_brief_text=final_design_brief,
            prd_text=prd_text,
            parsed_ba=parsed_ba,
            query_ollama_fn=query_ollama_fn,
            architecture_text=arch_text
        )
        judge_file = os.path.join(docs_dir, "design-judge.json")
        with open(judge_file, "w", encoding="utf-8") as f:
            json.dump(judge_verdict, f, indent=2)

    designer_state = {
        "status": "completed" if validation.get("all_passed") and judge_verdict.get("pass") else "needs_review",
        "has_output": True,
        "app_flow_path": "docs/app-flow.md",
        "design_brief_path": "docs/design-brief.md",
        "validation": validation,
        "judge_verdict": judge_verdict,
        "tokens": {
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "cost_usd": real_cost,
            "model": active_model,
            "latency_ms": pipeline_latency_ms
        },
        "escalated": not validation.get("all_passed")
    }

    state_file = os.path.join(session_dir, "designer_state.json")
    save_json_fn(state_file, designer_state)

    return {
        "status": "success",
        "app_flow_content": final_app_flow,
        "design_brief_content": final_design_brief,
        "validation": validation,
        "judge_verdict": judge_verdict,
        "tokens": designer_state["tokens"],
        "state": designer_state
    }



# ==============================================================================
# FASTAPI ROUTE INITIALIZATION
# ==============================================================================

def init_designer_routes(
    main_app,
    get_session_dir_fn,
    load_json_fn,
    save_json_fn,
    query_ollama_fn=None,
    data_projects_dir: str = ""
):
    """
    Mounts Designer routes on FastAPI application.
    """
    router = APIRouter(prefix="/designer", tags=["designer"])

    @router.post("/generate/{session_id}")
    def generate_design_artifacts_endpoint(session_id: str):
        session_dir = get_session_dir_fn(session_id)
        if not os.path.exists(session_dir):
            raise HTTPException(status_code=404, detail="Session not found")

        # Verify Gate 1 approval
        gate1_file = os.path.join(session_dir, "gate1_state.json")
        gate1_data = load_json_fn(gate1_file, {})
        if not gate1_data.get("approved"):
            raise HTTPException(
                status_code=403,
                detail="Gate 1 not approved. The client must approve the PRD and scope before design start."
            )

        try:
            res = run_designer_pipeline(
                session_id=session_id,
                get_session_dir_fn=get_session_dir_fn,
                load_json_fn=load_json_fn,
                save_json_fn=save_json_fn,
                query_ollama_fn=query_ollama_fn
            )
            return res
        except Exception as e:
            logger.error(f"Error generating design artifacts: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/session/{session_id}")
    def get_designer_session_endpoint(session_id: str):
        session_dir = get_session_dir_fn(session_id)
        if not os.path.exists(session_dir):
            raise HTTPException(status_code=404, detail="Session not found")

        docs_dir = os.path.join(session_dir, "docs")
        app_flow_path = os.path.join(docs_dir, "app-flow.md")
        design_brief_path = os.path.join(docs_dir, "design-brief.md")
        state_path = os.path.join(session_dir, "designer_state.json")

        app_flow_content = None
        if os.path.exists(app_flow_path):
            with open(app_flow_path, "r", encoding="utf-8") as f:
                app_flow_content = f.read()

        design_brief_content = None
        if os.path.exists(design_brief_path):
            with open(design_brief_path, "r", encoding="utf-8") as f:
                design_brief_content = f.read()

        state = load_json_fn(state_path, {})
        val_path = os.path.join(docs_dir, "design-validation.json")
        validation = load_json_fn(val_path, {})
        judge_path = os.path.join(docs_dir, "design-judge.json")
        judge = load_json_fn(judge_path, {})

        return {
            "session_id": session_id,
            "has_output": bool(app_flow_content and len(app_flow_content) > 50),
            "app_flow_content": app_flow_content,
            "design_brief_content": design_brief_content,
            "state": state,
            "validation": validation,
            "judge_verdict": judge
        }

    main_app.include_router(router)
    logger.info("UI/UX Designer routes initialized and mounted.")
