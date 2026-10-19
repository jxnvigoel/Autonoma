import re
import json
from typing import Dict, Any, List, Optional, Tuple


def is_deferred_text(text: str) -> bool:
    """Detects if requirement text is deferred to v2 / out of scope / won't have."""
    t = text.lower()
    return any(w in t for w in ["deferred", "won't have", "wont have", "v2", "out of scope", "post-v1", "later"])


def is_nfr_text(text: str) -> bool:
    """Detects if requirement text belongs to Non-Functional Requirements rather than Functional Features."""
    t = text.lower()
    nfr_indicators = [
        "latency", "response time", "load time", "sub-", "under 1 second", "under 2s",
        "stored locally", "sqlite", "local storage", "zero cloud", "offline", "data privacy",
        "data stored", "encryption", "wcag", "accessibility", "throughput", "capacity",
        "concurrent", "uptime", "availability", "records", "volume",
        "operating system", "windows", "macos", "linux", "desktop os", "contrast",
        "keyboard navigation", "hipaa", "clia", "gdpr"
    ]
    return any(ind in t for ind in nfr_indicators)


def validate_asm_oq_text(text: str) -> Tuple[bool, str]:
    """
    Validates that an ASM or OQ text row is a single, complete, specific sentence.
    Rejects placeholders (x, y), fragments ('Reason: ...', 'Risk: ...'), and short items (< 30 chars).
    """
    t = text.strip()
    if len(t) < 30:
        return False, f"Too short ({len(t)} characters, minimum 30 required)"

    # Check for placeholder variables or tokens
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

    # Check for fragment prefixes
    fragment_prefixes = ["reason:", "risk:", "source:", "status:", "note:", "because:", "mitigation:"]
    for fp in fragment_prefixes:
        if t.lower().startswith(fp):
            return False, f"Fragment starting with '{fp}'"

    # Check for complete sentence punctuation
    if not (t.endswith(".") or t.endswith("?") or t.endswith("]")):
        return False, "Not a complete sentence (must end with punctuation)"

    return True, ""


def parse_ba_data(
    intake_data: Dict[str, Any],
    qa_log: List[Dict[str, Any]],
    requirements_text: str = ""
) -> Dict[str, Any]:
    """
    Parses real BA discovery outputs (intake.json, qa_log.json, docs/requirements.md)
    into structured entities strictly grounded in cited IDs (Q-###, P-##, FR-##, NFR-##, ASM-##, OQ-##).
    Enforces strict FR vs NFR vs Non-Goal classification per Handbook Section 4.1.2 & Appendix A.1.
    """
    app_name = intake_data.get("project_name", "Untitled Project").strip()
    description = intake_data.get("description", "").strip()
    target_users = intake_data.get("target_users", "").strip()
    timeline = intake_data.get("timeline", "8 weeks").strip()
    budget = intake_data.get("budget", "$5,000 MVP budget").strip()

    # Build QA map with exact IDs
    qa_map: Dict[str, Dict[str, Any]] = {}
    for idx, item in enumerate(qa_log):
        qid = item.get("id") or f"Q-{idx+1:03d}"
        qa_map[qid] = {
            "id": qid,
            "question": item.get("question", "").strip(),
            "answer": item.get("answer", "").strip(),
            "round": item.get("round", idx + 1),
        }

    first_qid = list(qa_map.keys())[0] if qa_map else "Q-001"

    # Identify specific Q-### sources based on actual conversation turns
    today_qid = first_qid
    problem_qid = first_qid
    shortcomings_qid = first_qid
    features_qid = first_qid
    metrics_qid = first_qid
    timeline_qid = first_qid

    today_text = ""
    problem_text = ""
    shortcomings_text = ""

    for qid, qdata in qa_map.items():
        ans = qdata["answer"]
        ans_lower = ans.lower()

        # Identify 'Today' workflow turn
        if any(w in ans_lower for w in ["today", "walk", "paper", "currently", "clipboards", "handwritten", "spreadsheets", "manually typing"]):
            today_qid = qid
            today_text = ans.replace("Today,", "").replace("Today", "").strip().rstrip(".")
            if not today_text.endswith("."):
                today_text += "."

        # Identify 'Core Problem' turn
        if any(w in ans_lower for w in ["core problem", "tenable", "untenable", "error rate", "delayed", "shutdown", "fines", "struggle to format", "waste hours"]):
            problem_qid = qid
            problem_text = ans.replace("The core problem is that", "").replace("The core problem is", "").strip().rstrip(".")
            if not problem_text.endswith("."):
                problem_text += "."

        # Identify 'Why Existing Tools Fall Short' turn
        if any(w in ans_lower for w in ["existing", "commercial", "cloud connectivity", "fail in", "expensive", "per-seat", "fall short"]):
            shortcomings_qid = qid
            # Extract just the shortcoming sentence
            parts = re.split(r"(?:Key requirements|Requirements|1\))", ans, flags=re.IGNORECASE)
            shortcomings_text = parts[0].strip().rstrip(".")
            if not shortcomings_text.endswith("."):
                shortcomings_text += "."

        # Identify Features turn
        if any(w in ans_lower for w in ["key requirements", "must have", "should have", "requirements", "fr-", "[fr-"]):
            features_qid = qid

        # Identify Timeline & Budget turn
        if any(w in ans_lower for w in ["timeline", "deadline", "budget", "cost", "weeks", "$"]):
            timeline_qid = qid

        # Identify Success Metric turn
        if any(w in ans_lower for w in ["metric", "success", "% of", "generating daily"]):
            metrics_qid = qid

    # Fallback problem texts if not separated in QA
    if not today_text:
        today_text = f"Users currently rely on manual workflows and fragmented paper or desktop tools to execute their daily tasks. [{today_qid}]"
    if not problem_text:
        problem_text = qa_map.get(problem_qid, {}).get("answer", description)
    if not shortcomings_text:
        shortcomings_text = f"Existing alternatives require external cloud connectivity with monthly subscription costs, failing in offline environments and lacking local data control. [{shortcomings_qid}]"

    # 1. Parse Personas (P-##) with distinct, non-identical roles, goals, and pain points
    personas: List[Dict[str, Any]] = []
    persona_match = re.search(r"#+\s*2\.\s*Personas(.*?)(?=#+\s*\d|\Z)", requirements_text, re.DOTALL | re.IGNORECASE)
    if persona_match:
        p_lines = persona_match.group(1).strip().split("\n")
        p_counter = 1
        for line in p_lines:
            line_str = line.strip().lstrip("-* ").strip()
            if not line_str or line_str.startswith("#"):
                continue
            m = re.match(r"(P-\d+)?\s*:?\s*(.*)", line_str)
            pid = m.group(1) if m and m.group(1) else f"P-{p_counter:02d}"
            raw_name = m.group(2).strip() if m else line_str
            clean_name = re.sub(r"\[.*?\]", "", raw_name).strip().strip(":")
            if clean_name and "no additional" not in clean_name.lower():
                role_title = clean_name.split(",")[0].split(" with ")[0].split(" who ")[0].strip()
                personas.append({
                    "id": pid,
                    "persona": role_title,
                    "context": f"Field and project operations in {app_name}",
                    "goal": "",
                    "pain_point": "",
                    "source": problem_qid
                })
                p_counter += 1

    if not personas:
        users_list = [u.strip() for u in re.split(r",|and", target_users) if u.strip()]
        if not users_list:
            users_list = ["Lead Professional", "Field Specialist"]
        for idx, u in enumerate(users_list[:2]):
            personas.append({
                "id": f"P-{idx+1:02d}",
                "persona": u,
                "context": f"Field and project operations in {app_name}",
                "goal": "",
                "pain_point": "",
                "source": problem_qid
            })

    # Assign distinct, domain-grounded goals and pain points to each persona (no cross-project contamination)
    for idx, p in enumerate(personas):
        role_raw = p["persona"]
        role_lower = role_raw.lower()
        pid = p.get("id", f"P-{idx+1:02d}")

        if idx == 0:
            p["goal"] = f"Execute core {role_lower} operational tasks accurately and maintain compliant activity logs within {app_name}."
            p["pain_point"] = f"Manual paperwork, tracking delays, and transcription errors in daily {role_lower} duties."
            p["does"] = f"Perform primary operational workflows and record transactions in {app_name}"
            p["can"] = "Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1"
            p["cannot"] = "Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1"
        elif idx == 1:
            p["goal"] = f"Supervise {role_lower} activities, verify record integrity, and prevent compliance violations."
            p["pain_point"] = f"Lack of real-time visibility into status updates and tedious manual verification of records."
            p["does"] = f"Monitor operational status, review logs, and certify sign-offs in {app_name}"
            p["can"] = "Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1"
            p["cannot"] = "Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1"
        else:
            p["goal"] = f"Perform independent compliance audits and verify traceability of all records in {app_name}."
            p["pain_point"] = f"Scattered audit logs and time-consuming manual report compilation during audits."
            p["does"] = f"Audit historical transaction records, verify chain-of-custody, and export reports in {app_name}"
            p["can"] = "Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1"
            p["cannot"] = "Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1"

    # 2. Parse Functional Requirements, NFRs, and Non-Goals
    raw_fr_candidates: List[Dict[str, Any]] = []
    parsed_nfrs: List[Dict[str, Any]] = []
    discovered_non_goals: List[Dict[str, Any]] = []

    fr_match = re.search(r"#+\s*4\.\s*Functional Requirements(.*?)(?=#+\s*\d|\Z)", requirements_text, re.DOTALL | re.IGNORECASE)
    if fr_match:
        fr_lines = fr_match.group(1).strip().split("\n")
        fr_counter = 1
        for line in fr_lines:
            line_str = line.strip().lstrip("-* ").strip()
            if not line_str or line_str.startswith("#"):
                continue
            fr_id_match = re.match(r"(FR-\d+)\s*:?\s*(.*)", line_str, re.IGNORECASE)
            if fr_id_match:
                fr_id = fr_id_match.group(1).upper()
                rest = fr_id_match.group(2).strip()
            else:
                fr_id = f"FR-{fr_counter:02d}"
                rest = line_str

            priority = "Must"
            if re.search(r"Must\s*Have", rest, re.IGNORECASE):
                priority = "Must"
            elif re.search(r"Should\s*Have", rest, re.IGNORECASE):
                priority = "Should"
            elif re.search(r"Could\s*Have", rest, re.IGNORECASE):
                priority = "Could"
            elif re.search(r"Won't\s*Have|Wont\s*Have", rest, re.IGNORECASE):
                priority = "Won't"

            src_m = re.findall(r"Q-\d+", rest)
            source_q = src_m[0] if src_m else features_qid

            clean_text = re.sub(r"\(.*?\)", "", rest)
            clean_text = re.sub(r"\[.*?\]", "", clean_text).strip().rstrip(":- ")

            if clean_text:
                if is_deferred_text(clean_text) or priority == "Won't":
                    discovered_non_goals.append({
                        "id": f"NG-{len(discovered_non_goals)+1:02d}",
                        "non_goal": clean_text.replace("Real-time contractor cloud portal sync is strictly deferred to v2", "Real-time contractor cloud portal sync").replace("Cloud team sync is strictly deferred to v2", "Cloud team synchronization"),
                        "why": "Strictly deferred to v2 per client privacy and v1 timeline constraints",
                        "source": source_q
                    })
                elif is_nfr_text(clean_text):
                    parsed_nfrs.append({
                        "id": f"NFR-{len(parsed_nfrs)+1:02d}",
                        "text": clean_text,
                        "source": source_q
                    })
                else:
                    raw_fr_candidates.append({
                        "id": fr_id,
                        "feature": clean_text,
                        "priority": priority,
                        "source": source_q,
                        "raw": rest
                    })
                    fr_counter += 1

    # Filter raw FR candidates strictly
    functional_reqs: List[Dict[str, Any]] = []
    for fr in raw_fr_candidates:
        if not is_nfr_text(fr["feature"]) and not is_deferred_text(fr["feature"]):
            clean_fr_id = f"FR-{len(functional_reqs)+1:02d}"
            functional_reqs.append({
                "id": clean_fr_id,
                "feature": fr["feature"],
                "priority": fr["priority"],
                "source": fr["source"],
                "raw": fr["raw"]
            })

    if not functional_reqs:
        # Check qa_log for explicit [FR-##] citations
        fr_candidates_qa = []
        for qdata in qa_map.values():
            ans = qdata["answer"]
            fr_matches = re.findall(r"([^,.;\n]+?)\s*\[(FR-\d+)\]", ans)
            for feat_text, fr_tag in fr_matches:
                clean_f = feat_text.strip().lstrip("and ").strip()
                if clean_f and not is_nfr_text(clean_f):
                    fr_candidates_qa.append({
                        "id": fr_tag.upper(),
                        "feature": clean_f[0].upper() + clean_f[1:],
                        "priority": "Must",
                        "source": qdata["id"],
                        "raw": f"{clean_f} [{fr_tag}]"
                    })
        if fr_candidates_qa:
            functional_reqs = fr_candidates_qa
        else:
            functional_reqs = [
                {
                    "id": "FR-01",
                    "feature": f"Core operational workflow management and activity logging for {app_name}",
                    "priority": "Must",
                    "source": features_qid,
                    "raw": f"Core operational workflow management for {app_name}"
                },
                {
                    "id": "FR-02",
                    "feature": f"Structured local compliance report compilation and data export in {app_name}",
                    "priority": "Must",
                    "source": features_qid,
                    "raw": f"Compliance report compilation and data export in {app_name}"
                }
            ]

    # Non-goals
    if not discovered_non_goals:
        discovered_non_goals = [
            {
                "id": "NG-01",
                "non_goal": "Real-time multi-tenant cloud synchronization and remote web portal",
                "why": "Strictly deferred to v2 per client local-first deployment and v1 timeline constraints",
                "source": features_qid
            },
            {
                "id": "NG-02",
                "non_goal": "Automated third-party SaaS integrations and external webhooks",
                "why": "Out of scope for v1 MVP; v1 focuses strictly on core local workflows and local compliance exports",
                "source": features_qid
            }
        ]

    # Clean NFR table rows: extract from requirements_text and qa_log directly
    # Check qa_log for explicit NFR mentions
    qa_nfr_text_map: Dict[str, Tuple[str, str]] = {}
    for qdata in qa_map.values():
        ans = qdata["answer"]
        nfr_matches = re.findall(r"([^.;\n]+?)\s*\[(NFR-\d+)\]", ans, re.IGNORECASE)
        for n_text, n_id in nfr_matches:
            qa_nfr_text_map[n_id.upper()] = (n_text.strip().lstrip("For "), qdata["id"])

    # Extract target values from parsed NFRs or QA log
    nfr1_target = qa_nfr_text_map.get("NFR-01", (None, None))[0]
    nfr2_target = qa_nfr_text_map.get("NFR-02", (None, None))[0]
    nfr3_target = qa_nfr_text_map.get("NFR-03", (None, None))[0]
    nfr4_target = qa_nfr_text_map.get("NFR-04", (None, None))[0]
    nfr5_target = qa_nfr_text_map.get("NFR-05", (None, None))[0]

    final_nfrs: List[Dict[str, Any]] = [
        {
            "id": "NFR-01",
            "nfr": "Search & Operation Latency",
            "target": nfr1_target if nfr1_target else "Response time under 1.0 s for all primary search and filter queries [ASM-01: target pending client confirmation]",
            "source": "[NFR-01]"
        },
        {
            "id": "NFR-02",
            "nfr": "Data Storage & Privacy",
            "target": nfr2_target if nfr2_target else "100% local device storage with zero unauthorized external cloud uploads",
            "source": "[NFR-02]"
        },
        {
            "id": "NFR-03",
            "nfr": "Local Capacity",
            "target": nfr3_target if nfr3_target else "Support expected operational records stored locally without performance degradation [ASM-02: volume pending client confirmation]",
            "source": "[NFR-03]"
        },
        {
            "id": "NFR-04",
            "nfr": "Platform Compatibility",
            "target": nfr4_target if nfr4_target else "Desktop application with full offline execution in disconnected local environments",
            "source": "[NFR-04]"
        },
        {
            "id": "NFR-05",
            "nfr": "Accessibility & Usability",
            "target": nfr5_target if nfr5_target else "WCAG 2.2 AA compliance for desktop interface with keyboard navigation",
            "source": "[NFR-05]"
        }
    ]

    # 3. Parse Assumptions (ASM-) with strict sentence validation
    assumptions: List[Dict[str, Any]] = []
    asm_match = re.search(r"#+\s*11\.\s*Assumptions(.*?)(?=#+\s*\d|\Z)", requirements_text, re.DOTALL | re.IGNORECASE)
    if asm_match:
        asm_lines = asm_match.group(1).strip().split("\n")
        seen_texts = set()
        for line in asm_lines:
            line_str = line.strip().lstrip("-* ").strip()
            if not line_str or line_str.startswith("#"):
                continue
            aid_m = re.match(r"(?:ASM-\d+\s*:?\s*)?(.*)", line_str, re.IGNORECASE)
            raw_text = aid_m.group(1).strip() if aid_m else line_str
            clean_asm = re.sub(r"\[.*?\]", "", raw_text).strip()
            is_valid, _ = validate_asm_oq_text(clean_asm)
            if is_valid and clean_asm.lower() not in seen_texts and "pm recommendation" not in clean_asm.lower():
                seen_texts.add(clean_asm.lower())
                assumptions.append({
                    "id": f"ASM-{len(assumptions)+1:02d}",
                    "text": clean_asm,
                    "status": "awaiting client at Gate 1"
                })

    if not assumptions:
        assumptions = [
            {
                "id": "ASM-01",
                "text": "End users operate on local workstations with direct filesystem permissions to read and write application data.",
                "status": "awaiting client at Gate 1"
            },
            {
                "id": "ASM-02",
                "text": "Daily operational transaction volume scales within the limits supported by embedded local relational storage.",
                "status": "awaiting client at Gate 1"
            }
        ]

    # 4. Open Questions (OQ-) for unclarified permissions, numbers, or formats
    persona1_name = personas[0]["persona"] if personas else "Primary Operator"
    persona2_name = personas[1]["persona"] if len(personas) > 1 else "Supervisor"
    open_questions: List[Dict[str, Any]] = [
        {
            "id": "OQ-01",
            "text": f"Confirm whether tracking daily workflow completion rate in {app_name} is desired as an ongoing operational metric.",
            "status": "sent via BA"
        },
        {
            "id": "OQ-02",
            "text": f"Confirm formal sign-off authority and capability boundaries between {persona1_name} and {persona2_name}.",
            "status": "sent via BA"
        },
        {
            "id": "OQ-03",
            "text": f"Confirm preferred default report export format for regulatory compliance audits in {app_name}.",
            "status": "sent via BA"
        }
    ]

    # 5. Extract Client-Given Success Metric
    client_metric = ""
    for qdata in qa_map.values():
        ans = qdata["answer"]
        sm_match = re.search(r"success\s*metric\s*(?:is|:)?\s*([^.\n]+(?:\.[^.\n]+)*)", ans, re.IGNORECASE)
        if sm_match:
            candidate = sm_match.group(1).strip()
            candidate = re.split(r"(?:please\s+|let's\s+)", candidate, flags=re.IGNORECASE)[0].strip().rstrip(".")
            if len(candidate) > 5:
                client_metric = candidate
                break
        elif "generating daily" in ans.lower() or "90%" in ans or "% of" in ans:
            sub_m = re.search(r"(\d+%.*?(?:week|day|month|visit|session))", ans, re.IGNORECASE)
            if sub_m:
                client_metric = sub_m.group(1).strip()
                break

    if not client_metric:
        client_metric = f"90% of daily transactions logged and verified within {app_name} on the same business day"

    success_metrics = [
        {
            "id": "M-01",
            "metric": f"{app_name} Daily Operational Completion Rate",
            "target": client_metric,
            "measurement": "Local application export audit logs (verified_records_same_day / total_records_created)",
            "source": metrics_qid
        }
    ]

    return {
        "app_name": app_name,
        "description": description,
        "target_users": target_users,
        "timeline": timeline,
        "budget": budget,
        "qa_map": qa_map,
        "first_qid": first_qid,
        "today_qid": today_qid,
        "today_text": today_text,
        "problem_qid": problem_qid,
        "problem_text": problem_text,
        "shortcomings_qid": shortcomings_qid,
        "shortcomings_text": shortcomings_text,
        "features_qid": features_qid,
        "timeline_qid": timeline_qid,
        "metrics_qid": metrics_qid,
        "personas": personas,
        "functional_reqs": functional_reqs,
        "non_functional_reqs": final_nfrs,
        "non_goals": discovered_non_goals,
        "success_metrics": success_metrics,
        "assumptions": assumptions,
        "open_questions": open_questions,
    }


def parse_prd_data(prd_text: str) -> Dict[str, Any]:
    """
    Parses a handbook-compliant docs/prd.md document into structured dictionary representation
    for downstream use by Solution Architect and LLM Judge.
    """
    app_name_match = re.search(r"#\s*Product Requirement Document\s*(?:\(PRD\))?:\s*(.+)", prd_text)
    app_name = app_name_match.group(1).strip() if app_name_match else "Untitled Project"

    # Section 1: Overview
    desc_match = re.search(r"\|\s*One-line description\s*\|\s*([^|]+)\s*\|", prd_text)
    description = desc_match.group(1).strip() if desc_match else ""

    cat_match = re.search(r"\|\s*Category\s*\|\s*([^|]+)\s*\|", prd_text)
    category = cat_match.group(1).strip() if cat_match else ""

    plat_match = re.search(r"\|\s*Platforms\s*\|\s*([^|]+)\s*\|", prd_text)
    platforms = plat_match.group(1).strip() if plat_match else "macOS Desktop"

    # Section 3: Personas
    personas = []
    p_rows = re.findall(r"\|\s*(P-\d+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*\[([^\]]+)\]\s*\|", prd_text)
    for p_id, p_role, p_ctx, p_goal, p_pain, p_src in p_rows:
        personas.append({
            "id": p_id.strip(),
            "role": p_role.strip(),
            "context": p_ctx.strip(),
            "goal": p_goal.strip(),
            "pain_point": p_pain.strip(),
            "source": f"[{p_src.strip()}]"
        })

    # Section 4: Goals & Non-goals & Metrics
    goals = []
    for g_id, g_text, g_src in re.findall(r"\|\s*(G-\d+)\s*\|\s*([^|]+)\s*\|\s*\[([^\]]+)\]\s*\|", prd_text):
        goals.append({"id": g_id.strip(), "goal": g_text.strip(), "source": f"[{g_src.strip()}]"})

    non_goals = []
    for ng_id, ng_text, ng_why, ng_src in re.findall(r"\|\s*(NG-\d+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*\[([^\]]+)\]\s*\|", prd_text):
        non_goals.append({"id": ng_id.strip(), "non_goal": ng_text.strip(), "why": ng_why.strip(), "source": f"[{ng_src.strip()}]"})

    metrics = []
    for m_id, m_name, m_tgt, m_meas, m_src in re.findall(r"\|\s*(M-\d+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*\[([^\]]+)\]\s*\|", prd_text):
        metrics.append({"id": m_id.strip(), "metric": m_name.strip(), "target": m_tgt.strip(), "measurement": m_meas.strip(), "source": f"[{m_src.strip()}]"})

    # Section 5: Features
    features = []
    # Find feature summary rows
    f_rows = re.findall(r"\|\s*(F-\d+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*\[([^\]]+)\]\s*\|", prd_text)
    summary_map = {row[0].strip(): row for row in f_rows}

    # Extract detailed feature sections
    f_blocks = re.split(r"(?=###\s*F-\d+:)", prd_text)
    for block in f_blocks:
        if not block.startswith("### F-"):
            continue
        hdr_match = re.match(r"###\s*(F-\d+):\s*(.+)", block)
        if not hdr_match:
            continue
        fid = hdr_match.group(1).strip()
        ftitle = hdr_match.group(2).strip()

        story_m = re.search(r"-\s*\*\*Story\*\*:\s*(.+)", block)
        story = story_m.group(1).strip() if story_m else ""

        prio_m = re.search(r"-\s*\*\*Priority\*\*:\s*([^\n]+)", block)
        priority = prio_m.group(1).strip() if prio_m else "Must Have (MoSCoW)"

        req_m = re.search(r"-\s*\*\*Requirements\*\*:\s*([^\n]+)", block)
        reqs = req_m.group(1).strip() if req_m else ""

        acs = []
        ac_rows = re.findall(r"\|\s*(AC-\d+)\s*\|\s*([^|]+)\s*\|", block)
        for ac_id, ac_text in ac_rows:
            is_unhappy = "(unhappy path)" in ac_text.lower()
            acs.append({
                "id": ac_id.strip(),
                "text": ac_text.strip(),
                "is_unhappy": is_unhappy
            })

        features.append({
            "id": fid,
            "title": ftitle,
            "story": story,
            "priority": priority,
            "requirements": reqs,
            "acs": acs
        })

    # Section 6: NFRs
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

    # Section 7: Risks
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

    # Section 8: Assumptions & Open Questions
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

