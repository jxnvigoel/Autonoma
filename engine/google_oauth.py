"""
Sign in with Google (OAuth 2.0 for installed apps, authorization code + PKCE, loopback redirect).

Needs a Google Cloud OAuth client of type "Desktop app": set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET
in .env. Google sends the browser back to this engine at http://127.0.0.1:<engine port>/auth/google/callback;
the engine exchanges the code, asks Google who the user is (verified email only), and hands the app a
local session. This is the only part of accounts that talks to an outside service, and only when used.
"""

import os
import time
import base64
import hashlib
import secrets
import threading
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv
from fastapi import HTTPException

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
PENDING_TTL_S = 600

_pending: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()


def _config() -> Dict[str, str]:
    load_dotenv(override=True)
    port = os.environ.get("ENGINE_PORT", "8765")
    return {"client_id": os.environ.get("GOOGLE_CLIENT_ID", "").strip(),
            "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", "").strip(),
            "redirect_uri": f"http://127.0.0.1:{port}/auth/google/callback"}


def is_configured() -> bool:
    cfg = _config()
    return bool(cfg["client_id"] and cfg["client_secret"])


def _prune() -> None:
    now = time.time()
    for state in [k for k, v in _pending.items() if now - v["created"] > PENDING_TTL_S]:
        _pending.pop(state, None)


def start() -> Dict[str, str]:
    if not is_configured():
        raise HTTPException(status_code=503, detail=(
            "Google sign-in is not set up: create an OAuth client of type 'Desktop app' in Google Cloud Console "
            "and add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to .env"))
    cfg = _config()
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    with _lock:
        _prune()
        _pending[state] = {"verifier": verifier, "created": time.time(), "result": None, "error": None}
    url = AUTH_URL + "?" + urlencode({
        "client_id": cfg["client_id"], "redirect_uri": cfg["redirect_uri"], "response_type": "code",
        "scope": "openid email profile", "state": state, "code_challenge": challenge,
        "code_challenge_method": "S256", "prompt": "select_account"})
    return {"auth_url": url, "state": state}


def finish(code: Optional[str], state: Optional[str], error: Optional[str], create_session) -> str:
    """Handles Google's redirect. Returns the HTML shown in the browser tab."""
    with _lock:
        entry = _pending.get(state or "")
    if entry is None:
        return _page("This sign-in link has expired. Go back to Autonoma and try again.")
    if error or not code:
        entry["error"] = f"Google sign-in was cancelled ({error or 'no code'})"
        return _page("Sign-in was cancelled. You can close this tab.")
    cfg = _config()
    try:
        tok = requests.post(TOKEN_URL, data={
            "code": code, "client_id": cfg["client_id"], "client_secret": cfg["client_secret"],
            "redirect_uri": cfg["redirect_uri"], "grant_type": "authorization_code",
            "code_verifier": entry["verifier"]}, timeout=20)
        tok.raise_for_status()
        info = requests.get(USERINFO_URL, headers={"Authorization": f"Bearer {tok.json()['access_token']}"}, timeout=20)
        info.raise_for_status()
        profile = info.json()
    except (requests.RequestException, KeyError, ValueError) as e:
        entry["error"] = f"Could not complete Google sign-in: {e}"
        return _page("Google sign-in failed. Go back to Autonoma for details.")
    if not profile.get("email_verified"):
        entry["error"] = "Your Google email address is not verified"
        return _page("Your Google email is not verified, so it cannot be used to sign in.")
    entry["result"] = create_session(profile["sub"], profile["email"], profile.get("name", ""))
    return _page("You are signed in. You can close this tab and return to Autonoma.")


def result(state: str) -> Dict[str, Any]:
    """Polled by the app: pending, done (with the local session), or error."""
    with _lock:
        entry = _pending.get(state)
        if entry is None:
            raise HTTPException(status_code=404, detail="Unknown or expired sign-in attempt")
        if entry["error"]:
            _pending.pop(state, None)
            return {"status": "error", "detail": entry["error"]}
        if entry["result"] is None:
            return {"status": "pending"}
        _pending.pop(state, None)
        return {"status": "done", **entry["result"]}


def _page(message: str) -> str:
    return ("<!doctype html><html><head><meta charset='utf-8'><title>Autonoma sign-in</title></head>"
            "<body style='font-family:system-ui;padding:48px;text-align:center'>"
            f"<h2>Autonoma</h2><p>{message}</p></body></html>")
