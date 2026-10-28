"""
Append-only event log (Handbook 20.4, 24.1, 24.3).

Everything that happens in a project is an event: the activity feed, the build board
and the reports are read from these rows, and a crashed build resumes from them.
Rows are never updated or deleted.
"""

import os
import json
import sqlite3
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("autonoma-engine.events")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(PROJECT_ROOT, "data", "office.db")
DATA_PROJECTS_DIR = os.path.join(PROJECT_ROOT, "data", "projects")


def init_events_db(db_path: Optional[str] = None) -> None:
    db_path = db_path or DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                type TEXT NOT NULL,
                actor TEXT,
                task_id TEXT,
                data TEXT NOT NULL DEFAULT '{}'
            );
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_project_seq ON events(project_id, seq);")
        conn.commit()
    finally:
        conn.close()


def emit(project_id: str, type: str, actor: Optional[str] = None, task_id: Optional[str] = None,
         data: Optional[Dict[str, Any]] = None, db_path: Optional[str] = None) -> int:
    """Appends one event and returns its sequence number."""
    db_path = db_path or DEFAULT_DB_PATH
    init_events_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO events (project_id, type, actor, task_id, data) VALUES (?, ?, ?, ?, ?);",
            (project_id, type, actor, task_id, json.dumps(data or {}, default=str)),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_events(project_id: str, after_seq: int = 0, types: Optional[List[str]] = None,
                task_id: Optional[str] = None, limit: int = 500, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    db_path = db_path or DEFAULT_DB_PATH
    init_events_db(db_path)
    sql = "SELECT seq, project_id, at, type, actor, task_id, data FROM events WHERE project_id = ? AND seq > ?"
    args: List[Any] = [project_id, after_seq]
    if types:
        sql += f" AND type IN ({','.join('?' for _ in types)})"
        args.extend(types)
    if task_id:
        sql += " AND task_id = ?"
        args.append(task_id)
    sql += " ORDER BY seq ASC LIMIT ?"
    args.append(limit)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, args).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        item = dict(r)
        try:
            item["data"] = json.loads(item["data"])
        except Exception:
            pass
        out.append(item)
    return out


def llm_call_listener(db_path: Optional[str] = None):
    """
    LLM client listener that records every model call as an `llm.call` event.
    Paths resolve at call time, and only calls for an existing project are recorded.
    """
    def _listener(call: Dict[str, Any]) -> None:
        sid = call.get("session_id")
        if not sid or sid == "global" or not os.path.isdir(os.path.join(DATA_PROJECTS_DIR, sid)):
            return
        emit(sid, "llm.call", actor=call.get("role"), task_id=call.get("task_id"),
             data={"provider": call.get("provider"), "model": call.get("model"), "usage": call.get("usage"),
                   "latency_ms": call.get("latency_ms"), "is_degraded": call.get("is_degraded")},
             db_path=db_path or DEFAULT_DB_PATH)
    return _listener
