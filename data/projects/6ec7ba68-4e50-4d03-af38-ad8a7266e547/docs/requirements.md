# 1. Problem Statement
Biomedical scientists spend a significant amount of time manually copying snippets across PDF research papers into disconnected text files, and struggle to format bibliography citations for lab reports.

# 2. Personas
- P-01: Biomedical research scientist
- P-02: Lab technician

# 3. User Journeys
- User Journey 1: Research Scientist
  1. Log in to the app.
  2. Open a PDF document.
  3. Highlight and tag a snippet.
  4. Export the snippet with a citation.
- User Journey 2: Lab Technician
  1. Receive a request to retrieve a tagged snippet from a research scientist.
  2. Log in to the app.
  3. Search for the snippet.
  4. Retrieve the snippet.

# 4. Functional Requirements
- FR-01: Local document reader with smart highlight snippet tagging (Must Have) [Source: Q-003]
- FR-02: One-click local bibliography citation export in BibTeX and Markdown formats (Must Have) [Source: Q-003]
- FR-03: All documents and notes stored locally in SQLite with zero cloud uploads for proprietary research data privacy (Must Have) [Source: Q-003]
- FR-04: Search latency under 1 second for 5,000 snippets (NFR) [Source: Q-003]
- FR-05: Cloud team sync is strictly deferred to v2 (NFR) [Source: Q-003]

# 5. Non-Functional Requirements
- NFR-01: Latency under 1.0 second for core UI actions and report generation (NFR) [Source: Q-003]
- NFR-02: All application data stored locally in SQLite with zero external cloud dependencies (NFR) [Source: Q-003]
- NFR-03: Handle local database storage for up to 1000 tasks/records without degradation (NFR) [Source: Q-003]
- NFR-04: macOS Focus mode / Do Not Disturb integration (NFR) [Source: Q-003]
- NFR-05: WCAG 2.2 AA accessibility compliance (NFR) [Source: Q-003]

# 6. Data Requirements & Entities
- Document ID
- Tag ID
- Citation ID
- User ID

# 7. Integrations & External Services
- N/A

# 8. Timeline & Budget
- Timeline: 8 weeks for v1 MVP
- Budget: $6,000 MVP build budget, zero monthly running costs

# 9. v1 Scope vs Later
- v1 Scope: Local offline document reader and smart snippet organizer for research scientists with tag-based search and local citation export
- Later: Cloud team sync and additional features

# 10. Definition of Success & Key Metrics
- Definition of Success: 80% of lab scientists exporting at least 5 citation summaries per week
- Key Metrics: Time saved by lab scientists, number of snippets exported per week, user satisfaction

# 11. Assumptions
- ASM-01: The typical document size is in the range of 1-100 pages. (Risk: Unknown)
- ASM-02: The specific tags or categories used for the snippet organizer will be determined by the research scientist community. (Risk: Unknown)