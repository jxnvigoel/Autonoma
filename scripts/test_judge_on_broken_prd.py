import os
import sys
import json

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "engine"))
from judge import evaluate_prd_with_judge
from requirements_parser import parse_ba_data

def test_broken_prd():
    session_id = "0b05551a-0b67-47c5-851e-2f9914555236"
    session_dir = os.path.join("data", "projects", session_id)
    
    with open(os.path.join(session_dir, "intake.json"), "r", encoding="utf-8") as f:
        intake = json.load(f)
    with open(os.path.join(session_dir, "qa_log.json"), "r", encoding="utf-8") as f:
        qa_log = json.load(f)
    with open(os.path.join(session_dir, "docs", "requirements.md"), "r", encoding="utf-8") as f:
        req_text = f.read()
    with open(os.path.join(session_dir, "docs", "prd.md"), "r", encoding="utf-8") as f:
        broken_prd = f.read()

    parsed_ba = parse_ba_data(intake, qa_log, req_text)
    
    print("=== Testing Judge on Previous Broken PRD (DocuPulse Reader 0b05551a) ===")
    verdict = evaluate_prd_with_judge(
        prd_text=broken_prd,
        parsed_ba=parsed_ba,
        rubric_path="skills/pm/rubric.json"
    )

    print(f"Verdict Pass: {verdict.get('pass')} (MUST BE FALSE)")
    print(f"Verdict Summary: {verdict.get('verdict_summary')}")
    print(f"Total Score: {verdict.get('total')} / {verdict.get('max')}")
    print(f"Unsupported Claims / Defect Count: {len(verdict.get('unsupported_claims', []))}")
    print("\nDetected Defects:")
    for idx, claim in enumerate(verdict.get("unsupported_claims", [])):
        print(f"  {idx+1}. [{claim.get('section')}] {claim.get('text')[:80]}")
        print(f"     -> Reason: {claim.get('reason')}")

    assert verdict["pass"] is False, f"Expected Judge to FAIL broken PRD, but it passed!"
    assert len(verdict.get("unsupported_claims", [])) > 0, "Expected unsupported claims to be detected!"
    print("\n>>> SUCCESS: The Judge accurately FAILED the broken PRD as required by Chapter 14 and Quality Bar 5.2.5!")

if __name__ == "__main__":
    test_broken_prd()
