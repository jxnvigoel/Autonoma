#!/usr/bin/env python3
"""
End-to-end test script for the complete Virtual Office pipeline:
BA -> PM -> Feasibility Check (Stage 2 Step 8) -> Gate 1 Enforcement -> Gate 1 Approval ->
Architect Stage 3 Generation (architecture.md, openapi.yaml, schema.md, ADRs, team-plan.json) ->
Code-Level Validators (OpenAPI linter, SQLite DDL execution, Traceability) -> Judge Review.

Tested on a NEW project idea: BioVault Lab (Clinical Specimen & Cold-Chain Custody Tracker).
"""

import os
import sys
import json
import time
import requests

BASE_URL = "http://127.0.0.1:8765"

def log(msg):
    print(f"\n[E2E-TEST] {msg}")

def main():
    log("Starting E2E pipeline test for new project 'BioVault Lab'...")

    if len(sys.argv) > 1 and sys.argv[1]:
        session_id = sys.argv[1]
        log(f"Resuming existing session: {session_id}")
    else:
        # Step 1: BA Start
        log("Step 1: Initiating BA intake for BioVault Lab...")
        intake_payload = {
            "project_name": "BioVault Lab",
            "description": "A standalone desktop and local-network laboratory specimen inventory and chain-of-custody tracking tool for diagnostic pathology labs. It tracks bio-specimen accessioning, freezer cold-chain temperature logs, custodian sign-offs, and regulatory compliance audit exports.",
            "target_users": "Lab Technicians, Pathology Lab Managers, Quality Compliance Auditors",
            "timeline": "4 weeks MVP",
            "budget": "$6,000 development budget, local deployment with $0 monthly cloud costs"
        }

        res = requests.post(f"{BASE_URL}/ba/start", json=intake_payload, timeout=60)
        assert res.status_code == 200, f"BA start failed: {res.text}"
        start_data = res.json()
        session_id = start_data["session_id"]
        log(f"BA session created: {session_id}")

        # Step 2: Feed discovery answers into BA to complete the 9-point checklist
        discovery_answers = [
            "Yes, let's begin. We are building BioVault Lab to eliminate sample misplacement and compliance penalties in clinical diagnostic labs.",
            "The primary users are Lab Technicians who scan specimen vials, Lab Managers who monitor storage, and Quality Auditors who inspect the chain of custody. We need specimen check-in with 2D barcode generation [FR-01], cold-storage temperature excursion logging [FR-02], custodial transfer sign-off with digital confirmation [FR-03], and PDF/CSV regulatory inspection audit export [FR-04].",
            "For performance and privacy: barcode scanning and specimen search must respond in under 1.5 seconds [NFR-01]. All patient and specimen data must be stored locally on lab premises with zero cloud uploads for HIPAA and CLIA compliance [NFR-02]. The local system must support at least 10,000 specimen records [NFR-03].",
            "The software must run offline on lab workstations running macOS and Windows [NFR-04]. Gloved technicians need full keyboard navigation and high contrast matching WCAG 2.2 AA [NFR-05].",
            "We have confirmed all requirements: 4 weeks timeline, $6,000 budget, $0 monthly cloud spend, and local SQLite data storage. Please generate the complete requirements document."
        ]

        for i, ans in enumerate(discovery_answers, 1):
            log(f"Sending discovery answer {i}/5 to BA...")
            res = requests.post(f"{BASE_URL}/ba/message", json={"session_id": session_id, "message": ans}, timeout=120)
            assert res.status_code == 200, f"BA message {i} failed: {res.text}"

        # Step 3: Trigger PM to generate PRD and token estimate
        log("Step 3: Triggering PM agent to produce PRD and estimate...")
        res = requests.post(f"{BASE_URL}/pm/start", json={"session_id": session_id}, timeout=180)
        assert res.status_code == 200, f"PM start failed: {res.text}"
        pm_data = res.json()
        prd_content = pm_data.get("prd_content", "")
        assert len(prd_content) > 500, "PRD was not generated properly!"
        log(f"PM produced PRD ({len(prd_content)} chars) and estimate.")

    # Step 4: Feasibility Check (Stage 2 Step 8)
    log("Step 4: Executing Architect Stage 2 Step 8 feasibility check (<= 1 page note)...")
    res = requests.post(f"{BASE_URL}/architect/feasibility/{session_id}", timeout=60)
    assert res.status_code == 200, f"Feasibility check failed: {res.text}"
    feasibility_data = res.json()
    assert feasibility_data.get("status") in ["feasible", "feasibility_completed"]
    feasibility_note = feasibility_data.get("content", "") or feasibility_data.get("feasibility_note", "")
    log(f"Feasibility note generated ({len(feasibility_note)} chars). Fit: {feasibility_data.get('verdict')}")

    # Step 5 & 6: Gate 1 Enforcement & Approval (Handbook Section 2.7.3 step 10)
    gate_check = requests.get(f"{BASE_URL}/gate1/status/{session_id}").json()
    is_approved = gate_check.get("gate1", {}).get("approved") or gate_check.get("approved")
    if not is_approved:
        log("Step 5: Testing Gate 1 enforcement (must reject Architect generation prior to approval)...")
        res = requests.post(f"{BASE_URL}/architect/generate/{session_id}", timeout=30)
        assert res.status_code == 403, f"Gate 1 failed to block unapproved design start! Status: {res.status_code}"
        log(">>> CONFIRMED: Gate 1 blocked unapproved design start with HTTP 403 Forbidden.")

        log("Step 6: Client approves Gate 1 in Virtual Office...")
        res = requests.post(f"{BASE_URL}/gate1/approve", json={
            "session_id": session_id,
            "client_notes": "BioVault Lab PRD, scope, non-goals, and assumptions are approved for technical design."
        }, timeout=30)
        assert res.status_code == 200, f"Gate 1 approval failed: {res.text}"
        gate_res = res.json()
        assert gate_res.get("status") == "approved" or gate_res.get("approved") is True
        log(">>> CONFIRMED: Gate 1 approved.")
    else:
        log("Gate 1 already verified and approved for this session.")

    # Step 7: Architect Stage 3 Generation (Handbook Section 2.7.4 steps 11-13)
    log("Step 7: Executing Architect Stage 3 generation (TRD, OpenAPI, Schema, ADRs, Team Plan)...")
    res = requests.post(f"{BASE_URL}/architect/generate/{session_id}", timeout=180)
    assert res.status_code == 200, f"Architect generation failed: {res.text}"
    arch_res = res.json()
    
    validation = arch_res.get("validation") or arch_res.get("validation_results") or {}
    judge = arch_res.get("judge_verdict", {})
    
    log(f"OpenAPI Valid: {validation.get('openapi_valid')}")
    log(f"Schema DDL Valid: {validation.get('schema_valid')}")
    log(f"Traceability Valid: {validation.get('traceability_valid')}")
    log(f"All Validators Passed: {validation.get('all_passed')}")
    log(f"Judge Verdict Score: {judge.get('total')}/{judge.get('max')} (Pass: {judge.get('pass')})")

    assert validation.get("all_passed") is True, f"Code validators failed: {validation}"
    assert judge.get("pass") is True, f"Judge failed architecture: {judge}"

    log("\n>>> ALL STAGES COMPLETED SUCCESSFULLY FOR BIOVAULT LAB!")
    print(json.dumps({
        "session_id": session_id,
        "validation_results": validation,
        "judge_score": f"{judge.get('total')}/{judge.get('max')}",
        "judge_pass": judge.get("pass")
    }, indent=2))

if __name__ == "__main__":
    main()
