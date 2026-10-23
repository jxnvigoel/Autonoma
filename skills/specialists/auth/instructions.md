# Specialist Pack: Authentication & Authorization Instructions

Source Grounding: Virtual Office Handbook Chapter 7.1.7 (Security Architecture), Chapter 12.1.1 (Request Handling), Chapter 12.1.4 (OWASP Top 10 in Practice).

## 1. Password Hashing and Storage
*Grounded in Handbook Chapter 7.1.7 & 12.1.4*:
1. Passwords MUST be hashed using modern adaptive hashing algorithms: `Argon2id` (preferred) or `bcrypt` (work factor ≥ 12) with unique cryptographic salts.
2. Zero plaintext passwords in memory longer than necessary, zero plaintext in database columns, and zero in logs or audit records.
3. MD5, SHA-1, SHA-256 without salt/stretching, or DES are strictly forbidden for passwords.

## 2. Session and Token Management
*Grounded in Handbook Chapter 7.1.7*:
1. Web clients: Sessions must be stored in cookies marked `HttpOnly`, `Secure`, and `SameSite=Strict` (or `Lax` where cross-site navigation requires it). Cookie must never be readable via client-side JavaScript (`document.cookie`).
2. API / Mobile clients: Short-lived access tokens (JWT expiration ≤ 15 minutes) paired with rotating refresh tokens stored in database with revocation support.
3. Session Expiry [EXPLICIT EXTENSION beyond handbook text]:
   - Idle timeout: 120 minutes (2 hours).
   - Absolute timeout: 7 days.
   - Immediate server-side invalidation upon logout or password reset.

## 3. Rate Limiting and Lockout
*Grounded in Handbook Chapter 12.1.4 ("authentication failures: rate limits, lockout") & Chapter 19.4*:
1. Public auth endpoints (`/login`, `/register`, `/forgot-password`) must implement rate limiting (e.g., token bucket or sliding window).
2. Maximum 5 failed attempts per 15 minutes per IP/account before temporary lockout (HTTP `429 Too Many Requests`).
3. Return generic error messages on login failure ("Invalid email or password") to prevent user enumeration.

## 4. Password Reset Lifecycle
*Explicit Non-Handbook Standard [EXPLICIT EXTENSION]*:
1. Generate cryptographically strong random tokens using `secrets.token_urlsafe(32)`.
2. Store only the SHA-256 hash of the reset token in the database, with user ID, created timestamp, and 15-minute expiration time.
3. Invalidate previous tokens upon issuing a new token. Mark token as consumed immediately upon successful password change.

## 5. Server-Side Role and Ownership Checks (RBAC)
*Grounded in Handbook Chapter 12.1.4 ("Broken access control: check ownership on every object: WHERE id = $1 AND owner_id = $2")*:
1. Never trust client-asserted roles or user IDs from headers or request bodies. Extract identity exclusively from verified session/JWT claims.
2. For every protected object modification or query, enforce ownership checks: `SELECT ... WHERE id = $1 AND owner_id = $2`.
3. Administrative routes must enforce role checks (`user.role == 'admin'`) at the route boundary before executing any queries.
