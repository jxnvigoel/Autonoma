import unittest
import subprocess
import sys
import os

class TestHandbookCitations(unittest.TestCase):
    def test_verbatim_handbook_citations(self):
        """
        A2: Every quoted 'handbook line' in docs/agents/*.md, skills/*/role.md,
        and code comments must exist verbatim in docs/handbook/VirtualOffice_Complete_Guide.md.
        Run scripts/check_citations.py and fail if any ungrounded quote or forbidden phrase is found.
        """
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        script_path = os.path.join(repo_root, "scripts", "check_citations.py")
        res = subprocess.run([sys.executable, script_path], cwd=repo_root, capture_output=True, text=True)
        if res.returncode != 0:
            self.fail(f"check_citations.py failed with exit code {res.returncode}:\n{res.stdout}\n{res.stderr}")
        self.assertIn("[PASS] All cited handbook lines exist VERBATIM", res.stdout)

if __name__ == "__main__":
    unittest.main()
