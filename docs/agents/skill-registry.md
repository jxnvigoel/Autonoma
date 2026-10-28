# Specialist Skill Pack Registry Specification

Based on Virtual Office Handbook Chapter 6 (HR, Recruiter, and Skill Pack Registry), Chapter 3 (Operating Rules), Chapter 12 (Backend Role & Technical Discipline), Chapter 19 (Payments & Idempotency), Chapter 23 (Agent Runtime & Dynamic Assembly), and Chapter 24 (Evaluation & Verification).

---

## 1. Architectural Mission & Philosophy

The **Specialist Skill Pack Registry** is Autonoma's pluggable layer for attaching domain-specific expertise to virtual office agents without modifying agent runtime code or codebase scaffolding.

General-purpose role agents (Backend Engineer, UI/UX Designer, Architect, QA) possess universal best practices for their craft. However, specialized capabilities (e.g. PCI-compliant payment gateways, session/OAuth security, asynchronous multi-channel notifications, signed S3 file storage) require strict engineering discipline, zero-tolerance checklists, and customized evaluation rubrics.

### Core Handbook Rules
1. **Zero Invented Packs (Handbook 6.3.4 Step 1)**: If an incoming project requirement demands a specialist skill that does not exist in the registry, the Recruiter **MUST return blocked** naming the missing pack. Agents and Recruiters must **never** invent or hallucinate a non-existent skill pack.
2. **Strict Tool Boundaries (Handbook 6.1.3 Least privilege)**: Attaching a skill pack must **never** grant an agent tools beyond their core role allowance per Handbook 6.1.3 and 6.3.6. For example, attaching a performance-oriented pack to a backend role cannot grant `k6_run` (which is reserved exclusively for QA/Performance roles).
3. **Deterministic 0-Token Signal Detection (Handbook 23.2)**: Skill pack detection is performed deterministically against the project's PRD, discovery Q&A, and architecture documents with zero LLM token spend. Requirements identifiers (`F-###`, `FR-###`, `API-###`) provide verifiable evidence citations.
4. **Stable Cacheable Prompt Order (Handbook 23.4)**: Prompt assembly maintains a deterministic, cache-optimized prefix structure:
   `[Shared Operating Rules]` $\rightarrow$ `[Role Role.md]` $\rightarrow$ `[Attached Specialist Instructions (alphabetical)]` $\rightarrow$ `[Output Template / User Task]`.
5. **Composite Rubric Enforcement (Handbook 12 & 14)**: Deliverables produced by agents with attached packs are judged against the base role rubric **plus** each attached pack's specialist rubric. Must-pass criteria (such as zero raw card storage or webhook signature verification) cause immediate Gate failure if violated.

---

## 2. Directory Layout & Structure

Skill packs reside in `skills/` (core roles) and `skills/specialists/` (modular specialist packs).

```text
skills/
├── _shared/
│   └── operating-rules.md         # Universal Chapter 3 operating rules (prefix)
├── backend/                       # Role pack
│   ├── role.md                    # Core role instructions and boundaries
│   └── rubric.json                # 6 base criteria (18 pts max)
└── specialists/
    ├── payments/                  # Payments & Idempotency Specialist Pack
    │   ├── manifest.json          # Pack metadata, triggers, and tool boundaries
    │   ├── instructions.md        # Specialized engineering instructions
    │   ├── standards.md           # Engineering standards (PCI DSS, ISO 4217, etc.)
    │   ├── checklist.md           # Non-negotiable pre-flight checklist
    │   ├── rubric.json            # Specialist Judge criteria (must-pass)
    │   └── templates/             # Tested implementation templates
    │       ├── idempotency.sql    # Idempotency store DDL
    │       └── payment_handler.py # Gateway handler with HMAC & retry logic
    ├── auth/                      # Authentication & Session Specialist Pack
    ├── notifications/             # Multi-Channel Notification Specialist Pack
    └── file-storage/              # Secure Object Storage Specialist Pack
```

---

## 3. Manifest Specification (`manifest.json`)

Every skill pack must contain a valid `manifest.json` at its root. Adding a new pack requires **zero code changes**—the registry scans both directories on startup and indexes every valid manifest.

### Schema & Fields

| Field | Type | Description |
|---|---|---|
| `id` | `string` | Unique kebab-case identifier (e.g. `payments`, `auth`). |
| `name` | `string` | Human-readable name. |
| `version` | `string` | Semantic version string (e.g. `1.0.0`). |
| `description` | `string` | Executive summary of specialist capabilities. |
| `compatible_roles` | `string[]` | List of role IDs permitted to attach this pack (`backend`, `fullstack`, `architect`, `qa`). |
| `triggers` | `object` | Signals for deterministic detection: `keywords` and `document_patterns` (`f_code`, `fr_code`, `api_code`). |
| `required_tools` | `string[]` | Tools required by this pack (must be subset of role allowance). |
| `forbidden_tools` | `string[]` | Tools explicitly forbidden (e.g. `raw_sql_exec`, `unauthenticated_http`). |
| `rubric_path` | `string` | Relative path to `rubric.json` for Composite Judge evaluation. |
| `author` | `string` | Author or team owner. |

### Example Manifest (`skills/specialists/payments/manifest.json`)

```json
{
  "id": "payments",
  "name": "Payments & Idempotency Specialist",
  "version": "1.0.0",
  "description": "Production-grade payment gateway integrations, Idempotency-Key enforcement, webhook signature verification, and zero raw card storage.",
  "compatible_roles": ["backend", "fullstack", "architect", "qa"],
  "triggers": {
    "keywords": [
      "payment", "checkout", "charge", "refund", "subscription",
      "credit card", "stripe", "gateway", "pci", "billing", "invoice"
    ],
    "document_patterns": [
      "F-[0-9]+.*(?:payment|checkout|charge|subscription|billing)",
      "FR-[0-9]+.*(?:payment|checkout|charge|refund)",
      "API-[0-9]+.*(?:payments|checkout|charges|refunds|webhooks)"
    ]
  },
  "required_tools": [
    "read_file",
    "write_file",
    "replace_file_content",
    "run_command"
  ],
  "forbidden_tools": [
    "raw_card_collector",
    "bypass_signature_verification"
  ],
  "rubric_path": "rubric.json",
  "author": "Autonoma Architecture Team"
}
```

---

## 4. Role Tool Allowances & Least Privilege (Handbook Section 6.1.3)

Per **Handbook Section 6.1.3 (Least privilege)** verbatim:
```text
Role                                     Tools                                                                 Folder
BA, PM, HR, Recruiter, Scrum, Designer   read artifacts, write docs/                                           docs/
Architect                                + check_package                                                       docs/
Developers                               read/write/edit, run (allowlist), git on own branch, check_package     own worktree
Tech Lead                                read, diff, comment                                                   read-only
QA / Perf                                read, write tests, run_tests, k6_run                                  tests/, perf/
DevOps                                   CI, Docker, run                                                       repo root, never production
```

Per **Handbook Section 6.1.2 (Staffing by model tier - the Recruiter's job)** verbatim:
```text
Tier     Roles                                                  Why
High     Architect, developers, Tech Lead, LLM Judge            mistakes here are expensive and compound
Medium   PM, Designer, QA, Performance QA, DevOps               structured work with strong templates and tools
Low      BA relay turns, HR, Recruiter, Scrum summaries         short, templated text
```

Per **Handbook Chapter 12 (Backend and Full-stack Engineers)** verbatim:
> Build services that are correct, secure and fast, exactly to the API contract and data model.
>
> Full-stack engineers apply both the Frontend and the Backend expertise above to a vertical slice: migration → endpoint and tests → UI and tests → one end-to-end test. The contract still applies even when one agent owns both sides.

**Runtime Implementation Note**: As of the current virtual office phase, Backend, Frontend, Fullstack, DevOps, QA, and Performance roles are specification-only (per Handbook 6.3.4 Step 1) and evaluated via deterministic and composite Judge test suites.

If a skill pack's manifest specifies a `required_tool` not present in the role's allowance, `attach_skill_pack()` **rejects the attachment with a permission violation error**.

---

## 5. Deterministic 0-Token Signal Detection

The function `detect_specialist_needs(project_dir)` executes deterministic regex scanning across all markdown and YAML documents in `docs/`:

1. **Document Loading**: Reads `docs/prd.md`, `docs/requirements.md`, `docs/architecture.md`, `docs/openapi.yaml`, and `docs/app-flow.md`.
2. **Regex Extraction**:
   - Searches for explicit requirement codes: `F-###`, `FR-###`, `API-###`, `NFR-###`.
   - Searches for trigger keyword stems defined in pack manifests.
3. **Evidence Citations**:
   - Every detected need lists exact cited identifiers, e.g. `[F-003]`, `[FR-007]`, `[API-005]`.
   - If keyword triggers are found without concrete `F-###` / `FR-###` codes, detection marks `confidence: "medium"` and raises an `[OQ-]` for Gate confirmation.
   - If zero triggers match (e.g. BioVault Lab clinical specimen tracking), 0 packs are recommended.

---

## 6. Prompt Assembly Mechanics

The runtime function `assemble_agent_prompt(role, attached_pack_ids, task_context)` builds composite system prompts with a stable, cache-friendly prefix order:

```
+-----------------------------------------------------------+
| 1. Universal Operating Rules (skills/_shared/operating-rules.md) |
|    - Chapter 3 Non-Negotiables                            |
|    - Grounding, Verification, Error Recovery              |
+-----------------------------------------------------------+
| 2. Core Role Specification (skills/{role}/role.md)        |
|    - Mission, Inputs, Outputs, Tool Boundary              |
+-----------------------------------------------------------+
| 3. Attached Specialist Instructions (Alphabetical Order)   |
|    - Specialist Pack 1 (e.g. auth/instructions.md)         |
|    - Specialist Pack 2 (e.g. payments/instructions.md)     |
+-----------------------------------------------------------+
| 4. Task Context & Output Template                         |
|    - Session ID, Project Documents, Specific Objective    |
+-----------------------------------------------------------+
```

### Deterministic Token Ledger & Cost Safety
- Token estimation uses the standard heuristic ($1 \text{ token} \approx 4 \text{ chars}$).
- Maximum composite prompt budget: **16,000 tokens**.
- If a composite prompt exceeds budget, runtime logs a warning and raises an alert before LLM dispatch.

---

## 7. Composite Judge Evaluation

When evaluating deliverable artifacts (e.g. backend code in `src/`), `engine/judge.py` loads both the base role rubric and all attached specialist rubrics.

### Payments Specialist Must-Pass Criteria

1. **Idempotency Key Verification (`idempotency_key_enforced`)**:
   - Every POST endpoint mutating money, charges, or orders MUST require and validate an `Idempotency-Key` header.
   - Key checked against idempotency store before invoking payment gateway.
   - Max: 3 | Must-pass: **TRUE**.
2. **Zero Raw Card Data (`zero_raw_card_data`)**:
   - Code-level audit strips comments and inspects executable syntax.
   - Detects raw PAN identifiers (`card_number`, `pan`, `cvv`, `security_code`) or 15-16 digit card literals.
   - Only gateway tokens (`pm_card_...`) and `last4` columns are permitted.
   - Max: 3 | Must-pass: **TRUE**.
3. **Webhook Cryptographic Signature (`webhook_signature_verification`)**:
   - Any `/webhooks` receiver must compute HMAC-SHA256 signature using the configured webhook secret.
   - Enforces timestamp replay tolerance $\le 300\text{s}$.
   - Max: 3 | Must-pass: **TRUE**.
4. **Unhappy Path Preservation (`payment_failure_unhappy_path`)**:
   - Gateway decline, card expired, and insufficient funds paths must preserve unpaid state and return clear error messaging per AC-012.
   - Max: 3 | Must-pass: **TRUE**.

---

## 8. Pack Authoring Checklist

When authoring a new specialist skill pack, the author must complete all items before checking into `skills/specialists/`:

- [ ] `manifest.json` defines all required fields (`id`, `name`, `version`, `compatible_roles`, `triggers`, `required_tools`, `forbidden_tools`, `rubric_path`).
- [ ] `instructions.md` specifies step-by-step implementation rules citing relevant standards.
- [ ] `standards.md` references industry standards (e.g. RFC 7519, PCI DSS 4.0, OWASP ASVS).
- [ ] `checklist.md` contains a pre-flight verification checklist for the developer and QA.
- [ ] `rubric.json` defines quantifiable scoring criteria (score 0–3) with explicit `must_pass` flags.
- [ ] `templates/` provides working, copy-paste-ready implementation code with zero pseudocode or placeholders.
- [ ] Run `python3 tests/test_skill_registry.py` to ensure all 6 tests pass without regressions.
- [ ] Run `npx tsc --noEmit` to verify Virtual Office UI compatibility.
