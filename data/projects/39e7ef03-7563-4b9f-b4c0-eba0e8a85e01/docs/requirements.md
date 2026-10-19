# 1. Problem Statement
The core problem is that biomedical scientists waste hours manually copying snippets across PDF research papers into disconnected text files, and struggle to format bibliography citations for lab reports.

# 2. Personas
- P-01: Biomedical Research Scientist
- P-02: Lab Technician

# 3. User Journeys
- User Journey: "Research Scientist"
  - Research Scientist opens a PDF research paper
  - Research Scientist copies snippets from the PDF into a separate text file
  - Research Scientist struggles to format bibliography citations for the lab report
- User Journey: "Lab Technician"
  - Lab Technician is tasked with organizing reference materials for a research paper
  - Lab Technician uses the local document reader to highlight and tag snippets
  - Lab Technician exports citation summaries in BibTeX and Markdown formats

# 4. Functional Requirements
- FR-01: Local document reader with smart highlight snippet tagging (Must Have) [Source: Q-003]
- FR-02: One-click local bibliography citation export in BibTeX and Markdown formats (Must Have) [Source: Q-003]
- FR-03: All documents and notes stored locally in SQLite with zero cloud uploads for proprietary research data privacy (Must Have) [Source: Q-003]
- FR-04: Search latency under 1 second for 5,000 snippets (NFR) [Source: Q-003]
- FR-05: Focus timer with notification blocking (Must Have) [Source: Q-004]
- FR-06: Local git commit parser that generates markdown summaries (Must Have) [Source: Q-004]

# 5. Non-Functional Requirements
- NFR-01: Latency under 1.0 second for core UI actions and report generation [Source: Q-004]
- NFR-02: All application data stored locally in SQLite with zero external cloud dependencies [Source: Q-003]
- NFR-03: Handle local database storage for up to 1000 tasks/records without degradation [Source: Q-004]
- NFR-04: macOS Focus mode / Do Not Disturb integration [Source: Q-004]
- NFR-05: WCAG 2.2 AA accessibility compliance [Source: Q-004]
- NFR-06: Success metric: 80% of lab scientists exporting at least 5 citation summaries per week [Source: Q-004]

# 6. Data Requirements & Entities
- Data Entity: Document
- Data Entity: Snippet
- Data Entity: Citation Summary

# 7. Integrations & External Services
- No external services required

# 8. Timeline & Budget
- Timeline: 8 weeks for v1 MVP
- Budget: $6,000 MVP build budget

# 9. v1 Scope vs Later
- All requirements listed in this document will be included in v1 MVP
- Future versions will build upon this foundation

# 10. Definition of Success & Key Metrics
- Success metric: 80% of lab scientists exporting at least 5 citation summaries per week
- Key metrics: Snippet export rate, Citation summary export rate, User satisfaction

# 11. Assumptions
- ASM-01: No external cloud dependencies required for proprietary research data privacy [Source: Q-003]
- ASM-02: No changes to the database schema will be required for v1 MVP [Source: Q-003]