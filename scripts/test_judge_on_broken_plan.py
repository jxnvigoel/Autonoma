import os
import sys
import json
import time

WORKSPACE_ROOT = "/Users/janvi/Desktop/Autonoma"
sys.path.insert(0, WORKSPACE_ROOT)

from engine.judge import evaluate_hr_with_judge, evaluate_recruiter_with_judge
from engine.llm_client import default_llm_client

def run_broken_plan_judge_tests():
    print("======================================================================")
    print("RUNNING JUDGE AUDIT ON BROKEN STAFFING & RECRUITER PLANS (A8)")
    print("======================================================================")

    # Use local-only execution to test offline/local behavior with zero cloud rate limits
    for sid in ["broken_plan_01", "broken_plan_02", "broken_plan_03", "broken_plan_04", "broken_plan_05", "broken_plan_06", "broken_plan_07"]:
        default_llm_client.set_project_local_only(sid, True)

    results = []

    # Case 1: Seat with no refs
    time.sleep(1.5)
    plan_no_refs = {
        "seats": [
            {"id": "ROLE-01", "role": "backend", "count": 1, "from_week": 1, "to_week": 3, "why": "API without citations", "refs": []}
        ],
        "timeline_weeks": 3,
        "notes": []
    }
    verdict1 = evaluate_hr_with_judge(
        team_plan_or_session=plan_no_refs,
        prd_text="Feature F-001: Auth",
        architecture_text="ADR-001: FastAPI",
        session_id="broken_plan_01"
    )
    print("\nCase 1 (Seat with no refs):")
    print(f"  Pass: {verdict1.get('pass')}")
    print(f"  Verdict Summary: {verdict1.get('verdict_summary')}")
    print(f"  Unsupported Claims: {verdict1.get('unsupported_claims')}")
    assert verdict1.get("pass") is False, "Judge must FAIL seat with no refs!"
    results.append({"case": "seat_with_no_refs", "pass": verdict1.get("pass"), "summary": verdict1.get("verdict_summary"), "evidence": verdict1.get("unsupported_claims")})

    # Case 2: Must-have feature with no seat
    plan_missing_must_have = {
        "seats": [
            {"id": "ROLE-01", "role": "frontend", "count": 1, "from_week": 1, "to_week": 3, "why": "UI for F-001", "refs": ["F-001"]}
        ],
        "timeline_weeks": 3,
        "notes": []
    }
    # PRD has F-001 and F-002 (Must-have), but F-002 has no seat
    prd_with_uncovered = "## Features\n### Feature F-001: Core UI\nPriority: Must-have\n### Feature F-002: Security Audit\nPriority: Must-have"
    verdict2 = evaluate_hr_with_judge(
        team_plan_or_session=plan_missing_must_have,
        prd_text=prd_with_uncovered,
        architecture_text="ADR-001: Stack",
        session_id="broken_plan_02"
    )
    print("\nCase 2 (Must-have with no seat):")
    print(f"  Pass: {verdict2.get('pass')}")
    print(f"  Verdict Summary: {verdict2.get('verdict_summary')}")
    print(f"  Unsupported Claims: {verdict2.get('unsupported_claims')}")
    assert verdict2.get("pass") is False, "Judge must FAIL must-have with no seat!"
    results.append({"case": "must_have_with_no_seat", "pass": verdict2.get("pass"), "summary": verdict2.get("verdict_summary"), "evidence": verdict2.get("unsupported_claims")})

    # Case 3: Idle seat (> 1 week)
    plan_idle_seat = {
        "seats": [
            {"id": "ROLE-01", "role": "qa", "count": 1, "from_week": 1, "to_week": 4, "idle_weeks": 2, "why": "QA idle for 2 weeks", "refs": ["F-001"]}
        ],
        "timeline_weeks": 4,
        "notes": []
    }
    verdict3 = evaluate_hr_with_judge(
        team_plan_or_session=plan_idle_seat,
        prd_text="Feature F-001: Core",
        architecture_text="ADR-001: Stack",
        session_id="broken_plan_03"
    )
    print("\nCase 3 (Idle seat > 1 week):")
    print(f"  Pass: {verdict3.get('pass')}")
    print(f"  Verdict Summary: {verdict3.get('verdict_summary')}")
    print(f"  Unsupported Claims: {verdict3.get('unsupported_claims')}")
    assert verdict3.get("pass") is False, "Judge must FAIL idle seat!"
    results.append({"case": "idle_seat", "pass": verdict3.get("pass"), "summary": verdict3.get("verdict_summary"), "evidence": verdict3.get("unsupported_claims")})

    # Case 4: Shell tool on document role
    recruiter_report_doc_shell = "# Staffing Report\nAll agents hired."
    profiles_doc_shell = [
        {
            "agent_id": "hr-1",
            "name": "HR Agent",
            "role": "hr",
            "seat_id": "ROLE-01",
            "tools": ["read_file", "write_file", "shell"],  # Shell on doc role!
            "fs_scope": "docs/",
            "reports_to": None,
            "token_cap": 25000
        }
    ]
    verdict4 = evaluate_recruiter_with_judge(
        staffing_report_or_session=recruiter_report_doc_shell,
        agent_profiles=profiles_doc_shell,
        session_id="broken_plan_04"
    )
    print("\nCase 4 (Shell tool on document role):")
    print(f"  Pass: {verdict4.get('pass')}")
    print(f"  Verdict Summary: {verdict4.get('verdict_summary')}")
    print(f"  Unsupported Claims: {verdict4.get('unsupported_claims')}")
    assert verdict4.get("pass") is False, "Judge must FAIL shell tool on document role!"
    results.append({"case": "shell_tool_on_document_role", "pass": verdict4.get("pass"), "summary": verdict4.get("verdict_summary"), "evidence": verdict4.get("unsupported_claims")})

    # Case 5: Ghost reports_to (FK violation)
    profiles_ghost_reports = [
        {
            "agent_id": "backend-1",
            "name": "Dev",
            "role": "backend",
            "seat_id": "ROLE-01",
            "tools": ["read_file", "write_file", "bash"],
            "fs_scope": "projects/",
            "reports_to": "non_existent_manager_99",  # Ghost reports_to!
            "token_cap": 25000
        }
    ]
    verdict5 = evaluate_recruiter_with_judge(
        staffing_report_or_session=recruiter_report_doc_shell,
        agent_profiles=profiles_ghost_reports,
        session_id="broken_plan_05"
    )
    print("\nCase 5 (Ghost reports_to):")
    print(f"  Pass: {verdict5.get('pass')}")
    print(f"  Verdict Summary: {verdict5.get('verdict_summary')}")
    print(f"  Unsupported Claims: {verdict5.get('unsupported_claims')}")
    assert verdict5.get("pass") is False, "Judge must FAIL ghost reports_to!"
    results.append({"case": "ghost_reports_to", "pass": verdict5.get("pass"), "summary": verdict5.get("verdict_summary"), "evidence": verdict5.get("unsupported_claims")})

    # Case 6: Token cap below floor
    profiles_low_cap = [
        {
            "agent_id": "backend-1",
            "name": "Dev",
            "role": "backend",
            "seat_id": "ROLE-01",
            "tools": ["read_file", "write_file", "bash"],
            "fs_scope": "projects/",
            "reports_to": None,
            "token_cap": 500  # Below 2,500 floor!
        }
    ]
    verdict6 = evaluate_recruiter_with_judge(
        staffing_report_or_session=recruiter_report_doc_shell,
        agent_profiles=profiles_low_cap,
        session_id="broken_plan_06"
    )
    print("\nCase 6 (Token cap below floor):")
    print(f"  Pass: {verdict6.get('pass')}")
    print(f"  Verdict Summary: {verdict6.get('verdict_summary')}")
    print(f"  Unsupported Claims: {verdict6.get('unsupported_claims')}")
    assert verdict6.get("pass") is False, "Judge must FAIL token cap below floor!"
    results.append({"case": "token_cap_below_floor", "pass": verdict6.get("pass"), "summary": verdict6.get("verdict_summary"), "evidence": verdict6.get("unsupported_claims")})

    # Case 7: Invented pack
    profiles_invented_pack = [
        {
            "agent_id": "specialist-1",
            "name": "Specialist",
            "role": "quantum_crypto_trading_pack_v999",  # Non-existent pack
            "seat_id": "ROLE-01",
            "tools": ["read_file", "write_file"],
            "fs_scope": "projects/",
            "status": "ready",  # Marked ready despite non-existent pack
            "reports_to": None,
            "token_cap": 25000
        }
    ]
    verdict7 = evaluate_recruiter_with_judge(
        staffing_report_or_session=recruiter_report_doc_shell,
        agent_profiles=profiles_invented_pack,
        session_id="broken_plan_07"
    )
    print("\nCase 7 (Invented skill pack):")
    print(f"  Pass: {verdict7.get('pass')}")
    print(f"  Verdict Summary: {verdict7.get('verdict_summary')}")
    print(f"  Unsupported Claims: {verdict7.get('unsupported_claims')}")
    assert verdict7.get("pass") is False, "Judge must FAIL invented skill pack!"
    results.append({"case": "invented_skill_pack", "pass": verdict7.get("pass"), "summary": verdict7.get("verdict_summary"), "evidence": verdict7.get("unsupported_claims")})

    print("\n======================================================================")
    print("ALL 7 BROKEN CASES CONFIRMED FAILED BY JUDGE WITH EVIDENCE QUOTES!")
    print("======================================================================")
    return results

if __name__ == "__main__":
    run_broken_plan_judge_tests()
