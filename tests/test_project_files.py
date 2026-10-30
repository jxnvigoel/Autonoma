"""Code editor project files and live office desks (isolated temp data)."""

import os
import sys
import shutil
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine"))

from fastapi.testclient import TestClient

import jobs
import main


class ProjectFilesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        proj = os.path.join(self.tmp, "p1")
        os.makedirs(os.path.join(proj, "repo", "src"))
        os.makedirs(os.path.join(proj, "repo", ".git"))
        os.makedirs(os.path.join(proj, "docs"))
        with open(os.path.join(proj, "repo", "src", "app.py"), "w") as f:
            f.write("print('hi')\n")
        with open(os.path.join(proj, "docs", "prd.md"), "w") as f:
            f.write("# PRD\n")
        with open(os.path.join(proj, "intake.json"), "w") as f:
            f.write("{}")
        self.patches = [mock.patch.object(main, "DATA_PROJECTS_DIR", self.tmp),
                        mock.patch.object(jobs, "DATA_PROJECTS_DIR", self.tmp)]
        for p in self.patches:
            p.start()
        self.client = TestClient(main.app)

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_tree_shows_repo_and_docs_only(self):
        r = self.client.get("/project-files/tree/p1").json()
        self.assertEqual([n["name"] for n in r["tree"]], ["repo", "docs"])
        repo = r["tree"][0]
        self.assertEqual([c["name"] for c in repo["children"]], ["src"])  # .git hidden
        self.assertTrue(r["repo_path"].endswith(os.path.join("p1", "repo")))

    def test_read_edit_repo_but_not_docs_or_outside(self):
        f = self.client.get("/project-files/file/p1", params={"path": "repo/src/app.py"}).json()
        self.assertEqual((f["content"], f["editable"]), ("print('hi')\n", True))
        self.assertFalse(self.client.get("/project-files/file/p1", params={"path": "docs/prd.md"}).json()["editable"])

        ok = self.client.put("/project-files/file/p1", json={"path": "repo/src/new.py", "content": "x = 1\n"})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(self.client.put("/project-files/file/p1", json={"path": "docs/prd.md", "content": "x"}).status_code, 403)
        for bad in ("intake.json", "repo/../intake.json", "../p2/repo/a.py", "/etc/passwd"):
            self.assertEqual(self.client.get("/project-files/file/p1", params={"path": bad}).status_code, 403, bad)

    def test_git_history_and_commit_diff(self):
        import workspace
        repo = os.path.join(self.tmp, "p1", "repo")
        self.assertEqual(self.client.get("/project-files/git/p1").status_code, 404)  # no repo yet
        # An enclosing repo (like this app's, around data/projects) must not be shown as the project's history.
        outer = os.path.join(self.tmp, "p1")
        shutil.rmtree(os.path.join(repo, ".git"))
        workspace.git(["init", "-q", "-b", "main"], outer)
        workspace.commit_all(outer, "outer repo commit")
        self.assertEqual(self.client.get("/project-files/git/p1").status_code, 404)
        workspace.git(["init", "-q", "-b", "main"], repo)
        workspace.commit_all(repo, "feat(ST-001): app prints hi")
        with open(os.path.join(repo, "src", "app.py"), "a") as f:
            f.write("print('bye')\n")
        h = self.client.get("/project-files/git/p1").json()
        self.assertEqual((h["branch"], h["commits"][0]["subject"], h["uncommitted"]), ("main", "feat(ST-001): app prints hi", ["src/app.py"]))
        self.assertGreaterEqual(h["commits"][0]["insertions"], 1)
        d = self.client.get(f"/project-files/commit/p1/{h['commits'][0]['sha']}").json()
        self.assertIn("+print('hi')", d["diff"])
        self.assertEqual(self.client.get("/project-files/commit/p1/not-a-sha").status_code, 400)

    def test_running_stage_shows_its_desk_working(self):
        release = threading.Event()
        real = jobs._registry.get("architect")
        jobs.register("architect", lambda sid: release.wait(5))
        try:
            jobs.start("p1", "architect")
            st = self.client.get("/office/status/p1").json()
            self.assertEqual(st["running_jobs"], ["architect"])
            self.assertEqual(st["agents"]["architect"]["status"], "working")
            self.assertEqual(st["agents"]["engineer"]["status"], "idle")  # no build yet
        finally:
            release.set()
            jobs._threads.pop("p1:architect", None)
            if real:
                jobs.register("architect", real)


if __name__ == "__main__":
    unittest.main()
