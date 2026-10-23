# Specialist Pack: Authentication & Authorization Checklist

- [ ] **Argon2id/bcrypt Hashing**: All passwords hashed before database insert. Zero plaintext.
- [ ] **Cookie Security**: Session cookies set with `HttpOnly`, `Secure`, and `SameSite`.
- [ ] **Rate Limiting**: Login endpoint rejects more than 5 failed attempts per IP/account with HTTP 429.
- [ ] **Safe Error Messages**: Login failures return generic "Invalid credentials" error.
- [ ] **Secure Reset Tokens**: Password reset tokens generated via cryptographically secure RNG and hashed in DB.
- [ ] **Reset Expiry**: Password reset tokens expire in ≤ 15 minutes and invalidate upon single use.
- [ ] **Server-Side Ownership (WHERE id=$1 AND owner_id=$2)**: Every resource query and update checks authenticated ownership.
- [ ] **Role Authorization**: Admin and elevated endpoints check role permissions at boundary.
- [ ] **Session Expiry**: Sessions expire after inactivity and are invalidated on logout.
