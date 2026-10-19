# Product Requirement Document (PRD): SiteAudit Pro

## 1. App overview
| Field | Value | Source |
|---|---|---|
| App name | SiteAudit Pro | [Q-001] |
| One-line description | A local offline construction site inspection and hazard log tool for civil engineers and safety inspectors with structured deficiency tagging, offline photo-note organization, and one-click compliance punch-list export. | [Q-001] |
| Category | Civil Engineering & Construction Safety Compliance | [Q-001] |
| Platforms | macOS Desktop with offline execution | [NFR-04] |

## 2. Problem
- **Today**: field inspectors walk construction sites carrying paper clipboards and handwritten checklists, taking photos on personal phones, and then spending 2 to 3 hours every evening manually typing handwritten notes into spreadsheets. [Q-002]
- **Core problem**: manual clipboard transcription results in a 15% error rate in structural safety logs, lost photo context, and delayed critical hazard notices that risk job-site shutdowns and regulatory fines. [Q-003]
- **Why existing tools fall short**: Existing commercial construction platforms require persistent cloud connectivity which fails in underground basements and remote job sites, and charge expensive per-seat monthly subscriptions. [Q-004]

## 3. Users
### Personas
| ID | Persona | Context | Goal | Pain point | Source |
|---|---|---|---|---|---|
| P-01 | Civil Engineer | Field and project operations in SiteAudit Pro | Verify on-site structural safety compliance and certify punch-list reports without transcription delays. | Delayed hazard reporting and manual transcription errors that risk structural compliance failures. | [Q-003] |
| P-02 | Construction Safety Inspector | Field and project operations in SiteAudit Pro | Log on-site inspection checklist items and capture photo notes rapidly in offline field environments. | Lack of offline connectivity in basements and losing photo context when transcribing paper forms. | [Q-003] |

### User roles and permissions
| Role | Does | Can | Cannot | Source |
|---|---|---|---|---|
| Civil Engineer | Perform formal engineering assessments and certify punch-list reports | Create inspection templates, approve hazard flags, and export signed compliance reports | Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1 | [Q-003] |
| Construction Safety Inspector | Execute daily field inspections and record site hazard logs | Complete checklist items, attach deficiency tags, and export draft punch-lists | Unspecified in discovery; see [OQ-02] to confirm permission boundaries at Gate 1 | [Q-003] |

## 4. Goals, non-goals, metrics
### Goals
| ID | Goal | Source |
|---|---|---|
| G-01 | Deliver functional v1 MVP for SiteAudit Pro within 7 weeks for v1 MVP | [Q-005] |
| G-02 | Automate structured deficiency tagging with 100% local persistence | [Q-003] |
| G-03 | Automate one-click local punch-list report export in csv and formatted print-ready text with 100% local persistence | [Q-004] |

### Non-goals (not in v1)
| ID | Non-goal (not in v1) | Why | Source |
|---|---|---|---|
| NG-01 | Real-time contractor cloud portal sync | Strictly deferred to v2 per client privacy and v1 timeline constraints | [Q-004] |

### Success metrics
| ID | Metric | Target | How it is measured | Source |
|---|---|---|---|---|
| M-01 | Daily Punch-List Generation Rate | 90% of field inspectors generating daily punch-list reports on the same day as the inspection | Local application export audit logs (punchlists_exported_same_day / inspections_completed) | [Q-005] |

## 5. Features (v1)
### Summary
| ID | Feature | Description | Priority (MoSCoW) | Requirements |
|---|---|---|---|---|
| F-001 | Structured deficiency tagging | Offline site inspection checklist with structured hazard deficiency classification and tag indexing. | Must | [FR-01] |
| F-002 | One-click local punch-list report export in CSV and formatted print-ready text | One-click punch-list exporter generating structured CSV files and print-ready compliance summaries. | Must | [FR-02] |

### F-001: Structured deficiency tagging
- **Story**: As a [P-02], I want to log on-site inspection checklist items and tag safety deficiencies so that I can capture critical hazard records directly in offline field locations.
- **Priority**: Must Have (MoSCoW)
- **Requirements**: [FR-01]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-001 | Given a Construction Safety Inspector performing an inspection in SiteAudit Pro, when the user marks a checklist deficiency and assigns a hazard severity tag, then the system saves the record to local device storage and updates the active deficiency index within 500 ms. |
| AC-002 | (unhappy path) Given a required field (such as deficiency location or severity rating) is missing, when the user attempts to log the inspection item, then the system displays an inline validation message and preserves the entered notes without data loss. |

### F-002: One-click local punch-list report export in CSV and formatted print-ready text
- **Story**: As a [P-01], I want to export compiled site inspection punch-lists into CSV and formatted print-ready text so that I can issue same-day compliance notices without evening data entry.
- **Priority**: Must Have (MoSCoW)
- **Requirements**: [FR-02]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-003 | Given one or more logged site inspection deficiencies in SiteAudit Pro, when the user initiates punch-list export in CSV or text format, then the system compiles the deficiency log and writes the export file to the local filesystem within 1.0 s. |
| AC-004 | (unhappy path) Given the target local export folder lacks write permissions or disk space is exhausted, when the export executes, then the system presents a clear diagnostic warning and offers an alternative export location without aborting the session. |

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
| R-02 | Scope creep exceeding target 7 weeks for v1 MVP timeline | M | M | Strict MoSCoW prioritization; cloud sync and contractor portals deferred to v2 | PM |
| R-03 | Search query latency degrading over large local inspection record volumes | L | M | Maintain indexed local search queries to keep response time under 1.0 s for up to 3,000 records | Architect |

## 8. Assumptions and open questions
| ID | Text | Status |
|---|---|---|
| ASM-01 | The tool will be used primarily by civil engineers and construction safety inspectors. | awaiting client at Gate 1 |
| OQ-01 | Confirm whether tracking daily punch-list completion rate (target: >= 90%) is desired as an ongoing operational metric. | sent via BA |
| OQ-02 | Confirm formal sign-off authority and permission boundaries between Civil Engineer and Construction Site Inspector. | sent via BA |
| OQ-03 | Confirm preferred default punch-list export format between structured CSV and formatted print-ready text. | sent via BA |

## 9. Scope changes from the client’s request
| Requested | Decision | Reason | Source |
|---|---|---|---|
| Structured deficiency tagging | kept in v1 | Directly required by client discovery [Must priority] | [Q-003] |
| One-click local punch-list report export in CSV and formatted print-ready text | kept in v1 | Directly required by client discovery [Must priority] | [Q-004] |
| Real-time contractor cloud portal sync | moved to v2 | Scope constraint: Strictly deferred to v2 per client privacy and v1 timeline constraints | [Q-004] |

### Timeline and Budget Feasibility Reasoning
The v1 scope strictly includes 2 core functional features covering all client Must-have functional requirements. By deferring cloud synchronization and multi-user scaling to v2 (NG-01), the technical architecture fits securely within the 7 weeks for v1 MVP delivery timeline and local operating budget ($7,500 MVP build budget, zero monthly subscription costs).