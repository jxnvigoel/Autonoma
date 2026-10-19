# Data Schema: BioVault Lab

**Database**: Embedded Relational SQLite [ADR-003]  
**Query Layer**: Direct Parametrized SQL with B-Tree Index Optimization [ADR-003]  
**Migrations**: Managed Local DDL Migrations in `data/migrations/`  

---

## 1. Tables

### TBL-01: `users`
Stores authenticated local laboratory personnel and authorized system roles. Needed by [P-01], [P-02], [P-03], [ADR-004].

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | UUIDv7 unique identifier |
| `username` | TEXT | NOT NULL UNIQUE | Alphanumeric staff login identifier |
| `role` | TEXT | NOT NULL CHECK (role IN ('lab_technician', 'lab_manager', 'quality_auditor')) | Role-based authorization tier |
| `full_name` | TEXT | NOT NULL | Staff member display name |
| `created_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | UTC creation timestamp |

### TBL-02: `storage_units`
Stores monitored cold-chain storage refrigeration units, freezers, and temperature limits. Needed by [F-002], [AC-003], [NFR-03].

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | UUIDv7 unique unit identifier |
| `name` | TEXT | NOT NULL UNIQUE | Unit descriptor (e.g., 'Ultra-Low Freezer 01') |
| `unit_type` | TEXT | NOT NULL CHECK (unit_type IN ('ultra_low_freezer', 'cryo_tank', 'cold_room', 'refrigerator')) | Equipment category |
| `target_temp_celsius` | REAL | NOT NULL | Target baseline temperature in Celsius |
| `warning_threshold_celsius` | REAL | NOT NULL | Excursion warning threshold in Celsius |
| `created_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | Registration timestamp |

### TBL-03: `specimens`
Stores bio-specimen accessioning records, patient references, and active storage state. Needed by [F-001], [AC-001], [AC-002], [NFR-03].

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | UUIDv7 unique record identifier |
| `accession_number` | TEXT | NOT NULL UNIQUE | Unique specimen accession number [AC-001] |
| `patient_ref` | TEXT | NOT NULL | De-identified patient reference code for HIPAA compliance [NFR-02] |
| `sample_type` | TEXT | NOT NULL CHECK (sample_type IN ('blood', 'plasma', 'serum', 'tissue', 'urine', 'biopsy', 'swab')) | Specimen biological classification |
| `storage_unit_id` | TEXT | REFERENCES storage_units(id) ON DELETE SET NULL | Current cold-storage unit location [AC-002] |
| `status` | TEXT | NOT NULL DEFAULT 'accessioned' CHECK (status IN ('accessioned', 'in_storage', 'transferred', 'disposed')) | Specimen lifecycle state |
| `collected_at` | TEXT | NOT NULL | Specimen collection UTC timestamp |
| `created_by_user_id` | TEXT | NOT NULL REFERENCES users(id) | Accessioning technician [P-01] |
| `created_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | Accessioning UTC timestamp |
| `updated_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | Last state modification timestamp |

### TBL-04: `barcodes`
Stores generated 2D DataMatrix barcode labels mapped to accessioned specimens. Needed by [F-001], [AC-001], [API-002].

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | UUIDv7 unique barcode identifier |
| `specimen_id` | TEXT | NOT NULL UNIQUE REFERENCES specimens(id) ON DELETE CASCADE | Parent specimen record [AC-001] |
| `barcode_format` | TEXT | NOT NULL DEFAULT 'datamatrix' CHECK (barcode_format IN ('datamatrix', 'qr', 'code128')) | 2D barcode encoding standard |
| `payload` | TEXT | NOT NULL UNIQUE | Scannable encoded payload string |
| `printed_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | Print generation timestamp |
| `printed_by_user_id` | TEXT | NOT NULL REFERENCES users(id) | Printing technician [P-01] |

### TBL-05: `temperature_readings`
Stores continuous cold-chain temperature readings recorded from monitored units. Needed by [F-002], [AC-003], [NFR-01].

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | UUIDv7 unique reading identifier |
| `storage_unit_id` | TEXT | NOT NULL REFERENCES storage_units(id) ON DELETE CASCADE | Monitored storage unit [AC-003] |
| `temperature_celsius` | REAL | NOT NULL | Measured temperature reading in Celsius |
| `is_excursion` | INTEGER | NOT NULL DEFAULT 0 CHECK (is_excursion IN (0, 1)) | Flag indicating threshold violation |
| `recorded_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | Sensor log timestamp |

### TBL-06: `temperature_excursions`
Stores temperature excursion alarm events, peak severity, and managerial sign-offs. Needed by [F-002], [AC-004], [API-004].

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | UUIDv7 unique excursion event identifier |
| `storage_unit_id` | TEXT | NOT NULL REFERENCES storage_units(id) ON DELETE CASCADE | Compromised storage unit |
| `reading_id` | TEXT | NOT NULL REFERENCES temperature_readings(id) ON DELETE CASCADE | Triggering sensor reading |
| `peak_temp_celsius` | REAL | NOT NULL | Maximum excursion temperature recorded |
| `duration_minutes` | INTEGER | NOT NULL DEFAULT 0 | Out-of-range duration in minutes |
| `status` | TEXT | NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'acknowledged', 'resolved')) | Excursion resolution workflow state |
| `acknowledged_by_user_id` | TEXT | REFERENCES users(id) | Pathology Lab Manager reviewer [P-02] |
| `resolution_notes` | TEXT | | Managerial corrective action notes [AC-004] |
| `created_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | Excursion alarm trigger timestamp |
| `acknowledged_at` | TEXT | | Formal acknowledgment timestamp |

### TBL-07: `custody_transfers`
Stores chain-of-custody handoffs, releasing/receiving personnel, and digital confirmations. Needed by [F-003], [AC-005], [AC-006], [API-005].

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | UUIDv7 unique transfer identifier |
| `specimen_id` | TEXT | NOT NULL REFERENCES specimens(id) ON DELETE RESTRICT | Transferred specimen record [AC-005] |
| `releasing_user_id` | TEXT | NOT NULL REFERENCES users(id) | Relinquishing lab staff member [P-01] |
| `receiving_user_id` | TEXT | REFERENCES users(id) | Acknowledging recipient staff member |
| `destination_lab` | TEXT | NOT NULL | External or departmental transfer destination |
| `status` | TEXT | NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'rejected')) | Custodial transfer state |
| `digital_signature` | TEXT | | Digital confirmation hash upon receipt [AC-006] |
| `transferred_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | Physical transfer timestamp |

### TBL-08: `audit_exports`
Stores immutable regulatory inspection reports compiled to the local filesystem. Needed by [F-004], [AC-007], [AC-008], [NFR-02].

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | UUIDv7 unique export record identifier |
| `user_id` | TEXT | NOT NULL REFERENCES users(id) | Requesting auditor or manager [P-02, P-03] |
| `export_format` | TEXT | NOT NULL CHECK (export_format IN ('pdf', 'csv')) | Output document format |
| `file_path` | TEXT | NOT NULL | Canonical local filesystem destination path |
| `checksum_sha256` | TEXT | NOT NULL | Cryptographic SHA-256 integrity hash [NFR-02] |
| `record_count` | INTEGER | NOT NULL CHECK (record_count >= 0) | Total specimen/audit entries compiled |
| `exported_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | Export generation timestamp |

---

## 2. Relationships

The relational data model enforces strict referential integrity across all operational entities:
- `storage_units` (1) <────── (N) `specimens` [ON DELETE SET NULL]
- `users` (1) <────── (N) `specimens` [ON DELETE RESTRICT]
- `specimens` (1) <────── (1) `barcodes` [ON DELETE CASCADE]
- `storage_units` (1) <────── (N) `temperature_readings` [ON DELETE CASCADE]
- `storage_units` (1) <────── (N) `temperature_excursions` [ON DELETE CASCADE]
- `temperature_readings` (1) <────── (1) `temperature_excursions` [ON DELETE CASCADE]
- `specimens` (1) <────── (N) `custody_transfers` [ON DELETE RESTRICT]
- `users` (1) <────── (N) `custody_transfers` [ON DELETE RESTRICT]
- `users` (1) <────── (N) `audit_exports` [ON DELETE RESTRICT]

---

## 3. Indexes

One per main query, each with the exact API endpoint and query path it serves:

| Index Name | Table | Columns | Serves |
|---|---|---|---|
| `idx_specimens_accession` | `specimens` | `(accession_number)` | Barcode scanning & specimen check-in [API-001] [F-001] [AC-001] |
| `idx_specimens_unit_status` | `specimens` | `(storage_unit_id, status)` | Fast freezer inventory search and status filter [API-001] [F-001] [AC-002] |
| `idx_barcodes_payload` | `barcodes` | `(payload)` | Direct 2D barcode scanner verification [API-002] [F-001] |
| `idx_temp_readings_unit_time` | `temperature_readings` | `(storage_unit_id, recorded_at DESC)` | Time-series excursion queries & chart rendering [API-003] [F-002] [AC-003] |
| `idx_excursions_unit_status` | `temperature_excursions` | `(storage_unit_id, status)` | Active temperature excursion dashboard alerts [API-004] [F-002] [AC-004] |
| `idx_custody_specimen` | `custody_transfers` | `(specimen_id, transferred_at DESC)` | Chronological chain-of-custody audit trail [API-005] [F-003] [AC-005] |
| `idx_audit_exports_user_time` | `audit_exports` | `(user_id, exported_at DESC)` | Regulatory export history and audit log verification [API-007] [F-004] [AC-007] |

---

## 4. Access Rules & Permissions

Enforced by application service layer and local database connection boundaries [ADR-004]:

| Table | Read | Insert | Update | Delete | Enforced By |
|---|---|---|---|---|---|
| `specimens` | All Personas | Lab Technician [P-01] | Lab Technician [P-01] | Disallowed (Audit Immutability) | Service Layer Auth Policy |
| `barcodes` | All Personas | Lab Technician [P-01] | Disallowed | Disallowed | Service Layer Auth Policy |
| `storage_units` | All Personas | Pathology Lab Manager [P-02] | Pathology Lab Manager [P-02] | Disallowed | Service Layer Auth Policy |
| `temperature_readings` | All Personas | System Sensor / Technician | Disallowed | Disallowed | Service Layer Auth Policy |
| `temperature_excursions` | All Personas | System Monitor | Pathology Lab Manager [P-02] | Disallowed | Service Layer Auth Policy |
| `custody_transfers` | All Personas | Lab Technician [P-01] | Pathology Lab Manager [P-02] | Disallowed | Service Layer Auth Policy |
| `audit_exports` | Lab Manager, Quality Auditor | Quality Compliance Auditor [P-03] | Disallowed | Disallowed | Service Layer Auth Policy |
| `users` | All Personas | System Admin [OQ-02] | System Admin [OQ-02] | Disallowed | Service Layer Auth Policy |

---

## 5. Growth and Retention

| Table | Rows Year 1 | Retention Policy | Source |
|---|---|---|---|
| `specimens` | ~10,000 records | Retained locally for regulatory audit duration [NFR-03] | [NFR-03] |
| `barcodes` | ~10,000 records | Retained with parent specimen record [NFR-03] | [NFR-03] |
| `storage_units` | ~50 units | Permanent equipment catalog [NFR-03] | [NFR-03] |
| `temperature_readings` | ~365,000 readings | Retained locally with periodic archive [NFR-03] | [NFR-03] |
| `temperature_excursions` | ~500 events | Retained 7 years per CLIA audit standards [NFR-03] | [NFR-03] |
| `custody_transfers` | ~5,000 transfers | Retained permanently for chain-of-custody proof [NFR-03] | [NFR-03] |
| `audit_exports` | ~500 reports | Retained locally with SHA256 checksums [NFR-02] | [NFR-02] |
| `users` | ~25 records | Active staff directory [Q-002] | [Q-002] |

---

## 6. Seed Data

Initial testing data for preview environment:
- 3 test users (`tech_alex`, `manager_dr_smith`, `auditor_rachel`) covering all 3 personas [P-01, P-02, P-03].
- 2 monitored storage units: `Ultra-Low Freezer -80C (Unit 01)` and `Refrigerated Storage 4C (Unit 02)`.
- 5 baseline specimen records across sample types (blood, plasma, tissue) with generated 2D barcodes.
- 1 historical excursion record with managerial sign-off for walk-through demonstration.

---

## 7. Executable SQL DDL Migrations

```sql
-- Migration 001: Initial Relational Schema for BioVault Lab
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK (role IN ('lab_technician', 'lab_manager', 'quality_auditor')),
    full_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS storage_units (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    unit_type TEXT NOT NULL CHECK (unit_type IN ('ultra_low_freezer', 'cryo_tank', 'cold_room', 'refrigerator')),
    target_temp_celsius REAL NOT NULL,
    warning_threshold_celsius REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS specimens (
    id TEXT PRIMARY KEY,
    accession_number TEXT NOT NULL UNIQUE,
    patient_ref TEXT NOT NULL,
    sample_type TEXT NOT NULL CHECK (sample_type IN ('blood', 'plasma', 'serum', 'tissue', 'urine', 'biopsy', 'swab')),
    storage_unit_id TEXT REFERENCES storage_units(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'accessioned' CHECK (status IN ('accessioned', 'in_storage', 'transferred', 'disposed')),
    collected_at TEXT NOT NULL,
    created_by_user_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS barcodes (
    id TEXT PRIMARY KEY,
    specimen_id TEXT NOT NULL UNIQUE REFERENCES specimens(id) ON DELETE CASCADE,
    barcode_format TEXT NOT NULL DEFAULT 'datamatrix' CHECK (barcode_format IN ('datamatrix', 'qr', 'code128')),
    payload TEXT NOT NULL UNIQUE,
    printed_at TEXT NOT NULL DEFAULT (datetime('now')),
    printed_by_user_id TEXT NOT NULL REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS temperature_readings (
    id TEXT PRIMARY KEY,
    storage_unit_id TEXT NOT NULL REFERENCES storage_units(id) ON DELETE CASCADE,
    temperature_celsius REAL NOT NULL,
    is_excursion INTEGER NOT NULL DEFAULT 0 CHECK (is_excursion IN (0, 1)),
    recorded_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS temperature_excursions (
    id TEXT PRIMARY KEY,
    storage_unit_id TEXT NOT NULL REFERENCES storage_units(id) ON DELETE CASCADE,
    reading_id TEXT NOT NULL REFERENCES temperature_readings(id) ON DELETE CASCADE,
    peak_temp_celsius REAL NOT NULL,
    duration_minutes INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'acknowledged', 'resolved')),
    acknowledged_by_user_id TEXT REFERENCES users(id),
    resolution_notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    acknowledged_at TEXT
);

CREATE TABLE IF NOT EXISTS custody_transfers (
    id TEXT PRIMARY KEY,
    specimen_id TEXT NOT NULL REFERENCES specimens(id) ON DELETE RESTRICT,
    releasing_user_id TEXT NOT NULL REFERENCES users(id),
    receiving_user_id TEXT REFERENCES users(id),
    destination_lab TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'rejected')),
    digital_signature TEXT,
    transferred_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_exports (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    export_format TEXT NOT NULL CHECK (export_format IN ('pdf', 'csv')),
    file_path TEXT NOT NULL,
    checksum_sha256 TEXT NOT NULL,
    record_count INTEGER NOT NULL CHECK (record_count >= 0),
    exported_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_specimens_accession ON specimens (accession_number);
CREATE INDEX IF NOT EXISTS idx_specimens_unit_status ON specimens (storage_unit_id, status);
CREATE INDEX IF NOT EXISTS idx_barcodes_payload ON barcodes (payload);
CREATE INDEX IF NOT EXISTS idx_temp_readings_unit_time ON temperature_readings (storage_unit_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_excursions_unit_status ON temperature_excursions (storage_unit_id, status);
CREATE INDEX IF NOT EXISTS idx_custody_specimen ON custody_transfers (specimen_id, transferred_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_exports_user_time ON audit_exports (user_id, exported_at DESC);
```
