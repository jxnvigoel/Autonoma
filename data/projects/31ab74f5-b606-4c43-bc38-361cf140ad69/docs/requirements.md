# 1. Problem Statement
Biomedical research scientists waste hours manually copying snippets across PDF research papers into disconnected text files, and struggle to format bibliography citations for lab reports.

# 2. Personas
- P-01: Biomedical research scientist
- P-02: Lab technician

# 3. User Journeys
- User Journey 1: Research Scientist
  - The user opens a PDF research paper and highlights a snippet of interest.
  - The user wants to organize the snippet with other relevant notes.
- User Journey 2: Lab Technician
  - The user receives a PDF document from a researcher and wants to help them organize the contents.

# 4. Functional Requirements
- FR-01: Local document reader with smart highlight snippet tagging (Must Have) [Source: Q-003]
- FR-02: One-click local bibliography citation export in BibTeX and Markdown formats (Must Have) [Source: Q-003]
- FR-03: All documents and notes stored locally in SQLite with zero cloud uploads for proprietary research data privacy (Must Have) [Source: Q-003]
- FR-04: Search latency under 1 second for 5,000 snippets (NFR) [Source: Q-003]

# 5. Non-Functional Requirements
- NFR-01: Search latency under 1 second for 5,000 snippets [Source: Q-003]
- NFR-02: All documents and notes stored locally in SQLite with zero cloud uploads for proprietary research data privacy [Source: Q-003]
- NFR-03: Success metric: 80% of lab scientists exporting at least 5 citation summaries per week [Source: Q-004]
- NFR-04: Target timeline: 8 weeks [Source: Q-004]
- NFR-05: Budget: $6,000 MVP build budget, zero monthly running costs [Source: Q-004]

# 6. Data Requirements & Entities
- Data Entity 1: Research snippet
- Data Entity 2: Bibliography citation

# 7. Integrations & External Services
- No integrations or external services required.

# 8. Timeline & Budget
- Timeline: 8 weeks for v1 MVP
- Budget: $6,000 MVP build budget, zero monthly running costs

# 9. v1 Scope vs Later
- v1 Scope: Local document reader with smart highlight snippet tagging, one-click local bibliography citation export, all documents stored locally in SQLite.
- v2 Scope: Cloud team sync.

# 10. Definition of Success & Key Metrics
- Success metric: 80% of lab scientists exporting at least 5 citation summaries per week.
- Key Metric: Number of lab scientists exporting citation summaries per week.

# 11. Assumptions
- The project will require a local document reader and smart highlight snippet tagging feature.
- The project will require one-click local bibliography citation export in BibTeX and Markdown formats.
- The project will require all documents and notes stored locally in SQLite with zero cloud uploads for proprietary research data privacy.
- The project timeline will be strictly 8 weeks.
- The project budget will be strictly $6,000 with zero monthly running costs.