# 1. Problem Statement
Lab technicians currently retrieve cryogenic biological samples using manual paper logs, taking an average of 25 minutes per retrieval. This leads to misplaced specimens and risks non‑compliance with cold‑chain regulations. The BioVault Lab Specimen Tracker will replace paper logs with a desktop system that records accession data, generates 2D barcodes, and maintains a verifiable freezer chain‑of‑custody. [Source: Q-002]

# 2. Personas
- **P-01 – Lab Technician** – Scans 2D DataMatrix barcodes, logs freezer rack/shelf/box positions, verifies temperature thresholds, and handles alerts. [Source: Q-003, Q-004]  
- **P-02 – Principal Investigator** – Searches the specimen inventory and requests specimen pulls. [Source: Q-003]  
- **P-03 – Compliance Officer** – Audits chain‑of‑custody logs for regulatory compliance. [Source: Q-003]

# 3. User Journeys
1. **Accession & Storage (Technician)**  
   - Scan vial barcode → assign freezer coordinates (Freezer 2, Rack B, Shelf 3, Box 12, Position E4) → verify temperature threshold → save record.  
   - If temperature exceeds threshold, system flags alert and requires supervisor sign‑off. [Source: Q-004]

2. **Inventory Search (Principal Investigator)**  
   - Open search interface → query by specimen ID, location, or metadata → view result list. [Source: Q-003]

3. **Pull Request (Principal Investigator)**  
   - Select specimen(s) → submit pull request → system notifies technician. [Source: Q-003]

4. **Audit (Compliance Officer)**  
   - Access chain‑of‑custody log view → filter by date, specimen, or user → export audit report. [Source: Q-003]

5. **Alert Handling (Technician & Supervisor)**  
   - Temperature alert appears → technician cannot finalize accession until supervisor signs off. [Source: Q-004]

# 4. Functional Requirements
- **FR-01: Scan 2D DataMatrix barcode** (Must Have) [Source: Q-004]  
- **FR-02: Record precise freezer location (Freezer, Rack, Shelf, Box, Position)** (Must Have) [Source: Q-004]  
- **FR-03: Verify specimen temperature against predefined threshold** (Must Have) [Source: Q-004]  
- **FR-04: Flag temperature alerts and require supervisor sign‑off** (Must Have) [Source: Q-004]  
- **FR-05: Search specimen inventory by ID, location, or metadata** (Must Have) [Source: Q-003]  
- **FR-06: Submit specimen pull requests** (Must Have) [Source: Q-003]  
- **FR-07: View and audit chain‑of‑custody logs** (Must Have) [Source: Q-003]

# 5. Non‑Functional Requirements
- **NFR-01: UI response time** – Barcode scan processing must complete within 1.5 seconds. [Source: Q-005]  
- **NFR-02: Data storage** – All data must be stored locally in an SQLite database with zero cloud dependency. [Source: Q-005]  
- **NFR-03: Offline operation & platform compatibility** – The application must run offline on laboratory desktop workstations using macOS and Windows 11. [Source: Q-005]

# 6. Data Requirements & Entities
| Entity | Key Attributes |
|--------|----------------|
| **Specimen** | SpecimenID, Barcode, AccessionDate, Metadata (type, volume, etc.) |
| **Location** | FreezerID, RackID, ShelfID, BoxID, PositionCode |
| **TemperatureReading** | SpecimenID, Timestamp, TemperatureValue, ThresholdExceeded (bool) |
| **Alert** | AlertID, SpecimenID, Type (Temperature), Status (Pending/Resolved), SupervisorSignature |
| **User** | UserID, Role (Technician, PI, ComplianceOfficer, Supervisor), Name, Credentials |
| **PullRequest** | RequestID, SpecimenID, RequestedBy (UserID), Status, Timestamp |
| **AuditLog** | LogID, ActionType, UserID, SpecimenID, Timestamp, Details |

# 7. Integrations & External Services
No integrations with external LIMS, barcode printers, or temperature‑monitoring systems are required at MVP. [Source: Q-005]

# 8. Timeline & Budget
- **Timeline:** 6 weeks for v1 MVP.  
- **Budget:** $15,000 total development budget.  
- **Ongoing cost:** $0 per month for cloud infrastructure (system is fully offline).  

# 9. v1 Scope vs. Later
| Scope Item | Included in v1 | Planned for Future Releases |
|------------|----------------|-----------------------------|
| Barcode scanning & location logging | ✅ | – |
| Temperature verification & alert workflow | ✅ | – |
| Inventory search & pull request | ✅ | – |
| Chain‑of‑custody audit view | ✅ | – |
| Barcode generation for new specimens | ❌ | Planned |
| Advanced reporting & analytics | ❌ | Planned |
| Integration with LIMS or external temperature monitors | ❌ | Planned |
| User role hierarchy & permission management beyond three roles | ❌ | Planned |

# 10. Definition of Success & Key Metrics
Success criteria have not been formally defined by the client; they will be established in a follow‑up stakeholder meeting. [Assumption]

# 11. Assumptions
- **ASM-01:** Success metrics (e.g., retrieval‑time reduction, misplaced‑sample rate) will be defined and agreed upon after this requirements document.  
- **ASM-02:** No external barcode printer integration is needed; the scanning hardware provides standard DataMatrix output compatible with the application.  
- **ASM-03:** All laboratory desktops meet the minimum hardware specifications to run a modern desktop application on macOS or Windows 11.