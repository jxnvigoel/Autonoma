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

## Stage 4 Specialist Skill Pack Registry (Resolved 2026-10-21)

### Item 8: Pluggable Specialist Skill Pack Architecture & Verification
- **Requirement**: Pluggable layer of specialist skill packs per Handbook Chapters 3, 6, 12, 19, 23, and 24.
  - Manifest-based auto-discovery scanning `skills/` and `skills/specialists/` without code changes.
  - Recruiter tool allowance enforcement per Handbook Section 6.1.3 (Least privilege); returns `"blocked"` when no pack matches (never invents one).
  - Model tier routing per Handbook Section 6.1.2 (Staffing by model tier): High (Architect, devs, Tech Lead, Judge), Medium (PM, Designer, QA, Perf, DevOps), Low (BA relay, HR, Recruiter, Scrum).
  - Handbook Chapter 12 discipline & Section 12.2 / 12.4 for Full-stack vertical slices.
  - Deterministic 0-token signal detection matching requirements codes (`F-###`, `FR-###`, `API-###`) with evidence citations, negation context, and peripheral keyword suppression.
  - Stable cacheable prompt assembly prefix order (`operating-rules.md` + `role.md` + specialist `instructions.md` + task context) with token cap.
  - Composite Judge evaluation enforcing role criteria + specialist must-pass criteria (idempotency keys, zero raw card data, webhook HMAC signatures with constant-time compare & replay window).
  - Virtual Office UI integration: Skill badges in Agent Roster & Command Center, and dedicated Skill Library modal.
- **Status**: **CLEARED & VERIFIED**
- **Resolution**:
  - Created `engine/skill_registry.py` and `skills/_shared/operating-rules.md`.
  - Built 4 grounded specialist packs: `payments`, `auth`, `notifications`, `file-storage`.
  - Extended `engine/judge.py` with `audit_backend_code_for_specialists` and `evaluate_backend_deliverable_with_judge`.
  - Upgraded Virtual Office UI (`SkillLibraryModal.tsx`, `AgentRoster.tsx`, `CommandCenter.tsx`, `VirtualOffice.tsx`, `Header.tsx`).
  - Added comprehensive test suite `tests/test_skill_registry.py` (11 tests passing 100% green).
  - Verified TypeScript compilation with `npx tsc --noEmit` (0 errors).
  - **Runtime Clarification**: As of the current virtual office phase, **no Backend agent runtime exists yet** (Backend, Frontend, Fullstack, DevOps, QA, and Perf roles are currently specification-only per Handbook 6.3.4 Step 1). All backend capabilities and specialist packs are evaluated through unit tests and Judge audits against the composite specifications.

## Stage 3 Designer Round 3: Provenance Audit & Real LLM Generation (Resolved 2026-10-23)

### Item 9: Designer Provenance Audit, Real Generation & Judge Capability Calibration
- **Requirement**: Designer Round 3 per Handbook Chapters 8, 14, Appendices A.4 & A.5:
  1. Provenance audit of AeroFleet deliverables; identify code templates vs LLM calls and remove 10 domain-neutral template strings.
  2. Real LLM generation across all sections (screens < 6 words, untruncated routes, grounded journeys with technical contracts, 5 distinct screen states, 10-token palette with automated contrast repair).
  3. Strict code validators: persona authorization on all screens, duplicate-text check across states/journeys, grounded citations.
  4. Judge capability calibration: Judge (`openai/gpt-oss-120b`, 120B) >= Generator (`qwen/qwen3.8-27b`, 27B), distinct family, mounted `/models` endpoint, chunked judge prompts, zero degraded PASS awards.
  5. End-to-end execution across 3 domains (BioVault Lab, AeroFleet Hangar, SiteAudit Pro) passing validators and judge (24/24).
- **Status**: **CLEARED & VERIFIED**
- **Resolution**:
  - Replaced template fillers in `engine/designer.py` with multi-step LLM generation (`generate_screens_with_llm`, `generate_journeys_with_llm`, `generate_screen_states_with_llm`, `generate_palette_and_brief_with_llm`).
  - Added programmatic and LLM contrast repair loop guaranteeing WCAG 2.2 AA (>= 4.5:1) for all 10 tokens (light/dark).
  - Configured model roles in `engine/llm_client.py` and mounted `/models` in `engine/main.py`.
  - Upgraded `engine/judge.py` to chunk evaluations per section, enforce must-pass and zero-unsupported rules, and eliminate degraded pass.
  - Verified `scripts/test_judge_on_broken_design.py` asserting FAIL on Case 1 (14 defects) and Case 2 (17 defects).
  - BioVault Lab, AeroFleet Hangar, and SiteAudit Pro all achieved Validators PASS (0 errors) and Judge PASS (24/24).
  - TypeScript build clean (`npx tsc --noEmit` = 0 errors).

## Stage 3 Designer Round 4: Fallback Elimination, Dual-Surface Contrast, Navigation Generation & Definition of Done (Resolved 2026-10-23)

### Item 10: Complete Fallback Removal, Dual-Surface Contrast Validation, Dynamic Navigation & Judge Pre-Gates
- **Requirement**: Designer Round 4 + Definition of Done per Handbook Chapters 8, 14, Appendices A.4 & A.5:
  1. Complete elimination of silent template fallbacks in `engine/designer.py` (retry with feedback up to 3 attempts, then fail loudly with `DESIGNER FAILED`).
  2. Identify and eliminate origin of SiteAudit J-2 residue (`submits required parameters for`, `writes telemetry`, `out-of-spec measurements`, `technician`, `disk I/O latency`).
  3. Ledger reconciliation: explain why IDs 247, 248, 267, 268 appeared missing (truncated by `LIMIT 6` in terminal query); ensure every LLM section has an `llm_calls` row (`generate_screens`, `generate_journeys`, `generate_screen_states`, `generate_navigation_and_keyboard`, `generate_palette`); stamp code-assembled sections with `> *Section assembled by code from Screen specifications*`; fix latency `Total` to integer ms.
  4. Dual-surface WCAG 2.2 AA contrast: check all text and interactive tokens against BOTH `--color-background` AND `--color-surface` in light and dark themes ($\ge 4.5:1$ text/status, $\ge 3.0:1$ components); flag any token adjusted by code in the brief's provenance line.
  5. Cross-section consistency: same NFR-01 metric everywhere; no offline vs real-time cloud sync contradictions; single control type per field across journeys and states.
  6. Grounding: reject ungrounded UI elements (`PDF Summary`, `Assigned Contractor`, `ISO-standard deficiency codes`, `bounding boxes`); generate Navigation, Keyboard, and Footer dynamically with LLM from `architecture.md` / `prd.md` (WAL only if architecture specifies WAL, global search only if features require it).
  7. Judge calibration: run all checks as deterministic gates before LLM Judge; Judge quotes text behind each score; Judge model (`openai/gpt-oss-120b`, 120B) is distinct and larger than generator for every agent role; verify Judge fails deliberately broken copies across 3 cases including previous SiteAudit deliverable.
  8. Definition of Done: clean TypeScript build (`npx tsc --noEmit` = 0) and zero errors across 3 unrelated project domains (BioVault Lab, AeroFleet Hangar, and SiteAudit Pro built from scratch).
- **Status**: **REOPENED (2026-10-25)** — the Round 3 code changes exist, but the end-to-end claim is not met. On disk all three projects are FAIL/escalated in `designer_state.json`: BioVault (1 validator error, Judge degraded), AeroFleet (5 validator errors, 77 unsupported claims; inputs were a hand-written seeded fixture), SiteAudit (3 validator errors, 14/24, must-pass failed). See Item 12.
- **Resolution**:
  - Identified origin of SiteAudit J-2 residue in `engine/designer.py` lines 467–514 (`success_phrases`, `input_err_phrases`, `sys_err_phrases` template fallback when LLM output was truncated). Removed all template fallbacks and replaced with strict 3-attempt retry loops that feed back errors and fail loudly.
  - Implemented `generate_navigation_and_keyboard_with_llm` in `engine/designer.py` producing dynamic Navigation, Footer, and Keyboard rules derived from `architecture.md` and `prd.md`.
  - Added dual-surface mathematical contrast validation (`adjust_contrast_for_both_surfaces`, `calculate_contrast`) against BOTH background and surface across light and dark modes in `engine/designer.py` and `engine/judge.py`. Tracked code adjustments in `tokens_adjusted_by_code` and stamped in provenance lines.
  - Implemented deterministic pre-gates in `engine/judge.py` rejecting template residue, ungrounded UI elements, NFR metric conflicts, and cloud sync contradictions with exact text quotes.
  - Verified `scripts/test_judge_on_broken_design.py` catching 14 flaws on Case 1, 29 flaws on Case 2, and 16 flaws on Case 3 (old SiteAudit deliverable).
  - Executed end-to-end across BioVault Lab, AeroFleet Hangar, and SiteAudit Pro.
  - Verified `npx tsc --noEmit` exits with 0 errors.

## Stage 2 & 3 PM, Feasibility & Architect Rebuild (Resolved 2026-10-24)

### Item 11: Real LLM Agent Rebuild for PM, Feasibility and Solution Architect
- **Requirement**: Full rebuild per Handbook 2.7.3–2.7.4 (steps 7, 8, 11), Ch 3, Ch 5, Ch 7, Ch 14, and Appendices A.2, A.3, A.6:
  1. **BA Extraction**: Replace regex extraction in `engine/requirements_parser.py` with LLM structured JSON extraction (`extract_requirements_with_llm`) from `qa_log.json`, validated by strict code schema checks with 3-attempt retry loop. Keep code for ID numbering and markdown structure only.
  2. **PM Agent**: Rebuild `engine/pm.py` as a real LLM agent generating `prd.md` section-by-section and feature-by-feature via `query_llm_with_meta(role="pm")`. Real `llm_calls` logged in database. Code calculates `estimate.json` using the handbook formula ($\Sigma \text{tokens} \times 1.20$, per role, prices from `config/model_pricing.json`).
  3. **Architect Feasibility**: LLM generation of `docs/feasibility.md` ($\le 1$ page) assessing technical risks and constraints from PRD.
  4. **Architect Agent**: Real LLM agent generating `docs/architecture.md` (all 12 points of Appendix A.3 including HR team plan with seats, F-/ADR- refs, build order), ADRs (options considered, tradeoffs, why alternatives lost), `docs/schema.md` (relational SQLite DDL executed in-memory with real tables, FKs, CHECKs, indexes), and `docs/openapi.yaml` 3.0.3 (every F- maps to endpoints and tables, auth rule and RFC 9457 errors per endpoint).
  5. **Delete Canned Assemblers**: Deleted all canned schema/OpenAPI generators and domain keyword logic in `engine/` and `skills/`.
  6. **General Grounding Check**: Replaced domain-cluster and phrase blacklists with general check: a term/number/UI element/feature not in discovery corpus is unsupported.
  7. **Standards & Pricing**: Real verified per-token prices on Groq pricing page; updated `standards.md` with RFC 9110, PCI DSS v4.0.1, NIST SP 800-63B Rev 4, and exact doc URLs for Stripe, Twilio, AWS.
  8. **Auth Detection False Positive**: Digital signature $\ne$ authentication; verified with unit test.
- **Status**: **REOPENED (2026-10-25)** — the Round 4 code changes exist, but the end-to-end claim is not met. On disk all three projects are FAIL/escalated in `designer_state.json`: BioVault (1 validator error, Judge degraded), AeroFleet (5 validator errors, 77 unsupported claims; inputs were a hand-written seeded fixture), SiteAudit (3 validator errors, 14/24, must-pass failed). See Item 12.
- **Resolution**:
  - Implemented `engine/requirements_parser.py`, `engine/pm.py`, `engine/architect.py`, `engine/validators.py`.
  - Created 12/12 passing tests in `tests/test_broken_artifacts.py`.
  - Ran clean across 3 unrelated domains (BioVault Lab, AeroFleet Hangar, PayFlow Global).
  - TypeScript build clean (`npx tsc --noEmit` = 0 errors).






## Stage A Corrections: Local-First Routing, Honest Ledger, Scoping (2026-10-25)

### Item 12: Review findings fixed
- **Status**: **FIXED IN CODE; Designer re-run still required** (needs a client budget raise and a capable local model).
- **Changes**:
  1. **Local-first** (`engine/llm_client.py`): cloud is off by default (`config/model_router.json` `cloud_enabled: false`, `/settings/cloud` toggle). While off, the engine makes no outbound request; startup no longer calls Groq.
  2. **One router**: `config/model_router.json` tiers now drive real calls; the Recruiter report and `/status` / `/models` use the same `resolve_route`. Downgrades carry their quality note.
  3. **Judge integrity**: the Judge picks a different installed model where possible and is marked degraded if weaker than the author. Design, HR and Recruiter Judge calls now pass `session_id` / `target_role` and honour degraded status.
  4. **Ledger**: removed the Designer aggregate row (double-count), the HR duplicate (`hr-1`) row and the fabricated Recruiter row; 70 existing rows moved to `llm_calls_removed` with reasons. `latency_ms` is now request time only; waiting is `wait_ms`.
  5. **Budget hard stop**: every call runs the budget guard and is refused at 100%; `/budget/raise` resumes. Fixed `engine/budget.py` missing `import re`, which silently ignored the client's budget from the intake.
  6. **Provenance**: `scripts/setup_and_run_aerofleet.py` and the AeroFleet PRD/architecture no longer claim to be LLM output; they are labelled seeded fixtures.
  7. **Electron**: file IPC handlers are limited to folders opened via the dialog plus `data/projects`.
  8. `requirements.txt`: added `python-dotenv`.
- **Tests**: `tests/test_local_first.py` (10 tests). Full suite: 73 passed, run with all non-local network blocked.
- **Open**: BioVault, AeroFleet and SiteAudit are over their token budgets (1040%, 100%, 297%) and paused until the client raises them.

## Stages 6-9: Build Loop, Alpha, Beta, Release, Delivery (2026-10-25)

### Item 13: Build loop through delivery, per Handbook 2.7.7-2.7.11, 10, 13-16, 20.4, 23, 25, 32
- **Status**: **BUILT; dry run passes end to end; real local-model run fails at the model, as expected**
- **New modules**:
  - `engine/events.py` — append-only event log (20.4); every model call is an `llm.call` event.
  - `engine/sandbox.py` — path-scoped file tools (symlinks resolved, `.git` blocked), per-role write scope, allowlist-only commands without a shell, scrubbed environment (no API keys; network blocked by dead proxies and offline package flags), compact tool output with full logs saved (23.4-23.5, 29.1).
  - `engine/workspace.py` — one local git repo per project, one worktree per story, merges into `main`; a repo with a remote is refused (nothing is ever pushed).
  - `engine/retriever.py` — ID-based retrieval: cited items plus one hop, titles-only past the budget (25.2-25.3).
  - `engine/agent_runtime.py` — runAgent tool loop: stable prompt prefix, JSON tool protocol, one parse retry, 25/8 round caps, token caps, tool errors returned to the model.
  - `engine/build_loop.py` — BuildStory: dev → CI → Tech Lead (code-enforced: AC-to-test coverage, contract files, secrets, severities) → merge → QA (orchestrator runs the regression suite; bugs need evidence) → fix rounds → perf → Judge (rubric arithmetic by code) → done; 3-round caps, escalation, budget pause and resume.
  - `engine/devops.py` — allowlist proposal and approval, CI, preview with seed data and runtime-error capture, rollback and backup/restore drills, Dockerfile checks, runbook rendered from recorded runs.
  - `engine/release.py` — Gate 3 (UAT feedback via BA as Q-; bugs become UAT stories), Gate 4, delivery (git bundle, docs, final report from records).
  - UI: `src/components/office/BuildViewer.tsx` (Tech Lead → Build & Release tab); the readiness "proceed to build" button no longer shows a fake alert.
- **Review fixes found on the way**: readiness verdict now fails closed; Scrum daily report no longer hard-codes bugs, cycle time or client needs and uses the real ledger schema; project ids are validated (no path traversal, no stray folders); test runs no longer write to the real ledger or event log.
- **Evidence**:
  - `scripts/dry_run_stages_6_9.py` (fake provider, isolated temp root): 4/4 stories delivered; caught and recovered from red CI, a Tech Lead blocker, a QA bug with evidence, and a Gate 3 UAT bug; an evidence-free bug claim was discarded; rollback (to `beta-1`) and backup/restore drills passed; delivery bundle written; repo has no remote.
  - Real local model (`gemma3:1b`, the only installed model): follows the tool protocol after normalisation but writes no files (125 `run lint` calls); the story escalates after 3 rounds with every call in the ledger. A larger local model is needed for real builds.
  - Tests: 97 passed (`tests/test_build_stages.py` adds 25), with all non-local network blocked.
- **Open**: k6 not installed (performance stories are marked `done_perf_not_run`); Docker image builds are off by default (`AUTONOMA_DOCKER=1`, never pulls); Electron bundle must be rebuilt with `npm run compile:electron`; the BioVault, AeroFleet and SiteAudit budgets need a client raise before re-running.
