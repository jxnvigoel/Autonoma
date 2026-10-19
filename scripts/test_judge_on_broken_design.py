import os
import sys
import json

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from engine.judge import evaluate_design_with_judge

# Broken design artifacts deliberately seeded with fatal defects:
# 1. Feature unmapped: F-004 is completely missing from app-flow.md Section 2 Journeys
# 2. Incomplete screen states: Screen S-02 only has 2 states (no Loading, Error, or No Permission) in Section 3
# 3. Screen S-02 missing authorized persona citation in Section 1 Screens table
# 4. Egregious low contrast ratio: #94a3b8 on #f8fafc (2.41:1 vs required 4.5:1) in design-brief.md
# 5. Cross-project foreign domain terms: "field operators" and "drone photogrammetry"
# 6. Ungrounded number: "95000" not present in PRD/qa_log

broken_app_flow_text = """# Application Flow & Screen Architecture: BioVault Lab

## 1. Site map
| ID | Screen Name | Route | Purpose | Authorized Persona | Features |
|---|---|---|---|---|---|
| S-01 | Sample Intake Dashboard | `/intake` | Register incoming biological samples | [P-01] Lab Technician | [F-001], [F-002] |
| S-02 | Cold-Storage Monitor | `/monitoring` | Monitor real-time cold chain temperatures | None | [F-003] |

## 2. Journeys
| ID | Journey Name | Persona | Features | Primary Path | Unhappy Paths |
|---|---|---|---|---|---|
| J-01 | Sample Intake & Barcode Scanning | [P-01] | [F-001], [F-002] | S-01 -> S-02 | Scan failure [AC-001] |
| J-02 | Cold Chain Temperature Logging | [P-01] | [F-003] | S-02 | Out-of-spec alert [AC-002] |
<!-- Note: Feature 4 Export Chain of Custody is completely omitted from journeys! -->

## 3. Screen states

### S-01
- **Field operators** inspect incoming packages with 95000 drone photogrammetry items.

| State | Trigger | Layout & Key Elements | User Action & Feedback |
|---|---|---|---|
| Loading | Initial page mount | Shimmer skeleton table with 5 rows | Non-interactive until ready |
| Empty | No samples scanned today | Empty box illustration + 'Scan Sample' CTA button | Clicking CTA focuses barcode input field |
| Populated | 1+ samples loaded | Table showing Barcode, Temperature, Status, Timestamp | Selecting a row opens details drawer |
| Error | SQLite query error | Red banner with error description + 'Retry' button | Clicking retry re-fetches samples |
| No Permission | Role lacks technician permission | Padlock icon + 'Access Restricted' notice | 'Contact Administrator' link |

### S-02
| State | Trigger | Layout & Key Elements | User Action & Feedback |
|---|---|---|---|
| Populated | Sensor active | Temperature gauge displaying reading in Celsius | Real-time updates |
| Empty | No sensor connected | Warning banner | Prompt user to plug in sensor |
<!-- Fatal defect: Missing Loading, Error, and No Permission states! -->

## 4. Components
Standard components.

## 5. Navigation & shortcuts
Standard navigation.
"""

broken_design_brief_text = """# Visual Design Brief & Design System Specification: BioVault Lab

## 1. Design Principles & Theme Architecture
Local-first, high data density.

## 2. Colours
| Token | Light | Dark | Use | Contrast on Background |
|---|---|---|---|---|
| `--color-background` | `#f8fafc` | `#0f172a` | App page background | N/A |
| `--color-text` | `#94a3b8` | `#94a3b8` | Primary body text | 2.41:1 (FAIL) |
| `--color-primary` | `#0284c7` | `#38bdf8` | Primary interactive buttons | 4.67:1 (PASS) |

<!-- Note: #94a3b8 on #f8fafc has a contrast ratio of 2.41:1, severely failing WCAG 2.2 AA (min 4.5:1) -->

## 3. Typography
Standard Inter typography.

## 4. Components
Standard components.

## 5. Layout
Base spacing 4px.
"""

mock_parsed_ba = {
    "app_name": "BioVault Lab",
    "timeline": "8 weeks",
    "budget": "$15,000",
    "qa_map": {
        "Q-001": {
            "id": "Q-001",
            "question": "What is the application?",
            "answer": "A local biological sample tracking and cold-chain monitoring system for lab technicians."
        }
    },
    "non_functional_reqs": [
        {"id": "NFR-01", "name": "Query Latency", "target": "< 500 ms"},
        {"id": "NFR-02", "name": "Local Storage", "target": "100% local SQLite"},
        {"id": "NFR-03", "name": "Accessibility", "target": "WCAG 2.2 AA"}
    ],
    "functional_reqs": [
        {"id": "FR-01", "feature": "Barcode Scanning", "priority": "Must"},
        {"id": "FR-02", "feature": "Specimen Cataloging", "priority": "Must"},
        {"id": "FR-03", "feature": "Cold-Chain Temperature Logging", "priority": "Must"},
        {"id": "FR-04", "feature": "Audit Export", "priority": "Must"}
    ]
}

mock_prd_text = """# Product Requirement Document: BioVault Lab

## 3. Personas
- [P-01] Lab Technician (Primary Operator)
- [P-02] Compliance Auditor (Secondary Reviewer)

## 5. Features
- [F-001] Barcode Scanning
- [F-002] Specimen Cataloging
- [F-003] Cold-Chain Temperature Logging
- [F-004] Audit Export

## Acceptance Criteria
- [AC-001] Scan verification
- [AC-002] Out of spec alert

## 6. Non-Functional Requirements
- [NFR-01] Query Latency
- [NFR-02] Local Storage
- [NFR-03] Accessibility
"""

print("=== RUNNING JUDGE ON DELIBERATELY BROKEN UI/UX DESIGN ARTIFACTS ===")

verdict = evaluate_design_with_judge(
    app_flow_text=broken_app_flow_text,
    design_brief_text=broken_design_brief_text,
    prd_text=mock_prd_text,
    parsed_ba=mock_parsed_ba,
    rubric_path="skills/designer/rubric.json"
)

print(f"\nPass: {verdict.get('pass')}")
print(f"Total Score: {verdict.get('total')}/{verdict.get('max')}")
print(f"Verdict Summary: {verdict.get('verdict_summary')}")
print(f"Unsupported Claims Count: {len(verdict.get('unsupported_claims', []))}")

print("\n--- Detected Fatal Flaws / Unsupported Claims ---")
for idx, uc in enumerate(verdict.get("unsupported_claims", []), 1):
    print(f"{idx}. [{uc.get('section', 'General')}] {uc.get('reason')}")
    print(f"   Context snippet: {uc.get('text')}")

# Assertions verifying Judge correctly caught the flaws
assert verdict.get("pass") is False, "Judge MUST FAIL broken UI/UX design artifacts!"
assert len(verdict.get("unsupported_claims", [])) >= 4, f"Judge should catch at least 4 fatal defects, got {len(verdict.get('unsupported_claims', []))}"

# Specific checks:
reasons = [uc.get("reason", "") for uc in verdict.get("unsupported_claims", [])]

has_contrast_failure = any("contrast" in r.lower() for r in reasons)
assert has_contrast_failure, "Judge must catch WCAG contrast ratio failure (#94a3b8 on #f8fafc)!"

has_feature_failure = any("f-004" in r.lower() or "unmapped" in r.lower() for r in reasons)
assert has_feature_failure, "Judge must catch unmapped feature F-004!"

has_state_failure = any("state" in r.lower() for r in reasons)
assert has_state_failure, "Judge must catch missing screen states in S-02!"

has_persona_failure = any("persona" in r.lower() for r in reasons)
assert has_persona_failure, "Judge must catch missing persona citation in S-02!"

has_contamination = any("cross-project" in r.lower() or "field operator" in r.lower() for r in reasons)
assert has_contamination, "Judge must catch cross-project contamination terms ('field operators')!"

print("\n>>> PROOF COMPLETE: Judge successfully and deterministically REJECTED the broken design documents with exact defect identification across all 5 fatal error types!")
