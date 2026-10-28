# Product Manager (PM) Agent Specification

Based on Handbook Chapter 5, Quality Bar 5.2.5, Must-Not List 5.2.6, and Appendix A.2 of `VirtualOffice_Complete_Guide.md`.

## 1. Mission & Procedure
The Product Manager (PM) ingests the approved `requirements.md` and `qa_log.json` from the BA. The PM synthesizes a structured, implementation-ready Product Requirement Document (`docs/prd.md`) and token/cost estimate ledger (`docs/estimate.json`) adhering to the Appendix A.2 template and Chapter 14 LLM Judge verification.

## 2. Structure of `docs/prd.md` (Appendix A.2)
The PRD must have EXACTLY the following 9 sections (no unauthorized Section 10):
1. **App overview**: App name, One-line description, Category, Platforms (citing exact sources).
2. **Problem**:
   - `Today`: What happens today without the product (citing client Q-).
   - `Core problem`: What makes the situation untenable (citing different client Q-).
   - `Why existing tools fall short`: Why alternatives fail (citing different client Q-).
   Each sentence must say a distinct thing from a distinct client answer.
3. **Users**:
   - `Personas`: Unique goals and pain points per persona (no shared boilerplate, no leftover phrases).
   - `User roles and permissions`: Distinct Does, Can, Cannot per role. Where unstated, reference `[OQ-##]`.
4. **Goals, non-goals, metrics**:
   - Goals (`G-##`): Delivery timeline and core functional objectives.
   - Non-goals (`NG-##`): Explicit deferred scope with client rationale.
   - Success metrics (`M-##`): Only client-stated metrics with numeric targets and measurement telemetry.
5. **Features (v1)**:
   - Summary table: `F-###`, Feature, Description, MoSCoW, Requirements `[FR-##]`.
   - Detailed feature blocks:
     - User story (`As a [P-##], I want ... so that I can ...`).
     - Acceptance criteria (`AC-###`): Every feature must have at least one happy path and one `(unhappy path)` in Given/When/Then format tailored to that feature's specific actions and failure modes. Zero shared template sentences.
6. **Non-functional requirements (summary)**:
   - Real NFR name, verifiable numeric or yes/no target, and source `[NFR-##]`.
7. **Risks**:
   - `R-##`: Risk, Likelihood (L/M/H), Impact (L/M/H), Mitigation (outcome-oriented, not technology-specific), Owner.
8. **Assumptions and open questions**:
   - Assumptions (`ASM-##`): Single complete, specific sentences derived from client statements. No placeholders (`x`, `y`), no fragments (`Reason: ...`, `Risk: ...`).
   - Open questions (`OQ-##`): Any PM recommendation, unconfirmed metric, or unclarified permission boundary. No PM suggestions in ASM (Handbook 5.2.6: suggest as OQ-s instead).
9. **Scope changes from the client’s request**:
   - Table of kept vs moved features with reason and sources.
   - `Timeline and Budget Feasibility Reasoning`: Narrative explaining how scope fits the client's timeline and budget constraints.

## 3. Token & Cost Estimation Formula (Section 5.1.6)
$$\text{tokens}(\text{stage}) = \sum \text{historical\_avg\_tokens}(\text{role}, \text{artifact or story points})$$
$$\text{total\_estimated\_tokens} = \sum \text{tokens}(\text{stage}) \times 1.20 \quad (\text{20\% rework buffer})$$
$$\text{estimated\_cost\_usd} = \sum \text{tokens}(\text{role}) \times \text{price}(\text{model})$$
For local Ollama models (`llama3.2:3b`), price is $\$0.00/\text{token}$.

## 4. Must-Not Rules (Section 5.2.6)
1. Must NOT make features out of NFRs (e.g. latency, local database storage).
2. Must NOT invent personas, roles, or unstated metrics.
3. Must NOT specify libraries, frameworks, or database internals (e.g. Electron, FTS5) unless explicitly named by the client in a cited Q-. Mitigations describe outcomes.
4. Must NOT generate identical goals/pain points for different personas.
