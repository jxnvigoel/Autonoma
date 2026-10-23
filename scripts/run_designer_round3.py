"""
Executes Designer Round 3 Pipeline on 3 distinct project domains:
1. BioVault Lab (Clinical Specimen Tracking) - session 67abb028-5907-4a5b-8b24-3d069a0ca047
2. AeroFleet Hangar (Aviation Airframe Maintenance) - session a1f0e4b8-8c3d-4952-b68a-92e105db084c
3. SiteAudit Pro (Construction Job-Site Safety Inspection) - session 5514241c-ef82-4092-b91f-a9cf94290f58
"""

import os
import sys
import json
import sqlite3

ENGINE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "engine"))
if ENGINE_DIR not in sys.path:
    sys.path.insert(0, ENGINE_DIR)

from designer import run_designer_pipeline, calculate_contrast

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROJECTS_DIR = os.path.join(PROJECT_ROOT, "data", "projects")

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

import time

for idx, (name, session_id) in enumerate(projects):
    if idx > 0:
        print("\nPacing delay between projects (20s) to refresh Groq rate limit window...")
        time.sleep(20)
    print(f"\n{'='*70}\nRUNNING DESIGNER PIPELINE FOR: {name} ({session_id})\n{'='*70}")
    res = run_designer_pipeline(
        session_id=session_id,
        get_session_dir_fn=get_session_dir,
        load_json_fn=load_json,
        save_json_fn=save_json
    )
    
    # Query database for the recorded LLM call
    db_path = os.path.join(PROJECT_ROOT, "data", "office.db")
    db_call = None
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT model, provider, input_tokens, output_tokens, cost_usd, at FROM llm_calls WHERE project_id=? AND agent_id='designer' ORDER BY id DESC LIMIT 1",
            (session_id,)
        )
        row = cur.fetchone()
        if row:
            db_call = {
                "model": row[0],
                "provider": row[1],
                "input_tokens": row[2],
                "output_tokens": row[3],
                "cost_usd": row[4],
                "at": row[5]
            }
        conn.close()

    results[name] = {
        "session_id": session_id,
        "validation": res.get("validation", {}),
        "judge": res.get("judge_verdict", {}),
        "tokens": res.get("tokens", {}),
        "db_record": db_call,
        "app_flow_path": os.path.join(get_session_dir(session_id), "docs", "app-flow.md"),
        "design_brief_path": os.path.join(get_session_dir(session_id), "docs", "design-brief.md")
    }
    
    print(f"Validation: {res.get('validation', {}).get('all_passed')} (Errors: {len(res.get('validation', {}).get('errors', []))})")
    print(f"Judge Pass: {res.get('judge_verdict', {}).get('pass')} (Score: {res.get('judge_verdict', {}).get('total')}/{res.get('judge_verdict', {}).get('max')})")
    print(f"Tokens: {res.get('tokens')}")

print("\n\n" + "="*70)
print("ALL 3 PROJECTS COMPLETED. SUMMARY:")
print("="*70)
for name, data in results.items():
    print(f"\n[{name}]")
    print(f"  Session ID: {data['session_id']}")
    print(f"  Validators: {'PASS' if data['validation'].get('all_passed') else 'FAIL'}")
    print(f"  Judge: {'PASS' if data['judge'].get('pass') else 'FAIL'} ({data['judge'].get('total')}/{data['judge'].get('max')})")
    print(f"  LLM Ledger Call: {data['db_record']}")
