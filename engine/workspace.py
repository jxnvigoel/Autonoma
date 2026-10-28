"""
Project git workspace (Handbook 20.5, 23.5, 32 BuildStory).

One local git repository per project at data/projects/<id>/repo, checked out on `main`.
Every story is built in its own worktree on branch story/ST-### under
repo/.virtualoffice/wt/, so parallel stories never share a working folder.
The repository never has a remote: nothing is ever pushed anywhere.
"""

import os
import re
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PROJECTS_DIR = os.path.join(PROJECT_ROOT, "data", "projects")

GIT_ENV = {
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_AUTHOR_NAME": "Autonoma Office",
    "GIT_AUTHOR_EMAIL": "office@autonoma.local",
    "GIT_COMMITTER_NAME": "Autonoma Office",
    "GIT_COMMITTER_EMAIL": "office@autonoma.local",
}

PREBUILD_DOCS = ["requirements.md", "prd.md", "architecture.md", "openapi.yaml", "schema.md", "app-flow.md",
                 "design-brief.md", "team-plan.json", "backlog.json", "implementation-plan.md", "readiness.md",
                 "feasibility.md", "estimate.json"]

GITIGNORE = """# Autonoma agent scratch space, worktrees and logs
.virtualoffice/
# Secrets never enter the repository
.env
.env.*
!.env.example
__pycache__/
*.pyc
node_modules/
"""


class WorkspaceError(Exception):
    pass


def git(args: List[str], cwd: str, check: bool = True) -> Tuple[int, str]:
    env = dict(os.environ)
    env.update(GIT_ENV)
    proc = subprocess.run(["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
                          cwd=cwd, env=env, capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    if check and proc.returncode != 0:
        raise WorkspaceError(f"git {' '.join(args)} failed: {out.strip()}")
    return proc.returncode, out


def repo_path(session_id: str, projects_dir: str = DATA_PROJECTS_DIR) -> str:
    return os.path.join(projects_dir, session_id, "repo")


def assert_no_remote(repo: str) -> None:
    _, out = git(["remote"], repo)
    if out.strip():
        raise WorkspaceError(f"project repository has remote(s) {out.split()}; Autonoma never pushes, remove them")


def ensure_repo(session_id: str, projects_dir: str = DATA_PROJECTS_DIR) -> str:
    """Creates the project repository with the approved pre-build docs as the first commit."""
    repo = repo_path(session_id, projects_dir)
    if os.path.isdir(os.path.join(repo, ".git")):
        assert_no_remote(repo)
        return repo
    os.makedirs(repo, exist_ok=True)
    git(["init", "-q", "-b", "main"], repo)
    with open(os.path.join(repo, ".gitignore"), "w", encoding="utf-8") as f:
        f.write(GITIGNORE)
    src_docs = os.path.join(projects_dir, session_id, "docs")
    dst_docs = os.path.join(repo, "docs")
    os.makedirs(dst_docs, exist_ok=True)
    for name in PREBUILD_DOCS:
        src = os.path.join(src_docs, name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(dst_docs, name))
    adr_src = os.path.join(src_docs, "adr")
    if os.path.isdir(adr_src):
        shutil.copytree(adr_src, os.path.join(dst_docs, "adr"), dirs_exist_ok=True)
    git(["add", "-A"], repo)
    git(["commit", "-q", "-m", "chore: project setup with approved pre-build documents"], repo)
    return repo


def branch_dir_name(branch: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", branch)


def create_worktree(repo: str, branch: str, base: str = "main") -> str:
    """Creates (or reuses) a worktree for `branch`, branched from `base`."""
    path = os.path.join(repo, ".virtualoffice", "wt", branch_dir_name(branch))
    if os.path.isdir(path):
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    code, _ = git(["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], repo, check=False)
    if code == 0:
        git(["worktree", "add", "-q", path, branch], repo)
    else:
        git(["worktree", "add", "-q", "-b", branch, path, base], repo)
    return path


def current_branch(wt: str) -> str:
    _, out = git(["rev-parse", "--abbrev-ref", "HEAD"], wt)
    return out.strip()


def head_sha(wt: str) -> str:
    _, out = git(["rev-parse", "--short", "HEAD"], wt)
    return out.strip()


def commit_all(wt: str, message: str, expected_branch: Optional[str] = None) -> Optional[str]:
    """Commits every change in the worktree. Only allowed on the worktree's own branch."""
    if expected_branch and current_branch(wt) != expected_branch:
        raise WorkspaceError(f"refusing to commit: worktree is on '{current_branch(wt)}', expected '{expected_branch}'")
    git(["add", "-A"], wt)
    code, _ = git(["diff", "--cached", "--quiet"], wt, check=False)
    if code == 0:
        return None
    git(["commit", "-q", "-m", message], wt)
    return head_sha(wt)


def diff_against(wt: str, base: str = "main", max_chars: int = 60000) -> str:
    """Diff of the branch (committed and uncommitted) against `base`."""
    _, merge_base = git(["merge-base", base, "HEAD"], wt)
    _, out = git(["diff", merge_base.strip()], wt)
    if len(out) > max_chars:
        out = out[:max_chars] + f"\n... diff truncated at {max_chars} chars ..."
    return out


def changed_files(wt: str, base: str = "main") -> List[str]:
    _, merge_base = git(["merge-base", base, "HEAD"], wt)
    _, out = git(["diff", "--name-only", merge_base.strip()], wt)
    _, untracked = git(["ls-files", "--others", "--exclude-standard"], wt)
    return sorted(set(l for l in (out + "\n" + untracked).splitlines() if l.strip()))


def merge_branch(repo: str, branch: str, message: str) -> Tuple[bool, str]:
    """Merges `branch` into main (no fast-forward). On conflict the merge is aborted."""
    if current_branch(repo) != "main":
        git(["checkout", "-q", "main"], repo)
    code, out = git(["merge", "--no-ff", "-q", "-m", message, branch], repo, check=False)
    if code != 0:
        git(["merge", "--abort"], repo, check=False)
        return False, out.strip()
    return True, head_sha(repo)


def remove_worktree(repo: str, path: str) -> None:
    if os.path.isdir(path):
        git(["worktree", "remove", "--force", path], repo, check=False)
    git(["worktree", "prune"], repo, check=False)


def tag(repo: str, name: str, message: str) -> str:
    git(["tag", "-a", "-f", name, "-m", message], repo)
    return name


def log(repo: str, limit: int = 30) -> List[Dict[str, str]]:
    _, out = git(["log", f"-{limit}", "--pretty=format:%h%x1f%s%x1f%cI"], repo)
    rows = []
    for line in out.splitlines():
        parts = line.split("\x1f")
        if len(parts) == 3:
            rows.append({"sha": parts[0], "subject": parts[1], "at": parts[2]})
    return rows
