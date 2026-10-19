# Product Requirement Document (PRD): DocuPulse Reader

## 1. App overview
| Field | Value | Source |
|---|---|---|
| App name | DocuPulse Reader | [Q-001] |
| One-line description | A local offline document reader and smart snippet organizer for research scientists with tag-based search and local citation export. | [Q-001] |
| Category | Desktop Productivity & Workflow Automation | [Q-001] |
| Platforms | macOS Desktop (Local Electron) | [NFR-04] |

## 2. Problem
- **Today**: Biomedical research scientists manually copy snippets across PDF research papers into disconnected text files and format citations by hand. [Q-004]
- **Core problem**: Biomedical scientists waste hours manually copying snippets across PDF research papers into disconnected text files, and struggle to format bibliography citations for lab reports. [Q-004]
- **Why existing tools fall short**: Existing document tools require cloud uploads that compromise proprietary research data privacy, or lack integrated local BibTeX/Markdown citation export. [Q-003]

## 3. Users
### Personas
| ID | Persona | Context | Goal | Pain point | Source |
|---|---|---|---|---|---|
| P-01 | Biomedical Research Scientist | Daily professional workflow in DocuPulse Reader | Execute core biomedical research scientist responsibilities efficiently with local data ownership | Manual overhead, disconnected tools, and repetitive status formatting | [Q-004] |
| P-02 | Lab Technician | Daily professional workflow in DocuPulse Reader | Execute core lab technician responsibilities efficiently with local data ownership | Manual overhead, disconnected tools, and repetitive status formatting | [Q-004] |

### User roles and permissions
| Role | Does | Can | Cannot | Source |
|---|---|---|---|---|
| Biomedical Research Scientist | Primary workflow execution and report generation | Open documents, tag snippets, search local database, and export formatted reports | Modify system core application configuration files | [Q-004] |
| Lab Technician | Primary workflow execution and report generation | Open documents, tag snippets, search local database, and export formatted reports | Modify system core application configuration files | [Q-004] |

## 4. Goals, non-goals, metrics
### Goals
| ID | Goal | Source |
|---|---|---|
| G-01 | Deliver functional v1 MVP for DocuPulse Reader within 8 weeks for v1 MVP | [Q-004] |
| G-02 | Automate local document reader with smart highlight snippet tagging with 100% local persistence | [Q-003] |
| G-03 | Automate one-click local bibliography citation export in bibtex and markdown formats with 100% local persistence | [Q-003] |

### Non-goals (not in v1)
| ID | Non-goal (not in v1) | Why | Source |
|---|---|---|---|
| NG-01 | Cloud team synchronization and multi-device accounts | Strictly deferred to v2 per client privacy and v1 timeline constraints | [Q-003] |
| NG-02 | Real-time collaborative editing | Out of scope for v1 MVP; v1 is focused on single-user local scientist utility | [Q-003] |

### Success metrics
| ID | Metric | Target | How it is measured | Source |
|---|---|---|---|---|
| M-01 | Weekly Citation Export Adoption | 80% of lab scientists exporting at least 5 citation summaries per week | Local application export event logs (citations_exported / active_users) | [Q-004] |

## 5. Features (v1)
### Summary
| ID | Feature | Description | Priority (MoSCoW) | Requirements |
|---|---|---|---|---|
| F-001 | Local document reader with smart highlight snippet tagging | Local document reader with text highlighting and research tag snippet organization. | Must | [FR-01] |
| F-002 | One-click local bibliography citation export in BibTeX and Markdown formats | One-click local bibliography citation exporter supporting BibTeX and Markdown file formats. | Must | [FR-02] |

### F-001: Local document reader with smart highlight snippet tagging
- **Story**: As a [P-01], I want to view research documents and highlight text passages with custom tags so that I can organize critical findings without copying text into disconnected files.
- **Priority**: Must Have (MoSCoW)
- **Requirements**: [FR-01]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-001 | Given a Biomedical Research Scientist viewing a document in DocuPulse Reader, when the user highlights a text passage and assigns research tags, then the system saves the tagged snippet to the local SQLite database and updates the active tag index within 500 ms. |
| AC-002 | (unhappy path) Given a corrupted, empty, or unreadable document file, when the user attempts to open it in the reader, then the system displays an explicit error banner explaining the file issue and returns safely to the document list without crashing. |

### F-002: One-click local bibliography citation export in BibTeX and Markdown formats
- **Story**: As a [P-01], I want to export selected research snippets and their citations into BibTeX and Markdown formats so that I can compile bibliographies for lab reports with zero manual reformatting.
- **Priority**: Must Have (MoSCoW)
- **Requirements**: [FR-02]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-003 | Given one or more tagged research snippets in DocuPulse Reader, when the user selects 'Export Citations' and chooses BibTeX or Markdown format, then the system compiles the bibliography entries and copies the formatted text to the clipboard while prompting to save to disk within 1 second. |
| AC-004 | (unhappy path) Given a selected snippet lacks complete bibliographic metadata (such as author or publication year), when the user initiates citation export, then the system prompts the user to enter the missing fields or exports with an explicit '[Missing metadata]' placeholder without aborting. |

## 6. Non-functional requirements (summary)
| NFR | Target | Source |
|---|---|---|
| UI Action & Search Latency | < 1.0 s response time across local snippet collection | [NFR-01] |
| Data Storage & Privacy | 100% local SQLite storage, 0 external cloud calls for research privacy | [NFR-02] |
| Local Capacity | Support up to 5,000 snippets and 500 documents stored locally without degradation | [NFR-03] |
| Platform Compatibility | macOS Desktop (Local Electron) with offline execution | [NFR-04] |
| Accessibility | WCAG 2.2 AA compliance for desktop interface | [NFR-05] |

## 7. Risks
| ID | Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| R-01 | Local filesystem document read/write permission denial on macOS | M | H | Prompt explicit folder read permissions gracefully on startup with clear diagnostic notice | Engineer |
| R-02 | Scope creep exceeding target 8 weeks for v1 MVP timeline | M | M | Strict MoSCoW prioritization; cloud sync and multi-user accounts deferred to v2 | PM |
| R-03 | Search query latency degrading over large local snippet databases | L | M | Implement local SQLite FTS5 index on snippet text and tags to guarantee sub-second queries | Architect |

## 8. Assumptions and open questions
| ID | Text | Status |
|---|---|---|
| ASM-01 | Assume that the average number of snippets a scientist would need to organize and format citations for in a typical lab report is x [Source: Q-004] | awaiting client at Gate 1 |
| ASM-02 | Reason: Estimate based on client feedback | awaiting client at Gate 1 |
| ASM-03 | Risk: High (may not accurately reflect real-world usage) | awaiting client at Gate 1 |
| ASM-04 | Assume that the average document size is y [Source: Q-004] | awaiting client at Gate 1 |
| ASM-05 | Risk: High (may not accurately reflect real-world document sizes) | awaiting client at Gate 1 |
| ASM-06 | Assume that the research team will be using the software extensively [Source: Q-004] | awaiting client at Gate 1 |
| ASM-07 | Proposed secondary metric: Snippet tagging engagement >= 80% across active projects [Source: PM recommendation] | awaiting client at Gate 1 |
| OQ-01 | Confirm preferred default export format for citation summaries (BibTeX vs Markdown file). | sent via BA |

## 9. Scope changes from the client’s request
| Requested | Decision | Reason | Source |
|---|---|---|---|
| Local document reader with smart highlight snippet tagging | kept in v1 | Directly required by client discovery [Must priority] | [Q-003] |
| One-click local bibliography citation export in BibTeX and Markdown formats | kept in v1 | Directly required by client discovery [Must priority] | [Q-003] |
| Cloud team synchronization and multi-device accounts | moved to v2 | Scope constraint: Strictly deferred to v2 per client privacy and v1 timeline constraints | [Q-003] |
| Real-time collaborative editing | moved to v2 | Scope constraint: Out of scope for v1 MVP; v1 is focused on single-user local scientist utility | [Q-003] |

### Timeline and Budget Feasibility Reasoning
The v1 scope strictly includes 2 core functional features covering all client Must-have functional requirements. By deferring cloud synchronization and multi-user scaling to v2 (NG-01, NG-02), the technical architecture fits securely within the 8 weeks for v1 MVP delivery timeline and local operating budget ($6,000 MVP build budget, zero monthly cloud costs).