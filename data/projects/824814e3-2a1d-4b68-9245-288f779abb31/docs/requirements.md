# 1. Problem Statement
Biomedical scientists waste hours manually copying snippets across PDF research papers into disconnected text files, and struggle to format bibliography citations for lab reports.

# 2. Personas
- P-01: Biomedical Research Scientist
  * Pain points: Manual copying of snippets, formatting of bibliography citations
- P-02: Lab Technician
  * Pain points: Assisting researchers with snippet copying and citation formatting

# 3. User Journeys
- As a biomedical research scientist, I want to easily extract and organize snippets from PDF research papers so I can focus on my research.
- As a lab technician, I want to assist researchers in efficiently copying and formatting snippets and citations for lab reports.

# 4. Functional Requirements
- FR-01: Local document reader with smart highlight snippet tagging (Must Have) [Source: Q-003]
- FR-02: One-click local bibliography citation export in BibTeX and Markdown formats (Must Have) [Source: Q-003]
- FR-03: All documents and notes stored locally in SQLite with zero cloud uploads for proprietary research data privacy (Must Have) [Source: Q-003]
- FR-04: Search latency under 1 second for 5,000 snippets (NFR) [Source: Q-003]

# 5. Non-Functional Requirements
- NFR-01: Search latency under 1.0 second for core UI actions and report generation [Source: Q-003]
- NFR-02: All application data stored locally in SQLite with zero external cloud dependencies [Source: Q-003]
- NFR-03: Handle local database storage for up to 1000 tasks/records without degradation [Source: Q-004]
- NFR-04: macOS Focus mode / Do Not Disturb integration [Source: Q-004]
- NFR-05: WCAG 2.2 AA accessibility compliance [Source: Q-004]

# 6. Data Requirements & Entities
- All documents and notes stored locally in SQLite with zero cloud uploads for proprietary research data privacy (FR-03, NFR-02)

# 7. Integrations & External Services
- None

# 8. Timeline & Budget
- Target timeline: 8 weeks
- MVP build budget: $6,000 with zero monthly running costs

# 9. v1 Scope vs Later
- v1 MVP scope includes local document reader, smart snippet tagging, one-click citation export, and local data storage.

# 10. Definition of Success & Key Metrics
- 80% of lab scientists exporting at least 5 citation summaries per week (Success Metric, Q-004)

# 11. Assumptions
- ASM-01: No additional cloud storage services will be used beyond SQLite (Risk: data privacy, Source: Q-003)
- ASM-02: The target user base consists of biomedical research scientists and lab technicians (Source: Q-002)