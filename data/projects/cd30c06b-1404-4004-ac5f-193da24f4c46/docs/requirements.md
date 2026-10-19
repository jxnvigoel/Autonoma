# 1. Problem Statement
Biomedical scientists waste hours manually copying snippets across PDF research papers into disconnected text files, and struggle to format bibliography citations for lab reports.

# 2. Personas
- P-01: Research Scientist
- P-02: Lab Technician

# 3. User Journeys
- User Journey 1: A research scientist spends hours manually copying snippets from PDF research papers into disconnected text files, leading to decreased productivity and increased errors.
- User Journey 2: A lab technician assists researchers in formatting bibliography citations for lab reports, but struggles with the time-consuming process.

# 4. Functional Requirements
- FR-01: Local document reader with smart highlight snippet tagging (Must Have) [Source: Q-003]
- FR-02: One-click local bibliography citation export in BibTeX and Markdown formats (Must Have) [Source: Q-003]
- FR-03: All documents and notes stored locally in SQLite with zero cloud uploads for proprietary research data privacy (Must Have) [Source: Q-003]
- FR-04: Search latency under 1 second for 5,000 snippets (NFR) [Source: Q-003]
- FR-05: Tag-based search functionality (Should Have) [Source: Q-002]
- FR-06: Local citation export feature limited to specific types of citation styles, such as APA or MLA (Won't Have) [Source: Q-003]

# 5. Non-Functional Requirements
- NFR-01: Search latency under 1 second for 5,000 snippets [Source: Q-003]
- NFR-02: Storage & Privacy: All documents and notes stored locally in SQLite with zero cloud uploads [Source: Q-003]
- NFR-03: Platform Compatibility: Offline operation [Source: Q-003]
- NFR-04: Capacity / Concurrency: No record volume or snippet volume specified [Source: Q-003]
- NFR-05: Accessibility: No accessibility compliance specified [Source: Q-003]

# 6. Data Requirements & Entities
- Document entity: Research articles, theses
- Tag entity: Keywords, tags

# 7. Integrations & External Services
- No external services specified

# 8. Timeline & Budget
- Timeline: 8 weeks for v1 MVP
- Budget: $6,000 MVP build budget, zero monthly running costs

# 9. v1 Scope vs Later
- All features in v1 MVP, with strict deferral of cloud team sync to v2

# 10. Definition of Success & Key Metrics
- Success metric: 80% of lab scientists exporting at least 5 citation summaries per week

# 11. Assumptions
- The primary goal of the project is to improve productivity and accuracy in research and lab report formatting.