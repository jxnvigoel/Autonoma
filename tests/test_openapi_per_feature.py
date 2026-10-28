"""OpenAPI is written one feature at a time and assembled by code (Handbook 7.2.4 step 6)."""

import os
import sys
import shutil
import tempfile
import unittest
from unittest import mock

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine"))

import architect

FRAG_F1 = """/api/v1/auth/login:
  post:
    summary: Sign in [F-001] [API-001]
    operationId: login
    security: []
    responses:
      '200': {description: ok}
      '401': {$ref: '#/components/responses/Problem'}
"""
FRAG_F2_DUP = """/api/v1/auth/login:
  post:
    summary: duplicate [F-002]
    responses: {'200': {description: ok}, '400': {description: bad}}
"""
FRAG_F2 = """/api/v1/todos:
  get:
    summary: List my to-dos [F-002] [API-002]
    operationId: listTodos
    security: [{bearerAuth: []}]
    parameters: [{name: after, in: query}, {name: limit, in: query}]
    responses:
      '200': {description: ok}
      '401': {$ref: '#/components/responses/Problem'}
"""


class OpenApiPerFeatureTest(unittest.TestCase):
    def test_fragments_are_validated_and_assembled(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        replies = iter([FRAG_F1, FRAG_F2_DUP, FRAG_F2])
        calls = []

        def fake(prompt, **kw):
            calls.append(kw.get("task_id"))
            return next(replies), {"provider": "fake", "model": "fake", "stop": "end"}

        prd = {"app_name": "TaskNest", "features": [{"id": "F-001", "title": "Sign in", "priority": "Must"},
                                                     {"id": "F-002", "title": "List to-dos", "priority": "Must"}]}
        with mock.patch.object(architect, "query_llm_with_meta", side_effect=fake):
            path = architect.generate_openapi_spec({}, prd, tmp, session_id="s")
        # The duplicate login fragment is merged (F-002 cited on the existing endpoint): no retry is spent.
        self.assertEqual(calls, ["architect_openapi_F-001", "architect_openapi_F-002"])
        with open(path) as f:
            spec = yaml.safe_load(f.read())
        self.assertEqual(set(spec["paths"]), {"/api/v1/auth/login"})
        self.assertIn("[F-002]", spec["paths"]["/api/v1/auth/login"]["post"]["summary"])
        self.assertIn("Problem", spec["components"]["responses"])
        self.assertIn("bearerAuth", spec["components"]["securitySchemes"])


if __name__ == "__main__":
    unittest.main()


class ArchitectureInPartsTest(unittest.TestCase):
    def test_sections_written_in_parts_and_only_failing_part_redone(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        calls = []

        def fake(prompt, **kw):
            calls.append(kw["task_id"])
            part = int(kw["task_id"][-1])
            first = 1 + 4 * (part - 1)
            return "\n\n".join(f"## {n}. Section {n}\ntext [NFR-01]" for n in range(first, first + 4)), {"model": "fake"}

        verdicts = iter([(False, ["Section 10 (Reliability) has no SLO table"]), (True, [])])
        prd = {"app_name": "TaskNest", "features": [{"id": "F-001", "title": "Sign in", "priority": "Must"}], "nfrs": []}
        with mock.patch.object(architect, "query_llm_with_meta", side_effect=fake), \
                mock.patch.object(architect, "validate_architecture_pre_judge", side_effect=lambda *a, **k: next(verdicts)):
            path = architect.generate_architecture_trd({}, prd, tmp, adr_list=[], session_id="s")
        self.assertEqual(calls, ["architect_trd_p1", "architect_trd_p2", "architect_trd_p3", "architect_trd_p3"])
        text = open(path).read()
        self.assertIn("## 1. Section 1", text)
        self.assertIn("## 12. Section 12", text)


class ArchitectRejudgeTest(unittest.TestCase):
    def test_rejudge_scores_existing_documents_without_regenerating(self):
        import json
        import main
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        sid = "rejudge-test"
        pdir = os.path.join(root, sid)
        os.makedirs(os.path.join(pdir, "docs"))
        for name in ("architecture.md", "schema.md", "openapi.yaml", "prd.md"):
            with open(os.path.join(pdir, "docs", name), "w") as f:
                f.write(f"# {name}\n")
        for name, data in (("intake.json", {}), ("qa_log.json", []),
                           ("architect_state.json", {"status": "review_failed", "judge_verdict": {"is_degraded": True}})):
            with open(os.path.join(pdir, name), "w") as f:
                json.dump(data, f)
        import judge
        with mock.patch.object(main, "DATA_PROJECTS_DIR", root), \
                mock.patch.object(architect, "parse_ba_data", return_value={}), \
                mock.patch.object(architect, "generate_architecture_trd") as regen, \
                mock.patch.object(judge, "evaluate_architecture_with_judge",
                                  return_value={"pass": True, "total": 22, "max": 24, "is_degraded": False}):
            res = architect.rejudge_architect_endpoint(architect.ArchitectSessionRequest(session_id=sid))
        regen.assert_not_called()
        self.assertEqual(res["status"], "done")
        with open(os.path.join(pdir, "architect_state.json")) as f:
            self.assertEqual(json.load(f)["status"], "done")


class ArchitectureFindingRoutingTest(unittest.TestCase):
    def test_findings_go_to_the_part_holding_their_text(self):
        doc = ("## 1. Constraints\nx\n## 3. Tech stack\nCelery 5.3 workers\n## 6. API\ny\n"
               "## 8. External integrations\nSendGrid email\n## 10. Reliability\nDatadog agent\n")
        verdict = {"unsupported_claims": [{"text": "Celery 5.3", "reason": "foreign"}, {"text": "SendGrid", "reason": "no email"},
                                          {"text": "Datadog", "reason": "foreign"}, {"text": "not in doc", "reason": "x"}]}
        routed = architect.route_findings_to_parts(doc, verdict)
        self.assertTrue(any("Celery" in n for n in routed[1]))
        self.assertTrue(any("SendGrid" in n for n in routed[2]))
        self.assertTrue(any("Datadog" in n for n in routed[3]))
        self.assertTrue(all(any("not in doc" in n for n in routed[p]) for p in (1, 2, 3)))  # unlocated -> every part
