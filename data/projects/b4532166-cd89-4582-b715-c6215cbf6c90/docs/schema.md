# Data Schema: BioVault Lab

**Database**: Embedded Relational SQLite [ADR-003]  
**Query Layer**: Direct Parametrized SQL with B-Tree Index Optimization [ADR-003]  
**Migrations**: Managed Local DDL Migrations in `data/migrations/`  

---

## 1. Tables

### TBL-01: `specimen_check_in_with_2_records`
Stores persistent records for Specimen check-in with 2D barcode generation. Needed by [F-001], [API-001].

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | UUIDv7 unique record identifier |
| `name` | TEXT | NOT NULL | Record descriptor / title |
| `status` | TEXT | NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending', 'completed', 'archived')) | Operational workflow status |
| `details` | TEXT | NOT NULL | Serialized structured parameters |
| `created_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | UTC creation timestamp |
| `updated_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | UTC last modified timestamp |
### TBL-02: `cold_storage_temperature_records`
Stores persistent records for Cold-storage temperature excursion logging. Needed by [F-002], [API-002].

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | UUIDv7 unique record identifier |
| `name` | TEXT | NOT NULL | Record descriptor / title |
| `status` | TEXT | NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending', 'completed', 'archived')) | Operational workflow status |
| `details` | TEXT | NOT NULL | Serialized structured parameters |
| `created_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | UTC creation timestamp |
| `updated_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | UTC last modified timestamp |
### TBL-03: `custodial_transfer_sign__records`
Stores persistent records for Custodial transfer sign-off with digital confirmation. Needed by [F-003], [API-003].

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | UUIDv7 unique record identifier |
| `name` | TEXT | NOT NULL | Record descriptor / title |
| `status` | TEXT | NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending', 'completed', 'archived')) | Operational workflow status |
| `details` | TEXT | NOT NULL | Serialized structured parameters |
| `created_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | UTC creation timestamp |
| `updated_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | UTC last modified timestamp |
### TBL-04: `pdf_csv_regulatory_inspe_records`
Stores persistent records for PDF/CSV regulatory inspection audit export. Needed by [F-004], [API-004].

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | UUIDv7 unique record identifier |
| `name` | TEXT | NOT NULL | Record descriptor / title |
| `status` | TEXT | NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending', 'completed', 'archived')) | Operational workflow status |
| `details` | TEXT | NOT NULL | Serialized structured parameters |
| `created_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | UTC creation timestamp |
| `updated_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | UTC last modified timestamp |
### TBL-05: `barcode_scanning_and_spe_records`
Stores persistent records for Barcode scanning and specimen search must respond in under 1.5 seconds. Needed by [F-005], [API-005].

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | UUIDv7 unique record identifier |
| `name` | TEXT | NOT NULL | Record descriptor / title |
| `status` | TEXT | NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending', 'completed', 'archived')) | Operational workflow status |
| `details` | TEXT | NOT NULL | Serialized structured parameters |
| `created_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | UTC creation timestamp |
| `updated_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | UTC last modified timestamp |
### TBL-06: `freezer_temperature_devi_records`
Stores persistent records for Freezer temperature deviation must not exceed 5 degrees Celsius. Needed by [F-006], [API-006].

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | UUIDv7 unique record identifier |
| `name` | TEXT | NOT NULL | Record descriptor / title |
| `status` | TEXT | NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending', 'completed', 'archived')) | Operational workflow status |
| `details` | TEXT | NOT NULL | Serialized structured parameters |
| `created_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | UTC creation timestamp |
| `updated_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | UTC last modified timestamp |
### TBL-07: `the_software_must_be_abl_records`
Stores persistent records for The software must be able to display a minimum of 6 colors on a high contrast background. Needed by [F-007], [API-007].

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | UUIDv7 unique record identifier |
| `name` | TEXT | NOT NULL | Record descriptor / title |
| `status` | TEXT | NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending', 'completed', 'archived')) | Operational workflow status |
| `details` | TEXT | NOT NULL | Serialized structured parameters |
| `created_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | UTC creation timestamp |
| `updated_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | UTC last modified timestamp |


---

## 2. Relationships
All feature tables maintain foreign key auditability to the local system session and execution audit logs.
`specimen_check_in_with_2_records` (1) <────── (N) operational audit logs.

---

## 3. Indexes
One per main query, each with the exact API endpoint and query path it serves:

| Index Name | Table | Columns | Serves |
|---|---|---|---|
| `idx_specimen_check_in_with_2_status_created` | `specimen_check_in_with_2_records` | `(status, created_at DESC)` | Fast indexed lookup and filtering for [API-001] [F-001] |
| `idx_cold_storage_temperature_status_created` | `cold_storage_temperature_records` | `(status, created_at DESC)` | Fast indexed lookup and filtering for [API-002] [F-002] |
| `idx_custodial_transfer_sign__status_created` | `custodial_transfer_sign__records` | `(status, created_at DESC)` | Fast indexed lookup and filtering for [API-003] [F-003] |
| `idx_pdf_csv_regulatory_inspe_status_created` | `pdf_csv_regulatory_inspe_records` | `(status, created_at DESC)` | Fast indexed lookup and filtering for [API-004] [F-004] |
| `idx_barcode_scanning_and_spe_status_created` | `barcode_scanning_and_spe_records` | `(status, created_at DESC)` | Fast indexed lookup and filtering for [API-005] [F-005] |
| `idx_freezer_temperature_devi_status_created` | `freezer_temperature_devi_records` | `(status, created_at DESC)` | Fast indexed lookup and filtering for [API-006] [F-006] |
| `idx_the_software_must_be_abl_status_created` | `the_software_must_be_abl_records` | `(status, created_at DESC)` | Fast indexed lookup and filtering for [API-007] [F-007] |

---

## 4. Access Rules & Permissions
Enforced by application service layer and local database connection boundaries [ADR-004]:

| Table | Read | Insert | Update | Delete | Enforced By |
|---|---|---|---|---|---|
| `specimen_check_in_with_2_records` | All Personas | Authorized Role | Manager / Lead | Disallowed (Audit Log) | Service Layer Auth Policy |
| `cold_storage_temperature_records` | All Personas | Authorized Role | Manager / Lead | Disallowed (Audit Log) | Service Layer Auth Policy |
| `custodial_transfer_sign__records` | All Personas | Authorized Role | Manager / Lead | Disallowed (Audit Log) | Service Layer Auth Policy |
| `pdf_csv_regulatory_inspe_records` | All Personas | Authorized Role | Manager / Lead | Disallowed (Audit Log) | Service Layer Auth Policy |
| `barcode_scanning_and_spe_records` | All Personas | Authorized Role | Manager / Lead | Disallowed (Audit Log) | Service Layer Auth Policy |
| `freezer_temperature_devi_records` | All Personas | Authorized Role | Manager / Lead | Disallowed (Audit Log) | Service Layer Auth Policy |
| `the_software_must_be_abl_records` | All Personas | Authorized Role | Manager / Lead | Disallowed (Audit Log) | Service Layer Auth Policy |

---

## 5. Growth and Retention
| Table | Rows Year 1 | Retention Policy | Source |
|---|---|---|---|
| `specimen_check_in_with_2_records` | ~3,000 records | Retained locally for regulatory audit duration [NFR-03] | [NFR-03] |
| `cold_storage_temperature_records` | ~3,000 records | Retained locally for regulatory audit duration [NFR-03] | [NFR-03] |
| `custodial_transfer_sign__records` | ~3,000 records | Retained locally for regulatory audit duration [NFR-03] | [NFR-03] |
| `pdf_csv_regulatory_inspe_records` | ~3,000 records | Retained locally for regulatory audit duration [NFR-03] | [NFR-03] |
| `barcode_scanning_and_spe_records` | ~3,000 records | Retained locally for regulatory audit duration [NFR-03] | [NFR-03] |
| `freezer_temperature_devi_records` | ~3,000 records | Retained locally for regulatory audit duration [NFR-03] | [NFR-03] |
| `the_software_must_be_abl_records` | ~3,000 records | Retained locally for regulatory audit duration [NFR-03] | [NFR-03] |

---

## 6. Seed Data
Initial testing data for preview environment:
- Realistic default records seeded for each table to enable immediate end-to-end walking skeleton verification.

---

## 7. Executable SQL DDL Migrations

```sql
-- Migration 001: Initial Schema for BioVault Lab
CREATE TABLE IF NOT EXISTS specimen_check_in_with_2_records (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending', 'completed', 'archived')),
    details TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_specimen_check_in_with_2_status_created ON specimen_check_in_with_2_records (status, created_at DESC);
CREATE TABLE IF NOT EXISTS cold_storage_temperature_records (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending', 'completed', 'archived')),
    details TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_cold_storage_temperature_status_created ON cold_storage_temperature_records (status, created_at DESC);
CREATE TABLE IF NOT EXISTS custodial_transfer_sign__records (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending', 'completed', 'archived')),
    details TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_custodial_transfer_sign__status_created ON custodial_transfer_sign__records (status, created_at DESC);
CREATE TABLE IF NOT EXISTS pdf_csv_regulatory_inspe_records (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending', 'completed', 'archived')),
    details TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_pdf_csv_regulatory_inspe_status_created ON pdf_csv_regulatory_inspe_records (status, created_at DESC);
CREATE TABLE IF NOT EXISTS barcode_scanning_and_spe_records (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending', 'completed', 'archived')),
    details TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_barcode_scanning_and_spe_status_created ON barcode_scanning_and_spe_records (status, created_at DESC);
CREATE TABLE IF NOT EXISTS freezer_temperature_devi_records (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending', 'completed', 'archived')),
    details TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_freezer_temperature_devi_status_created ON freezer_temperature_devi_records (status, created_at DESC);
CREATE TABLE IF NOT EXISTS the_software_must_be_abl_records (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending', 'completed', 'archived')),
    details TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_the_software_must_be_abl_status_created ON the_software_must_be_abl_records (status, created_at DESC);

```
