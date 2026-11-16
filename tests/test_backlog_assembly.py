"""Scrum Master backlog assembled per feature, thinking-model answers, and the Tech Lead's verdict parsing."""
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine"))

import scrum  # noqa: E402
import readiness  # noqa: E402
from llm_client import strip_reasoning  # noqa: E402
from validators import (validate_backlog_schema, validate_backlog_points, validate_backlog_dependency_cycles,  # noqa: E402
                        validate_backlog_walking_skeleton, validate_backlog_must_have_ac_coverage,
                        validate_backlog_owners_in_roster, validate_backlog_refs_exist)

PRD = """# PRD
## 5. Features (v1)
### Feature F-001: Sign up
- **Priority**: Must Have (MoSCoW)
| AC-001 | Given a new user, when they register, then the account is created. |
| AC-002 | (unhappy path) Given a used email, when they register, then an error shows. |
### Feature F-002: Add task
- **Priority**: Must Have (MoSCoW)
| AC-003 | Given a signed-in user, when they add a task, then it is stored. |
## 6. Non-functional requirements
"""
ARCH = """## 7. Data model
| TBL-01 | `users` | id |
| TBL-02 | `tasks` | id |
| Feature | Endpoints | Tables |
|---|---|---|
| [F-001] | API-001 | TBL-01 `users` |
| [F-002] | API-002 | TBL-02 `tasks` |
## 8. Integrations
"""
OPENAPI = """paths:
  /users:
    post:
      summary: Register [F-001] [API-001]
  /tasks:
    post:
      summary: Add task [F-002] [API-002]
"""
ROSTER = [{"id": "p_backend-1", "role": "backend"}, {"id": "p_frontend-1", "role": "frontend"}]


def _check_all(backlog):
    errors = []
    for check in (validate_backlog_schema, validate_backlog_points, validate_backlog_dependency_cycles,
                  validate_backlog_walking_skeleton):
        errors += check(backlog)[1]
    errors += validate_backlog_must_have_ac_coverage(backlog, PRD)[1]
    errors += validate_backlog_owners_in_roster(backlog, ROSTER)[1]
    errors += validate_backlog_refs_exist(backlog, PRD, ARCH + OPENAPI)[1]
    return errors


class StripReasoningTest(unittest.TestCase):
    def test_think_block_removed(self):
        self.assertEqual(strip_reasoning('<think>{"x": 1}</think>\n{"stories": []}'), '{"stories": []}')

    def test_unclosed_think_leaves_nothing(self):
        self.assertEqual(strip_reasoning("<think>still thinking"), "")

    def test_missing_open_tag(self):
        self.assertEqual(strip_reasoning("reasoning</think>answer"), "answer")

    def test_plain_text_untouched(self):
        self.assertEqual(strip_reasoning("plain"), "plain")


class BacklogAssemblyTest(unittest.TestCase):
    def _build(self, answers):
        it = iter(answers)
        with mock.patch.object(scrum, "query_llm_with_meta", side_effect=lambda **k: (next(it), {})):
            return scrum.build_backlog("p", PRD, ARCH, OPENAPI, ROSTER)

    def test_good_answers_pass_every_check(self):
        good = lambda f, ac, api: ("<think>planning {</think>```json\n" + json.dumps({"stories": [
            {"title": f"{f} API", "role": "backend", "points": 8, "ac": ac + ["AC-999"], "api": [api, "API-777"],
             "after": []},
            {"title": f"{f} screen", "role": "ui", "points": 2, "after": [0, 5]}]}) + "\n```")
        backlog, notes = self._build([good("F-001", ["AC-001"], "API-001"), good("F-002", ["AC-003"], "API-002")])
        self.assertEqual(_check_all(backlog), [])
        self.assertEqual(notes, [])
        ids = [s["id"] for s in backlog["stories"]]
        self.assertEqual(ids, ["ST-001", "ST-002", "ST-003", "ST-004", "ST-005"])
        st2 = backlog["stories"][1]
        self.assertEqual(st2["points"], 5)                       # 8 snapped to the largest allowed size
        self.assertEqual(sorted(st2["refs"]["ac"]), ["AC-001", "AC-002"])  # invented id dropped, missing AC added
        self.assertEqual(st2["refs"]["api"], ["API-001"])
        self.assertEqual(backlog["stories"][2]["role"], "frontend")
        self.assertEqual(backlog["stories"][2]["depends_on"], ["ST-001", "ST-002"])  # out-of-range 'after' dropped

    def test_unreadable_answers_fall_back_to_prd_shaped_stories(self):
        backlog, notes = self._build(["no json here", "<think>never finished", "sorry", "{}"])
        self.assertEqual(_check_all(backlog), [])
        self.assertEqual(len(notes), 2)
        self.assertTrue(all(s["refs"]["ac"] for s in backlog["stories"][1:]))

    def test_failed_call_falls_back_instead_of_crashing(self):
        with mock.patch.object(scrum, "query_llm_with_meta", side_effect=RuntimeError("quota")):
            backlog, notes = scrum.build_backlog("p", PRD, ARCH, OPENAPI, ROSTER)
        self.assertEqual(_check_all(backlog), [])
        self.assertEqual(len(notes), 2)

    def test_feature_with_only_screens_gets_a_backend_story_first(self):
        ui_only = json.dumps({"stories": [{"title": "Form", "role": "frontend", "points": 2, "ac": ["AC-001"]},
                                          {"title": "Error", "role": "frontend", "points": 1, "ac": ["AC-002"],
                                           "after": [0]}]})
        ok = json.dumps({"stories": [{"title": "Add", "role": "backend", "points": 3, "ac": ["AC-003"]}]})
        backlog, _ = self._build([ui_only, ok])
        self.assertEqual(_check_all(backlog), [])
        f1 = [s for s in backlog["stories"] if s["refs"]["features"] == ["F-001"]]
        self.assertEqual([s["id"] for s in f1], ["ST-002", "ST-003", "ST-004"])
        self.assertEqual(f1[0]["role"], "backend")
        self.assertEqual(f1[0]["refs"]["api"], ["API-001"])
        self.assertEqual(f1[1]["depends_on"], ["ST-001", "ST-002"])
        self.assertEqual(f1[2]["depends_on"], ["ST-001", "ST-003", "ST-002"])

    def test_must_have_with_space_is_recognised(self):
        self.assertTrue(all(f["must_have"] for f in scrum.prd_features(PRD)))


class VerdictParseTest(unittest.TestCase):
    def test_json_block(self):
        v, gaps, _ = readiness._parse_verdict('text\n```json\n{"verdict": "not_ready", "gaps": ["AC-3 unclear"]}\n```')
        self.assertEqual((v, gaps), ("not_ready", ["AC-3 unclear"]))

    def test_verdict_line(self):
        self.assertEqual(readiness._parse_verdict("## 7. Verdict\n**Verdict: ready**")[0], "ready")

    def test_no_verdict(self):
        self.assertIsNone(readiness._parse_verdict("nothing decided")[0])


if __name__ == "__main__":
    unittest.main()
