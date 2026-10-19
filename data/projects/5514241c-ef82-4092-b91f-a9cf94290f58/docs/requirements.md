# 1. Problem Statement
The current manual clipboard transcription process results in a 15% error rate in structural safety logs, lost photo context, and delayed critical hazard notices that risk job-site shutdowns and regulatory fines.

# 2. Personas
- P-01: Civil Engineer
- P-02: Construction Safety Inspector

# 3. User Journeys
- **Field Inspector Workflow**
  - Conduct site inspection with paper clipboard and handheld devices
  - Manually transcribe notes into spreadsheet
  - Spend 2-3 hours evening reviewing and updating spreadsheet
- **Civil Engineer Workflow**
  - Receive site inspection report from field inspector
  - Review report and update project management system
  - Ensure compliance with regulatory requirements

# 4. Functional Requirements
- FR-01: Structured deficiency tagging (Must Have) [Source: Q-003]
- FR-02: One-click local punch-list report export in CSV and formatted print-ready text (Must Have) [Source: Q-004]
- FR-03: All inspection logs and photo notes stored on local device storage with zero cloud uploads (Must Have) [Source: Q-004]
- FR-04: Inspection log search and filter response time under 1 second across 3,000 site records (NFR) [Source: Q-004]
- FR-05: Real-time contractor cloud portal sync is strictly deferred to v2 (NFR) [Source: Q-004]

# 5. Non-Functional Requirements
- NFR-01: Inspection log search and filter response time under 1 second across 3,000 site records (Concrete number: under 1 second) [Source: Q-004]
- NFR-02: Storage & Privacy: All inspection logs and photo notes stored on local device storage with zero cloud uploads (Verifiable yes/no check: yes) [Source: Q-004]
- NFR-03: Capacity / Concurrency: Record volume: 3,000 site records (Concrete number: 3,000) [Source: Q-004]
- NFR-04: Platform Compatibility: Desktop OS (Offline operation) (Concrete number: desktop OS, offline operation) [Source: Q-004]

# 6. Data Requirements & Entities
- Site Inspection Log
  - Inspection Date
  - Inspection Type (e.g. structural safety log, photo note)
  - Deficiency Tagging (e.g. critical hazard notice, non-critical hazard notice)
- Photo Notes
  - Photo Date
  - Photo Caption
  - Photo URL

# 7. Integrations & External Services
- None specified

# 8. Timeline & Budget
- Timeline: 7 weeks for v1 MVP (Strictly 7 weeks) [Source: Q-005]
- Budget: $7,500 MVP build budget, zero monthly subscription fees [Source: Q-005]

# 9. v1 Scope vs Later
- v1 Scope: Implement structured deficiency tagging, one-click local punch-list report export, and local offline storage (excluding real-time contractor cloud portal sync) [Source: Q-004]
- Later Scope: Implement real-time contractor cloud portal sync (v2) [Source: Q-004]

# 10. Definition of Success & Key Metrics
- Success Metric: 90% of field inspectors generating daily punch-list reports on the same day as the inspection [Source: Q-005]
- Key Metrics: Daily punch-list report generation rate, inspection log search and filter response time

# 11. Assumptions
- ASM-01: The tool will be used primarily by civil engineers and construction safety inspectors.