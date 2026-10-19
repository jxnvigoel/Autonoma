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
| P-01 | – Lab Technician** – Scans 2‑D DataMatrix barcodes | Field and project operations in BioVault Lab Specimen Tracker | Execute core – lab technician** – scans 2‑d datamatrix barcodes operational tasks accurately and maintain compliant activity logs within BioVault Lab Specimen Tracker. | Manual paperwork, tracking delays, and transcription errors in daily – lab technician** – scans 2‑d datamatrix barcodes duties. | [Q-001] |
| P-02 | – Principal Investigator** – Searches the specimen inventory | Field and project operations in BioVault Lab Specimen Tracker | Supervise – principal investigator** – searches the specimen inventory activities, verify record integrity, and prevent compliance violations. | Lack of real-time visibility into status updates and tedious manual verification of records. | [Q-001] |
| P-03 | – Compliance Officer** – Audits chain‑of‑custody logs | Field and project operations in BioVault Lab Specimen Tracker | Perform independent compliance audits and verify traceability of all records in BioVault Lab Specimen Tracker. | Scattered audit logs and time-consuming manual report compilation during audits. | [Q-001] |

### User roles and permissions
| Role | Does | Can | Cannot | Source |
|---|---|---|---|---|
| – Lab Technician** – Scans 2‑D DataMatrix barcodes | Perform primary operational workflows and record transactions in BioVault Lab Specimen Tracker | Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1 | Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1 | [Q-001] |
| – Principal Investigator** – Searches the specimen inventory | Monitor operational status, review logs, and certify sign-offs in BioVault Lab Specimen Tracker | Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1 | Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1 | [Q-001] |
| – Compliance Officer** – Audits chain‑of‑custody logs | Audit historical transaction records, verify chain-of-custody, and export reports in BioVault Lab Specimen Tracker | Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1 | Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1 | [Q-001] |

## 4. Goals, non-goals, metrics
### Goals
| ID | Goal | Source |
|---|---|---|
| G-01 | Deliver functional v1 MVP for BioVault Lab Specimen Tracker within 6 weeks for v1 MVP | [Q-001] |
| G-02 | Automate accession new specimen** with 100% local persistence | [Q-004] |
| G-03 | Automate verify temperature threshold and trigger supervisor sign‑off on out‑of‑range readings** with 100% local persistence | [Q-004] |

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
| F-001 | Accession new specimen** | Specimen check-in and accessioning with 2D DataMatrix and QR barcode generation. | Must | [FR-01] |
| F-002 | Verify temperature threshold and trigger supervisor sign‑off on out‑of‑range readings** | Cold-storage temperature tracking and excursion event incident logging. | Must | [FR-02] |
| F-003 | Generate and print 2‑D DataMatrix barcode for newly accessioned specimens** | Specimen check-in and accessioning with 2D DataMatrix and QR barcode generation. | Must | [FR-03] |
| F-004 | Search inventory by barcode, sample type, donor ID, or other metadata** | Specimen check-in and accessioning with 2D DataMatrix and QR barcode generation. | Must | [FR-04] |
| F-005 | Display full freezer hierarchy mapping for a selected specimen** | Specimen check-in and accessioning with 2D DataMatrix and QR barcode generation. | Must | [FR-05] |
| F-006 | Export chain‑of‑custody / audit logs to CSV** | Custodial chain-of-custody transfer tracking with digital confirmation and recipient sign-off. | Must | [FR-06] |
| F-007 | Role‑based access control ** | Execution and management of role‑based access control ** with local storage and validation. | Must | [FR-07] |
| F-008 | Create and track pull requests for specimens** | Specimen check-in and accessioning with 2D DataMatrix and QR barcode generation. | Should | [FR-08] |
| F-009 | View immutable audit trail of all actions performed on a specimen** | Specimen check-in and accessioning with 2D DataMatrix and QR barcode generation. | Must | [FR-09] |

### F-001: Accession new specimen**
- **Story**: As a [P-01], I want to check in incoming bio-specimens and generate 2D barcodes so that each sample receives a unique, traceable identifier immediately upon arrival.
- **Priority**: Must Have (MoSCoW)
- **Requirements**: [FR-01]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-001 | Given an active – Lab Technician** – Scans 2‑D DataMatrix barcodes session in BioVault Lab Specimen Tracker, when the user inputs valid specimen metadata and generates a barcode, then the system saves the record to local database storage and returns printable barcode data within Response time under 1.0 s for all primary search and filter queries [ASM-01: target pending client confirmation]. |
| AC-002 | (unhappy path) Given a duplicate accession identifier or missing required sample reference, when the user confirms check-in, then the system blocks persistence, highlights the offending field with an inline alert, and preserves entered inputs without data loss. |

### F-002: Verify temperature threshold and trigger supervisor sign‑off on out‑of‑range readings**
- **Story**: As a [P-02], I want to monitor storage unit temperatures and log excursion events so that cold-chain integrity is strictly enforced according to compliance thresholds.
- **Priority**: Must Have (MoSCoW)
- **Requirements**: [FR-02]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-003 | Given an active monitoring session in BioVault Lab Specimen Tracker, when a temperature reading exceeds the configured safety threshold for a storage unit, then the system flags an excursion alert, logs the peak temperature, and prompts for incident notes within Response time under 1.0 s for all primary search and filter queries [ASM-01: target pending client confirmation]. |
| AC-004 | (unhappy path) Given an unreadable sensor input or invalid unit identifier during logging, when the reading executes, then the system records a diagnostic warning, marks the reading as unverified, and prevents false excursion clears. |

### F-003: Generate and print 2‑D DataMatrix barcode for newly accessioned specimens**
- **Story**: As a [P-01], I want to check in incoming bio-specimens and generate 2D barcodes so that each sample receives a unique, traceable identifier immediately upon arrival.
- **Priority**: Must Have (MoSCoW)
- **Requirements**: [FR-03]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-005 | Given an active – Lab Technician** – Scans 2‑D DataMatrix barcodes session in BioVault Lab Specimen Tracker, when the user inputs valid specimen metadata and generates a barcode, then the system saves the record to local database storage and returns printable barcode data within Response time under 1.0 s for all primary search and filter queries [ASM-01: target pending client confirmation]. |
| AC-006 | (unhappy path) Given a duplicate accession identifier or missing required sample reference, when the user confirms check-in, then the system blocks persistence, highlights the offending field with an inline alert, and preserves entered inputs without data loss. |

### F-004: Search inventory by barcode, sample type, donor ID, or other metadata**
- **Story**: As a [P-01], I want to check in incoming bio-specimens and generate 2D barcodes so that each sample receives a unique, traceable identifier immediately upon arrival.
- **Priority**: Must Have (MoSCoW)
- **Requirements**: [FR-04]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-007 | Given an active – Lab Technician** – Scans 2‑D DataMatrix barcodes session in BioVault Lab Specimen Tracker, when the user inputs valid specimen metadata and generates a barcode, then the system saves the record to local database storage and returns printable barcode data within Response time under 1.0 s for all primary search and filter queries [ASM-01: target pending client confirmation]. |
| AC-008 | (unhappy path) Given a duplicate accession identifier or missing required sample reference, when the user confirms check-in, then the system blocks persistence, highlights the offending field with an inline alert, and preserves entered inputs without data loss. |

### F-005: Display full freezer hierarchy mapping for a selected specimen**
- **Story**: As a [P-01], I want to check in incoming bio-specimens and generate 2D barcodes so that each sample receives a unique, traceable identifier immediately upon arrival.
- **Priority**: Must Have (MoSCoW)
- **Requirements**: [FR-05]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-009 | Given an active – Lab Technician** – Scans 2‑D DataMatrix barcodes session in BioVault Lab Specimen Tracker, when the user inputs valid specimen metadata and generates a barcode, then the system saves the record to local database storage and returns printable barcode data within Response time under 1.0 s for all primary search and filter queries [ASM-01: target pending client confirmation]. |
| AC-010 | (unhappy path) Given a duplicate accession identifier or missing required sample reference, when the user confirms check-in, then the system blocks persistence, highlights the offending field with an inline alert, and preserves entered inputs without data loss. |

### F-006: Export chain‑of‑custody / audit logs to CSV**
- **Story**: As a [P-01], I want to record specimen custodial handoffs with digital confirmation so that an unbroken, legally defensible chain of custody is established across lab personnel.
- **Priority**: Must Have (MoSCoW)
- **Requirements**: [FR-06]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-011 | Given an accessioned specimen in BioVault Lab Specimen Tracker, when the releasing custodian and receiving custodian confirm the handoff with their credentials, then the system records the custodial transfer with an immutable timestamp and updates the specimen location within Response time under 1.0 s for all primary search and filter queries [ASM-01: target pending client confirmation]. |
| AC-012 | (unhappy path) Given mismatched custodian credentials or an unconfirmed digital signature, when the transfer submission executes, then the system halts the transfer, preserves the prior custodian record, and logs an authorization alert. |

### F-007: Role‑based access control **
- **Story**: As a [P-01], I want to use role‑based access control ** so that I can execute operational workflows in BioVault Lab Specimen Tracker with verifiable local persistence.
- **Priority**: Must Have (MoSCoW)
- **Requirements**: [FR-07]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-013 | Given an active – Lab Technician** – Scans 2‑D DataMatrix barcodes session in BioVault Lab Specimen Tracker, when the user triggers role‑based access control ** with valid parameters, then the action completes successfully with immediate confirmation within Response time under 1.0 s for all primary search and filter queries [ASM-01: target pending client confirmation]. |
| AC-014 | (unhappy path) Given missing required input parameters during role‑based access control **, when the action executes, then the system displays a clear diagnostic notice, preserves unsaved inputs, and allows immediate retry. |

### F-008: Create and track pull requests for specimens**
- **Story**: As a [P-01], I want to check in incoming bio-specimens and generate 2D barcodes so that each sample receives a unique, traceable identifier immediately upon arrival.
- **Priority**: Should Have (MoSCoW)
- **Requirements**: [FR-08]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-015 | Given an active – Lab Technician** – Scans 2‑D DataMatrix barcodes session in BioVault Lab Specimen Tracker, when the user inputs valid specimen metadata and generates a barcode, then the system saves the record to local database storage and returns printable barcode data within Response time under 1.0 s for all primary search and filter queries [ASM-01: target pending client confirmation]. |
| AC-016 | (unhappy path) Given a duplicate accession identifier or missing required sample reference, when the user confirms check-in, then the system blocks persistence, highlights the offending field with an inline alert, and preserves entered inputs without data loss. |

### F-009: View immutable audit trail of all actions performed on a specimen**
- **Story**: As a [P-01], I want to check in incoming bio-specimens and generate 2D barcodes so that each sample receives a unique, traceable identifier immediately upon arrival.
- **Priority**: Must Have (MoSCoW)
- **Requirements**: [FR-09]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-017 | Given an active – Lab Technician** – Scans 2‑D DataMatrix barcodes session in BioVault Lab Specimen Tracker, when the user inputs valid specimen metadata and generates a barcode, then the system saves the record to local database storage and returns printable barcode data within Response time under 1.0 s for all primary search and filter queries [ASM-01: target pending client confirmation]. |
| AC-018 | (unhappy path) Given a duplicate accession identifier or missing required sample reference, when the user confirms check-in, then the system blocks persistence, highlights the offending field with an inline alert, and preserves entered inputs without data loss. |

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
| ASM-01 | All laboratory workstations will have a USB or Bluetooth 2‑D DataMatrix scanner compatible with the desktop application. | awaiting client at Gate 1 |
| ASM-02 | Users possess administrative rights to install the application on macOS and Windows 11 machines. | awaiting client at Gate 1 |
| ASM-03 | Temperature thresholds are predefined per sample type and stored within the application. | awaiting client at Gate 1 |
| ASM-04 | Only one user will access the SQLite database at a time; concurrent multi‑user editing is not required. | awaiting client at Gate 1 |
| ASM-05 | CSV format is sufficient for all compliance audit reporting needs in v1. | awaiting client at Gate 1 |
| OQ-01 | Confirm whether tracking daily workflow completion rate in BioVault Lab Specimen Tracker is desired as an ongoing operational metric. | sent via BA |
| OQ-02 | Confirm formal sign-off authority and capability boundaries between – Lab Technician** – Scans 2‑D DataMatrix barcodes and – Principal Investigator** – Searches the specimen inventory. | sent via BA |
| OQ-03 | Confirm preferred default report export format for regulatory compliance audits in BioVault Lab Specimen Tracker. | sent via BA |

## 9. Scope changes from the client’s request
| Requested | Decision | Reason | Source |
|---|---|---|---|
| Accession new specimen** | kept in v1 | Directly required by client discovery [Must priority] | [Q-004] |
| Verify temperature threshold and trigger supervisor sign‑off on out‑of‑range readings** | kept in v1 | Directly required by client discovery [Must priority] | [Q-004] |
| Generate and print 2‑D DataMatrix barcode for newly accessioned specimens** | kept in v1 | Directly required by client discovery [Must priority] | [Q-001] |
| Search inventory by barcode, sample type, donor ID, or other metadata** | kept in v1 | Directly required by client discovery [Must priority] | [Q-003] |
| Display full freezer hierarchy mapping for a selected specimen** | kept in v1 | Directly required by client discovery [Must priority] | [Q-006] |
| Export chain‑of‑custody / audit logs to CSV** | kept in v1 | Directly required by client discovery [Must priority] | [Q-006] |
| Role‑based access control ** | kept in v1 | Directly required by client discovery [Must priority] | [Q-003] |
| Create and track pull requests for specimens** | kept in v1 | Directly required by client discovery [Must priority] | [Q-003] |
| View immutable audit trail of all actions performed on a specimen** | kept in v1 | Directly required by client discovery [Must priority] | [Q-003] |
| Real-time multi-tenant cloud synchronization and remote web portal | moved to v2 | Scope constraint: Strictly deferred to v2 per client local-first deployment and v1 timeline constraints | [Q-001] |
| Automated third-party SaaS integrations and external webhooks | moved to v2 | Scope constraint: Out of scope for v1 MVP; v1 focuses strictly on core local workflows and local compliance exports | [Q-001] |

### Timeline and Budget Feasibility Reasoning
The v1 scope strictly includes 9 core functional features covering all client Must-have functional requirements. By deferring cloud synchronization and multi-user scaling to v2 (NG-01, NG-02), the technical architecture fits securely within the 6 weeks for v1 MVP delivery timeline and local operating budget ($15,000 budget with $0/month ongoing cloud infrastructure cost).