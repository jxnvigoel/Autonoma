# 1. Problem Statement
Lab technicians spend ~25 minutes retrieving cryogenic specimens using manual paper logs, leading to misplaced samples and cold‑chain compliance risks. The organization needs a desktop system that digitises accessioning, generates 2‑D barcodes, tracks freezer hierarchy, and provides auditable chain‑of‑custody logs. [Source: Q-002]

# 2. Personas
- **P-01 – Lab Technician** – Scans 2‑D DataMatrix barcodes, logs freezer rack/shelf/box positions, verifies temperature thresholds, and signs off alerts. [Source: Q-003, Q-004]  
- **P-02 – Principal Investigator** – Searches the specimen inventory, views sample details, and requests specimen pulls. [Source: Q-003]  
- **P-03 – Compliance Officer** – Audits chain‑of‑custody logs, exports audit data, and verifies compliance. [Source: Q-003]

# 3. User Journeys
1. **Accessioning (Technician)**  
   - Receive specimen vial.  
   - Scan 2‑D barcode.  
   - Assign storage coordinates (Freezer → Rack → Shelf → Box → Position).  
   - Verify current temperature against predefined threshold.  
   - If temperature out‑of‑range, flag and require supervisor sign‑off.  
   - Save record locally. [Source: Q-004]

2. **Inventory Search (PI)**  
   - Log in, enter search criteria (barcode, sample type, donor ID, etc.).  
   - View matching specimens with location details. [Source: Q-003]

3. **Pull Request (PI)**  
   - Select specimen(s) and submit a pull request.  
   - Technician receives request, retrieves specimen, updates status. [Source: Q-003]

4. **Audit Export (Compliance Officer)**  
   - Open audit view, filter by date/user/type.  
   - Export chain‑of‑custody log to CSV. [Source: Q-006]

# 4. Functional Requirements
- **FR-01: Accession new specimen** (Must Have) [Source: Q-004]  
- **FR-02: Verify temperature threshold and trigger supervisor sign‑off on out‑of‑range readings** (Must Have) [Source: Q-004]  
- **FR-03: Generate and print 2‑D DataMatrix barcode for newly accessioned specimens** (Must Have) [Source: Intake]  
- **FR-04: Search inventory by barcode, sample type, donor ID, or other metadata** (Must Have) [Source: Q-003]  
- **FR-05: Display full freezer hierarchy mapping for a selected specimen** (Must Have) [Source: Q-006]  
- **FR-06: Export chain‑of‑custody / audit logs to CSV** (Must Have) [Source: Q-006]  
- **FR-07: Role‑based access control (Technician edit, PI read/search, Compliance Officer read/audit/export)** (Must Have) [Source: Q-003]  
- **FR-08: Create and track pull requests for specimens** (Should Have) [Source: Q-003]  
- **FR-09: View immutable audit trail of all actions performed on a specimen** (Must Have) [Source: Q-003]

# 5. Non‑Functional Requirements
- **NFR-01: Performance – UI response for barcode scan ≤ 1.5 seconds** (Must Have) [Source: Q-005]  
- **NFR-02: Offline operation – All functionality must work without network connectivity** (Must Have) [Source: Q-005]  
- **NFR-03: Data storage – All specimen data stored locally in an SQLite database; no cloud upload** (Must Have) [Source: Q-005]  
- **NFR-04: Platform compatibility – Application runs on macOS (latest) and Windows 11 desktops** (Must Have) [Source: Q-005]  
- **NFR-05: Security – Local data file protected by OS‑level file permissions; no external data transmission** (Must Have) [Derived from NFR‑03]  
- **NFR-06: Reliability – No data loss on normal shutdown; SQLite integrity checks on startup** (Must Have)  

# 6. Data Requirements & Entities
| Entity | Mandatory Fields | Optional Fields |
|--------|------------------|-----------------|
| Specimen | Barcode value, Sample type, Collection date, Donor ID, Storage location (Freezer, Rack, Shelf, Box, Position), Accession timestamp, Temperature reading, Temperature threshold, Supervisor sign‑off flag | Notes, Additional metadata, External IDs |
| Pull Request | Request ID, Specimen barcode, Requesting PI, Request date, Status | Comments |
| Audit Log | Action type, User ID, Timestamp, Specimen barcode, Details of change | None |

# 7. Integrations & External Services
- **Barcode printer** – optional for future versions; not required for v1.  
- **Freezer temperature monitoring hardware** – temperature is entered manually during accession; real‑time hardware integration is out of scope for v1.  
- **Existing LIMS** – no integration required for v1.  

# 8. Timeline & Budget
- **Timeline:** 6 weeks to deliver v1 MVP. [Source: Intake]  
- **Budget:** $15,000 total; $0 monthly ongoing cloud infrastructure cost. [Source: Intake]

# 9. v1 Scope vs Later
| Feature | v1 (MVP) | Future Phase |
|---------|----------|--------------|
| Accessioning, barcode generation, location mapping | ✔ | – |
| Inventory search & barcode lookup | ✔ | – |
| Role‑based UI & audit trail | ✔ | – |
| CSV audit export | ✔ | – |
| Pull request workflow | Should Have (included) | – |
| Temperature alert sign‑off | ✔ | – |
| Integration with robotic arms | – | Planned for later |
| Real‑time temperature sensor feed | – | Planned for later |
| Web‑based reporting dashboard | – | Planned for later |

# 10. Definition of Success & Key Metrics
- Retrieval time reduced from 25 min to ≤ 5 min per specimen.  
- Zero misplaced samples recorded after launch.  
- 100 % compliance audit pass rate.  
- UI barcode‑scan latency ≤ 1.5 s.  
- Successful CSV export of complete audit log without data loss.  

# 11. Assumptions
- ASM-01: All laboratory workstations will have a USB or Bluetooth 2‑D DataMatrix scanner compatible with the desktop application.  
- ASM-02: Users possess administrative rights to install the application on macOS and Windows 11 machines.  
- ASM-03: Temperature thresholds are predefined per sample type and stored within the application.  
- ASM-04: Only one user will access the SQLite database at a time; concurrent multi‑user editing is not required.  
- ASM-05: CSV format is sufficient for all compliance audit reporting needs in v1.