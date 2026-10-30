"""The Architect's visuals are parsed by code from the documents: nothing invented, nothing dropped."""

import os
import sys
import shutil
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine"))

from fastapi.testclient import TestClient

import architecture_model as am
import main

ARCH = """# TRD

## 3. Tech stack

| Layer | Choice | Alternatives | Decision |
| :--- | :--- | :--- | :--- |
| **Backend** | Flask | Django | [ADR-001] simple |

## 4. Architecture overview

**Pattern:** Monolith.

```mermaid
flowchart TD
    subgraph Client
        Browser[Web Browser]
    end
    subgraph Server [Office PC]
        subgraph App [Python Process]
            API[Flask API<br/>REST]
        end
        DB[(SQLite)]
    end
    Browser -- HTTPS --> API
    API --> DB
```

## 11. Build order

1.  **Walking Skeleton**:
    -   `POST /login` [API-001] [F-001]

## 12. Team plan (for HR)

| Seat | Role | Count | Justification |
| :--- | :--- | :--- | :--- |
| ROLE-01 | Fullstack Developer | 2 | F-001 [ADR-001] |
"""

SCHEMA = """| **TBL-01** `users` | Accounts | `user_id` | ... |
```sql
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT NOT NULL PRIMARY KEY,
    email   TEXT NOT NULL UNIQUE
);
CREATE TABLE notes (
    note_id TEXT PRIMARY KEY,
    owner   TEXT NOT NULL REFERENCES users(user_id),
    body    TEXT,
    FOREIGN KEY (owner) REFERENCES users(user_id)
);
```
"""

OPENAPI = """openapi: 3.0.0
info: {title: t, version: '1'}
paths:
  /login:
    post:
      summary: '[F-001] Sign in [API-001]'
  /notes:
    get:
      summary: '[F-001] List notes [API-002]'
      security: [{bearer: []}]
"""

PRD = """## 5. Features (v1)

| ID | Feature | Description | Priority | Source |
| --- | --- | --- | --- | --- |
| F-001 | Sign in | ... | Must | [FR-001] |
| F-002 | Export | ... | Should | [FR-002] |

## 6. NFR
"""


class ArchitectureModelTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        docs = os.path.join(self.tmp, "p1", "docs")
        os.makedirs(os.path.join(docs, "adr"))
        for name, text in (("architecture.md", ARCH), ("schema.md", SCHEMA), ("openapi.yaml", OPENAPI), ("prd.md", PRD),
                           ("adr/ADR-001.md", "# ADR-001: Framework\n**Status**: accepted\n**Driven by**: [NFR-01]\n\n"
                                              "## Decision\nUse Flask.\n")):
            with open(os.path.join(docs, name), "w") as f:
                f.write(text)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_model_matches_the_documents(self):
        m = am.build_model(os.path.join(self.tmp, "p1"))
        sysm = m["system"]
        self.assertEqual({n["id"]: (n["label"], n["kind"], n["group"]) for n in sysm["nodes"]},
                         {"Browser": ("Web Browser", "service", "Client"), "API": ("Flask API\nREST", "service", "App"),
                          "DB": ("SQLite", "database", "Server")})
        self.assertEqual([(g["id"], g["parent"]) for g in sysm["groups"]], [("Client", None), ("Server", None), ("App", "Server")])
        self.assertEqual(sysm["edges"], [{"from": "Browser", "to": "API", "label": "HTTPS"}, {"from": "API", "to": "DB", "label": ""}])
        self.assertEqual(m["pattern"], "Monolith.")
        self.assertEqual(m["stack"], [{"layer": "Backend", "choice": "Flask", "refs": ["ADR-001"]}])

        users, notes = m["tables"]
        self.assertEqual((users["name"], users["id"], [c["name"] for c in users["columns"] if c["pk"]]), ("users", "TBL-01", ["user_id"]))
        self.assertEqual([c["name"] for c in notes["columns"]], ["note_id", "owner", "body"])
        self.assertTrue(next(c for c in notes["columns"] if c["name"] == "owner")["fk"])
        self.assertEqual({(f["column"], f["table"]) for f in notes["foreign_keys"]}, {("owner", "users")})

        self.assertEqual([(e["method"], e["path"], e["features"], e["api_id"], e["auth"]) for e in m["endpoints"]],
                         [("POST", "/login", ["F-001"], "API-001", False), ("GET", "/notes", ["F-001"], "API-002", True)])
        self.assertEqual(m["uncovered_features"], ["F-002"])  # a PRD feature with no endpoint is shown, not hidden
        self.assertEqual([(a["id"], a["status"], a["decision"]) for a in m["adrs"]], [("ADR-001", "accepted", "Use Flask.")])
        self.assertEqual(m["build_slices"][0]["title"], "Walking Skeleton")
        self.assertEqual((m["team"][0]["role"], m["team"][0]["count"]), ("Fullstack Developer", "2"))

    def test_route_and_missing_docs(self):
        with mock.patch.object(main, "DATA_PROJECTS_DIR", self.tmp):
            c = TestClient(main.app)
            self.assertEqual(len(c.get("/architect/model/p1").json()["endpoints"]), 2)
            os.makedirs(os.path.join(self.tmp, "empty"))
            empty = c.get("/architect/model/empty").json()
            self.assertEqual((empty["has_architecture"], empty["tables"], empty["system"]["nodes"]), (False, [], []))
            self.assertEqual(c.get("/architect/model/nope").status_code, 404)


if __name__ == "__main__":
    unittest.main()
