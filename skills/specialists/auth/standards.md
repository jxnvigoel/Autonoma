# Specialist Pack: Auth Standards

Source Grounding: Handbook Chapter 7.1.7, Chapter 12.1.4.

## 1. Password Hashing Specification
- Preferred: Argon2id (memory: 64MB, iterations: 3, parallelism: 1).
- Acceptable: bcrypt with cost factor ≥ 12.
- Forbidden: Plaintext, MD5, SHA-1, standard unsalted SHA-256.

## 2. Session Cookies Specification
- `Set-Cookie: session_id=<opaque-token>; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=604800`

## 3. Rate Limiting Specification
- Target: `/api/v1/auth/login`
- Limit: 5 requests per 60 seconds per IP.
- Penalty: HTTP 429 Problem Details with `Retry-After: 60`.

## 4. RBAC & Ownership Model
- SQL queries must enforce object tenant/owner scoping:
  ```sql
  SELECT * FROM documents WHERE id = :doc_id AND owner_id = :current_user_id;
  ```
