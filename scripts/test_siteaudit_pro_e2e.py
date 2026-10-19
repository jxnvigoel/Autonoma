import requests
import json
import time
import os
import re

BASE_URL = "http://127.0.0.1:8765"

def run_test():
    print("=== 1. Starting Fresh BA Session (SiteAudit Pro) ===")
    intake = {
        "project_name": "SiteAudit Pro",
        "description": "A local offline construction site inspection and hazard log tool for civil engineers and safety inspectors with structured deficiency tagging, offline photo-note organization, and one-click compliance punch-list export.",
        "target_users": "Civil engineers, construction safety inspectors",
        "timeline": "7 weeks for v1 MVP",
        "budget": "$7,500 MVP build budget, zero monthly subscription costs"
    }

    res = requests.post(f"{BASE_URL}/ba/start", json=intake, timeout=60)
    assert res.status_code == 200, f"ba_start failed: {res.text}"
    start_data = res.json()
    session_id = start_data["session_id"]
    print(f"Session started: {session_id}")
    print(f"BA Greeting: {start_data['message'][:120]}...")

    print("\n=== 2. Running Multi-Turn Discovery (Distinct Today vs Core Problem vs Shortcomings) ===")
    turns = [
        # Turn 1 (Q-001): Intake confirmation
        "Yes, please go ahead. Let's start the discovery.",

        # Turn 2 (Q-002): Today's workflow
        "Today, field inspectors walk construction sites carrying paper clipboards and handwritten checklists, taking photos on personal phones, and then spending 2 to 3 hours every evening manually typing handwritten notes into spreadsheets.",

        # Turn 3 (Q-003): Core problem
        "The core problem is that manual clipboard transcription results in a 15% error rate in structural safety logs, lost photo context, and delayed critical hazard notices that risk job-site shutdowns and regulatory fines.",

        # Turn 4 (Q-004): Why existing tools fall short & Key Requirements
        "Existing commercial construction platforms require persistent cloud connectivity which fails in underground basements and remote job sites, and charge expensive per-seat monthly subscriptions. Key requirements: 1) Local offline site inspection checklist with structured hazard deficiency tagging (Must Have), 2) One-click local punch-list report export in CSV and formatted print-ready text (Must Have), 3) All inspection logs and photo notes stored on local device storage with zero cloud uploads for site data privacy and basement offline reliability (Must Have), 4) Inspection log search and filter response time under 1 second across 3,000 site records (NFR). Real-time contractor cloud portal sync is strictly deferred to v2.",

        # Turn 5 (Q-005): Timeline, Budget & Success Metric
        "Target timeline is strictly 7 weeks for v1 MVP. Build budget is $7,500 with zero monthly subscription fees. Success metric: 90% of field inspectors generating daily punch-list reports on the same day as the inspection. Please finalize requirements.md."
    ]

    for idx, ans in enumerate(turns):
        print(f"\nSending Turn {idx+1}: {ans[:60]}...")
        msg_res = requests.post(f"{BASE_URL}/ba/message", json={
            "session_id": session_id,
            "message": ans
        }, timeout=180)
        assert msg_res.status_code == 200, f"Turn {idx+1} failed: {msg_res.text}"
        data = msg_res.json()
        print(f"BA Response {idx+1}: {data['message'][:100]}...")

    print("\n=== 3. Finalizing BA requirements.md ===")
    req_res = requests.get(f"{BASE_URL}/ba/requirements/{session_id}", timeout=180)
    assert req_res.status_code == 200, f"requirements.md failed: {req_res.text}"
    req_doc = req_res.json()["content"]
    print(f"requirements.md created ({len(req_doc)} chars):")
    print("\n".join(req_doc.split("\n")[:20]))

    print("\n=== 4. Handing off to PM (/pm/start) with Chapter 14 Judge ===")
    pm_start_res = requests.post(f"{BASE_URL}/pm/start", json={"session_id": session_id}, timeout=180)
    assert pm_start_res.status_code == 200, f"pm_start failed: {pm_start_res.text}"
    pm_data = pm_start_res.json()

    print(f"\nPM Greeting: {pm_data['message']}")
    prd_content = pm_data.get("prd_content", "")
    print(f"\nPRD Content Length: {len(prd_content)} characters")

    judge_verdict = pm_data.get("judge_verdict", {})
    print("\n=== 5. LLM Judge Audit Verdict (Chapter 14) ===")
    print(f"Judge Verdict Pass: {judge_verdict.get('pass')}")
    print(f"Total Score: {judge_verdict.get('total')} / {judge_verdict.get('max')}")
    print(f"Verdict Summary: {judge_verdict.get('verdict_summary')}")
    print("Criterion Scores:")
    for score in judge_verdict.get("scores", []):
        crit = score.get("criterion")
        sc = score.get("score")
        mx = score.get("max")
        ev = score.get("evidence", "")[:85]
        fx = score.get("fix", "")
        print(f"  - [{sc}/{mx}] {crit}: {ev}")
        if fx:
            print(f"      Fix: {fx}")

    print("\nUnsupported Claims / Defect Checks:")
    unsupported = judge_verdict.get("unsupported_claims", [])
    if not unsupported:
        print("  NONE! All claims, numbers, and citations 100% grounded and compliant with Quality Bar 5.2.5.")
    else:
        for u in unsupported:
            print(f"  - [{u.get('section')}] {u.get('text')}: {u.get('reason')}")

    assert judge_verdict.get("pass") is True, "Judge evaluation MUST pass!"
    assert len(unsupported) == 0, f"Judge detected {len(unsupported)} unsupported claims!"

    print("\n=== 6. Number Verification (Cross-referencing PRD vs qa_log.json) ===")
    docs_dir = os.path.join("data", "projects", session_id, "docs")
    with open(os.path.join(docs_dir, "prd.md"), "r", encoding="utf-8") as f:
        saved_prd = f.read()
    with open(os.path.join("data", "projects", session_id, "qa_log.json"), "r", encoding="utf-8") as f:
        saved_qa = json.load(f)

    all_qa_text = " ".join([q["question"] + " " + q["answer"] for q in saved_qa])

    # Numbers to check
    numbers_to_verify = [
        ("7 weeks", "Section 1, 4, 7, 9 Timeline", "7 weeks for v1 MVP"),
        ("$7,500", "Section 9 Budget", "$7,500"),
        ("90%", "Section 4 Success Metric", "90% of field inspectors"),
        ("3,000", "Section 6 NFR Capacity / Section 7 Risk", "3,000 site records"),
        ("1.0 s", "Section 6 Latency Target", "under 1 second / 1.0 s")
    ]

    for num_str, location, context in numbers_to_verify:
        in_qa = num_str in all_qa_text or ("1 second" in all_qa_text and num_str == "1.0 s")
        in_prd = num_str in saved_prd or ("1.0 s" in saved_prd and num_str == "1.0 s")
        print(f"  - Number: '{num_str}' | Location: {location} | In QA Log: {in_qa} | In PRD: {in_prd}")
        assert in_qa, f"Number '{num_str}' not found in qa_log.json!"
        assert in_prd, f"Number '{num_str}' not found in PRD!"

    print("\n=== 7. Verifying estimate.json (Section 5.1.6) ===")
    estimate = pm_data.get("estimate", {})
    print(f"Total Estimated Tokens: {estimate.get('total_estimated_tokens')}")
    print(f"Subtotal Tokens: {estimate.get('subtotal_tokens')}")
    print(f"Rework Buffer: {estimate.get('rework_buffer_tokens')} tokens ({estimate.get('rework_buffer_percentage')}%)")
    print(f"Estimated Cost: ${estimate.get('estimated_cost_usd')} USD (Model: {estimate.get('model')})")

    print(f"\nSESSION_ID={session_id}")
    print("ALL SITEAUDIT PRO E2E CHECKS PASSED!")

if __name__ == "__main__":
    run_test()
