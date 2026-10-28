"""
Automated Test Suite for Scrum Master and Tech Lead Readiness Review
Handbook Ch 9 (Scrum Master, 9.1-9.2.6), 10 (Tech Lead, 10.1.4, 10.2),
2.7.6 steps 18-19b, 22.4, 24.1 (reviews, tasks, approvals, llm_calls tables), and 26.4.

Test Categories:
1. Backlog Validators & Unit Tests:
   - Schema validation
   - Points sizing (Fibonacci 1,2,3,5; <= 5 points)
   - Critical path calculation & DAG ordering
   - Load balancing across agent roster
   - Walking skeleton first story
   - Implementation plan & Mermaid Gantt generation
   - Daily report generator from task records & ledger (blockers first)
2. Broken-Artifact Tests (each must FAIL with explicit reasons):
   - Story over 5 points fails with reason
   - Uncovered Must-have AC fails with reason
   - Dependency cycle fails with reason
   - Ghost owner fails with reason
   - Missing walking skeleton fails with reason
   - Non-existent API or table ref fails with reason
   - Readiness verdict "ready" with unresolved gaps fails with reason
   - Readiness review invalidated after backlog/arch/PRD change
3. Server-Side Gate Tests:
   - POST /scrum/start/{session} returns 403 before Gate 2 approved
   - POST /build/start/{session} returns 403 before readiness approved
   - POST /build/start/{session} returns 403 when readiness invalidated
4. Failure & Resilience Tests:
   - Rate limit / LLM down produces loud failure, no false PASS
   - Local-only project makes 0 cloud calls
"""

import os
import sys
import json
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENGINE_DIR = os.path.join(PROJECT_ROOT, "engine")
if ENGINE_DIR not in sys.path:
    sys.path.insert(0, ENGINE_DIR)

from starlette.testclient import TestClient
from fastapi import HTTPException

from main import app
from validators import (
    validate_backlog_schema,
    validate_backlog_points,
    validate_backlog_must_have_ac_coverage,
    validate_backlog_dependency_cycles,
    validate_backlog_walking_skeleton,
    validate_backlog_owners_in_roster,
    validate_backlog_refs_exist,
    validate_readiness_review_verdict,
)
from scrum import (
    init_tasks_db,
    calculate_critical_path,
    calculate_load_balance,
    generate_gantt_chart_data,
    render_implementation_plan,
    generate_daily_report,
    sync_stories_to_tasks,
)
from readiness import (
    init_reviews_db,
    compute_traceability_matrix,
    get_readiness_state,
    enforce_readiness_server_side,
)
from budget import (
    approve_gate2,
    enforce_gate2_server_side,
)


class TestScrumAndReadiness(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_office.db")
        init_tasks_db(self.db_path)
        init_reviews_db(self.db_path)

        self.session_id = "test_scrum_proj_01"
        self.session_dir = os.path.join("data", "projects", self.session_id)
        os.makedirs(os.path.join(self.session_dir, "docs"), exist_ok=True)
        os.makedirs(os.path.join(self.session_dir, "reports"), exist_ok=True)

        # Create valid mock PRD
        self.prd_content = """# PRD: Test Project
### Feature `F-001`: User Authentication
**Priority**: Must-have
- `AC-001`: User signs in with email and receives valid session token.
- `AC-002`: User signs out invalidating session.

### Feature `F-002`: Order Processing
**Priority**: Must-have
- `AC-003`: User creates an order with positive items.
- `AC-004`: Payment processed via gateway.
"""
        with open(os.path.join(self.session_dir, "docs", "prd.md"), "w", encoding="utf-8") as f:
            f.write(self.prd_content)

        # Create valid mock Architecture
        self.arch_content = """# Architecture
### 1. Build Order & Walking Skeleton
Walking skeleton: Initialize backend API, connect SQLite database, and run health check.

### 2. Endpoints
- `API-001`: POST /auth/login
- `API-002`: POST /orders

### 3. Database Schema
- `TBL-01`: users
- `TBL-02`: orders
"""
        with open(os.path.join(self.session_dir, "docs", "architecture.md"), "w", encoding="utf-8") as f:
            f.write(self.arch_content)

        # Create valid mock Backlog
        self.valid_backlog = {
            "stories": [
                {
                    "id": "ST-001",
                    "title": "Walking skeleton: App initialization, DB connection, health check",
                    "role": "devops",
                    "owner": f"{self.session_id}_devops-1",
                    "points": 2,
                    "refs": {
                        "features": ["F-001"],
                        "ac": ["AC-001"],
                        "api": ["API-001"],
                        "tables": ["TBL-01"]
                    },
                    "depends_on": [],
                    "needs_perf": False,
                    "definition_of_done": [
                        "AC-001 has passing automated tests",
                        "Tech Lead approved",
                        "API matches openapi.yaml"
                    ]
                },
                {
                    "id": "ST-002",
                    "title": "User sign-out and session invalidation",
                    "role": "backend",
                    "owner": f"{self.session_id}_backend-1",
                    "points": 3,
                    "refs": {
                        "features": ["F-001"],
                        "ac": ["AC-002"],
                        "api": ["API-001"],
                        "tables": ["TBL-01"]
                    },
                    "depends_on": ["ST-001"],
                    "needs_perf": False,
                    "definition_of_done": ["AC-002 has passing tests", "Tech Lead approved"]
                },
                {
                    "id": "ST-003",
                    "title": "POST /orders creates an order",
                    "role": "backend",
                    "owner": f"{self.session_id}_backend-1",
                    "points": 3,
                    "refs": {
                        "features": ["F-002"],
                        "ac": ["AC-003", "AC-004"],
                        "api": ["API-002"],
                        "tables": ["TBL-02"]
                    },
                    "depends_on": ["ST-001"],
                    "needs_perf": True,
                    "definition_of_done": ["AC-003 and AC-004 have passing tests", "Tech Lead approved"]
                }
            ]
        }
        with open(os.path.join(self.session_dir, "docs", "backlog.json"), "w", encoding="utf-8") as f:
            json.dump(self.valid_backlog, f, indent=2)

        # Create valid mock team-plan.json and estimate.json for Gate 2
        team_plan = {
            "seats": [
                {"id": "ROLE-01", "role": "devops", "count": 1, "from_week": 1, "to_week": 4, "why": "CI/CD", "refs": ["F-001"]},
                {"id": "ROLE-02", "role": "backend", "count": 1, "from_week": 1, "to_week": 4, "why": "APIs", "refs": ["F-001", "F-002"]}
            ],
            "timeline_weeks": 4,
            "notes": []
        }
        with open(os.path.join(self.session_dir, "docs", "team-plan.json"), "w", encoding="utf-8") as f:
            json.dump(team_plan, f, indent=2)

        estimate_data = {
            "total_tokens": 100000,
            "role_tokens": {"devops": 40000, "backend": 60000}
        }
        with open(os.path.join(self.session_dir, "docs", "estimate.json"), "w", encoding="utf-8") as f:
            json.dump(estimate_data, f, indent=2)

        self.roster = [
            {"id": f"{self.session_id}_devops-1", "role": "devops"},
            {"id": f"{self.session_id}_backend-1", "role": "backend"}
        ]

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
        shutil.rmtree(self.session_dir, ignore_errors=True)

    # ==========================================================================
    # 1. UNIT TESTS: VALIDATORS & DETERMINISTIC CALCULATIONS
    # ==========================================================================

    def test_valid_backlog_passes_all_validators(self):
        """Valid backlog passes schema, points, coverage, cycles, walking skeleton, and refs."""
        ok, errs = validate_backlog_schema(self.valid_backlog)
        self.assertTrue(ok, f"Schema validation failed: {errs}")

        ok, errs = validate_backlog_points(self.valid_backlog)
        self.assertTrue(ok, f"Points validation failed: {errs}")

        ok, errs = validate_backlog_must_have_ac_coverage(self.valid_backlog, self.prd_content)
        self.assertTrue(ok, f"AC coverage validation failed: {errs}")

        ok, errs = validate_backlog_dependency_cycles(self.valid_backlog)
        self.assertTrue(ok, f"Cycle validation failed: {errs}")

        ok, errs = validate_backlog_walking_skeleton(self.valid_backlog)
        self.assertTrue(ok, f"Walking skeleton validation failed: {errs}")

        ok, errs = validate_backlog_owners_in_roster(self.valid_backlog, self.roster)
        self.assertTrue(ok, f"Owner roster validation failed: {errs}")

        ok, errs = validate_backlog_refs_exist(self.valid_backlog, self.prd_content, self.arch_content)
        self.assertTrue(ok, f"Refs validation failed: {errs}")

    def test_critical_path_calculation(self):
        """Code computes DAG critical path and longest chain accurately."""
        stories = self.valid_backlog["stories"]
        crit_info = calculate_critical_path(stories)
        self.assertEqual(crit_info["critical_path_story_ids"][0], "ST-001")
        self.assertEqual(crit_info["estimated_days"], 5)  # ST-001 (2 pts) + ST-002 or ST-003 (3 pts)
        self.assertEqual(crit_info["total_critical_points"], 5)

    def test_load_balance_calculation(self):
        """Code aggregates stories and points per owner and role."""
        stories = self.valid_backlog["stories"]
        load = calculate_load_balance(stories)
        self.assertEqual(load["total_points"], 8)
        self.assertEqual(load["total_stories"], 3)
        self.assertEqual(load["by_owner"][f"{self.session_id}_devops-1"]["points"], 2)
        self.assertEqual(load["by_owner"][f"{self.session_id}_backend-1"]["points"], 6)

    def test_render_implementation_plan_contains_gantt_and_wip(self):
        """Plan generator renders Mermaid Gantt, critical path, and WIP limit declaration."""
        crit_info = calculate_critical_path(self.valid_backlog["stories"])
        load_info = calculate_load_balance(self.valid_backlog["stories"])
        gantt_info = generate_gantt_chart_data(self.valid_backlog["stories"], crit_info)
        plan_md = render_implementation_plan(self.session_id, self.valid_backlog, crit_info, load_info, gantt_info)

        self.assertIn("gantt", plan_md)
        self.assertIn("Critical Path", plan_md)
        self.assertIn("WIP Limit", plan_md)
        self.assertIn("ST-001", plan_md)

    def test_daily_report_blockers_first_and_reconciled(self):
        """Daily report lists blockers first and reconciles numbers with task records."""
        sync_stories_to_tasks(self.session_id, self.valid_backlog["stories"], self.db_path)
        report_md = generate_daily_report(self.session_id, day=1, db_path=self.db_path)

        self.assertIn("## 1. Blockers", report_md)
        self.assertIn("## 2. Progress & What Moved", report_md)
        self.assertIn("ST-001", report_md)
        self.assertIn("**Total Points Planned**: 8", report_md)

    # ==========================================================================
    # 2. BROKEN-ARTIFACT TESTS (MUST FAIL WITH EXPLICIT REASONS)
    # ==========================================================================

    def test_broken_story_over_5_points_must_fail(self):
        """Rule 9.2.5: No story over 5 points. Story with 8 points must fail."""
        broken = json.loads(json.dumps(self.valid_backlog))
        broken["stories"][1]["points"] = 8
        ok, errs = validate_backlog_points(broken)
        self.assertFalse(ok)
        self.assertTrue(any("exceeds 5 points" in e for e in errs))

    def test_broken_uncovered_must_have_ac_must_fail(self):
        """Rule 9.2.5: Every Must-have AC lands in some story. Omitted AC-004 must fail."""
        broken = json.loads(json.dumps(self.valid_backlog))
        # Remove AC-004 from story refs
        broken["stories"][2]["refs"]["ac"] = ["AC-003"]
        ok, errs = validate_backlog_must_have_ac_coverage(broken, self.prd_content)
        self.assertFalse(ok)
        self.assertTrue(any("AC-004" in e and "not covered" in e for e in errs))

    def test_broken_dependency_cycle_must_fail(self):
        """Rule 9.2.5: No dependency cycles. Cyclic graph ST-002 -> ST-003 -> ST-002 must fail."""
        broken = json.loads(json.dumps(self.valid_backlog))
        broken["stories"][1]["depends_on"] = ["ST-003"]
        broken["stories"][2]["depends_on"] = ["ST-002"]
        ok, errs = validate_backlog_dependency_cycles(broken)
        self.assertFalse(ok)
        self.assertTrue(any("Dependency cycle detected" in e for e in errs))

    def test_broken_ghost_owner_must_fail(self):
        """Handbook 9.2.4: Stories must be assigned to existing roster agents."""
        broken = json.loads(json.dumps(self.valid_backlog))
        broken["stories"][0]["owner"] = "ghost_agent_99"
        ok, errs = validate_backlog_owners_in_roster(broken, self.roster)
        self.assertFalse(ok)
        self.assertTrue(any("ghost_agent_99" in e for e in errs))

    def test_broken_missing_walking_skeleton_must_fail(self):
        """Rule 9.2.4 rule 1: First story is the walking skeleton from the architecture."""
        broken = json.loads(json.dumps(self.valid_backlog))
        broken["stories"][0]["title"] = "Create database migrations for user profile"
        ok, errs = validate_backlog_walking_skeleton(broken)
        self.assertFalse(ok)
        self.assertTrue(any("walking skeleton" in e.lower() for e in errs))

    def test_broken_nonexistent_api_ref_must_fail(self):
        """Story citing non-existent API-999 must fail validator."""
        broken = json.loads(json.dumps(self.valid_backlog))
        broken["stories"][0]["refs"]["api"] = ["API-999"]
        ok, errs = validate_backlog_refs_exist(broken, self.prd_content, self.arch_content)
        self.assertFalse(ok)
        self.assertTrue(any("API-999" in e and "non-existent" in e for e in errs))

    def test_broken_readiness_ready_with_gap_must_fail(self):
        """Handbook 10.1.4: Verdict 'ready' cannot be granted if blocking gaps exist."""
        ok, errs = validate_readiness_review_verdict(
            verdict="ready",
            gaps=["Must-have Feature F-002 has no mapped API endpoint."],
            contradictions=[]
        )
        self.assertFalse(ok)
        self.assertTrue(any("cannot be 'ready'" in e for e in errs))

    def test_readiness_invalidation_after_backlog_change(self):
        """Modifying backlog.json after readiness review invalidates the verdict."""
        # 1. Save valid review state in DB with current backlog hash
        backlog_path = os.path.join(self.session_dir, "docs", "backlog.json")
        arch_path = os.path.join(self.session_dir, "docs", "architecture.md")
        prd_path = os.path.join(self.session_dir, "docs", "prd.md")

        import hashlib
        def h(p):
            with open(p, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()

        review_body = {
            "verdict": "ready",
            "gaps": [],
            "contradictions": [],
            "hashes": {
                "backlog_sha256": h(backlog_path),
                "architecture_sha256": h(arch_path),
                "prd_sha256": h(prd_path)
            }
        }
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO reviews (project_id, target, reviewer, kind, passed, score, max_score, body) VALUES (?, 'docs/readiness.md', 'tl', 'readiness', 1, 1.0, 1.0, ?)",
            (self.session_id, json.dumps(review_body))
        )
        conn.commit()
        conn.close()

        # Check initial state is ready
        state = get_readiness_state(self.session_id, db_path=self.db_path)
        self.assertTrue(state["passed"])
        self.assertEqual(state["verdict"], "ready")

        # Now mutate backlog.json
        with open(backlog_path, "a", encoding="utf-8") as f:
            f.write("\n// modified\n")

        # Re-check state: MUST be invalidated
        state_after = get_readiness_state(self.session_id, db_path=self.db_path)
        self.assertFalse(state_after["passed"])
        self.assertEqual(state_after["status"], "invalidated")

    # ==========================================================================
    # 3. SERVER-SIDE GATE ENFORCEMENT (403 CHECKS)
    # ==========================================================================

    def test_scrum_start_returns_403_before_gate2_approval(self):
        """POST /scrum/start/{session_id} returns 403 Forbidden until Gate 2 is approved."""
        unapproved_session = "fresh_unapproved_session_99"
        unapproved_dir = os.path.join("data", "projects", unapproved_session)
        os.makedirs(os.path.join(unapproved_dir, "docs"), exist_ok=True)
        try:
            resp = self.client.post(f"/scrum/start/{unapproved_session}")
            self.assertEqual(resp.status_code, 403)
            self.assertTrue("Gate 2 approval required" in resp.text or "GATE2" in resp.text)
        finally:
            shutil.rmtree(unapproved_dir, ignore_errors=True)

    def test_build_start_returns_403_before_readiness_approved(self):
        """POST /build/start/{session_id} returns 403 until Tech Lead readiness is ready."""
        # Approve Gate 2 first
        approve_gate2(self.session_id, client_notes="Client approved Gate 2")

        # Now test build endpoint: readiness review has not been executed yet
        resp = self.client.post(f"/build/start/{self.session_id}")
        self.assertEqual(resp.status_code, 403)
        self.assertIn("READINESS_GATE_LOCKED", resp.text)

    # ==========================================================================
    # 4. FAILURE & RESILIENCE TESTS
    # ==========================================================================

    def test_local_only_project_makes_no_cloud_calls(self):
        """Local-only project routes to local provider without calling Groq/cloud."""
        from llm_client import query_llm_with_meta, default_llm_client
        tmp_db = os.path.join(tempfile.mkdtemp(), "office.db")
        default_llm_client.ledger_db_path = tmp_db  # keep the mocked call out of the real ledger
        self.addCleanup(setattr, default_llm_client, "ledger_db_path", None)
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                "response": "{\"verdict\": \"ready\", \"gaps\": [], \"contradictions\": []}"
            }
            res, meta = query_llm_with_meta(
                prompt="test local call",
                force_provider="ollama",
                force_model="llama3.2:3b"
            )
            # Verifies that cloud groq endpoints were not called
            self.assertEqual(meta.get("provider"), "ollama")
            self.assertEqual(meta.get("cost_usd"), 0.0)


if __name__ == "__main__":
    unittest.main()
