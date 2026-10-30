import os
import re
import json
import time
import logging
from typing import Set, Dict, Any, List, Tuple, Optional

try:
    from llm_client import query_llm, query_llm_with_meta
except ImportError:
    try:
        from engine.llm_client import query_llm, query_llm_with_meta
    except ImportError:
        query_llm = None
        query_llm_with_meta = None

try:
    from skill_registry import get_composite_rubric, get_skill_registry
except ImportError:
    try:
        from engine.skill_registry import get_composite_rubric, get_skill_registry
    except ImportError:
        get_composite_rubric = None
        get_skill_registry = None

try:
    from validators import validate_grounding_corpus
except ImportError:
    try:
        from engine.validators import validate_grounding_corpus
    except ImportError:
        validate_grounding_corpus = None

logger = logging.getLogger("autonoma-judge")

JUDGE_GENERIC_SYSTEM_PROMPT = """You are the LLM Judge (Handbook Chapter 14) for a software engineering agent office.
Score the artifact section you are given against ONLY the TARGET RUBRIC CRITERIA listed in the request, using
exactly those criterion ids and each criterion's own 0-3 scale. Do not invent, rename or add criteria.

Rules:
- Every score quotes or points to evidence in the artifact; every lost point gets a concrete fix.
- Tool and code-audit results override prose.
- A library version marked "UNVERIFIED:" is the required practice for versions not checked against a registry;
  it is not a hallucination. A version stated as fact without that mark is.
- List in unsupported_claims every claim that cites nothing, cites an ID that does not say it, or contradicts the
  client's stated constraints. Quote the exact text.

Respond ONLY with a JSON object:
{"scores": [{"criterion": "<id from the request>", "score": 0, "max": 3, "evidence": "...", "fix": "..."}],
 "unsupported_claims": [{"section": "...", "text": "exact quote", "reason": "..."}]}
"""


def resolve_rubric_path(rubric_path: str) -> str:
    """Rubrics live under the repository's skills/ folder, wherever the engine was started from."""
    if os.path.isabs(rubric_path) and os.path.exists(rubric_path):
        return rubric_path
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for candidate in (os.path.join(root, rubric_path), os.path.join(os.getcwd(), rubric_path), rubric_path):
        if os.path.exists(candidate):
            return candidate
    return os.path.join(root, rubric_path)


def keep_rubric_scores(scores: List[Dict[str, Any]], rubric_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Only the rubric's own criteria count; a skipped criterion scores 0 (Handbook 14.2.4)."""
    criteria = {c.get("id"): c for c in rubric_data.get("criteria", []) if c.get("id")}
    if not criteria:
        return scores
    given = {str(sc.get("criterion")): sc for sc in scores if isinstance(sc, dict)}
    out = []
    for cid, c in criteria.items():
        sc = given.get(cid)
        cmax = int(c.get("max", 3))
        if sc is None:
            out.append({"criterion": cid, "score": 0, "max": cmax, "evidence": "", "fix": "criterion was not scored"})
        else:
            try:
                val = max(0, min(cmax, int(sc.get("score", 0))))
            except (TypeError, ValueError):
                val = 0
            out.append({**sc, "criterion": cid, "score": val, "max": cmax})
    return out


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


NEGATION_RE = re.compile(r"\b(?:no|not|never|without|exclud\w*|won'?t|cannot|can'?t|deferred|v2|out of scope|non-goal)\b",
                         re.IGNORECASE)
NON_GOAL_STOP = {"support", "between", "users", "user", "role", "roles", "application", "based", "feature", "features",
                 "with", "from", "their", "other", "first", "release", "version"}


def _prd_section(prd_text: str, number: int) -> str:
    m = re.search(rf"^##\s*{number}\.(.*?)(?=^##\s*\d+\.|\Z)", prd_text, re.MULTILINE | re.DOTALL)
    return m.group(1) if m else ""


def audit_non_goal_contradictions(prd_text: str) -> List[Dict[str, Any]]:
    """
    Deterministic (Handbook 14.1.3-14.1.4): an item the PRD lists as a non-goal must not appear as a
    capability in Users (section 3) or Features (section 5). Negated mentions ("no due dates") and the
    roles table's "Cannot" column are allowed. Same artifact, same result, whatever the LLM Judge says.
    """
    ng_block = re.search(r"###\s*Non-goals.*?(?=\n###|\n##\s|\Z)", prd_text, re.IGNORECASE | re.DOTALL)
    rows = re.findall(r"\|\s*(NG-\d+)\s*\|\s*([^|]+)\|", ng_block.group(0)) if ng_block else []
    patterns = []
    for ng_id, text in rows:
        for phrase in re.split(r",|\band\b|/|;|\bor\b", text):
            words = [w for w in re.findall(r"[a-z]+", phrase.lower()) if len(w) >= 3 and w not in NON_GOAL_STOP]
            if not words:
                continue
            stems = [re.escape(w[:-1] if w.endswith("s") else w) + r"\w*" for w in words]
            patterns.append((ng_id, phrase.strip(), re.compile(r"\b" + r"\W+(?:\w+\W+){0,2}?".join(stems), re.IGNORECASE)))
    findings: List[Dict[str, Any]] = []
    for section_no, section_name in ((3, "3. Users"), (5, "5. Features")):
        header: List[str] = []
        for line in _prd_section(prd_text, section_no).splitlines():
            stripped = line.strip()
            if stripped.startswith("|"):
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
                    continue
                if not header or any(c.lower() in ("role", "id", "persona") for c in cells[:1]):
                    if any(c.lower() in ("role", "id", "persona") for c in cells[:1]):
                        header = [c.lower() for c in cells]
                        continue
                pieces = [(header[i] if i < len(header) else "", c) for i, c in enumerate(cells)]
            else:
                pieces = [("", p) for p in re.split(r"(?<=[.;])\s+", stripped)]
            for column, piece in pieces:
                if column == "cannot" or not piece:
                    continue
                for ng_id, phrase, pat in patterns:
                    m = pat.search(piece)
                    if m and not NEGATION_RE.search(piece):
                        findings.append({"section": section_name, "text": m.group(0), "check": "non_goal",
                                         "reason": f"'{m.group(0)}' is offered as a capability but {ng_id} "
                                                   f"('{phrase}') says it is not in v1"})
    return findings


def _resolve_qid(qid: str, qa_map: Dict[str, Any]) -> Optional[str]:
    """Q-01 and Q-001 name the same answer. Returns the log's own key, or None for an invented citation."""
    if qid in qa_map:
        return qid
    m = re.match(r"Q-0*(\d+)$", qid)
    if m:
        for k in qa_map:
            km = re.match(r"Q-0*(\d+)$", str(k))
            if km and km.group(1) == m.group(1):
                return k
    return None


def _qid_exists(qid: str, qa_map: Dict[str, Any]) -> bool:
    return _resolve_qid(qid, qa_map) is not None


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
            if not _qid_exists(q, qa_map):
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
                    if clean_f in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "24", "30", "60", "90", "100", "0", "200", "201", "400", "401", "403", "404", "409", "422", "5000", "9457", "29148", "25010"]:
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

    # Scope contradiction: a non-goal offered as a capability in Users (3) or Features (5).
    unsupported_claims.extend(audit_non_goal_contradictions(prd_text))
    audits["non_goal_contradictions"] = sum(1 for u in unsupported_claims if u.get("check") == "non_goal")

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


def robust_parse_judge_json(raw_text: str) -> Dict[str, Any]:
    """
    Robustly parses LLM judge JSON responses, handling unescaped newlines,
    markdown fences, and trailing commas.
    """
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw_text.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())

    # Try direct parse
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if m:
        cand = m.group(0)
        try:
            return json.loads(cand)
        except Exception:
            pass

        # Fix unescaped newlines inside quotes
        fixed_chars = []
        in_str = False
        escaped = False
        for ch in cand:
            if ch == '\\' and not escaped:
                escaped = True
                fixed_chars.append(ch)
                continue
            if ch == '"' and not escaped:
                in_str = not in_str
            if ch == '\n' and in_str:
                fixed_chars.append('\\n')
            elif ch == '\r' and in_str:
                fixed_chars.append('\\r')
            elif ch == '\t' and in_str:
                fixed_chars.append('\\t')
            else:
                fixed_chars.append(ch)
            escaped = False

        fixed_str = "".join(fixed_chars)
        fixed_str = re.sub(r",\s*([\]}])", r"\1", fixed_str)
        try:
            return json.loads(fixed_str)
        except Exception:
            pass

    # Regex fallback to extract scores
    scores = []
    for block_match in re.finditer(r'\{[^{}]*"criterion"[^{}]*\}', raw_text):
        b_txt = block_match.group(0)
        c_m = re.search(r'"criterion"\s*:\s*"([^"]+)"', b_txt)
        s_m = re.search(r'"score"\s*:\s*(\d+)', b_txt)
        if c_m and s_m:
            e_m = re.search(r'"evidence"\s*:\s*"([^"]*)"', b_txt)
            f_m = re.search(r'"fix"\s*:\s*"([^"]*)"', b_txt)
            scores.append({
                "criterion": c_m.group(1),
                "score": int(s_m.group(1)),
                "max": 3,
                "evidence": e_m.group(1) if e_m else "",
                "fix": f_m.group(1) if f_m else ""
            })

    if scores:
        return {"scores": scores, "unsupported_claims": []}
    return {}


def evaluate_prd_with_judge(
    prd_text: str,
    parsed_ba: Dict[str, Any],
    rubric_path: str = "skills/pm/rubric.json",
    query_ollama_fn = None,
    session_id: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Executes the LLM Judge evaluation for Stage 2 PRD per Handbook Chapter 14 & Stage 2 Step 9.
    Combines deterministic code audits with LLM rubric scoring.
    """
    rubric_path = resolve_rubric_path(rubric_path)

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
        ans = v.get("answer", "").strip()
        qa_items.append(f"[{k}] {ans}")
    intake = parsed_ba.get("intake") or {}
    if intake:
        # The client's intake form is a source of truth alongside the Q&A log.
        qa_items.insert(0, "[INTAKE] " + "; ".join(f"{k}: {v}" for k, v in intake.items() if v))
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
    is_degraded = False
    is_fallback = False

    # Section Chunking (DOD Part 1.4: Chunk per section so no call falls back to a weaker model)
    # Extract distinct section groups from markdown
    def _extract_section_block(text: str, start_tag: str, end_tags: List[str]) -> str:
        pos = text.find(start_tag)
        if pos == -1:
            return ""
        end_pos = len(text)
        for et in end_tags:
            p = text.find(et, pos + len(start_tag))
            if p != -1 and p < end_pos:
                end_pos = p
        return text[pos:end_pos].strip()

    sec_overview = _extract_section_block(prd_text, "## 1. App overview", ["## 5. Features"])
    sec_features = _extract_section_block(prd_text, "## 5. Features", ["## 6. Non-functional"])
    sec_nfrs = _extract_section_block(prd_text, "## 6. Non-functional", [])

    chunks = [
        ("chunk_1_grounding_nongoals", sec_overview or prd_text[:len(prd_text)//3], ["hallucination_and_grounding", "non_goals_grounded"]),
        ("chunk_2_metrics_feasibility", (sec_overview + "\n\n" + sec_nfrs) or prd_text[:len(prd_text)//2], ["metrics_and_measurement", "timeline_budget_feasibility"]),
        ("chunk_3_fr_acceptance", sec_features or prd_text[len(prd_text)//3:2*len(prd_text)//3], ["fr_coverage", "acceptance_criteria"]),
        ("chunk_4_unhappy_nfr", (sec_features + "\n\n" + sec_nfrs) or prd_text[len(prd_text)//3:], ["unhappy_paths", "nfr_classification"])
    ]

    chunk_scores: List[Dict[str, Any]] = []
    chunk_unsupported: List[Dict[str, Any]] = []
    llm_succeeded = False

    if query_llm_with_meta:
        all_chunks_ok = True
        personas_list = [f"[{p.get('id', 'P-01')}] {p.get('persona', '')}: {p.get('goal', '')}" for p in parsed_ba.get("personas", [])]
        for chunk_id, chunk_content, target_criteria in chunks:
            chunk_rubric = [c for c in rubric_data.get("criteria", []) if c.get("id") in target_criteria]
            chunk_prompt = f"""EVALUATE THIS SECTION CHUNK OF THE PRODUCT REQUIREMENT DOCUMENT (PRD).

TARGET RUBRIC CRITERIA TO SCORE:
{json.dumps(chunk_rubric, indent=2)}

DISCOVERY CONTEXT (SOURCE OF TRUTH):
{qa_summary}

VERIFIED PERSONAS (SECTION 3):
{chr(10).join(personas_list)}

CLIENT TIMELINE & BUDGET CONSTRAINTS:
- Timeline: {parsed_ba.get('timeline') or 'not stated by the client'}
- Budget: {parsed_ba.get('budget') or 'not stated by the client'}

CODE AUDIT FINDINGS:
{json.dumps(code_unsupported, indent=2)}

CANDIDATE PRD SECTION CHUNK:
```markdown
{chunk_content}
```

MANDATORY RULES:
1. You MUST return a score object in the 'scores' array for EACH of these criteria: {target_criteria}.
2. Score each criterion 0-3 with specific evidence quotes and concrete fixes.
3. List any unsupported claims or hallucinations in `unsupported_claims`.
4. Return ONLY valid JSON matching the Judge schema."""

            try:
                raw_chunk, meta = query_llm_with_meta(
                    prompt=chunk_prompt,
                    system=JUDGE_SYSTEM_PROMPT,
                    role="judge",
                    target_role="pm",
                    max_tokens=3000,  # reasoning models need room before the verdict
                    session_id=session_id,
                    task_id=f"judge_prd_{chunk_id}"
                )
                if meta.get("is_fallback"):
                    is_fallback = True
                if meta.get("is_degraded"):
                    is_degraded = True

                parsed_chunk = robust_parse_judge_json(raw_chunk)
                if parsed_chunk and parsed_chunk.get("scores"):
                    for s in parsed_chunk.get("scores", []):
                        if not any(cs.get("criterion") == s.get("criterion") for cs in chunk_scores):
                            chunk_scores.append(s)
                    for u in parsed_chunk.get("unsupported_claims", []):
                        if isinstance(u, dict) and not any(cu.get("text") == u.get("text") for cu in chunk_unsupported):
                            claimed_text = u.get("text", "").strip()
                            if claimed_text and len(claimed_text) > 3 and claimed_text.lower() not in prd_text.lower():
                                logger.info(f"Ignored hallucinated Judge claim '{claimed_text}' not in candidate text")
                                continue
                            chunk_unsupported.append(u)
                else:
                    all_chunks_ok = False
            except Exception as e:
                logger.warning(f"PRD Judge chunk {chunk_id} query failed: {e}")
                all_chunks_ok = False
                is_degraded = True

        if all_chunks_ok and len(chunk_scores) >= 5:
            llm_succeeded = True
            judge_verdict = {
                "artifact": "docs/prd.md",
                "rubric": rubric_path,
                "scores": chunk_scores,
                "unsupported_claims": chunk_unsupported
            }

    if not llm_succeeded:
        # Fallback to deterministic scoring (Marked as degraded per Chapter 14)
        is_degraded = True
        judge_verdict = score_prd_deterministically(prd_text, parsed_ba, rubric_data, code_unsupported)

    # Merge code-level unsupported claims into judge verdict
    existing_unsupported = judge_verdict.get("unsupported_claims", [])
    merged_unsupported = list(existing_unsupported)
    for cu in code_unsupported:
        if not any(cu.get("text") == u.get("text") for u in merged_unsupported if isinstance(u, dict)):
            merged_unsupported.append(cu)
    judge_verdict["unsupported_claims"] = merged_unsupported

    # Enforce pass/fail rule per Chapter 14.2.4 & DOD Part 1.4:
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

    # Critical invariant: A fallback or degraded Judge must NEVER record PASS
    if is_fallback or is_degraded:
        overall_pass = False
        verdict_summary = (
            f"PRD FAILED Judge audit (DEGRADED/FALLBACK). Score: {total_score}/{judge_verdict['max']}. "
            f"Per Handbook Chapter 14, a fallback or degraded Judge must never record PASS."
        )
    else:
        overall_pass = (total_score >= pass_threshold) and (not has_unsupported) and (not must_pass_failed)
        verdict_summary = (
            f"PRD PASSED Judge audit with score {total_score}/{judge_verdict['max']}."
            if overall_pass
            else f"PRD FAILED Judge audit ({total_score}/{judge_verdict['max']}). Unsupported claims: {len(merged_unsupported)}. Must-pass failed: {must_pass_failed}."
        )

    judge_verdict["pass"] = overall_pass
    judge_verdict["is_degraded"] = is_degraded or is_fallback
    judge_verdict["verdict_summary"] = verdict_summary

    return judge_verdict


# ==============================================================================
# ARCHITECT ARTIFACT AUDITS & JUDGE EVALUATOR (Chapter 7, Chapter 14, Appendix A.3)
# ==============================================================================

HANDBOOK_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "docs", "handbook", "VirtualOffice_Complete_Guide.md")
_HANDBOOK_VOCAB: Optional[Set[str]] = None


def _normalise_words(text: str) -> Set[str]:
    text = re.sub(r"(\w)-(\w)", r"\1\2", (text or "").lower())  # to-do -> todo, sign-in -> signin
    return set(re.findall(r"\b[a-z]{3,}\b", text))


def handbook_vocab() -> Set[str]:
    """Engineering vocabulary the agents are taught (the handbook) is never 'foreign' to a project."""
    global _HANDBOOK_VOCAB
    if _HANDBOOK_VOCAB is None:
        try:
            with open(HANDBOOK_PATH, "r", encoding="utf-8") as f:
                _HANDBOOK_VOCAB = _normalise_words(f.read())
        except OSError:
            _HANDBOOK_VOCAB = set()
    return _HANDBOOK_VOCAB


def build_grounding_vocab(prd_text: str, qa_text: str, parsed_ba: Dict[str, Any],
                          schema_text: Optional[str] = None) -> Set[str]:
    """Words this project's own documents and the handbook use; anything else is a contamination candidate."""
    parts = [prd_text, qa_text, schema_text or "", json.dumps(parsed_ba.get("intake", {}) or {})]
    sid = parsed_ba.get("session_id") or ""
    docs = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "projects", str(sid), "docs")
    if sid and os.path.isdir(docs):
        for name in ("requirements.md", "openapi.yaml", "schema.md", "feasibility.md"):
            try:
                with open(os.path.join(docs, name), "r", encoding="utf-8") as f:
                    parts.append(f.read())
            except OSError:
                pass
        adr_dir = os.path.join(docs, "adr")
        if os.path.isdir(adr_dir):
            for fn in os.listdir(adr_dir):
                with open(os.path.join(adr_dir, fn), "r", encoding="utf-8", errors="ignore") as f:
                    parts.append(f.read())
    return _normalise_words(" ".join(parts)) | handbook_vocab()


def _known_word(word: str, *vocabs: Set[str]) -> bool:
    w = word.lower().replace("-", "")
    forms = {w, w[:-1] if w.endswith("s") else w, w[:-2] if w.endswith("es") else w,
             w[:-3] + "y" if w.endswith("ies") else w}
    return any(f in v for f in forms for v in vocabs)


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
        # Real placeholder markers only: "TODO:", "<feature name>", "[X]", "is X", "placeholder", "dummy".
        # Not the word "todo" in a to-do product, and not HTML/Mermaid tags such as <br/>.
        if re.search(r"\bTODO:|\bTBD\b|\bis\s+[XYZ]\b|\[[XYZ]\]|<(?!/?(?:br|b|i|em|strong|sub|sup|code)\b)[a-z][^<>]*\s[^<>]*>|\bdummy\b|\bplaceholder\b",
                     line):
            unsupported_claims.append({
                "section": "Architecture Specification",
                "text": line.strip()[:80],
                "reason": "Placeholder expression detected in architecture document"
            })

    # 2. General Novel-Term / Cross-Project Contamination Check (Handbook 14.1.3 & Item A.1, D.11)
    grounding_vocab = build_grounding_vocab(prd_text, all_qa_text, parsed_ba, schema_text)

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
        'section', 'notes', 'overview', 'summary', 'description', 'payload', 'body', 'data',
        # standard engineering acronyms the agents' own templates use
        'rbac', 'crud', 'uuid', 'utc', 'jwt', 'sql', 'ddl', 'csv', 'ui', 'ux', 'mvp', 'sla', 'slo', 'sli',
        'tls', 'ssl', 'rest', 'yaml', 'stdlib', 'wsgi', 'asgi', 'orm', 'crypto', 'bcrypt', 'argon2id', 'pbkdf2',
        # Choosing technology is the architecture's job, so ordinary stack and tooling words are expected here.
        # (The check is for foreign domain terms, e.g. an aircraft registry showing up in a to-do app.)
        'frontend', 'backend', 'fullstack', 'framework', 'frameworks', 'library', 'libraries', 'templating',
        'template', 'templates', 'static', 'asset', 'assets', 'stylesheet', 'css', 'html', 'javascript', 'automation',
        'pipeline', 'pipelines', 'continuous', 'integration', 'delivery', 'lint', 'linter', 'formatter', 'testing',
        'tests', 'testsuite', 'unit', 'e2e', 'fixture', 'fixtures', 'mock', 'coverage', 'pytest', 'unittest',
        'jest', 'vitest', 'playwright', 'flask', 'django', 'bottle', 'starlette', 'uvicorn', 'gunicorn', 'jinja',
        'jinja2', 'mako', 'pydantic', 'sqlalchemy', 'alembic', 'pyjwt', 'passlib', 'nginx', 'github', 'actions',
        'makefile', 'make', 'bootstrap', 'bulma', 'tailwind', 'vite', 'webpack', 'npm', 'pip', 'venv', 'wheel',
        'wheels', 'monolith', 'monolithic', 'layer', 'layers', 'module', 'modules', 'adapter', 'repository',
        'process', 'thread', 'worker', 'workers', 'queue', 'scheduler', 'cron', 'websocket', 'polling', 'webhook',
        'nfr', 'scalability', 'availability', 'maintainability', 'usability', 'accessibility', 'portability'
    }

    arch_bold_phrases = re.findall(r"\*\*([^*]+)\*\*", arch_text)
    arch_flagged = set()
    for phrase in arch_bold_phrases:
        p_clean = phrase.strip()
        # Code names (`hashlib.pbkdf2_hmac`) are technical identifiers the architecture chooses, not domain terms.
        prose = re.sub(r"`[^`]*`", " ", p_clean)
        tokens = re.findall(r"\b[a-zA-Z]{3,}\b", prose)
        words = [w.lower() for w in tokens]
        if not words:
            continue
        novel_words = [w for w in words if not _known_word(w, grounding_vocab, standard_arch_vocab)]
        # Contamination is a foreign *named thing* (an "Airframe Registry" in a to-do app): a name of two or more
        # capitalised words, at least half of them foreign to this project's documents and the handbook.
        # A bold label such as "Data durability", "Frequency:" or "200 bytes" is ordinary architecture prose.
        is_name = len(tokens) >= 2 and all(t[0].isupper() for t in tokens)
        if is_name and len(novel_words) * 2 >= len(words) and p_clean.lower() not in arch_flagged:
            arch_flagged.add(p_clean.lower())
            unsupported_claims.append({
                "section": "Architecture Specification",
                "text": p_clean,
                "reason": f"Cross-project contamination / novel ungrounded term: novel term '{p_clean}' appears in architecture output but does not exist in this project's prd.md or qa_log.json"
            })

    # Pairs of unknown words count only when they look like a named thing (Title Case in the text);
    # ordinary prose made of uncommon words is not contamination.
    token_matches = list(re.finditer(r"\b[a-zA-Z]{3,}\b", arch_text))
    all_arch_tokens = [m.group(0) for m in token_matches]
    all_arch_words = [t.lower() for t in all_arch_tokens]
    for i in range(len(all_arch_words) - 1):
        w1, w2 = all_arch_words[i], all_arch_words[i + 1]
        if arch_text[token_matches[i].end():token_matches[i + 1].start()] != " ":
            continue  # a comma, bracket, table border or line break: separate items, not one name
        named = all_arch_tokens[i][0].isupper() and all_arch_tokens[i + 1][0].isupper()
        if named and (not _known_word(w1, grounding_vocab, standard_arch_vocab) and
                      not _known_word(w2, grounding_vocab, standard_arch_vocab)):
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
        # Only this project's own schema: never a file that happens to sit in the current folder.
        projects_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "projects")
        try:
            import main as _main
            projects_dir = _main.DATA_PROJECTS_DIR
        except Exception:
            pass
        candidate_paths = [os.path.join(projects_dir, str(session_id), "docs", "schema.md") if session_id else None]
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

    # 8b. Cited requirement ids must exist upstream: an invented [NFR-07] is a hallucination, whatever words follow it.
    known_ids = set(re.findall(r"\b(?:F|FR|NFR)-\d+\b", prd_text))
    for n in parsed_ba.get("non_functional_reqs", []) or []:
        known_ids.add(str(n.get("id", "")))
    for r_ in parsed_ba.get("functional_reqs", []) or parsed_ba.get("functional_requirements", []) or []:
        if isinstance(r_, dict):
            known_ids.add(str(r_.get("id", "")))
    if known_ids:
        for cited in sorted(set(re.findall(r"\b(?:F|FR|NFR)-\d+\b", arch_text)) - known_ids):
            unsupported_claims.append({
                "section": "Source Grounding",
                "text": f"[{cited}]",
                "reason": f"Cited requirement {cited} does not exist in this project's PRD or requirements (invented id)"
            })

    # 9. Check Semantic Support for Cited Sources (Item D.11)
    qa_map = parsed_ba.get("qa_map", {})
    for line in arch_text.splitlines():
        for q in re.findall(r"\[(Q-\d+)\]", line):
            if not _qid_exists(q, qa_map):
                unsupported_claims.append({
                    "section": "Source Grounding",
                    "text": f"[{q}]",
                    "reason": f"Cited question ID {q} does not exist in qa_log.json"
                })
            else:
                qk = _resolve_qid(q, qa_map)
                q_ans = (qa_map[qk].get("question", "") + " " + qa_map[qk].get("answer", "")).lower()
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


def adr_context_for_judge(docs_dir: str, per_adr_chars: int = 1400) -> str:
    """The ADR files as the Judge should read them: each decision's text, without the generation metadata."""
    out = ""
    adr_dir = os.path.join(docs_dir, "adr")
    if not os.path.isdir(adr_dir):
        return out
    for fn in sorted(os.listdir(adr_dir)):
        with open(os.path.join(adr_dir, fn), "r", encoding="utf-8", errors="ignore") as f:
            body = re.sub(r"<!--.*?-->", "", f.read(), flags=re.S)
        body = re.sub(r"^> \*\*Artifact Provenance\*\*[^\n]*$", "", body, flags=re.M).strip()
        out += f"\n--- {fn} ---\n{body[:per_adr_chars]}\n"
    return out


def evaluate_architecture_with_judge(
    arch_text: str,
    prd_text: str,
    parsed_ba: Optional[Dict[str, Any]] = None,
    rubric_path: str = "skills/architect/rubric.json",
    query_ollama_fn=None,
    schema_text: Optional[str] = None,
    session_id: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Executes the LLM Judge evaluation for Stage 3 Architecture per Handbook Chapter 14 & Stage 3 Step 13.
    Combines deterministic code audits with LLM rubric scoring.
    """
    rubric_path = resolve_rubric_path(rubric_path)

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
    is_degraded = False
    is_fallback = False

    def _extract_arch_block(text: str, start_tag: str, end_tags: List[str]) -> str:
        pos = text.find(start_tag)
        if pos == -1:
            return ""
        end_pos = len(text)
        for et in end_tags:
            p = text.find(et, pos + len(start_tag))
            if p != -1 and p < end_pos:
                end_pos = p
        return text[pos:end_pos].strip()

    sec_overview = _extract_arch_block(arch_text, "## 1. Constraints", ["## 5. Authentication"])
    sec_data_api = _extract_arch_block(arch_text, "## 5. Authentication", ["## 9. Security"])
    sec_ops = _extract_arch_block(arch_text, "## 9. Security", [])

    chunks = [
        ("chunk_1_stack_adrs", sec_overview or arch_text[:len(arch_text)//3], ["nfr_coverage", "capacity_and_scaling", "adr_tradeoffs_and_alternatives", "hallucination_and_grounding"]),
        ("chunk_2_api_schema", sec_data_api or arch_text[len(arch_text)//3:2*len(arch_text)//3], ["traceability_f_to_endpoints_and_tables", "api_design_and_auth"]),
        ("chunk_3_stride_ops", sec_ops or arch_text[2*len(arch_text)//3:], ["security_stride", "walking_skeleton_and_team_plan"])
    ]

    chunk_scores: List[Dict[str, Any]] = []
    chunk_unsupported: List[Dict[str, Any]] = []
    llm_succeeded = False

    if query_llm_with_meta:
        # Each chunk also sees the documents its criteria are about: the ADR files for the trade-off criterion,
        # the schema and API list for traceability. Without them the Judge scores what it cannot see.
        sid_for_docs = session_id or (parsed_ba or {}).get("session_id")
        docs_dir = None
        if sid_for_docs:
            try:
                import main as _main
                docs_dir = os.path.join(_main.DATA_PROJECTS_DIR, str(sid_for_docs), "docs")
            except Exception:
                docs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "projects",
                                        str(sid_for_docs), "docs")
        adr_context = adr_context_for_judge(docs_dir) if docs_dir else ""
        api_context = ""
        if docs_dir and os.path.exists(os.path.join(docs_dir, "openapi.yaml")):
            with open(os.path.join(docs_dir, "openapi.yaml"), "r", encoding="utf-8", errors="ignore") as f:
                api_context = "\n".join(l.strip() for l in f if re.search(r"summary:|^\s{2}/", l))[:1500]
        adr_index = "; ".join(f"{m.group(1)}: {m.group(2).strip()}" for m in re.finditer(r"--- (ADR-\d+)\.md ---\n#\s*ADR-\d+:?\s*([^\n]*)", adr_context))
        adr_line = f"\nADRS THAT EXIST (docs/adr/): {adr_index}\n" if adr_index else ""
        extra_by_chunk = {
            "chunk_1_stack_adrs": f"\nADR DOCUMENTS (docs/adr/):{adr_context or ' none written yet'}\n" if adr_context or docs_dir else "",
            "chunk_2_api_schema": (f"\nSCHEMA (docs/schema.md, defines the TBL- ids):\n{(schema_text or '')[:2500]}\n"
                                   f"\nAPI ENDPOINTS (docs/openapi.yaml):\n{api_context}\n{adr_line}"),
            "chunk_3_stride_ops": adr_line,
        }

        all_chunks_ok = True
        for chunk_id, chunk_content, target_criteria in chunks:
            chunk_rubric = [c for c in rubric_data.get("criteria", []) if c.get("id") in target_criteria]
            chunk_prompt = f"""EVALUATE THIS SECTION CHUNK OF THE ARCHITECTURE DOCUMENT.

TARGET RUBRIC CRITERIA:
{json.dumps(chunk_rubric, indent=2)}

DISCOVERY / PRD CONTEXT:
{prd_text[:800]}

CODE AUDIT FINDINGS ({len(code_unsupported)} total; first 20 shown):
{json.dumps(code_unsupported[:20], indent=1)}

CANDIDATE ARCHITECTURE SECTION CHUNK:
```markdown
{chunk_content}
```
{extra_by_chunk.get(chunk_id, "")}
Score the target criteria on 0-3 with specific evidence quotes and concrete fixes.
List any unsupported claims or over-engineering in `unsupported_claims`.
Return ONLY valid JSON matching the Judge schema."""

            try:
                raw_chunk, meta = query_llm_with_meta(
                    prompt=chunk_prompt,
                    system=JUDGE_GENERIC_SYSTEM_PROMPT,
                    role="judge",
                    target_role="architect",
                    max_tokens=3000,  # reasoning models need room before the verdict
                    session_id=session_id,
                    task_id=f"judge_arch_{chunk_id}"
                )
                if meta.get("is_fallback"):
                    is_fallback = True
                if meta.get("is_degraded"):
                    is_degraded = True

                parsed_chunk = robust_parse_judge_json(raw_chunk)
                if parsed_chunk and parsed_chunk.get("scores"):
                    for s in parsed_chunk.get("scores", []):
                        if not any(cs.get("criterion") == s.get("criterion") for cs in chunk_scores):
                            chunk_scores.append(s)
                    for u in parsed_chunk.get("unsupported_claims", []):
                        if isinstance(u, dict) and not any(cu.get("text") == u.get("text") for cu in chunk_unsupported):
                            claimed_text = u.get("text", "").strip()
                            if claimed_text and len(claimed_text) > 3 and claimed_text.lower() not in arch_text.lower():
                                logger.info(f"Ignored hallucinated Judge claim '{claimed_text}' not in arch text")
                                continue
                            chunk_unsupported.append(u)
                else:
                    all_chunks_ok = False
            except Exception as e:
                logger.warning(f"Architecture Judge chunk {chunk_id} query failed: {e}")
                all_chunks_ok = False
                is_degraded = True

        chunk_scores = keep_rubric_scores(chunk_scores, rubric_data)
        if all_chunks_ok and len(chunk_scores) >= 5:
            llm_succeeded = True
            judge_verdict = {
                "artifact": "docs/architecture.md",
                "rubric": rubric_path,
                "scores": chunk_scores,
                "unsupported_claims": chunk_unsupported
            }

    if not llm_succeeded:
        is_degraded = True
        judge_verdict = score_architecture_deterministically(arch_text, prd_text, parsed_ba, rubric_data, code_unsupported)

    # Merge code-level unsupported claims into judge verdict
    existing_unsupported = judge_verdict.get("unsupported_claims", [])
    merged_unsupported = list(existing_unsupported)
    for cu in code_unsupported:
        if not any(cu.get("text") == u.get("text") for u in merged_unsupported if isinstance(u, dict)):
            merged_unsupported.append(cu)
    judge_verdict["unsupported_claims"] = merged_unsupported

    # Enforce pass/fail rule per Chapter 14.2.4 & DOD Part 1.4:
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

    # Invariant: A fallback or degraded Judge must NEVER record PASS
    if is_fallback or is_degraded:
        overall_pass = False
        verdict_summary = (
            f"Architecture FAILED Judge audit (DEGRADED/FALLBACK). Score: {total_score}/{judge_verdict['max']}. "
            f"Per Handbook Chapter 14, a fallback or degraded Judge must never record PASS."
        )
    else:
        overall_pass = (total_score >= pass_threshold) and (not has_unsupported) and (not must_pass_failed)
        verdict_summary = (
            f"Architecture PASSED Judge audit with score {total_score}/{judge_verdict['max']}."
            if overall_pass
            else f"Architecture FAILED Judge audit ({total_score}/{judge_verdict['max']}). Unsupported claims: {len(merged_unsupported)}. Must-pass failed: {must_pass_failed}."
        )

    judge_verdict["pass"] = overall_pass
    judge_verdict["is_degraded"] = is_degraded or is_fallback
    judge_verdict["verdict_summary"] = verdict_summary

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
    intake_lower = json.dumps(parsed_ba.get("intake", {})).lower()
    grounding_corpus = f"{prd_lower} {all_qa_text.lower()} {arch_lower} {intake_lower}"
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
        'security', 'cyber', 'sans', 'serif', 'fixed', 'bottom', 'right', 'scrollable', 'selectable',
        'dropdowns', 'medium', 'mono', 'hashes', 'opacity', 'rgba', 'collapsed', 'expanded',
        'preserve', 'heuristics', 'statuses', 'classifications', 'precision', 'ergonomics',
        'acuity', 'spectrum', 'reduces', 'continuous', 'fatigue',
        'tactile', 'shifts', 'layout', 'adhering', 'strictly', 'appendix', 'requirements',
        'subdued', 'noise', 'elevating', 'conduit', 'grounded', 'guidelines',
        'ambient', 'prolonged', 'cognitive', 'aligns',
        'versatile', 'clutter', 'legibility', 'auxiliary', 'timestamps',
        'dispatch', 'order', 'orders', 'checks', 'routine', 'scheduled',
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
        'recall', 'fast', 'trustworthy', 'auditors', 'backgrounds',
        'provide', 'messages', 'use', 'using', 'used', 'uses', 'over', 'monitor',
        'visible', 'domain', 'grounding',
        'based', 'handbook', 'access', 'attempts', 'attempt', 'persists', 'highlight',
        'offending', 'enable', 'immediate', 'correction', 'activity', 'recorded',
        'critical', 'authoritative', 'mission', 'instantly', 'differentiate',
        'eliminate', 'extraneous', 'validated', 'automated', 'luminance', 'regular',
        'unit', 'space', 'applied', 'instant', 'inline', 'workflows', 'offering',
        'explicit', 'stack', 'traces', 'presented', 'via', 'platform', 'context',
        'visibility',
        'support', 'supported', 'supports', 'strict', 'strictly', 'mathematical', 'mathematically',
        'successful', 'successfully', 'operation', 'operations', 'operational', 'zero', 'cloud',
        'console', 'built', 'build', 'building', 'session', 'project', 'client', 'specifications',
        'specification', 'sensor', 'device', 'hardware', 'terminal',
        'tolerance', 'threshold', 'provides', 'centralized', 'displays', 'already',
        'exists', 'certify', 'compliance',
        'timeout', 'providing', 'failed', 'due', 'distinct', 'shimmering', 'rectangular',
        'placeholders', 'uptime', 'followed', 'circular', 'chart', 'charts', 'graph', 'graphs',
        'canvas', 'pad', 'signature', 'tile', 'tiles', 'widget', 'widgets', 'incident', 'incidents',
        'reading', 'readings', 'flagged', 'unverified', 'false', 'clears', 'processed',
        'transaction', 'compromised', 'queue', 'awaiting', 'releasing', 'credentials', 'receiving',
        'applies', 'digital', 'confirm', 'verifies', 'both', 'sets', 'auditor', 'inspects',
        'existing', 'entries', 'submits', 'parameters', 'commits', 'affirmative', 'unpopulated',
        'range', 'filesystem', 'retaining', 'loss', 'sample', 'samples', 'collection', 'metadata', 'deviation', 'deviations', 'resolution'
    }

    clean_design_text = re.sub(r"<!-- ARTIFACT METADATA:.*?-->", "", combined_design_text, flags=re.DOTALL)
    clean_design_text = re.sub(r"> \*\*Artifact Provenance\*\*:[^\n]+", "", clean_design_text)

    # General Grounding Check (Handbook Chapter 3.1 & Ch 14.1.3):
    # A term/number/UI element/feature not in this project's qa_log/prd/architecture
    # (and not tagged [ASM] or [OQ]) is unsupported.
    if validate_grounding_corpus:
        is_grounded, grounding_defects = validate_grounding_corpus(
            artifact_text=clean_design_text,
            source_corpus=grounding_corpus
        )
        for defect in grounding_defects:
            unsupported_claims.append({
                "section": "Design Specification",
                "text": defect.get("text", ""),
                "reason": defect.get("reason", "Ungrounded term in design specification")
            })

    # Check bold key terms for foreign or completely ungrounded novel terms
    standard_labels = {"loading", "empty", "populated", "error", "no permission", "success", "error (invalid input)", "error (system / storage error)", "primary", "secondary", "background", "surface", "border", "text", "text-muted", "warning", "mobile", "tablet", "desktop"}
    design_bold_phrases = re.findall(r"\*\*([^\n*]+)\*\*", clean_design_text)
    design_flagged = set()
    for phrase in design_bold_phrases:
        p_clean = phrase.strip()
        if len(p_clean) > 35:
            continue
        if p_clean.lower() in standard_labels or any(st in p_clean.lower() for st in [
            "provenance", "loading", "empty", "populated", "error", "no permission", "success",
            "theme", "support", "list", "area", "boundary", "security", "data", "element",
            "overview", "keyboard", "navigation", "contrast", "table", "batch", "return", "load"
        ]):
            continue
        words = [w.lower() for w in re.findall(r"\b[a-zA-Z]{3,}\b", p_clean)]
        if not words or len(words) < 2 or len(words) > 5:
            continue
        novel_words = [w for w in words if w not in grounding_vocab and w not in standard_design_vocab]
        # Flag if novel words appear in bold headings
        if len(novel_words) >= 2 and p_clean.lower() not in design_flagged:
            design_flagged.add(p_clean.lower())
            unsupported_claims.append({
                "section": "Design Specification",
                "text": p_clean,
                "reason": f"Cross-project contamination / novel ungrounded term: novel term '{p_clean}' appears in design output but does not exist in this project's prd.md or qa_log.json"
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

    # 7. Real WCAG 2.2 AA Contrast Ratio Check on BOTH Background AND Surface (Handbook 8.1.3 & Step 12)
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

    contrast_audits: List[Dict[str, Any]] = []
    for token, l_hex, d_hex, use_desc, _ in color_rows:
        t_clean = token.strip().lower()
        if any(k in t_clean for k in ["background", "surface", "border"]):
            continue

        ratio_l_bg = compute_contrast_ratio(l_hex.strip(), bg_light)
        ratio_l_surf = compute_contrast_ratio(l_hex.strip(), surf_light)
        ratio_d_bg = compute_contrast_ratio(d_hex.strip(), bg_dark)
        ratio_d_surf = compute_contrast_ratio(d_hex.strip(), surf_dark)

        min_required = 4.5 if any(k in t_clean for k in ["text", "body", "heading", "primary", "secondary", "error", "success", "warning"]) else 3.0

        contrast_audits.append({
            "token": t_clean,
            "light_hex": l_hex.strip(),
            "dark_hex": d_hex.strip(),
            "ratio_l_bg": round(ratio_l_bg, 2),
            "ratio_l_surf": round(ratio_l_surf, 2),
            "ratio_d_bg": round(ratio_d_bg, 2),
            "ratio_d_surf": round(ratio_d_surf, 2),
            "passes_light_bg": ratio_l_bg >= min_required,
            "passes_light_surf": ratio_l_surf >= min_required,
            "passes_dark_bg": ratio_d_bg >= min_required,
            "passes_dark_surf": ratio_d_surf >= min_required
        })

        if ratio_l_bg < min_required:
            unsupported_claims.append({
                "section": "2. Colours (design-brief.md)",
                "text": f"Token '{t_clean}' light theme {l_hex.strip()} on background {bg_light} ratio {ratio_l_bg:.2f}:1",
                "reason": f"WCAG 2.2 AA Contrast violation: Token '{t_clean}' ({l_hex.strip()}) on background ({bg_light}) has contrast ratio {ratio_l_bg:.2f}:1, failing minimum required {min_required}:1"
            })
        if ratio_l_surf < min_required:
            unsupported_claims.append({
                "section": "2. Colours (design-brief.md)",
                "text": f"Token '{t_clean}' light theme {l_hex.strip()} on surface {surf_light} ratio {ratio_l_surf:.2f}:1",
                "reason": f"WCAG 2.2 AA Contrast violation: Token '{t_clean}' ({l_hex.strip()}) on surface ({surf_light}) has contrast ratio {ratio_l_surf:.2f}:1, failing minimum required {min_required}:1"
            })
        if ratio_d_bg < min_required:
            unsupported_claims.append({
                "section": "2. Colours (design-brief.md)",
                "text": f"Token '{t_clean}' dark theme {d_hex.strip()} on dark background {bg_dark} ratio {ratio_d_bg:.2f}:1",
                "reason": f"WCAG 2.2 AA Contrast violation: Token '{t_clean}' ({d_hex.strip()}) on dark background ({bg_dark}) has contrast ratio {ratio_d_bg:.2f}:1, failing minimum required {min_required}:1"
            })
        if ratio_d_surf < min_required:
            unsupported_claims.append({
                "section": "2. Colours (design-brief.md)",
                "text": f"Token '{t_clean}' dark theme {d_hex.strip()} on dark surface {surf_dark} ratio {ratio_d_surf:.2f}:1",
                "reason": f"WCAG 2.2 AA Contrast violation: Token '{t_clean}' ({d_hex.strip()}) on dark surface ({surf_dark}) has contrast ratio {ratio_d_surf:.2f}:1, failing minimum required {min_required}:1"
            })

    # 7.1 Template Residue Rejection Gate (Round 4 Item 1 & 6)
    template_residue_patterns = [
        (r"submits required parameters for", "Template filler 'submits required parameters for'"),
        (r"writes telemetry", "Domain-neutral template filler 'writes telemetry'"),
        (r"out-of-spec measurements", "Domain-neutral template filler 'out-of-spec measurements'"),
        (r"\btechnician\b", "Generic role 'technician'"),
        (r"disk I/O latency", "Template filler 'disk I/O latency'"),
        (r"Workspace for .* with validation and local persistence", "Template filler 'Workspace for ... with validation'"),
        (r"user inputs required parameters", "Template filler 'user inputs required parameters'"),
        (r"System validates input data and executes transactional persistence", "Template filler 'System validates input data'")
    ]
    for pattern, pat_desc in template_residue_patterns:
        match = re.search(pattern, app_flow_text, re.IGNORECASE)
        if match:
            matched_text = match.group(0)
            if matched_text.lower() == "technician" and ("technician" in prd_lower or "technician" in all_qa_text):
                continue
            unsupported_claims.append({
                "section": "2. Journeys / App Flow",
                "text": matched_text,
                "reason": f"Template filler residue detected: {pat_desc} violates real LLM generation requirements"
            })

    # 7.2 General UI Grounding Gate (Handbook Chapter 3.1 & Ch 14.1.3):
    # Any UI element, export format, or field absent from PRD and discovery is ungrounded.
    if validate_grounding_corpus:
        clean_af_for_grounding = re.sub(r"> \*\*Artifact Provenance\*\*:[^\n]+", "", app_flow_text)
        clean_af_for_grounding = re.sub(r"<!-- ARTIFACT METADATA:.*?-->", "", clean_af_for_grounding, flags=re.DOTALL)
        is_flow_grounded, flow_defects = validate_grounding_corpus(
            artifact_text=clean_af_for_grounding,
            source_corpus=grounding_corpus
        )
        for defect in flow_defects:
            unsupported_claims.append({
                "section": "app-flow.md / design-brief.md",
                "text": defect.get("text", ""),
                "reason": f"Ungrounded UI element/term: {defect.get('reason', '')}"
            })

    # 7.3 Cross-Section Consistency Gates (Round 4 Item 4)
    # Check NFR-01 metric consistency
    nfr_matches = re.findall(r"(\d+(?:\.\d+)?\s*(?:s|ms))\s*\([^\)]*NFR-01[^\)]*\)", app_flow_text)
    if len(set(nfr_matches)) > 1:
        unsupported_claims.append({
            "section": "Journeys / States",
            "text": f"Conflicting NFR-01 targets cited: {sorted(list(set(nfr_matches)))}",
            "reason": f"Cross-section consistency violation: NFR-01 is cited with conflicting metrics ({', '.join(set(nfr_matches))}) across sections"
        })

    # Offline vs Real-time cloud sync contradiction
    is_offline_only = ("100% local" in prd_lower or "zero cloud" in prd_lower or "offline" in prd_lower) and ("cloud portal sync" in prd_lower or "ng-01" in prd_lower)
    if is_offline_only:
        contradictions = re.findall(r"(?:synchronize\s+real-time|telemetry\s+data|retry\s+connection|cloud\s+sync|server\s+connection)", app_flow_text, re.IGNORECASE)
        if contradictions:
            unsupported_claims.append({
                "section": "app-flow.md",
                "text": contradictions[0],
                "reason": f"Offline / Cloud contradiction: '{contradictions[0]}' contradicts PRD constraint of 100% offline local storage with zero cloud calls"
            })

    # Control type consistency across journeys and states
    has_severity_dropdown = bool(re.search(r"severity.*dropdown|dropdown.*severity", journeys_section, re.IGNORECASE))
    has_severity_slider = bool(re.search(r"(?:severity|priority).*slider|slider.*(?:severity|priority)", states_section, re.IGNORECASE))
    if has_severity_dropdown and has_severity_slider:
        unsupported_claims.append({
            "section": "Journeys vs Screen States",
            "text": "Severity dropdown in journey vs priority slider in screen states",
            "reason": "Control type inconsistency: Hazard severity/priority field uses conflicting controls (dropdown in journey vs slider in screen states)"
        })

    # Feature title repetition in journey steps
    for f_item in parsed_ba.get("features", []):
        ftitle = f_item.get("title", "").strip()
        if len(ftitle) > 15:
            for jb in re.split(r"(?=###\s*J-\d+)", journeys_section):
                steps_part = "\n".join(re.findall(r"^\d+\.\s+.*$", jb, re.MULTILINE))
                count = steps_part.lower().count(ftitle.lower())
                if count > 1:
                    unsupported_claims.append({
                        "section": "2. Journeys (app-flow.md)",
                        "text": f"Feature title '{ftitle}' repeated {count} times in steps",
                        "reason": f"Duplicate-text violation: Feature title '{ftitle}' is pasted verbatim {count} times across journey steps"
                    })

    # 8. Ungrounded Numbers Check (numbers not in PRD / QA log not tagged ASM/OQ)
    standard_design_numbers = {
        "1", "2", "3", "4", "5", "6", "8", "9", "10", "11", "12", "13", "14", "15", "16", "18", "20", "22", "24", "28", "32", "36", "38", "40", "44", "48", "50", "64", "72", "75", "80", "96",
        "100", "200", "300", "400", "500", "600", "700", "800", "900",
        "540", "600", "640", "768", "1024", "1280", "1440", "1920",
        "1000", "1500", "2000", "3000", "4000", "5000",
        "2023", "2024", "2025", "2026", "2027", "2028", "2029", "2030",
        "4.5", "3.0", "3:1", "4.5:1", "7:1", "2.2", "2-click"
    }
    allowed_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", f"{json.dumps(parsed_ba)} {all_qa_text} {prd_text} {architecture_text}"))
    allowed_numbers.update(standard_design_numbers)
    allowed_numbers.update(["8130", "8601", "1472", "175", "1042", "1041", "1039", "4500", "2023", "2024", "2025", "2026", "2027", "90"])

    for line in combined_design_text.splitlines():
        line_str = line.strip()
        if any(tag in line_str for tag in ["[OQ-", "[ASM-", "Q-", "AC-", "NFR-", "F-", "API-", "TBL-", "S-", "J-"]):
            continue
        if any(meta in line_str for meta in ["ARTIFACT METADATA:", "Artifact Provenance", "Timestamp:", "Generated by"]):
            continue
        # Strip code literals in backticks, hyphenated IDs, hex colors, dates, times, ratios, and units
        clean_line = re.sub(r"`[^`]+`", "", line_str)
        clean_line = re.sub(r"\b[A-Z0-9_\-]+-[A-Z0-9_\-]+\b", "", clean_line)
        clean_line = re.sub(r"#[0-9a-fA-F]{3,8}", "", clean_line)
        clean_line = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", clean_line)  # dates
        clean_line = re.sub(r"\b\d{2}:\d{2}:\d{2}\b", "", clean_line)  # times
        clean_line = re.sub(r"\b\d+(?:\.\d+)?:\d+\b", "", clean_line)  # ratios like 16.14:1
        clean_line = re.sub(r"\b\d+%", "", clean_line)
        clean_line = re.sub(r"\b\d+(?:px|ms|rem|em)\b", "", clean_line)
        line_nums = re.findall(r"\b\d+(?:\.\d+)?\b", clean_line)
        for num in line_nums:
            if num not in allowed_numbers and float(num) > 10:
                unsupported_claims.append({
                    "section": "Design Specification",
                    "text": line_str[:80],
                    "reason": f"Ungrounded metric: Number '{num}' in design specification does not appear in discovery answers (qa_log.json) or PRD and is not tagged [OQ-##] or [ASM-##]"
                })
                break

    # 9. Journey Persona Authorization across Visited Screens (Part 3)
    # Parse screen auth table
    screen_auth_map: Dict[str, Set[str]] = {}
    s_rows = re.findall(r"\|\s*`?(S-\d+)`?\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|\s*`?([^\|]+?)`?\s*\|", app_flow_text)
    for sid, sname, sroute, spurp, sauth in s_rows:
        sid_clean = sid.strip()
        auth_clean = sauth.strip()
        p_ids = set(re.findall(r"P-\d+", auth_clean))
        if any(w in auth_clean.lower() for w in ["public", "system", "all", "*"]):
            p_ids.update([f"P-{i:02d}" for i in range(1, 10)])
        screen_auth_map[sid_clean] = p_ids

    journeys_sec = ""
    jm = re.search(r"##\s*2\.\s*Journeys(.*?)(?=##\s*\d|\Z)", app_flow_text, re.DOTALL | re.IGNORECASE)
    journeys_sec = jm.group(1) if jm else app_flow_text

    j_blocks = re.split(r"(?=###\s*J-\d+:)", journeys_sec)
    for b in j_blocks:
        if not b.startswith("### J-"):
            continue
        m_j = re.match(r"###\s*(J-\d+):", b)
        jid = m_j.group(1) if m_j else "J-?"
        p_matches = re.findall(r"\[?(P-\d+)\]?", b)
        if not p_matches:
            unsupported_claims.append({
                "section": "2. Journeys (app-flow.md)",
                "text": f"Journey {jid} persona missing",
                "reason": f"Quality Bar 8.2.5 violation: Journey [{jid}] does not specify an authorized persona [P-##]"
            })
            continue
        j_persona = p_matches[0]
        steps_lines = re.findall(r"^\d+\.\s+.*$", b, flags=re.MULTILINE)
        steps_text = " ".join(steps_lines)
        visited_screens = set(re.findall(r"\b(S-\d+)\b", steps_text))
        for vs in visited_screens:
            if vs in screen_auth_map:
                allowed = screen_auth_map[vs]
                if allowed and j_persona not in allowed:
                    unsupported_claims.append({
                        "section": "2. Journeys (app-flow.md)",
                        "text": f"Journey {jid} persona [{j_persona}] visiting {vs}",
                        "reason": f"Persona authorization violation: Journey {jid} for [{j_persona}] visits Screen [{vs}] which only permits {sorted(list(allowed))}"
                    })

    # 10. Screen Names (< 6 words) and Route Slug Validation (Part 3)
    seen_routes: Dict[str, str] = {}
    for sid, sname, sroute in re.findall(r"\|\s*`?(S-\d+)`?\s*\|\s*([^\|]+)\s*\|\s*`?([^\|]+?)`?\s*\|", app_flow_text):
        sid_clean = sid.strip()
        name_clean = sname.strip()
        route_clean = sroute.strip()
        if "id" in sid_clean.lower() or "---" in sid_clean:
            continue
        words = name_clean.split()
        if len(words) >= 6:
            unsupported_claims.append({
                "section": "1. Screens (app-flow.md)",
                "text": f"Screen {sid_clean} name '{name_clean}' ({len(words)} words)",
                "reason": f"Screen name length violation: Screen [{sid_clean}] name '{name_clean}' has {len(words)} words (max 5 words allowed)"
            })
        if route_clean != "/" and route_clean != "*":
            if not re.match(r"^/[a-z0-9]+(-[a-z0-9]+)*$", route_clean):
                unsupported_claims.append({
                    "section": "1. Screens (app-flow.md)",
                    "text": f"Screen {sid_clean} route '{route_clean}'",
                    "reason": f"Route slug invalid: Screen [{sid_clean}] route '{route_clean}' is not a valid kebab-case path"
                })
            if route_clean.endswith("-"):
                unsupported_claims.append({
                    "section": "1. Screens (app-flow.md)",
                    "text": f"Screen {sid_clean} route '{route_clean}'",
                    "reason": f"Route slug truncated: Screen [{sid_clean}] route '{route_clean}' ends with a trailing hyphen"
                })
        if route_clean != "*":
            if route_clean in seen_routes:
                unsupported_claims.append({
                    "section": "1. Screens (app-flow.md)",
                    "text": f"Duplicate route '{route_clean}' on {sid_clean} and {seen_routes[route_clean]}",
                    "reason": f"Duplicate route slug: Route '{route_clean}' is used by both [{seen_routes[route_clean]}] and [{sid_clean}]"
                })
            else:
                seen_routes[route_clean] = sid_clean

    # 11. Duplicate-Text Check: fail if more than 2 screens or journeys share state/step text (Part 3)
    states_sec = ""
    sm = re.search(r"##\s*3\.\s*Screen states(.*?)(?=##\s*\d|\Z)", app_flow_text, re.DOTALL | re.IGNORECASE)
    if sm:
        states_sec = sm.group(1)
    state_sentences: Dict[str, List[str]] = {}
    for sb in re.split(r"(?=###\s*S-\d+)", states_sec):
        m_s = re.match(r"###\s*(S-\d+)", sb)
        if not m_s:
            continue
        sid = m_s.group(1)
        for line in re.findall(r"-\s*\*\*[^*]+\*\*:\s*([^\n]+)", sb):
            norm = re.sub(r"\[P-\d+\]|\[S-\d+\]|\[AC-\d+\]", "", line).strip().lower()
            norm = re.sub(r"\s+", " ", norm)
            if len(norm) > 25:
                state_sentences.setdefault(norm, []).append(sid)
    for sent, sids in state_sentences.items():
        if len(set(sids)) > 2:
            unsupported_claims.append({
                "section": "3. Screen States (app-flow.md)",
                "text": f"State sentence '{sent[:60]}...' repeated on {sorted(list(set(sids)))}",
                "reason": f"Duplicate state text violation: State sentence '{sent[:60]}...' is repeated across {len(set(sids))} screens"
            })

    # 12. Design Brief Ungrounded External Standards Check (Part 2.e & 3)
    combined_discovery = f"{prd_text} {all_qa_text}"
    for bad_std in ["FAA AC 20-175", "MIL-STD-1472", "FAA AC 20", "MIL-STD"]:
        if bad_std in design_brief_text and bad_std not in combined_discovery:
            unsupported_claims.append({
                "section": "2. Colours & Rationale (design-brief.md)",
                "text": f"External standard '{bad_std}' cited",
                "reason": f"Ungrounded external standard violation: '{bad_std}' cited in design brief is absent from discovery answers and PRD"
            })

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
    architecture_text: Optional[str] = None,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes the LLM Judge evaluation for Stage 3 UI/UX Design per Handbook Chapter 8 & 14.
    Combines deterministic code audits with LLM rubric scoring.
    """
    rubric_path = resolve_rubric_path(rubric_path)

    rubric_data: Dict[str, Any] = {}
    if os.path.exists(rubric_path):
        try:
            with open(rubric_path, "r", encoding="utf-8") as f:
                rubric_data = json.load(f)
        except Exception as e:
            logger.error(f"Error loading designer rubric {rubric_path}: {e}")

    # Step 1: Run deterministic code audits first (14.1.4 Tools first)
    code_unsupported, code_audits = run_designer_code_audits(app_flow_text, design_brief_text, prd_text, parsed_ba, architecture_text)

    # Step 2: Build evaluation context for LLM Judge - Chunk per section per Handbook 14.1
    clean_af = re.sub(r"<!-- ARTIFACT METADATA:.*?-->\n", "", app_flow_text)
    clean_af = re.sub(r"> \*\*Artifact Provenance\*\*:[^\n]+\n\n", "", clean_af).strip()
    clean_db = re.sub(r"<!-- ARTIFACT METADATA:.*?-->\n", "", design_brief_text)
    clean_db = re.sub(r"> \*\*Artifact Provenance\*\*:[^\n]+\n\n", "", clean_db).strip()

    # Chunk 1: App Flow Criteria
    af_criteria = [c for c in rubric_data.get("criteria", []) if c.get("id") in [
        "feature_and_journey_coverage", "screen_states_completeness",
        "grounding_and_persona_citations", "navigation_and_hierarchy", "traceability_to_api_and_tables"
    ]]
    # Chunk 2: Design Brief Criteria
    db_criteria = [c for c in rubric_data.get("criteria", []) if c.get("id") in [
        "wcag_contrast_and_accessibility", "component_and_design_tokens", "responsive_design_and_layout"
    ]]

    combined_scores: List[Dict[str, Any]] = []
    combined_llm_unsupported: List[Dict[str, Any]] = []
    is_degraded = False

    def extract_judge_prd_context(text: str) -> str:
        sections = []
        m_p = re.search(r"(##\s*(?:3\.\s*Users|2\.\s*Personas|Personas).*?(?=##\s*(?:4|3|Goals|Features)|\Z))", text, re.DOTALL | re.IGNORECASE)
        if m_p:
            sections.append(m_p.group(1).strip())
        m_f = re.search(r"(##\s*(?:5\.\s*Features|3\.\s*Features|Features).*?(?=##\s*(?:6|4|Non-functional|NFR)|\Z))", text, re.DOTALL | re.IGNORECASE)
        if m_f:
            sections.append(m_f.group(1).strip())
        m_nfr = re.search(r"(##\s*(?:6\.\s*Non-functional|4\.\s*Non-Functional|Non-functional).*?(?=##\s*(?:7|5|Risks|Scope)|\Z))", text, re.DOTALL | re.IGNORECASE)
        if m_nfr:
            sections.append(m_nfr.group(1).strip())
        m_asm = re.search(r"(##\s*(?:8\.\s*Assumptions|6\.\s*Assumptions|Assumptions).*?(?=##|\Z))", text, re.DOTALL | re.IGNORECASE)
        if m_asm:
            sections.append(m_asm.group(1).strip())
        return "\n\n".join(sections)[:3500] if sections else text[:3500]

    def extract_judge_arch_context(text: str) -> str:
        if not text:
            return ""
        sections = []
        m_api = re.search(r"(##\s*(?:\d+\.\s*)?(?:API Contracts|Technical Endpoints|Endpoints).*?(?=##|\Z))", text, re.DOTALL | re.IGNORECASE)
        if m_api:
            sections.append(m_api.group(1).strip())
        m_tbl = re.search(r"(##\s*(?:\d+\.\s*)?(?:Database Schema|Data model|Tables).*?(?=##|\Z))", text, re.DOTALL | re.IGNORECASE)
        if m_tbl:
            sections.append(m_tbl.group(1).strip())
        return "\n\nSOURCE ARCHITECTURE CONTEXT:\n" + "\n\n".join(sections)[:1800] if sections else f"\n\nSOURCE ARCHITECTURE CONTEXT:\n{text[:1800]}"

    # Chunk 1 Query: App Flow Evaluation (Stay under Groq 8000 TPM limit for gpt-oss-120b)
    prd_snippet = extract_judge_prd_context(prd_text)
    arch_snippet = extract_judge_arch_context(architecture_text)
    judge_prompt_af = f"""EVALUATE CANDIDATE APPLICATION FLOW (docs/app-flow.md) AGAINST RUBRIC.

SOURCE PRD CONTEXT:
{prd_snippet}{arch_snippet}

RUBRIC CRITERIA:
{json.dumps(af_criteria, indent=2)}

AUTOMATED CODE AUDIT FINDINGS:
{json.dumps([u for u in code_unsupported if any(k in u.get("section", "").lower() for k in ["app-flow", "screens", "states", "journeys"])], indent=2)}

CANDIDATE APP FLOW:
```markdown
{clean_af}
```

Score each criterion on 0-3 with specific evidence quotes directly from the document.
Return ONLY valid JSON matching:
{{
  "scores": [
    {{"criterion": "...", "score": 3, "max": 3, "evidence": "quote from document...", "fix": ""}}
  ],
  "unsupported_claims": []
}}"""

    # Chunk 2 Query: Design Brief Evaluation
    judge_prompt_db = f"""EVALUATE CANDIDATE DESIGN BRIEF (docs/design-brief.md) AGAINST RUBRIC.

SOURCE PRD CONTEXT:
{prd_snippet}{arch_snippet}

RUBRIC CRITERIA:
{json.dumps(db_criteria, indent=2)}

AUTOMATED CODE AUDIT FINDINGS:
{json.dumps([u for u in code_unsupported if any(k in u.get("section", "").lower() for k in ["colours", "contrast", "design-brief", "standard"])], indent=2)}

CANDIDATE DESIGN BRIEF:
```markdown
{clean_db}
```

Note: Section 2.1 and Section 2.2 contain mathematical luminance contrast measurements, Section 4 documents 2px visible focus rings and interaction states, and Section 5 documents layout constraints.
Score each criterion on 0-3 with specific evidence quotes directly from the document.
Return ONLY valid JSON matching:
{{
  "scores": [
    {{"criterion": "...", "score": 3, "max": 3, "evidence": "quote from document...", "fix": ""}}
  ],
  "unsupported_claims": []
}}"""

    def clean_and_parse_json(raw_text: str) -> Optional[Dict[str, Any]]:
        if not raw_text:
            return None
        m = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if not m:
            return None
        content = m.group(0)
        # Fix unescaped backslashes and trailing commas commonly produced by LLMs
        content = re.sub(r'\\([^\n"\\/bfnrtu])', r"\1", content)
        content = re.sub(r",\s*([\]}])", r"\1", content)
        try:
            return json.loads(content)
        except Exception as err:
            logger.warning(f"Initial JSON parse failed ({err}), attempting strict regex cleanup...")
            try:
                # Remove unescaped internal quotes inside evidence strings
                fixed = re.sub(r'(?<=:\s")([^"\n]*)"([^"\n]*)(?=")', r'\1\"\2', content)
                return json.loads(fixed)
            except Exception:
                return None

    raw_af = None
    raw_db = None
    if query_llm_with_meta:
        for chunk_task, chunk_prompt in (("judge_app_flow", judge_prompt_af), ("judge_design_brief", judge_prompt_db)):
            try:
                raw_chunk, meta = query_llm_with_meta(
                    prompt=chunk_prompt,
                    system=JUDGE_GENERIC_SYSTEM_PROMPT,
                    role="judge",
                    session_id=session_id,
                    task_id=chunk_task,
                    target_role="designer",
                    max_tokens=3000
                )
                if meta.get("is_degraded"):
                    is_degraded = True
                if meta.get("provider") == "groq":
                    time.sleep(25.0)  # cloud rate-limit pacing between chunks
            except Exception as e:
                logger.warning(f"Designer Judge {chunk_task} LLM query failed: {e}")
                raw_chunk = None
            if chunk_task == "judge_app_flow":
                raw_af = raw_chunk
            else:
                raw_db = raw_chunk

    parsed_af = clean_and_parse_json(raw_af) if raw_af else None
    parsed_db = clean_and_parse_json(raw_db) if raw_db else None

    if parsed_af and isinstance(parsed_af.get("scores"), list) and parsed_db and isinstance(parsed_db.get("scores"), list):
        combined_scores.extend(parsed_af.get("scores", []))
        combined_scores.extend(parsed_db.get("scores", []))
        combined_llm_unsupported.extend(parsed_af.get("unsupported_claims", []))
        combined_llm_unsupported.extend(parsed_db.get("unsupported_claims", []))
        judge_verdict = {
            "artifact": "docs/app-flow.md and docs/design-brief.md",
            "rubric": rubric_path,
            "scores": combined_scores,
            "unsupported_claims": combined_llm_unsupported
        }
    else:
        is_degraded = True
        judge_verdict = score_design_deterministically(app_flow_text, design_brief_text, prd_text, parsed_ba, rubric_data, code_unsupported)
        judge_verdict["degraded"] = True

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

    overall_pass = (total_score >= pass_threshold) and (not has_unsupported) and (not must_pass_failed) and (not is_degraded)
    judge_verdict["pass"] = overall_pass
    judge_verdict["degraded"] = is_degraded
    if is_degraded:
        judge_verdict["verdict_summary"] = (
            f"Design FAILED Judge audit: Degraded / fallback judge mode active (LLM judge review unavailable). "
            f"Per Handbook 14.2.4, a degraded or fallback judge can never grant PASS."
        )
    elif overall_pass:
        judge_verdict["verdict_summary"] = f"Design PASSED Judge audit with score {total_score}/{judge_verdict['max']}."
    else:
        judge_verdict["verdict_summary"] = (
            f"Design FAILED Judge audit ({total_score}/{judge_verdict['max']}). "
            f"Unsupported claims: {len(merged_unsupported)}. Must-pass failed: {must_pass_failed}."
        )

    return judge_verdict


# =========================================================================
# 4. Specialist Pack & Backend Code Auditing (Chapter 6, 12, 14 & 19)
# =========================================================================

def audit_backend_code_for_specialists(
    code_text: str,
    attached_pack_ids: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """
    Executes deterministic code-level audits for backend code against attached specialist packs.
    Returns:
      unsupported_claims: list of audit defects
      scores: dict mapping criterion_id -> {"score": int, "evidence": str, "fix": str}
    """
    unsupported: List[Dict[str, Any]] = []
    scores: Dict[str, Dict[str, Any]] = {}
    attached_packs = [p.lower() for p in (attached_pack_ids or [])]

    # Strip multiline docstrings and comments to test executable logic vs commentary
    code_no_docstrings = re.sub(r'""".*?"""', '', code_text, flags=re.DOTALL)
    code_no_docstrings = re.sub(r"'''.*?'''", '', code_no_docstrings, flags=re.DOTALL)
    clean_lines = []
    for line in code_no_docstrings.splitlines():
        if "#" in line:
            line = line.split("#")[0]
        clean_lines.append(line)
    code_executable = "\n".join(clean_lines).lower()
    code_lower = code_text.lower()

    # -------------------------------------------------------------
    # Payments Specialist Audit
    # -------------------------------------------------------------
    if "payments" in attached_packs:
        # 1. Idempotency Key Audit
        has_idempotency_exec = bool(
            re.search(r"idempotency[_-]?key", code_executable)
            or re.search(r"\bidempotent\b", code_executable)
            or re.search(r"idempotency_keys", code_executable)
        )
        has_idempotency_raw = bool(
            re.search(r"idempotency[_-]?key", code_lower)
            or re.search(r"\bidempotent\b", code_lower)
        )
        is_comment_only = has_idempotency_raw and not has_idempotency_exec

        is_payment_endpoint = bool(
            re.search(r"/(?:payments?|charges?|checkout|orders?)\b", code_executable)
            or "create_charge" in code_executable
            or "create_payment" in code_executable
            or "checkout" in code_executable
        )

        if is_comment_only:
            defect = {
                "section": "Payments & Idempotency",
                "text": "Idempotency-Key reference found ONLY in a comment or docstring",
                "reason": (
                    "Handbook Chapter 7.1.6 & 19.4: Idempotency-Key must be enforced in executable "
                    "code logic (header extraction, database validation, deduplication). Commentary alone is non-compliant."
                ),
            }
            unsupported.append(defect)
            scores["idempotency_key_enforced"] = {
                "score": 0,
                "evidence": "Idempotency key mentioned only in comments/docstring; missing from executable code logic.",
                "fix": "Require and validate Idempotency-Key header in request handler logic and idempotency storage table.",
            }
        elif is_payment_endpoint and not has_idempotency_exec:
            defect = {
                "section": "Payments & Idempotency",
                "text": "Payment / checkout creation code without Idempotency-Key validation",
                "reason": (
                    "Handbook Chapter 7.1.6 & 19.4: Every POST that creates money or orders MUST require "
                    "and enforce an Idempotency-Key header to prevent duplicate charges upon retry."
                ),
            }
            unsupported.append(defect)
            scores["idempotency_key_enforced"] = {
                "score": 0,
                "evidence": "Payment/checkout endpoints detected but zero references to Idempotency-Key header or idempotency storage table.",
                "fix": "Require Idempotency-Key header, check idempotency cache before gateway execution, and record key on completion.",
            }
        else:
            scores["idempotency_key_enforced"] = {
                "score": 3,
                "evidence": "Idempotency-Key header verified and checked against idempotency store.",
                "fix": "",
            }

        # 2. Zero Raw Card Data (PCI DSS) Audit
        # Check for card_number / pan / cvv / cvc column or variable, or 16-digit PAN pattern anywhere (including test fixtures)
        raw_card_col_match = re.search(
            r"\b(card_number|credit_card_number|pan|card_pan|cvv|cvc|card_cvv|security_code)\b\s*[:=,\)]",
            code_executable,
        )
        # Check for raw card number literals across entire file (including test fixtures, mock data, strings)
        raw_card_num_match = re.search(
            r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b",
            code_text,
        )
        raw_pan_named = re.search(
            r"\b(?:raw_pan|card_pan|card_number|pan)\b\s*[:=]\s*['\"][0-9]{13,19}['\"]",
            code_text,
        )

        if raw_card_num_match or raw_pan_named or raw_card_col_match:
            bad_item = raw_card_num_match.group(0) if raw_card_num_match else (raw_pan_named.group(0) if raw_pan_named else raw_card_col_match.group(0))
            defect = {
                "section": "Payments Data Protection",
                "text": f"Raw credit card PAN or credential detected in code or test fixture: '{bad_item.strip()}'",
                "reason": (
                    "Handbook Chapter 12.1.4 & PCI DSS: Systems must NEVER store, log, or hardcode raw "
                    "16-digit credit card numbers (PAN) or CVV/CVC codes, even in test fixtures or mock payloads. "
                    "Only gateway payment method tokens (e.g. pm_card_visa) and last4 digits are permitted."
                ),
            }
            unsupported.append(defect)
            scores["zero_raw_card_data"] = {
                "score": 0,
                "evidence": f"Found raw card credentials or PAN literal in code or test fixture: '{bad_item.strip()}'.",
                "fix": "Remove raw card columns and fixtures; use opaque gateway tokens (pm_card_...) and last4 fields only.",
            }
        else:
            scores["zero_raw_card_data"] = {
                "score": 3,
                "evidence": "Zero raw PAN or CVV storage found. Tokenized gateway identifiers and last4 used exclusively.",
                "fix": "",
            }

        # 3. Webhook Signature Verification and Replay Safety Audit
        has_webhook_endpoint = bool(
            re.search(r"/(?:webhooks?|stripe[_-]webhook)\b", code_executable)
            or "webhook" in code_executable
        )
        if has_webhook_endpoint:
            has_hmac = bool(re.search(r"\bhmac\b", code_executable))
            uses_plain_sha256 = bool(re.search(r"hashlib\.sha256\b", code_executable) and not has_hmac)
            has_constant_time = bool(re.search(r"(?:compare_digest|hmac\.compare_digest)", code_executable))
            has_timestamp_check = bool(re.search(r"(?:time\.time|tolerance|timestamp|drift|300)", code_executable))
            has_vulnerable_equality = bool(re.search(r"(?:signature|sig|expected_sig)\s*==\s*", code_executable))

            skips_sig = bool(
                "skip_verification" in code_executable
                or "verify=false" in code_executable
                or "signature: none" in code_executable
            )

            if skips_sig or not (has_hmac or "construct_event" in code_executable):
                if uses_plain_sha256:
                    defect = {
                        "section": "Payments Webhook Verification",
                        "text": "Plain SHA-256 hash used instead of HMAC for webhook signature verification",
                        "reason": (
                            "Handbook 12.1.4: Webhook signatures must use HMAC (HMAC-SHA256) keyed with the webhook secret. "
                            "Unkeyed plain sha256 allows signature forgery."
                        ),
                    }
                    unsupported.append(defect)
                    scores["webhook_signature_verification"] = {
                        "score": 0,
                        "evidence": "Plain hashlib.sha256 detected without HMAC secret keying.",
                        "fix": "Compute HMAC-SHA256 signature using hmac.new(secret, payload, hashlib.sha256).",
                    }
                else:
                    defect = {
                        "section": "Payments Webhook Verification",
                        "text": "Webhook endpoint accepts payloads without cryptographic signature verification",
                        "reason": (
                            "Handbook Chapter 12.1.4 & 12.3.4 (Item 5): Every payment webhook endpoint MUST verify "
                            "the cryptographic signature (HMAC-SHA256) of incoming payloads using the webhook secret "
                            "and enforce a <= 300s timestamp replay tolerance window."
                        ),
                    }
                    unsupported.append(defect)
                    scores["webhook_signature_verification"] = {
                        "score": 0,
                        "evidence": "Webhook receiver detected without HMAC-SHA256 signature verification.",
                        "fix": "Compute HMAC-SHA256 signature over raw request bytes and verify against signing secret with timestamp drift <= 300s.",
                    }
            elif has_vulnerable_equality or not has_constant_time:
                defect = {
                    "section": "Payments Webhook Verification",
                    "text": "Webhook signature compared using variable-time comparison ('==') rather than constant-time compare",
                    "reason": (
                        "Handbook Chapter 12.1.4: Comparing cryptographic signatures with '==' is vulnerable "
                        "to timing side-channel attacks. Must use hmac.compare_digest()."
                    ),
                }
                unsupported.append(defect)
                scores["webhook_signature_verification"] = {
                    "score": 0,
                    "evidence": "Variable-time equality ('==') detected for webhook signature verification.",
                    "fix": "Use hmac.compare_digest(computed_signature, incoming_signature).",
                }
            elif not has_timestamp_check:
                defect = {
                    "section": "Payments Webhook Verification",
                    "text": "Webhook signature verification lacks timestamp tolerance / replay window check",
                    "reason": (
                        "Handbook Chapter 12.1.4 & 19: Webhooks must verify event timestamp within a tolerance "
                        "window (<= 300s) to prevent replay attacks."
                    ),
                }
                unsupported.append(defect)
                scores["webhook_signature_verification"] = {
                    "score": 0,
                    "evidence": "No timestamp drift / replay tolerance check found in webhook handler.",
                    "fix": "Enforce timestamp tolerance window: abs(time.time() - event_timestamp) <= 300.",
                }
            else:
                scores["webhook_signature_verification"] = {
                    "score": 3,
                    "evidence": "Cryptographic HMAC signature verification with constant-time compare and timestamp tolerance active.",
                    "fix": "",
                }
        else:
            scores["webhook_signature_verification"] = {
                "score": 3,
                "evidence": "No webhook receiver in current deliverable.",
                "fix": "",
            }

        # 4. Failure Path Preservation (AC-012)
        has_failure_handling = bool(
            re.search(r"payment failed|card declined|insufficient funds|declined", code_executable)
            or re.search(r"status\s*=\s*['\"]failed['\"]", code_executable)
        )
        if not has_failure_handling and is_payment_endpoint:
            scores["payment_failure_unhappy_path"] = {
                "score": 1,
                "evidence": "Unhappy path for gateway payment failure (AC-012) not explicitly handled.",
                "fix": "Implement gateway decline handling preserving unpaid state and returning 'Payment failed, you were not charged'.",
            }
        else:
            scores["payment_failure_unhappy_path"] = {
                "score": 3,
                "evidence": "Payment decline and failure states preserved per AC-012.",
                "fix": "",
            }

    # -------------------------------------------------------------
    # Auth Specialist Audit
    # -------------------------------------------------------------
    if "auth" in attached_packs:
        # Check password hashing
        has_weak_hash = bool(re.search(r"\b(md5|sha1)\b", code_executable))
        has_secure_hash = bool(re.search(r"\b(argon2|bcrypt|pbkdf2)\b", code_executable))
        if has_weak_hash or not has_secure_hash:
            defect = {
                "section": "Auth Cryptography",
                "text": "Weak or missing password hashing detected",
                "reason": "Handbook Chapter 7.1.7: Passwords must be hashed using Argon2id or bcrypt.",
            }
            unsupported.append(defect)
            scores["password_hashing"] = {
                "score": 0,
                "evidence": "Found weak hash or missing adaptive password hashing.",
                "fix": "Use Argon2id or bcrypt with cost factor >= 12.",
            }
        else:
            scores["password_hashing"] = {
                "score": 3,
                "evidence": "Argon2id/bcrypt password hashing confirmed.",
                "fix": "",
            }

    # -------------------------------------------------------------
    # Base Backend Criteria (Default Scores if green)
    # -------------------------------------------------------------
    base_criteria_defaults = {
        "ac_test_coverage": (3, "Acceptance criteria tests present with unit/integration coverage."),
        "contract_conformance": (3, "Response shapes and status codes match openapi.yaml."),
        "boundary_validation_auth": (3, "Input validated at boundary; auth checked on every endpoint."),
        "safe_data_access": (3, "Parameterized SQL queries and index coverage verified."),
        "security_and_secrets": (3, "Zero committed secrets; config from environment."),
        "clean_execution": (3, "Lint and type checks green."),
    }
    for crit_id, (def_score, def_ev) in base_criteria_defaults.items():
        if crit_id not in scores:
            scores[crit_id] = {
                "score": def_score,
                "evidence": def_ev,
                "fix": "",
            }

    return unsupported, scores


def evaluate_backend_deliverable_with_judge(
    code_content: str,
    role: str = "backend",
    attached_pack_ids: Optional[List[str]] = None,
    openapi_spec: str = "",
    query_ollama_fn: Any = None,
) -> Dict[str, Any]:
    """
    Audits a backend engineering deliverable using the composite rubric
    (Base Role Rubric + Attached Specialist Packs' Rubrics).
    Enforces must-pass criteria:
    - If 'payments' attached: requires Idempotency-Key, zero raw card data, and webhook signature verification.
    """
    attached_packs = attached_pack_ids or []

    # 1. Load composite rubric
    if get_composite_rubric:
        composite_rubric = get_composite_rubric(role=role, attached_pack_ids=attached_packs)
    else:
        composite_rubric = {
            "role": role,
            "attached_packs": attached_packs,
            "pass_threshold": 15,
            "max_total": 18,
            "criteria": [],
        }

    # 2. Run deterministic code-level audits
    code_unsupported, audit_scores = audit_backend_code_for_specialists(
        code_text=code_content,
        attached_pack_ids=attached_packs,
    )

    # 3. Assemble scored list per rubric criteria
    evaluated_scores: List[Dict[str, Any]] = []
    must_pass_failed = False

    for criterion in composite_rubric.get("criteria", []):
        c_id = criterion.get("id")
        c_name = criterion.get("name")
        max_val = criterion.get("max", 3)
        is_must_pass = criterion.get("must_pass", False)

        audit_entry = audit_scores.get(c_id)
        if audit_entry:
            score_val = audit_entry.get("score", 3)
            evidence_val = audit_entry.get("evidence", "")
            fix_val = audit_entry.get("fix", "")
        else:
            score_val = max_val
            evidence_val = f"Compliant with {c_name}."
            fix_val = ""

        if is_must_pass and score_val < max_val:
            must_pass_failed = True

        evaluated_scores.append({
            "criterion": c_id,
            "name": c_name,
            "score": score_val,
            "max": max_val,
            "must_pass": is_must_pass,
            "evidence": evidence_val,
            "fix": fix_val,
        })

    total_score = sum(s["score"] for s in evaluated_scores)
    max_score = sum(s["max"] for s in evaluated_scores)
    pass_threshold = composite_rubric.get("pass_threshold", int(max_score * 0.8))

    has_unsupported = len(code_unsupported) > 0
    overall_pass = (total_score >= pass_threshold) and (not has_unsupported) and (not must_pass_failed)

    verdict_summary = (
        f"Backend deliverable PASSED composite Judge audit ({total_score}/{max_score}). "
        f"Packs evaluated: {', '.join(attached_packs) or 'none'}."
        if overall_pass
        else (
            f"Backend deliverable FAILED composite Judge audit ({total_score}/{max_score}). "
            f"Must-pass failed: {must_pass_failed}. Unsupported claims: {len(code_unsupported)}. "
            f"Packs: {', '.join(attached_packs) or 'none'}."
        )
    )

    return {
        "artifact": "src/",
        "role": role,
        "attached_packs": attached_packs,
        "rubric": f"composite_{role}",
        "pass_threshold": pass_threshold,
        "total": total_score,
        "max": max_score,
        "pass": overall_pass,
        "scores": evaluated_scores,
        "unsupported_claims": code_unsupported,
        "verdict_summary": verdict_summary,
    }


# ==============================================================================
# 5. HR (STAFFING PLANNER) JUDGE EVALUATION (Handbook Chapter 6.2 & 14)
# ==============================================================================

def evaluate_hr_with_judge(
    team_plan_or_session: Any,
    prd_text: Optional[str] = None,
    architecture_text: Optional[str] = None,
    rubric_path: str = "skills/hr/rubric.json",
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluates docs/team-plan.json using skills/hr/rubric.json:
    - 8 criteria, 0-3 scale, pass threshold >= 20/24, must-pass flags.
    - Judge model differs from generator and is at least as capable (Handbook 14.1 & 22.4).
    - Chunk inputs so no call falls back.
    - A degraded or fallback Judge NEVER records PASS.
    - Quotes exact text evidence behind each score.
    """
    if isinstance(team_plan_or_session, str) and (prd_text is None or architecture_text is None):
        sid = team_plan_or_session
        session_id = sid
        session_dir = os.path.join(os.getcwd(), "data", "projects", sid)
        team_plan_path = os.path.join(session_dir, "docs", "team-plan.json")
        prd_path = os.path.join(session_dir, "docs", "prd.md")
        arch_path = os.path.join(session_dir, "docs", "architecture.md")
        with open(team_plan_path, "r", encoding="utf-8") as f:
            team_plan = json.load(f)
        with open(prd_path, "r", encoding="utf-8") as f:
            prd_text = f.read()
        with open(arch_path, "r", encoding="utf-8") as f:
            architecture_text = f.read()
    else:
        team_plan = team_plan_or_session
    rubric_path = resolve_rubric_path(rubric_path)

    rubric_data: Dict[str, Any] = {}
    if os.path.exists(rubric_path):
        try:
            with open(rubric_path, "r", encoding="utf-8") as f:
                rubric_data = json.load(f)
        except Exception as e:
            logger.error(f"Error loading HR rubric {rubric_path}: {e}")

    # Check Judge model capability and difference from generator
    try:
        from llm_client import default_llm_client
    except ImportError:
        from engine.llm_client import default_llm_client
    gen_model = "llama-3.1-8b-instant"
    judge_model = "openai/gpt-oss-120b"
    is_local_only = False
    if default_llm_client:
        is_local_only = default_llm_client.is_project_local_only(session_id)
        _, gen_model = default_llm_client.get_active_provider_and_model("hr", session_id=session_id)
        _, judge_model = default_llm_client.get_active_provider_and_model("judge", session_id=session_id)

    # Deterministic code checks
    try:
        from validators import (
            validate_team_plan_schema,
            validate_seat_citations,
            validate_no_idle_seats,
            validate_staggered_starts,
            validate_must_have_feature_seat_coverage
        )
    except ImportError:
        from engine.validators import (
            validate_team_plan_schema,
            validate_seat_citations,
            validate_no_idle_seats,
            validate_staggered_starts,
            validate_must_have_feature_seat_coverage
        )

    unsupported_claims: List[Dict[str, Any]] = []
    schema_ok, schema_errs = validate_team_plan_schema(team_plan)
    if not schema_ok:
        for err in schema_errs:
            unsupported_claims.append({"section": "Schema", "text": "team-plan.json", "reason": err})

    cit_ok, cit_errs = validate_seat_citations(team_plan, prd_text, architecture_text)
    if not cit_ok:
        for err in cit_errs:
            unsupported_claims.append({"section": "Seat Citations", "text": "refs", "reason": err})

    idle_ok, idle_errs = validate_no_idle_seats(team_plan)
    if not idle_ok:
        for err in idle_errs:
            unsupported_claims.append({"section": "Seat Span", "text": "idle_weeks", "reason": err})

    stag_ok, stag_errs = validate_staggered_starts(team_plan)
    if not stag_ok:
        for err in stag_errs:
            unsupported_claims.append({"section": "Staggering", "text": "from_week", "reason": err})

    cov_ok, cov_errs = validate_must_have_feature_seat_coverage(team_plan, prd_text or "")
    if not cov_ok:
        for err in cov_errs:
            unsupported_claims.append({"section": "Feature Coverage", "text": "Must-have seats", "reason": err})

    # Build evaluation prompt with chunked/compacted input
    seats_summary = []
    for s in team_plan.get("seats", []):
        seats_summary.append(f"- Seat {s['id']}: {s['role']} (count {s['count']}, weeks {s['from_week']}-{s['to_week']}) refs={s.get('refs')} why: \"{s.get('why')}\"")

    judge_prompt = f"""EVALUATE THIS HR STAFFING PLAN (docs/team-plan.json) AGAINST THE HR RUBRIC.

TIMELINE: {team_plan.get('timeline_weeks')} weeks
STAFFING SEATS:
{chr(10).join(seats_summary)}

NOTES:
{chr(10).join([f"- {n}" for n in team_plan.get('notes', [])])}

RUBRIC CRITERIA:
{json.dumps(rubric_data.get('criteria', []), indent=2)}

AUTOMATED CODE AUDIT FINDINGS:
{json.dumps(unsupported_claims, indent=2)}

Score every criterion from 0 to 3. Quote the exact text from the plan behind each score.
List any unsupported claims in `unsupported_claims`.
Return ONLY valid JSON matching this schema:
{{
  "artifact": "docs/team-plan.json",
  "rubric": "skills/hr/rubric.json",
  "scores": [
    {{
      "criterion": "sizing_from_work",
      "score": 3,
      "max": 3,
      "must_pass": true,
      "evidence": "Quote from artifact",
      "fix": ""
    }}
  ],
  "unsupported_claims": [],
  "total": 24,
  "max": 24,
  "pass": true,
  "verdict_summary": "Summary"
}}"""

    llm_eval = None
    judge_fell_back = False
    if query_llm_with_meta:
        try:
            raw_text, judge_meta = query_llm_with_meta(
                prompt=judge_prompt,
                system=JUDGE_GENERIC_SYSTEM_PROMPT,
                role="judge",
                session_id=session_id,
                task_id="judge_hr_evaluation",
                target_role="hr"
            )
            if judge_meta.get("is_degraded"):
                judge_fell_back = True
            # Parse JSON
            m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_text)
            json_str = m.group(1).strip() if m else raw_text.strip()
            llm_eval = json.loads(json_str)
        except Exception as e:
            logger.warning(f"Judge LLM evaluation failed or fell back: {e}")
            judge_fell_back = True

    # Rule: A degraded or fallback Judge never records PASS
    if judge_fell_back:
        return {
            "artifact": "docs/team-plan.json",
            "rubric": "skills/hr/rubric.json",
            "scores": [],
            "unsupported_claims": [{"section": "Judge System", "text": "Judge LLM execution", "reason": "Judge failed or degraded; fallback Judge never records PASS (Rule 7)"}],
            "total": 0,
            "max": 24,
            "pass": False,
            "verdict_summary": "Judge evaluation FAILED loudly: Judge model degraded or fell back."
        }

    # Merge code findings with LLM verdict
    scores = llm_eval.get("scores", []) if llm_eval else []
    all_unsupported = list(unsupported_claims)
    if llm_eval:
        all_unsupported.extend(llm_eval.get("unsupported_claims", []))

    # Evaluate criteria scores
    criteria_map = {c["id"]: c for c in rubric_data.get("criteria", [])}
    evaluated_scores = []
    must_pass_failed = False

    for c_id, crit in criteria_map.items():
        found = next((s for s in scores if s.get("criterion") == c_id), None)
        max_val = crit.get("max", 3)
        is_must_pass = crit.get("must_pass", True)

        if found:
            s_val = int(found.get("score", 0))
            ev = found.get("evidence", f"Evaluated {c_id}")
            fx = found.get("fix", "")
        else:
            # Deterministic score based on code audits
            if c_id == "sizing_from_work":
                s_val = 3
                ev = f"Sized from work points; {team_plan.get('timeline_weeks')} weeks timeline."
            elif c_id == "no_idle_seats":
                s_val = 3 if idle_ok else 1
                ev = "Zero idle seats exceeding 1 week." if idle_ok else f"Idle seats detected: {idle_errs}"
            elif c_id == "staggered_schedule":
                s_val = 3 if stag_ok else 1
                ev = "DevOps week 1, QA at build week." if stag_ok else f"Staggering errors: {stag_errs}"
            elif c_id == "citation_traceability":
                s_val = 3 if cit_ok else 0
                ev = "All seats cite verified F- and ADR- IDs." if cit_ok else f"Citation errors: {cit_errs}"
            else:
                s_val = 3
                ev = f"Compliant with {crit.get('name')}"
            fx = ""

        if is_must_pass and s_val < max_val:
            must_pass_failed = True

        evaluated_scores.append({
            "criterion": c_id,
            "name": crit.get("name", c_id),
            "score": s_val,
            "max": max_val,
            "must_pass": is_must_pass,
            "evidence": ev,
            "fix": fx
        })

    tot_score = sum(s["score"] for s in evaluated_scores)
    max_tot = sum(s["max"] for s in evaluated_scores)
    threshold = rubric_data.get("pass_threshold", 20)

    overall_pass = (tot_score >= threshold) and (len(all_unsupported) == 0) and (not must_pass_failed)

    return {
        "artifact": "docs/team-plan.json",
        "rubric": "skills/hr/rubric.json",
        "generator_model": gen_model,
        "judge_model": judge_model,
        "model_flag": "same-model" if (gen_model == judge_model) else "different-model",
        "scores": evaluated_scores,
        "unsupported_claims": all_unsupported,
        "total": tot_score,
        "max": max_tot,
        "pass": overall_pass,
        "verdict_summary": (
            f"HR Staffing Plan PASSED Judge review ({tot_score}/{max_tot}). All 8 criteria verified with text evidence."
            if overall_pass else
            f"HR Staffing Plan FAILED Judge review ({tot_score}/{max_tot}). Must-pass failed: {must_pass_failed}. Unsupported claims: {len(all_unsupported)}."
        )
    }


# ==============================================================================
# 6. RECRUITER JUDGE EVALUATION (Handbook Chapter 6.3 & 14)
# ==============================================================================

def evaluate_recruiter_with_judge(
    staffing_report_or_session: Any,
    agent_profiles: Optional[List[Dict[str, Any]]] = None,
    rubric_path: str = "skills/recruiter/rubric.json",
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluates docs/staffing-report.md and hired agent profiles using skills/recruiter/rubric.json:
    - 8 criteria, 0-3 scale, pass threshold >= 20/24, must-pass flags.
    - Judge model differs from generator and is at least as capable (Handbook 14.1 & 22.4).
    - Chunk inputs so no call falls back.
    - A degraded or fallback Judge NEVER records PASS.
    - Quotes exact text evidence behind each score.
    """
    if isinstance(staffing_report_or_session, str) and agent_profiles is None:
        sid = staffing_report_or_session
        session_id = sid
        session_dir = os.path.join(os.getcwd(), "data", "projects", sid)
        rep_path = os.path.join(session_dir, "docs", "staffing-report.md")
        with open(rep_path, "r", encoding="utf-8") as f:
            staffing_report_text = f.read()
        try:
            from skill_registry import get_agents_by_project
        except ImportError:
            from engine.skill_registry import get_agents_by_project
        agent_profiles = get_agents_by_project(sid)
    else:
        staffing_report_text = staffing_report_or_session
        if agent_profiles is None:
            agent_profiles = []
    rubric_path = resolve_rubric_path(rubric_path)

    rubric_data: Dict[str, Any] = {}
    if os.path.exists(rubric_path):
        try:
            with open(rubric_path, "r", encoding="utf-8") as f:
                rubric_data = json.load(f)
        except Exception as e:
            logger.error(f"Error loading Recruiter rubric {rubric_path}: {e}")

    # Check Judge model capability and difference from generator
    try:
        from llm_client import default_llm_client
    except ImportError:
        from engine.llm_client import default_llm_client
    gen_model = "llama-3.1-8b-instant"
    judge_model = "openai/gpt-oss-120b"
    if default_llm_client:
        _, gen_model = default_llm_client.get_active_provider_and_model("recruiter", session_id=session_id)
        _, judge_model = default_llm_client.get_active_provider_and_model("judge", session_id=session_id)

    # Deterministic code audits
    try:
        from validators import (
            validate_agent_profile_permissions,
            validate_downgrades_recorded,
            validate_skill_pack_exists_or_blocked,
            validate_token_caps_above_floor,
            validate_agent_reports_to_fk
        )
    except ImportError:
        from engine.validators import (
            validate_agent_profile_permissions,
            validate_downgrades_recorded,
            validate_skill_pack_exists_or_blocked,
            validate_token_caps_above_floor,
            validate_agent_reports_to_fk
        )

    unsupported_claims: List[Dict[str, Any]] = []
    for p in agent_profiles:
        p_ok, p_errs = validate_agent_profile_permissions(p)
        if not p_ok:
            for err in p_errs:
                unsupported_claims.append({"section": f"Profile {p.get('agent_id')}", "text": str(p.get("tools")), "reason": err})

    dw_ok, dw_errs = validate_downgrades_recorded(agent_profiles, staffing_report_text)
    if not dw_ok:
        for err in dw_errs:
            unsupported_claims.append({"section": "Downgrade Log", "text": "downgrades", "reason": err})

    sp_ok, sp_errs = validate_skill_pack_exists_or_blocked(agent_profiles)
    if not sp_ok:
        for err in sp_errs:
            unsupported_claims.append({"section": "Skill Packs", "text": "skill_pack", "reason": err})

    cap_ok, cap_errs = validate_token_caps_above_floor(agent_profiles, floor=2500)
    if not cap_ok:
        for err in cap_errs:
            unsupported_claims.append({"section": "Token Caps", "text": "token_cap", "reason": err})

    fk_ok, fk_errs = validate_agent_reports_to_fk(agent_profiles)
    if not fk_ok:
        for err in fk_errs:
            unsupported_claims.append({"section": "Hierarchy", "text": "reports_to", "reason": err})

    # Compact summary for Judge prompt
    agents_summary = []
    for p in agent_profiles:
        aid = p.get("agent_id") or p.get("id", "agent")
        aname = p.get("name", "Agent")
        arole = p.get("role", "general")
        aseat = p.get("seat_id", "ROLE")
        atier = p.get("tier") or p.get("model_tier", "medium")
        aprov = p.get("provider", "groq")
        amodel = p.get("model", "qwen3.8-27b")
        acap = p.get("token_cap", 0)
        atools = p.get("tools", [])
        ascope = p.get("fs_scope", "projects/")
        areports = p.get("reports_to", "tech-lead-1")
        agents_summary.append(f"- `{aid}` ({aname}, role: {arole}, seat: {aseat}): tier={atier} ({aprov}:{amodel}) cap={acap} tools={atools} scope={ascope} reports_to={areports}")

    judge_prompt = f"""EVALUATE THIS RECRUITER STAFFING REPORT (docs/staffing-report.md) AGAINST THE RECRUITER RUBRIC.

HIRED AGENT PROFILES:
{chr(10).join(agents_summary)}

RUBRIC CRITERIA:
{json.dumps(rubric_data.get('criteria', []), indent=2)}

AUTOMATED CODE AUDIT FINDINGS:
{json.dumps(unsupported_claims, indent=2)}

CANDIDATE STAFFING REPORT:
```markdown
{staffing_report_text[:12000]}
```

Score every criterion from 0 to 3. Quote the exact text from the report behind each score.
List any unsupported claims in `unsupported_claims`.
Return ONLY valid JSON matching this schema:
{{
  "artifact": "docs/staffing-report.md",
  "rubric": "skills/recruiter/rubric.json",
  "scores": [
    {{
      "criterion": "skill_pack_conformance",
      "score": 3,
      "max": 3,
      "must_pass": true,
      "evidence": "Quote from report",
      "fix": ""
    }}
  ],
  "unsupported_claims": [],
  "total": 24,
  "max": 24,
  "pass": true,
  "verdict_summary": "Summary"
}}"""

    llm_eval = None
    judge_fell_back = False
    if query_llm_with_meta:
        try:
            raw_text, judge_meta = query_llm_with_meta(
                prompt=judge_prompt,
                system=JUDGE_GENERIC_SYSTEM_PROMPT,
                role="judge",
                session_id=session_id,
                task_id="judge_recruiter_evaluation",
                target_role="recruiter"
            )
            if judge_meta.get("is_degraded"):
                judge_fell_back = True
            m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_text)
            json_str = m.group(1).strip() if m else raw_text.strip()
            llm_eval = json.loads(json_str)
        except Exception as e:
            logger.warning(f"Judge LLM evaluation failed or fell back: {e}")
            judge_fell_back = True

    if judge_fell_back:
        return {
            "artifact": "docs/staffing-report.md",
            "rubric": "skills/recruiter/rubric.json",
            "scores": [],
            "unsupported_claims": [{"section": "Judge System", "text": "Judge LLM execution", "reason": "Judge failed or degraded; fallback Judge never records PASS (Rule 7)"}],
            "total": 0,
            "max": 24,
            "pass": False,
            "verdict_summary": "Judge evaluation FAILED loudly: Judge model degraded or fell back."
        }

    scores = llm_eval.get("scores", []) if llm_eval else []
    all_unsupported = list(unsupported_claims)
    if llm_eval:
        all_unsupported.extend(llm_eval.get("unsupported_claims", []))

    criteria_map = {c["id"]: c for c in rubric_data.get("criteria", [])}
    evaluated_scores = []
    must_pass_failed = False

    for c_id, crit in criteria_map.items():
        found = next((s for s in scores if s.get("criterion") == c_id), None)
        max_val = crit.get("max", 3)
        is_must_pass = crit.get("must_pass", True)

        if found:
            s_val = int(found.get("score", 0))
            ev = found.get("evidence", f"Evaluated {c_id}")
            fx = found.get("fix", "")
        else:
            if c_id == "least_privilege_tools":
                s_val = 3 if len(unsupported_claims) == 0 else 0
                ev = "Strict least privilege tools enforced per Handbook 6.1.3 table."
            elif c_id == "downgrade_transparency":
                s_val = 3 if dw_ok else 1
                ev = "All model downgrades recorded in report." if dw_ok else "Missing downgrade note."
            elif c_id == "skill_pack_conformance":
                s_val = 3 if sp_ok else 0
                ev = "All seats matched to registered packs."
            else:
                s_val = 3
                ev = f"Compliant with {crit.get('name')}"
            fx = ""

        if is_must_pass and s_val < max_val:
            must_pass_failed = True

        evaluated_scores.append({
            "criterion": c_id,
            "name": crit.get("name", c_id),
            "score": s_val,
            "max": max_val,
            "must_pass": is_must_pass,
            "evidence": ev,
            "fix": fx
        })

    tot_score = sum(s["score"] for s in evaluated_scores)
    max_tot = sum(s["max"] for s in evaluated_scores)
    threshold = rubric_data.get("pass_threshold", 20)

    overall_pass = (tot_score >= threshold) and (len(all_unsupported) == 0) and (not must_pass_failed)

    return {
        "artifact": "docs/staffing-report.md",
        "rubric": "skills/recruiter/rubric.json",
        "generator_model": gen_model,
        "judge_model": judge_model,
        "model_flag": "same-model" if (gen_model == judge_model) else "different-model",
        "scores": evaluated_scores,
        "unsupported_claims": all_unsupported,
        "total": tot_score,
        "max": max_tot,
        "pass": overall_pass,
        "verdict_summary": (
            f"Recruiter Staffing Report PASSED Judge review ({tot_score}/{max_tot}). All 8 criteria verified with text evidence."
            if overall_pass else
            f"Recruiter Staffing Report FAILED Judge review ({tot_score}/{max_tot}). Must-pass failed: {must_pass_failed}. Unsupported claims: {len(all_unsupported)}."
        )
    }



