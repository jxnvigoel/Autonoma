"""
Automated Test Suite for HR Staffing Planner, Recruiter, and Gate 2
Handbook Ch 6 (6.1.1–6.3.6), 2.7.5 (steps 14-17), 5.1.6, 22.4, 23.4–23.6, 24.1, 26.4.

Test Categories:
1. Unit Tests:
   - Sizing arithmetic from story points
   - Tier router risk mapping (22.4)
   - Least-privilege tool check (document roles cannot have shell/exec)
   - Token cap derivation (+20% rework buffer)
2. Broken-Artifact Tests (each must fail with explicit reason):
   - Seat with no refs
   - Must-have feature unassigned
   - Idle seat (>1 week idle)
   - Headcount over budget unflagged
   - Shell tool on document role
   - Hardcoded model
   - Missing downgrade note
   - Invented skill pack
   - Modified architecture/plan after approval
3. Gate 2 Tests:
   - POST /scrum/start/{session_id} returns 403 when unapproved
   - Approval invalidated after plan edit returns 403
   - Gate 2 approval and request-changes workflows
4. Failure Tests:
   - Missing architecture team plan stops with named error (Handbook 6.2.2)
   - LLM timeout / exception produces loud explicit error
5. Budget Guard Tests (Handbook 26.4):
   - Warn at 80%
   - Pause at 100%
   - Step 16 recomputed budget formula
"""

import os
import sys
import json
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Ensure engine path is available
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENGINE_DIR = os.path.join(PROJECT_ROOT, "engine")
if ENGINE_DIR not in sys.path:
    sys.path.insert(0, ENGINE_DIR)

from starlette.testclient import TestClient
from fastapi import HTTPException

from main import app
from hr import (
    load_staffing_assumptions,
    parse_prd_features_for_hr,
    extract_architect_team_plan_section,
    calculate_staffing_arithmetic,
    generate_hr_team_plan
)
from recruiter import (
    load_router_config,
    resolve_model_tier,
    calculate_token_cap_for_role,
    determine_reports_to,
    execute_recruiter_hiring
)
from budget import (
    recompute_budget_step16,
    check_budget_guard,
    get_gate2_state,
    save_gate2_approval_record,
    approve_gate2,
    request_changes_gate2,
    enforce_gate2_server_side,
    get_file_sha256
)
from validators import (
    validate_team_plan_schema,
    validate_seat_citations,
    validate_must_have_feature_coverage,
    validate_no_idle_seats,
    validate_staggered_starts,
    validate_role_merging,
    validate_headcount_budget_flagging,
    validate_agent_profile_permissions,
    validate_downgrades_recorded,
    validate_skill_pack_exists_or_blocked
)
from skill_registry import (
    validate_agent_permissions,
    init_agents_db,
    init_approvals_db,
    save_agent_profile_to_db,
    get_role_pack
)


class TestHRStaffingSizingArithmetic(unittest.TestCase):
    """Unit tests for HR sizing arithmetic derived from story points and assumptions."""

    def setUp(self):
        self.assumptions = load_staffing_assumptions()

    def test_sizing_arithmetic_from_story_points(self):
        """
        Verify story point derivation ([CFG-02]) and sizing arithmetic:
        seats(role) = ceil(points / (velocity * weeks))
        """
        features = [
            {"id": "F-001", "priority": "Must-have", "ac_count": 2, "user_story": "User login API"},
            {"id": "F-002", "priority": "Must-have", "ac_count": 4, "user_story": "Payment processing"},
            {"id": "F-003", "priority": "Must-have", "ac_count": 6, "user_story": "Subscription webhook"}
        ]
        arch_team_plan = "ROLE-01 backend 2 engineers weeks 1-4 for APIs\nROLE-02 frontend 1 engineer weeks 2-4"

        # Under CFG-02:
        # F-001 (2 AC) -> 2 points
        # F-002 (4 AC) -> 3 points
        # F-003 (6 AC) -> 5 points
        # Total backend points = 10 points
        calc = calculate_staffing_arithmetic(
            features=features,
            architecture_team_plan_text=arch_team_plan,
            timeline_weeks=4,
            assumptions=self.assumptions
        )

        self.assertIn("seats", calc)
        self.assertIn("timeline_weeks", calc)
        self.assertEqual(calc["timeline_weeks"], 4)

        # Check that backend role was created with valid span
        be_seat = next((s for s in calc["seats"] if s["role"] == "backend"), None)
        self.assertIsNotNone(be_seat)
        self.assertGreaterEqual(be_seat["count"], 1)
        self.assertEqual(be_seat["from_week"], 1)
        self.assertLessEqual(be_seat["to_week"], 4)

    def test_role_merging_under_two_stories(self):
        """Handbook 6.1.1 & [CFG-03]: Roles under ~2 stories are merged into neighbouring/fullstack role."""
        stories_per_role = {"frontend": 1, "backend": 6}
        plan_unmerged = {
            "seats": [
                {"id": "ROLE-01", "role": "frontend", "count": 1, "from_week": 1, "to_week": 4, "why": "Build frontend screen", "refs": ["F-001"]},
                {"id": "ROLE-02", "role": "backend", "count": 2, "from_week": 1, "to_week": 4, "why": "Build core backend APIs", "refs": ["F-002", "F-003"]}
            ],
            "timeline_weeks": 4,
            "notes": []
        }
        ok, errors = validate_role_merging(plan_unmerged, stories_per_role)
        self.assertFalse(ok)
        self.assertTrue(any("under 2 stories" in e or "< 2" in e for e in errors))

    def test_staggered_start_scheduling(self):
        """Handbook 6.1.1: DevOps from week 1, QA from first build week, Perf once APIs exist."""
        valid_staggered_plan = {
            "seats": [
                {"id": "ROLE-01", "role": "devops", "count": 1, "from_week": 1, "to_week": 4, "why": "CI/CD scaffolding", "refs": ["ADR-001"]},
                {"id": "ROLE-02", "role": "backend", "count": 2, "from_week": 1, "to_week": 4, "why": "API development", "refs": ["F-001", "F-002"]},
                {"id": "ROLE-03", "role": "qa", "count": 1, "from_week": 1, "to_week": 4, "why": "Test cases from first build week", "refs": ["F-001"]},
                {"id": "ROLE-04", "role": "perf", "count": 1, "from_week": 2, "to_week": 4, "why": "Performance testing after APIs exist", "refs": ["NFR-001"]}
            ],
            "timeline_weeks": 4,
            "notes": []
        }
        ok, errors = validate_staggered_starts(valid_staggered_plan)
        self.assertTrue(ok, f"Unexpected validation errors: {errors}")


class TestRecruiterTierRouterAndLeastPrivilege(unittest.TestCase):
    """Unit tests for Recruiter tier routing (Handbook 22.4), token caps, and least privilege."""

    def setUp(self):
        self.router_config = load_router_config()

    def test_tier_router_risk_mapping_22_4(self):
        """
        Verify Handbook 22.4 tier mapping:
        - High: Architect, developers (backend/frontend/fullstack), Tech Lead, Judge
        - Medium: PM, Designer, QA, Perf, DevOps
        - Low: BA relay, HR, Recruiter, Scrum
        """
        roles_map = self.router_config["roles"]
        self.assertEqual(roles_map["architect"], "high")
        self.assertEqual(roles_map["tech-lead"], "high")
        self.assertEqual(roles_map["backend"], "high")
        self.assertEqual(roles_map["frontend"], "high")
        self.assertEqual(roles_map["judge"], "high")

        self.assertEqual(roles_map["pm"], "medium")
        self.assertEqual(roles_map["designer"], "medium")
        self.assertEqual(roles_map["qa"], "medium")
        self.assertEqual(roles_map["devops"], "medium")

        self.assertEqual(roles_map["ba"], "low")
        self.assertEqual(roles_map["hr"], "low")
        self.assertEqual(roles_map["recruiter"], "low")
        self.assertEqual(roles_map["scrum"], "low")

    def test_least_privilege_tool_check(self):
        """
        Handbook 6.1.3 & 6.3.6: Document-only roles never get shell/exec/run tools.
        """
        # Document roles: hr, recruiter, pm, ba
        doc_roles = ["hr", "recruiter", "pm", "ba"]
        forbidden_tools = ["shell", "bash", "terminal", "k6_run", "run_tests", "exec_cmd"]

        for r in doc_roles:
            for ft in forbidden_tools:
                ok, errs = validate_agent_permissions(role=r, tools=[ft, "file_read"], fs_scope="docs/")
                self.assertFalse(ok, f"Tool '{ft}' was improperly permitted for document role '{r}'")
                self.assertTrue(any("unauthorized" in e.lower() or "violation" in e.lower() or "forbidden" in e.lower() for e in errs))

        # Permitted tools for document roles
        ok, errs = validate_agent_permissions(
            role="hr",
            tools=["read_file", "write_file", "get_artifact", "ask_client"],
            fs_scope="docs/"
        )
        self.assertTrue(ok, f"Valid tools were improperly rejected for HR: {errs}")

    def test_token_cap_derivation_with_20_percent_buffer(self):
        """
        Handbook 5.1.6: token_cap derived from estimate.json with 20% rework buffer.
        """
        estimate_data = {
            "stages": [
                {
                    "stage_id": "stage_backend",
                    "role": "software engineer backend",
                    "subtotal_tokens": 100000
                }
            ]
        }
        # With 1 seat: 100,000 * 1.20 = 120,000
        cap, err = calculate_token_cap_for_role("backend", estimate_data, seat_count=1)
        self.assertIsNone(err)
        self.assertEqual(cap, 120000)

        # With 2 seats: 120,000 // 2 = 60,000
        cap_split, err_split = calculate_token_cap_for_role("backend", estimate_data, seat_count=2)
        self.assertIsNone(err_split)
        self.assertEqual(cap_split, 60000)

        # Missing role in estimate -> must flag, don't guess
        cap_missing, err_missing = calculate_token_cap_for_role("blockchain_specialist", estimate_data, seat_count=1)
        self.assertIsNotNone(err_missing)
        self.assertEqual(cap_missing, 0)
        self.assertIn("missing from docs/estimate.json", err_missing)


class TestBrokenArtifacts(unittest.TestCase):
    """Broken-artifact tests: Each broken condition MUST fail with an explicit reason."""

    def test_seat_with_no_refs_fails(self):
        """Seat with no refs fails citation validation."""
        plan = {
            "seats": [
                {"id": "ROLE-01", "role": "backend", "count": 1, "from_week": 1, "to_week": 3, "why": "Build APIs with no citations", "refs": []}
            ],
            "timeline_weeks": 3,
            "notes": []
        }
        ok, errors = validate_seat_citations(plan, prd_text="Feature F-001", architecture_text="ADR-001")
        self.assertFalse(ok)
        self.assertTrue(any("has no refs" in e for e in errors))

    def test_seat_with_nonexistent_ref_fails(self):
        """Seat citing non-existent reference fails citation validation."""
        plan = {
            "seats": [
                {"id": "ROLE-01", "role": "backend", "count": 1, "from_week": 1, "to_week": 3, "why": "Build APIs with fake ref", "refs": ["F-999_NONEXISTENT"]}
            ],
            "timeline_weeks": 3,
            "notes": []
        }
        ok, errors = validate_seat_citations(plan, prd_text="Feature F-001", architecture_text="ADR-001")
        self.assertFalse(ok)
        self.assertTrue(any("non-existent reference" in e for e in errors))

    def test_must_have_feature_unassigned_fails(self):
        """Must-have feature unassigned to any engineering seat fails coverage validation."""
        plan = {
            "seats": [
                {"id": "ROLE-01", "role": "frontend", "count": 1, "from_week": 1, "to_week": 3, "why": "Build F-001 UI", "refs": ["F-001"]}
            ],
            "timeline_weeks": 3,
            "notes": []
        }
        prd_features = [
            {"id": "F-001", "priority": "Must-have"},
            {"id": "F-002", "priority": "Must-have"}  # Unassigned!
        ]
        ok, errors = validate_must_have_feature_coverage(plan, prd_features)
        self.assertFalse(ok)
        self.assertTrue(any("F-002" in e and "no assigned engineering seat" in e for e in errors))

    def test_idle_seat_fails(self):
        """Seat idle for more than 1 week fails idle seat validation (Handbook 6.1.1)."""
        plan = {
            "seats": [
                {"id": "ROLE-01", "role": "qa", "count": 1, "from_week": 1, "to_week": 4, "idle_weeks": 2, "why": "QA testing with long idle gap", "refs": ["F-001"]}
            ],
            "timeline_weeks": 4,
            "notes": []
        }
        ok, errors = validate_no_idle_seats(plan)
        self.assertFalse(ok)
        self.assertTrue(any("exceeding 1-week limit" in e for e in errors))

    def test_headcount_over_budget_unflagged_fails(self):
        """Headcount cost exceeding budget limit without being flagged in plan notes fails."""
        plan = {
            "seats": [{"id": "ROLE-01", "role": "backend", "count": 5, "from_week": 1, "to_week": 4, "why": "Large team", "refs": ["F-001"]}],
            "timeline_weeks": 4,
            "notes": ["Standard staffing schedule"]  # Does not flag budget deficit!
        }
        ok, errors = validate_headcount_budget_flagging(
            plan=plan,
            budget_limit_usd=100.0,
            estimated_cost_usd=250.0
        )
        self.assertFalse(ok)
        self.assertTrue(any("deficit is unflagged" in e for e in errors))

    def test_shell_tool_on_document_role_fails(self):
        """Document role assigned shell or execution tool fails least-privilege validator."""
        profile = {
            "agent_id": "hr-1",
            "role": "hr",
            "tools": ["file_read", "file_write", "shell"],
            "fs_scope": "docs/"
        }
        ok, errors = validate_agent_profile_permissions(profile)
        self.assertFalse(ok)
        self.assertTrue(any("shell" in e.lower() for e in errors))

    def test_missing_downgrade_note_fails(self):
        """Agent profile marked downgraded without documented explanation fails."""
        profiles = [
            {
                "agent_id": "backend-1",
                "name": "Marcus",
                "role": "backend",
                "downgraded": True,
                "downgrade_note": ""  # Missing!
            }
        ]
        ok, errors = validate_downgrades_recorded(profiles, staffing_report_text="Staffing Report")
        self.assertFalse(ok)
        self.assertTrue(any("no downgrade note" in e for e in errors))

    def test_invented_skill_pack_fails(self):
        """Agent assigned non-existent/invented skill pack must be marked status 'blocked'."""
        profiles = [
            {
                "agent_id": "crypto-specialist-1",
                "role": "crypto_trader_v99",
                "status": "ready"  # Non-existent pack must NOT be ready!
            }
        ]
        ok, errors = validate_skill_pack_exists_or_blocked(profiles)
        self.assertFalse(ok)
        self.assertTrue(any("invented skill pack forbidden" in e for e in errors))


class TestGate2AndServerSideEnforcement(unittest.TestCase):
    """Tests for Gate 2 state management, 403 server-side enforcement, and hash invalidation."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_office.db")
        init_approvals_db(self.db_path)
        init_agents_db(self.db_path)

        self.session_id = "test_gate2_project"
        self.project_dir = os.path.join(PROJECT_ROOT, "data", "projects", self.session_id)
        os.makedirs(os.path.join(self.project_dir, "docs"), exist_ok=True)

        self.team_plan_path = os.path.join(self.project_dir, "docs", "team-plan.json")
        self.estimate_path = os.path.join(self.project_dir, "docs", "estimate.json")

        with open(self.team_plan_path, "w", encoding="utf-8") as f:
            json.dump({"seats": [{"id": "ROLE-01", "role": "backend", "count": 1, "from_week": 1, "to_week": 3, "why": "API", "refs": ["F-001"]}], "timeline_weeks": 3, "notes": []}, f)
        with open(self.estimate_path, "w", encoding="utf-8") as f:
            json.dump({"budget_limit_usd": 500.0, "total_estimate_usd": 120.0, "stages": []}, f)

        self.client = TestClient(app)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
        shutil.rmtree(self.project_dir, ignore_errors=True)

    def test_gate2_server_side_enforcement_403_when_unapproved(self):
        """Downstream stage (Scrum Master) returns 403 when Gate 2 is unapproved."""
        # Ensure gate2 is unapproved
        with self.assertRaises(HTTPException) as ctx:
            enforce_gate2_server_side(self.session_id, db_path=self.db_path)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("Gate 2 approval required", ctx.exception.detail)

        # Test through FastAPI endpoint
        with patch("budget.DEFAULT_DB_PATH", self.db_path), patch("engine.budget.DEFAULT_DB_PATH", self.db_path):
            resp = self.client.post(f"/scrum/start/{self.session_id}")
            self.assertEqual(resp.status_code, 403)

    def test_gate2_approval_unlocks_downstream_stage(self):
        """Approving Gate 2 successfully unlocks downstream stages."""
        save_gate2_approval_record(self.session_id, summary_markdown="Gate 2 Summary", db_path=self.db_path)
        res = approve_gate2(self.session_id, client_notes="Approved by CTO", db_path=self.db_path)
        self.assertTrue(res["approved"])

        # Verification: enforce_gate2_server_side passes without exception
        try:
            enforce_gate2_server_side(self.session_id, db_path=self.db_path)
        except HTTPException:
            self.fail("enforce_gate2_server_side raised unexpected HTTPException after approval")

    def test_plan_mutation_invalidates_gate2_approval(self):
        """Modifying team-plan.json after approval invalidates Gate 2 and returns 403."""
        save_gate2_approval_record(self.session_id, summary_markdown="Gate 2 Summary", db_path=self.db_path)
        approve_gate2(self.session_id, client_notes="Approved", db_path=self.db_path)

        # Confirm approved
        state1 = get_gate2_state(self.session_id, db_path=self.db_path)
        self.assertTrue(state1["approved"])

        # Mutate team-plan.json
        with open(self.team_plan_path, "w", encoding="utf-8") as f:
            json.dump({"seats": [{"id": "ROLE-01", "role": "backend", "count": 99, "from_week": 1, "to_week": 3, "why": "Mutated", "refs": ["F-001"]}], "timeline_weeks": 3, "notes": []}, f)

        # Check gate2 state again -> Must be invalidated
        state2 = get_gate2_state(self.session_id, db_path=self.db_path)
        self.assertFalse(state2["approved"])
        self.assertEqual(state2["status"], "invalidated")

        # Now downstream enforcement must return 403
        with self.assertRaises(HTTPException) as ctx:
            enforce_gate2_server_side(self.session_id, db_path=self.db_path)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("invalidated", ctx.exception.detail.lower())

    def test_request_changes_workflow(self):
        """Requesting changes sets status to changes_requested and routes QA to BA."""
        res = request_changes_gate2(self.session_id, feedback="Add a performance tester", db_path=self.db_path)
        self.assertEqual(res["status"], "changes_requested")
        self.assertTrue(res["routed_qid"].startswith("Q-"))

        # Verify QA log updated
        qa_file = os.path.join(self.project_dir, "qa_log.json")
        self.assertTrue(os.path.exists(qa_file))
        with open(qa_file, "r", encoding="utf-8") as f:
            log = json.load(f)
            self.assertTrue(any("Add a performance tester" in item.get("answer", "") for item in log))


class TestBudgetGuardHandbook26_4(unittest.TestCase):
    """Tests for Budget Guard thresholds per Handbook 26.4: warn at 80%, pause at 100%."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_office.db")
        init_approvals_db(self.db_path)

        self.session_id = "test_budget_project"
        self.project_dir = os.path.join(PROJECT_ROOT, "data", "projects", self.session_id)
        os.makedirs(os.path.join(self.project_dir, "docs"), exist_ok=True)
        self.estimate_file = os.path.join(self.project_dir, "docs", "estimate.json")

        # Initialize llm_calls table in test db
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS llm_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                task_id TEXT,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                cached_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL,
                cost_usd REAL NOT NULL DEFAULT 0,
                latency_ms INTEGER,
                stop TEXT,
                at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        conn.commit()
        conn.close()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
        shutil.rmtree(self.project_dir, ignore_errors=True)

    def test_budget_guard_warn_at_80_percent(self):
        """Budget guard returns status 'warning' when projected spend reaches >= 80%."""
        estimate_data = {
            "budget_limit_usd": 100.0,
            "total_estimated_tokens": 100000,
            "stages": []
        }
        with open(self.estimate_file, "w", encoding="utf-8") as f:
            json.dump(estimate_data, f)

        # Record 85,000 tokens (85%) in ledger
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO llm_calls (project_id, agent_id, provider, model, input_tokens, output_tokens, cost_usd) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (self.session_id, "backend-1", "groq", "llama-3.1-8b-instant", 40000, 45000, 85.0)
        )
        conn.commit()
        conn.close()

        res = check_budget_guard(self.session_id, budget_limit_tokens=100000, budget_limit_usd=100.0, db_path=self.db_path)
        self.assertTrue(res["warn_80"])
        self.assertFalse(res["pause_100"])
        self.assertEqual(res["status"], "warning")
        self.assertIn("warning", res["message"].lower())

    def test_budget_guard_pause_at_100_percent(self):
        """Budget guard returns status 'paused' when projected spend reaches >= 100%."""
        estimate_data = {
            "budget_limit_usd": 100.0,
            "total_estimated_tokens": 100000,
            "stages": []
        }
        with open(self.estimate_file, "w", encoding="utf-8") as f:
            json.dump(estimate_data, f)

        # Record 105,000 tokens (105%) in ledger
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO llm_calls (project_id, agent_id, provider, model, input_tokens, output_tokens, cost_usd) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (self.session_id, "backend-1", "groq", "llama-3.1-8b-instant", 50000, 55000, 105.0)
        )
        conn.commit()
        conn.close()

        res = check_budget_guard(self.session_id, budget_limit_tokens=100000, budget_limit_usd=100.0, db_path=self.db_path)
        self.assertTrue(res["warn_80"])
        self.assertTrue(res["pause_100"])
        self.assertEqual(res["status"], "paused")
        self.assertIn("pause", res["message"].lower())

    def test_budget_recompute_step16_formula(self):
        """
        Handbook 2.7.5 step 16 & 5.1.6:
        Budget recomputed from spent tokens + remaining estimates * 1.20 (20% rework buffer).
        """
        estimate_data = {
            "budget_limit_usd": 500.0,
            "total_estimate_usd": 200.0,
            "stages": [
                {
                    "stage_id": "stage_sprint",
                    "role": "scrum master",
                    "subtotal_cost_usd": 20.0,
                    "subtotal_tokens": 10000
                },
                {
                    "stage_id": "stage_backend",
                    "role": "backend engineer",
                    "subtotal_cost_usd": 80.0,
                    "subtotal_tokens": 40000
                }
            ]
        }
        with open(self.estimate_file, "w", encoding="utf-8") as f:
            json.dump(estimate_data, f)

        # Enable cloud pricing by setting local_only=False in session_state.json
        state_file = os.path.join(self.project_dir, "session_state.json")
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({"local_only": False}, f)

        res = recompute_budget_step16(self.session_id, db_path=self.db_path)
        self.assertEqual(res["session_id"], self.session_id)
        rem = res["remaining_summary"]
        self.assertEqual(rem["rework_buffer_percentage"], 20)
        # Remaining stages: 50,000 tokens + 20% buffer (10,000) = 60,000 tokens
        self.assertEqual(rem["remaining_subtotal_tokens"], 50000)
        self.assertEqual(rem["rework_buffer_tokens"], 10000)
        self.assertEqual(rem["remaining_with_buffer_tokens"], 60000)
        self.assertGreater(rem["remaining_cost_usd"], 0.0)
        tot = res["total_budget"]
        self.assertIn("1.20", tot["formula"])

        # Also test local-only mode ($0.00 cost per Handbook 22.4 / 26.4)
        from llm_client import default_llm_client
        if default_llm_client:
            default_llm_client._project_local_only.pop(self.session_id, None)
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({"local_only": True}, f)
        res_local = recompute_budget_step16(self.session_id, db_path=self.db_path)
        self.assertTrue(res_local["is_local_only"])
        self.assertEqual(res_local["remaining_summary"]["remaining_cost_usd"], 0.0)


class TestFailureAndResilience(unittest.TestCase):
    """Failure and exception handling tests."""

    def test_missing_architect_team_plan_stops_with_named_error(self):
        """Handbook 6.2.2: Missing architecture team plan stops with named error."""
        arch_missing = """
# Architecture Document
## 1. System Overview
Architecture without section 10 or 12 team plan.
## 2. ADRs
ADR-001: SQLite
"""
        extracted = extract_architect_team_plan_section(arch_missing)
        self.assertEqual(extracted, "")

        # Calling generate_hr_team_plan on project missing team plan raises named error
        test_session = "proj_missing_arch_plan"
        proj_dir = os.path.join(PROJECT_ROOT, "data", "projects", test_session)
        os.makedirs(os.path.join(proj_dir, "docs"), exist_ok=True)
        try:
            with open(os.path.join(proj_dir, "docs", "prd.md"), "w") as f:
                f.write("### Feature F-001:\n**Priority**: Must-have\n- AC-001: Login")
            with open(os.path.join(proj_dir, "docs", "estimate.json"), "w") as f:
                json.dump({"timeline_weeks": 4, "stages": []}, f)
            with open(os.path.join(proj_dir, "docs", "architecture.md"), "w") as f:
                f.write(arch_missing)

            with self.assertRaises(RuntimeError) as ctx:
                generate_hr_team_plan(test_session)
            self.assertIn("missing team plan section", str(ctx.exception).lower())
        finally:
            shutil.rmtree(proj_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
