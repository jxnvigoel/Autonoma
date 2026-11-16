"""A failed endpoint must tell the screen why (Janvi's "the button does nothing" bug): model-availability
failures keep their own message and status, and even an unexpected crash answers with readable JSON that
carries CORS headers (a bare 500 has none, so the browser could only say "Failed to fetch")."""

import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "engine"))

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import llm_client  # noqa: E402
import main  # noqa: E402

ORIGIN = {"Origin": "http://localhost:5173"}


def make_client() -> TestClient:
    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    main._register_error_handlers(app)

    @app.get("/budget")
    def budget():
        raise llm_client.BudgetExhaustedError("BUDGET EXHAUSTED: 100% budget reached (10 / 5 tokens).")

    @app.get("/nomodel")
    def nomodel():
        raise llm_client.NoLocalModelError("No usable model for 'pm'.")

    @app.get("/quota")
    def quota():
        raise llm_client.DailyQuotaError("Groq daily quota used up", 60.0)

    @app.get("/crash")
    def crash():
        raise KeyError("stories")

    return TestClient(app, raise_server_exceptions=False)


class ErrorHandlerTest(unittest.TestCase):
    def setUp(self):
        self.client = make_client()

    def test_budget_exhausted_is_reported_with_its_message(self):
        res = self.client.get("/budget", headers=ORIGIN)
        self.assertEqual(res.status_code, 402)
        self.assertIn("BUDGET EXHAUSTED", res.json()["detail"])
        self.assertEqual(res.json()["error"], "BudgetExhaustedError")
        self.assertTrue(res.headers.get("access-control-allow-origin"))

    def test_no_model_and_quota_have_their_own_status(self):
        self.assertEqual(self.client.get("/nomodel", headers=ORIGIN).status_code, 503)
        res = self.client.get("/quota", headers=ORIGIN)
        self.assertEqual(res.status_code, 429)
        self.assertIn("daily quota", res.json()["detail"])

    def test_unexpected_crash_is_readable_by_the_browser(self):
        res = self.client.get("/crash", headers=ORIGIN)
        self.assertEqual(res.status_code, 500)
        self.assertIn("KeyError", res.json()["detail"])
        self.assertTrue(res.headers.get("access-control-allow-origin"))

    def test_the_real_engine_has_the_handlers(self):
        self.assertIn(llm_client.BudgetExhaustedError, main.app.exception_handlers)
        self.assertIn(Exception, main.app.exception_handlers)


if __name__ == "__main__":
    unittest.main()
