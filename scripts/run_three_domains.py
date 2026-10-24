import os
import sys
import json
import sqlite3
import time

WORKSPACE_ROOT = "/Users/janvi/Desktop/Autonoma"
sys.path.insert(0, WORKSPACE_ROOT)

from engine.requirements_parser import parse_ba_data
from engine.pm import build_handbook_compliant_prd_section_by_section, calculate_project_estimate
from engine.architect import (
    generate_feasibility_note,
    generate_adrs,
    generate_openapi_spec,
    generate_schema_doc,
    generate_team_plan,
    generate_architecture_trd
)
from engine.judge import evaluate_prd_with_judge, evaluate_architecture_with_judge
from engine.validators import (
    validate_prd_pre_judge,
    validate_schema_ddl,
    validate_openapi_spec as code_validate_openapi,
    validate_architecture_pre_judge,
    validate_grounding_corpus
)
from engine.llm_client import default_llm_client

def get_latest_ledger_rows(project_id: str, limit: int = 25):
    db_path = os.path.join(WORKSPACE_ROOT, "data", "office.db")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, task_id, provider, model, input_tokens, output_tokens, cost_usd, latency_ms
        FROM llm_calls
        WHERE project_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (project_id, limit)
    )
    rows = cur.fetchall()
    conn.close()
    return rows

def run_pipeline_for_project(session_id: str, intake: dict, qa_log: list, project_label: str):
    print(f"\n========================================================")
    print(f"RUNNING PIPELINE: {project_label} (ID: {session_id})")
    print(f"========================================================")

    session_dir = os.path.join(WORKSPACE_ROOT, "data", "projects", session_id)
    docs_dir = os.path.join(session_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)

    # Save intake and qa_log
    with open(os.path.join(session_dir, "intake.json"), "w", encoding="utf-8") as f:
        json.dump(intake, f, indent=2)
    with open(os.path.join(session_dir, "qa_log.json"), "w", encoding="utf-8") as f:
        json.dump(qa_log, f, indent=2)
    with open(os.path.join(session_dir, "session_state.json"), "w", encoding="utf-8") as f:
        json.dump({"session_id": session_id, "project_name": intake["project_name"], "local_only": False}, f, indent=2)

    # 1. BA Extraction
    print(f"[{project_label}] 1. BA Requirements Extraction via LLM...")
    parsed_ba = parse_ba_data(intake, qa_log, "", session_id=session_id)
    print(f"  App Name: {parsed_ba['app_name']}")
    print(f"  Personas extracted: {len(parsed_ba.get('personas', []))}")
    print(f"  FRs extracted: {len(parsed_ba.get('functional_reqs', []))}")
    print(f"  NFRs extracted: {len(parsed_ba.get('non_functional_reqs', []))}")

    # 2. PM PRD Generation
    print(f"[{project_label}] 2. PM PRD Section-by-Section via LLM...")
    prd_text, features_list = build_handbook_compliant_prd_section_by_section(
        parsed_ba=parsed_ba,
        session_id=session_id
    )
    prd_path = os.path.join(docs_dir, "prd.md")
    with open(prd_path, "w", encoding="utf-8") as f:
        f.write(prd_text)
    print(f"  PRD generated ({len(prd_text)} chars, {len(features_list)} features).")

    # Code validate PRD
    is_prd_valid, prd_errors = validate_prd_pre_judge(prd_text, parsed_ba.get("qa_map", {}))
    print(f"  PRD Code Validator: valid={is_prd_valid}, errors={len(prd_errors)}")
    assert is_prd_valid, f"PRD failed pre-Judge code validation: {prd_errors}"

    # Estimate.json
    estimate_data = calculate_project_estimate(
        session_id=session_id,
        project_name=parsed_ba["app_name"],
        features=features_list,
        model_name="qwen/qwen3.8-27b"
    )
    with open(os.path.join(docs_dir, "estimate.json"), "w", encoding="utf-8") as f:
        json.dump(estimate_data, f, indent=2)
    print(f"  Estimate.json generated: total_cost_usd=${estimate_data.get('total_cost_usd')}")

    # 3. Architect Feasibility
    print(f"[{project_label}] 3. Architect Feasibility Note via LLM (<= 1 page)...")
    prd_data = {
        "app_name": parsed_ba["app_name"],
        "features": features_list,
        "personas": parsed_ba.get("personas", []),
        "nfrs": parsed_ba.get("non_functional_reqs", []),
        "assumptions": parsed_ba.get("assumptions", [])
    }
    feas_path = generate_feasibility_note(
        session_id=session_id,
        parsed_ba=parsed_ba,
        prd_data=prd_data,
        docs_dir=docs_dir
    )
    with open(feas_path, "r", encoding="utf-8") as f:
        feas_text = f.read()
    print(f"  Feasibility note written to {feas_path} ({len(feas_text)} chars).")

    # 4. Gate 1 Judge
    print(f"[{project_label}] 4. Gate 1 LLM Judge Review...")
    judge_verdict = evaluate_prd_with_judge(
        prd_text=prd_text,
        parsed_ba=parsed_ba,
        rubric_path="skills/pm/rubric.json",
        session_id=session_id
    )
    print(f"  Judge Verdict: pass={judge_verdict.get('pass')}, score={judge_verdict.get('total_score')}/{judge_verdict.get('max_total_score')}")
    print(f"  Judge Summary: {judge_verdict.get('verdict_summary')}")
    assert judge_verdict.get("pass") is True, f"Gate 1 Judge failed: {judge_verdict}"

    # 5. Architect Deliverables
    print(f"[{project_label}] 5. Architect ADRs via LLM...")
    adr_list = generate_adrs(parsed_ba, prd_data, docs_dir, session_id=session_id)
    print(f"  Generated {len(adr_list)} ADRs.")

    print(f"[{project_label}] 6. Architect Schema DDL via LLM (SQLite executed)...")
    schema_path = generate_schema_doc(parsed_ba, prd_data, docs_dir, session_id=session_id)
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_text = f.read()
    is_ddl_valid, ddl_errors, created_tables = validate_schema_ddl(schema_text)
    print(f"  Schema DDL validated: tables={created_tables}, errors={ddl_errors}")
    assert is_ddl_valid, f"Schema validation failed: {ddl_errors}"

    print(f"[{project_label}] 7. Architect OpenAPI 3.0.3 via LLM...")
    openapi_path = generate_openapi_spec(parsed_ba, prd_data, docs_dir, session_id=session_id)
    with open(openapi_path, "r", encoding="utf-8") as f:
        openapi_yaml = f.read()
    is_oas_valid, oas_errors, ep_ids = code_validate_openapi(openapi_yaml, prd_features=features_list)
    print(f"  OpenAPI validated: endpoints={len(ep_ids)}, errors={oas_errors}")
    assert is_oas_valid, f"OpenAPI validation failed: {oas_errors}"

    print(f"[{project_label}] 8. Architect Team Plan...")
    team_plan_path = generate_team_plan(parsed_ba, prd_data, docs_dir, adrs=adr_list)
    print(f"  Team plan saved to {team_plan_path}.")

    print(f"[{project_label}] 9. Architect Architecture TRD (12 points) via LLM...")
    arch_path = generate_architecture_trd(parsed_ba, prd_data, docs_dir, adr_list=adr_list, session_id=session_id)
    with open(arch_path, "r", encoding="utf-8") as f:
        arch_text = f.read()
    is_arch_valid, arch_errors = validate_architecture_pre_judge(arch_text, prd_data, adr_list)
    print(f"  Architecture code validated: valid={is_arch_valid}, errors={arch_errors}")
    assert is_arch_valid, f"Architecture validation failed: {arch_errors}"

    # Evaluate Architecture with Judge
    arch_verdict = evaluate_architecture_with_judge(
        arch_text=arch_text,
        prd_text=prd_text,
        rubric_path="skills/architect/rubric.json",
        session_id=session_id
    )
    print(f"  Architecture Judge Verdict: pass={arch_verdict.get('pass')}, score={arch_verdict.get('total_score')}/{arch_verdict.get('max_total_score')}")

    ledger_rows = get_latest_ledger_rows(session_id, limit=30)
    print(f"\n[{project_label}] REAL LLM CALLS LOGGED: {len(ledger_rows)} rows")
    for r in ledger_rows[:10]:
        print(f"  Row ID {r[0]}: task='{r[1]}', model='{r[3]}', tokens={r[4]} in / {r[5]} out, cost=${r[6]:.5f}, latency={r[7]}ms")

    return {
        "session_id": session_id,
        "project_label": project_label,
        "prd_valid": is_prd_valid,
        "gate1_pass": judge_verdict.get("pass"),
        "schema_tables": created_tables,
        "openapi_endpoints": len(ep_ids),
        "arch_valid": is_arch_valid,
        "ledger_count": len(ledger_rows),
        "ledger_rows": ledger_rows
    }

def main():
    results = []

    # Domain 1: BioVault Lab Specimen Tracker
    biovault_intake = {
        "project_name": "BioVault Lab Specimen Tracker",
        "description": "Desktop tracking system for cryogenic bio-specimens, accessioning, 2D DataMatrix barcodes, freezer cold-chain chain of custody, and audit log compliance.",
        "target_users": "Lab Technician, Principal Investigator, Compliance Auditor",
        "timeline": "6 weeks for v1 MVP",
        "budget": "$10,000 budget, < $50/mo infrastructure",
        "created_at": "2026-10-24T12:00:00Z"
    }
    biovault_qa_log = [
        {
            "id": "Q-001",
            "question": "What is the primary problem you are solving today?",
            "answer": "Technicians lose 25 minutes per cryogenic specimen retrieval searching through paper freezer logs. Misplaced bio-specimens risk sample degradation and violate regulatory cold-chain custody requirements."
        },
        {
            "id": "Q-002",
            "question": "Who are the key personas that interact with the system?",
            "answer": "Lab Technician scans 2D DataMatrix barcodes and accessions samples. Principal Investigator monitors specimen inventory. Compliance Auditor inspects unbroken chain of custody records."
        },
        {
            "id": "Q-003",
            "question": "What are the core functional requirements for the v1 release?",
            "answer": "Accession incoming bio-specimens with 2D DataMatrix barcode generation [FR-01], log cold-storage temperature thresholds and excursion alerts [FR-02], and track custodial handoff transfers with recipient sign-offs [FR-03]."
        },
        {
            "id": "Q-004",
            "question": "What are the non-functional requirements and deployment constraints?",
            "answer": "Desktop offline-first application with 100% local database persistence [NFR-01], search latency under 1.0 second [NFR-02], and support 50,000 specimen records locally without degradation [NFR-03]."
        }
    ]
    res1 = run_pipeline_for_project("biovault_live_run", biovault_intake, biovault_qa_log, "BioVault Lab")
    results.append(res1)

    # Domain 2: AeroFleet Hangar
    aerofleet_intake = {
        "project_name": "AeroFleet Hangar",
        "description": "Mission-critical aviation fleet airworthiness management and hangar maintenance console for Part 145 repair stations. Tracks airframe work orders, technician task sign-offs, squawk logs, and airworthiness release exports.",
        "target_users": "A&P Mechanics, Chief Inspectors, Maintenance Controllers",
        "timeline": "6 weeks MVP",
        "budget": "$25,000",
        "created_at": "2026-10-24T12:00:00Z"
    }
    aerofleet_qa_log = [
        {
            "id": "Q-001",
            "question": "What is the primary problem AeroFleet Hangar solves?",
            "answer": "Aircraft-on-Ground (AOG) downtime costs $15,000/hr when technicians cannot track airframe work order sign-offs and open discrepancy squawks in real time."
        },
        {
            "id": "Q-002",
            "question": "Who uses the system in the hangar?",
            "answer": "A&P Mechanic performs maintenance tasks and logs squawks. Chief Inspector reviews discrepancy corrective actions and signs airworthiness approvals. Maintenance Controller tracks fleet readiness."
        },
        {
            "id": "Q-003",
            "question": "What are the core functional features for v1?",
            "answer": "Manage airframe scheduled work orders [FR-01], log line maintenance squawk discrepancies [FR-02], and certify technician return-to-service sign-offs [FR-03]."
        },
        {
            "id": "Q-004",
            "question": "What constraints must be adhered to?",
            "answer": "Local offline execution in aircraft hangars without internet [NFR-01], search response under 1.2s [NFR-02], and tamper-evident local audit log retention [NFR-03]."
        }
    ]
    res2 = run_pipeline_for_project("aerofleet_live_run", aerofleet_intake, aerofleet_qa_log, "AeroFleet Hangar")
    results.append(res2)

    # Domain 3: PayFlow Global (From scratch, zero prior fixtures)
    payflow_intake = {
        "project_name": "PayFlow Global Ledger",
        "description": "Multi-currency B2B payment orchestration and real-time ledger settlement platform with credit card charge tokenization, webhook signature verification, and automated invoice reconciliation.",
        "target_users": "Treasury Operations Manager, Merchant Admin, Compliance Officer",
        "timeline": "6 weeks for v1 MVP",
        "budget": "$30,000 budget, < $100/mo cloud infrastructure",
        "created_at": "2026-10-24T12:00:00Z"
    }
    payflow_qa_log = [
        {
            "id": "Q-001",
            "question": "What is the core business problem PayFlow Global solves?",
            "answer": "Cross-border B2B merchants lose 4.2% of revenue on double-spend payment disputes and un-reconciled gateway webhook events across disparate merchant currencies."
        },
        {
            "id": "Q-002",
            "question": "Who are the primary actors using PayFlow Global?",
            "answer": "Treasury Operations Manager monitors settlement balances and approves large transfers. Merchant Admin initiates idempotent payment charges. Compliance Officer audits PCI DSS tokenized transactions."
        },
        {
            "id": "Q-003",
            "question": "What are the core functional requirements for the v1 platform?",
            "answer": "Initiate credit card payment charges with idempotency keys [FR-01], manage double-entry multi-currency ledger accounts [FR-02], and verify gateway webhook HMAC-SHA256 signatures [FR-03]."
        },
        {
            "id": "Q-004",
            "question": "What security and performance boundaries must be respected?",
            "answer": "End-to-end payment processing latency under 1.5 seconds [NFR-01], zero raw PAN/CVV database persistence adhering to PCI DSS v4.0.1 [NFR-02], and immutable SHA-256 audit log hashing [NFR-03]."
        }
    ]
    res3 = run_pipeline_for_project("payflow_global_scratch", payflow_intake, payflow_qa_log, "PayFlow Global")
    results.append(res3)

    print("\n\n========================================================")
    print("ALL 3 UNRELATED DOMAINS COMPLETED SUCCESSFULLY!")
    print("========================================================")
    for r in results:
        print(f"Project: {r['project_label']} ({r['session_id']})")
        print(f"  PRD Valid: {r['prd_valid']}")
        print(f"  Gate 1 Pass: {r['gate1_pass']}")
        print(f"  Schema Tables: {r['schema_tables']}")
        print(f"  OpenAPI Endpoints: {r['openapi_endpoints']}")
        print(f"  Arch TRD Valid: {r['arch_valid']}")
        print(f"  Total LLM Calls: {r['ledger_count']}")

if __name__ == "__main__":
    main()
