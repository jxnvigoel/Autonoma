"""
Verification script for BA Workflow Bug Fixes (Bug 1 & Bug 2).
Tests:
1. Dynamic, project-specific BA opening replies for different intake submissions.
2. /ba/sessions list retrieval with project metadata and timestamps.
3. /ba/session/{session_id} isolation (each session has distinct qa_log and messages).
4. No disk overwriting when creating multiple distinct sessions.
"""

import os
import sys
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from fastapi.testclient import TestClient
from engine.main import app

client = TestClient(app)

def run_tests():
    print("=" * 80)
    print("AUTONOMA BA WORKFLOW: BUG 1 & BUG 2 TEST SUITE")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # TEST 1: BUG 1 - Dynamic Intake Opening & Follow-up Messages
    # -------------------------------------------------------------------------
    print("\n>>> TEST 1: Verifying Dynamic, Project-Specific BA Responses (Bug 1)")

    # Intake 1: Recipe App
    recipe_intake = {
        "project_name": "ChefMate Pantry AI",
        "description": "A smart home cooking and meal planning assistant that analyzes available pantry ingredients and generates personalized healthy recipes with zero food waste.",
        "target_users": "Home cooks, college students, and busy families.",
        "timeline": "4 weeks for MVP",
        "budget": "$3,500 budget, under $30/month server costs"
    }

    print("\n1.1 Submitting Project 1 (ChefMate Pantry AI)...")
    res1 = client.post("/ba/start", json=recipe_intake)
    assert res1.status_code == 200, f"Project 1 /ba/start failed: {res1.text}"
    s1_data = res1.json()
    s1_id = s1_data["session_id"]
    s1_msg = s1_data["message"]

    print(f"Session ID 1: {s1_id}")
    print(f"BA Opening Message for ChefMate:\n\"\"\"\n{s1_msg}\n\"\"\"")

    # Intake 2: Gym Booking App
    gym_intake = {
        "project_name": "IronPulse Gym Manager",
        "description": "A high-capacity boutique gym scheduling and member check-in platform with dynamic class capacity limits, QR code turnstile access, and trainer payouts.",
        "target_users": "Gym owners, personal trainers, and gym members.",
        "timeline": "8 weeks for MVP",
        "budget": "$12,000 build budget, under $150/month operating cost"
    }

    print("\n1.2 Submitting Project 2 (IronPulse Gym Manager)...")
    res2 = client.post("/ba/start", json=gym_intake)
    assert res2.status_code == 200, f"Project 2 /ba/start failed: {res2.text}"
    s2_data = res2.json()
    s2_id = s2_data["session_id"]
    s2_msg = s2_data["message"]

    print(f"Session ID 2: {s2_id}")
    print(f"BA Opening Message for IronPulse:\n\"\"\"\n{s2_msg}\n\"\"\"")

    # Assert distinct opening messages
    assert s1_msg != s2_msg, "ERROR: BA opening messages are identical!"
    assert ("ChefMate" in s1_msg or "cooking" in s1_msg or "recipe" in s1_msg or "pantry" in s1_msg), "Project 1 greeting did not reference project context!"
    assert ("IronPulse" in s2_msg or "gym" in s2_msg or "booking" in s2_msg or "class" in s2_msg), "Project 2 greeting did not reference project context!"
    print("✓ Both opening messages are dynamic, distinct, and project-aware.")

    # 1.3 Test Follow-up Question turns
    print("\n1.3 Submitting Client agreement to both sessions...")
    m1_res = client.post("/ba/message", json={"session_id": s1_id, "message": "Yes, let's get started!"})
    assert m1_res.status_code == 200
    m1_reply = m1_res.json()["message"]
    print(f"ChefMate Follow-up (Round 1):\n\"\"\"\n{m1_reply}\n\"\"\"")

    m2_res = client.post("/ba/message", json={"session_id": s2_id, "message": "Sure, let's begin."})
    assert m2_res.status_code == 200
    m2_reply = m2_res.json()["message"]
    print(f"IronPulse Follow-up (Round 1):\n\"\"\"\n{m2_reply}\n\"\"\"")

    assert m1_reply != m2_reply, "ERROR: Follow-up questions are identical!"
    print("✓ Follow-up questions are completely distinct and tailored to each domain.")

    # -------------------------------------------------------------------------
    # TEST 2: BUG 2 - Past Conversations Sidebar & Endpoints
    # -------------------------------------------------------------------------
    print("\n>>> TEST 2: Verifying Past Conversations Sidebar API (Bug 2)")

    # Intake 3: Developer Tool
    dev_intake = {
        "project_name": "GitSnap CLI",
        "description": "A developer CLI tool that creates instant branch visualizer diagrams and formats automated pull request summaries from local commits.",
        "target_users": "Software engineers and DevOps leads.",
        "timeline": "3 weeks",
        "budget": "$2,000"
    }

    print("\n2.1 Submitting Project 3 (GitSnap CLI)...")
    res3 = client.post("/ba/start", json=dev_intake)
    assert res3.status_code == 200
    s3_id = res3.json()["session_id"]
    print(f"Session ID 3: {s3_id}")

    # Test GET /ba/sessions
    print("\n2.2 Querying GET /ba/sessions...")
    sessions_res = client.get("/ba/sessions")
    assert sessions_res.status_code == 200, f"GET /ba/sessions failed: {sessions_res.text}"
    sessions_list = sessions_res.json()
    print(f"Retrieved {len(sessions_list)} sessions:")
    for idx, s in enumerate(sessions_list[:5], 1):
        print(f"  {idx}. [{s['session_id'][:8]}...] {s['project_name']} (Updated: {s['updated_at']})")

    session_ids_in_list = [s["session_id"] for s in sessions_list]
    assert s1_id in session_ids_in_list, f"Session 1 ({s1_id}) missing from /ba/sessions"
    assert s2_id in session_ids_in_list, f"Session 2 ({s2_id}) missing from /ba/sessions"
    assert s3_id in session_ids_in_list, f"Session 3 ({s3_id}) missing from /ba/sessions"
    print("✓ All created sessions appear in the sessions list with distinct names & metadata.")

    # Test GET /ba/session/{session_id} for session state isolation
    print("\n2.3 Verifying conversation history isolation between sessions...")
    d1 = client.get(f"/ba/session/{s1_id}").json()
    d2 = client.get(f"/ba/session/{s2_id}").json()
    d3 = client.get(f"/ba/session/{s3_id}").json()

    assert d1["intake"]["project_name"] == "ChefMate Pantry AI"
    assert d2["intake"]["project_name"] == "IronPulse Gym Manager"
    assert d3["intake"]["project_name"] == "GitSnap CLI"

    assert len(d1["messages"]) == 3  # Assistant intro, user agreement, assistant round 1
    assert len(d2["messages"]) == 3  # Assistant intro, user agreement, assistant round 1
    assert len(d3["messages"]) == 1  # Assistant intro only

    assert d1["qa_log"][0]["answer"] == "Yes, let's get started!"
    assert d2["qa_log"][0]["answer"] == "Sure, let's begin."
    assert len(d3["qa_log"]) == 0

    print("✓ No conversation bleeding: each session preserves its own isolated qa_log and messages.")

    # Check files on disk
    print("\n2.4 Verifying on-disk session folder integrity...")
    data_dir = os.path.join(PROJECT_ROOT, "data", "projects")
    for sid, name in [(s1_id, "ChefMate"), (s2_id, "IronPulse"), (s3_id, "GitSnap")]:
        sdir = os.path.join(data_dir, sid)
        assert os.path.exists(os.path.join(sdir, "intake.json")), f"intake.json missing for {name}"
        assert os.path.exists(os.path.join(sdir, "session_state.json")), f"session_state.json missing for {name}"
        assert os.path.exists(os.path.join(sdir, "qa_log.json")), f"qa_log.json missing for {name}"
        print(f"  ✓ {name} ({sid[:8]}...) verified intact on disk.")

    print("\n" + "=" * 80)
    print("ALL TESTS PASSED SUCCESSFULLY! Both Bug 1 and Bug 2 are fully verified.")
    print("=" * 80)

if __name__ == "__main__":
    run_tests()
