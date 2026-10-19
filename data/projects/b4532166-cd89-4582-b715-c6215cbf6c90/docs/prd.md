# Product Requirement Document (PRD): BioVault Lab

## 1. App overview
| Field | Value | Source |
|---|---|---|
| App name | BioVault Lab | [Q-001] |
| One-line description | A standalone desktop and local-network laboratory specimen inventory and chain-of-custody tracking tool for diagnostic pathology labs. It tracks bio-specimen accessioning, freezer cold-chain temperature logs, custodian sign-offs, and regulatory compliance audit exports. | [Q-001] |
| Category | Field Workflow Automation & Compliance Management | [Q-001] |
| Platforms | macOS Desktop with offline execution | [NFR-04] |

## 2. Problem
- **Today**: Users currently rely on manual workflows and fragmented paper or desktop tools to execute their daily tasks. [Q-001] [Q-001]
- **Core problem**: Yes, let's begin. We are building BioVault Lab to eliminate sample misplacement and compliance penalties in clinical diagnostic labs. [Q-001]
- **Why existing tools fall short**: Existing alternatives require external cloud connectivity with monthly subscription costs, failing in offline environments and lacking local data control. [Q-001] [Q-001]

## 3. Users
### Personas
| ID | Persona | Context | Goal | Pain point | Source |
|---|---|---|---|---|---|
| P-01 | Lab Technician | Field and project operations in BioVault Lab | Execute core lab technician responsibilities accurately with direct local data control. | Manual transcription overhead and delays caused by fragmented tools. | [Q-001] |
| P-02 | Lab Manager | Field and project operations in BioVault Lab | Assist with routine field data collection and checklist completion. | Unreliable network access during field data entry and tedious spreadsheet compilation. | [Q-001] |
| P-03 | Quality Auditor | Field and project operations in BioVault Lab |  |  | [Q-001] |

### User roles and permissions
| Role | Does | Can | Cannot | Source |
|---|---|---|---|---|
| Lab Technician | Manage primary operational workflows in BioVault Lab | Create, edit, verify workflow records, and export reports | Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1 | [Q-001] |
| Lab Manager | Execute routine field tracking and data entry in BioVault Lab | Input field data, tag items, and generate draft exports | Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1 | [Q-001] |
| Quality Auditor | Execute role responsibilities in workflow | Create and review project records | Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1 | [Q-001] |

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
| NG-01 | Real-time contractor cloud portal synchronization | Strictly deferred to v2 per client privacy and v1 timeline constraints | [Q-002] |
| NG-02 | Automated drone survey video feed ingestion | Out of scope for v1 MVP; v1 focuses on handheld inspection logging and punch-list export | [Q-002] |

### Success metrics
| ID | Metric | Target | How it is measured | Source |
|---|---|---|---|---|
| M-01 | Daily Punch-List Generation Rate | 90% of field inspectors generating daily punch-list reports on the same day as the inspection | Local application export audit logs (punchlists_exported_same_day / inspections_completed) | [Q-001] |

## 5. Features (v1)
### Summary
| ID | Feature | Description | Priority (MoSCoW) | Requirements |
|---|---|---|---|---|
| F-001 | Specimen check-in with 2D barcode generation | Execution and management of specimen check-in with 2d barcode generation. | Must | [FR-01] |
| F-002 | Cold-storage temperature excursion logging | Execution and management of cold-storage temperature excursion logging. | Should | [FR-02] |
| F-003 | Custodial transfer sign-off with digital confirmation | Execution and management of custodial transfer sign-off with digital confirmation. | Must | [FR-03] |
| F-004 | PDF/CSV regulatory inspection audit export | One-click punch-list exporter generating structured CSV files and print-ready compliance summaries. | Must | [FR-04] |
| F-005 | Barcode scanning and specimen search must respond in under 1.5 seconds | Execution and management of barcode scanning and specimen search must respond in under 1.5 seconds. | Should | [FR-05] |
| F-006 | Freezer temperature deviation must not exceed 5 degrees Celsius | Execution and management of freezer temperature deviation must not exceed 5 degrees celsius. | Should | [FR-06] |
| F-007 | The software must be able to display a minimum of 6 colors on a high contrast background | Execution and management of the software must be able to display a minimum of 6 colors on a high contrast background. | Should | [FR-07] |

### F-001: Specimen check-in with 2D barcode generation
- **Story**: As a [P-01], I want to use specimen check-in with 2d barcode generation so that I can streamline my operational workflow and prevent manual transcription errors.
- **Priority**: Must Have (MoSCoW)
- **Requirements**: [FR-01]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-001 | Given an active Lab Technician session in BioVault Lab, when the user triggers specimen check-in with 2d barcode generation, then the action completes successfully with immediate confirmation within 1.0 s. |
| AC-002 | (unhappy path) Given missing required input parameters or an unreadable data file during specimen check-in with 2d barcode generation, when the action executes, then the system displays a clear diagnostic notice, preserves unsaved inputs, and allows immediate retry. |

### F-002: Cold-storage temperature excursion logging
- **Story**: As a [P-01], I want to use cold-storage temperature excursion logging so that I can streamline my operational workflow and prevent manual transcription errors.
- **Priority**: Should Have (MoSCoW)
- **Requirements**: [FR-02]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-003 | Given an active Lab Technician session in BioVault Lab, when the user triggers cold-storage temperature excursion logging, then the action completes successfully with immediate confirmation within 1.0 s. |
| AC-004 | (unhappy path) Given missing required input parameters or an unreadable data file during cold-storage temperature excursion logging, when the action executes, then the system displays a clear diagnostic notice, preserves unsaved inputs, and allows immediate retry. |

### F-003: Custodial transfer sign-off with digital confirmation
- **Story**: As a [P-01], I want to use custodial transfer sign-off with digital confirmation so that I can streamline my operational workflow and prevent manual transcription errors.
- **Priority**: Must Have (MoSCoW)
- **Requirements**: [FR-03]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-005 | Given an active Lab Technician session in BioVault Lab, when the user triggers custodial transfer sign-off with digital confirmation, then the action completes successfully with immediate confirmation within 1.0 s. |
| AC-006 | (unhappy path) Given missing required input parameters or an unreadable data file during custodial transfer sign-off with digital confirmation, when the action executes, then the system displays a clear diagnostic notice, preserves unsaved inputs, and allows immediate retry. |

### F-004: PDF/CSV regulatory inspection audit export
- **Story**: As a [P-01], I want to export compiled site inspection punch-lists into CSV and formatted print-ready text so that I can issue same-day compliance notices without evening data entry.
- **Priority**: Must Have (MoSCoW)
- **Requirements**: [FR-04]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-007 | Given one or more logged site inspection deficiencies in BioVault Lab, when the user initiates punch-list export in CSV or text format, then the system compiles the deficiency log and writes the export file to the local filesystem within 1.0 s. |
| AC-008 | (unhappy path) Given the target local export folder lacks write permissions or disk space is exhausted, when the export executes, then the system presents a clear diagnostic warning and offers an alternative export location without aborting the session. |

### F-005: Barcode scanning and specimen search must respond in under 1.5 seconds
- **Story**: As a [P-01], I want to use barcode scanning and specimen search must respond in under 1.5 seconds so that I can streamline my operational workflow and prevent manual transcription errors.
- **Priority**: Should Have (MoSCoW)
- **Requirements**: [FR-05]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-009 | Given an active Lab Technician session in BioVault Lab, when the user triggers barcode scanning and specimen search must respond in under 1.5 seconds, then the action completes successfully with immediate confirmation within 1.0 s. |
| AC-010 | (unhappy path) Given missing required input parameters or an unreadable data file during barcode scanning and specimen search must respond in under 1.5 seconds, when the action executes, then the system displays a clear diagnostic notice, preserves unsaved inputs, and allows immediate retry. |

### F-006: Freezer temperature deviation must not exceed 5 degrees Celsius
- **Story**: As a [P-01], I want to use freezer temperature deviation must not exceed 5 degrees celsius so that I can streamline my operational workflow and prevent manual transcription errors.
- **Priority**: Should Have (MoSCoW)
- **Requirements**: [FR-06]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-011 | Given an active Lab Technician session in BioVault Lab, when the user triggers freezer temperature deviation must not exceed 5 degrees celsius, then the action completes successfully with immediate confirmation within 1.0 s. |
| AC-012 | (unhappy path) Given missing required input parameters or an unreadable data file during freezer temperature deviation must not exceed 5 degrees celsius, when the action executes, then the system displays a clear diagnostic notice, preserves unsaved inputs, and allows immediate retry. |

### F-007: The software must be able to display a minimum of 6 colors on a high contrast background
- **Story**: As a [P-01], I want to use the software must be able to display a minimum of 6 colors on a high contrast background so that I can streamline my operational workflow and prevent manual transcription errors.
- **Priority**: Should Have (MoSCoW)
- **Requirements**: [FR-07]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-013 | Given an active Lab Technician session in BioVault Lab, when the user triggers the software must be able to display a minimum of 6 colors on a high contrast background, then the action completes successfully with immediate confirmation within 1.0 s. |
| AC-014 | (unhappy path) Given missing required input parameters or an unreadable data file during the software must be able to display a minimum of 6 colors on a high contrast background, when the action executes, then the system displays a clear diagnostic notice, preserves unsaved inputs, and allows immediate retry. |

## 6. Non-functional requirements (summary)
| NFR | Target | Source |
|---|---|---|
| Search & Filter Latency | < 1.0 s response time across 3,000 site records | [NFR-01] |
| Data Storage & Privacy | 100% local device storage, 0 external cloud calls for site data privacy | [NFR-02] |
| Local Capacity | Support up to 3,000 inspection records and 500 photo notes stored locally without degradation | [NFR-03] |
| Platform Compatibility | macOS Desktop with full offline execution in disconnected job sites | [NFR-04] |
| Accessibility | WCAG 2.2 AA compliance for desktop interface | [NFR-05] |

## 7. Risks
| ID | Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| R-01 | Local filesystem document or report read/write permission denial | M | H | Prompt explicit folder read and write permissions gracefully on startup with clear diagnostic notice | Engineer |
| R-02 | Scope creep exceeding target 4 weeks MVP timeline | M | M | Strict MoSCoW prioritization; cloud sync and contractor portals deferred to v2 | PM |
| R-03 | Search query latency degrading over large local inspection record volumes | L | M | Maintain indexed local search queries to keep response time under 1.0 s for up to 3,000 records | Architect |

## 8. Assumptions and open questions
| ID | Text | Status |
|---|---|---|
| ASM-01 | All software development and testing will be conducted on Windows 10 and macOS 11 operating systems. | awaiting client at Gate 1 |
| ASM-02 | The local system will be running on a 64-bit processor with a minimum of 8GB RAM. | awaiting client at Gate 1 |
| ASM-03 | The barcode scanner will be capable of reading 2D barcodes at a minimum rate of 500 scans per minute. | awaiting client at Gate 1 |
| ASM-04 | The software will be designed to meet the WCAG 2.2 AA guidelines for accessibility. | awaiting client at Gate 1 |
| OQ-01 | Confirm whether tracking daily punch-list completion rate (target: >= 90%) is desired as an ongoing operational metric. | sent via BA |
| OQ-02 | Confirm formal sign-off authority and permission boundaries between Civil Engineer and Construction Site Inspector. | sent via BA |
| OQ-03 | Confirm preferred default punch-list export format between structured CSV and formatted print-ready text. | sent via BA |

## 9. Scope changes from the client’s request
| Requested | Decision | Reason | Source |
|---|---|---|---|
| Specimen check-in with 2D barcode generation | kept in v1 | Directly required by client discovery [Must priority] | [Q-002] |
| Cold-storage temperature excursion logging | kept in v1 | Directly required by client discovery [Must priority] | [Q-002] |
| Custodial transfer sign-off with digital confirmation | kept in v1 | Directly required by client discovery [Must priority] | [Q-002] |
| PDF/CSV regulatory inspection audit export | kept in v1 | Directly required by client discovery [Must priority] | [Q-002] |
| Barcode scanning and specimen search must respond in under 1.5 seconds | kept in v1 | Directly required by client discovery [Must priority] | [Q-003] |
| Freezer temperature deviation must not exceed 5 degrees Celsius | kept in v1 | Directly required by client discovery [Must priority] | [Q-004] |
| The software must be able to display a minimum of 6 colors on a high contrast background | kept in v1 | Directly required by client discovery [Must priority] | [Q-004] |
| Real-time contractor cloud portal synchronization | moved to v2 | Scope constraint: Strictly deferred to v2 per client privacy and v1 timeline constraints | [Q-002] |
| Automated drone survey video feed ingestion | moved to v2 | Scope constraint: Out of scope for v1 MVP; v1 focuses on handheld inspection logging and punch-list export | [Q-002] |

### Timeline and Budget Feasibility Reasoning
The v1 scope strictly includes 7 core functional features covering all client Must-have functional requirements. By deferring cloud synchronization and multi-user scaling to v2 (NG-01, NG-02), the technical architecture fits securely within the 4 weeks MVP delivery timeline and local operating budget ($6,000 development budget, local deployment with $0 monthly cloud costs).