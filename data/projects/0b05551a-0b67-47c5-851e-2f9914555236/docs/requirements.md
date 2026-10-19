# 1. Problem Statement
Biomedical scientists waste hours manually copying snippets across PDF research papers into disconnected text files, and struggle to format bibliography citations for lab reports.

# 2. Personas
- P-01: Biomedical Research Scientist
- P-02: Lab Technician

# 3. User Journeys
- Research Scientist:
  1. Identify key research papers to review.
  2. Manually copy snippets into separate text files.
  3. Format bibliography citations for lab reports.

# 4. Functional Requirements
- FR-01: Local document reader with smart highlight snippet tagging (Must Have) [Source: Q-003]
- FR-02: One-click local bibliography citation export in BibTeX and Markdown formats (Must Have) [Source: Q-003]
- FR-03: All documents and notes stored locally in SQLite with zero cloud uploads for proprietary research data privacy (Must Have) [Source: Q-003]
- FR-04: Search latency under 1 second for 5,000 snippets (NFR) [Source: Q-003]

# 5. Non-Functional Requirements
- NFR-01: Search latency under 1 second for 5,000 snippets [Source: Q-003]
- NFR-02: Storage & Privacy: All documents and notes stored locally in SQLite with zero cloud uploads [Source: Q-003]
- NFR-03: Platform Compatibility: Offline operation on desktop OS [Source: Q-003]
- NFR-04: Accessibility: Compliance with [insert relevant accessibility guidelines] [Source: Q-003]

# 6. Data Requirements & Entities
- Document data (e.g., PDF, Word document) [Source: Q-003]
- Snippet data (e.g., formatted text, citations) [Source: Q-003]
- Citation data (e.g., BibTeX, Markdown) [Source: Q-003]

# 7. Integrations & External Services
- None specified [Source: Q-004]

# 8. Timeline & Budget
- Target timeline: 8 weeks [Source: Q-004]
- MVP build budget: $6,000 [Source: Q-004]

# 9. v1 Scope vs Later
- v1 scope: Local document reader, smart snippet tagging, bibliography citation export [Source: Q-004]
- Future scope: Cloud team sync (v2) [Source: Q-003]

# 10. Definition of Success & Key Metrics
- Success metric: 80% of lab scientists exporting at least 5 citation summaries per week [Source: Q-004]
- Key metric: User satisfaction with the local document reader and bibliography citation export [Source: Q-004]

# 11. Assumptions
- ASM-01: Assume that the average number of snippets a scientist would need to organize and format citations for in a typical lab report is x [Source: Q-004]
- Reason: Estimate based on client feedback
- Risk: High (may not accurately reflect real-world usage)
- ASM-02: Assume that the average document size is y [Source: Q-004]
- Reason: Estimate based on client feedback
- Risk: High (may not accurately reflect real-world document sizes)
- ASM-03: Assume that the research team will be using the software extensively [Source: Q-004]
- Reason: Estimate based on client feedback
- Risk: High (may not accurately reflect real-world usage)