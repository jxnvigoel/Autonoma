import requests
import json
import time
import os

BASE_URL = "http://127.0.0.1:8765"

def run_test():
    print("=== 1. Starting Fresh BA Session (DocuPulse Reader) ===")
    intake = {
        "project_name": "DocuPulse Reader",
        "description": "A local offline document reader and smart snippet organizer for research scientists with tag-based search and local citation export.",
        "target_users": "Biomedical research scientists and lab technicians",
        "timeline": "8 weeks for v1 MVP",
        "budget": "$6,000 MVP build budget, zero monthly cloud costs"
    }

    res = requests.post(f"{BASE_URL}/ba/start", json=intake, timeout=60)
    assert res.status_code == 200, f"ba_start failed: {res.text}"
    start_data = res.json()
    session_id = start_data["session_id"]
    print(f"Session started: {session_id}")
    print(f"BA Greeting: {start_data['message'][:120]}...")

    print("\n=== 2. Running Discovery Conversation Turns ===")
    turns = [
        "Yes, please go ahead. Let's start the discovery.",
        "The core problem is that biomedical scientists waste hours manually copying snippets across PDF research papers into disconnected text files, and struggle to format bibliography citations for lab reports.",
        "Key requirements: 1) Local document reader with smart highlight snippet tagging (Must Have), 2) One-click local bibliography citation export in BibTeX and Markdown formats (Must Have), 3) All documents and notes stored locally in SQLite with zero cloud uploads for proprietary research data privacy (Must Have), 4) Search latency under 1 second for 5,000 snippets (NFR). Cloud team sync is strictly deferred to v2.",
        "Target timeline is strictly 8 weeks. MVP build budget is $6,000 with zero monthly running costs. Success metric: 80% of lab scientists exporting at least 5 citation summaries per week. Please finalize requirements.md."
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
    print("\n".join(req_doc.split("\n")[:18]))

    print("\n=== 4. Handing off to PM (/pm/start) with Chapter 14 Judge ===")
    pm_start_res = requests.post(f"{BASE_URL}/pm/start", json={"session_id": session_id}, timeout=180)
    assert pm_start_res.status_code == 200, f"pm_start failed: {pm_start_res.text}"
    pm_data = pm_start_res.json()

    print(f"\nPM Message: {pm_data['message']}")
    prd_content = pm_data.get("prd_content", "")
    print(f"\nPRD Content Length: {len(prd_content)} characters")

    judge_verdict = pm_data.get("judge_verdict", {})
    print("\n=== 5. LLM Judge Audit Verdict (Chapter 14) ===")
    print(f"Judge Verdict Pass: {judge_verdict.get('pass')}")
    print(f"Total Score: {judge_verdict.get('total')} / {judge_verdict.get('max')}")
    print(f"Summary: {judge_verdict.get('verdict_summary')}")
    print("Criterion Scores:")
    for score in judge_verdict.get("scores", []):
        crit = score.get("criterion")
        sc = score.get("score")
        mx = score.get("max")
        ev = score.get("evidence", "")[:80]
        fx = score.get("fix", "")
        print(f"  - [{sc}/{mx}] {crit}: {ev}")
        if fx:
            print(f"      Fix: {fx}")

    print("Unsupported Claims:")
    unsupported = judge_verdict.get("unsupported_claims", [])
    if not unsupported:
        print("  None (100% grounded in discovery citations)")
    else:
        for u in unsupported:
            print(f"  - {u.get('text')}: {u.get('reason')}")

    print("\n=== 6. Verifying estimate.json (Section 5.1.6) ===")
    estimate = pm_data.get("estimate", {})
    print(f"Total Estimated Tokens: {estimate.get('total_estimated_tokens')}")
    print(f"Subtotal Tokens: {estimate.get('subtotal_tokens')}")
    print(f"Rework Buffer: {estimate.get('rework_buffer_tokens')} tokens ({estimate.get('rework_buffer_percentage')}%)")
    print(f"Estimated Cost: ${estimate.get('estimated_cost_usd')} USD (Model: {estimate.get('model')})")
    print(f"Ledger Source: {estimate.get('ledger_metadata', {}).get('source')}")

    print("\n=== 7. Testing PM Follow-up Turn (/pm/message) ===")
    pm_msg_res = requests.post(f"{BASE_URL}/pm/message", json={
        "session_id": session_id,
        "message": "Can we confirm that citation exports support both BibTeX and Markdown formats?"
    }, timeout=180)
    assert pm_msg_res.status_code == 200, f"pm_message failed: {pm_msg_res.text}"
    pm_msg_data = pm_msg_res.json()
    print(f"PM Reply: {pm_msg_data['message'][:140]}...")

    print("\n=== 8. Checking Output Files on Disk ===")
    docs_dir = os.path.join("data", "projects", session_id, "docs")
    prd_file = os.path.join(docs_dir, "prd.md")
    estimate_file = os.path.join(docs_dir, "estimate.json")
    assert os.path.exists(prd_file), f"Missing {prd_file}"
    assert os.path.exists(estimate_file), f"Missing {estimate_file}"

    with open(prd_file, "r", encoding="utf-8") as f:
        saved_prd = f.read()

    print(f"Verified {prd_file} ({len(saved_prd)} chars)")
    print(f"Verified {estimate_file}")

    print("\n=== 9. Testing GET /pm/session/{session_id} ===")
    get_res = requests.get(f"{BASE_URL}/pm/session/{session_id}")
    assert get_res.status_code == 200
    sess_data = get_res.json()
    assert sess_data["started"] is True
    assert sess_data["prd_content"] is not None
    assert sess_data["estimate"] is not None
    print("GET /pm/session retrieved full PRD, estimate, and messages successfully.")

    print(f"\nSESSION_ID={session_id}")
    print("ALL CHECKS COMPLETED!")

if __name__ == "__main__":
    run_test()
