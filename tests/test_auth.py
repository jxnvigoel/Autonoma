"""Local accounts: sign up, log in, per-user projects, lockout, profiles, Google linking (isolated temp data)."""

import os
import sys
import json
import shutil
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine"))

from fastapi.testclient import TestClient

import auth
import google_oauth
import main


class AuthTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.projects = os.path.join(self.tmp, "projects")
        for pid in ("old-project-1", "old-project-2"):
            os.makedirs(os.path.join(self.projects, pid))
            with open(os.path.join(self.projects, pid, "intake.json"), "w") as f:
                json.dump({"project_name": pid}, f)
        self.patches = [mock.patch.object(auth, "DEFAULT_DB_PATH", os.path.join(self.tmp, "office.db")),
                        mock.patch.object(auth, "DATA_PROJECTS_DIR", self.projects),
                        mock.patch.object(main, "DATA_PROJECTS_DIR", self.projects)]
        for p in self.patches:
            p.start()
        self.client = TestClient(main.app)

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def hdr(self, token):
        return {"Authorization": f"Bearer {token}"}

    def names(self, token=None):
        r = self.client.get("/ba/sessions", headers=self.hdr(token) if token else {})
        return r.status_code, sorted(s.get("session_id") or s.get("id") for s in (r.json() if r.status_code == 200 else []))

    def test_without_accounts_the_app_works_as_before(self):
        self.assertEqual(self.names(), (200, ["old-project-1", "old-project-2"]))

    def test_first_account_keeps_existing_work_second_starts_fresh(self):
        a = self.client.post("/auth/signup", json={"name": "Ana", "email": "Ana@Example.com", "password": "pw-123456"}).json()
        self.assertEqual(sorted(a["claimed_existing_projects"]), ["old-project-1", "old-project-2"])
        b = self.client.post("/auth/signup", json={"name": "Ben", "email": "ben@example.com", "password": "pw-123456"}).json()
        self.assertEqual(b["claimed_existing_projects"], [])
        self.assertEqual(self.names(a["token"]), (200, ["old-project-1", "old-project-2"]))
        self.assertEqual(self.names(b["token"]), (200, []))
        self.assertEqual(self.names()[0], 401)  # accounts exist now: listing needs a login
        # logging in again brings the old projects back
        again = self.client.post("/auth/login", json={"email": "ana@example.com", "password": "pw-123456"}).json()
        self.assertEqual(self.names(again["token"])[1], ["old-project-1", "old-project-2"])
        # Ben cannot open Ana's project
        self.assertEqual(self.client.get("/ba/session/old-project-1", headers=self.hdr(b["token"])).status_code, 404)

    def test_signup_validation_and_duplicates(self):
        self.assertEqual(self.client.post("/auth/signup", json={"name": "A", "email": "bad", "password": "pw-123456"}).status_code, 400)
        self.assertEqual(self.client.post("/auth/signup", json={"name": "A", "email": "a@x.io", "password": "short"}).status_code, 400)
        self.client.post("/auth/signup", json={"name": "A", "email": "a@x.io", "password": "pw-123456"})
        self.assertEqual(self.client.post("/auth/signup", json={"name": "A", "email": "a@x.io", "password": "pw-123456"}).status_code, 409)

    def test_wrong_password_lockout(self):
        self.client.post("/auth/signup", json={"name": "A", "email": "a@x.io", "password": "pw-123456"})
        codes = [self.client.post("/auth/login", json={"email": "a@x.io", "password": "nope"}).status_code for _ in range(5)]
        self.assertEqual(codes, [401] * 5)
        self.assertEqual(self.client.post("/auth/login", json={"email": "a@x.io", "password": "pw-123456"}).status_code, 423)

    def test_profile_and_logout(self):
        tok = self.client.post("/auth/signup", json={"name": "A", "email": "a@x.io", "password": "pw-123456"}).json()["token"]
        p = self.client.put("/auth/profile", json={"title": "Founder", "organization": "TaskNest"}, headers=self.hdr(tok)).json()
        self.assertEqual((p["title"], p["organization"], p["project_count"]), ("Founder", "TaskNest", 2))
        self.client.post("/auth/logout", headers=self.hdr(tok))
        self.assertIsNone(self.client.get("/auth/me", headers=self.hdr(tok)).json()["user"])

    def test_google_sign_in(self):
        with mock.patch.dict(os.environ, {"GOOGLE_CLIENT_ID": "", "GOOGLE_CLIENT_SECRET": ""}), \
                mock.patch.object(google_oauth, "load_dotenv"):
            self.assertEqual(self.client.get("/auth/google/start").status_code, 503)
        g = auth.login_or_create_google_user("google-sub-1", "Gia@Gmail.com", "Gia")
        self.assertEqual(g["user"]["auth_method"], "google")
        r = self.client.post("/auth/login", json={"email": "gia@gmail.com", "password": "anything"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Google", r.json()["detail"])
        again = auth.login_or_create_google_user("google-sub-1", "gia@gmail.com", "Gia")
        self.assertEqual(again["user"]["id"], g["user"]["id"])


if __name__ == "__main__":
    unittest.main()
