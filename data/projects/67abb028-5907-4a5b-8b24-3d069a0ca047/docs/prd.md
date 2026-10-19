# Product Requirement Document (PRD): BioVault Lab

## 1. App overview
| Field | Value | Source |
|---|---|---|
| App name | BioVault Lab | [Q-001] |
| One-line description | A standalone desktop and local-network laboratory specimen inventory and chain-of-custody tracking tool for diagnostic pathology labs. It tracks bio-specimen accessioning, freezer cold-chain temperature logs, custodian sign-offs, and regulatory compliance audit exports. | [Q-001] |
| Category | Clinical Laboratory Specimen & Cold-Chain Custody Tracking | [Q-001] |
| Platforms | The software must run offline on lab workstations running macOS and Windows | [NFR-04] |

## 2. Problem
- **Today**: Users currently rely on manual workflows and fragmented paper or desktop tools to execute their daily tasks. [Q-001] [Q-001]
- **Core problem**: Yes, let's begin. We are building BioVault Lab to eliminate sample misplacement and compliance penalties in clinical diagnostic labs. [Q-001]
- **Why existing tools fall short**: Existing alternatives require external cloud connectivity with monthly subscription costs, failing in offline environments and lacking local data control. [Q-001] [Q-001]

## 3. Users
### Personas
| ID | Persona | Context | Goal | Pain point | Source |
|---|---|---|---|---|---|
| P-01 | Lab Technician | Field and project operations in BioVault Lab | Execute core lab technician operational tasks accurately and maintain compliant activity logs within BioVault Lab. | Manual paperwork, tracking delays, and transcription errors in daily lab technician duties. | [Q-001] |
| P-02 | Lab Manager | Field and project operations in BioVault Lab | Supervise lab manager activities, verify record integrity, and prevent compliance violations. | Lack of real-time visibility into status updates and tedious manual verification of records. | [Q-001] |
| P-03 | Quality Auditor | Field and project operations in BioVault Lab | Perform independent compliance audits and verify traceability of all records in BioVault Lab. | Scattered audit logs and time-consuming manual report compilation during audits. | [Q-001] |

### User roles and permissions
| Role | Does | Can | Cannot | Source |
|---|---|---|---|---|
| Lab Technician | Perform primary operational workflows and record transactions in BioVault Lab | Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1 | Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1 | [Q-001] |
| Lab Manager | Monitor operational status, review logs, and certify sign-offs in BioVault Lab | Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1 | Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1 | [Q-001] |
| Quality Auditor | Audit historical transaction records, verify chain-of-custody, and export reports in BioVault Lab | Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1 | Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1 | [Q-001] |

## 4. Goals, non-goals, metrics
### Goals
| ID | Goal | Source |
|---|---|---|
| G-01 | Deliver functional v1 MVP for BioVault Lab within 4 weeks MVP | [Q-005] |
| G-02 | Automate specimen check-in with 2d barcode generation with 100% local persistence | [Q-002] |
| G-03 | Automate cold-storage temperature excursion logging with 100% local persistence | [Q-002] |

### Non-goals (not in v1)
| ID | Non-goal (not in v1) | Why | Source |
|---|---|---|---|
| NG-01 | Real-time multi-tenant cloud synchronization and remote web portal | Strictly deferred to v2 per client local-first deployment and v1 timeline constraints | [Q-005] |
| NG-02 | Automated third-party SaaS integrations and external webhooks | Out of scope for v1 MVP; v1 focuses strictly on core local workflows and local compliance exports | [Q-005] |

### Success metrics
| ID | Metric | Target | How it is measured | Source |
|---|---|---|---|---|
| M-01 | BioVault Lab Daily Operational Completion Rate | 90% of daily transactions logged and verified within BioVault Lab on the same business day | Local application export audit logs (verified_records_same_day / total_records_created) | [Q-001] |

## 5. Features (v1)
### Summary
| ID | Feature | Description | Priority (MoSCoW) | Requirements |
|---|---|---|---|---|
| F-001 | Specimen check-in with 2D barcode generation | Specimen check-in and accessioning with 2D DataMatrix and QR barcode generation. | Must | [FR-01] |
| F-002 | Cold-storage temperature excursion logging | Cold-storage temperature tracking and excursion event incident logging. | Must | [FR-02] |
| F-003 | Custodial transfer sign-off with digital confirmation | Custodial chain-of-custody transfer tracking with digital confirmation and recipient sign-off. | Must | [FR-03] |
| F-004 | Regulatory inspection audit export | Regulatory inspection audit trail exporter generating structured CSV files and certified PDF summaries. | Must | [FR-04] |

### F-001: Specimen check-in with 2D barcode generation
- **Story**: As a [P-01], I want to check in incoming bio-specimens and generate 2D barcodes so that each sample receives a unique, traceable identifier immediately upon arrival.
- **Priority**: Must Have (MoSCoW)
- **Requirements**: [FR-01]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-001 | Given an active Lab Technician session in BioVault Lab, when the user inputs valid specimen metadata and generates a barcode, then the system saves the record to local database storage and returns printable barcode data within 5 seconds. |
| AC-002 | (unhappy path) Given a duplicate accession identifier or missing required sample reference, when the user confirms check-in, then the system blocks persistence, highlights the offending field with an inline alert, and preserves entered inputs without data loss. |

### F-002: Cold-storage temperature excursion logging
- **Story**: As a [P-02], I want to monitor storage unit temperatures and log excursion events so that cold-chain integrity is strictly enforced according to compliance thresholds.
- **Priority**: Must Have (MoSCoW)
- **Requirements**: [FR-02]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-003 | Given an active monitoring session in BioVault Lab, when a temperature reading exceeds the configured safety threshold for a storage unit, then the system flags an excursion alert, logs the peak temperature, and prompts for incident notes within 5 seconds. |
| AC-004 | (unhappy path) Given an unreadable sensor input or invalid unit identifier during logging, when the reading executes, then the system records a diagnostic warning, marks the reading as unverified, and prevents false excursion clears. |

### F-003: Custodial transfer sign-off with digital confirmation
- **Story**: As a [P-01], I want to record specimen custodial handoffs with digital confirmation so that an unbroken, legally defensible chain of custody is established across lab personnel.
- **Priority**: Must Have (MoSCoW)
- **Requirements**: [FR-03]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-005 | Given an accessioned specimen in BioVault Lab, when the releasing custodian and receiving custodian confirm the handoff with their credentials, then the system records the custodial transfer with an immutable timestamp and updates the specimen location within 5 seconds. |
| AC-006 | (unhappy path) Given mismatched custodian credentials or an unconfirmed digital signature, when the transfer submission executes, then the system halts the transfer, preserves the prior custodian record, and logs an authorization alert. |

### F-004: Regulatory inspection audit export
- **Story**: As a [P-03], I want to export specimen tracking and cold-chain temperature logs into PDF and CSV formats so that regulatory inspection audits can be certified without delay.
- **Priority**: Must Have (MoSCoW)
- **Requirements**: [FR-04]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-007 | Given logged specimen accession records and temperature histories in BioVault Lab, when the user selects regulatory audit export in PDF or CSV format, then the system compiles the full audit trail and saves the structured export file to the local filesystem within 5 seconds. |
| AC-008 | (unhappy path) Given a write-protected export directory or exhausted disk space, when the export executes, then the system alerts the user with an actionable directory selection dialog and prevents data corruption. |

## 6. Non-functional requirements (summary)
| NFR | Target | Source |
|---|---|---|
| Search & Operation Latency | 5 seconds | [NFR-01] |
| Data Storage & Privacy | All patient and specimen data must be stored locally on lab premises with zero cloud uploads for HIPAA and CLIA compliance | [NFR-02] |
| Local Capacity | The local system must support at least 10,000 specimen records | [NFR-03] |
| Platform Compatibility | The software must run offline on lab workstations running macOS and Windows | [NFR-04] |
| Accessibility & Usability | 2 AA | [NFR-05] |

## 7. Risks
| ID | Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| R-01 | Local filesystem document or report read/write permission denial | M | H | Prompt explicit folder read and write permissions gracefully on startup with clear diagnostic notice | Engineer |
| R-02 | Scope creep exceeding target 4 weeks MVP timeline | M | M | Strict MoSCoW prioritization; cloud sync and remote portals deferred to v2 | PM |
| R-03 | Search query latency degrading over large local record volumes | L | M | Maintain indexed local B-tree search queries to keep latency within 5 seconds across The local system must support at least 10,000 specimen records | Architect |

## 8. Assumptions and open questions
| ID | Text | Status |
|---|---|---|
| ASM-01 | All patient and specimen data will be stored locally on lab premises. | awaiting client at Gate 1 |
| ASM-02 | The local system will support at least 10,000 specimen records. | awaiting client at Gate 1 |
| ASM-03 | The system will comply with HIPAA and CLIA regulations. | awaiting client at Gate 1 |
| ASM-04 | Gloved technician full keyboard navigation is required. | awaiting client at Gate 1 |
| ASM-05 | High contrast matching WCAG 2.2 AA is required. | awaiting client at Gate 1 |
| ASM-06 | The software will run offline on lab workstations running macOS and Windows. | awaiting client at Gate 1 |
| OQ-01 | Confirm whether tracking daily workflow completion rate in BioVault Lab is desired as an ongoing operational metric. | sent via BA |
| OQ-02 | Confirm formal sign-off authority and capability boundaries between Lab Technician and Lab Manager. | sent via BA |
| OQ-03 | Confirm preferred default report export format for regulatory compliance audits in BioVault Lab. | sent via BA |

## 9. Scope changes from the client’s request
| Requested | Decision | Reason | Source |
|---|---|---|---|
| Specimen check-in with 2D barcode generation | kept in v1 | Directly required by client discovery [Must priority] | [Q-002] |
| Cold-storage temperature excursion logging | kept in v1 | Directly required by client discovery [Must priority] | [Q-002] |
| Custodial transfer sign-off with digital confirmation | kept in v1 | Directly required by client discovery [Must priority] | [Q-002] |
| Regulatory inspection audit export | kept in v1 | Directly required by client discovery [Must priority] | [Q-002] |
| Real-time multi-tenant cloud synchronization and remote web portal | moved to v2 | Scope constraint: Strictly deferred to v2 per client local-first deployment and v1 timeline constraints | [Q-005] |
| Automated third-party SaaS integrations and external webhooks | moved to v2 | Scope constraint: Out of scope for v1 MVP; v1 focuses strictly on core local workflows and local compliance exports | [Q-005] |

### Timeline and Budget Feasibility Reasoning
The v1 scope strictly includes 4 core functional features covering all client Must-have functional requirements. By deferring cloud synchronization and multi-user scaling to v2 (NG-01, NG-02), the technical architecture fits securely within the 4 weeks MVP delivery timeline and local operating budget ($6,000 development budget, local deployment with $0 monthly cloud costs).