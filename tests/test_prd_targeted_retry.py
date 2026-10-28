"""PRD retries regenerate only the failing features, with the validator's errors (Handbook 2.7.3)."""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine"))

import pm

PARSED = {"app_name": "TaskNest", "qa_map": {}, "personas": [], "non_functional_reqs": [],
          "discovered_features": [{"id": "FR-001", "feature": "Sign in"}, {"id": "FR-002", "feature": "Sign out"}]}


class PrdTargetedRetryTest(unittest.TestCase):
    def test_only_failing_feature_is_regenerated_with_feedback(self):
        feature_calls = []

        def fake_feature(**kw):
            feature_calls.append((kw["f_idx"], kw.get("feedback")))
            fid = f"F-{kw['f_idx']:03d}"
            return f"### Feature {fid}: x\n", [{"id": f"AC-{kw['f_idx']:03d}", "text": "t"}], {"model": "fake"}

        section = lambda *a, **k: ("## section", {"model": "fake", "provider": "fake"})
        verdicts = iter([(False, ["Feature F-002 is missing an explicit unhappy path acceptance criterion"]), (True, [])])
        patches = [mock.patch.object(pm, name, side_effect=section) for name in (
            "generate_section_1_overview_llm", "generate_section_2_problem_llm", "generate_section_3_users_llm",
            "generate_section_4_goals_metrics_llm", "generate_section_6_nfr_summary_llm",
            "generate_section_7_risks_llm", "generate_section_8_assumptions_llm", "generate_section_9_scope_changes_llm")]
        with mock.patch.object(pm, "generate_single_feature_spec_llm", side_effect=fake_feature), \
                mock.patch.object(pm, "validate_prd_pre_judge", side_effect=lambda *a, **k: next(verdicts)):
            for p in patches:
                p.start()
            try:
                pm.build_handbook_compliant_prd_section_by_section(PARSED, session_id="s")
                sec1_calls = pm.generate_section_1_overview_llm.call_count
            finally:
                for p in patches:
                    p.stop()
        self.assertEqual([c[0] for c in feature_calls], [1, 2, 2])
        self.assertIsNone(feature_calls[0][1])
        self.assertIn("unhappy path", feature_calls[2][1][0])
        self.assertEqual(sec1_calls, 1)


class StructuredFeatureSpecTest(unittest.TestCase):
    def test_json_spec_is_checked_and_rendered_by_code(self):
        import json
        bad = json.dumps({"story": "As a [P-01], I want to sign out so that my data is safe.",
                          "acceptance_criteria": [{"kind": "happy", "given": "a", "when": "b", "then": "c"},
                                                  {"kind": "happy", "given": "d", "when": "e", "then": "f"}]})
        good = json.dumps({"story": "As a [P-01], I want to sign out so that my data is safe",
                           "acceptance_criteria": [
                               {"kind": "happy", "given": "an active session", "when": "the user signs out",
                                "then": "the sign-in screen is displayed within < 1 s [NFR-01]"},
                               {"kind": "unhappy", "given": "the session already expired", "when": "the user signs out",
                                "then": "the sign-in screen is shown and no error is raised"}]})
        replies = iter([bad, good])
        prompts = []

        def fake(prompt, **kw):
            prompts.append(prompt)
            return next(replies), {"model": "fake"}

        with mock.patch.object(pm, "query_llm_with_meta", side_effect=fake):
            block, acs, _ = pm.generate_single_feature_spec_llm(
                feature_dict={"id": "FR-003", "feature": "Sign out", "priority": "Must"}, f_idx=3, ac_start_idx=5,
                personas=[{"id": "P-01", "persona": "Staff"}], nfr_latency="< 1 s", app_name="TaskNest")
        self.assertIn("at least one 'happy' and one 'unhappy'", prompts[1])
        self.assertEqual([a["id"] for a in acs], ["AC-005", "AC-006"])
        self.assertTrue(acs[1]["is_unhappy"])
        self.assertIn("| AC-006 | (unhappy path) Given the session already expired, when the user signs out, then", block)
        self.assertIn("- **Story**: As a [P-01], I want to sign out so that my data is safe.", block)


class JudgeFeedbackRoutingTest(unittest.TestCase):
    def test_findings_route_to_sections_and_reach_their_prompt(self):
        verdict = {"unsupported_claims": [
            {"section": "User roles and permissions", "text": "set due dates and reminders", "reason": "listed as won't have"},
            {"section": "5. Features", "text": "F-004 lets users attach files", "reason": "not in discovery"}],
            "scores": [{"criterion": "metrics", "score": 1, "max": 3, "evidence": "Goal G-01 has no target",
                        "fix": "give the goal a measurable target"}]}
        fb = pm.map_judge_findings_to_sections(verdict)
        self.assertIn("prd_sec_3_users", fb)
        self.assertIn("prd_sec_5_F-004", fb)
        self.assertIn("prd_sec_4_goals_metrics", fb)
        sent = []
        with mock.patch.object(pm, "_raw_query_llm_with_meta", side_effect=lambda prompt, **kw: sent.append(prompt) or ("x", {})):
            pm._SECTION_FEEDBACK.update(fb)
            try:
                pm._query_with_section_feedback("write section 3", task_id="prd_sec_3_users")
                pm._query_with_section_feedback("write section 6", task_id="prd_sec_6_nfr")
            finally:
                pm._SECTION_FEEDBACK.clear()
        self.assertIn("due dates and reminders", sent[0])
        self.assertNotIn("REVIEWER", sent[1])


if __name__ == "__main__":
    unittest.main()


class NonGoalContradictionTest(unittest.TestCase):
    PRD = """## 3. Users
| Role | Does | Can | Cannot | Source |
|---|---|---|---|---|
| Staff | Manage to-dos; set due dates and reminders. | Add to-dos | Share lists or see due dates | [Q-001] |

## 4. Goals
### Non-goals (not in v1)
| ID | Non-goal (not in v1) | Why | Source |
|---|---|---|---|
| NG-02 | Due dates and reminders | Excluded | [Q-001] |

## 5. Features
### Feature F-001: Add to-do
- **Story**: As a [P-01], I want to add a to-do with no due date so that I remember it.
"""

    def test_non_goal_offered_as_capability_is_flagged_once_per_mention(self):
        import judge
        found = judge.audit_non_goal_contradictions(self.PRD)
        self.assertEqual(sorted(f["text"].lower() for f in found), ["due dates", "reminders"])
        self.assertTrue(all(f["section"] == "3. Users" for f in found))  # "Cannot" column and "no due date" are fine
