# Application Flow: DocuPulse Reader

Based on Handbook Appendix A.4 (`VirtualOffice_Complete_Guide.md`), `docs/prd.md`, and `docs/architecture.md`.

---

## 1. Screens

| ID | Screen | Route | Purpose | Auth / Role | Features |
|---|---|---|---|---|---|
| `S-01` | Dashboard & Activity Overview | `/` | Operational dashboard showing recent activities, status summaries, and active alerts | `[P-01], [P-02], [P-03]` | `[F-001 / FR-01], [F-002 / FR-02], [F-003 / FR-03], [F-004 / FR-04]` |
| `S-02` | Specimen Accessioning & Check-In | `/specimens/new` | Input specimen metadata, register biological details, and generate 2D DataMatrix barcode | `[P-01]` | `[F-001 / FR-01]` |
| `S-03` | Specimen Inventory Catalog | `/specimens` | Filter, search, and inspect indexed specimen records and barcode print records | `[P-01], [P-02], [P-03]` | `[F-001 / FR-01]` |
| `S-04` | Cold-Storage Excursion Monitor | `/cold-storage` | Monitor refrigeration units, log temperature readings, and acknowledge excursion alarms | `[P-01], [P-02]` | `[F-002 / FR-02]` |
| `S-05` | Custody Transfer Portal | `/custody/transfer` | Initiate custodial handoff, record releasing custodian, and capture recipient digital sign-off | `[P-01], [P-02]` | `[F-003 / FR-03]` |
| `S-06` | Regulatory Inspection Audit Exporter | `/audit-export` | Compile tamper-evident regulatory inspection reports, review checksums, and export PDF/CSV | `[P-02], [P-03]` | `[F-004 / FR-04]` |
| `S-99` | Not Found & Permission Denied | `*` | Fallback route for invalid URLs or unauthorized access attempts | Public / Local | System Fallback |

---

## 2. Journeys

### J-1: Specimen Accessioning and Barcode Generation — covers [F-001 / FR-01], [AC-001], [AC-002]
1. On `S-01` (Dashboard) → Biomedical research scientists (`[P-01]`) sees accessioning summary widget → clicks "Check In Specimen" button.
2. `S-02` loads → Biomedical research scientists enters patient reference code, biological sample type, and target storage freezer → clicks "Generate Barcode" (`[API-001]`).
3. **Success**: System persists record in local database (`[TBL-03]`), renders 2D DataMatrix barcode (`[TBL-04]`, `[API-002]`) on screen, displays print confirmation toast, and navigates to `S-03` (`[AC-001]`).
4. **Error (invalid input)**: Inline validation error displays under empty required fields, focus shifts to offending input, and entered data is preserved without submission (`[AC-002]`).
5. **Error (system / duplicate)**: Modal alert announces duplicate accession identifier, prompts technician to refresh identifier or cancel, and preserves all user inputs (`[AC-002]`).

### J-2: Cold-Storage Temperature Excursion Logging — covers [F-002 / FR-02], [AC-003], [AC-004]
1. On `S-01` (Dashboard) → lab technicians (`[P-02]`) spots a visual excursion warning flag on the storage widget → clicks "Review Excursion".
2. `S-04` loads → displays active temperature trend chart (`[API-003]`, `[TBL-05]`) showing threshold violation for storage unit → user selects the active alert.
3. **Success**: Manager reviews peak temperature and elapsed duration, inputs corrective action notes into the sign-off dialog, and clicks "Acknowledge Incident" (`[API-004]`, `[TBL-06]`). System updates excursion status to 'acknowledged' and logs the manager credential within 5 seconds (`[AC-003]`).
4. **Error (invalid input / missing notes)**: If corrective resolution notes are empty, system highlights textarea in red and disables the acknowledge CTA (`[AC-004]`).
5. **Error (sensor read failure)**: Toast alert warns that recent sensor telemetry was unreadable, flags reading as unverified, and prompts manual verification (`[AC-004]`).

### J-3: Custodial Transfer and Digital Confirmation — covers [F-003 / FR-03], [AC-005], [AC-006]
1. On `S-03` (Specimen Catalog) → Biomedical research scientists (`[P-01]`) selects accessioned specimen → clicks "Initiate Custody Transfer".
2. `S-05` loads → Biomedical research scientists enters destination department, selects receiving personnel, and clicks "Request Receipt Confirmation" (`[API-005]`, `[TBL-07]`).
3. **Success**: Receiving staff member inputs authentication credential into digital confirmation dialog; system generates cryptographic confirmation hash, logs immutable transfer timestamp, and marks specimen location updated (`[API-006]`, `[AC-005]`).
4. **Error (mismatched credentials)**: Inline alert warns "Invalid recipient signature credentials", prevents status change, preserves releasing staff inputs, and logs an authorization alert (`[AC-006]`).
5. **Error (server / storage error)**: Non-blocking error banner appears with "Unable to commit transfer to local database. Retry", preserving all dialog state (`[AC-006]`).

### J-4: Regulatory Inspection Audit Export — covers [F-004 / FR-04], [AC-007], [AC-008]
1. On `S-01` (Dashboard) → Quality Compliance Auditor (`[P-03]`) clicks "Compliance Audit Export" in main navigation.
2. `S-06` loads → auditor selects date range, filters target storage units, chooses format (PDF summary or CSV records), and clicks "Compile Inspection Report" (`[API-007]`, `[TBL-08]`).
3. **Success**: System compiles full chain-of-custody and temperature log history, computes SHA-256 integrity hash, saves file to local filesystem export directory, and presents download/open link within 5 seconds (`[AC-007]`).
4. **Error (storage permission denied)**: If export folder lacks write permissions, system displays an actionable dialog prompting folder selection and avoids application crash (`[AC-008]`).
5. **Error (empty dataset)**: If no records match date range, system presents an informational prompt with filter reset CTA (`[AC-007]`).

---

## 3. Screen states

### S-01 Dashboard & Activity Overview
- **Loading**: Skeleton layout mirroring summary cards and operational activity feed with animated pulse effect.
- **Empty**: Informational banner stating "No lab activity recorded today", accompanied by a primary "Check In Specimen" CTA button (`[AC-001]`).
- **Populated**: Metric cards showing active specimens, storage unit status, recent excursions, and searchable activity table (`[AC-001]`, `[AC-003]`).
- **Error**: High-visibility banner stating "Unable to load dashboard metrics. Check local database connection", with a "Retry" button.
- **No Permission**: Clean access-restricted view stating "Your role does not have authorization to view operational dashboard metrics".

### S-02 Specimen Accessioning & Check-In
- **Loading**: Form skeleton displaying field placeholders and button outline.
- **Empty**: Clean form ready for data entry with autofocused accession number input and barcode preview placeholder (`[AC-001]`).
- **Populated**: Form populated with validated sample details, live 2D DataMatrix barcode preview, and "Confirm Check-In" CTA (`[AC-001]`).
- **Error**: Form fields preserved; high-contrast red error callout detailing field validation failures or duplicate accession identifiers (`[AC-002]`).
- **No Permission**: Card alert stating "Access restricted: Only Lab Technicians [P-01] are authorized to check in biological specimens" with navigation link to catalog.

### S-03 Specimen Inventory Catalog
- **Loading**: Skeleton table showing 10 rows with shimmer animation across columns.
- **Empty**: Centered illustration with message "No specimens found matching the selected filter", with a "Clear Filters" button (`[AC-001]`).
- **Populated**: Structured data table with accession number, sample type, storage unit, status badge, and action menu (`[AC-001]`).
- **Error**: Error banner stating "Failed to retrieve local specimen records", with an inline "Reload Records" action.
- **No Permission**: Notification stating "You do not have permission to view specimen inventory records".

### S-04 Cold-Storage Excursion Monitor
- **Loading**: Chart container with pulsing skeleton grid lines and placeholder status chips.
- **Empty**: Status display showing "All cold-storage units within normal temperature thresholds. Zero open excursions" (`[AC-003]`).
- **Populated**: Temperature telemetry charts, unit status cards (Normal / Warning / Excursion), and incident acknowledgment log (`[AC-003]`).
- **Error**: Warning alert stating "Temperature sensor polling timed out. Local telemetry offline", with a "Retry Sensor Connection" button (`[AC-004]`).
- **No Permission**: Banner stating "Only Pathology Lab Managers [P-02] are authorized to sign off on temperature excursions".

### S-05 Custody Transfer Portal
- **Loading**: Split-pane skeleton showing specimen details card and recipient verification box.
- **Empty**: Transfer form awaiting recipient credential input with "Scan Recipient Badge" prompt (`[AC-005]`).
- **Populated**: Active transfer record showing specimen accession metadata, releasing technician signature, and recipient confirmation button (`[AC-005]`).
- **Error**: Red alert box stating "Signature verification failed. Re-enter credentials", preserving current transfer fields (`[AC-006]`).
- **No Permission**: Warning message stating "You do not have permission to initiate or sign custody transfer records".

### S-06 Regulatory Inspection Audit Exporter
- **Loading**: Progress indicator skeleton showing export compilation steps.
- **Empty**: Export options panel with pre-selected standard CLIA compliance export preset and "Compile Report" button (`[AC-007]`).
- **Populated**: Completed export card displaying compiled PDF/CSV file path, record count, SHA-256 hash, and "Open File" button (`[AC-007]`).
- **Error**: Error dialog stating "Export write failed: Selected directory is read-only", with a "Choose Folder" selector CTA (`[AC-008]`).
- **No Permission**: Card alert stating "Only Quality Compliance Auditors [P-03] and Lab Managers [P-02] may export certified audit trails".

---

## 4. Navigation

- **Top Bar (Desktop Shell)**:
  - Left: Application logo + `DocuPulse Reader` branding link pointing to `S-01`.
  - Center: Global search input (`Cmd/Ctrl+K`) for rapid specimen accession lookup in under 1.5 seconds (`[NFR-01]`).
  - Right: System status badge (Offline / Local SQLite mode), active user avatar (`[P-01], [P-02], [P-03]`), and role badge.
- **Sidebar Navigation**:
  - `Dashboard` → `S-01` (`/`)
  - `Accession Specimen` → `S-02` (`/specimens/new`)
  - `Specimen Catalog` → `S-03` (`/specimens`)
  - `Cold-Storage Monitor` → `S-04` (`/cold-storage`)
  - `Custody Transfers` → `S-05` (`/custody/transfer`)
  - `Audit Export` → `S-06` (`/audit-export`)
- **Footer / Status Bar**:
  - Database status: `Local SQLite (Active WAL Mode)`
  - Storage directory: `Local File System (HIPAA compliant, zero cloud)`
  - Version: `v1.0.0 (BioVault MVP)`

---

## 5. Keyboard and focus

- **Logical Tab Order**: Every form and interactive data table follows standard DOM order: Top Bar Search → Main Navigation → Primary Content Inputs → Action Buttons.
- **Visible Focus Rings**: All interactive controls display high-contrast 2px focus rings (`--color-primary`, contrast ratio > 4.5:1) meeting WCAG 2.2 AA standards (`[NFR-05]`).
- **Keyboard Shortcuts**:
  - `Cmd/Ctrl + K`: Focus global accession search input.
  - `Cmd/Ctrl + N`: Open New Specimen Check-In (`S-02`).
  - `Esc`: Close modal dialogs and slide-over panels.
  - `Enter`: Submit active form or confirm modal dialog.
  - `Arrow Up / Down`: Navigate table rows and dropdown select options.
