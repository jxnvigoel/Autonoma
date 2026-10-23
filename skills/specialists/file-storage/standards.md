# Specialist Pack: File Storage Standards

Source Grounding: Handbook Chapter 12.1.4, Chapter 23.5.

## 1. Magic Bytes Reference Table
| Type | Extension | Initial Magic Bytes |
|---|---|---|
| PNG | `.png` | `89 50 4E 47 0D 0A 1A 0A` |
| JPEG | `.jpg`, `.jpeg` | `FF D8 FF` |
| PDF | `.pdf` | `25 50 44 46` (`%PDF`) |
| WebP | `.webp` | `52 49 46 46 ... 57 45 42 50` (`RIFF...WEBP`) |

## 2. File Record Table Schema
```sql
CREATE TABLE IF NOT EXISTS stored_files (
    id TEXT PRIMARY KEY, -- UUIDv4
    storage_path TEXT NOT NULL UNIQUE,
    original_filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    sha256_checksum TEXT NOT NULL,
    scan_status TEXT NOT NULL DEFAULT 'clean' CHECK(scan_status IN ('pending', 'clean', 'infected', 'quarantined')),
    owner_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_files_checksum ON stored_files(sha256_checksum);
CREATE INDEX IF NOT EXISTS idx_files_owner ON stored_files(owner_id);
```
