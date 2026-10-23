"""
Reference Payment & Webhook Handler Implementation
Grounded in Handbook Chapter 7.1.6, 12.1.3, 12.1.4, 19.4, and AC-012.
"""
import hmac
import hashlib
import time
import json
from typing import Dict, Any, Tuple, Optional

def verify_webhook_signature(
    raw_payload: bytes,
    signature_header: str,
    webhook_secret: str,
    max_drift_seconds: int = 300
) -> Tuple[bool, str]:
    """
    Cryptographically verifies webhook signature with replay protection.
    Header format: t=<timestamp>,v1=<signature>
    """
    if not signature_header or not webhook_secret:
        return False, "Missing signature header or webhook secret"

    parts = dict(item.split("=", 1) for item in signature_header.split(",") if "=" in item)
    timestamp_str = parts.get("t")
    received_signature = parts.get("v1")

    if not timestamp_str or not received_signature:
        return False, "Malformed signature header components"

    try:
        event_time = int(timestamp_str)
    except ValueError:
        return False, "Invalid timestamp format in header"

    current_time = int(time.time())
    if abs(current_time - event_time) > max_drift_seconds:
        return False, f"Webhook timestamp drift ({abs(current_time - event_time)}s) exceeds {max_drift_seconds}s replay tolerance"

    signed_payload = f"{timestamp_str}.".encode("utf-8") + raw_payload
    expected_sig = hmac.new(
        webhook_secret.encode("utf-8"),
        signed_payload,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, received_signature):
        return False, "Signature mismatch"

    return True, "Valid"
