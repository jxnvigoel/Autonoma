"""
Local user accounts: sign up, log in, and per-user projects.

Everything is stored in data/office.db on this machine. Passwords are salted PBKDF2-HMAC-SHA256
hashes compared in constant time; five wrong passwords lock the account for 15 minutes.
Each project has one owner; the project list and project detail only serve the owner.
The first account created on an install takes ownership of the projects that already exist,
so work done before accounts existed is not lost.
"""

import os
import re
import hmac
import uuid
import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(PROJECT_ROOT, "data", "office.db")
DATA_PROJECTS_DIR = os.path.join(PROJECT_ROOT, "data", "projects")

PBKDF2_ITERATIONS = 200_000
SESSION_DAYS = 30
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _conn(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_auth_db(db_path: Optional[str] = None) -> None:
    conn = _conn(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                failed_logins INTEGER NOT NULL DEFAULT 0,
                locked_until TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS auth_sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id),
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id);
            CREATE TABLE IF NOT EXISTS project_owners (
                project_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id),
                assigned_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_project_owners_user ON project_owners(user_id);
            """
        )
        cols = {r[1] for r in conn.execute("PRAGMA table_info(users)")}
        for col, ddl in (("title", "TEXT NOT NULL DEFAULT ''"), ("organization", "TEXT NOT NULL DEFAULT ''"),
                         ("google_sub", "TEXT"), ("auth_method", "TEXT NOT NULL DEFAULT 'password'")):
            if col not in cols:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} {ddl}")
        conn.commit()
    finally:
        conn.close()


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS).hex()


def _public(row: sqlite3.Row) -> Dict[str, Any]:
    keys = row.keys()
    return {"id": row["id"], "email": row["email"], "name": row["name"], "created_at": row["created_at"],
            "title": row["title"] if "title" in keys else "", "organization": row["organization"] if "organization" in keys else "",
            "auth_method": row["auth_method"] if "auth_method" in keys else "password"}


def _new_session(conn: sqlite3.Connection, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    conn.execute("INSERT INTO auth_sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                 (token, user_id, _now().isoformat(), (_now() + timedelta(days=SESSION_DAYS)).isoformat()))
    return token


def users_exist(db_path: Optional[str] = None) -> bool:
    init_auth_db(db_path)
    conn = _conn(db_path)
    try:
        return conn.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None
    finally:
        conn.close()


def signup(name: str, email: str, password: str, db_path: Optional[str] = None,
           projects_dir: Optional[str] = None) -> Dict[str, Any]:
    init_auth_db(db_path)
    name, email = (name or "").strip(), (email or "").strip().lower()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    if len(password or "") < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    conn = _conn(db_path)
    try:
        if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            raise HTTPException(status_code=409, detail="An account with this email already exists; log in instead")
        first_account = conn.execute("SELECT 1 FROM users LIMIT 1").fetchone() is None
        user_id, salt = str(uuid.uuid4()), secrets.token_hex(16)
        conn.execute("INSERT INTO users (id, email, name, password_hash, salt, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                     (user_id, email, name, _hash(password, salt), salt, _now().isoformat()))
        claimed: List[str] = []
        if first_account:
            claimed = _claim_unowned_projects(conn, user_id, projects_dir or DATA_PROJECTS_DIR)
        token = _new_session(conn, user_id)
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return {"token": token, "user": _public(row), "claimed_existing_projects": claimed}
    finally:
        conn.close()


def _claim_unowned_projects(conn: sqlite3.Connection, user_id: str, projects_dir: str) -> List[str]:
    """Projects created before accounts existed go to the first account on this install."""
    if not os.path.isdir(projects_dir):
        return []
    owned = {r["project_id"] for r in conn.execute("SELECT project_id FROM project_owners")}
    claimed = []
    for pid in sorted(os.listdir(projects_dir)):
        if os.path.isfile(os.path.join(projects_dir, pid, "intake.json")) and pid not in owned:
            conn.execute("INSERT INTO project_owners (project_id, user_id, assigned_at) VALUES (?, ?, ?)",
                         (pid, user_id, _now().isoformat()))
            claimed.append(pid)
    return claimed


def login(email: str, password: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    init_auth_db(db_path)
    email = (email or "").strip().lower()
    conn = _conn(db_path)
    try:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if row is None:
            raise HTTPException(status_code=401, detail="Wrong email or password")
        if "auth_method" in row.keys() and row["auth_method"] == "google":
            raise HTTPException(status_code=400, detail="This account signs in with Google; use Continue with Google")
        if row["locked_until"] and datetime.fromisoformat(row["locked_until"]) > _now():
            raise HTTPException(status_code=423, detail="Too many wrong passwords; try again in a few minutes")
        if not hmac.compare_digest(row["password_hash"], _hash(password or "", row["salt"])):
            failed = row["failed_logins"] + 1
            locked = (_now() + timedelta(minutes=LOCKOUT_MINUTES)).isoformat() if failed >= MAX_FAILED_LOGINS else None
            conn.execute("UPDATE users SET failed_logins = ?, locked_until = ? WHERE id = ?",
                         (0 if locked else failed, locked, row["id"]))
            conn.commit()
            raise HTTPException(status_code=401, detail="Wrong email or password")
        conn.execute("UPDATE users SET failed_logins = 0, locked_until = NULL WHERE id = ?", (row["id"],))
        token = _new_session(conn, row["id"])
        conn.commit()
        return {"token": token, "user": _public(row)}
    finally:
        conn.close()


def user_for_token(token: Optional[str], db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    init_auth_db(db_path)
    conn = _conn(db_path)
    try:
        row = conn.execute("SELECT u.*, s.expires_at FROM auth_sessions s JOIN users u ON u.id = s.user_id "
                           "WHERE s.token = ?", (token,)).fetchone()
        if row is None or datetime.fromisoformat(row["expires_at"]) <= _now():
            return None
        return _public(row)
    finally:
        conn.close()


def logout(token: Optional[str], db_path: Optional[str] = None) -> None:
    if not token:
        return
    init_auth_db(db_path)
    conn = _conn(db_path)
    try:
        conn.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
        conn.commit()
    finally:
        conn.close()


def token_from_header(authorization: Optional[str]) -> Optional[str]:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return None


def require_user(authorization: Optional[str], db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    The signed-in user for this request. Before any account exists the app works as before (returns None);
    once accounts exist, a valid session is required.
    """
    user = user_for_token(token_from_header(authorization), db_path)
    if user is None and users_exist(db_path):
        raise HTTPException(status_code=401, detail="Please log in")
    return user


def assign_project(project_id: str, user_id: str, db_path: Optional[str] = None) -> None:
    init_auth_db(db_path)
    conn = _conn(db_path)
    try:
        conn.execute("INSERT OR IGNORE INTO project_owners (project_id, user_id, assigned_at) VALUES (?, ?, ?)",
                     (project_id, user_id, _now().isoformat()))
        conn.commit()
    finally:
        conn.close()


def projects_of(user_id: str, db_path: Optional[str] = None) -> List[str]:
    init_auth_db(db_path)
    conn = _conn(db_path)
    try:
        return [r["project_id"] for r in conn.execute("SELECT project_id FROM project_owners WHERE user_id = ?",
                                                      (user_id,))]
    finally:
        conn.close()


def require_owner(project_id: str, user: Optional[Dict[str, Any]], db_path: Optional[str] = None) -> None:
    """Only the owner may open a project (no-op before accounts exist)."""
    if user is None:
        return
    init_auth_db(db_path)
    conn = _conn(db_path)
    try:
        row = conn.execute("SELECT user_id FROM project_owners WHERE project_id = ?", (project_id,)).fetchone()
    finally:
        conn.close()
    if row is None or row["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")


def update_profile(user: Dict[str, Any], name: Optional[str] = None, title: Optional[str] = None,
                   organization: Optional[str] = None, db_path: Optional[str] = None) -> Dict[str, Any]:
    fields = {k: v.strip() for k, v in (("name", name), ("title", title), ("organization", organization)) if v is not None}
    if "name" in fields and not fields["name"]:
        raise HTTPException(status_code=400, detail="Name cannot be empty")
    if any(len(v) > 120 for v in fields.values()):
        raise HTTPException(status_code=400, detail="Profile fields are limited to 120 characters")
    conn = _conn(db_path)
    try:
        if fields:
            conn.execute(f"UPDATE users SET {', '.join(f'{k} = ?' for k in fields)} WHERE id = ?",
                         [*fields.values(), user["id"]])
            conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
        profile = _public(row)
        profile["project_count"] = len(projects_of(user["id"], db_path))
        return profile
    finally:
        conn.close()


def login_or_create_google_user(sub: str, email: str, name: str, db_path: Optional[str] = None,
                                projects_dir: Optional[str] = None) -> Dict[str, Any]:
    """Google identity -> local account: matched by Google id, else by verified email, else a new account."""
    init_auth_db(db_path)
    email = (email or "").strip().lower()
    conn = _conn(db_path)
    try:
        row = conn.execute("SELECT * FROM users WHERE google_sub = ?", (sub,)).fetchone() or \
            conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        claimed: List[str] = []
        if row is None:
            first_account = conn.execute("SELECT 1 FROM users LIMIT 1").fetchone() is None
            user_id = str(uuid.uuid4())
            # No local password: the account signs in through Google only.
            conn.execute("INSERT INTO users (id, email, name, password_hash, salt, created_at, google_sub, auth_method) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?, 'google')",
                         (user_id, email, name or email.split("@")[0], "!", "00", _now().isoformat(), sub))
            if first_account:
                claimed = _claim_unowned_projects(conn, user_id, projects_dir or DATA_PROJECTS_DIR)
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        elif not row["google_sub"]:
            conn.execute("UPDATE users SET google_sub = ? WHERE id = ?", (sub, row["id"]))
        token = _new_session(conn, row["id"])
        conn.commit()
        return {"token": token, "user": _public(row), "claimed_existing_projects": claimed}
    finally:
        conn.close()
