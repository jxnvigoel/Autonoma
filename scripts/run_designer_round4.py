"""
Designer Round 4 Autonomous Runner
Executes the Designer pipeline with zero template fallbacks, dual-surface contrast checks,
dynamic navigation/keyboard generation, and full LLM Judge evaluation across 3 unrelated domains:
1. BioVault Lab (Clinical Specimen Tracking) - 67abb028-5907-4a5b-8b24-3d069a0ca047
2. AeroFleet Hangar (Aviation Airframe Maintenance) - a1f0e4b8-8c3d-4952-b68a-92e105db084c
3. SiteAudit Pro (Construction Job-Site Safety Inspection, built from scratch) - 5514241c-ef82-4092-b91f-a9cf94290f58
"""

import os
import sys
import json
import sqlite3
import time
from typing import Any, Dict

ENGINE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "engine"))
if ENGINE_DIR not in sys.path:
    sys.path.insert(0, ENGINE_DIR)

from designer import run_designer_pipeline, calculate_contrast

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROJECTS_DIR = os.path.join(PROJECT_ROOT, "data", "projects")
DB_PATH = os.path.join(PROJECT_ROOT, "data", "office.db")

def get_session_dir(session_id: str) -> str:
    return os.path.join(PROJECTS_DIR, session_id)

def load_json(path: str, default=None):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default if default is not None else {}
    return default if default is not None else {}

def save_json(path: str, data: Any):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

projects = [
    ("BioVault Lab", "67abb028-5907-4a5b-8b24-3d069a0ca047"),
    ("AeroFleet Hangar", "a1f0e4b8-8c3d-4952-b68a-92e105db084c"),
    ("SiteAudit Pro", "5514241c-ef82-4092-b91f-a9cf94290f58")
]

results = {}

for idx, (name, session_id) in enumerate(projects):
    if idx > 0:
        print(f"\n[Pacing Delay] Waiting 25s between projects to refresh Groq RPM/TPM window...")
        time.sleep(25)

    print(f"\n{'='*75}\n[ROUND 4] EXECUTING DESIGNER PIPELINE: {name} ({session_id})\n{'='*75}")
    t0 = time.time()
    res = run_designer_pipeline(
        session_id=session_id,
        get_session_dir_fn=get_session_dir,
        load_json_fn=load_json,
        save_json_fn=save_json
    )
    elapsed = time.time() - t0

    # Query all ledger calls recorded for this session
    calls = []
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            """SELECT id, agent_id, task_id, model, input_tokens, output_tokens, cost_usd, latency_ms, at
               FROM llm_calls
               WHERE project_id=? AND agent_id IN ('designer', 'judge')
               ORDER BY id ASC""",
            (session_id,)
        )
        for r in cur.fetchall():
            calls.append({
                "id": r[0],
                "agent_id": r[1],
                "task_id": r[2],
                "model": r[3],
                "input_tokens": r[4],
                "output_tokens": r[5],
                "cost_usd": r[6],
                "latency_ms": r[7],
                "at": r[8]
            })
        conn.close()

    val = res.get("validation", {})
    judge = res.get("judge_verdict", {})

    results[name] = {
        "session_id": session_id,
        "elapsed_sec": round(elapsed, 1),
        "validation": val,
        "judge": judge,
        "tokens": res.get("tokens", {}),
        "ledger_calls": calls,
        "app_flow_path": os.path.join(get_session_dir(session_id), "docs", "app-flow.md"),
        "design_brief_path": os.path.join(get_session_dir(session_id), "docs", "design-brief.md")
    }

    print(f"\n--- Result for {name} ---")
    print(f"Validation All Passed: {val.get('all_passed')} ({val.get('passed_count')}/{val.get('checks_count')} checks passed)")
    if val.get("errors"):
        print(f"Validation Errors ({len(val['errors'])}):")
        for err in val["errors"]:
            print(f"  - {err}")

    print(f"Judge Pass: {judge.get('pass')} | Score: {judge.get('total')}/{judge.get('max')}")
    print(f"Unsupported Claims: {len(judge.get('unsupported_claims', []))}")
    if judge.get("unsupported_claims"):
        print("Judge Flagged Claims:")
        for uc in judge.get("unsupported_claims", []):
            print(f"  - [{uc.get('section')}] {uc.get('reason')} (Text: {uc.get('text')})")

print("\n\n" + "="*75)
print("ROUND 4 PIPELINE EXECUTION COMPLETE FOR ALL 3 PROJECTS")
print("="*75)
for name, data in results.items():
    v = data["validation"]
    j = data["judge"]
    toks = data["tokens"]
    val_status = "PASS (0 errors)" if v.get("all_passed") else f"FAIL ({len(v.get('errors', []))} errors)"
    judge_status = "PASS (24/24)" if j.get("pass") else f"FAIL ({j.get('total')}/24, {len(j.get('unsupported_claims', []))} claims)"
    print(f"\nProject: {name}")
    print(f"  - Session ID: {data['session_id']}")
    print(f"  - Elapsed: {data['elapsed_sec']}s")
    print(f"  - Validation: {val_status}")
    print(f"  - Judge Verdict: {judge_status}")
    print(f"  - LLM Calls Recorded in Ledger: {len(data['ledger_calls'])}")
    numeric_latency_sum = sum(c['latency_ms'] for c in data['ledger_calls'] if c.get('latency_ms') is not None)
    print(f"  - Total Numeric Latency: {numeric_latency_sum} ms")
