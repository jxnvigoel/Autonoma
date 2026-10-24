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
claims_text = [(uc.get("reason", "") + " " + uc.get("text", "")).lower() for uc in verdict.get("unsupported_claims", [])]

has_contrast_failure = any("contrast" in c for c in claims_text)
assert has_contrast_failure, "Judge must catch WCAG contrast ratio failure (#94a3b8 on #f8fafc)!"

has_feature_failure = any("f-004" in c or "unmapped" in c or "not covered" in c for c in claims_text)
assert has_feature_failure, "Judge must catch unmapped feature F-004!"

has_state_failure = any("state" in c for c in claims_text)
assert has_state_failure, "Judge must catch missing screen states in S-02!"

has_persona_failure = any("persona" in c for c in claims_text)
assert has_persona_failure, "Judge must catch missing persona citation in S-02!"

has_contamination = any("cross-project" in c or "field operator" in c for c in claims_text)
assert has_contamination, "Judge must catch cross-project contamination terms ('field operators')!"

print("\n>>> PROOF COMPLETE (CASE 1): Judge successfully and deterministically REJECTED the broken design documents with exact defect identification across all 5 fatal error types!")


# ==============================================================================
# CASE 2: CURRENT / OLD AEROFLAT APP-FLOW & DESIGN BRIEF AUDIT (Part 4)
# Deliberate defects in old AeroFleet output:
# 1. Identical screen state sentences across screens S-02, S-03, S-04, S-05
# 2. Truncated route slug: /faa-form-8130-airwor
# 3. Screen names > 5 words: 'Airframe maintenance work order dispatch and digital sign-off'
# 4. Persona authorization mismatch / missing persona citations in table headers
# 5. Ungrounded external standards in design brief: FAA AC 20-175, MIL-STD-1472
# ==============================================================================
print("\n" + "="*70)
print("=== CASE 2: RUNNING JUDGE ON OLD AEROFLAT DELIVERABLE (DEFECT DETECTION) ===")
print("="*70)

old_aerofleet_af_text = """# Application Flow & Screen Architecture: AeroFleet Hangar

## 1. Screens
| ID | Screen Name | Route | Purpose | Authorized Persona | Features |
|---|---|---|---|---|---|
| S-01 | Dashboard & Activity Overview | `/` | Central operational overview | [P-01], [P-02], [P-03], [P-04] | [F-001], [F-002], [F-003], [F-004] |
| S-02 | Airframe maintenance work order dispatch and digital sign-off | `/airframe-maintenance` | Work order dispatch and sign-off | [P-01] | [F-001] |
| S-03 | Line-maintenance discrepancy squawk logging and corrective action tracking | `/line-maintenance-dis` | Squawk logging and corrective action | [P-02] | [F-002] |
| S-04 | Time-controlled component life limit and airworthiness directive monitoring | `/time-controlled-comp` | Component life limit monitoring | [P-03] | [F-003] |
| S-05 | FAA Form 8130 airworthiness approval release and compliance audit export | `/faa-form-8130-airwor` | Airworthiness approval release | [P-04] | [F-004] |

## 2. Journeys
### J-1: Airframe maintenance work order dispatch and digital sign-off — covers [F-001 / FR-01], [AC-001], [AC-002]
1. On `S-01` (Dashboard) → Line Maintenance Lead (`[P-01]`) views operational overview → clicks primary action button.
2. `S-02` loads → user inputs required parameters and configuration details (`[API-001]`).
3. **Success**: System validates input, persists record into local database (`[TBL-01]`), displays confirmation toast, and updates active view within 1.0 s (`[AC-001]`, `[NFR-01]`).
4. **Error (invalid input)**: Inline validation notices highlight offending fields, preserve user inputs without loss, and enable immediate correction (`[AC-002]`).
5. **Error (system / storage error)**: Non-blocking warning banner notifies user of local database error with an actionable retry button (`[AC-002]`).

### J-2: Line-maintenance discrepancy squawk logging and corrective action tracking — covers [F-002 / FR-02], [AC-003], [AC-004]
1. On `S-01` (Dashboard) → Quality Assurance Inspector (`[P-02]`) views operational overview → clicks primary action button.
2. `S-03` loads → user inputs required parameters and configuration details (`[API-002]`).
3. **Success**: System validates input, persists record into local database (`[TBL-02]`), displays confirmation toast, and updates active view within 1.0 s (`[AC-003]`, `[NFR-01]`).
4. **Error (invalid input)**: Inline validation notices highlight offending fields, preserve user inputs without loss, and enable immediate correction (`[AC-004]`).
5. **Error (system / storage error)**: Non-blocking warning banner notifies user of local database error with an actionable retry button (`[AC-004]`).

### J-3: Time-controlled component life limit and airworthiness directive monitoring — covers [F-003 / FR-03], [AC-005], [AC-006]
1. On `S-01` (Dashboard) → Aviation Maintenance Technician (`[P-03]`) views operational overview → clicks primary action button.
2. `S-04` loads → user inputs required parameters and configuration details (`[API-003]`).
3. **Success**: System validates input, persists record into local database (`[TBL-03]`), displays confirmation toast, and updates active view within 1.0 s (`[AC-005]`, `[NFR-01]`).
4. **Error (invalid input)**: Inline validation notices highlight offending fields, preserve user inputs without loss, and enable immediate correction (`[AC-006]`).
5. **Error (system / storage error)**: Non-blocking warning banner notifies user of local database error with an actionable retry button (`[AC-006]`).

### J-4: FAA Form 8130 airworthiness approval release and compliance audit export — covers [F-004 / FR-04], [AC-007], [AC-008]
1. On `S-01` (Dashboard) → Chief Inspector (`[P-04]`) views operational overview → clicks primary action button.
2. `S-05` loads → user inputs required parameters and configuration details (`[API-004]`).
3. **Success**: System validates input, persists record into local database (`[TBL-04]`), displays confirmation toast, and updates active view within 1.0 s (`[AC-007]`, `[NFR-01]`).
4. **Error (invalid input)**: Inline validation notices highlight offending fields, preserve user inputs without loss, and enable immediate correction (`[AC-008]`).
5. **Error (system / storage error)**: Non-blocking warning banner notifies user of local database error with an actionable retry button (`[AC-008]`).

## 3. Screen states
### S-01 Dashboard & Activity Overview
- **Loading**: Skeleton layout mirroring summary cards and operational activity feed with animated pulse effect.
- **Empty**: Informational banner stating "No operational activity recorded today", accompanied by a primary CTA button.
- **Populated**: Metric cards showing active records, system operational health, and searchable activity table.
- **Error**: High-visibility banner stating "Unable to load dashboard metrics. Check local database connection", with a "Retry" button.
- **No Permission**: Clean access-restricted view stating "Your role does not have authorization to view operational dashboard metrics".

### S-02 Airframe maintenance work order dispatch and digital sign-off
- **Loading**: Form and table skeleton displaying field placeholders and action button outlines with shimmer animation.
- **Empty**: Clean workspace ready for data entry with autofocused input and primary "Airframe maintenance work order dispatch and digital sign-off" CTA button.
- **Populated**: Structured interactive view displaying validated records, operational status badges, and action controls.
- **Error**: High-contrast error callout detailing field validation failures or local SQLite query errors, with an actionable "Retry" button.
- **No Permission**: Access-restricted notification stating "Access restricted: Only authorized personnel ([P-01]) may perform this action".

### S-03 Line-maintenance discrepancy squawk logging and corrective action tracking
- **Loading**: Form and table skeleton displaying field placeholders and action button outlines with shimmer animation.
- **Empty**: Clean workspace ready for data entry with autofocused input and primary "Line-maintenance discrepancy squawk logging and corrective action tracking" CTA button.
- **Populated**: Structured interactive view displaying validated records, operational status badges, and action controls.
- **Error**: High-contrast error callout detailing field validation failures or local SQLite query errors, with an actionable "Retry" button.
- **No Permission**: Access-restricted notification stating "Access restricted: Only authorized personnel ([P-02]) may perform this action".

### S-04 Time-controlled component life limit and airworthiness directive monitoring
- **Loading**: Form and table skeleton displaying field placeholders and action button outlines with shimmer animation.
- **Empty**: Clean workspace ready for data entry with autofocused input and primary "Time-controlled component life limit and airworthiness directive monitoring" CTA button.
- **Populated**: Structured interactive view displaying validated records, operational status badges, and action controls.
- **Error**: High-contrast error callout detailing field validation failures or local SQLite query errors, with an actionable "Retry" button.
- **No Permission**: Access-restricted notification stating "Access restricted: Only authorized personnel ([P-03]) may perform this action".

### S-05 FAA Form 8130 airworthiness approval release and compliance audit export
- **Loading**: Form and table skeleton displaying field placeholders and action button outlines with shimmer animation.
- **Empty**: Clean workspace ready for data entry with autofocused input and primary "FAA Form 8130 airworthiness approval release and compliance audit export" CTA button.
- **Populated**: Structured interactive view displaying validated records, operational status badges, and action controls.
- **Error**: High-contrast error callout detailing field validation failures or local SQLite query errors, with an actionable "Retry" button.
- **No Permission**: Access-restricted notification stating "Access restricted: Only authorized personnel ([P-04]) may perform this action".
"""

old_aerofleet_db_text = """# Visual Design Brief & Design System Specification: AeroFleet Hangar

## 1. Design Principles & Theme Architecture
Local-first, high data density per FAA AC 20-175 and MIL-STD-1472.

## 2. Colours
| Token | Light | Dark | Use | Contrast on Background |
|---|---|---|---|---|
| `--color-background` | `#f8fafc` | `#0f172a` | App page background | Baseline |
| `--color-primary` | `#0284c7` | `#38bdf8` | Primary interactive buttons | 4.67:1 (PASS) |
| `--color-text` | `#0f172a` | `#f8fafc` | Primary body text | 15.8:1 (PASS) |

Derived from military aviation standards FAA AC 20-175 and MIL-STD-1472.
"""

aerofleet_dir = os.path.join(os.path.dirname(__file__), "..", "data", "projects", "a1f0e4b8-8c3d-4952-b68a-92e105db084c")
aerofleet_prd_path = os.path.join(aerofleet_dir, "docs", "prd.md")
aerofleet_arch_path = os.path.join(aerofleet_dir, "docs", "architecture.md")
aerofleet_qa_path = os.path.join(aerofleet_dir, "qa_log.json")

with open(aerofleet_prd_path, "r", encoding="utf-8") as f:
    prd_old_text = f.read()
with open(aerofleet_arch_path, "r", encoding="utf-8") as f:
    arch_old_text = f.read()
with open(aerofleet_qa_path, "r", encoding="utf-8") as f:
    qa_old_log = json.load(f)

# Evaluate with judge
verdict_case2 = evaluate_design_with_judge(
    app_flow_text=old_aerofleet_af_text,
    design_brief_text=old_aerofleet_db_text,
    prd_text=prd_old_text,
    parsed_ba={"app_name": "AeroFleet Hangar", "qa_log": qa_old_log},
    rubric_path="skills/designer/rubric.json",
    architecture_text=arch_old_text
)

print(f"\nPass: {verdict_case2.get('pass')}")
print(f"Total Score: {verdict_case2.get('total')}/{verdict_case2.get('max')}")
print(f"Verdict Summary: {verdict_case2.get('verdict_summary')}")
print(f"Unsupported Claims Count: {len(verdict_case2.get('unsupported_claims', []))}")

print("\n--- Detected Fatal Flaws in Old AeroFleet Deliverable ---")
for idx, uc in enumerate(verdict_case2.get("unsupported_claims", []), 1):
    print(f"{idx}. [{uc.get('section', 'General')}] {uc.get('reason')}")
    print(f"   Context snippet: {uc.get('text')}")

# Assertions verifying Judge correctly caught the old AeroFleet flaws:
assert verdict_case2.get("pass") is False, "Judge MUST FAIL old AeroFleet deliverable!"

reasons_case2 = [uc.get("reason", "") for uc in verdict_case2.get("unsupported_claims", [])]

has_dup_states = any("duplicate state" in r.lower() for r in reasons_case2)
assert has_dup_states, "Judge must catch identical screen state sentences across screens S-02..S-05!"

has_screen_name_len = any("screen name" in r.lower() for r in reasons_case2)
assert has_screen_name_len, "Judge must catch screen name length violations (> 5 words)!"

has_ungrounded_std = any(
    ("standard" in uc.get("reason", "").lower() and "ungrounded" in uc.get("reason", "").lower()) or
    ("faa ac" in uc.get("text", "").lower() or "mil-std" in uc.get("text", "").lower())
    for uc in verdict_case2.get("unsupported_claims", [])
)
assert has_ungrounded_std, "Judge must catch ungrounded standards (FAA AC 20-175, MIL-STD-1472)!"

print("\n>>> PROOF COMPLETE (CASE 2): Judge successfully and deterministically REJECTED the old AeroFleet deliverable with exact defect identification across duplicate states, screen name length, and ungrounded standards!")


# ==============================================================================
# CASE 3: CURRENT / OLD SITEAUDIT PRO APP-FLOW & DESIGN BRIEF AUDIT (Round 4 Item 7)
# Fatal defects in previous SiteAudit output:
# 1. Template residue in J-2: 'submits required parameters for', 'writes telemetry', 'out-of-spec measurements', 'technician', 'disk I/O latency'
# 2. Contrast failures on dark surface: primary 4.14, secondary 3.96, error 3.60, warning 3.74
# 3. Ungrounded UI elements: 'PDF Summary', 'Assigned Contractor', 'ISO-standard deficiency codes', 'bounding boxes'
# 4. Cross-section consistency: NFR-01 latency conflict, 100% offline vs real-time telemetry cloud contradictions
# ==============================================================================
print("\n" + "="*70)
print("=== CASE 3: RUNNING JUDGE ON OLD SITEAUDIT DELIVERABLE (DEFECT DETECTION) ===")
print("="*70)

siteaudit_dir = os.path.join(os.path.dirname(__file__), "..", "data", "projects", "5514241c-ef82-4092-b91f-a9cf94290f58")
siteaudit_af_path = os.path.join(siteaudit_dir, "docs", "app-flow.md")
siteaudit_db_path = os.path.join(siteaudit_dir, "docs", "design-brief.md")
siteaudit_prd_path = os.path.join(siteaudit_dir, "docs", "prd.md")
siteaudit_arch_path = os.path.join(siteaudit_dir, "docs", "architecture.md")
siteaudit_qa_path = os.path.join(siteaudit_dir, "qa_log.json")

with open(siteaudit_af_path, "r", encoding="utf-8") as f:
    siteaudit_af_text = f.read()
with open(siteaudit_db_path, "r", encoding="utf-8") as f:
    siteaudit_db_text = f.read()
with open(siteaudit_prd_path, "r", encoding="utf-8") as f:
    siteaudit_prd_text = f.read()
with open(siteaudit_arch_path, "r", encoding="utf-8") as f:
    siteaudit_arch_text = f.read()
with open(siteaudit_qa_path, "r", encoding="utf-8") as f:
    siteaudit_qa_log = json.load(f)

verdict_case3 = evaluate_design_with_judge(
    app_flow_text=siteaudit_af_text,
    design_brief_text=siteaudit_db_text,
    prd_text=siteaudit_prd_text,
    parsed_ba={"app_name": "SiteAudit Pro", "qa_log": siteaudit_qa_log},
    rubric_path="skills/designer/rubric.json",
    architecture_text=siteaudit_arch_text
)

print(f"\nPass: {verdict_case3.get('pass')}")
print(f"Total Score: {verdict_case3.get('total')}/{verdict_case3.get('max')}")
print(f"Verdict Summary: {verdict_case3.get('verdict_summary')}")
print(f"Unsupported Claims Count: {len(verdict_case3.get('unsupported_claims', []))}")

print("\n--- Detected Fatal Flaws in Old SiteAudit Deliverable ---")
for idx, uc in enumerate(verdict_case3.get("unsupported_claims", []), 1):
    print(f"{idx}. [{uc.get('section', 'General')}] {uc.get('reason')}")
    print(f"   Context snippet: {uc.get('text')}")

# Mandatory assertion per Round 4 Item 7: Judge MUST FAIL the current SiteAudit deliverable!
assert verdict_case3.get("pass") is False, "Judge MUST FAIL the current/old SiteAudit app-flow.md!"

reasons_case3 = [uc.get("reason", "") for uc in verdict_case3.get("unsupported_claims", [])]

# Verify contrast failures on dark surface were detected
has_contrast_surface = any("surface" in r.lower() and "contrast" in r.lower() for r in reasons_case3)
assert has_contrast_surface, "Judge must catch contrast failure on dark surface in SiteAudit!"

# Verify template residue in J-2 was detected
has_template_residue = any("template" in r.lower() for r in reasons_case3)
assert has_template_residue, "Judge must catch template filler residue in SiteAudit J-2!"

# Verify ungrounded UI elements were detected
has_ungrounded_elements = any("ungrounded ui element" in r.lower() for r in reasons_case3)
assert has_ungrounded_elements, "Judge must catch ungrounded UI elements in SiteAudit!"

print("\n>>> PROOF COMPLETE (CASE 3): Judge successfully and deterministically REJECTED the old SiteAudit deliverable with exact defect identification across template residue, surface contrast, and ungrounded UI elements!")


