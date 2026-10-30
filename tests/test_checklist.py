"""Company checklist: statuses come from the project's records, owners from the Scrum Master's assignments."""

import os
import sys
import json
import shutil
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine"))

from fastapi.testclient import TestClient

import checklist
import main

PRD = """## 5. Features (v1)

### Summary

| ID | Feature | Description | Priority | Source |
| --- | --- | --- | --- | --- |
| F-001 | Sign in | ... | Must | [FR-001] |
| F-002 | Add task | ... | Must | [FR-002] |
| F-003 | Export | ... | Should | [FR-003] |

### Feature F-001: Sign in

| AC | Criterion |
| --- | --- |
| AC-001 | Given a user, when they sign in, then they see their tasks. |

### Feature F-002: Add task

| AC | Criterion |
| --- | --- |
| AC-002 | Given a title, when saved, then it is listed. |
| AC-003 | (unhappy path) Given an empty title, when saved, then it is refused. |

### Feature F-003: Export

## 6. NFR
"""

OPENAPI = """openapi: 3.0.0
info: {title: t, version: '1'}
paths:
  /login: {post: {summary: '[F-001] Sign in [API-001]'}}
  /tasks: {post: {summary: '[F-002] Add task [API-002]'}}
"""


class ChecklistTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.p = os.path.join(self.tmp, "p1")
        os.makedirs(os.path.join(self.p, "docs"))
        self.doc("prd.md", PRD)
        self.doc("openapi.yaml", OPENAPI)
        self.doc("requirements.md", "# Requirements")
        self.json("pm_state.json", {"judge_verdict": {"pass": True, "total": 24, "max": 24}})
        self.json("session_state.json", {"gate1_approved": True})
        self.json("docs/backlog.json", {"stories": [
            {"id": "ST-001", "title": "Sign in", "role": "backend", "owner": "p1_backend-1", "refs": {"features": ["F-001"]}},
            {"id": "ST-002", "title": "Add task", "role": "frontend", "owner": "p1_frontend-1", "refs": {"features": ["F-002"]}},
        ]})
        self.json("build_state.json", {"status": "running", "stories": {
            "ST-001": {"status": "done", "ac_coverage": {"covered": ["AC-001"], "uncovered": [], "failing_acs": [], "passed": True}},
            "ST-002": {"status": "fixing", "ac_coverage": {"covered": ["AC-002", "AC-003"], "uncovered": [],
                                                           "failing_acs": ["AC-003"], "passed": False}},
        }})
        agents = {"p1_backend-1": {"id": "p1_backend-1", "name": "Arjun", "role": "backend"},
                  "p1_frontend-1": {"id": "p1_frontend-1", "name": "Meera", "role": "frontend"}}
        self.agents = mock.patch.object(checklist, "_agents", return_value=agents)
        self.agents.start()

    def tearDown(self):
        self.agents.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def doc(self, name, text):
        with open(os.path.join(self.p, "docs", name), "w") as f:
            f.write(text)

    def json(self, name, data):
        with open(os.path.join(self.p, name), "w") as f:
            json.dump(data, f)

    def test_statuses_and_owners_follow_the_records(self):
        c = checklist.build_checklist("p1", self.tmp)
        stages = {s["id"]: s["status"] for s in c["stages"]}
        self.assertEqual((stages["CHK-01"], stages["CHK-02"], stages["CHK-03"], stages["CHK-09"], stages["CHK-11"]),
                         ("done", "done", "done", "done", "in_progress"))
        f1, f2, f3 = c["features"]
        self.assertEqual((f1["id"], f1["status"], [o["name"] for o in f1["owners"]]), ("F-001", "done", ["Arjun"]))
        self.assertEqual([a["status"] for a in f1["acceptance_tests"]], ["done"])
        # AC-003's test fails; AC-002 is only "done" once its story passes QA (the fix could still break it).
        self.assertEqual({a["id"]: a["status"] for a in f2["acceptance_tests"]}, {"AC-002": "in_progress", "AC-003": "needs_attention"})
        self.assertEqual(next(i for i in f2["items"] if i["id"] == "F-002-build")["status"], "in_progress")
        # Export has no endpoint, no story and no owner: shown as to do, never as done.
        self.assertEqual((f3["status"], f3["owners"], [i["status"] for i in f3["items"]]), ("todo", [], ["todo"] * 4))
        self.assertEqual([(a["name"], a["done"], len(a["stories"])) for a in c["agents"]], [("Arjun", 1, 1), ("Meera", 0, 1)])
        self.assertGreater(c["progress"]["needs_attention"], 0)

    def test_finishing_work_ticks_the_checklist(self):
        before = checklist.build_checklist("p1", self.tmp)["progress"]["done"]
        self.json("build_state.json", {"status": "complete", "final_regression": {"ok": True}, "stories": {
            "ST-001": {"status": "done", "ac_coverage": {"covered": ["AC-001"], "passed": True}},
            "ST-002": {"status": "done", "ac_coverage": {"covered": ["AC-002", "AC-003"], "failing_acs": [], "passed": True}},
        }})
        after = checklist.build_checklist("p1", self.tmp)
        self.assertGreater(after["progress"]["done"], before)
        self.assertEqual(after["features"][1]["status"], "done")
        self.assertEqual({s["id"]: s["status"] for s in after["stages"]}["CHK-12"], "done")

    def test_reads_older_prd_layouts(self):
        older = ("## 5. Features\n\n### F-001: Sign in**\n- **Priority**: Must-have\n"
                 "- AC-001: Given a user, when they log in, then they get a token.\n"
                 "- **AC-002**: (unhappy path) Given a wrong password, then 401.\n\n"
                 "### F-002 \u2014 Export\n| ID | Criterion |\n|---|---|\n| AC-003 | Given data, then a CSV. |\n\n## 6. NFR\n")
        feats = checklist.parse_prd_features(older)
        self.assertEqual([(f["id"], f["name"], f["priority"], [a["id"] for a in f["acs"]]) for f in feats],
                         [("F-001", "Sign in", "Must-have", ["AC-001", "AC-002"]), ("F-002", "Export", "", ["AC-003"])])

    def test_fresh_install_lists_no_agents_instead_of_crashing(self):
        import skill_registry
        with mock.patch.object(skill_registry, "DEFAULT_DB_PATH", os.path.join(self.tmp, "fresh.db")), \
                mock.patch.object(main, "DATA_PROJECTS_DIR", self.tmp):
            r = TestClient(main.app).get("/recruiter/agents/p1")
        self.assertEqual((r.status_code, r.json()["agents"]), (200, []))

    def test_hr_plan_is_served_in_the_screen_shape(self):
        self.json("docs/team-plan.json", {"planned_by": "hr", "timeline_weeks": 4, "seats": [
            {"id": "ROLE-01", "role": "backend", "count": 2, "from_week": 1, "to_week": 3, "why": "x", "refs": ["F-001"]}]})
        with mock.patch.object(main, "DATA_PROJECTS_DIR", self.tmp):
            v = TestClient(main.app).get("/hr/team-plan/p1").json()
        self.assertEqual((v["total_weeks"], v["total_headcount_weeks"], v["features_covered"]), (4, 6, ["F-001"]))
        self.assertEqual((v["requisitions"][0]["seat_id"], v["requisitions"][0]["start_week"], v["requisitions"][0]["end_week"]),
                         ("ROLE-01", 1, 3))
        self.assertEqual(v["unstaffed_must_haves"], ["F-002"])  # F-002 is a Must in the PRD and has no seat
        self.assertIsNone(v["headcount_budget_cap"])  # not invented

    def test_backlog_route_reads_the_configured_projects_folder(self):
        # It used a path relative to the current folder, so the Scrum screen stayed empty when the engine
        # was started from anywhere but the repo root.
        with mock.patch.object(main, "DATA_PROJECTS_DIR", self.tmp):
            r = TestClient(main.app).get("/scrum/backlog/p1").json()
        self.assertEqual([st["id"] for st in r["stories"]], ["ST-001", "ST-002"])

    def test_architect_draft_is_not_hr_plan(self):
        self.json("docs/team-plan.json", {"seats": [{"id": "ROLE-01"}]})  # the Architect's draft
        self.assertFalse(checklist.hr_planned(os.path.join(self.p, "docs")))
        self.assertEqual({s["id"]: s["status"] for s in checklist.build_checklist("p1", self.tmp)["stages"]}["CHK-06"], "todo")
        with mock.patch.object(main, "DATA_PROJECTS_DIR", self.tmp):
            c = TestClient(main.app)
            self.assertEqual(c.get("/hr/team-plan/p1").status_code, 404)
            self.assertEqual(c.post("/recruiter/hire/p1").status_code, 409)
            self.assertEqual(c.post("/gate2/approve", json={"session_id": "p1"}).status_code, 409)  # nothing hired yet
            self.assertEqual(c.get("/checklist/p1").status_code, 200)
        self.json("docs/team-plan.json", {"seats": [{"id": "ROLE-01"}], "planned_by": "hr"})
        self.assertTrue(checklist.hr_planned(os.path.join(self.p, "docs")))


if __name__ == "__main__":
    unittest.main()
