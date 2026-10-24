import unittest
import os
import json
import sqlite3
import yaml

from engine.validators import (
    validate_prd_pre_judge,
    validate_schema_ddl,
    validate_openapi_spec,
    validate_architecture_pre_judge,
    validate_grounding_corpus
)

class TestBrokenArtifactsAndOldBioVault(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old_biovault_dir = os.path.join(
            os.path.dirname(__file__), "..", "data", "projects", "2da196a1-4d4b-4347-8374-01078fd04e5b"
        )
        cls.old_prd_path = os.path.join(cls.old_biovault_dir, "prd.md")
        cls.qa_log_path = os.path.join(cls.old_biovault_dir, "qa_log.json")

    def test_old_biovault_prd_fails_with_named_defects(self):
        """
        The old BioVault PRD must FAIL with each defect explicitly named:
        - Core problem 'Yes, please proceed...'
        - Duplicate descriptions
        - 'pull requests for specimens'
        - F-006 title/story mismatch
        - Spliced ACs
        - Repeated sentences
        """
        self.assertTrue(os.path.exists(self.old_prd_path), f"Old BioVault PRD not found at {self.old_prd_path}")
        with open(self.old_prd_path, "r", encoding="utf-8") as f:
            old_prd_text = f.read()

        qa_map = {}
        if os.path.exists(self.qa_log_path):
            with open(self.qa_log_path, "r", encoding="utf-8") as f:
                qa_data = json.load(f)
                qa_map = {item["id"]: item for item in qa_data if "id" in item}

        is_valid, errors = validate_prd_pre_judge(old_prd_text, qa_map)
        self.assertFalse(is_valid, "Old BioVault PRD must FAIL pre-judge validation")

        errors_str = "\n".join(errors)

        # 1. Core problem filler
        self.assertTrue(
            any("Yes, please proceed" in e or "non-answer or filler" in e for e in errors),
            f"Missing defect: Core problem chat filler. Errors:\n{errors_str}"
        )

        # 2. Duplicate descriptions
        self.assertTrue(
            any("Duplicate feature description" in e for e in errors),
            f"Missing defect: Duplicate feature descriptions. Errors:\n{errors_str}"
        )

        # 3. Pull requests for specimens
        self.assertTrue(
            any("pull requests" in e.lower() for e in errors),
            f"Missing defect: 'pull requests for specimens'. Errors:\n{errors_str}"
        )

        # 4. F-006 title/story mismatch
        self.assertTrue(
            any("F-006" in e and "title/story mismatch" in e for e in errors),
            f"Missing defect: F-006 title/story mismatch. Errors:\n{errors_str}"
        )

        # 5. Spliced ACs
        self.assertTrue(
            any("Spliced acceptance criterion" in e for e in errors),
            f"Missing defect: Spliced ACs. Errors:\n{errors_str}"
        )

        # 6. Repeated sentences across features
        self.assertTrue(
            any("Sentence repeated across features" in e for e in errors),
            f"Missing defect: Repeated sentences across features. Errors:\n{errors_str}"
        )

    # -------------------------------------------------------------------------
    # BROKEN PRD DEFECT COPIES
    # -------------------------------------------------------------------------
    def test_broken_prd_chat_filler_in_problem(self):
        sample_prd = """# Product Requirement Document
## 1. App overview
| Field | Value | Source |
|---|---|---|
| App name | Test App | [Q-001] |
## 2. Problem
- **Today**: Manual paperwork causes tracking delays. [Q-001]
- **Core problem**: Let's begin the project now. [Q-001]
- **Why existing tools fall short**: Existing alternatives require cloud connectivity. [Q-001]
## 5. Features (v1)
### F-001: User Authentication
- **Story**: As a [P-01], I want to log in so that I access the system.
| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-001 | Given valid credentials, when the user logs in, then dashboard opens within 500ms [NFR-01]. |
| AC-002 | (unhappy path) Given invalid credentials, when logging in, then display error toast. |
"""
        is_valid, errors = validate_prd_pre_judge(sample_prd, {})
        self.assertFalse(is_valid)
        self.assertTrue(any("non-answer or filler" in e for e in errors))

    def test_broken_prd_duplicate_summary_descriptions(self):
        sample_prd = """# PRD
## 2. Problem
- **Today**: Manual tracking is slow and error prone across operations. [Q-001]
- **Core problem**: Critical samples are misplaced without automated verification. [Q-001]
- **Why existing tools fall short**: Cloud tools fail in air-gapped offline facilities. [Q-001]
## 5. Features (v1)
### Summary
| ID | Feature | Description | Priority (MoSCoW) | Requirements |
|---|---|---|---|---|
| F-001 | Feature One | Generic repeated description across the board. | Must | [FR-01] |
| F-002 | Feature Two | Generic repeated description across the board. | Must | [FR-02] |
### F-001: Feature One
- **Story**: As a [P-01], I want feature one so that value is delivered.
| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-001 | Given state, when action, then response within 200ms [NFR-01]. |
| AC-002 | (unhappy path) Given error, when retry, then show error alert. |
### F-002: Feature Two
- **Story**: As a [P-01], I want feature two so that other value is delivered.
| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-003 | Given other state, when other action, then other response within 200ms [NFR-01]. |
| AC-004 | (unhappy path) Given other error, when retry, then show error alert. |
"""
        is_valid, errors = validate_prd_pre_judge(sample_prd, {})
        self.assertFalse(is_valid)
        self.assertTrue(any("Duplicate feature description" in e for e in errors))

    def test_broken_prd_malformed_acceptance_criteria(self):
        sample_prd = """# PRD
## 2. Problem
- **Today**: Manual paperwork causes tracking delays in daily lab operations. [Q-001]
- **Core problem**: Tracking samples manually causes compliance risk during audits. [Q-001]
- **Why existing tools fall short**: Cloud alternatives fail in disconnected local setups. [Q-001]
## 5. Features (v1)
### F-001: Export Reports
- **Story**: As a [P-01], I want to export reports so that audit logs are saved.
| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-001 | The system should export the file quickly without any errors. |
| AC-002 | (unhappy path) When an error happens, show a dialog box. |
"""
        is_valid, errors = validate_prd_pre_judge(sample_prd, {})
        self.assertFalse(is_valid)
        self.assertTrue(any("not a grammatical Given / When / Then sentence" in e for e in errors))

    # -------------------------------------------------------------------------
    # BROKEN ARCHITECTURE DEFECT COPIES
    # -------------------------------------------------------------------------
    def test_broken_architecture_missing_required_sections(self):
        broken_arch = """# Architecture Document for Test Project
## 1. Constraints that shape the design
- SQLite local persistence [NFR-02]
- Offline-first execution on client workstation
## 2. Capacity estimate
- Storage: 1000 records * 1KB = 1MB calculation [NFR-03]
## 3. Tech stack
- Python 3.12, SQLite 3.45.0
## 4. Architecture overview
- Layered modular clean architecture with explicit boundary separation between domain models and persistence.
"""
        is_valid, errors = validate_architecture_pre_judge(broken_arch)
        self.assertFalse(is_valid)
        self.assertTrue(any("missing section" in e.lower() for e in errors))

    def test_broken_architecture_missing_walking_skeleton(self):
        broken_arch = """# Architecture Document
## 1. Constraints that shape the design
- Offline first [NFR-02]
## 2. Capacity estimate
- Storage: 1000 items * 2KB = 2MB calculation [NFR-03]
## 3. Tech stack
- Python 3.12, SQLite
## 4. Architecture overview
- Clean modular architecture
## 5. Authentication and authorization
- Local pin auth
## 6. API
- Local REST endpoints
## 7. Data model
- Tables: users, items
## 8. External integrations
- Barcode scanner serial
## 9. Security (STRIDE)
| Threat ID | Threat | Component | Mitigation |
|---|---|---|---|
| T-01 | Tampering | DB | SQLite WAL + sha256 checksums |
| T-02 | Spoofing | Auth | Argon2id salted hashing |
## 10. Reliability and operations
- Hourly automated local database backups
## 11. Build order
- Step 1: Create database schema
- Step 2: Implement core services
- Step 3: Implement UI views
## 12. Team plan (for HR)
- Fullstack Lead [F-001, ADR-001]
"""
        is_valid, errors = validate_architecture_pre_judge(broken_arch)
        self.assertFalse(is_valid)
        self.assertTrue(any("walking skeleton" in e.lower() for e in errors))

    def test_broken_architecture_team_plan_missing_citations(self):
        broken_arch = """# Architecture Document
## 1. Constraints that shape the design
- Offline first [NFR-02]
## 2. Capacity estimate
- Peak throughput: 10 requests/s * 2KB = 20KB/s calculation [NFR-01]
## 3. Tech stack
- Python 3.12, SQLite
## 4. Architecture overview
- Clean modular architecture
## 5. Authentication and authorization
- Local pin auth
## 6. API
- Local REST endpoints
## 7. Data model
- Tables: users, items
## 8. External integrations
- Barcode scanner serial
## 9. Security (STRIDE)
| Threat ID | Threat | Component | Mitigation |
|---|---|---|---|
| T-01 | Tampering | DB | SQLite WAL + sha256 checksums |
| T-02 | Spoofing | Auth | Argon2id salted hashing |
## 10. Reliability and operations
- Automated local backups
## 11. Build order
- Milestone 1: Implement the walking skeleton with health probe
## 12. Team plan (for HR)
- Role 1: Fullstack Engineer (builds the UI and API)
- Role 2: Backend Specialist (builds database)
"""
        is_valid, errors = validate_architecture_pre_judge(broken_arch)
        self.assertFalse(is_valid)
        self.assertTrue(any("does not cite any Feature" in e or "does not cite any [ADR" in e for e in errors))

    # -------------------------------------------------------------------------
    # BROKEN SCHEMA DEFECT COPIES
    # -------------------------------------------------------------------------
    def test_broken_schema_invalid_sql_syntax(self):
        broken_schema = """# Database Schema (schema.md)
```sql
CREAT TABLE broken_table (
    id TEXT PRIMARY KEY,
    name TEXT NOT NUL
);
```
"""
        is_valid, errors, tables = validate_schema_ddl(broken_schema)
        self.assertFalse(is_valid)
        self.assertTrue(any("syntax error" in e.lower() or "sqlite ddl execution failed" in e.lower() for e in errors))

    def test_broken_schema_missing_ddl_statements(self):
        broken_schema = """# Database Schema (schema.md)
This document discusses tables but does not contain any executable DDL code blocks.
"""
        is_valid, errors, tables = validate_schema_ddl(broken_schema)
        self.assertFalse(is_valid)
        self.assertTrue(any("No executable SQL DDL statements" in e for e in errors))

    # -------------------------------------------------------------------------
    # BROKEN OPENAPI DEFECT COPIES
    # -------------------------------------------------------------------------
    def test_broken_openapi_invalid_version(self):
        broken_openapi = """openapi: 2.0.0
info:
  title: Test API
  version: 1.0.0
paths:
  /items:
    get:
      summary: Get items [F-001]
      responses:
        '200':
          description: OK
        '400':
          description: Bad request
"""
        is_valid, errors, _ = validate_openapi_spec(broken_openapi, ["F-001"])
        self.assertFalse(is_valid)
        self.assertTrue(any("OpenAPI version must be 3.0" in e for e in errors))

    def test_broken_openapi_missing_f_feature_coverage(self):
        broken_openapi = """openapi: 3.0.3
info:
  title: Test API
  version: 1.0.0
paths:
  /items:
    get:
      summary: List items [F-001]
      responses:
        '200':
          description: OK
        '400':
          description: Bad request
        '500':
          description: Server error
"""
        # F-002 is required but has no endpoints
        is_valid, errors, _ = validate_openapi_spec(broken_openapi, ["F-001", "F-002"])
        self.assertFalse(is_valid)
        self.assertTrue(any("F-002" in e and "no matching OpenAPI endpoint" in e for e in errors))

    def test_broken_openapi_missing_error_responses(self):
        broken_openapi = """openapi: 3.0.3
info:
  title: Test API
  version: 1.0.0
paths:
  /items:
    get:
      summary: List items [F-001]
      responses:
        '200':
          description: OK only, missing 4xx/5xx
"""
        is_valid, errors, _ = validate_openapi_spec(broken_openapi, ["F-001"])
        self.assertFalse(is_valid)
        self.assertTrue(any("missing error response definitions" in e for e in errors))

if __name__ == "__main__":
    unittest.main()
