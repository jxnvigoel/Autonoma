"""
Specialist Skill Registry Unit & Verification Tests
Per Handbook Chapter 6, 3, 12, 19, 23, and 24.
"""

import os
import sys
import json
import unittest

# Ensure engine path is available
ENGINE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "engine"))
if ENGINE_DIR not in sys.path:
    sys.path.insert(0, ENGINE_DIR)

from skill_registry import (
    SkillRegistry,
    get_skill_registry,
    assemble_agent_prompt,
    detect_specialist_needs,
    attach_skill_pack,
    detach_skill_pack,
    get_composite_rubric,
    save_agent_profile_to_db,
    get_agent_profile_from_db,
    ROLE_TOOL_ALLOWANCES,
)
from judge import evaluate_backend_deliverable_with_judge


class TestSpecialistSkillRegistry(unittest.TestCase):

    def setUp(self):
        self.registry = SkillRegistry()

    def test_registry_scanning_and_manifest_validation(self):
        """Verify registry discovers all 4 specialist packs and reports broken packs clearly."""
        # 1. Verify 4 core specialist packs exist
        expected_packs = {"payments", "auth", "notifications", "file-storage"}
        loaded_packs = set(self.registry.packs.keys())
        self.assertTrue(expected_packs.issubset(loaded_packs), f"Missing packs: {expected_packs - loaded_packs}")

        # 2. Check each pack has required fields
        for p_id in expected_packs:
            pack = self.registry.get_pack(p_id)
            self.assertIsNotNone(pack)
            self.assertEqual(pack.id, p_id)
            self.assertEqual(pack.version, "1.0.0")
            self.assertTrue(len(pack.compatible_roles) > 0)
            self.assertIn("keywords", pack.triggers)
            self.assertTrue(os.path.exists(pack.rubric_path))
            self.assertTrue(pack.instructions_path and os.path.exists(pack.instructions_path))
            self.assertTrue(pack.standards_path and os.path.exists(pack.standards_path))
            self.assertTrue(pack.checklist_path and os.path.exists(pack.checklist_path))

        # 3. Test broken pack validation reporting
        broken_dir = os.path.join(self.registry.specialists_dir, "temp_broken_test_pack")
        os.makedirs(broken_dir, exist_ok=True)
        manifest_broken = os.path.join(broken_dir, "manifest.json")
        try:
            with open(manifest_broken, "w", encoding="utf-8") as f:
                json.dump({"name": "Broken Pack", "version": "0.1.0"}, f)

            temp_reg = SkillRegistry()
            broken_report = temp_reg.get_broken_packs()
            self.assertIn("temp_broken_test_pack", broken_report)
            self.assertIn("missing required manifest fields", broken_report["temp_broken_test_pack"])
        finally:
            if os.path.exists(manifest_broken):
                os.remove(manifest_broken)
            if os.path.exists(broken_dir):
                os.rmdir(broken_dir)

    def test_prompt_assembly_structure_and_cacheability(self):
        """Verify prompt assembly order (operating rules + role + specialist packs + template)."""
        role = "backend"
        attached = ["payments"]
        output_template = "Return valid JSON { \"status\": \"done\", \"code\": \"...\" }"

        result = assemble_agent_prompt(
            role=role,
            attached_pack_ids=attached,
            output_template=output_template,
            registry=self.registry,
        )

        sections = result["sections"]
        section_names = [s["name"] for s in sections]

        # Verify stable cacheable ordering:
        self.assertEqual(section_names[0], "operating_rules")
        self.assertEqual(section_names[1], "role_backend")
        self.assertEqual(section_names[2], "pack_payments")
        self.assertEqual(section_names[3], "output_template")

        self.assertGreater(result["total_chars"], 1000)
        self.assertGreater(result["total_tokens_estimated"], 250)
        self.assertGreater(result["cacheable_prefix_length"], 0)
        self.assertFalse(result["exceeded_cap"])
        self.assertIn("payments", result["loaded_packs"])

    def test_tool_permission_rejection(self):
        """Verify tool permissions reject packs that would give a role tools beyond its allowance."""
        # BA is a document role. Allowed tools: read_file, write_file, get_artifact, ask_client.
        ba_profile = {
            "agent_id": "ba-1",
            "name": "Priya",
            "role": "ba",
            "tools": ["read_file", "write_file", "get_artifact", "ask_client"],
            "skill_packs": [],
        }

        # Payments pack is compatible with backend, fullstack, architect, qa. NOT ba.
        res_incompatible = attach_skill_pack(ba_profile, "payments", self.registry)
        self.assertEqual(res_incompatible["status"], "rejected")
        self.assertIn("incompatible with role 'ba'", res_incompatible["error"])

        # Backend role attempting to attach a pack requiring forbidden tools
        backend_profile = {
            "agent_id": "be-1",
            "name": "Arjun",
            "role": "backend",
            "tools": ["read_file", "write_file"],
            "skill_packs": [],
        }

        # Create dummy pack requiring an unallowed tool for backend (e.g. 'k6_run' which is QA only)
        dummy_dir = os.path.join(self.registry.specialists_dir, "temp_forbidden_tool_pack")
        os.makedirs(dummy_dir, exist_ok=True)
        dummy_manifest = os.path.join(dummy_dir, "manifest.json")
        try:
            with open(dummy_manifest, "w", encoding="utf-8") as f:
                json.dump({
                    "id": "forbidden-tool-pack",
                    "name": "Forbidden Tool Pack",
                    "version": "1.0.0",
                    "description": "Tests privilege boundary enforcement",
                    "compatible_roles": ["backend"],
                    "triggers": {"keywords": ["test"], "signals": ["test"]},
                    "required_tools": ["k6_run"],  # k6_run is forbidden to backend per Table 6.1.3
                    "forbidden_tools": [],
                    "rubric_path": "rubric.json"
                }, f)

            with open(os.path.join(dummy_dir, "rubric.json"), "w", encoding="utf-8") as f:
                json.dump({"criteria": [], "max_total": 0, "pass_threshold": 0}, f)

            temp_reg = SkillRegistry()
            res = attach_skill_pack(backend_profile, "forbidden-tool-pack", temp_reg)
            self.assertEqual(res["status"], "rejected")
            self.assertIn("exceed role 'backend' tool allowance", res["error"])
        finally:
            if os.path.exists(os.path.join(dummy_dir, "rubric.json")):
                os.remove(os.path.join(dummy_dir, "rubric.json"))
            if os.path.exists(dummy_manifest):
                os.remove(dummy_manifest)
            if os.path.exists(dummy_dir):
                os.rmdir(dummy_dir)

    def test_nonexistent_pack_returns_blocked(self):
        """Recruiter returns 'blocked' naming the missing pack if no pack matches (never invents one)."""
        backend_profile = {
            "agent_id": "be-1",
            "name": "Arjun",
            "role": "backend",
            "tools": ["read_file", "write_file", "run"],
            "skill_packs": [],
        }

        # Request a pack that does not exist in registry
        res = attach_skill_pack(backend_profile, "crypto-derivatives-trading", self.registry)

        self.assertEqual(res["status"], "blocked")
        self.assertEqual(res["missing_pack"], "crypto-derivatives-trading")
        self.assertIn("Recruiter cannot invent skill packs", res["error"])

    def test_judge_rejects_broken_payments_code(self):
        """
        Test that a payments-attached backend output fails the Judge if:
        (1) it has no idempotency key
        (2) it stores raw card data
        (3) it skips webhook verification
        And passes when compliant.
        """
        # 1. Defect: Missing Idempotency Key
        code_no_idempotency = """
        from fastapi import FastAPI, HTTPException
        app = FastAPI()

        @app.post("/api/v1/payments/charges")
        def create_charge(amount: int, token: str):
            # Charge created directly without Idempotency-Key header check
            return {"charge_id": "ch_123", "status": "succeeded"}
        """
        verdict1 = evaluate_backend_deliverable_with_judge(
            code_content=code_no_idempotency,
            role="backend",
            attached_pack_ids=["payments"]
        )
        self.assertFalse(verdict1["pass"])
        self.assertTrue(any(
            s["criterion"] == "idempotency_key_enforced" and s["score"] == 0
            for s in verdict1["scores"]
        ), "Should fail idempotency_key_enforced must-pass criterion")

        # 2. Defect: Stores raw credit card data
        code_raw_card = """
        from fastapi import FastAPI, Header
        app = FastAPI()

        @app.post("/api/v1/payments/charges")
        def create_charge(amount: int, idempotency_key: str = Header(...)):
            card_number = "4111111111111111"  # Raw PAN
            cvv = "123"
            return {"charge_id": "ch_123", "card_number": card_number}
        """
        verdict2 = evaluate_backend_deliverable_with_judge(
            code_content=code_raw_card,
            role="backend",
            attached_pack_ids=["payments"]
        )
        self.assertFalse(verdict2["pass"])
        self.assertTrue(any(
            s["criterion"] == "zero_raw_card_data" and s["score"] == 0
            for s in verdict2["scores"]
        ), "Should fail zero_raw_card_data must-pass criterion")

        # 3. Defect: Skips webhook signature verification
        code_skip_webhook = """
        from fastapi import FastAPI, Header, Request
        app = FastAPI()

        @app.post("/api/v1/payments/charges")
        def create_charge(idempotency_key: str = Header(...)):
            return {"status": "succeeded"}

        @app.post("/api/v1/payments/webhook")
        async def payment_webhook(request: Request):
            # Defect: Accepts webhook payload without HMAC signature verification
            payload = await request.json()
            return {"received": True}
        """
        verdict3 = evaluate_backend_deliverable_with_judge(
            code_content=code_skip_webhook,
            role="backend",
            attached_pack_ids=["payments"]
        )
        self.assertFalse(verdict3["pass"])
        self.assertTrue(any(
            s["criterion"] == "webhook_signature_verification" and s["score"] == 0
            for s in verdict3["scores"]
        ), "Should fail webhook_signature_verification must-pass criterion")

        # 4. Fully compliant payments deliverable
        code_compliant = """
        import hmac
        import hashlib
        import time
        from fastapi import FastAPI, Header, Request, HTTPException

        app = FastAPI()
        IDEMPOTENCY_STORE = {}

        @app.post("/api/v1/payments/charges")
        def create_charge(amount: int, payment_method_token: str, idempotency_key: str = Header(..., alias="Idempotency-Key")):
            if idempotency_key in IDEMPOTENCY_STORE:
                return IDEMPOTENCY_STORE[idempotency_key]

            # Use tokenized payment method (pm_card_visa), zero raw card PAN or CVV stored
            last4 = "4242"
            brand = "visa"

            # Check failure unhappy path
            if amount <= 0:
                raise HTTPException(status_code=402, detail="Payment failed, you were not charged")

            res = {"status": "succeeded", "charge_id": "ch_123", "brand": brand, "last4": last4}
            IDEMPOTENCY_STORE[idempotency_key] = res
            return res

        @app.post("/api/v1/payments/webhook")
        async def payment_webhook(request: Request, signature: str = Header(..., alias="Stripe-Signature")):
            body = await request.body()
            secret = "whsec_test_secret"
            expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, signature):
                raise HTTPException(status_code=400, detail="Invalid webhook signature")
            return {"status": "verified"}
        """
        verdict_compliant = evaluate_backend_deliverable_with_judge(
            code_content=code_compliant,
            role="backend",
            attached_pack_ids=["payments"]
        )
        self.assertTrue(verdict_compliant["pass"])
        self.assertGreaterEqual(verdict_compliant["total"], verdict_compliant["pass_threshold"])

    def test_detection_biovault_vs_payments_project(self):
        """
        Verify:
        (a) Run detection on BioVault Lab -> payments must NOT match (0 false positives).
        (b) Run detection on a NEW project that includes payments -> payments MUST match with evidence.
        """
        # 1. BioVault Lab Artifacts
        biovault_session = "7fcb8a45-2fe8-4067-99b7-2bc8f409f3d3"
        biovault_dir = os.path.join(os.path.dirname(__file__), "..", "data", "projects", biovault_session, "docs")

        prd_path = os.path.join(biovault_dir, "prd.md")
        req_path = os.path.join(biovault_dir, "requirements.md")
        arch_path = os.path.join(biovault_dir, "architecture.md")

        biovault_prd = ""
        biovault_req = ""
        biovault_arch = ""

        if os.path.exists(prd_path):
            with open(prd_path, "r", encoding="utf-8") as f:
                biovault_prd = f.read()
        if os.path.exists(req_path):
            with open(req_path, "r", encoding="utf-8") as f:
                biovault_req = f.read()
        if os.path.exists(arch_path):
            with open(arch_path, "r", encoding="utf-8") as f:
                biovault_arch = f.read()

        res_biovault = detect_specialist_needs(
            prd_text=biovault_prd,
            requirements_text=biovault_req,
            architecture_text=biovault_arch
        )

        # BioVault Lab is a cryogenic specimen tracker: ZERO payments
        biovault_matched_pack_ids = [p["pack_id"] for p in res_biovault["specialist_needs"]]
        self.assertNotIn("payments", biovault_matched_pack_ids, "BioVault Lab must NOT match payments specialist pack!")

        # 2. NEW Project with Payments (PayFlow Global Checkout)
        new_project_prd = """
        # Product Requirement Document (PRD): PayFlow Global
        ## 4. User Personas
        | P-01 | Shopper | Makes purchases online |

        ## 5. Features and Acceptance Criteria
        ### Feature F-003: Payment Checkout Processing [FR-007]
        - Story: As a [P-01], I want to pay using my credit card so that I can complete my order.
        - Priority: Must
        - Acceptance Criteria:
          | AC-011 | Given a shopping cart with total $50, when user clicks checkout, then payment gateway session is created with Idempotency-Key. |
          | AC-012 | Given gateway returns decline, then fee shows unpaid and message says 'Payment failed, you were not charged'. |

        ### Feature F-005: Order Billing and Invoices [FR-009]
        - Story: As a [P-01], I want to view my invoice and request refunds.
        """

        new_project_req = """
        # Requirements Document: PayFlow Global
        ## Functional Requirements
        - [FR-007] The system must process credit card payments via Stripe gateway with webhook verification. [Source: Q-003]
        - [FR-009] The system must handle subscription billing and refund processing. [Source: Q-005]
        """

        new_project_arch = """
        # Architecture Document: PayFlow Global
        ## 6. API Contracts
        ### API-004: POST /api/v1/checkout/sessions
        - Request: { "cart_id": "cart_123", "amount": 5000 }
        - Headers: Idempotency-Key: UUIDv4
        - Response: 201 Created

        ### API-005: POST /api/v1/payments/webhook
        - Webhook receiver verifying Stripe-Signature HMAC-SHA256 signature.
        """

        res_new_project = detect_specialist_needs(
            prd_text=new_project_prd,
            requirements_text=new_project_req,
            architecture_text=new_project_arch
        )

        new_matched_pack_ids = [p["pack_id"] for p in res_new_project["specialist_needs"]]
        self.assertIn("payments", new_matched_pack_ids, "New payments project MUST match payments specialist pack!")

        payments_need = next(p for p in res_new_project["specialist_needs"] if p["pack_id"] == "payments")
        self.assertEqual(payments_need["confidence"], "high")
        self.assertGreaterEqual(payments_need["evidence_count"], 3)

        # Verify explicit citations
        evidence_ids = {e["id"] for e in payments_need["evidence"]}
        self.assertIn("F-003", evidence_ids)
        self.assertIn("FR-007", evidence_ids)
        self.assertTrue("API-004" in evidence_ids or "API-005" in evidence_ids)
        self.assertIn("ADR recommends attaching 'Payments & Idempotency Specialist'", payments_need["adr_recommendation"])


if __name__ == "__main__":
    unittest.main()
