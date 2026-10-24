# Specialist Pack: File Storage Standards

**Source Grounding**: Virtual Office Handbook Chapter 12.1.4, Chapter 23.5, Chapter 3.

## 1. Magic Bytes Reference Table
| Type | Extension | Initial Magic Bytes |
|---|---|---|
| PNG | `.png` | `89 50 4E 47 0D 0A 1A 0A` |
| JPEG | `.jpg`, `.jpeg` | `FF D8 FF` |
| PDF | `.pdf` | `25 50 44 46` (`%PDF`) |
| WebP | `.webp` | `52 49 46 46 ... 57 45 42 50` (`RIFF...WEBP`) |

- **Provenance**: Gary Kessler File Signatures Reference Table & ISO/IEC 15444 / RFC 2083
- **Source URL**: https://www.garykessler.net/library/file_sigs.html & https://www.rfc-editor.org/rfc/rfc2083.html
- **Version**: Reference Table 2024 | **Date**: 2024-02-18 | **Status**: VERIFIED

## 2. Object Storage REST API Specification (AWS S3)
- Direct pre-signed PUT/GET URLs, multipart uploads, and bucket ACLs adhere to AWS S3 REST API Specification.
- Standard HTTP status codes (200, 206 Partial Content, 403 Forbidden, 404 Not Found) per RFC 9110 (HTTP Semantics, obsoletes RFC 7231).
- **Provenance**: AWS S3 REST API Reference & RFC 9110
- **Source URL**: https://docs.aws.amazon.com/AmazonS3/latest/API/Welcome.html & https://www.rfc-editor.org/rfc/rfc9110.html
- **Version**: Amazon S3 API Version 2006-03-01 (Doc updated 2024) / RFC 9110 | **Date**: 2024-08-01 / 2022-06-01 | **Status**: VERIFIED

## 3. File Record Table Schema
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
- **Provenance**: Autonoma Architecture Team Reference DDL
- **Status**: [UNVERIFIED] (Internal schema standard for local file metadata; no RFC governs table layout)
