"""
Local-first routing, ledger and budget guard tests (Handbook 1.4, 22.4, 26.4).

Nothing here touches the network: cloud stays disabled, local models are stubbed,
and model calls go to the deterministic fake provider (Handbook 30.1).
"""

import os
import sys
import json
import shutil
import sqlite3
import tempfile
import unittest
from unittest import mock

ENGINE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "engine"))
sys.path.insert(0, ENGINE_DIR)

import llm_client
from llm_client import LLMClient, BudgetExhaustedError, NoLocalModelError


def _models(*names):
    return [{"name": n, "size": 0, "capability_score": llm_client.score_model_capability(n)} for n in names]


class LocalFirstClientTest(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"AUTONOMA_ALLOW_CLOUD": "0"})
        self.env.start()
        self.client = LLMClient()
        self.tmp = tempfile.mkdtemp()
        self.client.ledger_db_path = os.path.join(self.tmp, "office.db")
        self.client.budget_guard_enabled = False

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_cloud_disabled_makes_no_cloud_request(self):
        with mock.patch.object(llm_client.requests, "get") as get, mock.patch.object(llm_client.requests, "post") as post:
            self.assertFalse(self.client.cloud_enabled())
            self.assertEqual(self.client.fetch_groq_models(force_refresh=True), [])
            for c in get.call_args_list + post.call_args_list:
                self.assertNotIn("groq.com", str(c))

    def test_projects_default_to_local_only_while_cloud_disabled(self):
        self.assertTrue(self.client.is_project_local_only("no-such-project"))

    def test_route_uses_first_installed_model_of_role_tier(self):
        with mock.patch.object(self.client, "list_ollama_models", return_value=_models("llama3.1:8b", "gemma3:1b")):
            route = self.client.resolve_route("architect")
        self.assertEqual(route["provider"], "ollama")
        self.assertEqual(route["model"], "llama3.1:8b")
        self.assertFalse(route["downgraded"])

    def test_missing_tier_model_is_recorded_as_downgrade(self):
        with mock.patch.object(self.client, "list_ollama_models", return_value=_models("gemma3:1b")):
            route = self.client.resolve_route("architect")
        self.assertEqual(route["model"], "gemma3:1b")
        self.assertTrue(route["downgraded"])
        self.assertIn("architect", route["downgrade_note"])

    def test_no_local_model_fails_loudly(self):
        with mock.patch.object(self.client, "list_ollama_models", return_value=[]):
            with self.assertRaises(NoLocalModelError):
                self.client.query("hi", role="pm")

    def test_forced_cloud_provider_never_overrides_local_only(self):
        with mock.patch.object(self.client, "list_ollama_models", return_value=_models("gemma3:1b")), \
                mock.patch.object(self.client, "_execute_ollama_call", return_value={
                    "text": "ok", "usage": {"prompt_tokens": 1, "completion_tokens": 1}, "request_ms": 5}) as local, \
                mock.patch.object(self.client, "_execute_groq_call") as cloud:
            self.client.query("hi", role="pm", force_provider="groq", force_model="openai/gpt-oss-120b")
        cloud.assert_not_called()
        local.assert_called_once()

    def test_judge_prefers_a_different_model_that_is_not_weaker(self):
        with mock.patch.object(self.client, "list_ollama_models", return_value=_models("llama3.1:8b", "qwen2.5:7b")):
            judge = self.client.resolve_judge_route("designer")
        self.assertEqual(judge["generator_model"], "qwen2.5:7b")
        self.assertEqual(judge["model"], "llama3.1:8b")
        self.assertFalse(judge["same_model_as_author"])
        self.assertFalse(judge["weaker_than_author"])

    def test_judge_weaker_than_author_is_degraded(self):
        router = {"tiers": {"high": [{"provider": "ollama", "model": "gemma3:1b"}],
                            "medium": [{"provider": "ollama", "model": "qwen2.5:7b"}]},
                  "roles": {"judge": "high", "designer": "medium"}}
        with mock.patch.object(llm_client, "load_router", return_value=router), \
                mock.patch.object(self.client, "list_ollama_models", return_value=_models("gemma3:1b", "qwen2.5:7b")), \
                mock.patch.object(self.client, "_execute_ollama_call", return_value={
                    "text": "{}", "usage": {"prompt_tokens": 1, "completion_tokens": 1}, "request_ms": 5}):
            res = self.client.query("score", role="judge", target_role="designer")
        self.assertTrue(res["judge_weaker_than_author"])
        self.assertTrue(res["is_degraded"])

    def test_cloud_failure_tries_next_cloud_model_then_local(self):
        router = {"cloud_enabled": True,
                  "tiers": {"high": [{"provider": "groq", "model": "big"}, {"provider": "groq", "model": "mid"},
                                     {"provider": "ollama", "model": "gemma3:1b"}]},
                  "roles": {"backend": "high"}}
        ok = {"text": "ok", "usage": {"prompt_tokens": 1, "completion_tokens": 1}, "request_ms": 1}
        with mock.patch.object(llm_client, "load_router", return_value=router), \
                mock.patch.object(self.client, "cloud_enabled", return_value=True), \
                mock.patch.object(self.client, "is_project_local_only", return_value=False), \
                mock.patch.object(self.client, "fetch_groq_models", return_value=[{"id": "big"}, {"id": "mid"}]), \
                mock.patch.object(self.client, "list_ollama_models", return_value=_models("gemma3:1b")), \
                mock.patch.object(self.client, "log_fallback"):
            with mock.patch.object(self.client, "_execute_groq_call", side_effect=[RuntimeError("429 big"), dict(ok)]):
                res = self.client.query("hi", role="backend", session_id="s1")
            self.assertEqual(res["cloud_models_skipped"], ["big"])
            self.assertFalse(res["is_degraded"])
            with mock.patch.object(self.client, "_execute_groq_call", side_effect=RuntimeError("429")), \
                    mock.patch.object(self.client, "_execute_ollama_call", return_value=dict(ok)) as local:
                res = self.client.query("hi", role="backend", session_id="s1")
            local.assert_called_once()
            self.assertTrue(res["is_degraded"])

    def test_rate_tracker_learns_limits_and_plans_waits(self):
        rt = llm_client.RateTracker()
        rt.learn_from_429("q", 'Rate limit reached ... on output tokens per minute (OTPM): Limit 1000, Used 863')
        self.assertEqual(rt.max_output("q", 1500), 900)
        rt.record_call("q", 800)
        self.assertGreater(rt.wait_needed("q", 100, 500), 50)   # 800 + 500 > 1000 within the minute
        self.assertEqual(rt.wait_needed("q", 100, 150), 0.0)    # still fits
        rt.update_from_headers("q", {"x-ratelimit-remaining-tokens": "100", "x-ratelimit-reset-tokens": "7.5s"})
        self.assertAlmostEqual(rt.wait_needed("q", 300, 100), 7.5, delta=0.5)
        self.assertEqual(llm_client.parse_duration_s("1m2.5s"), 62.5)
        self.assertEqual(llm_client.parse_duration_s("120ms"), 0.12)

    def test_busy_model_work_moves_to_idle_sibling_in_tier(self):
        router = {"cloud_enabled": True,
                  "tiers": {"medium": [{"provider": "groq", "model": "busy"}, {"provider": "groq", "model": "idle"}]},
                  "roles": {"pm": "medium"}}
        with mock.patch.object(llm_client, "load_router", return_value=router), \
                mock.patch.object(self.client, "cloud_enabled", return_value=True), \
                mock.patch.object(self.client, "is_project_local_only", return_value=False), \
                mock.patch.object(self.client, "fetch_groq_models", return_value=[{"id": "busy"}, {"id": "idle"}]), \
                mock.patch.object(self.client, "list_ollama_models", return_value=[]):
            self.client.rates.learn_from_429("busy", "(OTPM): Limit 1000")
            self.client.rates.record_call("busy", 1000)
            model, wait = self.client._plan_cloud_model("pm", "s1", "busy", "medium", 100, 500, [])
        self.assertEqual((model, wait), ("idle", 0.0))

    def test_daily_quota_moves_work_to_another_model_of_the_tier(self):
        router = {"cloud_enabled": True,
                  "tiers": {"medium": [{"provider": "groq", "model": "qwen"}, {"provider": "groq", "model": "oss20"},
                                       {"provider": "ollama", "model": "gemma3:1b"}]},
                  "roles": {"pm": "medium"}}
        ok = {"text": "ok", "usage": {"prompt_tokens": 1, "completion_tokens": 1}, "request_ms": 1}
        calls = []

        def groq(prompt, system, model, *a, **k):
            calls.append(model)
            if model == "qwen":
                self.client.rates.block("qwen", 400)
                raise llm_client.DailyQuotaError("daily quota", 400)
            return dict(ok)

        with mock.patch.object(llm_client, "load_router", return_value=router), \
                mock.patch.object(self.client, "cloud_enabled", return_value=True), \
                mock.patch.object(self.client, "is_project_local_only", return_value=False), \
                mock.patch.object(self.client, "fetch_groq_models", return_value=[{"id": "qwen"}, {"id": "oss20"}]), \
                mock.patch.object(self.client, "list_ollama_models", return_value=_models("gemma3:1b")), \
                mock.patch.object(self.client, "_execute_groq_call", side_effect=groq), \
                mock.patch.object(llm_client.time, "sleep") as slept:
            res = self.client.query("hi", role="pm", session_id="s1")
            again = self.client.query("hi", role="pm", session_id="s1")  # qwen is still blocked: go straight to oss20
        self.assertEqual(calls, ["qwen", "oss20", "oss20"])
        self.assertFalse(res["is_degraded"])
        self.assertFalse(again["is_degraded"])
        slept.assert_not_called()

    def test_offline_machine_waits_for_network_instead_of_degrading(self):
        states = iter([False, False, False, True])  # initial check, then two 15 s waits
        with mock.patch.object(llm_client, "network_available", side_effect=lambda host: next(states)), \
                mock.patch.object(llm_client.time, "sleep"):
            waited = llm_client.wait_for_network("api.groq.com", max_s=120, step_s=15)
        self.assertEqual(waited, 30)

    def _two_tier_router(self, allow_down):
        return {"cloud_enabled": True, "allow_tier_downgrade": allow_down, "max_quota_wait_s": 600,
                "tiers": {"high": [{"provider": "groq", "model": "big-120b"}],
                          "medium": [{"provider": "groq", "model": "small-27b"}]},
                "roles": {"architect": "high", "judge": "high", "pm": "medium"}}

    def _cloud_patches(self, router, groq_side_effect):
        return [mock.patch.object(llm_client, "load_router", return_value=router),
                mock.patch.object(self.client, "cloud_enabled", return_value=True),
                mock.patch.object(self.client, "is_project_local_only", return_value=False),
                mock.patch.object(self.client, "fetch_groq_models", return_value=[{"id": "big-120b"}, {"id": "small-27b"}]),
                mock.patch.object(self.client, "list_ollama_models", return_value=[]),
                mock.patch.object(self.client, "_execute_groq_call", side_effect=groq_side_effect),
                mock.patch.object(llm_client.time, "sleep")]

    def test_no_silent_tier_downgrade_waits_for_quota(self):
        ok = {"text": "ok", "usage": {"prompt_tokens": 1, "completion_tokens": 1}, "request_ms": 1}
        calls = []

        def groq(prompt, system, model, *a, **k):
            calls.append(model)
            if len(calls) == 1:
                raise llm_client.DailyQuotaError("daily quota", 30)
            return dict(ok)
        ps = self._cloud_patches(self._two_tier_router(False), groq)
        for p in ps:
            p.start()
        try:
            res = self.client.query("hi", role="architect", session_id="s1")
        finally:
            for p in ps:
                p.stop()
        self.assertEqual(calls, ["big-120b", "big-120b"])   # waited, never sent to the weaker tier
        self.assertFalse(res.get("downgraded", False))

    def test_judge_answered_by_weaker_model_is_degraded(self):
        ok = {"text": "{}", "usage": {"prompt_tokens": 1, "completion_tokens": 1}, "request_ms": 1}

        def groq(prompt, system, model, *a, **k):
            if model == "big-120b":
                raise RuntimeError("HTTP 500")
            return {**ok, "model": model}
        ps = self._cloud_patches(self._two_tier_router(True), groq)
        for p in ps:
            p.start()
        try:
            res = self.client.query("score", role="judge", target_role="architect", session_id="s1")
        finally:
            for p in ps:
                p.stop()
        self.assertEqual(res["model"], "small-27b")
        self.assertTrue(res["downgraded"])
        self.assertTrue(res["is_degraded"])   # a 27B judge may not pass a 120B-tier author

    def test_ollama_context_window_fits_the_prompt(self):
        with mock.patch.object(self.client, "ollama_context_length", return_value=32768):
            self.assertEqual(self.client._num_ctx_for("m", "s" * 9000, "p" * 9000, 1000), 8192)
            self.assertEqual(self.client._num_ctx_for("m", "", "short", 500), 4096)
        with mock.patch.object(self.client, "ollama_context_length", return_value=8192):
            with self.assertRaises(RuntimeError):
                self.client._num_ctx_for("m", "", "p" * 60000, 500)

    def test_ledger_row_records_request_time_and_wait_separately(self):
        self.client.set_fake_responder(lambda **kw: "hello world")
        self.client.query("prompt text", role="pm", session_id="proj-x", task_id="t1")
        conn = sqlite3.connect(self.client.ledger_db_path)
        rows = conn.execute("SELECT project_id, agent_id, task_id, provider, latency_ms, wait_ms FROM llm_calls").fetchall()
        conn.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][:4], ("proj-x", "pm", "t1", "fake"))
        self.assertGreaterEqual(rows[0][4], 0)
        self.assertEqual(rows[0][5], 0)


class BudgetHardStopTest(unittest.TestCase):
    def setUp(self):
        import budget
        self.budget = budget
        self.tmp = tempfile.mkdtemp()
        self.projects = os.path.join(self.tmp, "projects")
        self.session = "budget-proj"
        os.makedirs(os.path.join(self.projects, self.session, "docs"))
        with open(os.path.join(self.projects, self.session, "intake.json"), "w") as f:
            json.dump({"budget": "1000 tokens"}, f)
        self.db = os.path.join(self.tmp, "office.db")
        import token_ledger
        token_ledger.record_llm_call(self.session, "pm", "m", 900, 200, db_path=self.db)
        self.patches = [mock.patch.object(budget, "DATA_PROJECTS_DIR", self.projects),
                        mock.patch.object(budget, "DEFAULT_DB_PATH", self.db),
                        mock.patch.object(llm_client, "DATA_PROJECTS_DIR", self.projects)]
        for p in self.patches:
            p.start()
        self.real_guard = budget.check_budget_guard
        self.guard = mock.patch.object(budget, "check_budget_guard",
                                       side_effect=lambda sid, **kw: self.real_guard(sid, db_path=self.db))
        self.guard.start()

    def tearDown(self):
        self.guard.stop()
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_call_refused_at_100_percent_and_resumes_after_raise(self):
        client = LLMClient()
        client.ledger_db_path = self.db
        client.set_fake_responder(lambda **kw: "ok")
        with self.assertRaises(BudgetExhaustedError):
            client.query("hi", role="pm", session_id=self.session)
        self.budget.raise_budget(self.session, budget_limit_tokens=10_000, note="client approved more")
        res = client.query("hi", role="pm", session_id=self.session)
        self.assertEqual(res["text"], "ok")


if __name__ == "__main__":
    unittest.main()
