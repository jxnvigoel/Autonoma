"""
Reference Secure File Storage Service Implementation
Grounded in Handbook Chapter 12.1.4 and Chapter 23.5.
"""
import os
import uuid
import hashlib
from typing import Tuple, Optional

ALLOWED_MAGIC_SIGNATURES = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"%PDF": "application/pdf",
}

def validate_magic_bytes(header_bytes: bytes) -> Optional[str]:
    """Inspects initial file bytes against known signatures."""
    for sig, mime in ALLOWED_MAGIC_SIGNATURES.items():
        if header_bytes.startswith(sig):
            return mime
    return None

def resolve_safe_storage_path(base_dir: str, file_ext: str) -> Tuple[str, str]:
    """Generates an unguessable UUID path and verifies path confinement."""
    safe_id = str(uuid.uuid4())
    filename = f"{safe_id}{file_ext}"
    target_path = os.path.abspath(os.path.join(base_dir, filename))
    base_resolved = os.path.abspath(base_dir)

    if os.path.commonpath([target_path, base_resolved]) != base_resolved:
        raise ValueError("Path traversal attempt detected")

    return safe_id, target_path
