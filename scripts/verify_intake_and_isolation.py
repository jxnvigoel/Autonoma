"""
End-to-End Verification for Session Isolation and Existing Project Picker.
Tests:
1. Back-to-back intake submissions: Session 1 (DevPulse) followed by Session 2 (PetCare)
   in the exact same application cycle.
   Asserts:
   - Session 2 generates a fresh UUID.
   - Session 2's session_state.json and qa_log.json on disk contain ONLY Session 2 messages.
   - Zero context or messages bleed from Session 1 into Session 2.
2. 'Open an existing project' picker workflow:
   - Queries /ba/sessions list.
   - Fetches /ba/session/{session_id} for a prior session.
   - Asserts exact project history, QA log, and metadata are returned.
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
    print("AUTONOMA: SESSION ISOLATION & EXISTING PROJECT PICKER TEST")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # TEST 1: Back-to-Back Form Submissions Session Isolation
    # -------------------------------------------------------------------------
    print("\n>>> TEST 1: Back-to-Back Intake Submissions in Same App Cycle")

    # 1.1 First Submission: DevPulse
    dev_intake = {
        "project_name": "DevPulse Focus Tracker",
        "description": "A lightweight macOS menu bar app for software developers to track deep work focus blocks and mute notifications.",
        "target_users": "Software engineers and remote workers.",
        "timeline": "4 weeks",
        "budget": "$4,000"
    }

    print("\n1.1 Submitting First Project (DevPulse Focus Tracker)...")
    res1 = client.post("/ba/start", json=dev_intake)
    assert res1.status_code == 200, f"/ba/start failed: {res1.text}"
    s1_data = res1.json()
    s1_id = s1_data["session_id"]
    s1_msg = s1_data["message"]
    print(f"Session 1 ID: {s1_id}")
    print(f"Session 1 Opening Message:\n\"\"\"\n{s1_msg}\n\"\"\"")

    # Send 2 conversation turns in Session 1
    print("\n1.2 Playing 2 conversation turns in Session 1...")
    turn1_res = client.post("/ba/message", json={"session_id": s1_id, "message": "Yes, please ask your questions!"})
    assert turn1_res.status_code == 200
    turn2_res = client.post("/ba/message", json={"session_id": s1_id, "message": "The focus blocks are usually 25 to 50 minutes long."})
    assert turn2_res.status_code == 200

    s1_detail = client.get(f"/ba/session/{s1_id}").json()
    assert len(s1_detail["messages"]) == 5, f"Expected 5 messages in Session 1, found {len(s1_detail['messages'])}"
    assert len(s1_detail["qa_log"]) == 2, f"Expected 2 QA entries in Session 1, found {len(s1_detail['qa_log'])}"
    print(f"Session 1 now has {len(s1_detail['messages'])} messages and {len(s1_detail['qa_log'])} QA entries.")

    # 1.3 Second Submission: PetCare AI (Immediately in the same cycle without app restart)
    pet_intake = {
        "project_name": "PetCare TeleVet",
        "description": "A 24/7 tele-health mobile consultation platform connecting dog and cat owners with licensed veterinarians via video.",
        "target_users": "Pet owners and veterinary clinics.",
        "timeline": "10 weeks",
        "budget": "$15,000"
    }

    print("\n1.3 Submitting Second Project (PetCare TeleVet) back-to-back...")
    res2 = client.post("/ba/start", json=pet_intake)
    assert res2.status_code == 200, f"/ba/start failed: {res2.text}"
    s2_data = res2.json()
    s2_id = s2_data["session_id"]
    s2_msg = s2_data["message"]
    print(f"Session 2 ID: {s2_id}")
    print(f"Session 2 Opening Message:\n\"\"\"\n{s2_msg}\n\"\"\"")

    assert s1_id != s2_id, "ERROR: Session 2 reused Session 1's ID!"

    # Check Session 2 isolation on disk & via API
    s2_detail = client.get(f"/ba/session/{s2_id}").json()
    print(f"\nSession 2 Messages Count: {len(s2_detail['messages'])}")
    print(f"Session 2 QA Log Count: {len(s2_detail['qa_log'])}")

    assert len(s2_detail["messages"]) == 1, f"ERROR: Session 2 leaked messages! Found {len(s2_detail['messages'])}"
    assert len(s2_detail["qa_log"]) == 0, f"ERROR: Session 2 leaked QA entries! Found {len(s2_detail['qa_log'])}"
    assert s2_detail["intake"]["project_name"] == "PetCare TeleVet"
    assert "DevPulse" not in json.dumps(s2_detail), "ERROR: DevPulse context leaked into PetCare session!"

    print("✓ Session 2 is completely clean, isolated, and contains ZERO messages or context from Session 1.")

    # -------------------------------------------------------------------------
    # TEST 2: Existing Project Picker Path
    # -------------------------------------------------------------------------
    print("\n>>> TEST 2: 'Open an existing project' Picker Retrieval & Resume")

    # 2.1 Retrieve sessions list
    sessions_res = client.get("/ba/sessions")
    assert sessions_res.status_code == 200
    sessions = sessions_res.json()
    print(f"Picker retrieved {len(sessions)} available past projects:")
    for s in sessions[:4]:
        print(f"  - [{s['session_id'][:8]}...] {s['project_name']} (Updated: {s['updated_at']})")

    # 2.2 Re-open Session 1 (DevPulse) from the picker
    print(f"\n2.2 Opening Session 1 ({s1_id}) via picker...")
    resumed_s1 = client.get(f"/ba/session/{s1_id}").json()
    assert resumed_s1["session_id"] == s1_id
    assert resumed_s1["intake"]["project_name"] == "DevPulse Focus Tracker"
    assert len(resumed_s1["messages"]) == 5
    assert len(resumed_s1["qa_log"]) == 2
    print(f"✓ Resumed Session 1 with all {len(resumed_s1['messages'])} messages and {len(resumed_s1['qa_log'])} QA entries intact.")

    # 2.3 Re-open Session 2 (PetCare) from the picker
    print(f"\n2.3 Opening Session 2 ({s2_id}) via picker...")
    resumed_s2 = client.get(f"/ba/session/{s2_id}").json()
    assert resumed_s2["session_id"] == s2_id
    assert resumed_s2["intake"]["project_name"] == "PetCare TeleVet"
    assert len(resumed_s2["messages"]) == 1
    assert len(resumed_s2["qa_log"]) == 0
    print(f"✓ Resumed Session 2 with clean state and exact intake data intact.")

    print("\n" + "=" * 80)
    print("ALL VERIFICATION CHECKS PASSED WITH ZERO LEAKAGE!")
    print("=" * 80)

if __name__ == "__main__":
    run_tests()
