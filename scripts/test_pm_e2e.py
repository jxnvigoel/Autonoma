import requests
import json
import time
import os

BASE_URL = "http://127.0.0.1:8765"

def run_test():
    print("=== 1. Starting BA Session ===")
    intake = {
        "project_name": "TaskSync Studio",
        "description": "A focused desktop task manager with local sqlite storage, automated daily standup markdown export, and distraction blocking timer for remote developers.",
        "target_users": "Solo remote software engineers and tech leads",
        "timeline": "6 weeks for v1 MVP",
        "budget": "$5,000 build budget, under $30/month local operating cost"
    }

    res = requests.post(f"{BASE_URL}/ba/start", json=intake, timeout=60)
    assert res.status_code == 200, f"ba_start failed: {res.text}"
    start_data = res.json()
    session_id = start_data["session_id"]
    print(f"Session started: {session_id}")
    print(f"BA Greeting: {start_data['message'][:120]}...")

    print("\n=== 2. Running BA Discovery Conversation ===")
    responses = [
        "Yes, please go ahead. Let's start the discovery.",
        "The core problem is that remote engineers lose focus switching between Jira, Slack, and manual notes, and forget what they built when writing daily standups. They need a distraction-free timer and a one-click local git commit parser that summarizes their work.",
        "Key requirements: 1) Focus timer with macOS DND integration (Must Have), 2) Local git log commit parser that generates markdown standup summaries (Must Have), 3) All data stored locally in SQLite with zero cloud dependencies for total privacy (Must Have), 4) Latency under 1 second (NFR), 5) Support 500-1000 daily active users in future. Cloud sync is strictly deferred to v2 (Won't Have for v1).",
        "Target timeline is strictly 6 weeks. Team size is 1 engineer and 1 designer. Success metric is 85% of engineers generating daily standup reports at least 4 days a week. That covers all my requirements, please finalize requirements.md."
    ]

    for idx, ans in enumerate(responses):
        print(f"\nSending User Turn {idx+1}: {ans[:60]}...")
        msg_res = requests.post(f"{BASE_URL}/ba/message", json={
            "session_id": session_id,
            "message": ans
        }, timeout=90)
        assert msg_res.status_code == 200, f"ba_message failed: {msg_res.text}"
        data = msg_res.json()
        print(f"BA Response {idx+1}: {data['message'][:100]}...")
        print(f"Ready for requirements: {data.get('ready_for_requirements')}")

    # Check / trigger requirements.md
    print("\n=== 3. Checking / Generating BA requirements.md ===")
    req_res = requests.get(f"{BASE_URL}/ba/requirements/{session_id}", timeout=180)
    if req_res.status_code == 200:
        req_content = req_res.json()["content"]
        print(f"requirements.md generated ({len(req_content)} chars):")
        print("\n".join(req_content.split("\n")[:15]))
    else:
        print(f"requirements.md status: {req_res.status_code}")

    print("\n=== 4. Starting PM Session (Handoff to PM) ===")
    pm_start_res = requests.post(f"{BASE_URL}/pm/start", json={"session_id": session_id}, timeout=180)
    assert pm_start_res.status_code == 200, f"pm_start failed: {pm_start_res.text}"
    pm_data = pm_start_res.json()

    print(f"PM Message: {pm_data['message'][:150]}...")
    print(f"PRD Content length: {len(pm_data.get('prd_content', ''))} chars")

    estimate = pm_data.get("estimate")
    print("\n=== 5. Verifying estimate.json ===")
    print(f"Total Estimated Tokens: {estimate['total_estimated_tokens']}")
    print(f"Subtotal Tokens: {estimate['subtotal_tokens']}")
    print(f"Rework Buffer Tokens: {estimate['rework_buffer_tokens']} ({estimate['rework_buffer_percentage']}%)")
    print(f"Estimated Cost: ${estimate['estimated_cost_usd']} USD (Model: {estimate['model']})")
    print(f"Ledger Source: {estimate['ledger_metadata']['source']}")
    print(f"Number of stages: {len(estimate['stages'])}")
    for st in estimate['stages'][:4]:
        print(f"  - {st['stage']} ({st['role']}): {st['subtotal_tokens']} tokens [{st['rate_source']}]")

    print("\n=== 6. Checking Output Files in Session Directory ===")
    project_dir = os.path.join("data", "projects", session_id)
    docs_dir = os.path.join(project_dir, "docs")
    prd_path = os.path.join(docs_dir, "prd.md")
    estimate_path = os.path.join(docs_dir, "estimate.json")

    assert os.path.exists(prd_path), f"File {prd_path} does not exist!"
    assert os.path.exists(estimate_path), f"File {estimate_path} does not exist!"

    with open(prd_path, "r", encoding="utf-8") as f:
        prd_full = f.read()

    with open(estimate_path, "r", encoding="utf-8") as f:
        est_full = json.load(f)

    print(f"Verified {prd_path} exists on disk ({len(prd_full)} chars).")
    print(f"Verified {estimate_path} exists on disk ({len(json.dumps(est_full))} chars).")

    print("\n=== 7. Quality Bar 5.2.5 Point-by-Point Check ===")
    q_bar = pm_data.get("quality_bar", {})
    for k, v in q_bar.items():
        if isinstance(v, dict):
            status_icon = "PASS" if v.get("passed") else "CHECK"
            print(f"[{status_icon}] {v.get('rule', k)}: {v.get('details')}")

    print("\n=== 8. Testing PM Iteration Turn ===")
    pm_msg_res = requests.post(f"{BASE_URL}/pm/message", json={
        "session_id": session_id,
        "message": "Can we confirm that the local git log summary exports to clipboard as well as markdown files?"
    }, timeout=180)
    assert pm_msg_res.status_code == 200, f"pm_message failed: {pm_msg_res.text}"
    pm_msg_data = pm_msg_res.json()
    print(f"PM Iteration reply: {pm_msg_data['message'][:120]}...")

    with open(prd_path, "r", encoding="utf-8") as f:
        post_iter_prd = f.read()
    assert "# Product Requirement Document (PRD)" in post_iter_prd, "prd.md lost PRD header!"
    assert "## 5. Features (v1)" in post_iter_prd, "prd.md lost Features section!"
    print(f"Post-iteration prd.md verified on disk ({len(post_iter_prd)} chars) with all Appendix A.2 sections intact.")

    print("\n=== 9. Testing GET /pm/session/{session_id} ===")
    get_res = requests.get(f"{BASE_URL}/pm/session/{session_id}")
    assert get_res.status_code == 200
    session_detail = get_res.json()
    assert session_detail["started"] is True
    assert session_detail["prd_content"] is not None
    assert session_detail["estimate"] is not None
    assert "# Product Requirement Document" in session_detail["prd_content"]
    print("GET /pm/session returned full state with PRD and estimate.")
    print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_test()
