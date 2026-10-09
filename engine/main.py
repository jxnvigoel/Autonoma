import os
import sys
import logging
import json
import uuid
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import uvicorn

# Import the BA system prompt
try:
    from prompts.ba_system_prompt import BA_SYSTEM_PROMPT
except ImportError:
    try:
        from engine.prompts.ba_system_prompt import BA_SYSTEM_PROMPT
    except ImportError:
        # Fallback if imported from different working directory
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from prompts.ba_system_prompt import BA_SYSTEM_PROMPT

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("autonoma-engine")

app = FastAPI(title="Autonoma Engine", version="1.0.0")

# Enable CORS for Electron renderer and web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PROJECTS_DIR = os.path.join(PROJECT_ROOT, "data", "projects")
CONVERSATION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conversation.json")

BA_STATE_PATTERN = re.compile(r"<!--\s*BA_STATE:\s*(\{.*?\})\s*-->", re.DOTALL)


# Data helper utilities
def get_session_dir(session_id: str) -> str:
    path = os.path.join(DATA_PROJECTS_DIR, session_id)
    os.makedirs(path, exist_ok=True)
    os.makedirs(os.path.join(path, "docs"), exist_ok=True)
    return path


def load_json(file_path: str, default: Any = None) -> Any:
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
    return default if default is not None else {}


def save_json(file_path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving {file_path}: {e}")


def strip_ba_state_marker(text: str) -> str:
    cleaned = BA_STATE_PATTERN.sub("", text).strip()
    return cleaned


def parse_ba_state(text: str) -> Optional[Dict[str, Any]]:
    match = BA_STATE_PATTERN.search(text)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception as e:
            logger.warning(f"Could not parse BA_STATE JSON: {e}")
    return None


def query_ollama(prompt: str, system: Optional[str] = None, model: Optional[str] = None) -> str:
    target_model = model or DEFAULT_MODEL
    payload = {
        "model": target_model,
        "prompt": prompt,
        "stream": False,
    }
    if system:
        payload["system"] = system

    try:
        res = requests.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=180)
        if res.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model '{target_model}' not found in Ollama. Run 'ollama pull {target_model}'",
            )
        elif res.status_code != 200:
            raise HTTPException(
                status_code=res.status_code,
                detail=f"Ollama returned error HTTP {res.status_code}: {res.text}",
            )
        data = res.json()
        return data.get("response", "")
    except requests.exceptions.ConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to Ollama at {OLLAMA_HOST}. Make sure Ollama is running.",
        )


def generate_requirements_doc(session_id: str) -> str:
    session_dir = get_session_dir(session_id)
    intake_file = os.path.join(session_dir, "intake.json")
    qa_file = os.path.join(session_dir, "qa_log.json")
    doc_file = os.path.join(session_dir, "docs", "requirements.md")

    intake_data = load_json(intake_file, {})
    qa_log = load_json(qa_file, [])

    prompt = f"""You are the Business Analyst. The client discovery phase is now complete.
Write the complete, comprehensive, unambiguous, and testable `requirements.md` document for this project based strictly on the client intake and full Q&A discovery log below.

CLIENT INTAKE:
- Project Name: {intake_data.get('project_name', 'Untitled Project')}
- What they are building: {intake_data.get('description', 'N/A')}
- Target Users: {intake_data.get('target_users', 'N/A')}
- Target Timeline: {intake_data.get('timeline', 'N/A')}
- Budget & Monthly Running Cost: {intake_data.get('budget', 'N/A')}

FULL Q&A LOG (Q-### Source Citations):
{json.dumps(qa_log, indent=2)}

You MUST structure the document with these exact sections:
# 1. Problem Statement
# 2. Personas (P-01, P-02, etc.)
# 3. User Journeys
# 4. Functional Requirements (FR-01, FR-02, etc. with MoSCoW priority: Must Have / Should Have / Could Have / Won't Have, and cite the Q-### it came from, e.g. [Source: Q-001])
# 5. Non-Functional Requirements (NFR-01, NFR-02, etc. with concrete metrics, and cite the Q-### it came from)
# 6. Data Requirements & Entities
# 7. Integrations & External Services
# 8. Timeline & Budget
# 9. v1 Scope vs Later
# 10. Definition of Success & Key Metrics
# 11. Assumptions (ASM-01, ASM-02, etc. for any items unresolved or assumed, citing reason and risk)

GROUNDING RULE: Every requirement and key decision must cite the Q- entry it came from. Never invent client facts, dates, or numbers.
Output ONLY the markdown content for requirements.md. Do not wrap in extra conversational commentary or append state markers."""

    raw_response = query_ollama(prompt=prompt, system=BA_SYSTEM_PROMPT)
    cleaned_doc = strip_ba_state_marker(raw_response)

    os.makedirs(os.path.dirname(doc_file), exist_ok=True)
    with open(doc_file, "w", encoding="utf-8") as f:
        f.write(cleaned_doc)

    logger.info(f"Generated requirements.md successfully at {doc_file}")
    return cleaned_doc


# Pydantic models
class IntakeRequest(BaseModel):
    project_name: str
    description: str
    target_users: str
    timeline: str
    budget: str


class BAMessageRequest(BaseModel):
    session_id: str
    message: str


class ChatMessage(BaseModel):
    id: str
    role: str
    content: str
    timestamp: str
    meta: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    prompt: str
    model: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    duration: float
    token_count: int


class StatusResponse(BaseModel):
    status: str
    ollama_online: bool
    model_ready: bool
    version: Optional[str] = None
    message: str


def load_conversation() -> List[Dict[str, Any]]:
    if os.path.exists(CONVERSATION_FILE):
        try:
            with open(CONVERSATION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            logger.error(f"Error loading conversation file: {e}")
    return []


def save_conversation(messages: List[Dict[str, Any]]) -> None:
    try:
        with open(CONVERSATION_FILE, "w", encoding="utf-8") as f:
            json.dump(messages, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving conversation file: {e}")


conversation_store: List[Dict[str, Any]] = load_conversation()


# -----------------------------------------------------------------------------
# System & General Endpoints
# -----------------------------------------------------------------------------

@app.get("/status", response_model=StatusResponse)
def get_status():
    """Pings Ollama and checks if the service is reachable and whether llama3.2:3b is ready."""
    model_name = DEFAULT_MODEL
    try:
        version_res = requests.get(f"{OLLAMA_HOST}/api/version", timeout=3)
        if version_res.status_code != 200:
            return StatusResponse(
                status="error",
                ollama_online=False,
                model_ready=False,
                message=f"Cannot connect to Ollama at {OLLAMA_HOST} (HTTP {version_res.status_code}). Make sure the Ollama daemon is running.",
            )
        version_data = version_res.json()
        version = version_data.get("version", "unknown")

        tags_res = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        if tags_res.status_code != 200:
            return StatusResponse(
                status="error",
                ollama_online=True,
                model_ready=False,
                version=version,
                message=f"Ollama is running, but failed to retrieve downloaded models (HTTP {tags_res.status_code}).",
            )

        tags_data = tags_res.json()
        models = tags_data.get("models", [])
        model_names = [m.get("name", "") for m in models]
        model_found = any(
            name == model_name or name.startswith(f"{model_name}:") or name == f"{model_name}:latest"
            for name in model_names
        )

        if not model_found:
            return StatusResponse(
                status="error",
                ollama_online=True,
                model_ready=False,
                version=version,
                message=f"Model '{model_name}' not found in Ollama. Run: ollama pull {model_name}",
            )

        return StatusResponse(
            status="ready",
            ollama_online=True,
            model_ready=True,
            version=version,
            message="Ollama is online and llama3.2:3b is ready",
        )

    except requests.exceptions.ConnectionError:
        return StatusResponse(
            status="error",
            ollama_online=False,
            model_ready=False,
            message=f"Unable to reach Ollama at {OLLAMA_HOST}. Please ensure the Ollama service is running.",
        )
    except Exception as e:
        return StatusResponse(
            status="error",
            ollama_online=False,
            model_ready=False,
            message=f"Error checking Ollama status: {str(e)}",
        )


@app.get("/conversation", response_model=List[ChatMessage])
def get_conversation():
    return conversation_store


@app.delete("/conversation")
def clear_conversation():
    global conversation_store
    conversation_store = []
    save_conversation(conversation_store)
    return {"status": "ok", "message": "Conversation history cleared"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prompt cannot be empty",
        )

    model = req.model or DEFAULT_MODEL

    user_msg = {
        "id": str(uuid.uuid4()),
        "role": "user",
        "content": prompt,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "meta": None,
    }
    conversation_store.append(user_msg)
    save_conversation(conversation_store)

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }

    try:
        res = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json=payload,
            timeout=180,
        )

        if res.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model '{model}' not found in Ollama. Run 'ollama pull {model}' in your terminal.",
            )
        elif res.status_code != 200:
            raise HTTPException(
                status_code=res.status_code,
                detail=f"Ollama returned error HTTP {res.status_code}: {res.text}",
            )

        data = res.json()
        response_text = data.get("response", "")
        duration = data.get("total_duration", 0)
        token_count = data.get("eval_count", 0)

        assistant_msg = {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": response_text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "meta": {
                "duration": duration,
                "token_count": token_count,
            },
        }
        conversation_store.append(assistant_msg)
        save_conversation(conversation_store)

        return ChatResponse(
            response=response_text,
            duration=duration,
            token_count=token_count,
        )

    except requests.exceptions.ConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to Ollama at {OLLAMA_HOST}. Make sure Ollama is running.",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error communicating with Ollama: {str(e)}",
        )


# -----------------------------------------------------------------------------
# Business Analyst (BA) Workflow Endpoints
# -----------------------------------------------------------------------------

@app.post("/ba/start")
def ba_start(req: IntakeRequest):
    """
    Creates a new BA session, stores intake to data/projects/<session_id>/intake.json,
    and calls Ollama with BA_SYSTEM_PROMPT to produce the round 0 opening greeting + intro + permission ask.
    """
    session_id = str(uuid.uuid4())
    session_dir = get_session_dir(session_id)

    intake_data = {
        "project_name": req.project_name.strip(),
        "description": req.description.strip(),
        "target_users": req.target_users.strip(),
        "timeline": req.timeline.strip(),
        "budget": req.budget.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    save_json(os.path.join(session_dir, "intake.json"), intake_data)
    save_json(os.path.join(session_dir, "qa_log.json"), [])

    initial_state = {
        "checklist_covered": [],
        "checklist_missing": [
            "problem",
            "personas",
            "journeys",
            "requirements",
            "data",
            "integrations",
            "timeline_budget",
            "scope",
            "success_metric",
        ],
        "round": 0,
        "ready_for_requirements": False,
        "messages": [],
    }
    save_json(os.path.join(session_dir, "session_state.json"), initial_state)

    prompt = f"""New Project Intake Context:
- Project Name: {req.project_name}
- What they are trying to build: {req.description}
- Who will use it: {req.target_users}
- Target Timeline: {req.timeline}
- Budget & Expected Monthly Running Cost: {req.budget}

Instructions for Round 0:
Strictly follow OPENING BEHAVIOR:
1. Greet the client warmly.
2. Introduce yourself as their Business Analyst specifically for the "{req.project_name}" project.
3. In 1-2 sentences, acknowledge what they want to build ({req.description}) and explain what you'll do: ask questions to turn their specific idea into a clear, testable plan the rest of the team can build from.
4. Explicitly ask their permission to begin (e.g. "Mind if I ask a few questions to get started?").
Do NOT ask any substantive discovery questions yet until they confirm.
At the end on its own line append:
<!--BA_STATE:{{"checklist_covered":[],"checklist_missing":["problem","personas","journeys","requirements","data","integrations","timeline_budget","scope","success_metric"],"round":0,"ready_for_requirements":false}}-->"""

    raw_response = query_ollama(prompt=prompt, system=BA_SYSTEM_PROMPT)
    cleaned_message = strip_ba_state_marker(raw_response)

    # Store first message in session messages
    initial_state["messages"].append({
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "content": cleaned_message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    save_json(os.path.join(session_dir, "session_state.json"), initial_state)

    return {
        "session_id": session_id,
        "message": cleaned_message,
    }


@app.post("/ba/message")
def ba_message(req: BAMessageRequest):
    """
    Appends the client's answer to qa_log.json, queries Ollama with conversation context + checklist state,
    strips BA_STATE marker, parses ready_for_requirements, and triggers requirements.md generation when ready.
    """
    session_id = req.session_id.strip()
    session_dir = get_session_dir(session_id)
    intake_file = os.path.join(session_dir, "intake.json")
    qa_file = os.path.join(session_dir, "qa_log.json")
    state_file = os.path.join(session_dir, "session_state.json")

    if not os.path.exists(intake_file):
        raise HTTPException(status_code=404, detail="Session not found")

    intake_data = load_json(intake_file, {})
    qa_log = load_json(qa_file, [])
    session_state = load_json(state_file, {
        "checklist_covered": [],
        "checklist_missing": [
            "problem",
            "personas",
            "journeys",
            "requirements",
            "data",
            "integrations",
            "timeline_budget",
            "scope",
            "success_metric",
        ],
        "round": 0,
        "ready_for_requirements": False,
        "messages": [],
    })

    client_answer = req.message.strip()
    messages_history = session_state.get("messages", [])

    # Find the last assistant question/prompt
    last_ba_msg = ""
    for m in reversed(messages_history):
        if m.get("role") == "assistant":
            last_ba_msg = m.get("content", "")
            break

    # Determine round
    current_round = session_state.get("round", 0) + 1
    session_state["round"] = current_round

    # Append to real qa_log.json array
    q_id = f"Q-{len(qa_log) + 1:03d}"
    qa_entry = {
        "id": q_id,
        "question": last_ba_msg,
        "answer": client_answer,
        "round": current_round,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    qa_log.append(qa_entry)
    save_json(qa_file, qa_log)

    # Append client turn to message history
    messages_history.append({
        "id": str(uuid.uuid4()),
        "role": "user",
        "content": client_answer,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    checklist_covered = session_state.get("checklist_covered", [])
    checklist_missing = session_state.get("checklist_missing", [
        "problem",
        "personas",
        "journeys",
        "requirements",
        "data",
        "integrations",
        "timeline_budget",
        "scope",
        "success_metric",
    ])

    prompt = f"""PROJECT CONTEXT:
- Project Name: {intake_data.get('project_name')}
- What they are building: {intake_data.get('description')}
- Target Users: {intake_data.get('target_users')}
- Target Timeline: {intake_data.get('timeline')}
- Budget & Monthly Running Cost: {intake_data.get('budget')}

CURRENT DISCOVERY STATUS:
- Checklist Covered: {checklist_covered}
- Checklist Missing: {checklist_missing}
- Round: {current_round} of 6

QA HISTORY SO FAR:
{json.dumps(qa_log, indent=2)}

CLIENT'S NEW RESPONSE:
"{client_answer}"

INSTRUCTIONS FOR THIS TURN:
1. Briefly acknowledge what they just told you in your own words.
2. If this is Round 1 (permission granted), begin asking your first batch of questions (at most 3 questions, most-blocking first).
3. If this is subsequent rounds, ask at most 3 questions to clarify missing checklist items (turning vague words into numbers, using 5 Whys).
4. If round >= 6 or all discovery checklist items are covered, state that the discovery is complete and requirements will be generated, and set "ready_for_requirements": true.
5. End your response with the hidden state marker on its own line:
<!--BA_STATE:{{"checklist_covered":[...],"checklist_missing":[...],"round":{current_round},"ready_for_requirements":true_or_false}}-->"""

    raw_response = query_ollama(prompt=prompt, system=BA_SYSTEM_PROMPT)
    cleaned_reply = strip_ba_state_marker(raw_response)
    parsed_state = parse_ba_state(raw_response)

    ready_for_requirements = False
    if parsed_state:
        session_state["checklist_covered"] = parsed_state.get("checklist_covered", checklist_covered)
        session_state["checklist_missing"] = parsed_state.get("checklist_missing", checklist_missing)
        ready_for_requirements = parsed_state.get("ready_for_requirements", False)

    if current_round >= 6:
        ready_for_requirements = True

    session_state["ready_for_requirements"] = ready_for_requirements

    messages_history.append({
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "content": cleaned_reply,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    session_state["messages"] = messages_history
    save_json(state_file, session_state)

    # Step 4 trigger if ready
    if ready_for_requirements:
        try:
            generate_requirements_doc(session_id)
        except Exception as e:
            logger.error(f"Error auto-generating requirements.md: {e}")

    return {
        "message": cleaned_reply,
        "ready_for_requirements": ready_for_requirements,
        "session_id": session_id,
    }


@app.get("/ba/requirements/{session_id}")
def get_ba_requirements(session_id: str):
    """
    Returns the generated requirements.md content once it exists, 404 if not yet generated.
    """
    session_dir = get_session_dir(session_id)
    doc_file = os.path.join(session_dir, "docs", "requirements.md")

    if not os.path.exists(doc_file):
        # Check if session is ready and generate if not already written
        state_file = os.path.join(session_dir, "session_state.json")
        session_state = load_json(state_file, {})
        if session_state.get("ready_for_requirements", False):
            try:
                content = generate_requirements_doc(session_id)
                return {"session_id": session_id, "content": content}
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to generate requirements: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Requirements document has not been generated yet.",
        )

    try:
        with open(doc_file, "r", encoding="utf-8") as f:
            content = f.read()
        return {"session_id": session_id, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading requirements.md: {e}")


@app.get("/ba/sessions")
def list_ba_sessions():
    """
    Lists all BA sessions under DATA_PROJECTS_DIR with project name, timestamps, and status.
    """
    if not os.path.exists(DATA_PROJECTS_DIR):
        return []

    sessions = []
    try:
        for item in os.listdir(DATA_PROJECTS_DIR):
            session_dir = os.path.join(DATA_PROJECTS_DIR, item)
            if not os.path.isdir(session_dir):
                continue

            intake_file = os.path.join(session_dir, "intake.json")
            if not os.path.exists(intake_file):
                continue

            intake_data = load_json(intake_file, {})
            state_file = os.path.join(session_dir, "session_state.json")
            session_state = load_json(state_file, {})
            doc_file = os.path.join(session_dir, "docs", "requirements.md")
            has_requirements = os.path.exists(doc_file)

            # Determine latest mtime among files in session_dir
            mtime = os.path.getmtime(session_dir)
            for fname in ["session_state.json", "qa_log.json", "intake.json"]:
                fpath = os.path.join(session_dir, fname)
                if os.path.exists(fpath):
                    mtime = max(mtime, os.path.getmtime(fpath))
            if has_requirements:
                mtime = max(mtime, os.path.getmtime(doc_file))

            updated_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
            created_at = intake_data.get("created_at", updated_at)

            sessions.append({
                "session_id": item,
                "project_name": intake_data.get("project_name", "Untitled Project"),
                "description": intake_data.get("description", ""),
                "created_at": created_at,
                "updated_at": updated_at,
                "ready_for_requirements": session_state.get("ready_for_requirements", False) or has_requirements,
                "has_requirements": has_requirements,
                "round": session_state.get("round", 0),
            })
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        return []

    # Sort most recently updated first
    sessions.sort(key=lambda s: s["updated_at"], reverse=True)
    return sessions


@app.get("/ba/session/{session_id}")
def get_ba_session(session_id: str):
    """
    Returns a session's full intake, conversation messages, qa_log, and requirements status.
    """
    session_dir = get_session_dir(session_id)
    intake_file = os.path.join(session_dir, "intake.json")
    state_file = os.path.join(session_dir, "session_state.json")
    qa_file = os.path.join(session_dir, "qa_log.json")
    doc_file = os.path.join(session_dir, "docs", "requirements.md")

    if not os.path.exists(intake_file):
        raise HTTPException(status_code=404, detail="Session not found")

    intake_data = load_json(intake_file, {})
    session_state = load_json(state_file, {})
    qa_log = load_json(qa_file, [])
    has_requirements = os.path.exists(doc_file)
    requirements_content = None

    if has_requirements:
        try:
            with open(doc_file, "r", encoding="utf-8") as f:
                requirements_content = f.read()
        except Exception as e:
            logger.warning(f"Failed to read requirements.md: {e}")

    messages = session_state.get("messages", [])

    # If messages is empty but qa_log exists, reconstruct messages for display
    if not messages and qa_log:
        for item in qa_log:
            if item.get("question"):
                messages.append({
                    "id": str(uuid.uuid4()),
                    "role": "assistant",
                    "content": item["question"],
                    "timestamp": item.get("timestamp", datetime.now(timezone.utc).isoformat()),
                })
            if item.get("answer"):
                messages.append({
                    "id": str(uuid.uuid4()),
                    "role": "user",
                    "content": item["answer"],
                    "timestamp": item.get("timestamp", datetime.now(timezone.utc).isoformat()),
                })

    return {
        "session_id": session_id,
        "intake": intake_data,
        "state": session_state,
        "qa_log": qa_log,
        "messages": messages,
        "ready_for_requirements": session_state.get("ready_for_requirements", False) or has_requirements,
        "has_requirements": has_requirements,
        "requirements_content": requirements_content,
    }


if __name__ == "__main__":
    port = int(os.environ.get("ENGINE_PORT", 8765))
    logger.info(f"Starting Autonoma Python Engine on http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
