"""PM workstation and Gate 1 as the UI drives them: load PM, chat, approve unlocks Stage 3, send back rewrites."""

import os
import sys
import json
import time
import shutil
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine"))

from fastapi.testclient import TestClient

import jobs
import llm_client
import main

SID = "proj-1"


class PmGate1FlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.proj = os.path.join(self.tmp, SID)
        os.makedirs(os.path.join(self.proj, "docs"))
        self.write("intake.json", {"project_name": "TaskNest"})
        self.write("qa_log.json", [{"id": "Q-001", "question": "Who uses it?", "answer": "Office staff", "round": 1,
                                    "timestamp": "2026-10-27T10:00:00Z"}])
        with open(os.path.join(self.proj, "docs", "requirements.md"), "w") as f:
            f.write("# Requirements: TaskNest\n- FR-001 staff log in [Q-001]\n")
        self.patches = [mock.patch.object(main, "DATA_PROJECTS_DIR", self.tmp),
                        mock.patch.object(jobs, "DATA_PROJECTS_DIR", self.tmp)]
        for p in self.patches:
            p.start()
        self.client = TestClient(main.app)
        self.real_pm = jobs._registry.get("pm")
        self.pm_runs = []
        self.release = threading.Event()

        def fake_pm(sid):
            self.pm_runs.append(sid)
            self.release.wait(5)
            with open(os.path.join(self.proj, "docs", "prd.md"), "w") as f:
                f.write(f"# PRD v{len(self.pm_runs)}\nF-001 Login [FR-001]\n")
            self.write("pm_state.json", {"round": 1, "messages": [{"id": "m", "role": "assistant", "content": "Drafted"}],
                                         "judge_verdict": {"pass": True, "total": 24, "max": 24}})
            return {"session_id": sid, "message": "Drafted", "prd_content": "# PRD"}

        jobs.register("pm", fake_pm)

    def tearDown(self):
        self.release.set()
        for t in list(jobs._threads.values()):
            t.join(2)
        jobs._threads.clear()
        if self.real_pm:
            jobs.register("pm", self.real_pm)
        llm_client.default_llm_client.set_fake_responder(None)
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, name, data):
        with open(os.path.join(self.proj, name), "w") as f:
            json.dump(data, f)

    def wait_job(self, want="done"):
        for _ in range(200):
            st = self.client.get(f"/jobs/pm/{SID}").json()
            if st["status"] == want:
                return st
            time.sleep(0.02)
        self.fail(f"pm job never reached {want}: {st}")

    def test_pm_session_loads_before_and_after_the_prd(self):
        before = self.client.get(f"/pm/session/{SID}")
        self.assertEqual(before.status_code, 200)  # was a 404 the UI read as "PM not started"
        self.assertEqual((before.json()["started"], before.json()["can_start"]), (False, True))
        self.client.post(f"/jobs/pm/{SID}")
        self.release.set()
        self.wait_job()
        after = self.client.get(f"/pm/session/{SID}").json()
        self.assertEqual((after["started"], after["status"], after["can_start"]), (True, "done", False))
        self.assertIn("# PRD v1", after["prd_content"])
        self.assertEqual(self.client.get("/pm/session/no-such-project").status_code, 404)

    def test_pm_chat_answers_and_is_saved(self):
        self.assertEqual(self.client.post("/pm/message", json={"session_id": SID, "message": "hi"}).status_code, 409)
        self.client.post(f"/jobs/pm/{SID}")
        self.release.set()
        self.wait_job()
        llm_client.default_llm_client.set_fake_responder(lambda **kw: "Login is F-001 [FR-001].")
        r = self.client.post("/pm/message", json={"session_id": SID, "message": "What does login cover?"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["message"], "Login is F-001 [FR-001].")
        msgs = self.client.get(f"/pm/session/{SID}").json()["messages"]
        self.assertEqual([m["role"] for m in msgs[-2:]], ["user", "assistant"])

    def test_gate1_approval_unlocks_architect_and_designer(self):
        self.client.post(f"/jobs/pm/{SID}")
        self.release.set()
        self.wait_job()
        self.assertFalse(self.client.get(f"/gate1/status/{SID}").json()["gate1"]["approved"])
        r = self.client.post("/gate1/approve", json={"session_id": SID, "client_notes": "ok"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(self.client.get(f"/gate1/status/{SID}").json()["gate1"]["approved"])
        office = self.client.get(f"/office/status/{SID}").json()
        self.assertTrue(office["gate1"]["approved"])
        self.assertEqual(office["agents"]["architect"]["status"], "waiting-on-you")
        self.assertTrue(office["agents"]["designer"]["can_start"])

    def test_send_back_records_feedback_keeps_old_prd_and_rewrites(self):
        self.client.post(f"/jobs/pm/{SID}")
        self.release.set()
        self.wait_job()
        self.release.clear()
        r = self.client.post("/gate1/request-changes", json={"session_id": SID, "feedback": "Managers must approve leave."})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual((body["routed_qid"], body["previous_version"]), ("Q-002", "docs/prd.v1.md"))
        qa = json.load(open(os.path.join(self.proj, "qa_log.json")))
        self.assertEqual((qa[-1]["id"], qa[-1]["answer"], qa[-1]["source"]), ("Q-002", "Managers must approve leave.", "gate1"))
        self.assertTrue(os.path.exists(os.path.join(self.proj, "docs", "prd.v1.md")))
        self.assertEqual(self.client.get(f"/gate1/status/{SID}").json()["gate1"]["status"], "changes_requested")
        # The PM rewrite is running; a second send-back while it runs is refused.
        self.assertEqual(self.client.get(f"/office/status/{SID}").json()["running_jobs"], ["pm"])
        self.assertEqual(self.client.post("/gate1/request-changes",
                                          json={"session_id": SID, "feedback": "again"}).status_code, 409)
        self.release.set()
        self.wait_job()
        self.assertEqual(len(self.pm_runs), 2)
        self.assertIn("# PRD v2", open(os.path.join(self.proj, "docs", "prd.md")).read())
        self.assertEqual(self.client.post("/gate1/request-changes", json={"session_id": SID, "feedback": " "}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
