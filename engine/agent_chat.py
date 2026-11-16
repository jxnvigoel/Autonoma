"""
Client chat with the delivery agents (Architect, Designer, HR, Recruiter, Scrum Master, Tech Lead).

Each agent keeps its own thread in data/projects/<id>/agent_chats/<agent>.json and answers from the documents
it wrote, the way the PM answers from the PRD (pm.py /pm/message). Agents answer questions; changes go through
their stage's own buttons and the Judge, never through chat.
"""

import os
import uuid
import glob
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["agents"])

# agent -> (LLM role, display name, documents it answers from, relative to docs/)
AGENTS: Dict[str, tuple] = {
    "architect": ("architect", "Solution Architect", ["architecture.md", "adr/*.md", "schema.md", "openapi.yaml"]),
    "designer": ("designer", "UI/UX Designer", ["app-flow.md", "design-brief.md"]),
    "hr": ("hr", "HR Staffing Planner", ["team-plan.json", "staffing-report.md"]),
    "recruiter": ("recruiter", "Recruiter", ["staffing-report.md", "team-plan.json"]),
    "scrum": ("scrum", "Scrum Master", ["backlog.json", "sprint-plan.md"]),
    "tech-lead": ("tech-lead", "Tech Lead", ["readiness.md", "backlog.json", "architecture.md"]),
}

DOC_CHARS = 12000


class AgentMessageRequest(BaseModel):
    session_id: str
    agent: str
    message: str


def _paths(session_id: str, agent: str):
    import main
    if agent not in AGENTS:
        raise HTTPException(status_code=404, detail=f"Unknown agent '{agent}'")
    session_dir = os.path.join(main.DATA_PROJECTS_DIR, main.validate_session_id(session_id))
    if not os.path.isdir(session_dir):
        raise HTTPException(status_code=404, detail=f"Project {session_id} not found")
    return session_dir, os.path.join(session_dir, "agent_chats", f"{agent}.json")


def _documents(session_dir: str, patterns: List[str]) -> str:
    """The agent's own documents, in order, up to DOC_CHARS; empty when the stage has not run."""
    out, used = [], 0
    for pattern in patterns:
        for path in sorted(glob.glob(os.path.join(session_dir, "docs", pattern))):
            try:
                text = open(path, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            take = text[:max(0, DOC_CHARS - used)]
            if take:
                out.append(f"--- {os.path.relpath(path, session_dir)} ---\n{take}")
                used += len(take)
    return "\n\n".join(out)


@router.get("/agent/messages/{session_id}/{agent}")
def get_agent_messages(session_id: str, agent: str):
    import main
    session_dir, thread_file = _paths(session_id, agent)
    return {"session_id": session_id, "agent": agent, "messages": main.load_json(thread_file, []),
            "has_documents": bool(_documents(session_dir, AGENTS[agent][2]))}


@router.post("/agent/message")
def agent_message(req: AgentMessageRequest):
    import main
    from llm_client import query_llm_with_meta

    text = (req.message or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    session_dir, thread_file = _paths(req.session_id, req.agent)
    role, name, patterns = AGENTS[req.agent]
    docs = _documents(session_dir, patterns)
    thread: List[dict] = main.load_json(thread_file, [])

    system = (f"You are the {name} on this project. The client is asking you a question. Answer from your "
              f"documents below only and cite their IDs (F-, NFR-, ADR-, API-, TBL-, ROLE-, ST-, Q-) where they "
              f"apply. If the answer is not in them, say so plainly instead of guessing. If the client asks for a "
              f"change, restate it in one sentence and say it is made by re-running your stage, which the Judge "
              f"reviews; do not claim you have changed anything. Keep answers short.")
    if not docs:
        system += " Your stage has not produced its documents yet: say so, and explain what you will produce."
    history = "\n".join(f"{'Client' if m.get('role') == 'user' else name}: {m.get('content', '')}" for m in thread[-8:])
    prompt = (f"YOUR DOCUMENTS:\n{docs or '(none yet)'}\n\nCONVERSATION SO FAR:\n{history}\n\n"
              f"Client: {text}\n{name}:")
    answer, meta = query_llm_with_meta(prompt=prompt, system=system, role=role, session_id=req.session_id,
                                       task_id=f"{req.agent}_chat", max_tokens=1200)
    answer = (answer or "").strip() or "I could not produce an answer just now; please ask again."

    now = datetime.now(timezone.utc).isoformat()
    thread += [
        {"id": str(uuid.uuid4()), "role": "user", "content": text, "timestamp": now},
        {"id": str(uuid.uuid4()), "role": "assistant", "content": answer, "timestamp": now,
         "meta": {"model": meta.get("model"), "provider": meta.get("provider")}},
    ]
    os.makedirs(os.path.dirname(thread_file), exist_ok=True)
    main.save_json(thread_file, thread)
    return {"session_id": req.session_id, "agent": req.agent, "message": answer, "messages": thread,
            "model": meta.get("model"), "provider": meta.get("provider")}
