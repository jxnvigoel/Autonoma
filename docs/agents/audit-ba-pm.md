# BA to PM Agent Audit & Handoff Specification

Based on Handbook Sections 4, 5, Chapter 14 (LLM Judge), Quality Bar 5.2.5, Must-Not 5.2.6, and Appendix A.1/A.2.

## 1. BA Audit Against Handbook Section 4 & Appendix A.1
An end-to-end audit of the Business Analyst agent was performed across all Handbook requirements:

### A. Section 4.2 Job Description Alignment
- **Mission**: Verified. BA operates as the single channel between client and virtual office, outputting `docs/requirements.md` and immutable `qa_log.json`.
- **Inputs & Outputs**: Verified. Inputs take intake form, Q&A log (`Q-###`), and open questions (`OQ-###`). Outputs produce Appendix A.1 compliant requirements and sequential `Q-###` entries.
- **Procedure & Discovery Checklist**: Verified. Discovery checklist covers problem, personas, journeys, FRs with MoSCoW, NFRs with quantified targets, data ownership/retention, integrations, timeline/budget, v1 vs later scope, and client success quotes.
- **Skill Files**: Verified. Added `skills/ba/role.md` and `skills/ba/rubric.json` to complete the skill pack per Section 4.2 and Chapter 14.

### B. Appendix A.1 Template Structure & Classification Audit
- **Strict FR vs NFR Classification**:
  - Functional Requirements (`FR-##`): Only user workflows and interactive business logic.
  - Non-Functional Requirements (`NFR-##`): Latency, throughput, local SQLite storage, offline operation, data privacy, HIPAA/CLIA compliance, desktop OS platform compatibility, and WCAG accessibility.
  - *Identified Gap*: LLM previously leaked platform compatibility (macOS/Windows) and WCAG accessibility into FRs.
  - *Resolution*: Upgraded `engine/requirements_parser.py` (`is_nfr_text`) with platform, OS, desktop, contrast, and accessibility indicators. Hardened prompt in `engine/main.py` with explicit negative constraints.
- **Traceability**: Every FR and NFR cites a verified `[Source: Q-###]`.
- **Assumptions and Open Questions**: Every unstated constraint or gap is logged as an `ASM-##` or `OQ-##` with single complete sentences, no placeholders (`[x]`, `[y]`), and no fragments.

## 2. Handoff Contract (BA to PM)
1. **Pre-requisite**: BA produces `docs/requirements.md` and complete `qa_log.json` with sequential `Q-###` citations.
2. **Deterministic Pre-checks**:
   - Zero NFRs listed as functional requirements (`FR-##`).
   - Zero ungrounded personas or generic boilerplate roles.
   - All client-requested numbers (timeline, budget, success metrics) present in `qa_log.json`.
3. **PM Ingestion**:
   - PM maps every Must-have `FR-##` to an `F-###`.
   - PM maps every `NFR-##` to Section 6 summary table.
   - PM maps deferred requests to `NG-##` in Section 4 and Section 9.
   - PM assigns happy-path and unhappy-path acceptance criteria (`AC-###`) to EVERY feature.
   - PM maps unconfirmed permissions in Roles table "Can" and "Cannot" columns to `[OQ-02]`.

## 3. Chapter 14 Independent LLM Judge & Rubric Verification
The PRD is graded by an independent LLM Judge using `skills/pm/rubric.json`:
- **Scoring Scale**: 8 criteria evaluated on 0–3 points (Maximum: 24).
- **Pass Threshold**: $\ge 20 / 24$ points with ZERO must-pass failures.
- **Audited Criteria**:
  1. `fr_coverage` (Must-pass): 100% of Must-have FRs covered in `F-###`.
  2. `acceptance_criteria` (Must-pass): Specific Given/When/Then criteria without vague fillers ("seamless", "user-friendly").
  3. `unhappy_paths` (Must-pass): Every feature must have an explicit `(unhappy path)` criterion.
  4. `non_goals_grounded`: Clean table of deferred items with client rationale.
  5. `metrics_and_measurement`: Numeric targets with verifiable telemetry query methods.
  6. `nfr_classification` (Must-pass): Zero technical/storage/latency constraints misfiled in Section 5.
  7. `hallucination_and_grounding` (Must-pass): Every cited Q- must exist in `qa_log.json` and semantically support the claim. Zero invented roles, ungrounded metrics, or filler text.
  8. `timeline_budget_feasibility`: Explicit feasibility reasoning for scope vs timeline/budget.

## 4. Strict Quality Gates & Defect Rejection Rules
The Judge immediately rejects artifacts if any of the following are detected:
- **Placeholder Defect**: Presence of `is x`, `is y`, ` x `, ` y `, `[x]`, `[y]`, `TBD`, `TODO`.
- **Fragment Defect**: Section 8 ASM/OQ rows starting with `Reason:`, `Risk:`, `Source:`, or under 30 characters.
- **Must-Not Violation**: PM recommendations or secondary metrics placed in `ASM-##` instead of `OQ-##`.
- **Tech Stack Leaks**: Unprompted mention of libraries/frameworks (e.g. Electron, FTS5) not specified by the client.
- **Duplication Defect**: Personas sharing identical goals or pain points, or Section 2 "Today" and "Core problem" having identical text or citing the same Q-.
- **Citation & Grounding Failure**: Any cited `Q-###` that does not exist in `qa_log.json`, asserts numbers not in `qa_log.json`, or cites a Q- that does not semantically support the asserted claim.
- **Cross-Project Contamination**: Presence of foreign domain terms or numbers from prior projects.

## 5. Audit Summary Matrix

| Requirement | Handbook Reference | Audit Status | Gap Identified | Resolution |
|---|---|---|---|---|
| BA Role Spec | Section 4.2 | PASS | `skills/ba/role.md` missing | Created `skills/ba/role.md` |
| BA Rubric | Section 4.2.6 & Ch 14 | PASS | `skills/ba/rubric.json` missing | Created `skills/ba/rubric.json` |
| FR/NFR Separation | Section 4.1.2 & A.1 | PASS | Desktop OS & WCAG in FR | Upgraded `is_nfr_text` & prompt |
| Template Alignment | Appendix A.1 | PASS | Minor table formatting gaps | Standardized parser and prompt |
| Grounding & Citations | Section 4.2.6 | PASS | No semantic check in Judge | Added semantic support check |
| Roles Table Permissions | Polish Backlog Item 2 | PASS | Unstated "Can" permissions | Tagged unconfirmed permissions `[OQ-02]` |
| Ungrounded Numbers | Polish Backlog Item 1 | PASS | Uncited numbers asserted | Numbers tagged `[ASM-##]` / `[OQ-##]` |
