# Specialist Pack: File Storage Checklist

- [ ] **Magic Byte MIME Sniffing**: Initial file bytes verified against allowed MIME types. Header alone is never trusted.
- [ ] **Size Limit Enforced**: File size capped during ingest; payloads above limit rejected with HTTP 413.
- [ ] **UUID Storage Filenames**: Files stored under random UUIDs; original user filenames never used as disk paths.
- [ ] **Path Traversal Defense**: All target filepaths validated to remain strictly within storage root directory.
- [ ] **SHA-256 Checksums**: Checksum calculated on upload and stored with record for tamper verification.
- [ ] **Virus Scan Seam**: Scanner hook point implemented with quarantine status for suspect uploads.
- [ ] **No Public Execution**: Upload directory permissions and web server config forbid direct script execution.
