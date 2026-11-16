"""gpt-oss built-in tool calls rejected by Groq (HTTP 400 tool_use_failed) are recovered, not failed over."""
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine"))

import llm_client  # noqa: E402
from agent_runtime import normalize_reply, extract_json_object, tools_for_role  # noqa: E402


class _Res:
    status_code = 400
    headers = {}

    def __init__(self, body):
        self._body = body
        self.text = json.dumps(body)

    def json(self):
        return self._body


class ToolUseFailedRecoveryTest(unittest.TestCase):
    def test_failed_generation_becomes_the_answer(self):
        gen = '{"name": "repo_browser.list_files", "arguments": {"path": "", "depth": 2}\n}'
        body = {"error": {"message": "Tool choice is none, but model called a tool", "code": "tool_use_failed",
                          "failed_generation": gen}}
        client = llm_client.LLMClient()
        with mock.patch.object(llm_client.requests, "post", return_value=_Res(body)), \
                mock.patch.object(client, "cloud_enabled", return_value=True), \
                mock.patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}):
            out = client._execute_groq_call("task", "system", "openai/gpt-oss-120b", 0.2, 1000, role="backend")
        self.assertEqual(out["text"], gen)
        self.assertTrue(out["recovered_tool_call"])
        obj, notes = normalize_reply(extract_json_object(out["text"]), tools_for_role("backend"), ["lint", "test"])
        self.assertEqual(obj, {"tool_calls": [{"name": "list_files", "input": {"glob": "**/*"}}]})
        self.assertTrue(any("repo_browser.list_files" in n for n in notes))

    def test_open_file_maps_to_read_file(self):
        obj, _ = normalize_reply({"name": "repo_browser.open_file", "arguments": {"path": "src/app.py"}},
                                 tools_for_role("backend"), [])
        self.assertEqual(obj["tool_calls"][0], {"name": "read_file", "input": {"path": "src/app.py"}})

    def test_unknown_builtin_stays_unknown(self):
        obj, _ = normalize_reply({"name": "browser.search_web", "arguments": {}}, tools_for_role("backend"), [])
        self.assertEqual(obj["tool_calls"][0]["name"], "browser.search_web")  # the validator rejects it visibly


if __name__ == "__main__":
    unittest.main()
