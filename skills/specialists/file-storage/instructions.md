# Specialist Pack: File Storage & Upload Security Instructions

Source Grounding: Virtual Office Handbook Chapter 12.1.4 (OWASP Security & Injection Defense), Chapter 23.5 (Sandbox & Path Boundaries).

## 1. Upload Validation and Magic-Byte Inspection
*Grounded in Handbook Chapter 12.1.4 (Input Validation & Safe Boundary Handling)*:
1. Never trust client-supplied `Content-Type` headers or file extensions alone.
2. Read initial file bytes (magic bytes / file signature) to verify the actual binary MIME type before storing.
3. Reject executable formats (`.exe`, `.sh`, `.bat`, `.php`, `.js`, `.py`, `.dll`) and disallowed MIME types with HTTP `415 Unsupported Media Type`.

## 2. File Size Limits and Streaming Rejection
*Explicit Non-Handbook Standard [EXPLICIT EXTENSION]*:
1. Enforce strict maximum file size limits (e.g. 10MB default, configurable by tenant/endpoint).
2. Measure bytes during streaming ingest; if the byte count exceeds the limit, immediately terminate the connection and return HTTP `413 Payload Too Large`. Never buffer unbounded files into server RAM.

## 3. Safe Storage Paths and Traversal Elimination
*Grounded in Handbook Chapter 23.5 ("Folder scope: always every path resolved and checked")*:
1. NEVER save an uploaded file directly under the user-supplied filename. User filenames can contain directory traversal attacks (`../`, `..\\`), null bytes, or dangerous shell characters.
2. Generate a random UUIDv4 for physical disk/object storage (e.g., `uploads/7f3b...12a.png`).
3. Retain the original filename sanitized only in metadata database columns.
4. Verify all resolved target storage paths reside strictly within the designated storage directory using `os.path.commonpath` or equivalent path resolution.

## 4. SHA-256 Integrity Checksums
*Explicit Non-Handbook Standard [EXPLICIT EXTENSION]*:
1. Calculate a SHA-256 cryptographic digest as bytes stream to storage.
2. Persist the checksum in the file record table.
3. Use the checksum for deduplication and tamper-evidence verification on retrieval.

## 5. Antivirus Scan Seam / Hook Point
*Explicit Non-Handbook Standard [EXPLICIT EXTENSION]*:
1. Implement a clear hook point / adapter interface for malware and virus scanning (e.g. ClamAV daemon or cloud scanner).
2. Quarantine any file flagged by the scanner before making it readable to other users or triggering background processing.
