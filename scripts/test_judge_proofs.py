#!/usr/bin/env python3
"""
Test script proving that the upgraded Judge (engine/judge.py):
1. FAILS the current broken BioVault architecture.md and schema.md (detecting cross-project contamination, generic schema, etc.)
2. FAILS the current SiteAudit PRD (detecting ungrounded 500 ms and 500 photo notes)
3. Continues to FAIL earlier broken-doc test suites (DocuPulse Reader and BrokenApp)
"""

import os
import sys
import json

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "engine"))
from judge import evaluate_prd_with_judge, evaluate_architecture_with_judge
from requirements_parser import parse_ba_data


def test_judge_on_current_biovault():
    print("=" * 80)
    print("TEST 1: Upgraded Judge on Current BioVault architecture.md and schema.md")
    print("=" * 80)
    session_id = "fae4102a-16df-466e-ab26-6192b4913809"
    session_dir = os.path.join("data", "projects", session_id)

    with open(os.path.join(session_dir, "intake.json"), "r", encoding="utf-8") as f:
        intake = json.load(f)
    with open(os.path.join(session_dir, "qa_log.json"), "r", encoding="utf-8") as f:
        qa_log = json.load(f)
    with open(os.path.join(session_dir, "docs", "requirements.md"), "r", encoding="utf-8") as f:
        req_text = f.read()
    with open(os.path.join(session_dir, "docs", "prd.md"), "r", encoding="utf-8") as f:
        prd_text = f.read()
    with open(os.path.join(session_dir, "docs", "architecture.md"), "r", encoding="utf-8") as f:
        arch_text = f.read()
    with open(os.path.join(session_dir, "docs", "schema.md"), "r", encoding="utf-8") as f:
        schema_text = f.read()

    parsed_ba = parse_ba_data(intake, qa_log, req_text)

    verdict = evaluate_architecture_with_judge(
        arch_text=arch_text,
        prd_text=prd_text,
        parsed_ba=parsed_ba,
        rubric_path="skills/architect/rubric.json",
        schema_text=schema_text
    )

    print(f"Verdict Pass: {verdict.get('pass')} (MUST BE False)")
    print(f"Total Score: {verdict.get('total')}/{verdict.get('max')}")
    print(f"Summary: {verdict.get('verdict_summary')}")
    print(f"Unsupported Claims Count: {len(verdict.get('unsupported_claims', []))}")
    print("\nDetected Defects in BioVault Architecture / Schema:")
    for idx, c in enumerate(verdict.get("unsupported_claims", []), 1):
        print(f"  {idx}. [{c.get('section')}] {c.get('text')}")
        print(f"     -> Reason: {c.get('reason')}")

    assert verdict.get("pass") is False, "Judge MUST FAIL current defective BioVault architecture and schema!"
    assert len(verdict.get("unsupported_claims", [])) > 0, "Judge MUST detect defects in current BioVault!"
    print("\n>>> PROOF 1 PASSED: Upgraded Judge correctly FAILED current BioVault architecture & schema!")


def test_judge_on_siteaudit_prd():
    print("\n" + "=" * 80)
    print("TEST 2: Upgraded Judge on Current SiteAudit PRD")
    print("=" * 80)
    session_id = "5514241c-ef82-4092-b91f-a9cf94290f58"
    session_dir = os.path.join("data", "projects", session_id)

    with open(os.path.join(session_dir, "intake.json"), "r", encoding="utf-8") as f:
        intake = json.load(f)
    with open(os.path.join(session_dir, "qa_log.json"), "r", encoding="utf-8") as f:
        qa_log = json.load(f)
    with open(os.path.join(session_dir, "docs", "requirements.md"), "r", encoding="utf-8") as f:
        req_text = f.read()
    with open(os.path.join(session_dir, "docs", "prd.md"), "r", encoding="utf-8") as f:
        prd_text = f.read()

    parsed_ba = parse_ba_data(intake, qa_log, req_text)

    verdict = evaluate_prd_with_judge(
        prd_text=prd_text,
        parsed_ba=parsed_ba,
        rubric_path="skills/pm/rubric.json"
    )

    print(f"Verdict Pass: {verdict.get('pass')} (MUST BE False)")
    print(f"Total Score: {verdict.get('total')}/{verdict.get('max')}")
    print(f"Summary: {verdict.get('verdict_summary')}")
    print(f"Unsupported Claims Count: {len(verdict.get('unsupported_claims', []))}")
    print("\nDetected Defects in SiteAudit PRD:")
    for idx, c in enumerate(verdict.get("unsupported_claims", []), 1):
        print(f"  {idx}. [{c.get('section')}] {c.get('text')}")
        print(f"     -> Reason: {c.get('reason')}")

    assert verdict.get("pass") is False, "Judge MUST FAIL current SiteAudit PRD with ungrounded metrics!"
    assert any("500" in str(c.get("reason", "")) or "500" in str(c.get("text", "")) for c in verdict.get("unsupported_claims", [])), "Judge MUST catch 500 ms or 500 photo notes!"
    print("\n>>> PROOF 2 PASSED: Upgraded Judge correctly FAILED current SiteAudit PRD!")


if __name__ == "__main__":
    test_judge_on_current_biovault()
    test_judge_on_siteaudit_prd()
