"""
Background jobs for long agent stages (PRD, feasibility, architecture, design, staffing, backlog, readiness).

A stage runs on the engine, not inside a browser request: starting it returns immediately, and its
status (running / done / failed / interrupted) is written to data/projects/<id>/jobs/<kind>.json.
Leaving a screen, switching projects or restarting the app no longer loses or duplicates the work:
the UI reads the job status and re-attaches. Starting a stage that is already running returns the
running job instead of starting a second copy.
"""

import os
import json
import logging
import threading
import traceback
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import HTTPException

logger = logging.getLogger("autonoma-engine.jobs")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PROJECTS_DIR = os.path.join(PROJECT_ROOT, "data", "projects")

_registry: Dict[str, Callable[[str], Any]] = {}
_threads: Dict[str, threading.Thread] = {}
_records: Dict[str, Dict[str, Any]] = {}   # running job records, updated live by the activity feed
_paths: Dict[str, str] = {}
_lock = threading.RLock()
ACTIVITY_KEEP = 60

# What each model call is for, in words the client understands (task_id prefix -> label).
_TASK_LABELS = [
    (r"^extract_requirements_json_p(\d+)", "Extracting verified requirements (part {0} of 3)"),
    (r"^generate_requirements", "Writing the requirements document"),
    (r"^prd_sec_1", "Writing PRD 1: app overview"),
    (r"^prd_sec_2", "Writing PRD 2: the problem"),
    (r"^prd_sec_3", "Writing PRD 3: users and personas"),
    (r"^prd_sec_4", "Writing PRD 4: goals and success metrics"),
    (r"^prd_sec_5_(F-\d+)", "Writing feature spec {0} (stories and acceptance criteria)"),
    (r"^prd_sec_6", "Writing PRD 6: non-functional requirements"),
    (r"^prd_sec_7", "Writing PRD 7: risks"),
    (r"^prd_sec_8", "Writing PRD 8: assumptions"),
    (r"^prd_sec_9", "Writing PRD 9: scope changes"),
    (r"^judge_prd", "Judge is reviewing the PRD against the rubric"),
    (r"^feasibility", "Architect is checking feasibility"),
    (r"^architect_openapi_(F-\d+)", "Designing the API for {0}"),
    (r"^architect_schema", "Designing the database schema"),
    (r"^architect_trd_p(\d+)", "Writing the architecture document (part {0} of 3)"),
    (r"^adr_(ADR-\d+)", "Recording decision {0}"),
    (r"^judge_arch", "Judge is reviewing the architecture"),
    (r"^generate_palette", "Designer is choosing the colour palette"),
    (r"^contrast_repair", "Designer is fixing colour contrast"),
    (r"^generate_screens", "Designer is listing the screens"),
    (r"^generate_screen_([^_]+)", "Designer is specifying screen {0}"),
    (r"^generate_journey_(\d+)", "Designer is mapping user journey {0}"),
    (r"^generate_navigation", "Designer is planning navigation and keyboard use"),
    (r"^hr_team_plan", "HR is planning the team"),
    (r"^judge_hr", "Judge is reviewing the staffing plan"),
    (r"^judge_recruiter", "Judge is reviewing the hires"),
    (r"^scrum_backlog", "Scrum Master is writing the backlog"),
    (r"^tech_lead_readiness", "Tech Lead is reviewing build readiness"),
]


def describe_task(task_id: Optional[str], role: Optional[str]) -> str:
    import re
    for pattern, label in _TASK_LABELS:
        m = re.match(pattern, task_id or "")
        if m:
            return label.format(*m.groups())
    return f"{(role or 'agent').upper()} is working" + (f" ({task_id})" if task_id else "")


def on_llm_call(call: Dict[str, Any]) -> None:
    """LLM client listener: adds each model call to the activity feed of the stage running for that project."""
    sid = call.get("session_id")
    if not sid:
        return
    phase = call.get("phase", "done")
    entry = {"at": _now(), "phase": phase, "role": call.get("role"), "task_id": call.get("task_id"),
             "label": describe_task(call.get("task_id"), call.get("role")),
             "model": call.get("model"), "provider": call.get("provider")}
    if phase == "done":
        entry.update({"tokens": (call.get("usage") or {}).get("total_tokens"), "ms": call.get("latency_ms")})
    elif phase == "waiting":
        entry.update({"reason": call.get("reason"), "wait_s": call.get("wait_s")})
    with _lock:
        keys = [k for k, t in _threads.items() if k.startswith(sid + ":") and t.is_alive() and k in _records]
        for key in keys:
            rec = _records[key]
            rec.setdefault("activity", []).append(entry)
            del rec["activity"][:-ACTIVITY_KEEP]
            if phase in ("start", "waiting"):
                rec["current"] = entry
            elif rec.get("current", {}).get("task_id") == entry["task_id"]:
                rec["current"] = None
            stats = rec.setdefault("stats", {"calls": 0, "tokens": 0})
            if phase == "done":
                stats["calls"] += 1
                stats["tokens"] += entry.get("tokens") or 0
            try:
                _write(sid, rec["kind"], rec, _paths.get(key))
            except OSError:
                pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def register(kind: str, fn: Callable[[str], Any]) -> None:
    _registry[kind] = fn


def kinds() -> List[str]:
    return sorted(_registry)


def _path(session_id: str, kind: str) -> str:
    return os.path.join(DATA_PROJECTS_DIR, session_id, "jobs", f"{kind}.json")


def _write(session_id: str, kind: str, record: Dict[str, Any], path: Optional[str] = None) -> None:
    path = path or _path(session_id, kind)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, default=str)
    os.replace(tmp, path)


def _read(session_id: str, kind: str) -> Optional[Dict[str, Any]]:
    path = _path(session_id, kind)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        record = json.load(f)
    key = f"{session_id}:{kind}"
    t = _threads.get(key)
    if record.get("status") == "running" and not (t and t.is_alive()):
        # The engine restarted while this ran: say so instead of pretending it is still running.
        record.update({"status": "interrupted", "finished_at": _now(),
                       "error": "The engine stopped while this was running; start it again."})
        _write(session_id, kind, record)
    return record


def status(session_id: str, kind: str, include_result: bool = True) -> Dict[str, Any]:
    record = _read(session_id, kind) or {"kind": kind, "session_id": session_id, "status": "not_started"}
    if not include_result:
        record = {k: v for k, v in record.items() if k != "result"}
    return record


def all_status(session_id: str) -> List[Dict[str, Any]]:
    return [status(session_id, k, include_result=False) for k in kinds()]


def start(session_id: str, kind: str) -> Dict[str, Any]:
    if kind not in _registry:
        raise HTTPException(status_code=404, detail=f"Unknown job '{kind}'. Known: {kinds()}")
    if not os.path.isdir(os.path.join(DATA_PROJECTS_DIR, session_id)):
        raise HTTPException(status_code=404, detail=f"Project {session_id} not found")
    key = f"{session_id}:{kind}"
    with _lock:
        t = _threads.get(key)
        if t and t.is_alive():
            return status(session_id, kind, include_result=False)  # already running: attach, do not duplicate
        record = {"kind": kind, "session_id": session_id, "status": "running", "started_at": _now(),
                  "finished_at": None, "error": None, "result": None, "current": None, "activity": [],
                  "stats": {"calls": 0, "tokens": 0}}
        path = _path(session_id, kind)  # fixed now, so the final status lands next to the running one
        _write(session_id, kind, record, path)
        _records[key] = record
        _paths[key] = path

        def _run() -> None:
            try:
                result = _registry[kind](session_id)
                record.update({"status": "done", "finished_at": _now(), "result": result})
            except HTTPException as e:
                record.update({"status": "failed", "finished_at": _now(), "error": e.detail,
                               "http_status": e.status_code})
            except Exception as e:  # report, never hide
                logger.exception(f"job {key} failed")
                record.update({"status": "failed", "finished_at": _now(), "error": f"{type(e).__name__}: {e}",
                               "trace": traceback.format_exc()[-2000:]})
            record["current"] = None
            with _lock:
                _records.pop(key, None)
                _paths.pop(key, None)
                try:
                    _write(session_id, kind, record, path)
                except OSError as e:  # the project folder was removed while the stage ran
                    logger.warning(f"job {key} finished as {record['status']} but its status could not be saved: {e}")

        t = threading.Thread(target=_run, name=f"job-{key}", daemon=True)
        _threads[key] = t
        t.start()
    return {k: v for k, v in record.items() if k != "result"}


def register_from_routes(app, routes: Dict[str, str]) -> None:
    """
    kind -> POST route path. Each job calls that route's own handler, so a job does exactly what the
    button used to do. Handlers take either session_id or a request model with a session_id field.

    The route is looked up when the job first runs, not now, so it does not matter in which order the
    engine attaches its routers (a stage whose router is attached later is still a known job).
    """
    import inspect
    from pydantic import BaseModel

    def _resolve(path: str):
        for r in app.routes:
            if getattr(r, "path", None) == path and "POST" in (getattr(r, "methods", None) or ()):
                return r.endpoint
        raise HTTPException(status_code=500, detail=f"The engine has no POST {path} route for this stage")

    for kind, path in routes.items():
        def _call(session_id: str, path=path):
            endpoint = _resolve(path)
            params = list(inspect.signature(endpoint).parameters.values())
            ann = params[0].annotation if params else None
            if inspect.isclass(ann) and issubclass(ann, BaseModel):
                return endpoint(ann(session_id=session_id))
            return endpoint(session_id)

        register(kind, _call)


def missing_routes(app, routes: Dict[str, str]) -> List[str]:
    """Stage paths with no POST route on the app (checked at startup and logged, never silent)."""
    have = {r.path for r in app.routes if "POST" in (getattr(r, "methods", None) or ())}
    return [f"{kind}: {path}" for kind, path in routes.items() if path not in have]
