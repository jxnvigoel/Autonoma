"""
Reference Authentication & Session Management Module
Grounded in Handbook Chapter 7.1.7 and 12.1.4.
"""
import os
import secrets
import hashlib
from typing import Optional, Dict, Any

try:
    import bcrypt
    def hash_password(password: str) -> str:
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
except ImportError:
    # Fallback to PBKDF2 HMAC SHA-256 with 200,000 rounds if bcrypt not installed
    def hash_password(password: str) -> str:
        salt = secrets.token_hex(16)
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200000)
        return f"pbkdf2:sha256:200000${salt}${key.hex()}"

    def verify_password(plain_password: str, hashed_password: str) -> bool:
        try:
            _, algo, iters, salt, key = hashed_password.split("$")
            computed = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), int(iters))
            return secrets.compare_digest(computed.hex(), key)
        except Exception:
            return False

def generate_reset_token() -> Tuple[str, str]:
    """Generates a secure random reset token and its database storage hash."""
    raw_token = secrets.token_urlsafe(32)
    db_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    return raw_token, db_hash
