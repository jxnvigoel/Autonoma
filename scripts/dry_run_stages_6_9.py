#!/usr/bin/env python3
"""
Dry run of Stages 6-9 end to end (Handbook 30.1 fake provider, 33.3 "a to-do app with login").

Isolation: a fresh temporary root with its own data/projects and office.db; the real project
data and ledger are never touched. Nothing leaves the machine: model replies come from a
scripted fake provider, and the only network traffic is to the preview on 127.0.0.1.

Inputs: the pre-build documents (PRD, architecture, OpenAPI, schema, app flow, backlog, team plan)
are a HAND-WRITTEN FIXTURE, labelled as such, standing in for Stages 1-5.
Real: Gate 2 + readiness checks, git repo and worktrees, every CI / unit-test run, Tech Lead code
rules, QA regression runs, the HTTP preview with seed data, rollback and backup/restore drills,
Gates 3 and 4, and the delivery bundle.

Scripted failures prove the loops: red CI (ST-002 r1), a Tech Lead blocker (ST-002 r2),
a QA bug with evidence (ST-003), and a UAT bug at Gate 3 that re-enters the build (ST-004).

Usage: python3 scripts/dry_run_stages_6_9.py [--keep] [--root DIR]
"""

import os
import re
import sys
import json
import shutil
import argparse
import tempfile
from collections import defaultdict

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "engine"))

FIXTURE_NOTE = "<!-- Seeded dry-run fixture: hand-written test input standing in for Stages 1-5, not agent output -->"
SID = "dryrun-todo"

# ----------------------------------------------------------------------------- fixture docs

PRD = FIXTURE_NOTE + """
# PRD: Todo with Login

## Features

### F-001: Sign in
- **Priority**: Must-have
- Story: As a [P-1] I want to sign in so that my to-dos are private. [Q-001]
- AC-001: Given a registered user, when they log in with the right password, then they get 200 and a session token.
- AC-002: Given a registered user, when they log in with a wrong password, then they get 401 and no token.

### F-002: Manage to-dos
- **Priority**: Must-have
- Story: As a [P-1] I want to add to-dos so that I remember tasks. [Q-002]
- AC-003: Given a signed-in user, when they create a to-do with a title, then they get 201 and it appears in their list.
- AC-004: Given a signed-in user, when they create a to-do with an empty title, then they get 400 and nothing is stored.
"""

ARCH = FIXTURE_NOTE + """
# Architecture: Todo with Login

Stack: Python standard library (http.server, sqlite3, hashlib, unittest) [ADR-001].

## API
- API-001: GET /health — liveness and database check.
- API-002: POST /api/v1/auth/signup and POST /api/v1/auth/login — sessions (F-001).
- API-003: POST /api/v1/todos — create a to-do (F-002).
- API-004: GET /api/v1/todos — list own to-dos (F-002).

## Tables
- TBL-01: users (id, email, password_hash, salt).
- TBL-02: todos (id, user_id, title, created_at).
- TBL-03: sessions (token, user_id).

## Team plan
| Role | Count | Work |
|---|---|---|
| devops | 1 | ST-001 walking skeleton [ADR-001] |
| backend | 1 | F-001, F-002 |
"""

OPENAPI = FIXTURE_NOTE.replace("<!--", "#").replace("-->", "") + """
openapi: 3.0.3
info: {title: Todo with Login, version: 1.0.0}
paths:
  /health: {get: {operationId: API-001}}
  /api/v1/auth/login: {post: {operationId: API-002}}
  /api/v1/todos: {post: {operationId: API-003}, get: {operationId: API-004}}
"""

SCHEMA = FIXTURE_NOTE + """
# Schema
- TBL-01 users: id INTEGER PK, email TEXT UNIQUE, password_hash TEXT, salt TEXT
- TBL-02 todos: id INTEGER PK, user_id INTEGER FK users.id, title TEXT NOT NULL, created_at TEXT
- TBL-03 sessions: token TEXT PK, user_id INTEGER FK users.id
"""

APP_FLOW = FIXTURE_NOTE + """
# App flow
- J-001: Sign in (F-001, AC-001, AC-002).
- J-002: Add a to-do (F-002, AC-003, AC-004).
"""

BACKLOG = {"stories": [
    {"id": "ST-001", "title": "Walking skeleton: server, health check, database, seed, backup",
     "role": "devops", "owner": "devops-1", "points": 2,
     "refs": {"features": ["F-001", "F-002"], "ac": [], "api": ["API-001"], "tables": ["TBL-01"]},
     "depends_on": [], "needs_perf": False,
     "definition_of_done": ["GET /health returns 200", "CI green", "Tech Lead approved"]},
    {"id": "ST-002", "title": "Sign up and log in", "role": "backend", "owner": "be-1", "points": 3,
     "refs": {"features": ["F-001"], "ac": ["AC-001", "AC-002"], "api": ["API-002"], "tables": ["TBL-01", "TBL-03"]},
     "depends_on": ["ST-001"], "needs_perf": False,
     "definition_of_done": ["AC-001 and AC-002 have passing tests", "Tech Lead approved"]},
    {"id": "ST-003", "title": "Create and list to-dos", "role": "backend", "owner": "be-1", "points": 3,
     "refs": {"features": ["F-002"], "ac": ["AC-003", "AC-004"], "api": ["API-003", "API-004"], "tables": ["TBL-02"]},
     "depends_on": ["ST-002"], "needs_perf": True,
     "definition_of_done": ["AC-003 and AC-004 have passing tests", "Tech Lead approved"]},
]}

TEAM_PLAN = {"seats": [
    {"id": "ROLE-01", "role": "devops", "count": 1, "from_week": 1, "to_week": 2, "why": "ST-001 [ADR-001]", "refs": ["ADR-001"]},
    {"id": "ROLE-02", "role": "backend", "count": 1, "from_week": 1, "to_week": 2, "why": "F-001, F-002", "refs": ["F-001", "F-002"]},
    {"id": "ROLE-03", "role": "qa", "count": 1, "from_week": 1, "to_week": 2, "why": "AC-001..AC-004", "refs": ["F-001", "F-002"]},
], "timeline_weeks": 2, "notes": ["dry-run fixture"]}

# ----------------------------------------------------------------------------- product code written by the scripted developer

DB_PY = '''import os
import sqlite3


def data_dir():
    d = os.environ.get("APP_DATA_DIR") or os.path.join(os.getcwd(), ".data")
    os.makedirs(d, exist_ok=True)
    return d


def db_path():
    return os.path.join(data_dir(), "app.db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, salt TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id));
CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), title TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE INDEX IF NOT EXISTS idx_todos_user ON todos(user_id, id);
"""


def connect():
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn
'''

APP_V1 = '''import json

from src import db


def problem(status, title, detail=""):
    return status, {"type": "about:blank", "title": title, "status": status, "detail": detail}


def handle(method, path, headers=None, body=b""):
    if method == "GET" and path == "/health":
        conn = db.connect()
        conn.execute("SELECT 1")
        conn.close()
        return 200, {"status": "ok"}
    return problem(404, "Not Found")
'''

SERVER_PY = '''import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from src import app


class Handler(BaseHTTPRequestHandler):
    def _dispatch(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        status, payload = app.handle(self.command, self.path, dict(self.headers), body)
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = _dispatch
    do_POST = _dispatch

    def log_message(self, fmt, *args):
        print(fmt % args, flush=True)


def main():
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
'''

SEED_V1 = '''from src import db

if __name__ == "__main__":
    db.connect().close()
    print("seeded: schema only")
'''

BACKUP_PY = '''import os
import sqlite3

from src import db

if __name__ == "__main__":
    target_dir = os.environ.get("BACKUP_DIR") or os.path.join(db.data_dir(), "backups")
    os.makedirs(target_dir, exist_ok=True)
    src = db.connect()
    dst = sqlite3.connect(os.path.join(target_dir, "app.db.bak"))
    src.backup(dst)
    dst.close()
    src.close()
    print("backup written")
'''

RESTORE_PY = '''import os
import sqlite3

from src import db

if __name__ == "__main__":
    source_dir = os.environ.get("BACKUP_DIR") or os.path.join(db.data_dir(), "backups")
    src = sqlite3.connect(os.path.join(source_dir, "app.db.bak"))
    dst = db.connect()
    src.backup(dst)
    count = dst.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    dst.close()
    src.close()
    print(f"restored; users={count}")
'''

DOCKERFILE = '''FROM python:3.12.6-slim
WORKDIR /app
COPY src ./src
RUN useradd --create-home app
USER app
ENV HOST=0.0.0.0 PORT=8000 APP_DATA_DIR=/home/app/data
HEALTHCHECK CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["python3", "-m", "src.server"]
'''

TEST_BASE = '''import os
import tempfile
import unittest


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["APP_DATA_DIR"] = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()
'''

TEST_HEALTH = '''from tests.base import AppTestCase
from src import app


class HealthTest(AppTestCase):
    def test_health_returns_200(self):
        # API-001 walking skeleton
        status, body = app.handle("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")

    def test_unknown_route_is_404_problem(self):
        status, body = app.handle("GET", "/nope")
        self.assertEqual(status, 404)
        self.assertEqual(body["status"], 404)
'''

AUTH_BUGGY = '''import hashlib
import secrets

from src import db


def signup(email, password):
    conn = db.connect()
    conn.execute("INSERT INTO users (email, password_hash, salt) VALUES (?, ?, ?)", (email, password, ""))
    conn.commit()
    conn.close()


def login(email, password):
    conn = db.connect()
    row = conn.execute("SELECT id, password_hash FROM users WHERE email = ?", (email,)).fetchone()
    # BUG: compares against the hash of the password, but signup stored the raw password
    if not row or row["password_hash"] != hashlib.sha256(password.encode()).hexdigest():
        conn.close()
        return None
    token = secrets.token_hex(16)
    conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, row["id"]))
    conn.commit()
    conn.close()
    return token
'''

AUTH_PLAINTEXT = AUTH_BUGGY.replace(
    "    # BUG: compares against the hash of the password, but signup stored the raw password\n"
    "    if not row or row[\"password_hash\"] != hashlib.sha256(password.encode()).hexdigest():",
    "    if not row or row[\"password_hash\"] != password:")

AUTH_GOOD = '''import hashlib
import hmac
import secrets

from src import db


def _hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()


def signup(email, password):
    salt = secrets.token_hex(16)
    conn = db.connect()
    conn.execute("INSERT INTO users (email, password_hash, salt) VALUES (?, ?, ?)", (email, _hash(password, salt), salt))
    conn.commit()
    conn.close()


def login(email, password):
    conn = db.connect()
    row = conn.execute("SELECT id, password_hash, salt FROM users WHERE email = ?", (email,)).fetchone()
    if not row or not hmac.compare_digest(row["password_hash"], _hash(password, row["salt"])):
        conn.close()
        return None
    token = secrets.token_hex(16)
    conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, row["id"]))
    conn.commit()
    conn.close()
    return token


def user_for_token(token):
    conn = db.connect()
    row = conn.execute("SELECT user_id FROM sessions WHERE token = ?", (token or "",)).fetchone()
    conn.close()
    return row["user_id"] if row else None
'''

AUTH_CASE_INSENSITIVE = AUTH_GOOD.replace(
    'def signup(email, password):\n    salt',
    'def signup(email, password):\n    email = email.strip().lower()\n    salt').replace(
    'def login(email, password):\n    conn',
    'def login(email, password):\n    email = email.strip().lower()\n    conn')

APP_V2 = '''import json

from src import auth, db


def problem(status, title, detail=""):
    return status, {"type": "about:blank", "title": title, "status": status, "detail": detail}


def _json(body):
    try:
        return json.loads(body or b"{}")
    except ValueError:
        return None


def handle(method, path, headers=None, body=b""):
    if method == "GET" and path == "/health":
        conn = db.connect()
        conn.execute("SELECT 1")
        conn.close()
        return 200, {"status": "ok"}
    if method == "POST" and path in ("/api/v1/auth/signup", "/api/v1/auth/login"):
        data = _json(body)
        if not data or not data.get("email") or not data.get("password"):
            return problem(400, "Bad Request", "email and password are required")
        if path.endswith("signup"):
            auth.signup(data["email"], data["password"])
            return 201, {"email": data["email"]}
        token = auth.login(data["email"], data["password"])
        if not token:
            return problem(401, "Unauthorized", "wrong email or password")
        return 200, {"token": token}
    return problem(404, "Not Found")
'''

TODOS_ROUTES = '''
    if path == "/api/v1/todos":
        user_id = auth.user_for_token((headers or {}).get("Authorization", "").replace("Bearer ", ""))
        if not user_id:
            return problem(401, "Unauthorized")
        conn = db.connect()
        try:
            if method == "GET":
                rows = conn.execute("SELECT id, title FROM todos WHERE user_id = ? ORDER BY id LIMIT 100", (user_id,)).fetchall()
                return 200, {"items": [dict(r) for r in rows]}
            if method == "POST":
                data = _json(body) or {}
                title = data.get("title", "")
                __VALIDATION__cur = conn.execute("INSERT INTO todos (user_id, title) VALUES (?, ?)", (user_id, title))
                conn.commit()
                return 201, {"id": cur.lastrowid, "title": title}
        finally:
            conn.close()
    return problem(404, "Not Found")
'''
VALIDATION = ('if not isinstance(title, str) or not title.strip():\n'
              '                    return problem(400, "Bad Request", "title must not be empty")\n                ')
APP_V3_BUGGY = APP_V2.replace('    return problem(404, "Not Found")\n', TODOS_ROUTES.replace("__VALIDATION__", ""), 1)
APP_V3_FIXED = APP_V2.replace('    return problem(404, "Not Found")\n', TODOS_ROUTES.replace("__VALIDATION__", VALIDATION), 1)

SEED_V2 = '''from src import auth, db

if __name__ == "__main__":
    conn = db.connect()
    exists = conn.execute("SELECT 1 FROM users WHERE email = 'demo@example.com'").fetchone()
    conn.close()
    if not exists:
        auth.signup("demo@example.com", "demo-password-1")
    print("seeded: demo user")
'''

TEST_AUTH = '''import json

from tests.base import AppTestCase
from src import app


def post(path, payload):
    return app.handle("POST", path, {}, json.dumps(payload).encode())


class AuthTest(AppTestCase):
    def test_ac_001_login_with_right_password_returns_token(self):
        # AC-001
        post("/api/v1/auth/signup", {"email": "a@example.com", "password": "pw-123456"})
        status, body = post("/api/v1/auth/login", {"email": "a@example.com", "password": "pw-123456"})
        self.assertEqual(status, 200)
        self.assertTrue(body["token"])

    def test_ac_002_wrong_password_is_401_without_token(self):
        # AC-002
        post("/api/v1/auth/signup", {"email": "a@example.com", "password": "pw-123456"})
        status, body = post("/api/v1/auth/login", {"email": "a@example.com", "password": "nope"})
        self.assertEqual(status, 401)
        self.assertNotIn("token", body)

    def test_missing_fields_is_400(self):
        status, _ = post("/api/v1/auth/login", {"email": ""})
        self.assertEqual(status, 400)
'''

TEST_TODOS = '''import json

from tests.base import AppTestCase
from src import app


def call(method, path, payload=None, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return app.handle(method, path, headers, json.dumps(payload or {}).encode())


class TodosTest(AppTestCase):
    def sign_in(self):
        call("POST", "/api/v1/auth/signup", {"email": "t@example.com", "password": "pw-123456"})
        return call("POST", "/api/v1/auth/login", {"email": "t@example.com", "password": "pw-123456"})[1]["token"]

    def test_ac_003_create_then_listed(self):
        # AC-003
        token = self.sign_in()
        status, body = call("POST", "/api/v1/todos", {"title": "buy milk"}, token)
        self.assertEqual(status, 201)
        status, listing = call("GET", "/api/v1/todos", token=token)
        self.assertEqual([i["title"] for i in listing["items"]], ["buy milk"])

    def test_ac_004_unauthenticated_create_is_rejected(self):
        # AC-004 (the developer tested the wrong thing: auth, not the empty title)
        status, _ = call("POST", "/api/v1/todos", {"title": "x"})
        self.assertEqual(status, 401)
'''

QA_TEST_ST003 = '''import json

from tests.base import AppTestCase
from src import app


def call(method, path, payload=None, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return app.handle(method, path, headers, json.dumps(payload or {}).encode())


class QATodos(AppTestCase):
    def sign_in(self):
        call("POST", "/api/v1/auth/signup", {"email": "q@example.com", "password": "pw-123456"})
        return call("POST", "/api/v1/auth/login", {"email": "q@example.com", "password": "pw-123456"})[1]["token"]

    def test_tc_003_ac_003_list_is_private(self):
        # TC-003 AC-003: another user's to-dos are not listed
        token = self.sign_in()
        call("POST", "/api/v1/todos", {"title": "mine"}, token)
        call("POST", "/api/v1/auth/signup", {"email": "z@example.com", "password": "pw-123456"})
        other = call("POST", "/api/v1/auth/login", {"email": "z@example.com", "password": "pw-123456"})[1]["token"]
        self.assertEqual(call("GET", "/api/v1/todos", token=other)[1]["items"], [])

    def test_tc_004_ac_004_empty_title_is_400_and_not_stored(self):
        # TC-004 AC-004
        token = self.sign_in()
        for title in ("", "   "):
            status, _ = call("POST", "/api/v1/todos", {"title": title}, token)
            self.assertEqual(status, 400)
        self.assertEqual(call("GET", "/api/v1/todos", token=token)[1]["items"], [])
'''

QA_TEST_ST002 = '''import json

from tests.base import AppTestCase
from src import app


def post(path, payload):
    return app.handle("POST", path, {}, json.dumps(payload).encode())


class QAAuth(AppTestCase):
    def test_tc_001_ac_001_token_is_unique_per_login(self):
        # TC-001 AC-001
        post("/api/v1/auth/signup", {"email": "u@example.com", "password": "pw-123456"})
        t1 = post("/api/v1/auth/login", {"email": "u@example.com", "password": "pw-123456"})[1]["token"]
        t2 = post("/api/v1/auth/login", {"email": "u@example.com", "password": "pw-123456"})[1]["token"]
        self.assertNotEqual(t1, t2)

    def test_tc_002_ac_002_unknown_email_is_401(self):
        # TC-002 AC-002
        status, body = post("/api/v1/auth/login", {"email": "ghost@example.com", "password": "x"})
        self.assertEqual(status, 401)
'''

TEST_UAT = '''import json

from tests.base import AppTestCase
from src import app


def post(path, payload):
    return app.handle("POST", path, {}, json.dumps(payload).encode())


class UATLogin(AppTestCase):
    def test_uat_q_003_email_is_case_insensitive(self):
        # Q-003 UAT: "I signed up as Ana@Example.com and cannot log in as ana@example.com"
        post("/api/v1/auth/signup", {"email": "Ana@Example.com", "password": "pw-123456"})
        status, _ = post("/api/v1/auth/login", {"email": "ana@example.com", "password": "pw-123456"})
        self.assertEqual(status, 200)
'''

# ----------------------------------------------------------------------------- scripted model replies

def tools(*calls):
    return json.dumps({"tool_calls": [{"name": n, "input": i} for n, i in calls]})


def final(**env):
    env.setdefault("status", "done")
    return json.dumps({"final": env})


def w(path, content):
    return ("write_file", {"path": path, "content": content})


RUN_TESTS = tools(("run_tests", {"command": "test"}))

DEV_SCRIPTS = {
    # ST-001 walking skeleton: written, tests run, done.
    "ST-001:build:dev1": [
        tools(w("src/__init__.py", ""), w("src/db.py", DB_PY), w("src/app.py", APP_V1), w("src/server.py", SERVER_PY),
              w("src/seed.py", SEED_V1), w("src/backup.py", BACKUP_PY), w("src/restore.py", RESTORE_PY),
              w("Dockerfile", DOCKERFILE), w("tests/__init__.py", ""), w("tests/base.py", TEST_BASE),
              w("tests/test_health.py", TEST_HEALTH)),
        RUN_TESTS,
        final(artifact="story/ST-001", handoff_note="Skeleton: /health, SQLite WAL, seed, backup/restore, Dockerfile."),
    ],
    # ST-002 round 1: buggy login -> CI red.
    "ST-002:build:dev1": [
        tools(w("src/auth.py", AUTH_BUGGY), w("src/app.py", APP_V2), w("tests/test_auth.py", TEST_AUTH)),
        final(artifact="story/ST-002", handoff_note="Login added (did not run tests)."),
    ],
    # ST-002 round 2: tests green but passwords in plain text -> Tech Lead blocker.
    "ST-002:build:dev2": [
        tools(w("src/auth.py", AUTH_PLAINTEXT)),
        RUN_TESTS,
        final(artifact="story/ST-002", handoff_note="Fixed CI: AC-001, AC-002 pass."),
    ],
    # ST-002 round 3: salted PBKDF2 -> approved.
    "ST-002:build:dev3": [
        tools(w("src/auth.py", AUTH_GOOD), w("src/seed.py", SEED_V2)),
        RUN_TESTS,
        final(artifact="story/ST-002", handoff_note="Passwords hashed with salted PBKDF2; AC-001, AC-002 pass."),
    ],
    # ST-003: missing empty-title validation (the dev test for AC-004 checks the wrong thing).
    "ST-003:build:dev1": [
        tools(w("src/app.py", APP_V3_BUGGY), w("tests/test_todos.py", TEST_TODOS)),
        RUN_TESTS,
        final(artifact="story/ST-003", handoff_note="To-dos create/list; AC-003, AC-004 tests pass."),
    ],
    # ST-003 fix after QA BUG: add validation.
    "ST-003:fix:dev1": [
        tools(w("src/app.py", APP_V3_FIXED)),
        RUN_TESTS,
        final(artifact="fix/ST-003-r1", handoff_note="Empty titles rejected with 400 (AC-004)."),
    ],
    # ST-004 UAT fix.
    "ST-004:build:dev1": [
        tools(w("src/auth.py", AUTH_CASE_INSENSITIVE), w("tests/test_uat_login.py", TEST_UAT)),
        RUN_TESTS,
        final(artifact="story/ST-004", handoff_note="Emails normalised to lower case at signup and login (Q-003)."),
    ],
}

QA_SCRIPTS = {
    "ST-001:qa1": [RUN_TESTS, final(tests=[{"id": "TC-000", "ac": "-", "file": "tests/test_health.py"}], bugs=[])],
    "ST-002:qa1": [tools(w("tests/test_qa_st002.py", QA_TEST_ST002)), RUN_TESTS,
                   final(tests=[{"id": "TC-001", "ac": "AC-001", "file": "tests/test_qa_st002.py"},
                                {"id": "TC-002", "ac": "AC-002", "file": "tests/test_qa_st002.py"}], bugs=[])],
    "ST-003:qa1": [tools(w("tests/test_qa_st003.py", QA_TEST_ST003)), RUN_TESTS,
                   final(tests=[{"id": "TC-003", "ac": "AC-003", "file": "tests/test_qa_st003.py"},
                                {"id": "TC-004", "ac": "AC-004", "file": "tests/test_qa_st003.py"}],
                         bugs=[{"ac": "AC-004", "severity": "major", "steps": ["POST /api/v1/todos with title ''"],
                                "expected": "400", "actual": "201",
                                "evidence": "test_tc_004_ac_004_empty_title_is_400_and_not_stored"},
                               {"ac": "AC-003", "severity": "major", "steps": ["looked at the code"],
                                "expected": "pagination", "actual": "LIMIT 100", "evidence": "my opinion"}])],
    "ST-003:qa2": [RUN_TESTS, final(tests=[{"id": "TC-004", "ac": "AC-004", "file": "tests/test_qa_st003.py"}], bugs=[])],
    "ST-004:qa1": [RUN_TESTS, final(tests=[{"id": "TC-005", "ac": "-", "file": "tests/test_uat_login.py"}], bugs=[])],
}

REVIEW_SCRIPTS = {
    # ST-002's first review (round 1 was red, so this reviews round 2's code) raises a blocker.
    ("ST-002", 1): final(decision="changes_requested", comments=[
        {"file": "src/auth.py", "line": 9, "severity": "blocker", "rule": "checklist:security.passwords",
         "issue": "passwords are stored in plain text", "fix": "hash with a per-user salt (PBKDF2/Argon2id) and compare in constant time"}],
        handoff_note="Blocker on password storage."),
}


class FakeOffice:
    """Scripted fake provider: replies keyed by the agent's task id and tool round (Handbook 30.1)."""

    def __init__(self):
        self.calls = defaultdict(int)
        self.review_counts = defaultdict(int)
        self.unscripted = []

    def __call__(self, prompt, system, role, task_id):
        task_id = task_id or ""
        if task_id == "tech_lead_readiness_review":
            return ("# Pre-Build Readiness Review\n\n1. Building F-001, F-002 via API-001..API-004 [fixture].\n"
                    "2. Gaps: None\n3. Contradictions: None\n7. Verdict: ready\n"
                    '```json\n{"verdict": "ready", "first_milestone": "ST-001", "gaps_count": 0, "contradictions_count": 0}\n```')
        m = re.match(r"^(.*):r(\d+)$", task_id)
        key, rnd = (m.group(1), int(m.group(2))) if m else (task_id, 1)
        sid = key.split(":")[0]
        if role in ("backend", "frontend", "fullstack", "devops", "engineer"):
            script = DEV_SCRIPTS.get(key)
        elif role == "qa":
            script = QA_SCRIPTS.get(key)
        elif role == "tech-lead" and ":review" in key:
            if rnd == 1:
                self.review_counts[sid] += 1
            reply = REVIEW_SCRIPTS.get((sid, self.review_counts[sid]))
            return reply or final(decision="approve", comments=[
                {"file": "src/app.py", "line": 1, "severity": "nit", "rule": "readability",
                 "issue": "module docstring missing", "fix": "add a one-line docstring"}], handoff_note="Approved.")
        elif role == "judge":
            crit = re.findall(r"^- ([a-z0-9_]+) \(max (\d+)", prompt, re.MULTILINE)
            return final(scores=[{"criterion": c, "score": int(mx), "max": int(mx),
                                  "evidence": "diff and passing regression run", "fix": ""} for c, mx in crit],
                         unsupported_claims=[], handoff_note="Meets its ACs.")
        else:
            script = None
        if not script or rnd > len(script):
            self.unscripted.append((role, task_id))
            return final(status="blocked", handoff_note=f"no scripted reply for {task_id}")
        return script[rnd - 1]


# ----------------------------------------------------------------------------- driver

def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text if isinstance(text, str) else json.dumps(text, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="keep the temporary root for inspection")
    ap.add_argument("--root", help="use this directory as the isolated root")
    args = ap.parse_args()

    root = args.root or tempfile.mkdtemp(prefix="autonoma-dryrun-")
    projects = os.path.join(root, "data", "projects")
    db_path = os.path.join(root, "data", "office.db")
    pdir = os.path.join(projects, SID)
    if os.path.exists(pdir):
        shutil.rmtree(pdir)
    os.makedirs(os.path.join(pdir, "docs"), exist_ok=True)

    import llm_client, budget, readiness, workspace, devops, build_loop, release, events
    path_mods = (llm_client, budget, readiness, workspace, devops, build_loop, release, events)
    db_mods = (budget, readiness, build_loop, release, events)
    saved = ([(m, "DATA_PROJECTS_DIR", m.DATA_PROJECTS_DIR) for m in path_mods] +
             [(m, "DEFAULT_DB_PATH", m.DEFAULT_DB_PATH) for m in db_mods])
    saved_env = os.environ.get("AUTONOMA_ALLOW_CLOUD")
    client = llm_client.default_llm_client
    listener = events.llm_call_listener(db_path)
    for m in path_mods:
        m.DATA_PROJECTS_DIR = projects
    for m in db_mods:
        m.DEFAULT_DB_PATH = db_path
    os.environ["AUTONOMA_ALLOW_CLOUD"] = "0"
    fake = FakeOffice()
    client.set_fake_responder(fake)
    client.ledger_db_path = db_path
    client.add_call_listener(listener)
    try:
        return run_dry_run(root, projects, db_path, pdir, fake, args)
    finally:
        for m, attr, val in saved:
            setattr(m, attr, val)
        if saved_env is None:
            os.environ.pop("AUTONOMA_ALLOW_CLOUD", None)
        else:
            os.environ["AUTONOMA_ALLOW_CLOUD"] = saved_env
        client.set_fake_responder(None)
        client.ledger_db_path = None
        if listener in client._call_listeners:
            client._call_listeners.remove(listener)


def run_dry_run(root, projects, db_path, pdir, fake, args):
    import budget, readiness, workspace, devops, build_loop, release, events

    write(os.path.join(pdir, "intake.json"), {"project_name": "Todo with Login (dry run)", "budget": "500000 tokens"})
    write(os.path.join(pdir, "session_state.json"), {"local_only": True})
    write(os.path.join(pdir, "qa_log.json"), [
        {"id": "Q-001", "question": "Who uses it?", "answer": "Individuals who want private to-do lists."},
        {"id": "Q-002", "question": "What must v1 do?", "answer": "Sign in and add to-dos."}])
    docs = os.path.join(pdir, "docs")
    for name, text in (("prd.md", PRD), ("architecture.md", ARCH), ("openapi.yaml", OPENAPI), ("schema.md", SCHEMA),
                       ("app-flow.md", APP_FLOW), ("staffing-report.md", FIXTURE_NOTE + "\n# Staffing report (fixture)\n")):
        write(os.path.join(docs, name), text)
    write(os.path.join(docs, "backlog.json"), BACKLOG)
    write(os.path.join(docs, "team-plan.json"), TEAM_PLAN)
    write(os.path.join(docs, "estimate.json"), {"total_estimated_tokens": 500000, "fixture": True})

    results = {}

    def step(name, value):
        results[name] = value
        print(f"[{name}] {json.dumps(value, default=str)[:300]}")
        return value

    # Gate 2 and readiness go through their real checks.
    from fastapi import HTTPException
    try:
        build_loop_blocked = None
        budget.enforce_gate2_server_side(SID, db_path=db_path)
    except HTTPException as e:
        build_loop_blocked = e.detail
    step("gate2_locked_before_approval", bool(build_loop_blocked))
    budget.approve_gate2(SID, client_notes="dry run", db_path=db_path)
    budget.enforce_gate2_server_side(SID, db_path=db_path)
    rv = readiness.run_readiness_review(SID, db_path=db_path)
    step("readiness", {"verdict": rv["verdict"], "gaps": rv["gaps"], "contradictions": rv["contradictions"]})
    readiness.enforce_readiness_server_side(SID, db_path=db_path)

    prop = devops.propose_allowlist(SID, projects)
    step("allowlist_proposed", {"stack": prop["stack"], "commands": prop["commands"], "problems": prop["problems"]})
    try:
        build_loop.BuildLoop(SID, projects, db_path).prepare()
        step("build_refused_without_allowlist", False)
    except RuntimeError as e:
        step("build_refused_without_allowlist", str(e))
    devops.approve_allowlist(SID, projects_dir=projects)

    # Stage 6-7
    summary = build_loop.BuildLoop(SID, projects, db_path).run()
    step("build_1", {"status": summary["status"], "counts": summary["counts"]})

    # Stage 8: Beta -> UAT bug -> back to Stage 6 -> Beta again -> approve
    g3 = release.start_beta(SID, projects, db_path)
    step("gate3_opened", {"status": g3["status"], "preview": g3["details"]["preview"], "issues": g3["details"]["known_issues"]})
    fb = release.uat_feedback(SID, "I signed up as Ana@Example.com and cannot log in as ana@example.com", "bug",
                              projects, db_path)
    step("uat_feedback", {"q": fb["q_id"], "story": fb.get("story", {}).get("id")})
    summary2 = build_loop.BuildLoop(SID, projects, db_path).run()
    step("build_2_after_uat", {"status": summary2["status"], "counts": summary2["counts"]})
    g3b = release.start_beta(SID, projects, db_path)
    step("gate3_reopened", {"status": g3b["status"], "issues": g3b["details"]["known_issues"]})
    release.decide_gate(SID, 3, True, "UAT passed", projects, db_path)

    # Stage 9
    try:
        release.deliver(SID, projects, db_path)
        step("deliver_refused_before_gate4", False)
    except HTTPException as e:
        step("deliver_refused_before_gate4", e.status_code)
    g4 = release.prepare_release(SID, "v1.0.0", projects, db_path)
    step("gate4_opened", {"status": g4["status"], "checks": g4["details"]["checks"]})
    release.decide_gate(SID, 4, True, "go live", projects, db_path)
    delivered = release.deliver(SID, projects, db_path)
    step("delivered", {"path": delivered["path"], "files": delivered["files"]})

    # Evidence
    state = build_loop.get_build_state(SID, projects)
    hist = {sid: [(h["kind"], h.get("round"), h.get("green", h.get("decision", h.get("passed", h.get("pass")))))
                  for h in s.get("history", [])] for sid, s in state["stories"].items()}
    step("story_histories", hist)
    step("bugs", [(b["id"], b.get("ac"), b.get("evidence")) for b in state.get("bugs", [])])
    repo = workspace.repo_path(SID, projects)
    step("main_log", [c["subject"] for c in workspace.log(repo, 40)])
    _, remotes = workspace.git(["remote"], repo)
    step("git_remotes", remotes.strip() or "none")
    step("unscripted_calls", fake.unscripted)
    ev = events.list_events(SID, db_path=db_path, limit=5000)
    kinds = defaultdict(int)
    for e in ev:
        kinds[e["type"]] += 1
    step("event_counts", dict(kinds))

    expected = {
        "ST-001": "done", "ST-002": "done", "ST-003": "done_perf_not_run", "ST-004": "done",
    }
    actual = {sid: s["status"] for sid, s in state["stories"].items()}
    ok = (actual == expected and results["readiness"]["verdict"] == "ready" and results["gate2_locked_before_approval"]
          and isinstance(results["build_refused_without_allowlist"], str) and results["deliver_refused_before_gate4"] == 403
          and results["git_remotes"] == "none" and not fake.unscripted
          and any(b[2] and "empty_title" in b[2] for b in results["bugs"])
          and ("ci", 1, False) in hist["ST-002"] and ("review", None, "changes_requested") in hist["ST-002"])
    print("\nDRY RUN", "PASSED" if ok else "FAILED", f"— stories {actual}")
    print(f"Isolated root: {root}")
    devops.stop_preview(SID, projects)
    if not args.keep and not args.root:
        shutil.rmtree(root, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
