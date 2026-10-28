"""Architecture grounding audit: real contamination is caught, ordinary project prose is not (Handbook 14.1.3)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine"))

import judge

PRD = "# PRD\nStaff keep a private to-do list. Users sign in with email and password. [Q-001]\n"
QA = {"Q-001": {"question": "What is it?", "answer": "A to-do app with sign in, on one offline office computer."}}
ARCH = """## 3. Tech stack
| Layer | Choice |
|---|---|
| Backend | Python standard library http.server [ADR-001] |
The **RBAC Table** below lists who can read todos. Sessions are stored in SQLite with WAL [ADR-002].
The safest stdlib option keeps deps pip installable, bytes approx 2 KB per todo [Q-01].
"""


class ArchitectureGroundingTest(unittest.TestCase):
    def audit(self, text):
        found, _ = judge.run_architecture_code_audits(text, PRD, {"qa_map": QA}, "CREATE TABLE todos (id INTEGER);")
        return [f for f in found if "contamination" in f.get("reason", "") or "Placeholder" in f.get("reason", "")
                or "Cited question" in f.get("reason", "")]

    def test_ordinary_project_prose_is_not_flagged(self):
        self.assertEqual(self.audit(ARCH), [])

    def test_planted_contamination_and_invented_citation_are_caught(self):
        found = self.audit(ARCH + "\n**Airframe Registry** stores Drone Photogrammetry tiles [Q-07].\nTODO: fill in\n")
        texts = {f["text"] for f in found}
        self.assertIn("Airframe Registry", texts)
        self.assertIn("drone photogrammetry", texts)
        self.assertIn("[Q-07]", texts)
        self.assertTrue(any("Placeholder" in f["reason"] for f in found))


if __name__ == "__main__":
    unittest.main()
