# Data Schema: SiteAudit Pro

**Database**: Embedded Relational SQLite [ADR-003]  
**Query Layer**: Direct Parametrized SQL with Index Optimization [ADR-003]  
**Migrations**: Managed Local DDL Migrations in `data/migrations/`  

---

## 1. Tables

### TBL-01: `deficiencies`
Stores site inspection deficiency records, severity tags, and photo references. Needed by [F-001], [API-001], [API-002].

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | UUIDv7 sortable unique identifier |
| `location` | TEXT | NOT NULL | Physical site area (e.g. Basement Footing B-2) |
| `severity` | TEXT | NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')) | MoSCoW hazard severity classification |
| `category` | TEXT | NOT NULL | Deficiency taxonomy classification |
| `notes` | TEXT | NOT NULL | Inspector field observation narrative |
| `photo_ref` | TEXT | NULL | Local relative photo storage path |
| `status` | TEXT | NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'resolved', 'certified')) | Workflow status |
| `created_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | UTC creation timestamp |
| `updated_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | UTC last modified timestamp |

### TBL-02: `punchlists`
Stores compiled punch-list export history and audit tracking records. Needed by [F-002], [API-003].

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | UUIDv7 export tracking identifier |
| `format` | TEXT | NOT NULL CHECK (format IN ('csv', 'text')) | Target file format |
| `records_count` | INTEGER | NOT NULL CHECK (records_count >= 0) | Number of deficiencies included |
| `output_path` | TEXT | NOT NULL | Local filesystem destination |
| `exported_at` | TEXT | NOT NULL DEFAULT (datetime('now')) | UTC timestamp of export event |

---

## 2. Relationships
`deficiencies` (1) <────── (N) `punchlist_items` (M:N junction for certified export tracking)

---

## 3. Indexes
One per main query, each with the exact API endpoint and query path it serves:

| Index Name | Table | Columns | Serves |
|---|---|---|---|
| `idx_deficiencies_status_severity` | `deficiencies` | `(status, severity)` | Fast filtered query for active open hazards [API-002] |
| `idx_deficiencies_created_at` | `deficiencies` | `(created_at DESC)` | Chronological punch-list compilation [API-003] |
| `idx_deficiencies_location` | `deficiencies` | `(location)` | Spatial inspection search queries [API-002] |

---

## 4. Access Rules & Permissions
Enforced by application service layer and local database connection boundaries [ADR-004]:

| Table | Read | Insert | Update | Delete | Enforced By |
|---|---|---|---|---|---|
| `deficiencies` | Inspector, Engineer | Inspector, Engineer | Inspector, Engineer | Engineer Only | Service Layer Auth Policy |
| `punchlists` | Inspector, Engineer | Engineer, Inspector | Disallowed (Append-Only) | Disallowed (Audit Log) | Database Triggers |

---

## 5. Growth and Retention
| Table | Rows Year 1 | Retention Policy | Source |
|---|---|---|---|
| `deficiencies` | ~3,000 records | Retained locally for project warranty duration (minimum 3 years) | [NFR-03] |
| `punchlists` | ~250 export events | Permanent local audit trail | [Q-005] |

---

## 6. Seed Data
Initial testing data for preview environment:
- 10 standard civil safety checklist items (shoring, concrete curing, fall protection, electrical clearance).
- 3 sample deficiency tags (1 critical basement water intrusion, 1 medium rebar spacing variance, 1 low housekeeping flag).

---

## 7. Executable SQL DDL Migrations

```sql
-- Migration 001: Initial Schema for SiteAudit Pro
CREATE TABLE IF NOT EXISTS deficiencies (
    id TEXT PRIMARY KEY,
    location TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    category TEXT NOT NULL,
    notes TEXT NOT NULL,
    photo_ref TEXT,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'resolved', 'certified')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_deficiencies_status_severity ON deficiencies (status, severity);
CREATE INDEX IF NOT EXISTS idx_deficiencies_created_at ON deficiencies (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_deficiencies_location ON deficiencies (location);

CREATE TABLE IF NOT EXISTS punchlists (
    id TEXT PRIMARY KEY,
    format TEXT NOT NULL CHECK (format IN ('csv', 'text')),
    records_count INTEGER NOT NULL CHECK (records_count >= 0),
    output_path TEXT NOT NULL,
    exported_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```
