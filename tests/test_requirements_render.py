"""requirements.md and the PRD share one set of IDs (Handbook 3.4, 25.1)."""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine"))

import json
import shutil
import tempfile
from unittest import mock

import requirements_parser
from requirements_parser import render_requirements_markdown, validate_extracted_requirements_json

PARSED = {
    "app_name": "TaskNest", "first_qid": "Q-001", "today_qid": "Q-001", "problem_qid": "Q-001",
    "shortcomings_qid": "Q-002", "today_text": "Paper lists.", "problem_text": "Tasks get lost.",
    "shortcomings_text": "No private list.",
    "personas": [{"id": "P-01", "persona": "Office staff", "context": "Daily tasks", "goal": "Track tasks", "source": "Q-001"}],
    "functional_reqs": [
        {"id": "FR-001", "feature": "Sign in", "description": "Email and password", "priority": "Must", "source": "Q-001"},
        {"id": "FR-002", "feature": "Add to-do", "description": "Title 1-200 chars", "priority": "Must", "source": "Q-001"},
        {"id": "FR-003", "feature": "Export", "description": "", "priority": "Could", "source": "Q-002"},
    ],
    "non_functional_reqs": [{"id": "NFR-01", "nfr": "Latency", "target": "< 1 s", "source": "[Q-001]"}],
    "discovered_goals": [], "discovered_metrics": [], "discovered_non_goals": [],
    "assumptions": [{"id": "ASM-01", "text": "Self sign-up.", "status": "awaiting client at Gate 1"}],
    "open_questions": [], "extracted_raw": {"entities": []},
}


class RequirementsRenderTest(unittest.TestCase):
    def test_ids_match_what_the_prd_check_reads(self):
        md = render_requirements_markdown(PARSED, {"timeline": "4 weeks", "budget": "$2,000"})
        must = set(re.findall(r"\b(FR-\d+)\b[^\n]+Must", md, re.IGNORECASE))  # same regex as validate_prd_pre_judge
        self.assertEqual(must, {"FR-001", "FR-002"})
        self.assertIn("- FR-003: Export (Could Have) [Source: Q-002]", md)
        self.assertIn("| ASM-01 | assumption | Self sign-up. |", md)
        self.assertTrue(md.startswith("# Requirements: TaskNest"))


class ExtractionReuseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "p1"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_extraction_is_reused_until_answers_change(self):
        calls = []
        def fake_extract(intake, qa, session_id=None):
            calls.append(1)
            return {"functional_requirements": [{"title": f"v{len(calls)}"}]}
        with mock.patch.object(requirements_parser, "PROJECTS_DIR", self.tmp), \
                mock.patch.object(requirements_parser, "extract_requirements_with_llm", side_effect=fake_extract):
            a = requirements_parser.load_or_extract_requirements({"x": 1}, [{"id": "Q-001"}], "p1")
            b = requirements_parser.load_or_extract_requirements({"x": 1}, [{"id": "Q-001"}], "p1")
            c = requirements_parser.load_or_extract_requirements({"x": 1}, [{"id": "Q-001"}, {"id": "Q-002"}], "p1")
        self.assertEqual(len(calls), 2)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_wrong_shapes_are_errors_not_crashes(self):
        ok, errors = validate_extracted_requirements_json({"goals": ["just a string"], "problem": "text"}, {})
        self.assertFalse(ok)
        self.assertTrue(any("goals[0] must be an object" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
