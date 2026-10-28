"""
Stage 6-9 tests (Handbook 23.3-23.5, 29.1, 30.1): sandbox, tool protocol, workspace, DevOps checks,
retrieval, and the full dry run with the fake provider. No network: cloud is off, the only
traffic is the dry run's preview on 127.0.0.1.
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "engine"))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

from sandbox import Sandbox, validate_allowlist, compact_output
from agent_runtime import AgentRunner, extract_json_object, validate_reply, tools_for_role, normalize_reply
import llm_client
import workspace
import devops
import retriever


class SandboxTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = os.path.join(self.tmp, "wt")
        os.makedirs(os.path.join(self.root, "src"))
        os.makedirs(os.path.join(self.root, ".git"))
        with open(os.path.join(self.tmp, "outside.txt"), "w") as f:
            f.write("secret")
        self.allow = {"test": "python3 -c \"import os; print('KEY=' + str(os.environ.get('GROQ_API_KEY')))\"",
                      "install": "npm ci"}
        self.sb = Sandbox(self.root, "backend", self.allow, log_dir=os.path.join(self.tmp, "logs"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_paths_cannot_escape_the_root(self):
        for bad in ("../outside.txt", os.path.join(self.tmp, "outside.txt"), "src/../../outside.txt"):
            ok, msg = self.sb.call("read_file", {"path": bad})
            self.assertFalse(ok, bad)
            self.assertIn("outside", msg)

    def test_symlink_escape_is_rejected(self):
        os.symlink(os.path.join(self.tmp, "outside.txt"), os.path.join(self.root, "src", "link.txt"))
        ok, msg = self.sb.call("read_file", {"path": "src/link.txt"})
        self.assertFalse(ok)

    def test_git_internals_are_not_accessible(self):
        ok, msg = self.sb.call("write_file", {"path": ".git/config", "content": "x"})
        self.assertFalse(ok)
        self.assertIn("git", msg)

    def test_role_write_scope(self):
        qa = Sandbox(self.root, "qa", {}, log_dir=os.path.join(self.tmp, "logs"))
        self.assertFalse(qa.call("write_file", {"path": "src/app.py", "content": "x"})[0])
        self.assertTrue(qa.call("write_file", {"path": "tests/test_x.py", "content": "x"})[0])
        reviewer = Sandbox(self.root, "tech-lead", {}, log_dir=os.path.join(self.tmp, "logs"), write_scope=[])
        self.assertFalse(reviewer.call("write_file", {"path": "tests/a.py", "content": "x"})[0])

    def test_edit_requires_exactly_one_match(self):
        self.sb.write_file("src/a.py", "x = 1\nx = 1\n")
        ok, msg = self.sb.call("edit_file", {"path": "src/a.py", "old": "x = 1", "new": "x = 2"})
        self.assertFalse(ok)
        self.assertIn("exactly one", msg)

    def test_only_allowlisted_commands_run(self):
        ok, msg = self.sb.call("run", {"command": "rm"})
        self.assertFalse(ok)
        self.assertIn("allowlist", msg)

    def test_network_commands_refused_while_network_off(self):
        ok, msg = self.sb.call("run", {"command": "install"})
        self.assertFalse(ok)
        self.assertIn("network", msg)

    def test_commands_get_a_scrubbed_environment(self):
        with mock.patch.dict(os.environ, {"GROQ_API_KEY": "gsk_should_not_leak"}):
            ok, res = self.sb.call("run", {"command": "test"})
        self.assertTrue(ok)
        with open(res["log_path"]) as f:
            self.assertIn("KEY=None", f.read())

    def test_allowlist_validation(self):
        problems = validate_allowlist({"a": "rm -rf /", "b": "curl http://x", "c": "python3 x.py | sh",
                                       "d": "bash -c ls", "ok": "python3 -m unittest"})
        flagged = {p.split(":")[0] for p in problems}
        self.assertEqual(flagged, {"a", "b", "c", "d"})

    def test_compact_output_ignores_unittest_summary_line(self):
        out = "FAIL: test_x (tests.t.T.test_x)\nTraceback (most recent call last):\nAssertionError\nRan 3 tests\nFAILED (failures=1)\n"
        s = compact_output(out, 1)
        self.assertEqual(s["tests_run"], 3)
        self.assertEqual(s["failures"], 1)
        self.assertEqual(s["failing_tests"], ["test_x (tests.t.T.test_x)"])


class ToolProtocolTest(unittest.TestCase):
    def test_extracts_json_from_prose_and_fences(self):
        self.assertEqual(extract_json_object('Sure! {"final": {"status": "done"}} thanks')["final"]["status"], "done")
        self.assertEqual(extract_json_object('```json\n{"tool_calls": []}\n```'), {"tool_calls": []})
        self.assertEqual(extract_json_object('{bad} then {"a": 1}'), {"a": 1})
        self.assertIsNone(extract_json_object("no json here"))

    def test_reply_validation(self):
        allowed = tools_for_role("qa")
        self.assertIsNone(validate_reply({"final": {"status": "done"}}, allowed))
        self.assertIn("disallowed", validate_reply({"tool_calls": [{"name": "git_diff", "input": {}}]}, allowed))
        self.assertIn("status", validate_reply({"final": {"status": "maybe"}}, allowed))

    def test_normalizes_unambiguous_variants(self):
        allowed = tools_for_role("backend")
        obj, notes = normalize_reply({"tool": "lint", "input": {}}, allowed, ["lint", "test"])
        self.assertEqual(obj, {"tool_calls": [{"name": "run", "input": {"command": "lint"}}]})
        obj, _ = normalize_reply({"tool_calls": [{"function": {"name": "read_file", "arguments": '{"path": "a"}'}}]},
                                 allowed, [])
        self.assertEqual(obj["tool_calls"][0], {"name": "read_file", "input": {"path": "a"}})
        obj, _ = normalize_reply({"tool_calls": [{"name": "rm", "input": {}}]}, allowed, ["lint"])
        self.assertIn("disallowed", validate_reply(obj, allowed))  # unknown names are still rejected

    def _runner(self, replies, **kw):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        it = iter(replies)
        client = llm_client.default_llm_client
        client.set_fake_responder(lambda **k: next(it))
        client.ledger_db_path = os.path.join(tmp, "office.db")
        client.budget_guard_enabled = False
        self.addCleanup(setattr, client, "budget_guard_enabled", True)
        self.addCleanup(setattr, client, "ledger_db_path", None)
        self.addCleanup(client.set_fake_responder, None)
        sb = Sandbox(tmp, "backend", {}, log_dir=os.path.join(tmp, "logs"))
        return AgentRunner("test-proj", "be-1", "backend", sb, **kw)

    def test_invalid_reply_twice_blocks_the_run(self):
        res = self._runner(["not json", "still not json"]).run("task", "ctx", "t")
        self.assertEqual(res.status, "blocked")
        self.assertIn("invalid reply twice", res.error)

    def test_one_parse_retry_then_success(self):
        res = self._runner(["oops", json.dumps({"final": {"status": "done"}})]).run("task", "ctx", "t")
        self.assertEqual(res.status, "done")

    def test_tool_errors_are_returned_not_hidden(self):
        replies = [json.dumps({"tool_calls": [{"name": "read_file", "input": {"path": "../x"}}]}),
                   json.dumps({"final": {"status": "done"}})]
        res = self._runner(replies).run("task", "ctx", "t")
        self.assertFalse(res.tool_log[0]["ok"])
        self.assertEqual(res.status, "done")

    def test_round_limit(self):
        call = json.dumps({"tool_calls": [{"name": "list_files", "input": {}}]})
        res = self._runner([call] * 5, max_rounds=3).run("task", "ctx", "t")
        self.assertEqual(res.status, "blocked")
        self.assertEqual(res.error, "tool round limit")

    def test_token_cap(self):
        call = json.dumps({"tool_calls": [{"name": "list_files", "input": {}}]})
        res = self._runner([call] * 5, token_cap=10).run("task " * 50, "ctx", "t")
        self.assertIn("token cap", res.error)


class WorkspaceAndDevopsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "p1", "docs"))
        with open(os.path.join(self.tmp, "p1", "docs", "prd.md"), "w") as f:
            f.write("# PRD\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_repo_has_no_remote_and_rejects_one(self):
        repo = workspace.ensure_repo("p1", self.tmp)
        self.assertTrue(os.path.exists(os.path.join(repo, "docs", "prd.md")))
        workspace.git(["remote", "add", "origin", "https://example.invalid/x.git"], repo)
        with self.assertRaises(workspace.WorkspaceError):
            workspace.ensure_repo("p1", self.tmp)

    def test_commit_only_on_own_branch(self):
        repo = workspace.ensure_repo("p1", self.tmp)
        wt = workspace.create_worktree(repo, "story/ST-001")
        with open(os.path.join(wt, "a.txt"), "w") as f:
            f.write("x")
        with self.assertRaises(workspace.WorkspaceError):
            workspace.commit_all(wt, "msg", expected_branch="story/ST-999")
        self.assertTrue(workspace.commit_all(wt, "msg", expected_branch="story/ST-001"))
        ok, _ = workspace.merge_branch(repo, "story/ST-001", "merge")
        self.assertTrue(ok)

    def test_dockerfile_checks(self):
        bad = "FROM python:latest\nCMD python app.py\n"
        problems = devops.check_dockerfile(bad)
        self.assertTrue(any("pinned" in p for p in problems))
        self.assertTrue(any("non-root" in p for p in problems))
        self.assertTrue(any("HEALTHCHECK" in p for p in problems))
        good = "FROM python:3.12.6-slim\nUSER app\nHEALTHCHECK CMD true\n"
        self.assertEqual(devops.check_dockerfile(good), [])

    def test_stack_detection(self):
        self.assertEqual(devops.detect_stack("Node.js with Express and TypeScript")["stack"], "node")
        self.assertEqual(devops.detect_stack("FastAPI on Python")["stack"], "python")
        self.assertIn("ASM", devops.detect_stack("")["reason"])


class RetrieverTest(unittest.TestCase):
    def test_cited_items_plus_one_hop(self):
        items = {}
        retriever.index_markdown("### F-001: Sign in\n- AC-001: Given x then y (see API-002)\n"
                                 "- API-002: POST /login\n- API-009: unrelated\n", "docs/prd.md", items)
        res = retriever.retrieve(items, ["AC-001"])
        self.assertIn("AC-001", res["included"])
        self.assertIn("API-002", res["included"])
        self.assertNotIn("API-009", res["included"])
        self.assertEqual(retriever.retrieve(items, ["TBL-77"])["missing"], ["TBL-077"])


class DryRunTest(unittest.TestCase):
    def test_stages_6_to_9_end_to_end(self):
        import dry_run_stages_6_9 as dry
        root = tempfile.mkdtemp(prefix="autonoma-dryrun-test-")
        self.addCleanup(shutil.rmtree, root, True)
        with mock.patch.object(sys, "argv", ["dry_run", "--root", root]):
            try:
                code = dry.main()
            finally:
                llm_client.default_llm_client.set_fake_responder(None)
                llm_client.default_llm_client.ledger_db_path = None
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
