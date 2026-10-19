# 1. Problem Statement
The laboratory is losing cryogenic biological samples stored across –80 °C freezers and liquid‑nitrogen tanks. Technicians spend ~25 minutes per retrieval using manual paper logs, creating cold‑chain compliance risk. [Source: Q-002]

# 2. Personas
- **P-01 – Lab Technician** – Scans 2D DataMatrix barcodes, logs freezer rack/shelf/box positions, verifies temperature thresholds, and saves records. [Source: Q-003]  
- **P-02 – Principal Investigator** – Searches the sample inventory and requests specimen pulls. [Source: Q-003]  
- **P-03 – Compliance Officer** – Audits chain‑of‑custody logs. [Source: Q-003]

# 3. User Journeys
### Technician accession workflow (MVP core)
1. Technician receives a specimen vial.  
2. Scans the vial’s 2D DataMatrix barcode.  
3. Assigns the exact freezer location (Freezer → Rack → Shelf → Box → Position).  
4. System verifies the current temperature against the specimen’s predefined threshold.  
5. If temperature is within limits, the record is saved locally.  
6. If temperature is out of range, the system flags an alert and requires a supervisor’s sign‑off before the record can be saved. [Source: Q-004, Q-005]

# 4. Functional Requirements
- **FR-01: Scan 2D DataMatrix barcode** (Must Have) [Source: Q-004]  
- **FR-02: Record freezer location hierarchy (Freezer, Rack, Shelf, Box, Position)** (Must Have) [Source: Q-004]  
- **FR-03: Verify specimen temperature against a predefined threshold and flag out‑of‑range readings** (Must Have) [Source: Q-004]  
- **FR-04: Require supervisor sign‑off for any temperature‑alert flagged record** (Must Have) [Source: Q-004]  
- **FR-05: Persist specimen record locally on the workstation** (Must Have) [Source: Q-005]

# 5. Non‑Functional Requirements
- **NFR-01: UI response time for barcode scans must be ≤ 1.5 seconds** [Source: Q-005]  
- **NFR-02: All data must be stored locally in an SQLite database with zero cloud dependency** [Source: Q-005]  
- **NFR-03: The application must operate fully offline on laboratory desktop workstations** [Source: Q-005]  
- **NFR-04: The application must run on Windows 11 and macOS** [Source: Q-005]

# 6. Data Requirements & Entities
## Specimen Entity
| Field | Description | Source |
|-------|-------------|--------|
| SampleID (from barcode) | Unique identifier encoded in the 2D DataMatrix barcode | Q-004 |
| Freezer | Identifier of the freezer (e.g., “Freezer 2”) | Q-004 |
| Rack | Rack label within the freezer (e.g., “Rack B”) | Q-004 |
| Shelf | Shelf number (e.g., “Shelf 3”) | Q-004 |
| Box | Box number (e.g., “Box 12”) | Q-004 |
| Position | Position within the box (e.g., “E4”) | Q-004 |
| TemperatureReading | Current temperature at time of accession | Q-004 |
| TemperatureThreshold | Pre‑defined acceptable temperature limit for the specimen type | Q-004 |
| AlertFlag | Boolean indicating out‑of‑range temperature | Q-004 |
| SupervisorApproval | Timestamp/user ID of supervisor sign‑off when AlertFlag is true | Q-004 |
| RecordTimestamp | Date‑time when the specimen record is saved | Q-004 |

# 7. Integrations & External Services
No external integrations (barcode printers, LIMS, temperature sensors, network drives) are required for the MVP. [Source: Q-005]

# 8. Timeline & Budget
- **Target timeline:** 6 weeks for v1 MVP [Intake]  
- **Budget:** $15,000 total; $0/month ongoing cloud infrastructure cost [Intake]

# 9. v1 Scope vs. Later
**v1 MVP Scope** – Implements FR‑01 through FR‑05 and associated NFRs; supports the technician accession workflow described in Section 3.  
**Future Enhancements** – May include barcode generation, inventory search, pull request handling, exportable reports, and audit‑log viewing, but these are out of scope for the initial 6‑week release.

# 10. Definition of Success & Key Metrics
- Average specimen retrieval time reduced from ~25 minutes to ≤ 5 minutes. [Source: Q-002]  
- 100 % of specimens accessioned with a scanned barcode and complete location data. [Source: Q-004]  
- Zero temperature‑alert incidents remain unapproved (all require supervisor sign‑off). [Source: Q-004]  
- UI barcode‑scan response time consistently ≤ 1.5 seconds. [Source: Q-005]  

# 11. Assumptions
- **ASM-01:** Temperature thresholds for each specimen type are predefined in the system before accessioning begins. [Source: Q-004]  
- **ASM-02:** A supervisor is available to provide sign‑off on the same workstation when a temperature alert occurs. [Source: Q-004]  
- **ASM-03:** Each workstation operates on its own local SQLite database without concurrent multi‑user editing. [Source: Q-005]