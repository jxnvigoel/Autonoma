# Specialist Pack: Auth Standards

**Source Grounding**: Virtual Office Handbook Chapter 7.1.7, Chapter 12.1.4, Chapter 3.

## 1. Password Hashing Specification
- Preferred: Argon2id (memory: 64MB, iterations: 3, parallelism: 1).
- Acceptable: bcrypt with cost factor ≥ 12.
- Forbidden: Plaintext, MD5, SHA-1, standard unsalted SHA-256.
- **Provenance**: RFC 9106 (Argon2 Password Hashing) & OWASP Password Storage Cheat Sheet
- **Source URL**: https://www.rfc-editor.org/rfc/rfc9106.html & https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- **Version**: RFC 9106 / OWASP 2024 | **Date**: 2021-09-01 / 2024-01-15 | **Status**: VERIFIED

## 2. Digital Identity & Authentication Lifecycle (NIST SP 800-63B)
- Password length minimum: ≥ 8 characters; rate limiting and credential stuffing protection required.
- Do not impose arbitrary composition rules (special characters/uppercase mandatory) or mandatory periodic resets without evidence of compromise.
- **Provenance**: NIST SP 800-63B (Revision 4, Digital Identity Guidelines: Authentication and Lifecycle Management)
- **Source URL**: https://pages.nist.gov/800-63-4/sp800-63b.html
- **Version**: NIST SP 800-63B Rev. 4 (2PD) | **Date**: 2024-08-20 | **Status**: VERIFIED

## 3. HTTP Authentication Semantics (RFC 9110)
- HTTP Authentication headers (`Authorization: Bearer <token>`, `WWW-Authenticate: Bearer error="invalid_token"`) must adhere to RFC 9110 Section 11 (obsoletes RFC 7235 & RFC 7231 authentication definitions).
- **Provenance**: RFC 9110 (HTTP Semantics, Section 11 Authentication)
- **Source URL**: https://www.rfc-editor.org/rfc/rfc9110.html#section-11
- **Version**: RFC 9110 | **Date**: 2022-06-01 | **Status**: VERIFIED

## 4. Session Cookies Specification
- `Set-Cookie: session_id=<opaque-token>; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=604800`
- **Provenance**: RFC 6265bis (Cookies: HTTP State Management Mechanism) & OWASP Session Management Cheat Sheet
- **Source URL**: https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-rfc6265bis & https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- **Version**: RFC 6265bis draft-14 | **Date**: 2024-04-05 | **Status**: VERIFIED

## 5. Rate Limiting Specification
- Target: `/api/v1/auth/login`
- Limit: 5 requests per 60 seconds per IP.
- Penalty: HTTP 429 Problem Details with `Retry-After: 60`.
- **Provenance**: Autonoma Operations Security Heuristic
- **Status**: [UNVERIFIED] (Internal heuristic limit; threshold is an operational policy rather than an RFC standard)

## 6. RBAC & Ownership Model
- SQL queries must enforce object tenant/owner scoping:
  ```sql
  SELECT * FROM documents WHERE id = :doc_id AND owner_id = :current_user_id;
  ```
- **Provenance**: OWASP Top 10:2021 A01 (Broken Access Control)
- **Source URL**: https://owasp.org/Top10/A01_2021-Broken_Access_Control/
- **Version**: OWASP Top 10:2021 | **Date**: 2021-10-01 | **Status**: VERIFIED
