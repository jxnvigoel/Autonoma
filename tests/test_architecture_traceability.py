"""Code-owned TRD parts: API ids and errors, the feature -> endpoint -> table map, cited capacity inputs, and what
the Judge is shown (every ADR option, the client's answers)."""

import os
import sys
import json
import shutil
import tempfile
import unittest
from unittest import mock

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine"))

import architect
import judge

SPEC = {"openapi": "3.0.3", "paths": {
    "/api/v1/auth/signin": {"post": {"summary": "[F-001] Sign in [API-001]", "security": [], "requestBody": {},
                                     "responses": {"200": {"description": "ok"}}}},
    "/api/v1/todos": {"get": {"summary": "[F-002] List to-dos", "security": [{"bearerAuth": []}],
                              "responses": {"200": {"description": "ok"}}}},
    "/api/v1/todos/{todoId}": {"delete": {"summary": "[F-003] Delete [API-002]", "security": [{"bearerAuth": []}],
                                          "responses": {"204": {"description": "gone"}}}},
}}
SCHEMA = """| Table | Description |
|---|---|
| **TBL-01** `users` | accounts |
| **TBL-02** `sessions` | logins |
| **TBL-03** `todos` | items |

CREATE TABLE IF NOT EXISTS users (id TEXT);
CREATE TABLE IF NOT EXISTS sessions (id TEXT);
CREATE TABLE IF NOT EXISTS todos (id TEXT);
"""
QA = {"Q-001": {"answer": "About 20 users, at most 10 at the same time, each with under 500 to-dos."}}


class CodeOwnedTrdTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        spec = architect.normalize_openapi_spec(json.loads(json.dumps(SPEC)))
        with open(os.path.join(self.tmp, "openapi.yaml"), "w") as f:
            f.write(yaml.safe_dump(spec, sort_keys=False))
        with open(os.path.join(self.tmp, "schema.md"), "w") as f:
            f.write(SCHEMA)
        self.spec = spec

    def test_every_operation_gets_an_id_and_only_the_errors_that_apply(self):
        paths = self.spec["paths"]
        signin, todos, delete = (paths["/api/v1/auth/signin"]["post"], paths["/api/v1/todos"]["get"],
                                 paths["/api/v1/todos/{todoId}"]["delete"])
        self.assertIn("[API-003]", todos["summary"])  # the next unused id, not a duplicate of API-001/002
        self.assertEqual([c for c in signin["responses"] if c[0] in "45"], ["400", "422", "500"])  # public: no 401/403
        self.assertEqual([c for c in todos["responses"] if c[0] in "45"], ["400", "401", "403", "500"])
        self.assertIn("404", delete["responses"])

    def test_features_map_to_endpoints_and_tables(self):
        api, trace = architect.api_traceability_sections(self.tmp)
        self.assertIn("| API-001 | `POST /api/v1/auth/signin` | [F-001] | Public | 400, 422, 500 | TBL-01 `users`, TBL-02 `sessions` |", api)
        self.assertIn("| [F-002] | API-003 | TBL-03 `todos` |", trace)
        self.assertIn("| [F-003] | API-002 | TBL-03 `todos` |", trace)

    def test_code_sections_replace_sections_6_and_7_and_are_not_added_twice(self):
        # The model once wrote its own map with ids (TBL-001) the schema does not have.
        doc = ("## 6. API\nmodel-written table\n\n## 7. Data model\n| TBL-001 | users |\n\n"
               "## 8. External integrations\nnone\n")
        once = architect._with_code_sections(doc, self.tmp)
        self.assertNotIn("model-written table", once)
        self.assertNotIn("TBL-001", once)
        self.assertIn("| TBL-01 | `users` | id |", once)
        self.assertIn("## 8. External integrations\nnone", once)
        self.assertEqual(architect._with_code_sections(once, self.tmp), once)

    def test_errors_that_cannot_happen_are_dropped(self):
        spec = {"paths": {"/api/v1/todos": {"get": {"summary": "[F-002] List [API-001]", "security": [{"bearerAuth": []}],
                                                     "responses": {"200": {}, "404": {}, "409": {}, "422": {}}}},
                          "/api/v1/users": {"post": {"summary": "[F-001] Register [API-002]", "security": [], "requestBody": {},
                                                      "responses": {"201": {}, "401": {}, "409": {}}}}}}
        paths = architect.normalize_openapi_spec(spec)["paths"]
        self.assertEqual(sorted(paths["/api/v1/todos"]["get"]["responses"]), ["200", "400", "401", "403", "500"])
        self.assertEqual(sorted(paths["/api/v1/users"]["post"]["responses"]), ["201", "400", "409", "422", "500"])

    def test_api_findings_rewrite_only_the_named_features_endpoints(self):
        verdict = {"scores": [{"criterion": "api_design_and_auth", "score": 1, "max": 3,
                               "evidence": "API-002 lists every user", "fix": "remove it"},
                              {"criterion": "security_stride", "score": 2, "max": 3, "fix": "x"}],
                   "unsupported_claims": [{"text": "GET /api/v1/todos returns 409", "reason": "r"},
                                          {"text": "a TRD sentence", "reason": "y"}]}
        feedback, rest = architect.split_api_findings(verdict, self.tmp)
        self.assertEqual(sorted(feedback), ["F-002", "F-003"])  # API-002 is F-003's; /api/v1/todos is F-002's
        self.assertEqual([s["criterion"] for s in rest["scores"]], ["security_stride"])
        self.assertEqual([u["text"] for u in rest["unsupported_claims"]], ["a TRD sentence"])

        prompts = []

        def fake(prompt, **kw):
            prompts.append(prompt)
            return "/api/v1/todos/{todoId}:\n  delete:\n    summary: '[F-003] Delete own to-do'\n    security: [{bearerAuth: []}]\n" \
                   "    responses: {'204': {description: gone}}\n", {"model": "fake"}

        prd = {"app_name": "T", "features": [{"id": "F-001", "title": "Sign in", "priority": "Must"},
                                             {"id": "F-002", "title": "List", "priority": "Must"},
                                             {"id": "F-003", "title": "Delete", "priority": "Must", "story": "As a user I delete my to-do"}]}
        with mock.patch.object(architect, "query_llm_with_meta", side_effect=fake):
            architect.generate_openapi_spec({}, prd, self.tmp, session_id="s", only=["F-003"], feedback={"F-003": ["lists every user"]})
        self.assertEqual(len(prompts), 1)
        self.assertIn("lists every user", prompts[0])
        self.assertIn("As a user I delete my to-do", prompts[0])
        paths = yaml.safe_load(open(os.path.join(self.tmp, "openapi.yaml")).read().split("\n", 1)[1])["paths"]
        self.assertIn("[API-001]", paths["/api/v1/auth/signin"]["post"]["summary"])  # other features kept as they were
        self.assertIn("[API-003]", paths["/api/v1/todos"]["get"]["summary"])
        self.assertIn("[API-002]", paths["/api/v1/todos/{todoId}"]["delete"]["summary"])  # rewritten, reuses its freed id

    def test_assumption_ids_must_exist_or_be_defined(self):
        ba = {"assumptions": [{"id": "ASM-01", "text": "staff self sign up"}, {"id": "ASM-02", "text": "x"}]}
        self.assertEqual(architect._known_assumptions(ba)[1], "ASM-03")
        bad = "## 2. Capacity estimate\nPeak = 5 req/s [ASM-001]\n## 3. Tech stack\nsee ASM-01\n"
        good = "## 2. Capacity estimate\n- **ASM-03**: 0.5 req/s per user\nPeak = 5 req/s [ASM-03]\n## 3. Tech stack\nsee ASM\u201101\n"
        self.assertIn("ASM-001", architect.assumption_errors(bad, ba)[0])
        self.assertEqual(architect.assumption_errors(good, ba), [])

    def test_team_plan_comes_from_the_project_and_fills_section_12(self):
        prd = {"app_name": "T", "features": [{"id": "F-001", "title": "a", "priority": "Must"},
                                             {"id": "F-002", "title": "b", "priority": "Should"}]}
        architect.generate_team_plan({"intake": {"timeline": "6 weeks"}}, prd, self.tmp,
                                     adrs=[{"id": f"ADR-00{n}"} for n in range(1, 5)])
        plan = json.load(open(os.path.join(self.tmp, "team-plan.json")))
        self.assertEqual(plan["timeline_weeks"], 6)
        self.assertNotIn("GitHub", json.dumps(plan))
        self.assertTrue(all(any(r.startswith("ADR-") for r in st["refs"]) for st in plan["seats"]))
        doc = "## 6. API\nx\n## 7. Data model\ny\n## 12. Team plan (for HR)\nmodel seats\n"
        out = architect._with_code_sections(doc, self.tmp)
        self.assertNotIn("model seats", out)
        self.assertIn("| ROLE-01 | backend | 1 | 1-6 |", out)
        self.assertIn("Every Must-have feature is covered: F-001", out)

    def test_plural_auth_paths_and_public_sign_in_errors(self):
        self.assertEqual(architect._tables_for_path("/api/v1/auth/signins", ["users", "sessions", "todos"]), ["users", "sessions"])
        spec = {"paths": {"/api/v1/auth/signins": {"post": {"summary": "[F-002] [API-001]", "security": [], "requestBody": {},
                                                             "responses": {"200": {}, "401": {}, "403": {}, "404": {}}}}}}
        codes = sorted(architect.normalize_openapi_spec(spec)["paths"]["/api/v1/auth/signins"]["post"]["responses"])
        self.assertEqual(codes, ["200", "400", "401", "422", "500"])  # a wrong password is 401; nothing is 403 or 404

    def test_capacity_inputs_must_be_numbers_the_client_gave(self):
        good = "## 2. Capacity estimate\n| Peak users | 10 at once [Q-001] | 10 |\n| RPS | 10 users × 1 req/s [ASM-001] | 10 |\n## 3. Tech stack\n"
        bad = "## 2. Capacity estimate\n| Peak users | 50 simultaneous users (max from [Q-001]) | 50 |\n## 3. Tech stack\n"
        self.assertEqual(architect.capacity_citation_errors(good, QA), [])
        errors = architect.capacity_citation_errors(bad, QA)
        self.assertEqual(len(errors), 1)
        self.assertIn("'50'", errors[0])


class JudgeSeesTheSourcesTest(unittest.TestCase):
    def test_long_option_rows_do_not_hide_option_b(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        os.makedirs(os.path.join(tmp, "adr"))
        long_cell = "pro " * 300
        with open(os.path.join(tmp, "adr", "ADR-001.md"), "w") as f:
            f.write("# ADR-001: Style\n## Options\n| Option | Pros | Cons |\n|---|---|---|\n"
                    f"| **A. Monolith** | {long_cell} | {long_cell} |\n| **B. Microservices** | x | y |\n## Decision\nA.\n")
        ctx = judge.adr_context_for_judge(tmp)
        self.assertIn("**B. Microservices**", ctx)
        self.assertIn("A.", ctx.split("## Decision")[1])

    def test_retyped_quotes_still_match(self):
        doc = "API summary (from docs/openapi.yaml; every error is an RFC 9457 Problem Details body): (Q\u2011001) **10** users"
        for quote in ('"every error is an RFC 9457 Problem Details body"', "(**Q-001**) 10 users"):
            self.assertIn(judge.normalize_quote(quote), judge.normalize_quote(doc))

    def test_every_chunk_knows_the_requirement_ids_and_adrs_keep_every_section(self):
        prompts = {}

        def fake(prompt, task_id=None, **kw):
            prompts[task_id] = prompt
            return json.dumps({"scores": [], "unsupported_claims": []}), {}

        ba = {"qa_map": QA, "non_functional_reqs": [{"id": "NFR-01", "nfr": "Latency", "target": "under 1 s"}],
              "assumptions": [{"id": "ASM-01", "text": "staff self sign up"}], "discovered_goals": [{"id": "G-02", "goal": "privacy"}]}
        arch = "## 1. Constraints\nx\n## 5. Authentication\ny\n## 9. Security\nlatency [NFR-01]\n"
        with mock.patch.object(judge, "query_llm_with_meta", side_effect=fake):
            judge.evaluate_architecture_with_judge(arch, "# PRD F-001", ba, schema_text="")
        self.assertIn("NFR-01 Latency: under 1 s", prompts["judge_arch_chunk_3_stride_ops"])
        self.assertIn("ASM-01 staff self sign up", prompts["judge_arch_chunk_1b_adr_files"])
        self.assertIn("G-02 privacy", prompts["judge_arch_chunk_1b_adr_files"])
        long_adr = ("# ADR-001: x\n## Context\n" + "word " * 400 + "\n## Options\n| Option | Pros |\n|---|---|\n"
                    "| A. a | b |\n| B. c | d |\n## Decision\n" + "why " * 400 + "\n## Consequences\nEasier backups.\n")
        compact = judge._compact_adr(long_adr)
        self.assertIn("## Consequences\nEasier backups.", compact)
        self.assertIn("[section shortened for review]", compact)

    def test_judge_gets_client_answers_and_judges_adrs_separately(self):
        prompts = {}

        def fake(prompt, task_id=None, **kw):
            prompts[task_id] = prompt
            return json.dumps({"scores": [], "unsupported_claims": []}), {}

        arch = "## 1. Constraints\nx\n## 5. Authentication\ny\n## 9. Security\nz\n"
        with mock.patch.object(judge, "query_llm_with_meta", side_effect=fake):
            judge.evaluate_architecture_with_judge(arch, "# PRD", {"qa_map": QA}, schema_text="")
        self.assertIn("at most 10 at the same time", prompts["judge_arch_chunk_1_stack_adrs"])
        self.assertIn("adr_tradeoffs_and_alternatives", prompts["judge_arch_chunk_1b_adr_files"])
        self.assertNotIn("adr_tradeoffs_and_alternatives", prompts["judge_arch_chunk_1_stack_adrs"])


GOOD_ADR = """# ADR-002: Data storage
**Status**: accepted
**Driven by**: [NFR-02], [Q-001]

## Context
One office computer with only Python [NFR-02].

## Options
| Option | Pros | Cons | Fits constraints? |
|---|---|---|---|
| A. SQLite file | stdlib | one writer | Yes [NFR-02] |
| B. PostgreSQL server | concurrency | extra install | No [NFR-02] |

## Decision
We choose SQLite because it ships with Python; PostgreSQL needs an install [NFR-02].

## Consequences
Backups are a file copy.
"""
BA = {"non_functional_reqs": [{"id": "NFR-01", "nfr": "Latency", "target": "under 1 s"},
                              {"id": "NFR-02", "nfr": "Platform", "target": "one office PC, Python only"}],
      "qa_map": {"Q-001": {"answer": "One office computer, no internet."}}}
PRD_DATA = {"app_name": "TaskNest", "features": [{"id": "F-001", "title": "Sign in"}], "nfrs": []}


class ProjectGroundedAdrTest(unittest.TestCase):
    def setUp(self):
        self.ids = architect._project_ids(BA, PRD_DATA)

    def test_a_complete_adr_passes(self):
        self.assertEqual(architect.validate_adr(GOOD_ADR, "ADR-002", self.ids), [])
        self.assertTrue(architect.adr_decision(GOOD_ADR).startswith("We choose SQLite"))

    def test_one_option_or_an_invented_id_fails(self):
        one_option = GOOD_ADR.replace("| B. PostgreSQL server | concurrency | extra install | No [NFR-02] |\n", "")
        self.assertIn("1 option row", " ".join(architect.validate_adr(one_option, "ADR-002", self.ids)))
        invented = GOOD_ADR.replace("[Q-001]", "[OQ-02]")
        self.assertIn("OQ-02", " ".join(architect.validate_adr(invented, "ADR-002", self.ids)))

    def test_prompt_carries_the_projects_requirements_not_fixed_options(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        prompts = []

        def fake(prompt, task_id=None, **kw):
            prompts.append(prompt)
            n = task_id.split("_")[1]
            reply = GOOD_ADR.replace("ADR-002", n)
            one_option = reply.replace("| B. PostgreSQL server | concurrency | extra install | No [NFR-02] |\n", "")
            return (one_option if len(prompts) == 1 else reply), {"model": "fake"}

        with mock.patch.object(architect, "query_llm_with_meta", side_effect=fake):
            adrs = architect.generate_adrs(BA, PRD_DATA, tmp, session_id="s")
        self.assertEqual([a["id"] for a in adrs], ["ADR-001", "ADR-002", "ADR-003", "ADR-004"])
        self.assertEqual(len(prompts), 5)  # ADR-001's first reply had one option and was redone
        self.assertIn("[NFR-02] Platform: one office PC, Python only", prompts[0])
        self.assertIn("FAILED THESE CHECKS", prompts[1])
        self.assertNotIn("Electron", "".join(prompts))
        self.assertIn("ADR-001: We choose SQLite", prompts[2])  # later ADRs see the earlier decisions
        self.assertIn("must be a SQL database", prompts[2])  # ADR-002: the schema step only builds SQL DDL
        self.assertNotIn("TOOLCHAIN LIMIT", prompts[0])

        with mock.patch.object(architect, "query_llm_with_meta", side_effect=fake):
            architect.generate_adrs(BA, PRD_DATA, tmp, session_id="s", feedback={"ADR-003": ["cites NFR-01 wrongly"]},
                                    only=["ADR-003"])
        self.assertEqual(len(prompts), 6)
        self.assertIn("cites NFR-01 wrongly", prompts[-1])

    def test_adr_findings_go_to_the_adr_not_the_trd(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        with open(os.path.join(tmp, "ADR-002.md"), "w") as f:
            f.write(GOOD_ADR)
        verdict = {"unsupported_claims": [{"text": "it ships with Python", "reason": "x"},
                                          {"text": "a TRD sentence", "reason": "y"}],
                   "scores": [{"criterion": "adr_tradeoffs_and_alternatives", "score": 1, "max": 3,
                               "evidence": "ADR-002 has weak cons", "fix": "expand"},
                              {"criterion": "api_design_and_auth", "score": 2, "max": 3, "fix": "z"}]}
        adr_fb, trd = architect.split_adr_findings(verdict, tmp)
        self.assertEqual(list(adr_fb), ["ADR-002"])
        self.assertEqual(len(adr_fb["ADR-002"]), 2)
        self.assertEqual([u["text"] for u in trd["unsupported_claims"]], ["a TRD sentence"])
        self.assertEqual([s["criterion"] for s in trd["scores"]], ["api_design_and_auth"])


if __name__ == "__main__":
    unittest.main()
