# Product Requirement Document (PRD): DocuPulse Reader

## 1. App overview
| Field | Value | Source |
|---|---|---|
| App name | DocuPulse Reader | [Q-001] |
| One-line description | A local offline document reader and smart snippet organizer for research scientists with tag-based search and local citation export. | [Q-001] |
| Category | Desktop Productivity & Workflow Automation | [Q-001] |
| Platforms | macOS Desktop (Local Electron) | [NFR-04] |

## 2. Problem
- **Today**: Users currently rely on manual copy-pasting across disconnected files and fragmented workarounds to manage their work, resulting in lost context and wasted hours. [Q-003]
- **Core problem**: The core problem is that biomedical scientists waste hours manually copying snippets across PDF research papers into disconnected text files, and struggle to format bibliography citations for lab reports. [Q-003]
- **Why existing tools fall short**: Existing solutions either require heavy cloud services with ongoing subscription fees, lack local data ownership, or fail to automate the repetitive manual synthesis required by daily workflows. [Q-003]

## 3. Users
### Personas
| ID | Persona | Context | Goal | Pain point | Source |
|---|---|---|---|---|---|
| P-01 | Biomedical Research Scientist | Daily professional workflow in DocuPulse Reader | Execute core biomedical research scientist responsibilities efficiently with local data ownership | Manual overhead, disconnected tools, and repetitive status formatting | [Q-003] |
| P-02 | Lab Technician | Daily professional workflow in DocuPulse Reader | Execute core lab technician responsibilities efficiently with local data ownership | Manual overhead, disconnected tools, and repetitive status formatting | [Q-003] |

### User roles and permissions
| Role | Does | Can | Cannot | Source |
|---|---|---|---|---|
| Biomedical Research Scientist | Primary workflow execution and report generation | Open documents, tag snippets, search local database, and export formatted reports | Modify system core application configuration files | [Q-003] |
| Lab Technician | Primary workflow execution and report generation | Open documents, tag snippets, search local database, and export formatted reports | Modify system core application configuration files | [Q-003] |

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
| NG-01 | Cloud team synchronization and multi-device accounts | Strictly deferred to v2 per client privacy and v1 timeline constraints | [Q-004] |
| NG-02 | Real-time collaborative editing | Out of scope for v1 MVP; v1 is focused on single-user local scientist utility | [Q-004] |

### Success metrics
| ID | Metric | Target | How it is measured | Source |
|---|---|---|---|---|
| M-01 | Weekly Citation Export Adoption | Target timeline is strictly 8 weeks. MVP build budget is $6,000 with zero monthly running costs.  80% of lab scientists exporting at least 5 citation summaries per week. Please finalize requirements.md | Local application export event logs (citations_exported / active_users) | [Q-004] |
| M-02 | Snippet Tagging Engagement Rate | >= 85% of viewed research documents having at least one tagged snippet | Local SQLite database query on tagged snippet count | [Q-004] |

## 5. Features (v1)
### Summary
| ID | Feature | Description | Priority (MoSCoW) | Requirements |
|---|---|---|---|---|
| F-001 | Local document reader with smart highlight snippet tagging | Local document reader with text highlighting and research tag snippet organization. | Must | [FR-01] |
| F-002 | One-click local bibliography citation export in BibTeX and Markdown formats | One-click local bibliography citation exporter supporting BibTeX and Markdown file formats. | Must | [FR-02] |
| F-003 | Focus timer with notification blocking | Distraction-free focus timer block with automatic macOS Do Not Disturb notification suppression. | Must | [FR-03] |
| F-004 | Local git commit parser that generates markdown summaries | Local git commit history parser that extracts commit messages, authors, and timestamps into markdown format. | Must | [FR-04] |

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

### F-003: Focus timer with notification blocking
- **Story**: As a [P-01], I want to start a timed focus block that activates macOS Do Not Disturb mode so that I can work without incoming notification distractions.
- **Priority**: Must Have (MoSCoW)
- **Requirements**: [FR-03]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-005 | Given a developer starting work on a task in DocuPulse Reader, when they start a focus timer session, then the timer starts counting down and macOS Do Not Disturb mode activates within 1 second. |
| AC-006 | (unhappy path) Given macOS system notification permissions have not been granted, when the user starts the focus timer, then the application presents an inline permission prompt, keeps the local timer running, and logs a non-fatal warning without terminating the session. |

### F-004: Local git commit parser that generates markdown summaries
- **Story**: As a [P-01], I want to parse today's local git commit logs into a markdown standup summary so that I can report my daily progress without manually reviewing terminal logs.
- **Priority**: Must Have (MoSCoW)
- **Requirements**: [FR-04]

| ID | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-007 | Given a local git repository with commits made in the active tracking period, when the user clicks parse commits, then the system reads the local git log and generates a bulleted markdown summary within 1 second. |
| AC-008 | (unhappy path) Given no git commits exist for the selected date or the specified path is not a git repository, when the user requests a commit summary, then the system displays an explicit empty-state message with instructions to select a valid git repository. |

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
| ASM-01 | No external cloud dependencies required for proprietary research data privacy [Source: Q-003] | awaiting client at Gate 1 |
| ASM-02 | No changes to the database schema will be required for v1 MVP [Source: Q-003] | awaiting client at Gate 1 |
| OQ-01 | Confirm preferred default export format for citation summaries (BibTeX vs Markdown file). | sent via BA |

## 9. Scope changes from the client’s request
| Requested | Decision | Reason | Source |
|---|---|---|---|
| Local document reader with smart highlight snippet tagging | kept in v1 | Directly required by client discovery [Must priority] | [Q-003] |
| One-click local bibliography citation export in BibTeX and Markdown formats | kept in v1 | Directly required by client discovery [Must priority] | [Q-003] |
| Focus timer with notification blocking | kept in v1 | Directly required by client discovery [Must priority] | [Q-004] |
| Local git commit parser that generates markdown summaries | kept in v1 | Directly required by client discovery [Must priority] | [Q-004] |
| Cloud team synchronization and multi-device accounts | moved to v2 | Scope constraint: Strictly deferred to v2 per client privacy and v1 timeline constraints | [Q-004] |
| Real-time collaborative editing | moved to v2 | Scope constraint: Out of scope for v1 MVP; v1 is focused on single-user local scientist utility | [Q-004] |

### Timeline and Budget Feasibility Reasoning
The v1 scope strictly includes 4 core functional features covering all client Must-have functional requirements. By deferring cloud synchronization and multi-user scaling to v2 (NG-01, NG-02), the technical architecture fits securely within the 8 weeks for v1 MVP delivery timeline and local operating budget ($6,000 MVP build budget, zero monthly cloud costs).