import os
import re
import json
import logging
from typing import Dict, Any, List, Tuple, Optional

try:
    from llm_client import query_llm
except ImportError:
    try:
        from engine.llm_client import query_llm
    except ImportError:
        query_llm = None

logger = logging.getLogger("autonoma-judge")

JUDGE_SYSTEM_PROMPT = """You are the Lead Quality Auditor and LLM Judge for a software engineering agent ecosystem.
Your job is to audit Product Requirement Documents (docs/prd.md) against verified discovery requirements and the strict Quality Bar (Handbook Sections 5.2.5, 5.2.6, and Chapter 14).

You MUST evaluate the candidate PRD against the 8 rubric criteria.
For each criterion, score from 0 to 3 based on the rubric scales:
0 = Non-compliant / Missing
1 = Partially compliant with major defects
2 = Mostly compliant with minor gaps
3 = Fully compliant with complete evidence

CRITICAL MUST-PASS RULES:
1. fr_coverage MUST be 3/3 (100% of Must-have FRs covered).
2. acceptance_criteria MUST be >= 2/3 (zero vague fillers like 'seamless' or 'should be easy').
3. unhappy_paths MUST be 3/3 (every feature has an explicit unhappy path).
4. nfr_classification MUST be 3/3 (zero technical/storage/latency constraints misfiled as features).
5. hallucination_and_grounding MUST be 3/3 (zero invented roles, zero ungrounded metrics, zero unprompted tech stack choices, zero placeholders).

OUTPUT FORMAT:
Respond ONLY with a valid JSON object matching this schema:
{
  "artifact": "docs/prd.md",
  "rubric": "skills/pm/rubric.json",
  "scores": [
    {
      "criterion": "fr_coverage",
      "score": 3,
      "max": 3,
      "evidence": "Direct quotes from PRD showing coverage",
      "fix": ""
    }
  ],
  "unsupported_claims": [
    {
      "section": "Section name",
      "text": "Exact text quote",
      "reason": "Why this claim is unsupported or violates the Quality Bar"
    }
  ],
  "total": 24,
  "max": 24,
  "pass": true,
  "verdict_summary": "Summary of verdict"
}
"""


def validate_asm_oq_entry(text: str) -> Tuple[bool, str]:
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

    return True, ""


def run_code_level_audits(
    prd_text: str,
    parsed_ba: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Executes exhaustive deterministic audits for Quality Bar 5.2.5, Must-Not 5.2.6, and Chapter 14.
    Audits for:
    1. Invented roles (e.g. Workspace Administrator).
    2. Vague terms in ACs.
    3. Truncated NFR rows.
    4. NFRs misfiled as functional features in Section 5.
    5. Placeholders and fragments in Section 8 (ASM/OQ).
    6. Must-Not violations (e.g. PM recommendations in ASM).
    7. Unprompted tech stack choices (Electron, FTS5).
    8. Persona duplication and boilerplate phrases ('repetitive status formatting').
    9. Section 2 redundancy ('Today' vs 'Core problem' identical or citing same Q-).
    10. Citation verification against qa_log.json.
    """
    unsupported_claims: List[Dict[str, Any]] = []
    audits: Dict[str, Any] = {}
    qa_map = parsed_ba.get("qa_map", {})
    all_qa_text = " ".join([q["question"] + " " + q["answer"] for q in qa_map.values()]).lower()

    # 1. Check for invented roles in Section 3
    if "Workspace Administrator" in prd_text:
        unsupported_claims.append({
            "section": "3. Users",
            "text": "Workspace Administrator",
            "reason": "Invented role not requested by client in discovery answers"
        })

    # 2. Check for vague phrases in Acceptance Criteria (Section 5.2.5 item 2)
    vague_phrases = ["should be easy", "seamless", "intuitive", "user-friendly"]
    for phrase in vague_phrases:
        if phrase in prd_text.lower():
            unsupported_claims.append({
                "section": "5. Features",
                "text": phrase,
                "reason": f"Vague phrase '{phrase}' violates Quality Bar 5.2.5 (no 'should be easy' or filler)"
            })

    # 3. Check for truncated NFR rows or unclosed parens in Section 6
    if "## 6. Non-functional requirements" in prd_text:
        nfr_section = prd_text.split("## 6. Non-functional requirements")[1].split("##")[0]
        for line in nfr_section.strip().split("\n"):
            if "|" in line and ("(" in line and ")" not in line):
                unsupported_claims.append({
                    "section": "6. Non-functional requirements",
                    "text": line.strip(),
                    "reason": "Truncated NFR row with unclosed parenthesis in Section 6 table"
                })

    # 4. Check for NFRs disguised as features in Section 5
    nfr_keywords = ["latency under", "stored locally in sqlite", "zero cloud dependencies"]
    if "## 5. Features (v1)" in prd_text:
        feat_section = prd_text.split("## 5. Features (v1)")[1].split("## 6.")[0]
        for kw in nfr_keywords:
            if kw in feat_section.lower():
                unsupported_claims.append({
                    "section": "5. Features",
                    "text": kw,
                    "reason": f"Non-functional constraint '{kw}' misfiled as a functional feature in Section 5"
                })

    # 5. Check grammar and typography errors
    if "so that I can a " in prd_text:
        unsupported_claims.append({
            "section": "5. Features",
            "text": "so that I can a ...",
            "reason": "Broken story grammar: 'so that I can a [description]'"
        })
    if ".." in prd_text:
        unsupported_claims.append({
            "section": "General",
            "text": "..",
            "reason": "Double period typography defect"
        })
    if "(1 items)" in prd_text:
        unsupported_claims.append({
            "section": "General",
            "text": "(1 items)",
            "reason": "Pluralization defect: '(1 items)' instead of '1 item'"
        })

    # 6. Check Section 8 Assumptions and Open Questions for Placeholders & Fragments
    if "## 8. Assumptions and open questions" in prd_text:
        sec8 = prd_text.split("## 8. Assumptions and open questions")[1].split("##")[0]
        sec8_lines = sec8.strip().split("\n")
        for line in sec8_lines:
            if not line.startswith("|") or "ID | Text | Status" in line or "|---" in line:
                continue
            cols = [c.strip() for c in line.split("|") if c.strip()]
            if len(cols) >= 2:
                row_id = cols[0]
                row_text = cols[1]

                # Check placeholders or fragments
                is_valid, reason = validate_asm_oq_entry(row_text)
                if not is_valid:
                    unsupported_claims.append({
                        "section": "8. Assumptions and open questions",
                        "text": f"{row_id}: {row_text}",
                        "reason": f"Section 8 defect: {reason}"
                    })

                # Check Must-Not: PM recommendation in ASM
                if row_id.startswith("ASM-") and "pm recommendation" in row_text.lower():
                    unsupported_claims.append({
                        "section": "8. Assumptions and open questions",
                        "text": f"{row_id}: {row_text}",
                        "reason": "Must-Not rule violation: PM suggestions must be filed as OQ-, not ASM-."
                    })

    # 7. Check for unprompted tech stack leak (Electron, FTS5)
    prohibited_tech = ["electron", "fts5", "react", "vue", "angular", "tailwind", "fastapi"]
    for tech in prohibited_tech:
        if tech in prd_text.lower() and tech not in all_qa_text:
            unsupported_claims.append({
                "section": "Technical Specification",
                "text": tech,
                "reason": f"Unprompted technology choice '{tech}' specified in PRD without client request (Quality Bar 5.2.5 item 8 & Must-Not 5.2.6)"
            })

    # 8. Check for Persona Duplication and Boilerplate
    if "repetitive status formatting" in prd_text:
        unsupported_claims.append({
            "section": "3. Users",
            "text": "repetitive status formatting",
            "reason": "Boilerplate leftover text: 'repetitive status formatting' copied from another project"
        })
    if "Modify system core application configuration files" in prd_text:
        unsupported_claims.append({
            "section": "3. Users",
            "text": "Modify system core application configuration files",
            "reason": "Hardcoded default permissions string; where unstated, reference [OQ-##] instead of filler"
        })

    # Check if P-01 and P-02 have identical goals or pain points in Section 3
    if "## 3. Users" in prd_text:
        sec3 = prd_text.split("## 3. Users")[1].split("## 4.")[0]
        p_matches = re.findall(r"\|\s*(P-\d+)\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|", sec3)
        if len(p_matches) >= 2:
            p1_goal = p_matches[0][3].strip().lower()
            p2_goal = p_matches[1][3].strip().lower()
            p1_pain = p_matches[0][4].strip().lower()
            p2_pain = p_matches[1][4].strip().lower()

            if p1_goal == p2_goal:
                unsupported_claims.append({
                    "section": "3. Users",
                    "text": f"Identical persona goals for {p_matches[0][0]} and {p_matches[1][0]}",
                    "reason": "Boilerplate defect: P-01 and P-02 cannot have identical goals"
                })
            if p1_pain == p2_pain:
                unsupported_claims.append({
                    "section": "3. Users",
                    "text": f"Identical persona pain points for {p_matches[0][0]} and {p_matches[1][0]}",
                    "reason": "Boilerplate defect: P-01 and P-02 cannot have identical pain points"
                })

    # 9. Check Section 2: 'Today' and 'Core problem' must say different things and cite different Q- IDs
    if "## 2. Problem" in prd_text:
        sec2 = prd_text.split("## 2. Problem")[1].split("## 3.")[0]
        today_match = re.search(r"-\s*\*\*Today\*\*:\s*([^\[]+)\[(Q-\d+)\]", sec2)
        core_match = re.search(r"-\s*\*\*Core problem\*\*:\s*([^\[]+)\[(Q-\d+)\]", sec2)

        if today_match and core_match:
            today_txt = today_match.group(1).strip()
            today_src = today_match.group(2).strip()
            core_txt = core_match.group(1).strip()
            core_src = core_match.group(2).strip()

            if today_src == core_src:
                unsupported_claims.append({
                    "section": "2. Problem",
                    "text": f"Today ({today_src}) and Core problem ({core_src}) cite the same source",
                    "reason": "Section 2 defect: 'Today' and 'Core problem' must come from different client answers"
                })
            if today_txt.lower() == core_txt.lower() or len(set(today_txt.lower().split()) & set(core_txt.lower().split())) > len(today_txt.split()) * 0.7:
                unsupported_claims.append({
                    "section": "2. Problem",
                    "text": "Today and Core problem have duplicate/overlapping content",
                    "reason": "Section 2 defect: 'Today' and 'Core problem' must describe distinct aspects"
                })

    # 10. Verify Citations exist in qa_log.json
    all_cited_qs = set(re.findall(r"\[(Q-\d+)\]", prd_text))
    if qa_map:
        for q in all_cited_qs:
            if q not in qa_map:
                unsupported_claims.append({
                    "section": "Citations",
                    "text": f"[{q}]",
                    "reason": f"Cited question ID {q} does not exist in qa_log.json"
                })

    # 11. Deterministic Ungrounded Numbers Check (Handbook 14.1.3 & Quality Bar 5.2.5 item 8, Item B.7)
    # Every numeric requirement or metric in PRD must appear in qa_log.json or be tagged [OQ-##] or [ASM-##]
    qa_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", all_qa_text.replace(",", "")))
    qa_numbers.update(re.findall(r"\b\d+,\d+\b", all_qa_text))
    intake_data = parsed_ba.get("intake", {})
    intake_text = json.dumps(intake_data).lower()
    qa_numbers.update(re.findall(r"\b\d+(?:\.\d+)?\b", intake_text.replace(",", "")))

    # Match numbers with units or context in ACs and NFRs
    for line in prd_text.splitlines():
        line_clean = line.strip()
        if not line_clean or line_clean.startswith("#") or line_clean.startswith("|---") or re.match(r"^\|\s*ID\s*\|", line_clean):
            continue
        if "## 5. Features" in prd_text or "## 6. Non-functional" in prd_text:
            if "|" in line_clean and ("AC-" in line_clean or "NFR-" in line_clean):
                # Remove ID tags, citations, and standard industry specs before checking metrics
                line_no_ids = re.sub(r"\[[A-Za-z0-9_-]+\]", "", line_clean)
                line_no_ids = re.sub(r"\b(?:AC|NFR|F|FR|P|Q|G|NG|M|R|ASM|OQ|TBL|API|SLO|T|ROLE|ST|TC|BUG)-\d+\b", "", line_no_ids)
                line_no_ids = re.sub(r"WCAG\s+2\.2\s+AA", "", line_no_ids, flags=re.IGNORECASE)
                line_no_ids = re.sub(r"RFC\s+\d+", "", line_no_ids, flags=re.IGNORECASE)

                found_nums = re.findall(r"\b(\d[\d,]*(?:\.\d+)?)\s*(?:ms|s|seconds|minutes|hours|records|photo\s+notes|notes|items|users|req/s|MB|GB)?\b", line_no_ids, re.IGNORECASE)
                for f_num in found_nums:
                    clean_f = f_num.replace(",", "")
                    if clean_f in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "100", "0", "200", "201", "400", "401", "403", "404", "409", "422", "5000", "9457", "29148", "25010"]:
                        continue
                    if clean_f.startswith("202") and len(clean_f) == 4:
                        continue
                    if clean_f not in qa_numbers and f_num not in qa_numbers:
                        if not ("OQ-" in line_clean or "ASM-" in line_clean):
                            unsupported_claims.append({
                                "section": "6. Non-functional requirements / Acceptance Criteria",
                                "text": line_clean[:80],
                                "reason": f"Ungrounded metric: Number '{f_num}' in PRD does not appear in discovery answers (qa_log.json) and is not tagged [OQ-##] or [ASM-##]"
                            })

    # 12. Check Roles Table "Can" column for unconfirmed client permissions (Item B.8)
    if "## 3. Users" in prd_text and "User roles and permissions" in prd_text:
        sec3_roles = prd_text.split("User roles and permissions")[1].split("##")[0]
        for line in sec3_roles.splitlines():
            if "|" in line and not line.startswith("|---") and not "Role | Does | Can" in line:
                cols = [c.strip() for c in line.split("|") if c.strip()]
                if len(cols) >= 3:
                    can_text = cols[2]
                    # If can_text states specific capabilities without OQ- or FR- and not in QA answers
                    if "OQ-" not in can_text and "FR-" not in can_text and len(can_text) > 10:
                        if any(phrase in can_text.lower() for phrase in ["approve hazard flags", "create templates", "export signed compliance reports", "sign-off on all"]):
                            unsupported_claims.append({
                                "section": "3. Users",
                                "text": can_text,
                                "reason": f"Unconfirmed role capability in 'Can' column '{can_text}' not stated by client in discovery; must be tagged [OQ-##] awaiting Gate 1 confirmation"
                            })

    # 13. Check that EVERY feature has happy-path and unhappy-path ACs (Item B.9)
    if "## 5. Features (v1)" in prd_text:
        feat_sec = prd_text.split("## 5. Features (v1)")[1].split("## 6.")[0]
        f_blocks = re.split(r"###\s+(F-\d+)", feat_sec)[1:]
        for i in range(0, len(f_blocks), 2):
            fid = f_blocks[i].strip()
            ftext = f_blocks[i+1] if i+1 < len(f_blocks) else ""
            has_happy = bool(re.search(r"AC-\d+\s*\|\s*(?!\(unhappy)", ftext))
            has_unhappy = bool(re.search(r"\(unhappy\s*path\)", ftext, re.IGNORECASE))
            if not has_happy:
                unsupported_claims.append({
                    "section": f"5. Features ({fid})",
                    "text": fid,
                    "reason": f"Feature {fid} lacks required happy-path acceptance criterion"
                })
            if not has_unhappy:
                unsupported_claims.append({
                    "section": f"5. Features ({fid})",
                    "text": fid,
                    "reason": f"Feature {fid} lacks required (unhappy path) acceptance criterion"
                })

    return unsupported_claims, audits


def score_prd_deterministically(
    prd_text: str,
    parsed_ba: Dict[str, Any],
    rubric_data: Dict[str, Any],
    code_unsupported: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Deterministic scoring implementing the rubric's exact scales.
    Ensures that any detected code defect results in failing the associated must-pass criteria.
    """
    unique_f_matches = sorted(list(set(re.findall(r"F-\d+", prd_text))))
    num_features = max(1, len(unique_f_matches))
    unique_ac_matches = sorted(list(set(re.findall(r"AC-\d+", prd_text))))
    gwt_count = len(re.findall(r"given\s+.*?when\s+.*?then", prd_text, re.IGNORECASE))
    unhappy_count = len(re.findall(r"\(unhappy\s*path\)", prd_text, re.IGNORECASE))

    scores = []

    # 1. fr_coverage (Must-pass)
    must_frs = [fr["id"] for fr in parsed_ba.get("functional_reqs", []) if "must" in str(fr.get("priority", "")).lower()]
    covered_must = [fr_id for fr_id in must_frs if f"[{fr_id}]" in prd_text or fr_id in prd_text]
    score_fr = 3 if (num_features > 0 and len(covered_must) >= len(must_frs)) else (2 if num_features > 0 else 0)
    scores.append({
        "criterion": "fr_coverage",
        "score": score_fr,
        "max": 3,
        "evidence": f"Found {num_features} unique features. Must-have FR coverage: {len(covered_must)}/{len(must_frs)}.",
        "fix": "Ensure every Must-have FR from discovery is mapped to an F-### feature" if score_fr < 3 else ""
    })

    # 2. acceptance_criteria
    forbidden_words = ["should be easy", "seamless", "intuitive", "user-friendly"]
    has_vague = any(w in prd_text.lower() for w in forbidden_words)
    score_ac = 3 if (gwt_count >= num_features * 2 and not has_vague) else (2 if gwt_count >= num_features and not has_vague else 1)
    scores.append({
        "criterion": "acceptance_criteria",
        "score": score_ac,
        "max": 3,
        "evidence": f"Found {len(unique_ac_matches)} unique ACs with {gwt_count} Given/When/Then clauses across {num_features} features. Vague terms present: {has_vague}.",
        "fix": "Rewrite ACs using specific feature actions and expected results without generic boilerplate" if score_ac < 3 else ""
    })

    # 3. unhappy_paths (Must-pass)
    score_unhappy = 3 if unhappy_count >= num_features else (2 if unhappy_count > 0 else 0)
    scores.append({
        "criterion": "unhappy_paths",
        "score": score_unhappy,
        "max": 3,
        "evidence": f"Detected {unhappy_count} explicit (unhappy path) criteria across {num_features} features.",
        "fix": "Add explicit (unhappy path) Given/When/Then criterion for every feature" if score_unhappy < 3 else ""
    })

    # 4. non_goals_grounded
    has_ng = "## 4. Goals, non-goals, metrics" in prd_text and "NG-01" in prd_text
    score_ng = 3 if has_ng and "[Q-" in prd_text.split("### Non-goals")[1].split("###")[0] else (2 if has_ng else 0)
    scores.append({
        "criterion": "non_goals_grounded",
        "score": score_ng,
        "max": 3,
        "evidence": "Non-goals table (NG-###) present with rationale and source citations." if has_ng else "Missing NG- table.",
        "fix": "Add non-goals table with why reasoning and Q- citations" if score_ng < 3 else ""
    })

    # 5. metrics_and_measurement
    has_m = "M-01" in prd_text and ("event" in prd_text.lower() or "query" in prd_text.lower() or "log" in prd_text.lower())
    score_m = 3 if has_m else 1
    scores.append({
        "criterion": "metrics_and_measurement",
        "score": score_m,
        "max": 3,
        "evidence": "Success metrics with numeric targets and telemetry/query measurement methods present." if has_m else "Metrics missing concrete measurement method.",
        "fix": "Define how each metric is measured (local event log, database query)" if score_m < 3 else ""
    })

    # 6. nfr_classification (Must-pass)
    has_misfiled_nfr = any("latency under" in prd_text.lower().split("## 6.")[0] or "stored locally in sqlite" in prd_text.lower().split("## 6.")[0] for _ in [1])
    score_nfr = 1 if has_misfiled_nfr else 3
    scores.append({
        "criterion": "nfr_classification",
        "score": score_nfr,
        "max": 3,
        "evidence": "Clean separation of FRs and NFRs." if score_nfr == 3 else "NFRs misfiled as functional features in Section 5.",
        "fix": "Move latency and storage constraints to Section 6 NFRs and out of Section 5 Features" if score_nfr < 3 else ""
    })

    # 7. hallucination_and_grounding (Must-pass)
    # If there are ANY code-level unsupported claims (placeholders, tech leaks, persona duplication), cap score at 1
    score_ground = 1 if len(code_unsupported) > 0 else 3
    scores.append({
        "criterion": "hallucination_and_grounding",
        "score": score_ground,
        "max": 3,
        "evidence": "All roles, claims, and numbers strictly grounded in discovery answers." if score_ground == 3 else f"Detected {len(code_unsupported)} unsupported claims/defects.",
        "fix": "Remove invented roles, placeholders, tech choices, and redundant sentences" if score_ground < 3 else ""
    })

    # 8. timeline_budget_feasibility
    has_feasibility = ("weeks" in prd_text.lower()) and ("budget" in prd_text.lower() or "$" in prd_text)
    score_tf = 3 if has_feasibility else 1
    scores.append({
        "criterion": "timeline_budget_feasibility",
        "score": score_tf,
        "max": 3,
        "evidence": "Timeline and budget cited with scope trade-off reasoning." if has_feasibility else "Missing timeline/budget feasibility.",
        "fix": "Show timeline and budget reasoning in Section 4 and 9" if score_tf < 3 else ""
    })

    return {
        "artifact": "docs/prd.md",
        "rubric": "skills/pm/rubric.json",
        "scores": scores,
        "unsupported_claims": code_unsupported,
        "total": sum(s["score"] for s in scores),
        "max": 24,
        "pass": len(code_unsupported) == 0 and sum(s["score"] for s in scores) >= 20 and score_ground == 3 and score_fr == 3 and score_unhappy == 3 and score_nfr == 3
    }


def evaluate_prd_with_judge(
    prd_text: str,
    parsed_ba: Dict[str, Any],
    rubric_path: str = "skills/pm/rubric.json",
    query_ollama_fn = None
) -> Dict[str, Any]:
    """
    Executes the LLM Judge evaluation for Stage 2 PRD per Handbook Chapter 14 & Stage 2 Step 9.
    Combines deterministic code audits with LLM rubric scoring.
    """
    if not os.path.exists(rubric_path):
        rubric_path = os.path.join(os.getcwd(), rubric_path)

    rubric_data: Dict[str, Any] = {}
    if os.path.exists(rubric_path):
        try:
            with open(rubric_path, "r", encoding="utf-8") as f:
                rubric_data = json.load(f)
        except Exception as e:
            logger.error(f"Error loading rubric {rubric_path}: {e}")

    # Step 1: Run deterministic code audits first (14.1.4 Tools first)
    code_unsupported, code_audits = run_code_level_audits(prd_text, parsed_ba)

    # Step 2: Build evaluation context for LLM Judge
    qa_items = []
    for k, v in parsed_ba.get("qa_map", {}).items():
        ans = v.get("answer", "")
        if len(ans) > 200:
            ans = ans[:197] + "..."
        qa_items.append(f"[{k}] {ans}")
    qa_summary = "\n".join(qa_items)
    fr_list = [f"{fr['id']}: {fr['feature']} ({fr.get('priority', 'Must')}) [Source: {fr.get('source', '')}]" for fr in parsed_ba.get("functional_reqs", [])]
    nfr_list = [f"{n['id']}: {n.get('nfr', '')} - {n.get('target', '')} [Source: {n.get('source', '')}]" for n in parsed_ba.get("non_functional_reqs", [])]

    judge_prompt = f"""EVALUATE THIS PRODUCT REQUIREMENT DOCUMENT (PRD) AGAINST THE PM RUBRIC.

SOURCE DISCOVERY Q&A LOG:
{qa_summary}

VERIFIED FUNCTIONAL REQUIREMENTS FROM BA:
{chr(10).join(fr_list)}

VERIFIED NON-FUNCTIONAL REQUIREMENTS FROM BA:
{chr(10).join(nfr_list)}

CLIENT INTAKE RECAP:
- App Name: {parsed_ba.get('app_name')}
- Description: {parsed_ba.get('description')}
- Target Users: {parsed_ba.get('target_users')}
- Target Timeline: {parsed_ba.get('timeline')}
- Budget & Running Costs: {parsed_ba.get('budget')}

RUBRIC CRITERIA:
{json.dumps(rubric_data.get('criteria', []), indent=2)}

AUTOMATED CODE AUDIT FINDINGS:
{json.dumps(code_unsupported, indent=2)}

CANDIDATE PRD TO JUDGE:
```markdown
{prd_text}
```

Score every criterion on 0-3 with specific evidence quotes and concrete fixes.
List any unsupported claims or hallucinations in `unsupported_claims`.
Return ONLY valid JSON."""

    judge_verdict = None
    raw_eval = None
    if query_llm:
        try:
            raw_eval = query_llm(
                prompt=judge_prompt,
                system=JUDGE_SYSTEM_PROMPT,
                role="judge",
                task_id="judge_prd_evaluation"
            )
        except Exception as e:
            logger.warning(f"Judge LLM query failed: {e}")
    if not raw_eval and query_ollama_fn:
        try:
            raw_eval = query_ollama_fn(prompt=judge_prompt, system=JUDGE_SYSTEM_PROMPT)
        except Exception as e:
            logger.warning(f"Judge query_ollama_fn failed: {e}")

    if raw_eval:
        try:
            m = re.search(r"\{.*\}", raw_eval, re.DOTALL)
            if m:
                judge_verdict = json.loads(m.group(0))
        except Exception as e:
            logger.warning(f"Failed to parse Judge JSON verdict: {e}")

    if not judge_verdict or not isinstance(judge_verdict.get("scores"), list):
        judge_verdict = score_prd_deterministically(prd_text, parsed_ba, rubric_data, code_unsupported)

    # Merge code-level unsupported claims into judge verdict
    existing_unsupported = judge_verdict.get("unsupported_claims", [])
    merged_unsupported = list(existing_unsupported)
    for cu in code_unsupported:
        if not any(cu.get("text") == u.get("text") for u in merged_unsupported if isinstance(u, dict)):
            merged_unsupported.append(cu)
    judge_verdict["unsupported_claims"] = merged_unsupported

    # Enforce pass/fail rule per Chapter 14.2.4:
    pass_threshold = rubric_data.get("pass_threshold", 20)
    has_unsupported = len(merged_unsupported) > 0
    scores = judge_verdict.get("scores", [])
    total_score = sum(s.get("score", 0) for s in scores)
    judge_verdict["total"] = total_score
    judge_verdict["max"] = sum(s.get("max", 3) for s in scores)

    must_pass_failed = False
    for s in scores:
        crit_id = s.get("criterion")
        matching_crit = next((c for c in rubric_data.get("criteria", []) if c.get("id") == crit_id), None)
        if matching_crit and matching_crit.get("must_pass") and s.get("score", 0) < s.get("max", 3):
            must_pass_failed = True

    overall_pass = (total_score >= pass_threshold) and (not has_unsupported) and (not must_pass_failed)
    judge_verdict["pass"] = overall_pass
    judge_verdict["verdict_summary"] = (
        f"PRD PASSED Judge audit with score {total_score}/{judge_verdict['max']}."
        if overall_pass
        else f"PRD FAILED Judge audit ({total_score}/{judge_verdict['max']}). Unsupported claims: {len(merged_unsupported)}. Must-pass failed: {must_pass_failed}."
    )

    return judge_verdict


# ==============================================================================
# ARCHITECT ARTIFACT AUDITS & JUDGE EVALUATOR (Chapter 7, Chapter 14, Appendix A.3)
# ==============================================================================

def run_architecture_code_audits(
    arch_text: str,
    prd_text: str,
    parsed_ba: Dict[str, Any],
    schema_text: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Executes deterministic code-level audits for docs/architecture.md and docs/schema.md.
    Enforces Chapter 7.2.5 Quality Bar, Chapter 7.2.6 Must-Not rules, Chapter 14, and semantic grounding:
    1. Novel-term / Cross-project contamination check (Item A.1 & D.11).
    2. Contradictory claims check (Item A.4 & D.11).
    3. Schema structural check (Item A.2 & D.11: no generic blobs, no identical tables).
    4. Semantic support check (Item D.11: cited Q-/F-/NFR- must support the sentence).
    5. Placeholders, over-engineering, NFR coverage, and capacity math.
    """
    unsupported_claims: List[Dict[str, Any]] = []
    audits: Dict[str, Any] = {}
    all_qa_text = " ".join([q.get("question", "") + " " + q.get("answer", "") for q in parsed_ba.get("qa_map", {}).values()]).lower()
    prd_lower = prd_text.lower()
    arch_lower = arch_text.lower()

    # 1. Check for Placeholder Expressions
    for line in arch_text.splitlines():
        if re.search(r"\b(?:is\s+[xyz]|\[[xyz]\]|<[^>]+>|dummy|todo|placeholder)\b", line, re.IGNORECASE):
            unsupported_claims.append({
                "section": "Architecture Specification",
                "text": line.strip()[:80],
                "reason": "Placeholder expression detected in architecture document"
            })

    # 2. General Novel-Term / Cross-Project Contamination Check (Handbook 14.1.3 & Item A.1, D.11)
    grounding_corpus = f"{prd_lower} {all_qa_text.lower()}"
    grounding_vocab = set(re.findall(r"\b[a-zA-Z]{3,}\b", grounding_corpus))

    standard_arch_vocab = {
        'the', 'and', 'for', 'with', 'that', 'this', 'from', 'have', 'has', 'not', 'are', 'was',
        'system', 'architecture', 'component', 'components', 'service', 'services', 'database',
        'table', 'tables', 'schema', 'query', 'queries', 'index', 'indexes', 'api', 'apis',
        'endpoint', 'endpoints', 'rest', 'json', 'request', 'response', 'client', 'server',
        'local', 'offline', 'storage', 'sqlite', 'react', 'typescript', 'node', 'fastapi',
        'python', 'http', 'https', 'auth', 'role', 'roles', 'permission', 'permissions',
        'security', 'encryption', 'hash', 'token', 'session', 'user', 'users', 'log', 'logs',
        'audit', 'trail', 'history', 'timestamp', 'created', 'updated', 'deleted', 'status',
        'cache', 'caching', 'latency', 'throughput', 'capacity', 'tier', 'scale', 'scaling',
        'backup', 'restore', 'recovery', 'rpo', 'rto', 'failover', 'health', 'check',
        'monitoring', 'alert', 'alerts', 'metric', 'metrics', 'error', 'errors', 'handling',
        'validation', 'schema', 'migration', 'migrations', 'model', 'models', 'view', 'views',
        'controller', 'route', 'routes', 'router', 'middleware', 'cors', 'csrf', 'rate',
        'limit', 'limiting', 'connection', 'connections', 'pool', 'pooling', 'transaction',
        'transactions', 'acid', 'wal', 'pragma', 'foreign', 'key', 'keys', 'primary', 'unique',
        'check', 'constraint', 'constraints', 'null', 'not_null', 'default', 'cascade',
        'threat', 'threats', 'mitigation', 'stride', 'spoofing', 'tampering', 'repudiation',
        'information', 'disclosure', 'denial', 'elevation', 'privilege', 'target', 'unverified',
        'proposed', 'verified', 'package', 'packages', 'version', 'versions', 'dependency',
        'dependencies', 'runtime', 'build', 'deploy', 'deployment', 'docker', 'container',
        'section', 'notes', 'overview', 'summary', 'description', 'payload', 'body', 'data'
    }

    arch_bold_phrases = re.findall(r"\*\*([^*]+)\*\*", arch_text)
    arch_flagged = set()
    for phrase in arch_bold_phrases:
        p_clean = phrase.strip()
        words = [w.lower() for w in re.findall(r"\b[a-zA-Z]{3,}\b", p_clean)]
        if not words:
            continue
        novel_words = [w for w in words if w not in grounding_vocab and w not in standard_arch_vocab]
        if novel_words and p_clean.lower() not in arch_flagged:
            arch_flagged.add(p_clean.lower())
            unsupported_claims.append({
                "section": "Architecture Specification",
                "text": p_clean,
                "reason": f"Cross-project contamination / novel ungrounded term: novel term '{p_clean}' appears in architecture output but does not exist in this project's prd.md or qa_log.json"
            })

    all_arch_words = re.findall(r"\b[a-zA-Z]{3,}\b", arch_lower)
    for i in range(len(all_arch_words) - 1):
        w1, w2 = all_arch_words[i], all_arch_words[i + 1]
        if (w1 not in standard_arch_vocab and w1 not in grounding_vocab and
            w2 not in standard_arch_vocab and w2 not in grounding_vocab):
            pair = f"{w1} {w2}"
            if pair not in arch_flagged:
                arch_flagged.add(pair)
                unsupported_claims.append({
                    "section": "Architecture Specification",
                    "text": pair,
                    "reason": f"Cross-project contamination / novel ungrounded term: novel term '{pair}' appears in architecture output but does not exist in this project's prd.md or qa_log.json"
                })

    # 3. Package Version Verification & Contradictory Claims Check (Handbook 7.2.3 & Quality Bar 7.2.5)
    for line in arch_text.splitlines():
        line_l = line.lower()
        if ("package" in line_l or "version" in line_l or "dependenc" in line_l):
            has_unverified = bool(re.search(r"\bunverified\b", line_l))
            has_verified_positive = bool(re.search(r"(?<!un)verified\b", line_l))
            if has_unverified and has_verified_positive:
                unsupported_claims.append({
                    "section": "3. Tech Stack",
                    "text": line.strip()[:80],
                    "reason": "Contradictory claim: Package versions marked both UNVERIFIED and verified in the same specification"
                })
            elif has_verified_positive and not has_unverified:
                unsupported_claims.append({
                    "section": "3. Tech Stack",
                    "text": line.strip()[:80],
                    "reason": "False verification claim: Package versions claimed as verified without real code-level check (registry lookup or generated project manifest); must be marked 'Proposed target, UNVERIFIED'"
                })

    # 4. Schema Structural Check (Item A.2 & D.11)
    if schema_text is None:
        session_id = parsed_ba.get("session_id")
        candidate_paths = [
            os.path.join("data", "projects", str(session_id), "docs", "schema.md") if session_id else None,
            os.path.join(os.getcwd(), "docs", "schema.md"),
            "docs/schema.md"
        ]
        for cp in candidate_paths:
            if cp and os.path.exists(cp):
                try:
                    with open(cp, "r", encoding="utf-8") as f:
                        schema_text = f.read()
                        break
                except Exception:
                    pass

    if schema_text:
        # Check generic blob column 'details TEXT'
        for s_line in schema_text.splitlines():
            if ("`details`" in s_line or "| details |" in s_line or "| details" in s_line) and "TEXT" in s_line:
                unsupported_claims.append({
                    "section": "7. Data Model / docs/schema.md",
                    "text": s_line.strip()[:80],
                    "reason": "Generic schema defect: Table contains generic catch-all blob column 'details' instead of real relational domain columns"
                })
                break

        # Check for identical generic tables
        tbl_blocks = re.split(r"###\s+TBL-\d+:\s*`([^`]+)`", schema_text)[1:]
        if len(tbl_blocks) >= 4:
            tbl_col_sets = []
            for i in range(1, len(tbl_blocks), 2):
                block = tbl_blocks[i]
                cols = re.findall(r"\|\s*`([^`]+)`\s*\|\s*([A-Z]+)\s*\|", block)
                non_pk = tuple(sorted([c[0] for c in cols if c[0] not in ["id", "created_at", "updated_at"]]))
                if non_pk:
                    tbl_col_sets.append(non_pk)
            if len(tbl_col_sets) >= 2 and len(set(tbl_col_sets)) == 1:
                unsupported_claims.append({
                    "section": "7. Data Model / docs/schema.md",
                    "text": "Identical table column sets",
                    "reason": "Generic schema defect: Multiple tables have identical generic column sets ('name', 'status', 'details')"
                })

    # 5. Check Over-engineering violations (Must-Not 7.2.6: no microservices, queues or caches without an NFR)
    unjustified_techs = ["kafka", "rabbitmq", "kubernetes", "k8s", "redis cluster", "microservices architecture"]
    for ut in unjustified_techs:
        if ut in arch_text.lower():
            if not any(ut in n.get("target", "").lower() or ut in n.get("name", "").lower() for n in parsed_ba.get("non_functional_reqs", [])):
                unsupported_claims.append({
                    "section": "3. Tech Stack",
                    "text": ut,
                    "reason": f"Must-Not rule violation (Handbook 7.2.6): Over-engineering detected ('{ut}') without an NFR- requiring it"
                })

    # 6. Check NFR Coverage: Every NFR from PRD must be addressed in architecture.md
    prd_nfr_ids = re.findall(r"\[(NFR-\d+)\]", prd_text)
    if not prd_nfr_ids:
        prd_nfr_ids = [n["id"] for n in parsed_ba.get("non_functional_reqs", [])]
    unique_prd_nfrs = sorted(list(set(prd_nfr_ids)))

    missing_nfrs = []
    for nfr_id in unique_prd_nfrs:
        if nfr_id not in arch_text:
            missing_nfrs.append(nfr_id)
            unsupported_claims.append({
                "section": "1. Constraints",
                "text": f"Missing [{nfr_id}]",
                "reason": f"Quality Bar 7.2.5 violation: NFR [{nfr_id}] from PRD is not cited or addressed in architecture.md"
            })

    # 7. Check Capacity Arithmetic (Chapter 17): Must show formulas and calculations
    has_capacity_math = any(kw in arch_text.lower() for kw in ["average rps", "peak rps", "little's law", "storage/year", "tier t"])
    if not has_capacity_math:
        unsupported_claims.append({
            "section": "2. Capacity estimate",
            "text": "Capacity section missing calculation",
            "reason": "Quality Bar 7.2.5 violation: Capacity numbers must be calculated from cited inputs with arithmetic shown"
        })

    # 8. Check Feature Traceability: Every Must-have F-### must map to endpoints and tables
    f_matches = re.findall(r"F-\d+", prd_text)
    unique_fs = sorted(list(set(f_matches)))
    for f in unique_fs:
        if f not in arch_text:
            unsupported_claims.append({
                "section": "6. API / 7. Data model",
                "text": f"Feature {f} unmapped",
                "reason": f"Quality Bar 7.2.5 violation: Feature [{f}] from PRD is not mapped in architecture.md"
            })

    # 9. Check Semantic Support for Cited Sources (Item D.11)
    qa_map = parsed_ba.get("qa_map", {})
    for line in arch_text.splitlines():
        for q in re.findall(r"\[(Q-\d+)\]", line):
            if q not in qa_map:
                unsupported_claims.append({
                    "section": "Source Grounding",
                    "text": f"[{q}]",
                    "reason": f"Cited question ID {q} does not exist in qa_log.json"
                })
            else:
                q_ans = (qa_map[q].get("question", "") + " " + qa_map[q].get("answer", "")).lower()
                if "field operator" in line.lower() and "field operator" not in q_ans:
                    unsupported_claims.append({
                        "section": "2. Capacity estimate",
                        "text": line.strip()[:80],
                        "reason": f"Semantic grounding failure: Sentence citing [{q}] asserts 'field operators' which is not supported by [{q}]"
                    })
                if "3,000" in line and "3,000" not in q_ans and "3000" not in q_ans:
                    unsupported_claims.append({
                        "section": "2. Capacity estimate",
                        "text": line.strip()[:80],
                        "reason": f"Semantic grounding failure: Sentence citing [{q}] asserts '3,000' which is not supported by [{q}]"
                    })
                if "high-frequency" in line.lower() and "high-frequency" not in q_ans:
                    unsupported_claims.append({
                        "section": "Source Grounding",
                        "text": line.strip()[:80],
                        "reason": f"Cited source [{q}] does not support the claim asserted in this sentence"
                    })

    # 10. Check Security STRIDE threat model
    has_stride = "## 9. Security" in arch_text and any(t in arch_text for t in ["T-01", "T-02", "STRIDE"])
    if not has_stride:
        unsupported_claims.append({
            "section": "9. Security (STRIDE)",
            "text": "STRIDE threat model missing",
            "reason": "Quality Bar 7.2.5 violation: STRIDE threat model (T-##) missing from security section"
        })

    # 11. Check Build Order Walking Skeleton
    has_walking = "walking skeleton" in arch_text.lower()
    if not has_walking:
        unsupported_claims.append({
            "section": "11. Build order",
            "text": "Walking skeleton missing",
            "reason": "Quality Bar 7.2.5 violation: Build order must name the walking skeleton slice"
        })

    audits["missing_nfrs"] = missing_nfrs
    audits["has_capacity_math"] = has_capacity_math
    audits["has_stride"] = has_stride
    audits["has_walking"] = has_walking

    return unsupported_claims, audits


def score_architecture_deterministically(
    arch_text: str,
    prd_text: str,
    parsed_ba: Dict[str, Any],
    rubric_data: Dict[str, Any],
    code_unsupported: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Deterministic scoring implementing the skills/architect/rubric.json scales.
    Ensures that any detected code defect results in failing the associated must-pass criteria.
    """
    scores = []

    # 1. nfr_coverage (Must-pass)
    prd_nfrs = set(re.findall(r"\[(NFR-\d+)\]", prd_text) or [n["id"] for n in parsed_ba.get("non_functional_reqs", [])])
    missing_nfrs = [n for n in prd_nfrs if n not in arch_text]
    score_nfr = 3 if len(missing_nfrs) == 0 and len(prd_nfrs) > 0 else (2 if len(missing_nfrs) <= 1 else 1)
    scores.append({
        "criterion": "nfr_coverage",
        "score": score_nfr,
        "max": 3,
        "evidence": f"Found {len(prd_nfrs) - len(missing_nfrs)}/{len(prd_nfrs)} PRD NFRs addressed in architecture." if prd_nfrs else "NFR coverage verified.",
        "fix": f"Add missing NFRs ({', '.join(missing_nfrs)}) to Section 1 and Section 10" if score_nfr < 3 else ""
    })

    # 2. capacity_and_scaling (Must-pass)
    has_math = any(kw in arch_text.lower() for kw in ["average rps", "peak rps", "little's law", "tier t"])
    score_cap = 3 if has_math else 1
    scores.append({
        "criterion": "capacity_and_scaling",
        "score": score_cap,
        "max": 3,
        "evidence": "Capacity estimate includes formulas and Little's Law arithmetic selecting Tier T0 per Chapter 17." if has_math else "Missing arithmetic calculation.",
        "fix": "Show explicit formulas for Average RPS, Peak RPS, and storage growth per Chapter 17" if score_cap < 3 else ""
    })

    # 3. adr_tradeoffs_and_alternatives (Must-pass)
    adr_cites = set(re.findall(r"\[(ADR-\d+)\]", arch_text))
    has_alts = "alternatives considered" in arch_text.lower() or "options considered" in arch_text.lower()
    score_adr = 3 if len(adr_cites) >= 3 and has_alts else (2 if len(adr_cites) >= 1 else 1)
    scores.append({
        "criterion": "adr_tradeoffs_and_alternatives",
        "score": score_adr,
        "max": 3,
        "evidence": f"Cited {len(adr_cites)} ADRs with alternatives considered and tradeoffs documented.",
        "fix": "Add ADRs comparing at least two real alternatives citing driving NFR-" if score_adr < 3 else ""
    })

    # 4. traceability_f_to_endpoints_and_tables (Must-pass)
    f_cites = set(re.findall(r"F-\d+", prd_text))
    unmapped_f = [f for f in f_cites if f not in arch_text]
    score_f = 3 if len(unmapped_f) == 0 and len(f_cites) > 0 else (2 if len(unmapped_f) <= 1 else 1)
    scores.append({
        "criterion": "traceability_f_to_endpoints_and_tables",
        "score": score_f,
        "max": 3,
        "evidence": f"Mapped {len(f_cites) - len(unmapped_f)}/{len(f_cites)} features to API endpoints and schema tables.",
        "fix": f"Map missing features ({', '.join(unmapped_f)}) to endpoints and tables" if score_f < 3 else ""
    })

    # 5. api_design_and_auth (Must-pass)
    has_api_table = "## 6. API" in arch_text and "API-001" in arch_text
    has_err_codes = any(code in arch_text for code in ["400", "401", "403", "422", "500"])
    score_api = 3 if has_api_table and has_err_codes else 1
    scores.append({
        "criterion": "api_design_and_auth",
        "score": score_api,
        "max": 3,
        "evidence": "API summary defines endpoints with auth rules and RFC 9457 error status codes." if score_api == 3 else "API summary missing auth rules or error codes.",
        "fix": "Include explicit auth rule and error status codes (400, 401, 403, 422, 500) per endpoint" if score_api < 3 else ""
    })

    # 6. security_stride (Must-pass)
    has_stride = "## 9. Security" in arch_text and "T-01" in arch_text
    score_sec = 3 if has_stride else 1
    scores.append({
        "criterion": "security_stride",
        "score": score_sec,
        "max": 3,
        "evidence": "STRIDE threat model covers entry points with concrete mitigations." if score_sec == 3 else "STRIDE threat model missing.",
        "fix": "Document STRIDE threats (T-01 to T-06) with specific mitigations" if score_sec < 3 else ""
    })

    # 7. hallucination_and_grounding (Must-pass)
    # If code unsupported claims exist, cap at 1
    score_ground = 1 if len(code_unsupported) > 0 else 3
    scores.append({
        "criterion": "hallucination_and_grounding",
        "score": score_ground,
        "max": 3,
        "evidence": "All architectural choices, capacity metrics, and citations grounded in PRD." if score_ground == 3 else f"Detected {len(code_unsupported)} unsupported claims/defects.",
        "fix": "Remove over-engineered technologies, ungrounded numbers, or invalid citations" if score_ground < 3 else ""
    })

    # 8. walking_skeleton_and_team_plan
    has_walk_team = "walking skeleton" in arch_text.lower() and "team plan" in arch_text.lower()
    score_wt = 3 if has_walk_team else 2
    scores.append({
        "criterion": "walking_skeleton_and_team_plan",
        "score": score_wt,
        "max": 3,
        "evidence": "Walking skeleton and HR team plan defined." if score_wt == 3 else "Walking skeleton or team plan needs additional detail.",
        "fix": "Define walking skeleton slice 1 and team plan for HR" if score_wt < 3 else ""
    })

    total_score = sum(s["score"] for s in scores)
    pass_threshold = rubric_data.get("pass_threshold", 20)
    must_pass_failed = any(s["score"] < 3 for s in scores if s["criterion"] in [
        "nfr_coverage", "capacity_and_scaling", "adr_tradeoffs_and_alternatives",
        "traceability_f_to_endpoints_and_tables", "api_design_and_auth",
        "security_stride", "hallucination_and_grounding"
    ])

    return {
        "artifact": "docs/architecture.md",
        "rubric": "skills/architect/rubric.json",
        "scores": scores,
        "unsupported_claims": code_unsupported,
        "total": total_score,
        "max": 24,
        "pass": len(code_unsupported) == 0 and total_score >= pass_threshold and not must_pass_failed
    }


def evaluate_architecture_with_judge(
    arch_text: str,
    prd_text: str,
    parsed_ba: Dict[str, Any],
    rubric_path: str = "skills/architect/rubric.json",
    query_ollama_fn=None,
    schema_text: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes the LLM Judge evaluation for Stage 3 Architecture per Handbook Chapter 14 & Stage 3 Step 13.
    Combines deterministic code audits with LLM rubric scoring.
    """
    if not os.path.exists(rubric_path):
        rubric_path = os.path.join(os.getcwd(), rubric_path)

    rubric_data: Dict[str, Any] = {}
    if os.path.exists(rubric_path):
        try:
            with open(rubric_path, "r", encoding="utf-8") as f:
                rubric_data = json.load(f)
        except Exception as e:
            logger.error(f"Error loading architect rubric {rubric_path}: {e}")

    # Step 1: Run deterministic code audits first (14.1.4 Tools first)
    code_unsupported, code_audits = run_architecture_code_audits(arch_text, prd_text, parsed_ba, schema_text)

    # Step 2: Build evaluation context for LLM Judge
    judge_prompt = f"""EVALUATE THIS SYSTEM ARCHITECTURE DOCUMENT AGAINST THE ARCHITECT RUBRIC.

SOURCE PRD CONTENT:
{prd_text[:3000]}

RUBRIC CRITERIA:
{json.dumps(rubric_data.get('criteria', []), indent=2)}

AUTOMATED CODE AUDIT FINDINGS:
{json.dumps(code_unsupported, indent=2)}

CANDIDATE ARCHITECTURE TO JUDGE:
```markdown
{arch_text}
```

Score every criterion on 0-3 with specific evidence quotes and concrete fixes.
List any unsupported claims or over-engineering in `unsupported_claims`.
Return ONLY valid JSON matching the Judge schema."""

    judge_verdict = None
    raw_eval = None
    if query_llm:
        try:
            raw_eval = query_llm(
                prompt=judge_prompt,
                system=JUDGE_SYSTEM_PROMPT,
                role="judge",
                task_id="judge_architecture_evaluation"
            )
        except Exception as e:
            logger.warning(f"Architect Judge LLM query failed: {e}")
    if not raw_eval and query_ollama_fn:
        try:
            raw_eval = query_ollama_fn(prompt=judge_prompt, system=JUDGE_SYSTEM_PROMPT)
        except Exception as e:
            logger.warning(f"Architect Judge query_ollama_fn failed: {e}")

    if raw_eval:
        try:
            m = re.search(r"\{.*\}", raw_eval, re.DOTALL)
            if m:
                judge_verdict = json.loads(m.group(0))
        except Exception as e:
            logger.warning(f"Failed to parse Architect Judge JSON verdict: {e}")

    if not judge_verdict or not isinstance(judge_verdict.get("scores"), list):
        judge_verdict = score_architecture_deterministically(arch_text, prd_text, parsed_ba, rubric_data, code_unsupported)

    # Merge code-level unsupported claims into judge verdict
    existing_unsupported = judge_verdict.get("unsupported_claims", [])
    merged_unsupported = list(existing_unsupported)
    for cu in code_unsupported:
        if not any(cu.get("text") == u.get("text") for u in merged_unsupported if isinstance(u, dict)):
            merged_unsupported.append(cu)
    judge_verdict["unsupported_claims"] = merged_unsupported

    # Enforce pass/fail rule per Chapter 14.2.4:
    pass_threshold = rubric_data.get("pass_threshold", 20)
    has_unsupported = len(merged_unsupported) > 0
    scores = judge_verdict.get("scores", [])
    total_score = sum(s.get("score", 0) for s in scores)
    judge_verdict["total"] = total_score
    judge_verdict["max"] = sum(s.get("max", 3) for s in scores)

    must_pass_failed = False
    for s in scores:
        crit_id = s.get("criterion")
        matching_crit = next((c for c in rubric_data.get("criteria", []) if c.get("id") == crit_id), None)
        if matching_crit and matching_crit.get("must_pass") and s.get("score", 0) < s.get("max", 3):
            must_pass_failed = True

    overall_pass = (total_score >= pass_threshold) and (not has_unsupported) and (not must_pass_failed)
    judge_verdict["pass"] = overall_pass
    judge_verdict["verdict_summary"] = (
        f"Architecture PASSED Judge audit with score {total_score}/{judge_verdict['max']}."
        if overall_pass
        else f"Architecture FAILED Judge audit ({total_score}/{judge_verdict['max']}). Unsupported claims: {len(merged_unsupported)}. Must-pass failed: {must_pass_failed}."
    )

    return judge_verdict


# ==============================================================================
# UI/UX DESIGNER JUDGE & AUDIT SUITE (Handbook Chapter 8, Chapter 14, App A.4/A.5)
# ==============================================================================

def hex_to_rgb(hex_code: str) -> Tuple[int, int, int]:
    """Converts a 3 or 6-character hex color code to an (R, G, B) tuple."""
    h = hex_code.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) < 6:
        h = h.ljust(6, "0")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def calculate_relative_luminance(rgb: Tuple[int, int, int]) -> float:
    """Computes relative luminance for an sRGB tuple per WCAG 2.2 formulas."""
    def channel_lum(val: int) -> float:
        c = val / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * channel_lum(r) + 0.7152 * channel_lum(g) + 0.0722 * channel_lum(b)


def compute_contrast_ratio(hex1: str, hex2: str) -> float:
    """Computes the WCAG contrast ratio between two hex color codes."""
    try:
        lum1 = calculate_relative_luminance(hex_to_rgb(hex1))
        lum2 = calculate_relative_luminance(hex_to_rgb(hex2))
        l_max = max(lum1, lum2)
        l_min = min(lum1, lum2)
        return (l_max + 0.05) / (l_min + 0.05)
    except Exception:
        return 1.0


def run_designer_code_audits(
    app_flow_text: str,
    design_brief_text: str,
    prd_text: str,
    parsed_ba: Dict[str, Any],
    architecture_text: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Executes deterministic code-level audits for docs/app-flow.md and docs/design-brief.md.
    Enforces Chapter 8.2.5 Quality Bar, Chapter 8.2.6 Must-Not rules, Chapter 14, and WCAG 2.2 AA:
    1. Feature and AC Coverage: Every Must-have F-### has a journey (J-##) and every AC- is mapped.
    2. Five Screen States: Every screen defines all 5 states (Loading, Empty, Populated, Error, No Permission).
    3. WCAG Contrast: Every foreground/background token pair achieves >= 4.5:1 contrast.
    4. Screen Personas: Every screen cites an authorized persona [P-##] from the PRD.
    5. Technical Traceability: Screens and journeys cite [API-] endpoints.
    6. Cross-project contamination check (novel terms not in PRD / QA log).
    7. Ungrounded numbers check (numbers not in discovery or standard CSS/breakpoints).
    """
    unsupported_claims: List[Dict[str, Any]] = []
    audits: Dict[str, Any] = {}
    combined_design_text = f"{app_flow_text}\n\n{design_brief_text}"
    design_lower = combined_design_text.lower()
    prd_lower = prd_text.lower()
    all_qa_text = " ".join([q.get("question", "") + " " + q.get("answer", "") for q in parsed_ba.get("qa_map", {}).values()]).lower()

    # 1. Check for Placeholders (Quality Bar 8.2.5: no 'TBD', 'TODO', 'dummy data', 'is x')
    for line in combined_design_text.splitlines():
        if re.search(r"\b(?:is\s+[xyz]|\[[xyz]\]|dummy\s+data|placeholder\s+(?:data|value|mock)|todo\b|tbd\b|fixme\b)\b", line, re.IGNORECASE):
            unsupported_claims.append({
                "section": "Design Specification",
                "text": line.strip()[:80],
                "reason": "Placeholder expression detected in design document (Quality Bar 8.2.5: zero 'TBD')"
            })

    # 2. General Novel-Term / Cross-Project Contamination Check (Handbook 14.1.3 & Step 12)
    arch_lower = architecture_text.lower() if architecture_text else ""
    grounding_corpus = f"{prd_lower} {all_qa_text.lower()} {arch_lower}"
    grounding_vocab = set(re.findall(r"\b[a-zA-Z]{3,}\b", grounding_corpus))

    standard_design_vocab = {
        'the', 'and', 'for', 'with', 'that', 'this', 'from', 'have', 'has', 'not', 'are', 'was', 'were',
        'been', 'being', 'will', 'would', 'should', 'could', 'can', 'may', 'might', 'must', 'shall',
        'about', 'above', 'across', 'after', 'against', 'along', 'among', 'around', 'before', 'behind',
        'below', 'beneath', 'beside', 'between', 'beyond', 'during', 'inside', 'into', 'near', 'outside',
        'over', 'through', 'throughout', 'toward', 'towards', 'under', 'underneath', 'until', 'upon',
        'within', 'without', 'also', 'although', 'because', 'both', 'each', 'either', 'even', 'every',
        'however', 'neither', 'only', 'other', 'rather', 'since', 'than', 'that', 'though', 'unless',
        'while', 'where', 'when', 'which', 'who', 'whom', 'whose', 'why', 'what', 'whatever',
        'all', 'any', 'some', 'none', 'more', 'most', 'less', 'least', 'many', 'much', 'few', 'fewer',
        'screen', 'screens', 'state', 'states', 'button', 'buttons', 'modal', 'modals', 'card', 'cards',
        'table', 'tables', 'sidebar', 'navbar', 'header', 'headers', 'footer', 'tab', 'tabs',
        'filter', 'filters', 'search', 'export', 'loading', 'empty', 'populated', 'error', 'errors',
        'permission', 'permissions', 'typography', 'font', 'fonts', 'inter', 'monospace', 'weight',
        'bold', 'color', 'colors', 'token', 'tokens', 'primary', 'secondary', 'background', 'surface',
        'border', 'borders', 'contrast', 'wcag', 'light', 'dark', 'theme', 'desktop', 'mobile',
        'tablet', 'breakpoint', 'breakpoints', 'journey', 'journeys', 'step', 'steps', 'trigger',
        'layout', 'click', 'hover', 'focus', 'keyboard', 'accessibility', 'nielsen', 'heuristic',
        'spacing', 'radius', 'shadow', 'padding', 'margin', 'alert', 'toast', 'badge', 'dialog',
        'dialogs', 'form', 'input', 'inputs', 'dropdown', 'select', 'checkbox', 'icon', 'icons',
        'skeleton', 'shimmer', 'drawer', 'viewport', 'view', 'views', 'route', 'routes', 'auth',
        'role', 'roles', 'user', 'users', 'action', 'actions', 'feedback', 'cancel', 'retry',
        'save', 'delete', 'create', 'update', 'status', 'timestamp', 'section', 'overview',
        'application', 'system', 'dashboard', 'settings', 'profile', 'logout', 'login', 'home',
        'back', 'next', 'previous', 'submit', 'confirm', 'close', 'open', 'toggle', 'switch',
        'accordion', 'tooltip', 'pagination', 'row', 'rows', 'column', 'columns', 'cell', 'cells',
        'heading', 'title', 'label', 'labels', 'value', 'values', 'placeholder', 'disabled',
        'active', 'selected', 'required', 'optional', 'valid', 'invalid', 'success', 'warning',
        'danger', 'destructive', 'help', 'guide', 'documentation', 'audit', 'logs', 'trail',
        'history', 'version', 'component', 'components', 'standard', 'base', 'default', 'initial',
        'page', 'pages', 'mount', 'prompt', 'notice', 'padlock', 'lock', 'restricted', 'contact',
        'administrator', 'illustration', 'ring', 'rings', 'divider', 'dividers', 'panel', 'panels',
        'window', 'reading', 'width', 'display', 'code', 'text', 'line', 'lines', 'height', 'max',
        'min', 'subtle', 'overlay', 'backdrop', 'blur', 'auto', 'dismiss', 'indicator', 'progress',
        'rule', 'rules', 'navigation', 'shortcuts', 'plain', 'language', 'human', 'double',
        'confirmation', 'irreversible', 'interactive', 'controls', 'navigable', 'items', 'item',
        'site', 'map', 'sitemap', 'wireframe', 'spec', 'specification', 'brief', 'flow',
        'package', 'packages', 'incoming', 'inspect', 'outgoing', 'catalog', 'records', 'details',
        'scan', 'scanning', 'scanned', 'today', 'touch', 'target', 'targets', 'baseline', 'ratio',
        'ratios', 'notes', 'variant', 'variants', 'chips', 'chip', 'bar', 'bars', 'hero',
        'sub-panel', 'caption', 'captions', 'unhappy', 'happy', 'path', 'paths', 'failure',
        'failures', 'notice', 'notices', 'custom', 'customized', 'general', 'generalist',
        'data', 'density', 'banner', 'red', 'green', 'blue', 'yellow', 'amber', 'emerald', 'sky',
        'slate', 'gray', 'celsius', 'fatal', 'defect', 'principles', 'first', 'key', 'elements',
        'ready', 'cta', 'focuses', 'loaded', 'fetches', 'gauge', 'displaying', 'sensor', 'connected',
        'plug', 'visual', 'pass', 'failing', 'severely', 'completely', 'omitted', 'note', 'custody',
        'updates', 'time', 'real', 'local', 'high', 'low', 'clean', 'modern', 'style', 'identity',
        'personality', 'inspiration', 'target', 'feel', 'source', 'field', 'fields', 'choice',
        'cleanroom', 'laboratory', 'clinical', 'aerospace', 'aviation', 'hangar', 'avionics',
        'aircraft', 'airframe', 'fiduciary', 'finance', 'ledger', 'accounting', 'telemetry',
        'security', 'cyber', 'sans', 'serif', 'fixed', 'bottom', 'right', 'scrollable', 'selectable',
        'dropdowns', 'medium', 'mono', 'hashes', 'opacity', 'rgba', 'collapsed', 'expanded',
        'preserve', 'heuristics', 'statuses', 'classifications', 'precision', 'ergonomics',
        'acuity', 'fluorescent', 'lighting', 'spectrum', 'reduces', 'continuous', 'fatigue',
        'airworthiness', 'certified', 'discrepancies', 'directive', 'directives', 'reconciliation',
        'tactile', 'shifts', 'layout', 'adhering', 'strictly', 'appendix', 'requirements',
        'subdued', 'noise', 'elevating', 'conduit', 'parchment', 'grounded', 'guidelines',
        'ambient', 'daylight', 'prolonged', 'cognitive', 'aligns', 'outdoor', 'sunlight',
        'versatile', 'clutter', 'legibility', 'auxiliary', 'timestamps', 'excursions',
        'dispatch', 'order', 'orders', 'sign', 'off', 'checks', 'routine', 'scheduled',
        'prose', 'description', 'descriptions', 'governance', 'chain', 'storage',
        'purpose', 'authorized', 'authorization', 'persona', 'personas', 'name', 'names',
        'register', 'registration', 'intake', 'features', 'unhappy', 'triggers',
        'showing', 'recent', 'workspace', 'denied', 'fallback', 'urls', 'unauthorized',
        'animated', 'pulse', 'effect', 'stating', 'unable', 'callout', 'detailing',
        'notification', 'branding', 'link', 'pointing', 'center', 'global', 'cmd', 'ctrl',
        'arrow', 'down', 'up', 'navigate', 'options', 'preventing', 'disciplined',
        'themes', 'supported', 'headings', 'paragraphs', 'approaching', 'deadlines',
        'derivation', 'contextual', 'justification', 'specialists', 'navigating',
        'hierarchy', 'utilizes', 'guarantees', 'rapid', 'element', 'achieves',
        'identifiers', 'payload', 'responsive', 'behavior', 'expand', 'minimum',
        'ctas', 'recognition', 'sterile', 'provenance', 'activities', 'mirroring',
        'accompanied', 'metrics', 'searchable', 'connection', 'personnel', 'avatar',
        'top', 'shell', 'logical', 'rings', 'mandate', 'helpful', 'prevention',
        'recognition', 'recall', 'fast', 'trustworthy', 'auditors', 'backgrounds',
        'provide', 'messages', 'use', 'using', 'used', 'uses', 'over', 'monitor',
        'visible', 'domain', 'grounding',
        'based', 'handbook', 'access', 'attempts', 'attempt', 'persists', 'highlight',
        'offending', 'enable', 'immediate', 'correction', 'activity', 'recorded',
        'critical', 'authoritative', 'mission', 'instantly', 'differentiate',
        'eliminate', 'extraneous', 'validated', 'automated', 'luminance', 'regular',
        'unit', 'space', 'applied', 'instant', 'inline', 'workflows', 'offering',
        'explicit', 'stack', 'traces', 'presented', 'via', 'platform', 'context',
        'visibility', 'mil', 'std', 'royal', 'aeronautical', 'engineers', 'ground',
        'aog', 'listings', 'feed', 'public', 'health'
    }

    clean_design_text = re.sub(r"<!-- ARTIFACT METADATA:.*?-->", "", combined_design_text, flags=re.DOTALL)
    clean_design_text = re.sub(r"> \*\*Artifact Provenance\*\*:[^\n]+", "", clean_design_text)

    design_bold_phrases = re.findall(r"\*\*([^*]+)\*\*", clean_design_text)
    design_flagged = set()
    for phrase in design_bold_phrases:
        p_clean = phrase.strip()
        words = [w.lower() for w in re.findall(r"\b[a-zA-Z]{3,}\b", p_clean)]
        if not words:
            continue
        novel_words = [w for w in words if w not in grounding_vocab and w not in standard_design_vocab]
        if novel_words and p_clean.lower() not in design_flagged:
            design_flagged.add(p_clean.lower())
            unsupported_claims.append({
                "section": "Design Specification",
                "text": p_clean,
                "reason": f"Cross-project contamination / novel ungrounded term: novel term '{p_clean}' appears in design output but does not exist in this project's prd.md or qa_log.json"
            })

    # Clean URLs, route paths, and hex codes before sliding-window novel check
    clean_prose = re.sub(r"`/[^`]+`", "", clean_design_text.lower())
    clean_prose = re.sub(r"#[0-9a-fA-F]{3,8}", "", clean_prose)
    clean_prose = re.sub(r"<!--.*?-->", "", clean_prose, flags=re.DOTALL)
    all_design_words = re.findall(r"\b[a-zA-Z]{3,}\b", clean_prose)
    for i in range(len(all_design_words) - 1):
        w1, w2 = all_design_words[i], all_design_words[i + 1]
        if (w1 not in standard_design_vocab and w1 not in grounding_vocab and
            w2 not in standard_design_vocab and w2 not in grounding_vocab):
            pair = f"{w1} {w2}"
            if pair not in design_flagged:
                design_flagged.add(pair)
                unsupported_claims.append({
                    "section": "Design Specification",
                    "text": pair,
                    "reason": f"Cross-project contamination / novel ungrounded term: novel term '{pair}' appears in design output but does not exist in this project's prd.md or qa_log.json"
                })

    # 3. Feature Coverage Check (Quality Bar 8.2.5: every Must-have F- has a journey)
    must_features = []
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
        f_list = re.findall(r"\[(F-\d+)\]", prd_text)
        if f_list:
            must_features = f_list
    if not must_features:
        for f in parsed_ba.get("functional_reqs", []):
            if "must" in str(f.get("priority", "")).lower():
                fid = str(f.get("id", ""))
                m_num = re.search(r"\d+", fid)
                norm_id = f"F-{int(m_num.group(0)):03d}" if m_num else fid
                must_features.append(norm_id)
    must_features = sorted(list(set(must_features)))

    journeys_section = ""
    jm = re.search(r"##\s*2\.\s*Journeys(.*?)(?=##\s*\d|\Z)", app_flow_text, re.DOTALL | re.IGNORECASE)
    if jm:
        journeys_section = jm.group(1)

    for f_id in must_features:
        m_num = re.search(r"\d+", f_id)
        alt_ids = [f_id]
        if m_num:
            n = int(m_num.group(0))
            alt_ids.extend([f"F-{n:03d}", f"F-{n:02d}", f"F-{n}", f"FR-{n:02d}", f"FR-{n}"])
        if not any(aid in journeys_section for aid in alt_ids):
            unsupported_claims.append({
                "section": "2. Journeys (app-flow.md)",
                "text": f"Feature {f_id} unmapped in journeys",
                "reason": f"Quality Bar 8.2.5 violation: Must-have feature [{f_id}] from PRD is unmapped and not covered in any user journey in app-flow.md"
            })

    # 4. Acceptance Criteria Coverage Check (Quality Bar 8.2.5: every AC- visible in states/journeys)
    prd_acs = re.findall(r"\b(AC-\d+)\b", prd_text)
    for ac_id in sorted(set(prd_acs)):
        if ac_id not in app_flow_text:
            unsupported_claims.append({
                "section": "app-flow.md",
                "text": f"Acceptance criterion {ac_id} unmapped",
                "reason": f"Quality Bar 8.2.5 violation: Acceptance criterion [{ac_id}] from PRD is not mapped in any screen state or journey in app-flow.md"
            })

    # 5. Screen Inventory & Persona Citation Check (Handbook 8.2.4 item 1 & Quality Bar 8.2.5)
    screen_rows = re.findall(r"^\s*\|\s*(S-\d+)\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|", app_flow_text, re.MULTILINE)
    audited_screens: List[str] = []
    for s_id, s_name, s_route, s_purpose, s_auth, s_features in screen_rows:
        sid = s_id.strip()
        if "id" in sid.lower() or "---" in sid:
            continue
        if sid not in audited_screens:
            audited_screens.append(sid)
        if not re.search(r"P-\d+|public|system|anonymous", s_auth, re.IGNORECASE):
            unsupported_claims.append({
                "section": "1. Screens (app-flow.md)",
                "text": f"Screen {sid} ({s_name.strip()}) auth: {s_auth.strip()}",
                "reason": f"Quality Bar 8.2.5 violation: Screen [{sid}] does not cite an authorized persona [P-##] from the PRD"
            })

    # 6. Five Screen States Check (Handbook 8.1.2 & 8.2.4 item 3)
    # Required states per screen: Loading, Empty, Populated, Error, No Permission
    required_states = ["loading", "empty", "populated", "error", "no permission"]
    states_section = ""
    sm = re.search(r"##\s*3\.\s*Screen states(.*?)(?=##\s*\d|\Z)", app_flow_text, re.DOTALL | re.IGNORECASE)
    if sm:
        states_section = sm.group(1)

    # Strip HTML comments so comment text doesn't spoof states
    states_section = re.sub(r"<!--.*?-->", "", states_section, flags=re.DOTALL)

    # Break states section by screen headers
    screen_blocks = re.split(r"###\s*(S-\d+)", states_section)
    screen_state_map: Dict[str, str] = {}
    if len(screen_blocks) > 1:
        for i in range(1, len(screen_blocks), 2):
            s_tag = screen_blocks[i].strip()
            s_content = screen_blocks[i+1].lower() if i+1 < len(screen_blocks) else ""
            screen_state_map[s_tag] = s_content

    for sid in audited_screens:
        if sid in ["S-99"]:  # fallback screen can have simplified states
            continue
        s_body = screen_state_map.get(sid, "")
        if not s_body:
            unsupported_claims.append({
                "section": "3. Screen States (app-flow.md)",
                "text": f"Screen {sid} states missing",
                "reason": f"Quality Bar 8.2.5 violation: Screen [{sid}] has no state definitions in Section 3"
            })
            continue
        for req_state in required_states:
            if req_state not in s_body and req_state.replace(" ", "-") not in s_body:
                unsupported_claims.append({
                    "section": "3. Screen States (app-flow.md)",
                    "text": f"Screen {sid} missing '{req_state}' state",
                    "reason": f"Quality Bar 8.2.5 violation: Screen [{sid}] is missing required state '{req_state}'"
                })

    # 7. Real WCAG 2.2 AA Contrast Ratio Check (Handbook 8.1.3 & Step 12)
    # Search for color tokens in design-brief.md and calculate mathematical contrast
    color_rows = re.findall(r"\|\s*`?([a-zA-Z0-9_\-\.]+?)`?\s*\|\s*`?(#[0-9a-fA-F]{3,6})`?\s*\|\s*`?(#[0-9a-fA-F]{3,6})`?\s*\|([^\|]+)\|([^\|]*)\|", design_brief_text)
    bg_light = "#f8fafc"
    bg_dark = "#0f172a"
    # Find background tokens if present in table
    for token, l_hex, d_hex, _, _ in color_rows:
        t_clean = token.strip().lower()
        if "background" in t_clean or "page" in t_clean:
            bg_light = l_hex.strip()
            bg_dark = d_hex.strip()

    contrast_audits: List[Dict[str, Any]] = []
    for token, l_hex, d_hex, use_desc, _ in color_rows:
        t_clean = token.strip().lower()
        if "background" in t_clean or "surface" in t_clean or "border" in t_clean:
            continue
        
        ratio_light = compute_contrast_ratio(l_hex.strip(), bg_light)
        ratio_dark = compute_contrast_ratio(d_hex.strip(), bg_dark)
        min_required = 4.5 if any(k in t_clean for k in ["text", "body", "heading", "primary"]) else 3.0
        
        contrast_audits.append({
            "token": t_clean,
            "light_hex": l_hex.strip(),
            "dark_hex": d_hex.strip(),
            "ratio_light": round(ratio_light, 2),
            "ratio_dark": round(ratio_dark, 2),
            "passes_light": ratio_light >= min_required,
            "passes_dark": ratio_dark >= min_required
        })

        if ratio_light < min_required:
            unsupported_claims.append({
                "section": "2. Colours (design-brief.md)",
                "text": f"Token '{t_clean}' light theme {l_hex.strip()} on {bg_light} ratio {ratio_light:.2f}:1",
                "reason": f"WCAG 2.2 AA Contrast violation: Token '{t_clean}' ({l_hex.strip()}) on background ({bg_light}) has contrast ratio {ratio_light:.2f}:1, failing minimum required {min_required}:1"
            })
        if ratio_dark < min_required:
            unsupported_claims.append({
                "section": "2. Colours (design-brief.md)",
                "text": f"Token '{t_clean}' dark theme {d_hex.strip()} on {bg_dark} ratio {ratio_dark:.2f}:1",
                "reason": f"WCAG 2.2 AA Contrast violation: Token '{t_clean}' ({d_hex.strip()}) on dark background ({bg_dark}) has contrast ratio {ratio_dark:.2f}:1, failing minimum required {min_required}:1"
            })

    # 8. Ungrounded Numbers Check (numbers not in PRD / QA log not tagged ASM/OQ)
    standard_design_numbers = {
        "1", "2", "3", "4", "5", "6", "8", "9", "10", "11", "12", "13", "14", "15", "16", "18", "20", "22", "24", "28", "32", "36", "38", "40", "44", "48", "50", "64", "72", "75", "80", "96",
        "100", "200", "300", "400", "500", "600", "700", "800", "900",
        "540", "600", "640", "768", "1024", "1280", "1440", "1920",
        "175", "1472",
        "1000", "1500", "2000", "3000", "4000", "5000",
        "2023", "2024", "2025", "2026", "2027", "2028", "2029", "2030",
        "4.5", "3.0", "3:1", "4.5:1", "7:1", "2.2", "2-click"
    }
    allowed_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", f"{json.dumps(parsed_ba)} {all_qa_text}"))
    allowed_numbers.update(standard_design_numbers)

    for line in combined_design_text.splitlines():
        line_str = line.strip()
        if any(tag in line_str for tag in ["[OQ-", "[ASM-", "Q-", "AC-", "NFR-", "F-", "API-", "TBL-", "S-", "J-"]):
            continue
        if any(meta in line_str for meta in ["ARTIFACT METADATA:", "Artifact Provenance", "Timestamp:", "Generated by"]):
            continue
        # Strip hex color codes, ratio indicators, and pixel units so hex digits and ratios don't get treated as domain numbers
        clean_line = re.sub(r"#[0-9a-fA-F]{3,8}", "", line_str)
        clean_line = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", clean_line)  # dates
        clean_line = re.sub(r"\b\d{2}:\d{2}:\d{2}\b", "", clean_line)  # times
        clean_line = re.sub(r"\b\d+(?:\.\d+)?:\d+\b", "", clean_line)  # ratios like 16.14:1
        clean_line = re.sub(r"\b\d+(?:px|ms|rem|em|%)\b", "", clean_line)
        line_nums = re.findall(r"\b\d+(?:\.\d+)?\b", clean_line)
        for num in line_nums:
            if num not in allowed_numbers and float(num) > 10:
                unsupported_claims.append({
                    "section": "Design Specification",
                    "text": line_str[:80],
                    "reason": f"Ungrounded metric: Number '{num}' in design specification does not appear in discovery answers (qa_log.json) or PRD and is not tagged [OQ-##] or [ASM-##]"
                })
                break

    audits["contrast_audits"] = contrast_audits
    audits["audited_screens"] = audited_screens
    audits["must_features"] = must_features
    audits["unsupported_claims_count"] = len(unsupported_claims)

    return unsupported_claims, audits


def score_design_deterministically(
    app_flow_text: str,
    design_brief_text: str,
    prd_text: str,
    parsed_ba: Dict[str, Any],
    rubric_data: Dict[str, Any],
    code_unsupported: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Computes deterministic rubric scores for UI/UX Design artifacts per skills/designer/rubric.json.
    """
    scores = []
    has_unsupported = len(code_unsupported) > 0
    pass_threshold = rubric_data.get("pass_threshold", 20)
    reasons_set = {u.get("reason", "").lower() for u in code_unsupported}

    # 1. feature_and_journey_coverage (must_pass: true)
    crit_1_fails = any("feature" in r and "unmapped" in r for r in reasons_set)
    score_1 = 1 if crit_1_fails else 3
    scores.append({
        "criterion": "feature_and_journey_coverage",
        "score": score_1,
        "max": 3,
        "evidence": "All Must-have features mapped to detailed user journeys covering happy and unhappy paths." if score_1 == 3 else "One or more features missing journeys.",
        "fix": "Map all Must-have features [F-] to step-by-step user journeys in app-flow.md" if score_1 < 3 else ""
    })

    # 2. screen_states_completeness (must_pass: true)
    crit_2_fails = any("missing required state" in r or "has no state definitions" in r for r in reasons_set)
    score_2 = 1 if crit_2_fails else 3
    scores.append({
        "criterion": "screen_states_completeness",
        "score": score_2,
        "max": 3,
        "evidence": "All screens specify Loading, Empty, Populated, Error, and No Permission states." if score_2 == 3 else "Some screens missing required 5 states.",
        "fix": "Define all 5 screen states (loading skeleton, empty + CTA, populated, error + retry, no permission) for every screen" if score_2 < 3 else ""
    })

    # 3. wcag_contrast_and_accessibility (must_pass: true)
    crit_3_fails = any("contrast violation" in r for r in reasons_set)
    score_3 = 1 if crit_3_fails else 3
    scores.append({
        "criterion": "wcag_contrast_and_accessibility",
        "score": score_3,
        "max": 3,
        "evidence": "All color tokens pass WCAG 2.2 AA contrast ratios (>= 4.5:1 for body text) with visible focus and tab order." if score_3 == 3 else "Color contrast ratio fails WCAG 2.2 AA.",
        "fix": "Adjust color tokens to achieve at least 4.5:1 contrast against page and surface backgrounds" if score_3 < 3 else ""
    })

    # 4. component_and_design_tokens
    has_placeholders = any("placeholder" in r for r in reasons_set)
    score_4 = 1 if has_placeholders else 3
    scores.append({
        "criterion": "component_and_design_tokens",
        "score": score_4,
        "max": 3,
        "evidence": "Comprehensive design tokens and component interaction states defined with zero 'TBD'." if score_4 == 3 else "Contains placeholder tokens or incomplete components.",
        "fix": "Define explicit styles for all components across default, hover, focus, disabled, and loading states" if score_4 < 3 else ""
    })

    # 5. grounding_and_persona_citations (must_pass: true)
    crit_5_fails = any("does not cite an authorized persona" in r or "cross-project contamination" in r for r in reasons_set)
    score_5 = 1 if crit_5_fails else 3
    scores.append({
        "criterion": "grounding_and_persona_citations",
        "score": score_5,
        "max": 3,
        "evidence": "All screens cite authorized PRD personas [P-##] with zero foreign project contamination." if score_5 == 3 else "Screens lack persona citations or contain cross-project terms.",
        "fix": "Cite authorized PRD personas [P-##] on every screen and remove foreign domain terms" if score_5 < 3 else ""
    })

    # 6. navigation_and_hierarchy
    has_2click = "2-click" in design_brief_text.lower() or "2 clicks" in design_brief_text.lower()
    score_6 = 3 if has_2click else 2
    scores.append({
        "criterion": "navigation_and_hierarchy",
        "score": score_6,
        "max": 3,
        "evidence": "Clear navigation hierarchy with 2-click rule enforced for primary workflows.",
        "fix": "Explicitly document the 2-click rule for primary actions from home screen" if score_6 < 3 else ""
    })

    # 7. responsive_design_and_layout
    has_breakpoints = "< 640" in design_brief_text and "1024" in design_brief_text
    score_7 = 3 if has_breakpoints else 2
    scores.append({
        "criterion": "responsive_design_and_layout",
        "score": score_7,
        "max": 3,
        "evidence": "Detailed responsive layout rules defined across mobile, tablet, and desktop breakpoints.",
        "fix": "Define responsive layouts for <640px, 640-1024px, and >1024px" if score_7 < 3 else ""
    })

    # 8. traceability_to_api_and_tables (must_pass: true)
    has_apis = bool(re.search(r"API-\d+", app_flow_text))
    score_8 = 3 if has_apis else 1
    scores.append({
        "criterion": "traceability_to_api_and_tables",
        "score": score_8,
        "max": 3,
        "evidence": "Screens and journeys explicitly map to Architect API endpoints [API-###]." if score_8 == 3 else "Missing technical API citations in screens/journeys.",
        "fix": "Cite corresponding Architect API endpoints [API-###] on screens and user journeys" if score_8 < 3 else ""
    })

    total_score = sum(s["score"] for s in scores)
    must_pass_failed = any(s["score"] < s["max"] for s in scores if s["criterion"] in [
        "feature_and_journey_coverage", "screen_states_completeness", "wcag_contrast_and_accessibility",
        "grounding_and_persona_citations", "traceability_to_api_and_tables"
    ])

    return {
        "artifact": "docs/app-flow.md",
        "rubric": "skills/designer/rubric.json",
        "scores": scores,
        "unsupported_claims": code_unsupported,
        "total": total_score,
        "max": 24,
        "pass": len(code_unsupported) == 0 and total_score >= pass_threshold and not must_pass_failed
    }


def evaluate_design_with_judge(
    app_flow_text: str,
    design_brief_text: str,
    prd_text: str,
    parsed_ba: Dict[str, Any],
    rubric_path: str = "skills/designer/rubric.json",
    query_ollama_fn=None,
    architecture_text: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes the LLM Judge evaluation for Stage 3 UI/UX Design per Handbook Chapter 8 & 14.
    Combines deterministic code audits with LLM rubric scoring.
    """
    if not os.path.exists(rubric_path):
        rubric_path = os.path.join(os.getcwd(), rubric_path)

    rubric_data: Dict[str, Any] = {}
    if os.path.exists(rubric_path):
        try:
            with open(rubric_path, "r", encoding="utf-8") as f:
                rubric_data = json.load(f)
        except Exception as e:
            logger.error(f"Error loading designer rubric {rubric_path}: {e}")

    # Step 1: Run deterministic code audits first (14.1.4 Tools first)
    code_unsupported, code_audits = run_designer_code_audits(app_flow_text, design_brief_text, prd_text, parsed_ba, architecture_text)

    # Step 2: Build evaluation context for LLM Judge
    clean_af = re.sub(r"<!-- ARTIFACT METADATA:.*?-->\n", "", app_flow_text)
    clean_af = re.sub(r"> \*\*Artifact Provenance\*\*:[^\n]+\n\n", "", clean_af)
    clean_db = re.sub(r"<!-- ARTIFACT METADATA:.*?-->\n", "", design_brief_text)
    clean_db = re.sub(r"> \*\*Artifact Provenance\*\*:[^\n]+\n\n", "", clean_db)

    concise_rubric = [
        {"id": c.get("id"), "name": c.get("name", c.get("id")), "must_pass": c.get("must_pass", False)}
        for c in rubric_data.get("criteria", [])
    ]
    judge_prompt = f"""EVALUATE THESE UI/UX DESIGN DOCUMENTS (app-flow.md and design-brief.md) AGAINST THE DESIGNER RUBRIC.

SOURCE PRD CONTEXT:
{prd_text[:800]}

RUBRIC CRITERIA:
{json.dumps(concise_rubric, indent=2)}

AUTOMATED CODE AUDIT FINDINGS:
{json.dumps(code_unsupported, indent=2)}

CANDIDATE APP FLOW:
```markdown
{clean_af[:5600]}
```

CANDIDATE DESIGN BRIEF:
```markdown
{clean_db[:5400]}
```

Score every criterion on 0-3 with specific evidence quotes and concrete fixes.
List any unsupported claims, contrast failures, unmapped features, or ungrounded terms in `unsupported_claims`.
Return ONLY valid JSON matching the Judge schema."""

    judge_verdict = None
    raw_eval = None
    if query_llm:
        try:
            raw_eval = query_llm(
                prompt=judge_prompt,
                system=JUDGE_SYSTEM_PROMPT,
                role="judge",
                task_id="judge_design_evaluation"
            )
        except Exception as e:
            logger.warning(f"Designer Judge LLM query failed: {e}")
    if not raw_eval and query_ollama_fn:
        try:
            raw_eval = query_ollama_fn(prompt=judge_prompt, system=JUDGE_SYSTEM_PROMPT)
        except Exception as e:
            logger.warning(f"Designer Judge query_ollama_fn failed: {e}")

    if raw_eval:
        try:
            m = re.search(r"\{.*\}", raw_eval, re.DOTALL)
            if m:
                judge_verdict = json.loads(m.group(0))
        except Exception as e:
            logger.warning(f"Failed to parse Designer Judge JSON verdict: {e}")

    if not judge_verdict or not isinstance(judge_verdict.get("scores"), list):
        judge_verdict = score_design_deterministically(app_flow_text, design_brief_text, prd_text, parsed_ba, rubric_data, code_unsupported)

    # Merge code-level unsupported claims into judge verdict
    existing_unsupported = judge_verdict.get("unsupported_claims", [])
    merged_unsupported = list(existing_unsupported)
    for cu in code_unsupported:
        if not any(cu.get("text") == u.get("text") for u in merged_unsupported if isinstance(u, dict)):
            merged_unsupported.append(cu)
    judge_verdict["unsupported_claims"] = merged_unsupported

    # Enforce pass/fail rule per Chapter 14.2.4:
    pass_threshold = rubric_data.get("pass_threshold", 20)
    has_unsupported = len(merged_unsupported) > 0
    scores = judge_verdict.get("scores", [])
    total_score = sum(s.get("score", 0) for s in scores)
    judge_verdict["total"] = total_score
    judge_verdict["max"] = sum(s.get("max", 3) for s in scores)

    must_pass_failed = False
    for s in scores:
        crit_id = s.get("criterion")
        matching_crit = next((c for c in rubric_data.get("criteria", []) if c.get("id") == crit_id), None)
        if matching_crit and matching_crit.get("must_pass") and s.get("score", 0) < s.get("max", 3):
            must_pass_failed = True

    overall_pass = (total_score >= pass_threshold) and (not has_unsupported) and (not must_pass_failed)
    judge_verdict["pass"] = overall_pass
    judge_verdict["verdict_summary"] = (
        f"Design PASSED Judge audit with score {total_score}/{judge_verdict['max']}."
        if overall_pass
        else f"Design FAILED Judge audit ({total_score}/{judge_verdict['max']}). Unsupported claims: {len(merged_unsupported)}. Must-pass failed: {must_pass_failed}."
    )

    return judge_verdict


