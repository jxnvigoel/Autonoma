import requests
import json
import time
import os
import sys

BASE_URL = "http://127.0.0.1:8765"

def run_e2e_full_pipeline():
    print("================================================================================")
    print("STAGE 1-3 MULTI-AGENT PIPELINE TEST: DocuPulse Reader")
    print("Agents: Business Analyst -> Product Manager -> Gate 1 Sign-Off ->")
    print("        Solution Architect (Parallel) + UI/UX Designer (Parallel)")
    print("================================================================================")

    # 1. Start BA Session
    intake = {
        "project_name": "DocuPulse Reader",
        "description": "An offline document reader and smart snippet organizer for research scientists with tag-based search and local citation export.",
        "target_users": "Biomedical research scientists and lab technicians",
        "timeline": "8 weeks for v1 MVP",
        "budget": "$6,000 MVP build budget, zero monthly cloud costs"
    }

    print("\n[Step 1] Starting BA Session...")
    res = requests.post(f"{BASE_URL}/ba/start", json=intake, timeout=60)
    assert res.status_code == 200, f"ba_start failed: {res.text}"
    start_data = res.json()
    session_id = start_data["session_id"]
    print(f"Session started: {session_id}")

    # 2. Conversational Discovery Turns
    turns = [
        "Yes, please go ahead. Let's start the discovery.",
        "The core problem is that biomedical scientists waste hours manually copying snippets across PDF research papers into disconnected text files, and struggle to format bibliography citations for lab reports.",
        "Key requirements: 1) Local document reader with smart highlight snippet tagging (Must Have), 2) One-click local bibliography citation export in BibTeX and Markdown formats (Must Have), 3) All documents and notes stored locally in SQLite with zero cloud uploads for proprietary research data privacy (Must Have), 4) Search latency under 1 second for 5,000 snippets (NFR). Cloud team sync is strictly deferred to v2.",
        "Target timeline is strictly 8 weeks. MVP build budget is $6,000 with zero monthly running costs. Success metric: 80% of lab scientists exporting at least 5 citation summaries per week. Please finalize requirements.md."
    ]

    for idx, ans in enumerate(turns, 1):
        print(f"[Step 2.{idx}] Answering BA discovery prompt...")
        msg_res = requests.post(f"{BASE_URL}/ba/message", json={
            "session_id": session_id,
            "message": ans
        }, timeout=180)
        assert msg_res.status_code == 200, f"Turn {idx} failed: {msg_res.text}"

    # 3. Finalize BA Requirements
    print("\n[Step 3] Fetching requirements.md...")
    req_res = requests.get(f"{BASE_URL}/ba/requirements/{session_id}", timeout=180)
    assert req_res.status_code == 200, f"requirements.md failed: {req_res.text}"
    req_content = req_res.json()["content"]
    print(f"requirements.md generated ({len(req_content)} chars)")

    # 4. Hand off to PM
    print("\n[Step 4] Handing off to Product Manager (Drafting PRD & token estimation)...")
    pm_res = requests.post(f"{BASE_URL}/pm/start", json={"session_id": session_id}, timeout=180)
    assert pm_res.status_code == 200, f"pm_start failed: {pm_res.text}"
    pm_data = pm_res.json()
    prd_content = pm_data.get("prd_content", "")
    print(f"PRD generated ({len(prd_content)} chars)")
    print(f"PM Judge Pass: {pm_data.get('judge_verdict', {}).get('pass')} (Score: {pm_data.get('judge_verdict', {}).get('total')}/24)")

    # 5. Architect Feasibility Check (Step 9)
    print("\n[Step 5] Running Architect Feasibility Check...")
    feas_res = requests.post(f"{BASE_URL}/architect/feasibility/{session_id}", timeout=60)
    assert feas_res.status_code == 200, f"feasibility failed: {feas_res.text}"
    feas_data = feas_res.json()
    print(f"Feasibility Status: {feas_data.get('status')} (Verdict: {feas_data.get('verdict')})")

    # 6. Verify Gate 1 blocks until approved
    print("\n[Step 6] Verifying Gate 1 enforcement (Must block Stage 3 before approval)...")
    blocked_arch = requests.post(f"{BASE_URL}/architect/generate/{session_id}")
    assert blocked_arch.status_code == 403, f"Expected 403 Forbidden before Gate 1 approval, got {blocked_arch.status_code}"
    blocked_des = requests.post(f"{BASE_URL}/designer/generate/{session_id}")
    assert blocked_des.status_code == 403, f"Expected 403 Forbidden before Gate 1 approval, got {blocked_des.status_code}"
    print("Gate 1 correctly BLOCKED both Architect and Designer.")

    # 7. Approve Gate 1
    print("\n[Step 7] Approving Gate 1 Sign-Off...")
    appr_res = requests.post(f"{BASE_URL}/gate1/approve", json={
        "session_id": session_id,
        "client_notes": "DocuPulse Reader PRD, offline scope, and non-goals signed off."
    }, timeout=30)
    assert appr_res.status_code == 200, f"Gate 1 approval failed: {appr_res.text}"
    print("Gate 1 Approved successfully.")

    # 8. Run Solution Architect (Stage 3 Step 11)
    print("\n[Step 8] Running Solution Architect (Generating architecture.md, schema.md, openapi.json)...")
    arch_res = requests.post(f"{BASE_URL}/architect/generate/{session_id}", timeout=180)
    assert arch_res.status_code == 200, f"architect generation failed: {arch_res.text}"
    arch_data = arch_res.json()
    arch_val = arch_data.get("validation", {})
    arch_judge = arch_data.get("judge_verdict", {})
    print(f"Architect Validators Passed: {arch_val.get('all_passed')} ({arch_val.get('passed_count')}/{arch_val.get('checks_count')})")
    print(f"Architect Judge Pass: {arch_judge.get('pass')} (Score: {arch_judge.get('total')}/{arch_judge.get('max')})")

    # 9. Run UI/UX Designer (Stage 3 Step 11 Parallel)
    print("\n[Step 9] Running UI/UX Designer (Generating app-flow.md, design-brief.md)...")
    des_res = requests.post(f"{BASE_URL}/designer/generate/{session_id}", timeout=180)
    assert des_res.status_code == 200, f"designer generation failed: {des_res.text}"
    des_data = des_res.json()
    des_val = des_data.get("validation", {})
    des_judge = des_data.get("judge_verdict", {})
    print(f"Designer Validators Passed: {des_val.get('all_passed')} ({des_val.get('passed_count')}/{des_val.get('checks_count')})")
    print(f"Designer Judge Pass: {des_judge.get('pass')} (Score: {des_judge.get('total')}/{des_judge.get('max')})")

    # 10. Check Cross-Project Contamination
    print("\n[Step 10] Checking for Cross-Project Contamination...")
    combined_docs = f"{arch_data.get('architecture_content', '')} {des_data.get('app_flow_content', '')} {des_data.get('design_brief_content', '')}"
    contamination_words = [
        "biovault", "freezer", "specimen", "barcode", "clia",
        "siteaudit", "photo notes", "field operators", "punchlist"
    ]
    detected_contamination = [w for w in contamination_words if w in combined_docs.lower()]
    assert not detected_contamination, f"Cross-project contamination detected: {detected_contamination}"
    print("Zero cross-project contamination detected! 100% clean domain isolation.")

    # 11. Assertions
    assert arch_val.get("all_passed") is True, "Architect validators must all pass"
    assert arch_judge.get("pass") is True, "Architect Judge must pass"
    assert des_val.get("all_passed") is True, "Designer validators must all pass"
    assert des_judge.get("pass") is True, "Designer Judge must pass"
    assert des_judge.get("total") >= 20, "Designer Judge score must be >= 20"

    print("\n================================================================================")
    print(">>> FULL STAGE 1-3 MULTI-AGENT PIPELINE TEST COMPLETED WITH 100% SUCCESS! <<<")
    print(f"Project: DocuPulse Reader ({session_id})")
    print(f"Gate 1: Approved")
    print(f"Architect: Validated (4/4) & Judge Passed ({arch_judge.get('total')}/24)")
    print(f"Designer:  Validated (4/4) & Judge Passed ({des_judge.get('total')}/24)")
    print("================================================================================")

if __name__ == "__main__":
    run_e2e_full_pipeline()
