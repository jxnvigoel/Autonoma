"""Long agent stages run as engine jobs: no duplicates, status survives leaving the screen or restarting."""

import os
import sys
import time
import shutil
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine"))

from fastapi import HTTPException

import jobs


class JobsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "p1"))
        self.p = mock.patch.object(jobs, "DATA_PROJECTS_DIR", self.tmp)
        self.p.start()
        self.release = threading.Event()
        self.calls = []

        def slow(sid):
            self.calls.append(sid)
            self.release.wait(5)
            return {"prd_content": "# PRD", "session_id": sid}

        def broken(sid):
            raise HTTPException(status_code=409, detail="Gate 1 client approval is required")

        jobs.register("slow-test", slow)
        jobs.register("broken-test", broken)

    def tearDown(self):
        self.release.set()
        for t in list(jobs._threads.values()):
            t.join(2)  # let job threads finish before their temp folder goes away
        jobs._threads.clear()
        self.p.stop()
        for k in ("slow-test", "broken-test"):
            jobs._registry.pop(k, None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def wait_for(self, kind, want):
        for _ in range(100):
            st = jobs.status("p1", kind)
            if st["status"] == want:
                return st
            time.sleep(0.02)
        self.fail(f"{kind} never reached {want}: {jobs.status('p1', kind)}")

    def test_second_start_attaches_instead_of_duplicating(self):
        a = jobs.start("p1", "slow-test")
        b = jobs.start("p1", "slow-test")
        self.assertEqual((a["status"], b["status"]), ("running", "running"))
        self.assertEqual(a["started_at"], b["started_at"])
        self.release.set()
        done = self.wait_for("slow-test", "done")
        self.assertEqual(done["result"]["prd_content"], "# PRD")
        self.assertEqual(self.calls, ["p1"])  # ran once

    def test_failure_keeps_the_reason(self):
        jobs.start("p1", "broken-test")
        st = self.wait_for("broken-test", "failed")
        self.assertEqual((st["http_status"], st["error"]), (409, "Gate 1 client approval is required"))

    def test_running_job_lost_by_a_restart_reads_as_interrupted(self):
        jobs.start("p1", "slow-test")
        lost = jobs._threads.pop("p1:slow-test")  # what an engine restart looks like
        self.assertEqual(jobs.status("p1", "slow-test")["status"], "interrupted")
        self.release.set()
        lost.join(2)

    def test_activity_feed_shows_what_the_agent_is_doing(self):
        import llm_client
        client = llm_client.default_llm_client
        client.add_call_listener(jobs.on_llm_call)
        client.set_fake_responder(lambda **kw: "ok")
        seen_running = []

        def stage(sid):
            client.query(prompt="x", role="pm", session_id=sid, task_id="prd_sec_5_F-003")
            seen_running.append(jobs.status(sid, "feed-test")["current"])
            client.query(prompt="x", role="judge", session_id=sid, task_id="judge_prd_1")
            return {"ok": True}

        jobs.register("feed-test", stage)
        try:
            with mock.patch.object(client, "ledger_db_path", os.path.join(self.tmp, "office.db")):
                jobs.start("p1", "feed-test")
                st = self.wait_for("feed-test", "done")
        finally:
            client.set_fake_responder(None)
            client._call_listeners.remove(jobs.on_llm_call)
            jobs._registry.pop("feed-test", None)
        labels = [(a["phase"], a["label"]) for a in st["activity"]]
        self.assertEqual(labels, [("start", "Writing feature spec F-003 (stories and acceptance criteria)"),
                                  ("done", "Writing feature spec F-003 (stories and acceptance criteria)"),
                                  ("start", "Judge is reviewing the PRD against the rubric"),
                                  ("done", "Judge is reviewing the PRD against the rubric")])
        self.assertEqual((st["stats"]["calls"], st["current"]), (2, None))
        self.assertEqual(seen_running, [None])  # between calls nothing is in flight

    def test_unknown_job_and_project(self):
        with self.assertRaises(HTTPException):
            jobs.start("p1", "nope")
        with self.assertRaises(HTTPException):
            jobs.start("missing-project", "slow-test")


class StageRoutesTest(unittest.TestCase):
    """The UI starts stages by job kind; each kind must map to a real engine route."""

    def test_job_registered_before_its_router_still_runs(self):
        # Janvi's engine said "Unknown job 'pm'" because routers were attached after registration.
        from fastapi import APIRouter, FastAPI
        from pydantic import BaseModel

        class Req(BaseModel):
            session_id: str

        app = FastAPI()
        jobs.register_from_routes(app, {"late-test": "/late/start"})
        router = APIRouter()

        @router.post("/late/start")
        def late(req: Req):
            return {"ran_for": req.session_id}

        self.assertEqual(jobs.missing_routes(app, {"late-test": "/late/start"}), ["late-test: /late/start"])
        app.include_router(router)
        self.assertEqual(jobs.missing_routes(app, {"late-test": "/late/start"}), [])
        try:
            self.assertEqual(jobs._registry["late-test"]("p9"), {"ran_for": "p9"})
        finally:
            jobs._registry.pop("late-test", None)

    def test_every_ui_job_kind_is_registered(self):
        import main  # noqa: F401  (registers the jobs)
        ui = ["pm", "feasibility", "architect", "designer", "hr", "recruiter", "scrum", "readiness"]
        self.assertEqual([k for k in ui if k not in jobs.kinds()], [])

    def test_architect_session_reads_the_docs(self):
        import main
        from fastapi.testclient import TestClient

        tmp = tempfile.mkdtemp()
        try:
            docs = os.path.join(tmp, "p1", "docs")
            os.makedirs(os.path.join(docs, "adr"))
            for name, text in (("architecture.md", "# Arch"), ("schema.md", "# Schema"),
                               ("openapi.yaml", "openapi: 3.0.0"), ("adr/ADR-001.md", "# ADR")):
                with open(os.path.join(docs, name), "w") as f:
                    f.write(text)
            with mock.patch.object(main, "DATA_PROJECTS_DIR", tmp):
                client = TestClient(main.app)
                r = client.get("/architect/session/p1").json()
                self.assertEqual((r["has_output"], r["architecture_content"], r["schema_content"],
                                  r["openapi_content"], list(r["adrs"])),
                                 (True, "# Arch", "# Schema", "openapi: 3.0.0", ["ADR-001.md"]))
                self.assertEqual(client.get("/architect/session/no-such-project").status_code, 404)
                self.assertFalse(os.path.exists(os.path.join(tmp, "no-such-project")))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
