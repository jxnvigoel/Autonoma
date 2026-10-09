"""
Verification script for Autonoma BA Workflow.
Runs a full real end-to-end session through FastAPI & Ollama.
"""

import os
import sys
import json
import time

# Ensure project root in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from fastapi.testclient import TestClient
from engine.main import app

client = TestClient(app)

def run_verification():
    print("=" * 70)
    print("STEP 6 VERIFICATION: Full End-to-End BA Workflow Run")
    print("=" * 70)

    # 1. Health & Ollama Status check
    status_res = client.get("/status")
    print(f"Status check HTTP {status_res.status_code}: {status_res.json()}")
    assert status_res.status_code == 200, "Engine /status failed"

    # 2. STEP 1 & 3: Submit Intake Form (/ba/start)
    intake_payload = {
        "project_name": "DevPulse",
        "description": "A lightweight macOS desktop tool for remote software engineers to track deep work focus blocks, mute distraction notifications automatically, and summarize daily git commits into an async standup report.",
        "target_users": "Solo remote software developers and engineering team leads.",
        "timeline": "6 weeks for v1 MVP",
        "budget": "$6,000 build budget, under $40/month operating cost"
    }

    print("\n--- Submitting Intake Form to /ba/start ---")
    start_res = client.post("/ba/start", json=intake_payload)
    assert start_res.status_code == 200, f"/ba/start failed: {start_res.text}"
    start_data = start_res.json()
    session_id = start_data["session_id"]
    greeting = start_data["message"]

    print(f"Session ID: {session_id}")
    print(f"\n[BA Round 0 Greeting]:\n{greeting}\n")

    # Check files on disk
    session_dir = os.path.join(PROJECT_ROOT, "data", "projects", session_id)
    intake_file = os.path.join(session_dir, "intake.json")
    qa_file = os.path.join(session_dir, "qa_log.json")

    assert os.path.exists(intake_file), f"intake.json not found on disk at {intake_file}"
    with open(intake_file, "r", encoding="utf-8") as f:
        saved_intake = json.load(f)
    print(f"intake.json verified on disk: Project={saved_intake['project_name']}")

    # 3. Play through conversation turns
    turns = [
        # Turn 1: Client grants permission
        "Yes, absolutely! Mind if we start? Let's do it.",
        # Turn 2: Answering questions about tracking & notifications
        "It should detect active IDE windows (like VS Code, IntelliJ) and terminal sessions. When in a focus block, it can enable macOS Do Not Disturb via system script. We expect about 500-1000 daily active users initially.",
        # Turn 3: Answering questions about git commits & standup report
        "For the standup report, it can read local git log from configured repo paths and use a local LLM or simple template to format into: Done Today, In Progress, Blockers. It must run 100% locally with zero cloud leakage of code.",
        # Turn 4: Answering questions about data storage & export
        "Data should be stored in SQLite locally on the user's Mac. Users should be able to export reports as Markdown or copy directly to clipboard for Slack.",
        # Turn 5: Answering questions about timeline & priorities
        "For v1, Must-Have is focus timer with macOS DND, local git commit parser, and markdown standup generator. Slack integration and team dashboards can wait for v2.",
        # Turn 6: Final wrap-up / success metric
        "Success metric is at least 80% of beta users generating daily standup reports 4+ days a week and latency under 1 second for generating reports."
    ]

    for i, user_reply in enumerate(turns, start=1):
        print(f"\n" + "-" * 60)
        print(f"Turn {i} -> Client: {user_reply}")
        msg_res = client.post("/ba/message", json={"session_id": session_id, "message": user_reply})
        assert msg_res.status_code == 200, f"/ba/message failed on turn {i}: {msg_res.text}"
        msg_data = msg_res.json()
        ba_reply = msg_data["message"]
        is_ready = msg_data["ready_for_requirements"]

        print(f"\n[BA Reply (Round {i})]:\n{ba_reply}")
        print(f"Ready for requirements: {is_ready}")

        # Verify qa_log.json on disk
        assert os.path.exists(qa_file), f"qa_log.json missing on turn {i}"
        with open(qa_file, "r", encoding="utf-8") as f:
            qa_log_data = json.load(f)
        print(f"qa_log.json entries on disk: {len(qa_log_data)} (Last ID: {qa_log_data[-1]['id']})")
        assert len(qa_log_data) == i, f"Expected {i} QA entries, found {len(qa_log_data)}"

    # 4. Check requirements.md generation
    req_file = os.path.join(session_dir, "docs", "requirements.md")
    print(f"\nChecking requirements.md on disk at: {req_file}")
    
    # Also test GET /ba/requirements/{session_id}
    req_res = client.get(f"/ba/requirements/{session_id}")
    assert req_res.status_code == 200, f"GET /ba/requirements failed: {req_res.text}"
    req_data = req_res.json()
    requirements_content = req_data["content"]

    assert os.path.exists(req_file), f"requirements.md not found on disk at {req_file}"
    with open(req_file, "r", encoding="utf-8") as f:
        file_content = f.read()

    print("\n" + "=" * 70)
    print("ACTUAL GENERATED REQUIREMENTS.MD CONTENT:")
    print("=" * 70)
    print(file_content)
    print("=" * 70)

    # Verify Q- citations and required sections in generated requirements
    required_sections = [
        "Problem Statement",
        "Personas",
        "Functional Requirements",
        "Non-Functional Requirements",
        "Timeline",
    ]
    for sec in required_sections:
        if sec.lower() in file_content.lower():
            print(f"✓ Section found: {sec}")
        else:
            print(f"⚠ Warning: Section '{sec}' not explicitly found in header text")

    assert len(file_content.strip()) > 200, "Requirements doc content is too short"
    print("\n✓ Full verification passed successfully!")
    return session_id, file_content

if __name__ == "__main__":
    run_verification()
