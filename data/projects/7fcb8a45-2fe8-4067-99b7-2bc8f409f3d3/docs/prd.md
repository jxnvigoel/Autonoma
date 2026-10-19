# Product Requirement Document (PRD): BioVault Lab Specimen Tracker

## 1. App overview
| Field | Value | Source |
|---|---|---|
| App name | BioVault Lab Specimen Tracker | [Q-001] |
| One-line description | Desktop tracking system for cryogenic bio-specimens, accessioning, 2D barcodes, and freezer chain of custody. | [Q-001] |
| Category | Clinical Laboratory Specimen & Cold-Chain Custody Tracking | [Q-001] |
| Platforms | Desktop application with full offline execution in disconnected local environments | [NFR-04] |

## 2. Problem
- **Today**: The primary problem is misplacing cryogenic biological samples stored across -80C freezers and liquid nitrogen tanks. Technicians spend 25 minutes per retrieval with manual paper logs, causing cold-chain compliance risks. [Q-002]
- **Core problem**: Yes, please proceed with the discovery questions. [Q-001]
- **Why existing tools fall short**: Existing alternatives require external cloud connectivity with monthly subscription costs, failing in offline environments and lacking local data control. [Q-001] [Q-001]

## 3. Users
### Personas
| ID | Persona | Context | Goal | Pain point | Source |
|---|---|---|---|---|---|
| P-01 | – Lab Technician** – Scans 2D DataMatrix barcodes | Field and project operations in BioVault Lab Specimen Tracker | Execute core – lab technician** – scans 2d datamatrix barcodes operational tasks accurately and maintain compliant activity logs within BioVault Lab Specimen Tracker. | Manual paperwork, tracking delays, and transcription errors in daily – lab technician** – scans 2d datamatrix barcodes duties. | [Q-001] |
| P-02 | – Principal Investigator** – Searches the sample inventory and requests specimen pulls. | Field and project operations in BioVault Lab Specimen Tracker | Supervise – principal investigator** – searches the sample inventory and requests specimen pulls. activities, verify record integrity, and prevent compliance violations. | Lack of real-time visibility into status updates and tedious manual verification of records. | [Q-001] |
| P-03 | – Compliance Officer** – Audits chain‑of‑custody logs. | Field and project operations in BioVault Lab Specimen Tracker | Perform independent compliance audits and verify traceability of all records in BioVault Lab Specimen Tracker. | Scattered audit logs and time-consuming manual report compilation during audits. | [Q-001] |

### User roles and permissions
| Role | Does | Can | Cannot | Source |
|---|---|---|---|---|
| – Lab Technician** – Scans 2D DataMatrix barcodes | Perform primary operational workflows and record transactions in BioVault Lab Specimen Tracker | Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1 | Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1 | [Q-001] |
| – Principal Investigator** – Searches the sample inventory and requests specimen pulls. | Monitor operational status, review logs, and certify sign-offs in BioVault Lab Specimen Tracker | Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1 | Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1 | [Q-001] |
| – Compliance Officer** – Audits chain‑of‑custody logs. | Audit historical transaction records, verify chain-of-custody, and export reports in BioVault Lab Specimen Tracker | Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1 | Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1 | [Q-001] |

## 4. Goals, non-goals, metrics
### Goals
| ID | Goal | Source |
|---|---|---|
| G-01 | Deliver functional v1 MVP for BioVault Lab Specimen Tracker within 6 weeks for v1 MVP | [Q-001] |
| G-02 | Automate scan 2d datamatrix barcode** with 100% local persistence | [Q-004] |
| G-03 | Automate record freezer location hierarchy ** with 100% local persistence | [Q-004] |

### Non-goals (not in v1)
| ID | Non-goal (not in v1) | Why | Source |
|---|---|---|---|
| NG-01 | Real-time multi-tenant cloud synchronization and remote web portal | Strictly deferred to v2 per client local-first deployment and v1 timeline constraints | [Q-001] |
| NG-02 | Automated third-party SaaS integrations and external webhooks | Out of scope for v1 MVP; v1 focuses strictly on core local workflows and local compliance exports | [Q-001] |

### Success metrics
| ID | Metric | Target | How it is measured | Source |
|---|---|---|---|---|
| M-01 | BioVault Lab Specimen Tracker Daily Operational Completion Rate | 90% of daily transactions logged and verified within BioVault Lab Specimen Tracker on the same business day | Local application export audit logs (verified_records_same_day / total_records_created) | [Q-001] |

## 5. Features (v1)
### Summary
| ID | Feature | Description | Priority (MoSCoW) | Requirements |
|---|---|---|---|---|
| F-001 | Scan 2D DataMatrix barcode** | Specimen check-in and accessioning with 2D DataMatrix and QR barcode generation. | Must | [FR-01] |
| F-002 | Record freezer location hierarchy ** | Execution and management of record freezer location hierarchy ** with local storage and validation. | Must | [FR-02] |
| F-003 | Verify specimen temperature against a predefined threshold and flag out‑of‑range readings** | Specimen check-in and accessioning with 2D DataMatrix and QR barcode generation. | Must | [FR-03] |
| F-004 | Require supervisor sign‑off for any temperature‑alert flagged record** | Cold-storage temperature tracking and excursion event incident logging. | Must | [FR-04] |
| F-005 | Persist specimen record locally on the workstation** | Specimen check-in and accessioning with 2D DataMatrix and QR barcode generation. | Must | [FR-05] |

### F-001: Scan 2D DataMatrix barcode**
- **Story**: As a [P-01], I want to check in incoming bio-specimens and generate 2D barcodes so that each sample receives a unique, traceable identifier immediately upon arrival.
- **Priority**: Must Have (MoSCoW)
- **Requirements**: [FR-01]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-001 | Given an active – Lab Technician** – Scans 2D DataMatrix barcodes session in BioVault Lab Specimen Tracker, when the user inputs valid specimen metadata and generates a barcode, then the system saves the record to local database storage and returns printable barcode data within Response time under 1.0 s for all primary search and filter queries [ASM-01: target pending client confirmation]. |
| AC-002 | (unhappy path) Given a duplicate accession identifier or missing required sample reference, when the user confirms check-in, then the system blocks persistence, highlights the offending field with an inline alert, and preserves entered inputs without data loss. |

### F-002: Record freezer location hierarchy **
- **Story**: As a [P-01], I want to use record freezer location hierarchy ** so that I can execute operational workflows in BioVault Lab Specimen Tracker with verifiable local persistence.
- **Priority**: Must Have (MoSCoW)
- **Requirements**: [FR-02]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-003 | Given an active – Lab Technician** – Scans 2D DataMatrix barcodes session in BioVault Lab Specimen Tracker, when the user triggers record freezer location hierarchy ** with valid parameters, then the action completes successfully with immediate confirmation within Response time under 1.0 s for all primary search and filter queries [ASM-01: target pending client confirmation]. |
| AC-004 | (unhappy path) Given missing required input parameters during record freezer location hierarchy **, when the action executes, then the system displays a clear diagnostic notice, preserves unsaved inputs, and allows immediate retry. |

### F-003: Verify specimen temperature against a predefined threshold and flag out‑of‑range readings**
- **Story**: As a [P-01], I want to check in incoming bio-specimens and generate 2D barcodes so that each sample receives a unique, traceable identifier immediately upon arrival.
- **Priority**: Must Have (MoSCoW)
- **Requirements**: [FR-03]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-005 | Given an active – Lab Technician** – Scans 2D DataMatrix barcodes session in BioVault Lab Specimen Tracker, when the user inputs valid specimen metadata and generates a barcode, then the system saves the record to local database storage and returns printable barcode data within Response time under 1.0 s for all primary search and filter queries [ASM-01: target pending client confirmation]. |
| AC-006 | (unhappy path) Given a duplicate accession identifier or missing required sample reference, when the user confirms check-in, then the system blocks persistence, highlights the offending field with an inline alert, and preserves entered inputs without data loss. |

### F-004: Require supervisor sign‑off for any temperature‑alert flagged record**
- **Story**: As a [P-02], I want to monitor storage unit temperatures and log excursion events so that cold-chain integrity is strictly enforced according to compliance thresholds.
- **Priority**: Must Have (MoSCoW)
- **Requirements**: [FR-04]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-007 | Given an active monitoring session in BioVault Lab Specimen Tracker, when a temperature reading exceeds the configured safety threshold for a storage unit, then the system flags an excursion alert, logs the peak temperature, and prompts for incident notes within Response time under 1.0 s for all primary search and filter queries [ASM-01: target pending client confirmation]. |
| AC-008 | (unhappy path) Given an unreadable sensor input or invalid unit identifier during logging, when the reading executes, then the system records a diagnostic warning, marks the reading as unverified, and prevents false excursion clears. |

### F-005: Persist specimen record locally on the workstation**
- **Story**: As a [P-01], I want to check in incoming bio-specimens and generate 2D barcodes so that each sample receives a unique, traceable identifier immediately upon arrival.
- **Priority**: Must Have (MoSCoW)
- **Requirements**: [FR-05]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-009 | Given an active – Lab Technician** – Scans 2D DataMatrix barcodes session in BioVault Lab Specimen Tracker, when the user inputs valid specimen metadata and generates a barcode, then the system saves the record to local database storage and returns printable barcode data within Response time under 1.0 s for all primary search and filter queries [ASM-01: target pending client confirmation]. |
| AC-010 | (unhappy path) Given a duplicate accession identifier or missing required sample reference, when the user confirms check-in, then the system blocks persistence, highlights the offending field with an inline alert, and preserves entered inputs without data loss. |

## 6. Non-functional requirements (summary)
| NFR | Target | Source |
|---|---|---|
| Search & Operation Latency | Response time under 1.0 s for all primary search and filter queries [ASM-01: target pending client confirmation] | [NFR-01] |
| Data Storage & Privacy | 100% local device storage with zero unauthorized external cloud uploads | [NFR-02] |
| Local Capacity | Support expected operational records stored locally without performance degradation [ASM-02: volume pending client confirmation] | [NFR-03] |
| Platform Compatibility | Desktop application with full offline execution in disconnected local environments | [NFR-04] |
| Accessibility & Usability | WCAG 2.2 AA compliance for desktop interface with keyboard navigation | [NFR-05] |

## 7. Risks
| ID | Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| R-01 | Local filesystem document or report read/write permission denial | M | H | Prompt explicit folder read and write permissions gracefully on startup with clear diagnostic notice | Engineer |
| R-02 | Scope creep exceeding target 6 weeks for v1 MVP timeline | M | M | Strict MoSCoW prioritization; cloud sync and remote portals deferred to v2 | PM |
| R-03 | Search query latency degrading over large local record volumes | L | M | Maintain indexed local B-tree search queries to keep latency within Response time under 1.0 s for all primary search and filter queries [ASM-01: target pending client confirmation] across Support expected operational records stored locally without performance degradation [ASM-02: volume pending client confirmation] | Architect |

## 8. Assumptions and open questions
| ID | Text | Status |
|---|---|---|
| ASM-01 | ** Temperature thresholds for each specimen type are predefined in the system before accessioning begins. | awaiting client at Gate 1 |
| ASM-02 | ** A supervisor is available to provide sign‑off on the same workstation when a temperature alert occurs. | awaiting client at Gate 1 |
| ASM-03 | ** Each workstation operates on its own local SQLite database without concurrent multi‑user editing. | awaiting client at Gate 1 |
| OQ-01 | Confirm whether tracking daily workflow completion rate in BioVault Lab Specimen Tracker is desired as an ongoing operational metric. | sent via BA |
| OQ-02 | Confirm formal sign-off authority and capability boundaries between – Lab Technician** – Scans 2D DataMatrix barcodes and – Principal Investigator** – Searches the sample inventory and requests specimen pulls.. | sent via BA |
| OQ-03 | Confirm preferred default report export format for regulatory compliance audits in BioVault Lab Specimen Tracker. | sent via BA |

## 9. Scope changes from the client’s request
| Requested | Decision | Reason | Source |
|---|---|---|---|
| Scan 2D DataMatrix barcode** | kept in v1 | Directly required by client discovery [Must priority] | [Q-004] |
| Record freezer location hierarchy ** | kept in v1 | Directly required by client discovery [Must priority] | [Q-004] |
| Verify specimen temperature against a predefined threshold and flag out‑of‑range readings** | kept in v1 | Directly required by client discovery [Must priority] | [Q-004] |
| Require supervisor sign‑off for any temperature‑alert flagged record** | kept in v1 | Directly required by client discovery [Must priority] | [Q-004] |
| Persist specimen record locally on the workstation** | kept in v1 | Directly required by client discovery [Must priority] | [Q-005] |
| Real-time multi-tenant cloud synchronization and remote web portal | moved to v2 | Scope constraint: Strictly deferred to v2 per client local-first deployment and v1 timeline constraints | [Q-001] |
| Automated third-party SaaS integrations and external webhooks | moved to v2 | Scope constraint: Out of scope for v1 MVP; v1 focuses strictly on core local workflows and local compliance exports | [Q-001] |

### Timeline and Budget Feasibility Reasoning
The v1 scope strictly includes 5 core functional features covering all client Must-have functional requirements. By deferring cloud synchronization and multi-user scaling to v2 (NG-01, NG-02), the technical architecture fits securely within the 6 weeks for v1 MVP delivery timeline and local operating budget ($15,000 budget with $0/month ongoing cloud infrastructure cost).