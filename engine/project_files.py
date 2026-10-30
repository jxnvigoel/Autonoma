"""
Project files for the code editor: the code the agents build (repo/) and the approved documents (docs/).

The editor reads these through the engine so it works in Electron and in a browser, always shows the
open project (not the app's own source), and can follow a running build. repo/ is editable; docs/ is
read-only because those documents passed the Judge and the client gates, and changing them here would
bypass that review.
"""

import os
import re
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

ROOTS = {"repo": True, "docs": False}  # folder -> editable
SKIP = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".pytest_cache"}
MAX_FILE_BYTES = 1_000_000
MAX_NODES = 5000

router = APIRouter()


def _project_dir(session_id: str) -> str:
    import main  # the projects folder and id check live there (tests point them at a temp folder)

    path = os.path.join(main.DATA_PROJECTS_DIR, main.validate_session_id(session_id))
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail=f"Project {session_id} not found")
    return path


def _resolve(session_id: str, rel: str) -> Tuple[str, bool]:
    """Project-relative path -> (absolute path, editable). Refuses anything outside repo/ or docs/."""
    base = os.path.realpath(_project_dir(session_id))
    rel = (rel or "").replace("\\", "/").lstrip("/")
    top = rel.split("/", 1)[0]
    if top not in ROOTS:
        raise HTTPException(status_code=403, detail=f"Only {', '.join(ROOTS)} can be opened here")
    full = os.path.realpath(os.path.join(base, rel))
    root = os.path.join(base, top)
    if not (full == root or full.startswith(root + os.sep)):
        raise HTTPException(status_code=403, detail="Path is outside the project")
    return full, ROOTS[top]


def _walk(base: str, rel: str, budget: List[int]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    full = os.path.join(base, rel)
    try:
        names = sorted(os.listdir(full), key=lambda n: (not os.path.isdir(os.path.join(full, n)), n.lower()))
    except OSError:
        return out
    for name in names:
        if name in SKIP or budget[0] <= 0:
            continue
        budget[0] -= 1
        child_rel = f"{rel}/{name}"
        child = os.path.join(base, child_rel)
        if os.path.isdir(child):
            out.append({"name": name, "path": child_rel, "relativePath": child_rel, "isDirectory": True,
                        "children": _walk(base, child_rel, budget)})
        else:
            out.append({"name": name, "path": child_rel, "relativePath": child_rel, "isDirectory": False,
                        "size": os.path.getsize(child)})
    return out


@router.get("/project-files/tree/{session_id}")
def project_tree(session_id: str):
    base = _project_dir(session_id)
    budget = [MAX_NODES]
    tree = [{"name": top, "path": top, "relativePath": top, "isDirectory": True, "editable": editable,
             "children": _walk(base, top, budget)}
            for top, editable in ROOTS.items() if os.path.isdir(os.path.join(base, top))]
    repo = os.path.join(base, "repo")
    return {"session_id": session_id, "tree": tree, "truncated": budget[0] <= 0,
            "repo_path": repo if os.path.isdir(repo) else None}


@router.get("/project-files/file/{session_id}")
def project_file(session_id: str, path: str):
    full, editable = _resolve(session_id, path)
    if not os.path.isfile(full):
        raise HTTPException(status_code=404, detail=f"No file {path}")
    if os.path.getsize(full) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail=f"{path} is larger than 1 MB; open it outside the editor")
    with open(full, "rb") as f:
        raw = f.read()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=415, detail=f"{path} is not a text file")
    return {"path": path, "content": content, "editable": editable, "mtime": os.path.getmtime(full)}


class ProjectFileWrite(BaseModel):
    path: str
    content: str


@router.put("/project-files/file/{session_id}")
def write_project_file(session_id: str, req: ProjectFileWrite):
    full, editable = _resolve(session_id, req.path)
    if not editable:
        raise HTTPException(status_code=403, detail="docs/ is read-only here: those documents passed review "
                                                    "and the client gates. Ask the owning agent for changes.")
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(req.content)
    return {"path": req.path, "saved": True, "mtime": os.path.getmtime(full)}


# ------------------------------------------------------------------ git history (read-only)

def _repo(session_id: str) -> str:
    """The project's own git repo. Never an enclosing one: data/projects can sit inside another repo
    (e.g. this app's), and git would otherwise walk up and show that repo's history as the project's."""
    try:
        import workspace
    except ImportError:
        from engine import workspace
    repo = os.path.realpath(os.path.join(_project_dir(session_id), "repo"))
    code, top = workspace.git(["rev-parse", "--show-toplevel"], repo, check=False) if os.path.isdir(repo) else (1, "")
    if code != 0 or os.path.realpath(top.strip()) != repo:
        raise HTTPException(status_code=404, detail="No code yet: the repo is created when the build starts")
    return repo


@router.get("/project-files/git/{session_id}")
def project_git(session_id: str, limit: int = 50):
    """Commit history of the project's repo (all branches), newest first: who changed what, and when."""
    try:
        import workspace
    except ImportError:
        from engine import workspace
    repo = _repo(session_id)
    _, out = workspace.git(["log", "--all", f"-{max(1, min(limit, 200))}",
                            "--pretty=format:%h%x1f%an%x1f%s%x1f%cI%x1f%D", "--shortstat"], repo, check=False)
    commits: List[Dict[str, Any]] = []
    for line in out.splitlines():
        if "\x1f" in line:
            sha, author, subject, at, refs = (line.split("\x1f") + [""] * 5)[:5]
            commits.append({"sha": sha, "author": author, "subject": subject, "at": at,
                            "refs": [r.strip() for r in refs.split(",") if r.strip()], "files": 0, "insertions": 0,
                            "deletions": 0})
        elif commits and "changed" in line:
            for n, word in ((r"(\d+) files? changed", "files"), (r"(\d+) insertions?", "insertions"),
                            (r"(\d+) deletions?", "deletions")):
                m = re.search(n, line)
                if m:
                    commits[-1][word] = int(m.group(1))
    _, branch = workspace.git(["rev-parse", "--abbrev-ref", "HEAD"], repo, check=False)
    _, status = workspace.git(["status", "--porcelain"], repo, check=False)
    return {"session_id": session_id, "branch": branch.strip(), "commits": commits,
            "uncommitted": [l[3:] for l in status.splitlines() if l.strip()]}


@router.get("/project-files/commit/{session_id}/{sha}")
def project_commit(session_id: str, sha: str):
    """One commit's diff (capped), for the editor's history view."""
    try:
        import workspace
    except ImportError:
        from engine import workspace
    if not re.fullmatch(r"[0-9a-f]{4,40}", sha):
        raise HTTPException(status_code=400, detail="Not a commit id")
    repo = _repo(session_id)
    code, out = workspace.git(["show", "--stat", "--patch", "--format=%H%n%an%n%cI%n%s%n%b", sha], repo, check=False)
    if code != 0:
        raise HTTPException(status_code=404, detail=f"No commit {sha}")
    return {"sha": sha, "diff": out[:200000], "truncated": len(out) > 200000}
