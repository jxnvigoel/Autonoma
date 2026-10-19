# Data Schema: DocuPulse Reader

**Database**: Embedded Relational SQLite [ADR-003]  
**Query Layer**: Direct Parametrized SQL with B-Tree Index Optimization [ADR-003]  
**Migrations**: Managed Local DDL Migrations in `data/migrations/`  

---

## 1. Tables

### TBL-01: `users`
Stores authenticated local application users and operational roles. Needed by [P-01], [P-02], [ADR-004].

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | UUIDv7 unique record identifier |
| `username` | TEXT | NOT NULL UNIQUE | User account name |
| `role` | TEXT | NOT NULL CHECK (role IN ('operator', 'supervisor', 'admin')) | Authorization role tier |
| `full_name` | TEXT | NOT NULL | User display name |
| `created_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | UTC creation timestamp |
### TBL-02: `allow_users_search_items`
Stores persistent records for Allow users to search documents by tags. Needed by [F-001], [API-001].

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | UUIDv7 unique record identifier |
| `title` | TEXT | NOT NULL | Record title / descriptor |
| `category` | TEXT | NOT NULL DEFAULT 'standard' | Operational classification |
| `status` | TEXT | NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending', 'completed', 'archived')) | Operational workflow status |
| `assigned_user_id` | TEXT | REFERENCES users(id) | Responsible operator [P-01] |
| `file_format` | TEXT | NOT NULL DEFAULT 'pdf' | Domain attribute for [F-001] |
| `file_size_bytes` | INTEGER | NOT NULL DEFAULT 0 | Domain attribute for [F-001] |
| `created_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | UTC creation timestamp |
| `updated_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | UTC last modified timestamp |
### TBL-03: `document_reader_items`
Stores persistent records for Enable users to organize snippets in a smart snippet organizer. Needed by [F-002], [API-002].

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | UUIDv7 unique record identifier |
| `title` | TEXT | NOT NULL | Record title / descriptor |
| `category` | TEXT | NOT NULL DEFAULT 'standard' | Operational classification |
| `status` | TEXT | NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending', 'completed', 'archived')) | Operational workflow status |
| `assigned_user_id` | TEXT | REFERENCES users(id) | Responsible operator [P-01] |
| `confidence_score` | REAL | NOT NULL DEFAULT 1.0 | Domain attribute for [F-002] |
| `raw_payload` | TEXT |  | Domain attribute for [F-002] |
| `created_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | UTC creation timestamp |
| `updated_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | UTC last modified timestamp |
### TBL-04: `citations_items`
Stores persistent records for Support local citation export. Needed by [F-003], [API-003].

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | UUIDv7 unique record identifier |
| `title` | TEXT | NOT NULL | Record title / descriptor |
| `category` | TEXT | NOT NULL DEFAULT 'standard' | Operational classification |
| `status` | TEXT | NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending', 'completed', 'archived')) | Operational workflow status |
| `assigned_user_id` | TEXT | REFERENCES users(id) | Responsible operator [P-01] |
| `reference_key` | TEXT | NOT NULL DEFAULT '' | Domain attribute for [F-003] |
| `source_system` | TEXT | NOT NULL DEFAULT 'local' | Domain attribute for [F-003] |
| `created_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | UTC creation timestamp |
| `updated_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | UTC last modified timestamp |
### TBL-05: `provide_user_friendly_items`
Stores persistent records for Provide a user-friendly interface for managing documents. Needed by [F-004], [API-004].

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | UUIDv7 unique record identifier |
| `title` | TEXT | NOT NULL | Record title / descriptor |
| `category` | TEXT | NOT NULL DEFAULT 'standard' | Operational classification |
| `status` | TEXT | NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending', 'completed', 'archived')) | Operational workflow status |
| `assigned_user_id` | TEXT | REFERENCES users(id) | Responsible operator [P-01] |
| `export_format` | TEXT | NOT NULL DEFAULT 'json' | Domain attribute for [F-004] |
| `checksum_sha256` | TEXT | NOT NULL DEFAULT '' | Domain attribute for [F-004] |
| `created_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | UTC creation timestamp |
| `updated_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | UTC last modified timestamp |


---

## 2. Relationships
All feature tables maintain foreign key integrity to the `users` table and operational audit logs.
`users` (1) <────── (N) `allow_users_search_items`.

---

## 3. Indexes
One per main query, each with the exact API endpoint and query path it serves:

| Index Name | Table | Columns | Serves |
|---|---|---|---|
| `idx_users_role` | `users` | `(role)` | Fast role-based permission lookup [ADR-004] |
| `idx_allow_users_search_status_time` | `allow_users_search_items` | `(status, created_at DESC)` | Fast indexed lookup and filtering for [API-001] [F-001] |
| `idx_document_reader_status_time` | `document_reader_items` | `(status, created_at DESC)` | Fast indexed lookup and filtering for [API-002] [F-002] |
| `idx_citations_status_time` | `citations_items` | `(status, created_at DESC)` | Fast indexed lookup and filtering for [API-003] [F-003] |
| `idx_provide_user_friendly_status_time` | `provide_user_friendly_items` | `(status, created_at DESC)` | Fast indexed lookup and filtering for [API-004] [F-004] |

---

## 4. Access Rules & Permissions
Enforced by application service layer and local database connection boundaries [ADR-004]:

| Table | Read | Insert | Update | Delete | Enforced By |
|---|---|---|---|---|---|
| `users` | All Personas | System Admin | System Admin | Disallowed | Service Layer Auth Policy |
| `allow_users_search_items` | All Personas | Operator [P-01] | Supervisor [P-02] | Disallowed (Audit Log) | Service Layer Auth Policy |
| `document_reader_items` | All Personas | Operator [P-01] | Supervisor [P-02] | Disallowed (Audit Log) | Service Layer Auth Policy |
| `citations_items` | All Personas | Operator [P-01] | Supervisor [P-02] | Disallowed (Audit Log) | Service Layer Auth Policy |
| `provide_user_friendly_items` | All Personas | Operator [P-01] | Supervisor [P-02] | Disallowed (Audit Log) | Service Layer Auth Policy |

---

## 5. Growth and Retention
| Table | Rows Year 1 | Retention Policy | Source |
|---|---|---|---|
| `users` | ~50 records | Local user roster [Q-002] | [Q-002] |
| `allow_users_search_items` | Scaled for operational volume | Retained locally for operational audit duration [NFR-03] | [NFR-03] |
| `document_reader_items` | Scaled for operational volume | Retained locally for operational audit duration [NFR-03] | [NFR-03] |
| `citations_items` | Scaled for operational volume | Retained locally for operational audit duration [NFR-03] | [NFR-03] |
| `provide_user_friendly_items` | Scaled for operational volume | Retained locally for operational audit duration [NFR-03] | [NFR-03] |

---

## 6. Seed Data
Initial testing data for preview environment:
- Realistic default records seeded for each table to enable immediate end-to-end walking skeleton verification.

---

## 7. Executable SQL DDL Migrations

```sql
-- Migration 001: Initial Schema for DocuPulse Reader
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK (role IN ('operator', 'supervisor', 'admin')),
    full_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_users_role ON users (role);
CREATE TABLE IF NOT EXISTS allow_users_search_items (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'standard',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending', 'completed', 'archived')),
    assigned_user_id TEXT REFERENCES users(id),
    file_format TEXT NOT NULL DEFAULT 'pdf',
    file_size_bytes INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_allow_users_search_status_time ON allow_users_search_items (status, created_at DESC);
CREATE TABLE IF NOT EXISTS document_reader_items (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'standard',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending', 'completed', 'archived')),
    assigned_user_id TEXT REFERENCES users(id),
    confidence_score REAL NOT NULL DEFAULT 1.0,
    raw_payload TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_document_reader_status_time ON document_reader_items (status, created_at DESC);
CREATE TABLE IF NOT EXISTS citations_items (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'standard',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending', 'completed', 'archived')),
    assigned_user_id TEXT REFERENCES users(id),
    reference_key TEXT NOT NULL DEFAULT '',
    source_system TEXT NOT NULL DEFAULT 'local',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_citations_status_time ON citations_items (status, created_at DESC);
CREATE TABLE IF NOT EXISTS provide_user_friendly_items (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'standard',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending', 'completed', 'archived')),
    assigned_user_id TEXT REFERENCES users(id),
    export_format TEXT NOT NULL DEFAULT 'json',
    checksum_sha256 TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_provide_user_friendly_status_time ON provide_user_friendly_items (status, created_at DESC);

```
