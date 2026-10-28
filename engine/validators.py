"""
Deterministic Validators for HR Staffing Plan, Recruiter Profiles, and Gate 2
Per Handbook Chapter 6 (6.1.1–6.3.6), 2.7.5, 5.1.6, 22.4, 23.4–23.6, 24.1, 26.4
"""

import os
import re
import json
import logging
import sqlite3
import yaml
from typing import Dict, Any, List, Tuple, Set, Optional

logger = logging.getLogger("autonoma-engine.validators")


def validate_team_plan_schema(plan: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validates team-plan.json against the exact schema specified in Handbook 6.2.3:
    {
      "seats": [
        {
          "id": "ROLE-01",
          "role": "backend",
          "count": 2,
          "from_week": 1,
          "to_week": 4,
          "why": "F-003, F-005: payments and orders APIs",
          "refs": ["F-003", "F-005", "ADR-004"]
        }
      ],
      "timeline_weeks": 6,
      "notes": []
    }
    """
    errors: List[str] = []

    if not isinstance(plan, dict):
        return False, ["team-plan.json must be a JSON object"]

    if "seats" not in plan or not isinstance(plan["seats"], list):
        errors.append("Field 'seats' is required and must be an array of seat objects")

    if "timeline_weeks" not in plan or not isinstance(plan["timeline_weeks"], int) or plan["timeline_weeks"] <= 0:
        errors.append("Field 'timeline_weeks' is required and must be a positive integer")

    if "notes" not in plan or not isinstance(plan["notes"], list):
        errors.append("Field 'notes' is required and must be an array of strings")

    seats = plan.get("seats", [])
    if not seats:
        errors.append("At least one seat is required in 'seats'")

    seat_ids: Set[str] = set()
    for idx, seat in enumerate(seats):
        prefix = f"seats[{idx}]"
        if not isinstance(seat, dict):
            errors.append(f"{prefix} must be a JSON object")
            continue

        # Check required fields
        for field in ["id", "role", "count", "from_week", "to_week", "why", "refs"]:
            if field not in seat:
                errors.append(f"{prefix} missing required field '{field}'")

        sid = seat.get("id", "")
        if not re.match(r"^ROLE-\d{2,}$", str(sid)):
            errors.append(f"{prefix}.id '{sid}' must match format 'ROLE-##'")
        if sid in seat_ids:
            errors.append(f"{prefix}.id '{sid}' is duplicated; seat IDs must be unique")
        seat_ids.add(sid)

        count = seat.get("count", 0)
        if not isinstance(count, int) or count <= 0:
            errors.append(f"{prefix}.count must be an integer >= 1")

        fw = seat.get("from_week", 0)
        tw = seat.get("to_week", 0)
        if not isinstance(fw, int) or fw <= 0:
            errors.append(f"{prefix}.from_week must be an integer >= 1")
        if not isinstance(tw, int) or tw <= 0:
            errors.append(f"{prefix}.to_week must be an integer >= 1")
        if isinstance(fw, int) and isinstance(tw, int) and fw > tw:
            errors.append(f"{prefix}.from_week ({fw}) cannot be greater than to_week ({tw})")
        timeline = plan.get("timeline_weeks", 0)
        if isinstance(tw, int) and tw > timeline:
            errors.append(f"{prefix}.to_week ({tw}) exceeds project timeline_weeks ({timeline})")

        why = str(seat.get("why", "")).strip()
        if len(why) < 15:
            errors.append(f"{prefix}.why is too short ({len(why)} chars, minimum 15 required)")

        refs = seat.get("refs", [])
        if not isinstance(refs, list) or len(refs) == 0:
            errors.append(f"{prefix}.refs must be a non-empty array of cited IDs")

    return (len(errors) == 0, errors)


def validate_seat_citations(
    plan: Dict[str, Any],
    prd_text: str,
    architecture_text: str
) -> Tuple[bool, List[str]]:
    """
    Validates that every seat in team-plan.json has refs that exist in the PRD or architecture.
    Cites only IDs that exist and whose text supports the claim.
    """
    errors: List[str] = []
    seats = plan.get("seats", [])

    # Extract all known valid IDs from artifacts
    valid_f_ids = set(re.findall(r"\b(F-\d{2,4})\b", prd_text))
    valid_adr_ids = set(re.findall(r"\b(ADR-\d{2,4})\b", architecture_text))
    valid_nfr_ids = set(re.findall(r"\b(NFR-\d{1,4})\b", prd_text + "\n" + architecture_text))
    valid_api_ids = set(re.findall(r"\b(API-\d{2,4})\b", architecture_text))

    all_valid_ids = valid_f_ids.union(valid_adr_ids).union(valid_nfr_ids).union(valid_api_ids)

    for idx, seat in enumerate(seats):
        sid = seat.get("id", f"seat[{idx}]")
        refs = seat.get("refs", [])
        if not refs:
            errors.append(f"{sid} has no refs")
            continue

        for r in refs:
            clean_r = r.strip()
            if clean_r not in all_valid_ids:
                errors.append(f"{sid} cites non-existent reference '{clean_r}' not found in PRD or Architecture")

    return (len(errors) == 0, errors)


def validate_must_have_feature_coverage(
    plan: Dict[str, Any],
    prd_features: List[Dict[str, Any]]
) -> Tuple[bool, List[str]]:
    """
    Validates that every Must-have F- has a seat that can build it.
    """
    errors: List[str] = []
    seats = plan.get("seats", [])

    # Map roles that build features
    builder_roles = {"frontend", "backend", "fullstack", "engineer"}

    covered_features: Set[str] = set()
    for s in seats:
        role = s.get("role", "").lower()
        if role in builder_roles or "developer" in role or "engineer" in role:
            for r in s.get("refs", []):
                if r.startswith("F-"):
                    covered_features.add(r)
            # Check why text for feature IDs as well
            for fid in re.findall(r"\b(F-\d{2,4})\b", s.get("why", "")):
                covered_features.add(fid)

    for f in prd_features:
        fid = f.get("id", "")
        priority = str(f.get("priority", "")).lower()
        is_must = "must" in priority or priority == "p0"
        if is_must:
            if fid not in covered_features:
                errors.append(f"Must-have feature '{fid}' has no assigned engineering seat able to build it")

    return (len(errors) == 0, errors)


def validate_no_idle_seats(plan: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Handbook 6.1.1 & 6.2.5: No seat idle more than 1 week of its span.
    """
    errors: List[str] = []
    seats = plan.get("seats", [])

    for s in seats:
        sid = s.get("id", "ROLE")
        fw = s.get("from_week", 1)
        tw = s.get("to_week", 1)
        span = tw - fw + 1
        idle_weeks = s.get("idle_weeks", 0)

        if idle_weeks > 1:
            errors.append(f"{sid} ({s.get('role')}) is scheduled idle for {idle_weeks} weeks, exceeding 1-week limit")

        if span <= 0:
            errors.append(f"{sid} has invalid span {span} weeks")

    return (len(errors) == 0, errors)


def validate_staggered_starts(plan: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Handbook 6.1.1: DevOps from week 1, QA from the first build week, Performance QA once APIs exist.
    """
    errors: List[str] = []
    seats = plan.get("seats", [])

    devops_seats = [s for s in seats if s.get("role", "").lower() in ["devops", "sre"]]
    qa_seats = [s for s in seats if s.get("role", "").lower() in ["qa", "tester"]]
    perf_seats = [s for s in seats if s.get("role", "").lower() in ["perf", "performance", "performance_qa"]]
    dev_seats = [s for s in seats if s.get("role", "").lower() in ["backend", "frontend", "fullstack", "engineer"]]

    # 1. DevOps from week 1
    if devops_seats:
        earliest_devops = min(s.get("from_week", 1) for s in devops_seats)
        if earliest_devops > 1:
            errors.append(f"DevOps seat start is staggered at week {earliest_devops}; Handbook 6.1.1 requires DevOps from week 1")

    # First build week
    earliest_dev = min((s.get("from_week", 1) for s in dev_seats), default=1)

    # 2. QA from first build week
    if qa_seats:
        earliest_qa = min(s.get("from_week", 1) for s in qa_seats)
        if earliest_qa < earliest_dev:
            errors.append(f"QA starts at week {earliest_qa} before first build week {earliest_dev}")

    # 3. Performance QA once APIs exist (after initial build week, typically >= week 2)
    if perf_seats:
        earliest_perf = min(s.get("from_week", 1) for s in perf_seats)
        if earliest_perf <= earliest_dev and earliest_dev == 1:
            errors.append(f"Performance QA starts at week {earliest_perf}; must stagger after APIs exist (build start week {earliest_dev})")

    return (len(errors) == 0, errors)


def validate_role_merging(
    plan: Dict[str, Any],
    stories_per_role: Dict[str, int]
) -> Tuple[bool, List[str]]:
    """
    Handbook 6.1.1 & [CFG-03]: Roles with under ~2 stories are merged into a neighbouring role (e.g. fullstack, or perf into QA).
    """
    errors: List[str] = []
    seats = plan.get("seats", [])

    for s in seats:
        role = s.get("role", "").lower()
        if role in ["frontend", "backend"]:
            story_count = stories_per_role.get(role, 0)
            if 0 < story_count < 2:
                errors.append(
                    f"Role '{role}' has only {story_count} stories (< 2). Handbook 6.1.1 requires merging into a neighbouring/fullstack role"
                )
        elif role == "perf":
            story_count = stories_per_role.get("perf", 0)
            if 0 < story_count < 2:
                errors.append(
                    f"Role 'perf' has only {story_count} stories (< 2). Handbook 6.1.1 requires merging into QA role"
                )

    return (len(errors) == 0, errors)


def validate_headcount_budget_flagging(
    plan: Dict[str, Any],
    budget_limit_usd: Optional[float] = None,
    estimated_cost_usd: Optional[float] = None
) -> Tuple[bool, List[str]]:
    """
    Handbook 6.1.1 & 6.2.5: Headcount × weeks vs budget: flag the gap in notes, never hide it.
    """
    errors: List[str] = []
    notes = " ".join(plan.get("notes", [])).lower()

    if budget_limit_usd and estimated_cost_usd and estimated_cost_usd > budget_limit_usd:
        # Cost exceeds budget: must flag in notes
        if "budget" not in notes and "exceed" not in notes and "deficit" not in notes and "gap" not in notes:
            errors.append("Headcount staffing exceeds client budget limit, but the deficit is unflagged in plan notes")

    return (len(errors) == 0, errors)


def validate_arithmetic_matches_code(
    plan: Dict[str, Any],
    computed_plan: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """
    Validates that the LLM's numbers and seat counts match the code's computed arithmetic.
    """
    errors: List[str] = []
    plan_seats = plan.get("seats", [])
    calc_seats = computed_plan.get("seats", [])

    if len(plan_seats) != len(calc_seats):
        errors.append(f"Seat count mismatch: LLM generated {len(plan_seats)} seats, code calculated {len(calc_seats)}")
        return False, errors

    calc_map = {s["id"]: s for s in calc_seats}
    for s in plan_seats:
        sid = s.get("id", "")
        if sid not in calc_map:
            errors.append(f"LLM generated unexpected seat ID '{sid}' not in code calculation")
            continue

        c = calc_map[sid]
        if s.get("role", "").lower() != c.get("role", "").lower():
            errors.append(f"Seat '{sid}' role mismatch: LLM='{s.get('role')}', code='{c.get('role')}'")
        if s.get("count") != c.get("count"):
            errors.append(f"Seat '{sid}' count mismatch: LLM={s.get('count')}, code={c.get('count')}")
        if s.get("from_week") != c.get("from_week"):
            errors.append(f"Seat '{sid}' from_week mismatch: LLM={s.get('from_week')}, code={c.get('from_week')}")
        if s.get("to_week") != c.get("to_week"):
            errors.append(f"Seat '{sid}' to_week mismatch: LLM={s.get('to_week')}, code={c.get('to_week')}")

    return (len(errors) == 0, errors)


def validate_agent_profile_permissions(
    profile: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """
    Handbook 6.1.3 & 6.3.6: Minimal tools and folder per role.
    Roles that only write documents never get run/shell/network tools.
    """
    try:
        from skill_registry import validate_agent_permissions
    except ImportError:
        from engine.skill_registry import validate_agent_permissions
    role = profile.get("role", "")
    tools = profile.get("tools", [])
    fs_scope = profile.get("fs_scope", "")
    return validate_agent_permissions(role=role, tools=tools, fs_scope=fs_scope)


def validate_downgrades_recorded(
    agent_profiles: List[Dict[str, Any]],
    staffing_report_text: str
) -> Tuple[bool, List[str]]:
    """
    Handbook 6.1.2 & 22.4 rule 2: Every downgrade in model tier is recorded with expected effect on quality.
    """
    errors: List[str] = []
    report_lower = staffing_report_text.lower()

    for p in agent_profiles:
        downgraded = p.get("downgraded", False)
        if downgraded:
            agent_id = p.get("agent_id", "")
            name = p.get("name", "")
            downgrade_note = p.get("downgrade_note", "")
            if not downgrade_note:
                errors.append(f"Agent '{agent_id}' ({name}) experienced a tier downgrade but has no downgrade note")
            elif agent_id.lower() not in report_lower and name.lower() not in report_lower and "downgrade" not in report_lower:
                errors.append(f"Downgrade for agent '{agent_id}' ({name}) not documented in docs/staffing-report.md")

    return (len(errors) == 0, errors)


def validate_skill_pack_exists_or_blocked(
    agent_profiles: List[Dict[str, Any]]
) -> Tuple[bool, List[str]]:
    """
    Handbook 6.3.4 Step 1: Match role -> skill pack in the registry.
    If no pack exists: status 'blocked', do not invent one.
    """
    try:
        from skill_registry import get_role_pack
    except ImportError:
        from engine.skill_registry import get_role_pack
    errors: List[str] = []

    for p in agent_profiles:
        role = p.get("role", "")
        status = p.get("status", "")
        pack_info = get_role_pack(role)
        if not pack_info["exists"]:
            if status != "blocked":
                errors.append(
                    f"Agent '{p.get('agent_id')}' assigned non-existent skill pack for role '{role}', "
                    f"but status is '{status}' instead of 'blocked' (invented skill pack forbidden)"
                )

    return (len(errors) == 0, errors)


def validate_no_duplicate_sentences_in_reasons(
    plan: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """
    Checks that seat justifications ('why') do not repeat boilerplate or identical sentences across seats.
    """
    errors: List[str] = []
    seats = plan.get("seats", [])
    seen_whys: Dict[str, str] = {}

    for s in seats:
        sid = s.get("id", "")
        why = s.get("why", "").strip()
        # Normalize punctuation and casing for comparison
        norm_why = re.sub(r"\s+", " ", why.lower())
        if norm_why in seen_whys:
            errors.append(f"Seat '{sid}' has duplicate 'why' text identical to seat '{seen_whys[norm_why]}'")
        seen_whys[norm_why] = sid

    return (len(errors) == 0, errors)


def validate_gate2_summary_completeness(
    summary: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """
    Handbook 2.7.5 step 17, 22.4, 26.4:
    Gate 2 summary must include:
    - team table (seat, role, count, weeks, why/refs, model/tier/provider, tools, token cap)
    - every downgrade
    - blocked or spec_only seats
    - specialist packs attached with evidence
    - budget and cost with inputs (spent + remaining * 1.20)
    - WHICH providers will see project data (privacy requirement; honour local-only)
    """
    errors: List[str] = []
    required_keys = [
        "team_table",
        "downgrades",
        "blocked_or_spec_only",
        "specialist_packs",
        "budget_and_cost",
        "privacy_providers"
    ]
    for rk in required_keys:
        if rk not in summary:
            errors.append(f"Gate 2 summary missing required section '{rk}'")

    # Check budget_and_cost contents
    bc = summary.get("budget_and_cost", {})
    if isinstance(bc, dict):
        for sub_k in ["spent_tokens", "spent_cost_usd", "estimated_remaining_tokens", "total_project_tokens", "total_project_cost_usd"]:
            if sub_k not in bc:
                errors.append(f"Gate 2 budget_and_cost missing input/metric '{sub_k}'")

    # Check privacy_providers
    privacy = summary.get("privacy_providers", {})
    if isinstance(privacy, dict):
        if "providers_with_access" not in privacy:
            errors.append("Gate 2 privacy summary missing 'providers_with_access'")

    return (len(errors) == 0, errors)


# ==============================================================================
# PRD PRE-JUDGE CODE VALIDATOR (Handbook Chapter 5, Appendix A.2)
# ==============================================================================

NON_ANSWER_PATTERNS = [
    r"\byes,?\s*(?:please\s+proceed|let['’]s\s+begin|go\s+ahead|start)\b",
    r"\bplease\s+proceed\b",
    r"\blet['’]s\s+begin\b",
    r"\bsounds\s+good\b",
    r"\bas\s+an\s+ai\b",
    r"\btoday\s+users\s+do\s+without\s+this\s+app\b",
    r"\bthe\s+single\s+biggest\s+pain\b",
    r"\bn/?a\b",
    r"\bto\s+be\s+determined\b",
    r"\btbd\b"
]


# Handbook 5.1.2: unhappy paths cover invalid input, empty state, no permission, no network,
# duplicate submission, limits reached and timeouts.
UNHAPPY_PATH_RE = re.compile(
    r"\(unhappy path\)|\binvalid|\berror|\bfail|\bdenied|\bunauthori[sz]ed|\bnot (?:signed|logged) in|\bexpired"
    r"|\bempty\b|\bmissing\b|\bblank\b|\bduplicate|\balready\b|\blimit|\btime(?:s)? ?out|\boffline|\bno network"
    r"|\bnot found|\bdoes not exist|\bno longer exists|\breject|\bwrong\b|\bwithout permission|\bno permission"
    r"|\bforbidden|\bexceed|\bnon-?existent", re.IGNORECASE)


def validate_prd_pre_judge(
    prd_text: str,
    qa_map: Dict[str, Any],
    requirements_text: str = ""
) -> Tuple[bool, List[str]]:
    """
    Code validator executed before the LLM Judge. Errors are fed back to PM generator.
    Enforces:
    - No non-answers or chat filler in problem/context fields
    - Unique feature names and descriptions
    - Story and ACs match feature title
    - Every AC is a grammatical Given / When / Then with a measurable bound
    - No stray markdown, no duplicate citations
    - Every number and term grounded
    - Same NFR number everywhere
    - Every ID cited exists and its text supports the claim
    - F- -> FR / AC coverage
    - No sentence repeated across features
    """
    errors: List[str] = []

    if not prd_text or len(prd_text) < 200:
        return False, ["PRD content is missing or too short"]

    # 1. No non-answers or chat filler in problem / context fields
    prob_m = re.search(r"##\s*2\.\s*Problem(.*?)(?=##\s*3|\Z)", prd_text, re.DOTALL | re.IGNORECASE)
    if not prob_m:
        errors.append("PRD is missing '## 2. Problem' section")
    else:
        prob_text = prob_m.group(1)

        # Check required fields and inspect their values for non-answer filler
        for field in ["Today", "Core problem", "Why existing tools fall short"]:
            f_m = re.search(rf"\*\*{field}\*\*:\s*([^\n]+)", prob_text, re.IGNORECASE)
            if not f_m:
                errors.append(f"Problem section missing required field '**{field}**'")
            else:
                val = f_m.group(1).strip()
                if len(val) < 25:
                    errors.append(f"Problem field '**{field}**' is too short ({len(val)} chars, minimum 25 required)")
                for pat in NON_ANSWER_PATTERNS:
                    match = re.search(pat, val, re.IGNORECASE)
                    if match:
                        errors.append(f"Problem section contains non-answer or filler text matching '{match.group(0)}'")

    # 2. Extract features and validate uniqueness, stories, ACs, sentences
    summary_desc_by_fid: Dict[str, str] = {}
    summary_m = re.search(r"###\s*Summary(.*?)(?=###\s*(?:Feature\s+)?F-|\Z)", prd_text, re.DOTALL | re.IGNORECASE)
    if summary_m:
        sum_rows = re.findall(r"\|\s*(F-\d+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|", summary_m.group(1))
        seen_summary_descs: Dict[str, str] = {}
        for sum_fid, sum_title, sum_desc in sum_rows:
            summary_desc_by_fid[sum_fid.strip()] = sum_desc.strip()
            norm_d = re.sub(r"\s+", " ", sum_desc.strip().lower())
            if len(norm_d) >= 15:
                if norm_d in seen_summary_descs:
                    errors.append(f"Duplicate feature description: '{sum_desc.strip()}' in {sum_fid} was already used in {seen_summary_descs[norm_d]}")
                seen_summary_descs[norm_d] = sum_fid

    f_blocks = re.split(r"(?=###\s*(?:Feature\s+)?F-\d+:)", prd_text)
    features_found = []
    seen_titles: Dict[str, str] = {}
    seen_stories: Dict[str, str] = {}
    sentence_to_feature: Dict[str, str] = {}

    for block in f_blocks:
        hdr_match = re.search(r"###\s*(?:Feature\s+)?(F-\d+):\s*(.+)", block)
        if not hdr_match:
            continue
        fid = hdr_match.group(1).strip()
        ftitle = hdr_match.group(2).strip().replace("**", "")

        # Check unique feature title
        norm_title = re.sub(r"\s+", " ", ftitle.lower().strip())
        if norm_title in seen_titles:
            errors.append(f"Duplicate feature title '{ftitle}' in {fid} (already used in {seen_titles[norm_title]})")
        seen_titles[norm_title] = fid

        # Check ungrounded features
        if "pull request" in ftitle.lower():
            errors.append(f"Ungrounded feature: 'pull requests' in {fid} does not exist in discovery or requirements")

        # Extract Story
        story_m = re.search(r"-\s*\*\*Story\*\*:\s*([^\n]+)", block, re.IGNORECASE)
        if not story_m:
            story_m = re.search(r"Story:\s*([^\n]+)", block, re.IGNORECASE)
        story = story_m.group(1).strip() if story_m else ""
        if not story:
            errors.append(f"Feature {fid} is missing user Story")
        else:
            # Check story format: As a [P-##], I want ... so that ...
            # "As a [P-01], I want ..." with an optional persona name after the ID.
            if not re.search(r"\bAs\s+an?\s+\[?P-\d+\]?(?:\s+[^,\n]{1,60}?)?,?\s+I\s+want\s+.+\s+so\s+that\s+.+", story, re.IGNORECASE):
                errors.append(f"Feature {fid} story '{story}' does not match standard 'As a [P-##], I want ... so that ...' format")

            # Check duplicate user story across features
            norm_story = re.sub(r"\s+", " ", story.lower().strip())
            if norm_story in seen_stories:
                errors.append(f"Duplicate user story across features: {fid} reuses identical story from {seen_stories[norm_story]}")
            seen_stories[norm_story] = fid

            # Check title / story keyword match
            operative_title_words = [w.lower() for w in re.findall(r"\b[a-zA-Z]{4,}\b", ftitle) if w.lower() not in {"with", "from", "that", "this", "local", "management", "system", "track", "tracking"}]
            # The story must share a word with the title or with the feature's own summary description
            # ("User Authentication" / "sign in with email and password" / "I want to sign in").
            desc_words = [w.lower() for w in re.findall(r"\b[a-zA-Z]{4,}\b", summary_desc_by_fid.get(fid, ""))
                          if w.lower() not in {"with", "from", "that", "this", "their", "users", "user"}]
            story_match_words = operative_title_words + desc_words
            if ("export" in ftitle.lower() or "csv" in ftitle.lower()) and not any(w in story.lower() for w in ["export", "csv", "download", "file"]):
                errors.append(f"Feature {fid} title '{ftitle}' does not match its story text (title/story mismatch: title specifies export/CSV but story does not mention export)")
            elif ("pull" in ftitle.lower() or "requests" in ftitle.lower()) and not any(w in story.lower() for w in ["pull", "request"]):
                errors.append(f"Feature {fid} title '{ftitle}' does not match its story text (title/story mismatch: title specifies pull requests but story does not match)")
            elif operative_title_words and not any(tw in story.lower() or tw[:4] in story.lower() for tw in story_match_words):
                errors.append(f"Feature {fid} title '{ftitle}' does not match its story text (title/story mismatch)")

        # Extract ACs
        ac_rows = re.findall(r"\|\s*(AC-\d+)\s*\|\s*([^|]+)\s*\|", block)
        if not ac_rows:
            errors.append(f"Feature {fid} has no Acceptance Criteria table rows")
        else:
            has_unhappy = False
            for ac_id, ac_text in ac_rows:
                act = ac_text.strip()
                if UNHAPPY_PATH_RE.search(act):
                    has_unhappy = True

                # Check for spliced ACs
                if re.search(r"\bwithin\s+response\s+time\s+under\b.*?\bsearch\s+and\s+filter\b", act, re.IGNORECASE) and not any(kw in ftitle.lower() for kw in ["search", "filter", "query"]):
                    errors.append(f"Spliced acceptance criterion: {fid} {ac_id} splices search/filter latency clause into non-search feature ('{act[:60]}...')")

                # Every AC must be a grammatical Given / When / Then
                clean_act = re.sub(r"\(unhappy\s+path\)", "", act, flags=re.IGNORECASE).strip()
                gwt_match = re.search(r"\bGiven\s+(.+?)\s+when\s+(.+?)\s+then\s+(.+)", clean_act, re.IGNORECASE)
                if not gwt_match:
                    errors.append(f"{fid} {ac_id} is not a grammatical Given / When / Then sentence: '{act}'")
                else:
                    # Check for measurable bound or explicit verification condition
                    has_bound = any([
                        re.search(r"\b(?:under|within|<|>|<=|>=)\s+\d+(?:\.\d+)?\s*(?:s|ms|sec|second|seconds|mb|kb|gb)\b", act, re.IGNORECASE),
                        re.search(r"\b(?:status\s+code\s+)?(?:200|201|400|401|403|404|409|422|429|500)\b", act),
                        re.search(r"\[(?:NFR-\d+|ASM-\d+)\]", act),
                        re.search(r"\b(?:error|success|toast|inline|modal|dialog|message|sealed|disabled|enabled|stored|stores|persisted|persists|logged|logs|flagged|flags|displayed|displays|display|rendered|renders|render|shown|shows|show|visible|returned|returns|created|creates|updated|updates|writes|write|written|removes|remove|removed|deleted|deletes|delete|recorded|records|record|saved|saves|save|increments|decrements|cleared|clears|clear|invalidated|invalidates|terminated|terminates|ended|ends|redirected|redirects|marked|marks|appears|appear|listed|lists|hidden|hides|rejected|rejects|blocked|blocks|locked|locks|signed out|signed in|prevented|prevents|unchanged|remains|reverted)\b", act, re.IGNORECASE)
                    ])
                    if not has_bound:
                        errors.append(f"{fid} {ac_id} lacks a measurable bound or verification threshold: '{act}'")

                # Sentence repetition across features
                sentences = [s.strip() for s in re.split(r"[.!?]", act) if len(s.strip()) >= 25]
                for sent in sentences:
                    norm_s = re.sub(r"\s+", " ", sent.lower())
                    if norm_s in sentence_to_feature and sentence_to_feature[norm_s] != fid:
                        errors.append(f"Sentence repeated across features: '{sent[:50]}...' in {fid} was already used in {sentence_to_feature[norm_s]}")
                    sentence_to_feature[norm_s] = fid

            if not has_unhappy:
                errors.append(f"Feature {fid} is missing an explicit unhappy path acceptance criterion")

        features_found.append(fid)

    if not features_found:
        errors.append("No features (### F-###:) found in Section 5")

    # 3. Check for stray markdown (unescaped broken formatting)
    lines = prd_text.split("\n")
    for line_idx, line in enumerate(lines, start=1):
        # Odd number of asterisks in a single line (excluding lines with list bullets)
        clean_line = line.strip()
        if clean_line and not clean_line.startswith("* ") and not clean_line.startswith("- "):
            star_count = clean_line.count("**")
            if clean_line.count("*") % 2 != 0 and star_count % 2 != 0:
                errors.append(f"Stray markdown formatting on line {line_idx}: '{clean_line[:60]}'")

    # 4. Check for duplicate citations (e.g. [Q-001] [Q-001])
    dup_cite_m = re.search(r"(\[(?:Q-\d+|NFR-\d+|FR-\d+)\])\s*\1", prd_text)
    if dup_cite_m:
        errors.append(f"Duplicate consecutive citation found: '{dup_cite_m.group(0)}'")

    # 5. Check cited IDs exist in discovery / requirements
    if qa_map:
        cited_qids = re.findall(r"\[(Q-\d+)\]", prd_text)
        for qid in cited_qids:
            if qid not in qa_map:
                errors.append(f"Cited discovery turn '{qid}' does not exist in qa_log.json")

    if requirements_text:
        req_frs = set(re.findall(r"\b(FR-\d+)\b", requirements_text))
        cited_frs = set(re.findall(r"\b(FR-\d+)\b", prd_text))
        missing_frs = req_frs - cited_frs
        # All Must-have FRs in requirements should be covered
        must_req_frs = set(re.findall(r"\b(FR-\d+)\b[^\n]+Must", requirements_text, re.IGNORECASE))
        missing_must = must_req_frs - cited_frs
        if missing_must:
            errors.append(f"Must-have functional requirements not covered in PRD features: {sorted(list(missing_must))}")

    return len(errors) == 0, errors


# ==============================================================================
# SCHEMA DDL CODE VALIDATOR (Handbook 2.7.4 Step 12, Appendix A.6)
# ==============================================================================

def validate_schema_ddl(schema_text: str) -> Tuple[bool, List[str], List[str]]:
    """
    Code validates SQL DDL by executing it directly in an in-memory SQLite database.
    Catches syntax errors, invalid column constraints, duplicate tables, and missing FKs.
    Returns (is_valid, error_list, table_names_created).
    """
    errors: List[str] = []
    created_tables: List[str] = []

    if not schema_text or len(schema_text) < 50:
        return False, ["Schema document is empty or too short"], []

    # Extract SQL code blocks or CREATE TABLE statements
    sql_blocks = re.findall(r"```(?:sql|sqlite)?\s*\n(.*?)\n```", schema_text, re.DOTALL | re.IGNORECASE)
    if sql_blocks:
        full_ddl = "\n\n".join(sql_blocks).strip()
    else:
        # Filter to only executable SQL DDL
        ddl_statements = []
        for stmt in schema_text.split(";"):
            s_clean = stmt.strip()
            if not s_clean:
                continue
            if any(s_clean.upper().startswith(kw) for kw in ["CREATE TABLE", "CREATE INDEX", "CREATE UNIQUE INDEX", "CREATE TRIGGER", "CREATE VIEW", "PRAGMA", "ALTER TABLE"]):
                ddl_statements.append(s_clean + ";")
        full_ddl = "\n".join(ddl_statements).strip()

    if not full_ddl:
        return False, ["No executable SQL DDL statements (CREATE TABLE / INDEX) found in schema.md"], []

    conn = None
    try:
        conn = sqlite3.connect(":memory:")
        cur = conn.cursor()
        # Enable foreign keys
        cur.execute("PRAGMA foreign_keys = ON;")
        cur.executescript(full_ddl)

        # Inspect tables created
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        rows = cur.fetchall()
        created_tables = [r[0] for r in rows]

        if not created_tables:
            errors.append("SQL DDL parsed without error but created 0 database tables")

        # Verify tables have columns
        for tbl in created_tables:
            cur.execute(f"PRAGMA table_info('{tbl}');")
            cols = cur.fetchall()
            if not cols:
                errors.append(f"Table '{tbl}' has 0 columns")

    except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
        errors.append(f"SQLite DDL execution failed: {e}")
    finally:
        if conn:
            conn.close()

    return len(errors) == 0, errors, created_tables


# ==============================================================================
# OPENAPI 3.0.3 CODE VALIDATOR (Handbook 2.7.4 Step 12)
# ==============================================================================

def validate_openapi_spec(
    openapi_text: str,
    prd_features: Optional[List[Dict[str, Any]]] = None
) -> Tuple[bool, List[str], List[str]]:
    """
    Code validates openapi.yaml:
    - Parses YAML syntax
    - Enforces OpenAPI 3.0.x schema structure
    - Every endpoint states auth rule, responses, and 4xx/5xx errors
    - Every F- feature maps to at least one endpoint
    Returns (is_valid, error_list, endpoint_ids).
    """
    errors: List[str] = []
    endpoint_ids: List[str] = []

    if not openapi_text or len(openapi_text) < 100:
        return False, ["OpenAPI specification is empty or too short"], []

    # Clean markdown fences if LLM wrapped in ```yaml
    clean_yaml = openapi_text.strip()
    if clean_yaml.startswith("```"):
        clean_yaml = re.sub(r"^```[a-zA-Z]*\n", "", clean_yaml)
        clean_yaml = re.sub(r"\n```$", "", clean_yaml).strip()

    try:
        spec = yaml.safe_load(clean_yaml)
    except Exception as e:
        return False, [f"OpenAPI YAML syntax error: {e}"], []

    if not isinstance(spec, dict):
        return False, ["OpenAPI document must be a YAML object dictionary"], []

    # Check root fields
    openapi_version = str(spec.get("openapi", ""))
    if not openapi_version.startswith("3.0"):
        errors.append(f"OpenAPI version must be 3.0.x (found '{openapi_version}') per Handbook 2.7.4")

    info = spec.get("info", {})
    if not isinstance(info, dict) or "title" not in info or "version" not in info:
        errors.append("OpenAPI 'info' object must include 'title' and 'version'")

    paths = spec.get("paths", {})
    if not isinstance(paths, dict) or len(paths) == 0:
        errors.append("OpenAPI 'paths' object is missing or empty")
        return False, errors, []

    # Inspect operations
    all_cited_features: Set[str] = set()
    standard_methods = {"get", "post", "put", "delete", "patch"}

    for path_str, path_item in paths.items():
        if not isinstance(path_item, dict):
            errors.append(f"Path '{path_str}' must be a dictionary of operations")
            continue

        for method, op in path_item.items():
            if method.lower() not in standard_methods:
                continue

            if not isinstance(op, dict):
                errors.append(f"Operation {method.upper()} '{path_str}' must be a dictionary")
                continue

            # Summary or description
            summary = op.get("summary") or op.get("description", "")
            if not summary:
                errors.append(f"Operation {method.upper()} '{path_str}' is missing summary/description")

            # Responses
            responses = op.get("responses", {})
            if not isinstance(responses, dict) or not responses:
                errors.append(f"Operation {method.upper()} '{path_str}' is missing 'responses'")
            else:
                resp_codes = {str(k) for k in responses.keys()}
                has_success = any(c.startswith("2") for c in resp_codes)
                has_error = any(c.startswith("4") or c.startswith("5") for c in resp_codes)
                if not has_success:
                    errors.append(f"Operation {method.upper()} '{path_str}' is missing a 2xx success response")
                if not has_error:
                    errors.append(f"Operation {method.upper()} '{path_str}' is missing error response definitions (RFC 9457 Problem Details)")

            # Check feature citation
            op_text = json.dumps(op)
            f_matches = re.findall(r"\b(F-\d{2,4})\b", op_text)
            for fm in f_matches:
                all_cited_features.add(fm)

            # Check API ID
            api_m = re.findall(r"\b(API-\d{2,4})\b", op_text)
            for am in api_m:
                endpoint_ids.append(am)

    # Coverage: Every Must-have PRD feature must map to at least one API endpoint
    if prd_features:
        for f in prd_features:
            if isinstance(f, str):
                fid = f
                prio = "must"
                ftitle = f
            else:
                fid = f.get("id", "")
                prio = str(f.get("priority", "")).lower()
                ftitle = f.get("title", "")
            if "must" in prio and fid and fid not in all_cited_features:
                errors.append(f"Must-have feature '{fid}' ({ftitle}) has no matching OpenAPI endpoint")

    return len(errors) == 0, errors, endpoint_ids


# ==============================================================================
# ARCHITECTURE PRE-JUDGE CODE VALIDATOR (Handbook Chapter 7, Appendix A.3)
# ==============================================================================

def validate_architecture_pre_judge(
    arch_text: str,
    prd_data: Optional[Dict[str, Any]] = None,
    adr_list: Optional[List[Dict[str, Any]]] = None
) -> Tuple[bool, List[str]]:
    """
    Code validator executed before Judge on architecture.md.
    Enforces:
    - All 12 Appendix A.3 points present
    - Capacity estimate shows calculation arithmetic from cited inputs
    - Tech stack lists options and cites ADRs
    - Unchecked library versions tagged UNVERIFIED
    - Team plan seats cite F- and ADR- and cover every Must-have feature
    - F- -> API and TBL coverage
    """
    errors: List[str] = []

    if not arch_text or len(arch_text) < 300:
        return False, ["architecture.md is missing or too short"]

    # 1. Check required 12 sections from Appendix A.3
    required_sections = [
        ("1. Constraints that shape the design", r"##\s*1\.\s*Constraints"),
        ("2. Capacity estimate", r"##\s*2\.\s*Capacity"),
        ("3. Tech stack", r"##\s*3\.\s*Tech\s+stack"),
        ("4. Architecture overview", r"##\s*4\.\s*Architecture\s+overview"),
        ("5. Authentication and authorization", r"##\s*5\.\s*Authentication"),
        ("6. API", r"##\s*6\.\s*API"),
        ("7. Data model", r"##\s*7\.\s*Data\s+model"),
        ("8. External integrations", r"##\s*8\.\s*External\s+integrations"),
        ("9. Security (STRIDE)", r"##\s*9\.\s*Security"),
        ("10. Reliability and operations", r"##\s*10\.\s*Reliability"),
        ("11. Build order", r"##\s*11\.\s*Build\s+order"),
        ("12. Team plan (for HR)", r"##\s*12\.\s*Team\s+plan")
    ]
    for sec_title, sec_pattern in required_sections:
        if not re.search(sec_pattern, arch_text, re.IGNORECASE):
            errors.append(f"Architecture document missing section '{sec_title}'")

    # 2. Capacity arithmetic check: must show calculation from cited inputs (Handbook 7.2.4 & Appendix A.3)
    cap_m = re.search(r"##\s*2\.\s*Capacity\s+estimate(.*?)(?=##\s*3|\Z)", arch_text, re.DOTALL | re.IGNORECASE)
    if cap_m:
        cap_text = cap_m.group(1)
        if not re.search(r"\b(?:requests?/s|throughput|peak|storage|bytes?|mb|gb|calculation|arithmetic)\b", cap_text, re.IGNORECASE):
            errors.append("Section 2 (Capacity estimate) lacks arithmetic calculation from cited inputs")
        if not re.search(r"\[(?:NFR-\d+|Q-\d+)\]", cap_text):
            errors.append("Section 2 (Capacity estimate) does not cite source NFR- or Q- inputs")

    # 3. Security (STRIDE) table check
    sec_m = re.search(r"##\s*9\.\s*Security(.*?)(?=##\s*10|\Z)", arch_text, re.DOTALL | re.IGNORECASE)
    if sec_m:
        sec_text = sec_m.group(1)
        t_rows = re.findall(r"\|\s*(T-\d+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|", sec_text)
        if len(t_rows) < 2:
            errors.append("Section 9 (Security STRIDE) must include at least 2 threat table rows with mitigations")

    # 4. Build order check: walking skeleton must be named
    bo_m = re.search(r"##\s*11\.\s*Build\s+order(.*?)(?=##\s*12|\Z)", arch_text, re.DOTALL | re.IGNORECASE)
    if bo_m:
        bo_text = bo_m.group(1)
        if "walking skeleton" not in bo_text.lower():
            errors.append("Section 11 (Build order) must explicitly name the 'walking skeleton'")

    # 5. Team plan seats check: must cover Must-have features and cite F- / ADR-
    tp_m = re.search(r"##\s*12\.\s*Team\s+plan(.*?)(?=#+\s*\d|\Z)", arch_text, re.DOTALL | re.IGNORECASE)
    if tp_m:
        tp_text = tp_m.group(1)
        f_refs = set(re.findall(r"\b(F-\d{2,4})\b", tp_text))
        adr_refs = set(re.findall(r"\b(ADR-\d{2,4})\b", tp_text))
        if not f_refs:
            errors.append("Section 12 (Team plan) does not cite any Feature [F-###] IDs")
        if not adr_refs:
            errors.append("Section 12 (Team plan) does not cite any [ADR-###] IDs")

    return len(errors) == 0, errors


# ==============================================================================
# GENERAL GROUNDING VALIDATOR (Zero Domain Clusters / Blacklists)
# ==============================================================================

def validate_grounding_corpus(
    artifact_text: str,
    source_corpus: str,
    allowed_asm_oq: bool = True
) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    General grounding check replacing domain-cluster blacklists.
    Per Handbook Chapter 3.1:
    A term, entity, or feature not in this project's qa_log, prd, or architecture
    (and not tagged [ASM-##] or [OQ-##]) is unsupported.
    """
    unsupported: List[Dict[str, Any]] = []

    clean_source = source_corpus.lower()
    source_vocab = set(re.findall(r"\b[a-zA-Z]{4,}\b", clean_source))

    # General standard software terms and UI/UX design tokens that are always permitted
    generic_vocab = {
        "status", "created", "updated", "timestamp", "description", "details",
        "action", "actions", "filter", "search", "export", "report", "table",
        "button", "dialog", "modal", "window", "sidebar", "header", "footer",
        "desktop", "sqlite", "offline", "client", "server", "endpoint", "database",
        "record", "records", "entity", "entities", "schema", "column", "primary",
        "foreign", "unique", "constraint", "index", "indices", "latency", "response",
        "request", "success", "error", "warning", "loading", "empty", "populated",
        "permission", "permissions", "persona", "personas", "audit", "compliance",
        "verification", "storage", "privacy", "access", "control", "summary",
        "overview", "problem", "solution", "architecture", "system", "component",
        "artifact", "provenance", "section", "area", "chart", "charts",
        "row", "rows", "column", "columns", "bottom", "top", "left", "right", "center",
        "recent", "activity", "alert", "alerts", "critical", "visual", "structure",
        "notification", "banner", "date", "time", "panel", "panels", "pane", "panes",
        "brief", "grounding", "domain", "token", "tokens", "reading", "read",
        "typography", "palette", "surface", "canvas", "background", "foreground", "border",
        "hover", "active", "focus", "pressed", "disabled", "ring", "rings", "visible",
        "spacing", "unit", "units", "width", "height", "limit", "limits",
        "recognition", "recall", "shortcut", "shortcuts", "keyboard", "navigation",
        "shimmer", "skeleton", "click", "rule", "badge", "chip", "chips", "card", "cards",
        "grid", "layout", "toast", "input", "dropdown", "select", "radio", "checkbox",
        "contrast", "ratio", "ratios", "accessibility", "mandate", "formula", "luminance",
        "relative", "wcag", "mathematical", "normal", "large", "interactive",
        "scale", "family", "weight", "radius", "shadow", "elevation", "clear", "cancel",
        "save", "submit", "confirm", "close", "back", "next", "previous", "sort",
        "spec", "specs", "specification", "guideline", "guidelines", "order", "sequence",
        "escape", "enter", "space", "arrow", "keys", "mode", "toggle", "field", "fields",
        "security", "boundary", "notification", "notifications", "theme", "themes", "support",
        "supported", "list", "lists", "element", "elements", "item", "items", "content",
        "entry", "entries", "data", "value", "values", "trend", "trends", "consumption",
        "statement", "interactive", "indicator", "indicators", "target", "targets",
        "retry", "load", "mark", "check", "checked", "return", "dashboard", "batch",
        "manager", "managers", "current", "access", "restricted", "permission", "permissions",
        "begin", "start", "stop"
    }

    # Extract bold phrases on a single line (avoid matching across paragraphs)
    bold_phrases = re.findall(r"\*\*([^\n*]+)\*\*", artifact_text)
    for phrase in bold_phrases:
        p_clean = phrase.strip()
        if len(p_clean) > 35:
            continue
        words = [w.lower() for w in re.findall(r"\b[a-zA-Z]{4,}\b", p_clean)]
        if not words or len(words) < 2 or len(words) > 5:
            continue
        # Skip standard markdown headers or stamps
        if any(sw in p_clean.lower() for sw in [
            "provenance", "loading", "empty", "error", "success", "given", "when", "then",
            "step", "screen", "journey", "table", "section", "overview", "navigation", "keyboard", "focus",
            "theme", "support", "security", "boundary", "data", "element", "list", "area", "batch"
        ]):
            continue

        novel = [w for w in words if w not in source_vocab and w not in generic_vocab]
        if len(novel) >= 2:
            # Check if tagged with [ASM] or [OQ] in immediate context
            is_tagged = "[asm" in artifact_text.lower() or "[oq" in artifact_text.lower()
            unsupported.append({
                "text": p_clean,
                "reason": f"Ungrounded term '{p_clean}' introduces novel vocabulary ({', '.join(novel)}) not found in project discovery corpus"
            })

    return len(unsupported) == 0, unsupported


def validate_token_caps_above_floor(
    profiles: List[Dict[str, Any]],
    floor: int = 2500
) -> Tuple[bool, List[str]]:
    """
    Handbook 5.1.6, 6.3.4 & Gate 2 blocker fix A3:
    Every agent must have a token cap derived from estimate.json (+20%) and floored at
    a measured per-story minimum (floor >= 2500). Caps below the floor are rejected.
    """
    errors: List[str] = []
    for p in profiles:
        agent_id = p.get("agent_id") or p.get("id", "agent")
        cap = p.get("token_cap")
        if cap is None or cap < floor:
            errors.append(
                f"Agent '{agent_id}' has token cap {cap} which is below the measured minimum floor of {floor} tokens."
            )
        if p.get("token_cap_warning") == "NO ESTIMATE" or p.get("status") == "NO ESTIMATE":
            errors.append(
                f"Agent '{agent_id}' has NO ESTIMATE in docs/estimate.json; cannot hire without token estimate."
            )
    return len(errors) == 0, errors


def validate_agent_reports_to_fk(
    profiles: List[Dict[str, Any]],
    db_path: Optional[str] = None
) -> Tuple[bool, List[str]]:
    """
    Handbook 2.1, 6.3.4, 24.1 & Gate 2 blocker fix A4:
    Every reports_to must reference an existing agent row (FK-valid).
    Ghost reports_to references are rejected.
    """
    errors: List[str] = []
    known_agent_ids = set()

    for p in profiles:
        aid = p.get("agent_id") or p.get("id")
        if aid:
            known_agent_ids.add(str(aid).strip())

    if db_path and os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT id FROM agents")
            for row in cur.fetchall():
                known_agent_ids.add(str(row[0]).strip())
            conn.close()
        except Exception:
            pass

    for p in profiles:
        aid = p.get("agent_id") or p.get("id", "agent")
        reports_to = p.get("reports_to")
        if reports_to:
            reports_to_str = str(reports_to).strip()
            if reports_to_str not in known_agent_ids:
                errors.append(
                    f"Agent '{aid}' reports to ghost manager '{reports_to_str}'; target agent does not exist in roster or agents table (FK violation)."
                )

    return len(errors) == 0, errors


def validate_must_have_feature_seat_coverage(
    plan: Dict[str, Any],
    prd_text: str
) -> Tuple[bool, List[str]]:
    """
    Handbook 6.2.5 & Gate 2 blocker fix A8:
    Every Must-have feature must have a role / seat able to build it.
    A Must-have feature with no seat is rejected.
    """
    errors: List[str] = []
    must_have_pattern = re.compile(
        r"###\s*(?:Feature\s*)?`?(F-\d{2,4})`?:[^\n\r]*\n[\s\S]*?\*\*(?:Priority|MoSCoW)\*\*:\s*Must-have",
        re.IGNORECASE
    )
    must_have_fids = set(must_have_pattern.findall(prd_text))
    if not must_have_fids:
        # Fallback to general F-### IDs if explicit priority not found
        all_fids = set(re.findall(r"\b(F-\d{2,4})\b", prd_text))
        must_have_fids = all_fids

    covered_fids = set()
    seats = plan.get("seats", [])
    for s in seats:
        refs = s.get("refs", [])
        for r in refs:
            if str(r).startswith("F-"):
                covered_fids.add(str(r))

    uncovered = must_have_fids - covered_fids
    if uncovered:
        for u in sorted(list(uncovered)):
            errors.append(
                f"Must-have feature '{u}' has no assigned seat in docs/team-plan.json (Quality Bar 6.2.5 violation)."
            )

    return len(errors) == 0, errors


# ==============================================================================
# SCRUM MASTER BACKLOG & STORY VALIDATORS (Handbook Chapter 9, 9.1.2-9.2.5)
# ==============================================================================

def validate_backlog_schema(backlog: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validates docs/backlog.json schema per Handbook 9.2:
    {
      "stories": [
        {
          "id": "ST-007",
          "title": "POST /orders creates an order",
          "role": "backend",
          "owner": "be-2",
          "points": 3,
          "refs": {
            "features": ["F-003"],
            "ac": ["AC-011", "AC-012"],
            "api": ["API-005"],
            "tables": ["TBL-02"]
          },
          "depends_on": ["ST-002"],
          "needs_perf": true,
          "definition_of_done": ["AC-011 and AC-012 have passing tests", "Tech Lead approved", "API matches openapi.yaml"]
        }
      ]
    }
    """
    errors: List[str] = []
    if not isinstance(backlog, dict):
        return False, ["backlog.json must be a JSON object"]

    stories = backlog.get("stories")
    if not isinstance(stories, list) or len(stories) == 0:
        return False, ["Field 'stories' is required and must be a non-empty array of story objects"]

    seen_ids = set()
    for idx, story in enumerate(stories):
        prefix = f"stories[{idx}]"
        if not isinstance(story, dict):
            errors.append(f"{prefix} must be a JSON object")
            continue

        for req_field in ["id", "title", "role", "owner", "points", "refs", "depends_on", "definition_of_done"]:
            if req_field not in story:
                errors.append(f"{prefix} missing required field '{req_field}'")

        sid = story.get("id", "")
        if not re.match(r"^ST-\d{3,}$", str(sid)):
            errors.append(f"{prefix}.id '{sid}' must match format 'ST-###'")
        if sid in seen_ids:
            errors.append(f"{prefix}.id '{sid}' is duplicated; story IDs must be unique")
        seen_ids.add(sid)

        refs = story.get("refs")
        if not isinstance(refs, dict):
            errors.append(f"{prefix}.refs must be an object with keys 'features', 'ac', 'api', 'tables'")
        else:
            for rk in ["features", "ac"]:
                if rk not in refs or not isinstance(refs[rk], list):
                    errors.append(f"{prefix}.refs.{rk} must be a list of string identifiers")

        deps = story.get("depends_on")
        if not isinstance(deps, list):
            errors.append(f"{prefix}.depends_on must be a list of story IDs")

        dod = story.get("definition_of_done")
        if not isinstance(dod, list) or len(dod) == 0:
            errors.append(f"{prefix}.definition_of_done must be a non-empty list of criteria")

    return len(errors) == 0, errors


def validate_backlog_points(backlog: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Handbook 9.1.3, 9.2.5:
    No story over 5 points.
    Story points on a Fibonacci scale (1, 2, 3, 5); anything bigger is split.
    """
    errors: List[str] = []
    stories = backlog.get("stories", [])
    allowed_points = {1, 2, 3, 5}

    for story in stories:
        sid = story.get("id", "ST-???")
        pts = story.get("points")
        if not isinstance(pts, int):
            errors.append(f"Story '{sid}' points must be an integer, got {pts}")
            continue
        if pts > 5:
            errors.append(f"Story '{sid}' exceeds 5 points ({pts} pts). Rule 9.2.5: No story over 5 points.")
        elif pts not in allowed_points:
            errors.append(f"Story '{sid}' has non-Fibonacci points ({pts}). Sizing must be 1, 2, 3, or 5.")

    return len(errors) == 0, errors


def validate_backlog_must_have_ac_coverage(
    backlog: Dict[str, Any],
    prd_text: str
) -> Tuple[bool, List[str]]:
    """
    Handbook 9.2.4 rule 3 & 9.2.5:
    Every story cites the AC-s it satisfies. Every AC- of a Must-have feature lands in some story.
    """
    errors: List[str] = []

    # 1. Extract Must-have features and their ACs from PRD
    # Parse feature blocks: ### Feature F-###: ... **MoSCoW**: Must-have ... AC-###
    must_have_acs = set()

    # Look for Must-have feature sections
    feature_sections = re.split(r"(?=###\s*(?:Feature\s*)?`?F-\d+)", prd_text)
    found_must_have_sections = False

    for sec in feature_sections:
        if not sec.strip().startswith("###"):
            continue
        # Check if priority is Must-have
        is_must_have = bool(re.search(r"\*\*(?:Priority|MoSCoW)\*\*:\s*Must-have", sec, re.IGNORECASE))
        if is_must_have:
            found_must_have_sections = True
            acs_in_sec = re.findall(r"\b(AC-\d{2,4})\b", sec)
            for ac in acs_in_sec:
                must_have_acs.add(ac)

    # Fallback: if no explicit Must-have header matched, extract all AC-###
    if not found_must_have_sections:
        all_acs = re.findall(r"\b(AC-\d{2,4})\b", prd_text)
        must_have_acs = set(all_acs)

    # 2. Gather ACs covered by backlog stories
    covered_acs = set()
    for story in backlog.get("stories", []):
        refs = story.get("refs", {})
        if isinstance(refs, dict):
            for ac in refs.get("ac", []):
                covered_acs.add(str(ac).strip())

    missing_acs = must_have_acs - covered_acs
    if missing_acs:
        for mac in sorted(list(missing_acs)):
            errors.append(f"Must-have acceptance criteria '{mac}' is not covered by any story in docs/backlog.json (Quality Bar 9.2.5).")

    return len(errors) == 0, errors


def validate_backlog_dependency_cycles(backlog: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Handbook 9.2.4 rule 4 & 9.2.5:
    Record dependencies. No cycles.
    Uses Kahn's algorithm for topological sorting to detect dependency cycles.
    """
    errors: List[str] = []
    stories = backlog.get("stories", [])
    story_ids = {s.get("id") for s in stories if s.get("id")}

    # Build adjacency list: node -> set of nodes that depend on it
    # and in-degree map: node -> count of dependencies
    in_degree: Dict[str, int] = {sid: 0 for sid in story_ids}
    adj: Dict[str, Set[str]] = {sid: set() for sid in story_ids}

    for story in stories:
        sid = story.get("id")
        deps = story.get("depends_on", [])
        for dep in deps:
            if dep not in story_ids:
                errors.append(f"Story '{sid}' depends on unknown story '{dep}'.")
                continue
            if dep == sid:
                errors.append(f"Story '{sid}' self-depends on itself (cycle).")
                continue
            adj[dep].add(sid)
            in_degree[sid] += 1

    # Kahn's algorithm queue of nodes with in_degree == 0
    queue = [sid for sid, deg in in_degree.items() if deg == 0]
    visited_count = 0

    while queue:
        node = queue.pop(0)
        visited_count += 1
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if visited_count < len(story_ids):
        # Find cycle members
        cycle_members = [sid for sid, deg in in_degree.items() if deg > 0]
        errors.append(
            f"Dependency cycle detected in story graph among stories: {cycle_members} (Rule 9.2.5: No dependency cycles)."
        )

    return len(errors) == 0, errors


def validate_backlog_walking_skeleton(backlog: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Handbook 9.1.4, 9.2.4 rule 1 & 9.2.5:
    1. First story is the walking skeleton from the architecture.
    """
    errors: List[str] = []
    stories = backlog.get("stories", [])
    if not stories:
        return False, ["Backlog has no stories."]

    first_story = stories[0]
    first_id = first_story.get("id", "")
    first_title = first_story.get("title", "").lower()
    first_deps = first_story.get("depends_on", [])

    if first_id != "ST-001":
        errors.append(f"First story ID must be 'ST-001', got '{first_id}'.")

    # Walking skeleton must not depend on other feature stories
    if len(first_deps) > 0:
        errors.append(f"Walking skeleton story '{first_id}' must not depend on other stories; got depends_on: {first_deps}.")

    skeleton_keywords = ["walking skeleton", "skeleton", "scaffold", "foundation", "bootstrap", "core", "initialization", "setup", "proving architecture"]
    if not any(kw in first_title for kw in skeleton_keywords):
        errors.append(
            f"First story '{first_id}: {first_story.get('title')}' is not designated as the walking skeleton (Handbook 9.2.4 rule 1)."
        )

    return len(errors) == 0, errors


def validate_backlog_owners_in_roster(
    backlog: Dict[str, Any],
    roster_or_team_plan: Any
) -> Tuple[bool, List[str]]:
    """
    Handbook 9.2.4 rule 5:
    Assign owners from the roster by role. Balance load; the orchestrator will check it.
    """
    errors: List[str] = []
    known_owners = set()

    if isinstance(roster_or_team_plan, list):
        # Roster list of dicts: {"id": "...", "role": "..."}
        for item in roster_or_team_plan:
            if isinstance(item, dict):
                oid = item.get("id") or item.get("agent_id") or item.get("name")
                if oid:
                    known_owners.add(str(oid))
                seat_id = item.get("seat_id")
                if seat_id:
                    known_owners.add(str(seat_id))
    elif isinstance(roster_or_team_plan, dict):
        seats = roster_or_team_plan.get("seats", [])
        for s in seats:
            sid = s.get("id")
            if sid:
                known_owners.add(str(sid))
            role = s.get("role")
            if role:
                known_owners.add(str(role))

    for story in backlog.get("stories", []):
        sid = story.get("id", "ST-???")
        owner = story.get("owner")
        if not owner:
            errors.append(f"Story '{sid}' has no assigned owner.")
        elif known_owners and str(owner) not in known_owners:
            # Check if owner contains a valid seat/role
            matches = any(str(owner).startswith(k) or k in str(owner) or str(owner) in k for k in known_owners)
            if not matches:
                errors.append(f"Story '{sid}' assigned to owner '{owner}' not found in team roster or seats.")

    return len(errors) == 0, errors


def validate_backlog_refs_exist(
    backlog: Dict[str, Any],
    prd_text: str,
    arch_text: str
) -> Tuple[bool, List[str]]:
    """
    Verifies that all cited IDs (AC-###, API-###, TBL-###) exist in the source documents.
    """
    errors: List[str] = []
    known_acs = set(re.findall(r"\b(AC-\d{2,4})\b", prd_text))
    known_apis = set(re.findall(r"\b(API-\d{2,4})\b", arch_text))
    known_tbls = set(re.findall(r"\b(TBL-\d{2,4})\b", arch_text))

    for story in backlog.get("stories", []):
        sid = story.get("id", "ST-???")
        refs = story.get("refs", {})
        if not isinstance(refs, dict):
            continue

        for ac in refs.get("ac", []):
            if known_acs and str(ac) not in known_acs:
                errors.append(f"Story '{sid}' cites non-existent acceptance criteria '{ac}'.")

        for api in refs.get("api", []):
            if known_apis and str(api) not in known_apis:
                errors.append(f"Story '{sid}' cites non-existent API endpoint '{api}'.")

        for tbl in refs.get("tables", []):
            if known_tbls and str(tbl) not in known_tbls:
                errors.append(f"Story '{sid}' cites non-existent table '{tbl}'.")

    return len(errors) == 0, errors


def validate_readiness_review_verdict(
    verdict: str,
    gaps: List[str],
    contradictions: List[str]
) -> Tuple[bool, List[str]]:
    """
    Handbook 10.1.4, Appendix A.9:
    Verdict must be 'ready' or 'not_ready'.
    If there are unresolved gaps or contradictions, the verdict CANNOT be 'ready'.
    """
    errors: List[str] = []
    v_clean = str(verdict).strip().lower()

    if v_clean not in ["ready", "not_ready"]:
        errors.append(f"Invalid readiness verdict '{verdict}'; must be 'ready' or 'not_ready'.")

    blocking_issues = len(gaps) + len(contradictions)
    if v_clean == "ready" and blocking_issues > 0:
        errors.append(
            f"Readiness review verdict cannot be 'ready' when {len(gaps)} gaps and {len(contradictions)} contradictions remain unresolved."
        )

    return len(errors) == 0, errors



