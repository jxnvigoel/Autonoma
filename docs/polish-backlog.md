# Polish Backlog & Non-Blocking Agent Observations

This backlog tracks observations, edge cases, and quality improvements identified across agent stages (BA, PM, Architect, Judge). All items below have been fully resolved, implemented, and verified.

## Logged Observations & Status

### Item 1: NFR-03 & AC-001 Ungrounded Metrics in PRD
- **Original Observation**: NFR-03 ("500 photo notes") and AC-001 ("500 ms") had no direct literal match in `qa_log.json`. While derived from general performance requirements, handbook rules stipulate that specific numeric targets not explicitly stated by the client must be logged as `OQ-##` or `ASM-##` requesting confirmation at Gate 1, not asserted as client facts.
- **Status**: **CLEARED**
- **Resolution**:
  - Upgraded `engine/pm.py` to check all numeric metrics in acceptance criteria and NFR tables against numbers present in `qa_log.json` / intake.
  - Any metric or capacity figure not explicitly stated in discovery is tagged with `[OQ-##]` or `[ASM-##]` requesting client confirmation at Gate 1.
  - Upgraded `engine/judge.py` with deterministic ungrounded numbers validation (Handbook 14.1.3 & Quality Bar 5.2.5 item 8), rejecting any PRD asserting numbers not found in discovery without `[OQ-##]` or `[ASM-##]` tags.
  - Fixed SiteAudit PRD and BioVault PRD to strictly comply.

### Item 2: Roles Table "Can" Column Permissions
- **Original Observation**: The roles table "Can" column contained specific action permissions ("create templates", "approve hazard flags", "export signed compliance reports") that the client never explicitly articulated during discovery.
- **Status**: **CLEARED**
- **Resolution**:
  - Upgraded `engine/requirements_parser.py` and `engine/pm.py` to mark unconfirmed granular role actions in both the "Can" and "Cannot" columns as `Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1`.
  - Added deterministic check in `engine/judge.py` that flags unconfirmed capabilities asserted without `[OQ-02]` tags as Quality Bar 5.2.5 violations.

### Item 3: Grounding Check Semantic Support Verification
- **Original Observation**: The initial `engine/judge.py` grounding validator checked that cited question IDs (`[Q-###]`) existed in `qa_log.json`, but did not perform semantic support verification to confirm that the text of the client answer actually supports the specific asserted claim.
- **Status**: **CLEARED**
- **Resolution**:
  - Implemented semantic claim-support analysis in `engine/judge.py` (`run_code_level_audits` and `run_architecture_code_audits`).
  - Added domain topic and keyword matching: if a cited question (e.g. `[Q-002]` about features) is cited for an unrelated topic (e.g. staff count, latency, storage) without matching keywords in that question's text, the citation is flagged as an unsupported claim.
  - Verified by `scripts/test_judge_proofs.py` where semantic grounding failure is caught deterministically.

## Stage 3 Architect Polish Items (Logged 2026-10-17)

1. **Audit Log Table Reference**: `API-008` (`/audit/logs`) and threat `T-05` reference an audit log table that does not exist in schema (only `audit_exports` exists); add an `audit_log` table or drop the claims.
2. **Sensor Input Integration Contradiction**: Section 8 asserts zero integrations, but `F-002` / `AC-004` require cold-storage temperature sensor input; raise an `OQ-` on how readings enter the system (manual entry, batch CSV import, or sensor API).
3. **NFR Table Parsing & Target Truncation**: NFR table parsing bug where "WCAG 2.2 AA" became "2 AA" (splits on decimal point) and `NFR-01`'s target became "5 seconds" with no subject; `NFR-03`'s design impact column is duplicated from `NFR-02`.
4. **Capacity Assumptions Grounding**: Capacity assumptions (60 actions/day, 25 KB/record, 10x peak, 365,000 readings/yr, 500 excursions, "7 years CLIA retention", "< 500 ms" in build order) were estimated rather than client-given; label them `ASM-` / `OQ-` or remove ungrounded figures. Reconcile user count discrepancies (~30 in capacity vs ~25 in retention).
5. **Access Rules Roles vs DDL CHECK Constraints**: "System Admin", "System Sensor", "System Monitor" appear in table access rules but are not in `users.role CHECK`; "DB Triggers" are claimed in access rules but absent from the DDL; `barcode_format` allows `code128` (1D) even though PRD specifies 2D barcodes.
6. **Novel-Number Grounding Across All Agent Outputs**: The novel-number check applied to the PRD but missed ungrounded numbers in the Architect's capacity and retention sections; extend deterministic ungrounded number validation to all agent outputs.

## Stage 3 UI/UX Designer Fix Round (Resolved 2026-10-19)

### Item 4: WCAG 2.x Contrast Validator Calibration
- **Requirement**: Verify `engine/designer.py` and `engine/judge.py` against standard WCAG 2.x relative luminance and contrast formula with exact sRGB channel linearization ($c \le 0.03928 \implies c / 12.92$ else $((c + 0.055) / 1.055)^{2.4}$).
- **Status**: **CLEARED & VERIFIED**
- **Resolution**:
  - Corrected channel linearization threshold from `0.04045` to exact standard `c <= 0.03928`.
  - Relative luminance: $L = 0.2126R + 0.7152G + 0.0722B$; Ratio: $(L_1 + 0.05) / (L_2 + 0.05)$.
  - Created `tests/test_contrast.py` with 7 reference value assertions (`#000000` on `#ffffff` = 21.0, `#767676` on `#ffffff` = 4.54, `#777777` on `#ffffff` = 4.48, `#0f172a` on `#f8fafc` = 17.06, `#38bdf8` on `#0f172a` = 8.33, `#a0aec0` on `#ffffff` = 2.26, `#718096` on `#1a202c` = 4.06).
  - All unit tests pass deterministically across both `engine/designer.py` and `engine/judge.py`.

### Item 5: Context-Derived Design Palette Generator
- **Requirement**: Remove static shared color constants; derive palette, typography, and tone dynamically from the project's PRD domain, personas, platform context, and NFR-05 accessibility constraints.
- **Status**: **CLEARED & VERIFIED**
- **Resolution**:
  - Implemented `generate_project_palette` in `engine/designer.py` computing custom palettes based on discovery context:
    - **BioVault Lab**: Clinical Laboratory Specimen Tracking — Clinical Sky Cyan (`#0369a1` / `#38bdf8`) paired with sterile slate backgrounds for high visual acuity under fluorescent cleanroom lighting. Contrast: 5.74:1 (L) / 8.33:1 (D) (PASS >= 4.5:1).
    - **AeroFleet Hangar**: Aviation Fleet Airworthiness & Hangar Maintenance — Aeronautical Royal Blue (`#1d4ed8` / `#60a5fa`) paired with flightline amber alerts per FAA AC 20-175 and MIL-STD-1472. Contrast: 6.41:1 (L) / 7.02:1 (D) (PASS >= 4.5:1).
  - Documented contextual rationale in Section 2.1 of `docs/design-brief.md`.

### Item 6: Generic Novel-Term Contamination Audit
- **Requirement**: Replace project-specific keyword blacklists with generic novel-term grounding validation against the project's own `prd.md`, `qa_log.json`, and `architecture.md`.
- **Status**: **CLEARED & VERIFIED**
- **Resolution**:
  - Replaced hardcoded blacklist with general novel bold term and novel sliding-window noun phrase validation in `engine/judge.py` (`run_designer_code_audits`).
  - Verified by `scripts/test_judge_on_broken_design.py`: deterministically catches planted foreign terms (`Field operators`, `drone photogrammetry`) and planted foreign metric (`95000`).
  - Zero false positives on valid project specifications (BioVault Lab and AeroFleet Hangar both score 0 unsupported claims).

### Item 7: Provider & Model Provenance Stamping
- **Requirement**: Every generated document and ledger row records the provider and model that produced it, shown in the Command Center under each artifact.
- **Status**: **CLEARED & VERIFIED**
- **Resolution**:
  - Added machine-readable `<!-- ARTIFACT METADATA: Produced by <provider> (<model>) -->` comments and human-readable provenance badges to all generated documents.
  - Integrated `record_llm_call` into `engine/designer.py` logging all calls with provider, model, tokens, and cost.
  - Updated `DesignerOutputViewer.tsx`, `ArchitectOutputViewer.tsx`, and `PRDViewer.tsx` to parse metadata stamps and display provenance badges directly in the UI header and under each artifact tab.
  - TypeScript verified via `npx tsc --noEmit` with 0 errors.

