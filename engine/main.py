import os
import sys
import time
import logging
import json
import uuid
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, status, Header
from fastapi.responses import HTMLResponse
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
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from prompts.ba_system_prompt import BA_SYSTEM_PROMPT

# Import Unified LLM Client (Groq default, Ollama fallback)
try:
    from llm_client import default_llm_client, query_llm, GroqKeyMissingError, load_pricing_config, OLLAMA_DEFAULT_MODEL
except ImportError:
    try:
        from engine.llm_client import default_llm_client, query_llm, GroqKeyMissingError, load_pricing_config, OLLAMA_DEFAULT_MODEL
    except ImportError:
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from llm_client import default_llm_client, query_llm, GroqKeyMissingError, load_pricing_config, OLLAMA_DEFAULT_MODEL

# Import Specialist Skill Registry
try:
    from skill_registry import (
        get_skill_registry,
        detect_specialist_needs,
        attach_skill_pack,
        detach_skill_pack,
        assemble_agent_prompt,
        save_agent_profile_to_db,
        get_agent_profile_from_db,
        init_agents_db,
    )
except ImportError:
    try:
        from engine.skill_registry import (
            get_skill_registry,
            detect_specialist_needs,
            attach_skill_pack,
            detach_skill_pack,
            assemble_agent_prompt,
            save_agent_profile_to_db,
            get_agent_profile_from_db,
            init_agents_db,
        )
    except ImportError:
        get_skill_registry = None

# Import HR, Recruiter, and Budget modules (Chapters 6, 22.4, 23.4-23.6, 26.4)
try:
    from hr import generate_hr_team_plan
    from recruiter import execute_recruiter_hiring
    from budget import (
        get_gate2_state,
        save_gate2_approval_record,
        approve_gate2,
        request_changes_gate2,
        check_budget_guard,
        raise_budget,
        recompute_budget_step16,
        enforce_gate2_server_side,
    )
    from skill_registry import get_agents_by_project
    from scrum import (
        generate_backlog_and_plan,
        generate_daily_report,
        calculate_critical_path,
        calculate_load_balance,
        generate_gantt_chart_data,
        init_tasks_db,
    )
    from readiness import (
        run_readiness_review,
        get_readiness_state,
        enforce_readiness_server_side,
        init_reviews_db,
    )
except ImportError:
    try:
        from engine.hr import generate_hr_team_plan
        from engine.recruiter import execute_recruiter_hiring
        from engine.budget import (
            get_gate2_state,
            save_gate2_approval_record,
            approve_gate2,
            request_changes_gate2,
            check_budget_guard,
            raise_budget,
        raise_budget,
            recompute_budget_step16,
            enforce_gate2_server_side,
        )
        from engine.skill_registry import get_agents_by_project
        from engine.scrum import (
            generate_backlog_and_plan,
            generate_daily_report,
            calculate_critical_path,
            calculate_load_balance,
            generate_gantt_chart_data,
            init_tasks_db,
        )
        from engine.readiness import (
            run_readiness_review,
            get_readiness_state,
            enforce_readiness_server_side,
            init_reviews_db,
        )
    except ImportError:
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from hr import generate_hr_team_plan
        from recruiter import execute_recruiter_hiring
        from budget import (
            get_gate2_state,
            save_gate2_approval_record,
            approve_gate2,
            request_changes_gate2,
            check_budget_guard,
            raise_budget,
        raise_budget,
            recompute_budget_step16,
            enforce_gate2_server_side,
        )
        from skill_registry import get_agents_by_project
        from scrum import (
            generate_backlog_and_plan,
            generate_daily_report,
            calculate_critical_path,
            calculate_load_balance,
            generate_gantt_chart_data,
            init_tasks_db,
        )
        from readiness import (
            run_readiness_review,
            get_readiness_state,
            enforce_readiness_server_side,
            init_reviews_db,
        )

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
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL") or OLLAMA_DEFAULT_MODEL

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PROJECTS_DIR = os.path.join(PROJECT_ROOT, "data", "projects")
CONVERSATION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conversation.json")

BA_STATE_PATTERN = re.compile(r"<!--\s*BA_STATE:\s*(\{.*?\})\s*-->", re.DOTALL)


# Data helper utilities
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")


def validate_session_id(session_id: str) -> str:
    """Project ids become folder names: reject anything that could escape data/projects (Handbook 29.1)."""
    if not isinstance(session_id, str) or not SESSION_ID_RE.match(session_id):
        raise HTTPException(status_code=400, detail=f"Invalid project id: {session_id!r}")
    return session_id


def get_session_dir(session_id: str) -> str:
    path = os.path.join(DATA_PROJECTS_DIR, validate_session_id(session_id))
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
# 4. Functional Requirements (FR-01, FR-02, etc.)
   CRITICAL CLASSIFICATION RULE:
   - ONLY list interactive user capabilities or business logic workflows explicitly asked for in the Q&A log.
   - Format: - FR-01: <Feature name> (Must Have / Should Have / Could Have / Won't Have) [Source: Q-###]
   - NEVER put latency, response times, database engines, storage mechanisms, privacy rules, offline operation, platform compatibility (OS, Windows, macOS), or accessibility (WCAG) in FRs. Those are strictly NFRs!
   - NEVER invent or copy example features from other projects. Only extract what this user requested.

# 5. Non-Functional Requirements (NFR-01, NFR-02, etc.)
   CRITICAL CLASSIFICATION RULE:
   - All quality constraints, performance numbers, database and storage choices, offline operation, and platform compatibility MUST go here.
   - Examples of NFR categories to look for in the client answers:
     - Performance / Latency (response time targets) [Source: Q-###]
     - Storage & Privacy (local data storage, zero cloud uploads) [Source: Q-###]
     - Capacity / Concurrency (record volume, snippet volume) [Source: Q-###]
     - Platform Compatibility (desktop OS, offline operation) [Source: Q-###]
     - Accessibility (accessibility compliance) [Source: Q-###]
   - Every NFR must specify a concrete number or verifiable yes/no check, and cite its source [Source: Q-###].
   - Only list constraints that are relevant to this client's application.

# 6. Data Requirements & Entities
# 7. Integrations & External Services
# 8. Timeline & Budget
# 9. v1 Scope vs Later
# 10. Definition of Success & Key Metrics
# 11. Assumptions (ASM-01, ASM-02, etc.)
   CRITICAL ASSUMPTIONS RULE:
   - Each ASM-## must be written as a single, complete, specific sentence on one line.
   - NEVER use placeholder variables (e.g. x, y, TBD). State concrete, verifiable assumptions.
   - NEVER create fragment lines like 'Reason: ...' or 'Risk: ...' as separate lines. Include any rationale in the single sentence.

GROUNDING RULE: Every requirement and key decision must cite the Q- entry it came from. Never invent client facts, dates, or numbers.
Output ONLY the markdown content for requirements.md. Do not wrap in extra conversational commentary or append state markers."""

    try:
        raw_response = query_llm(
            prompt=prompt,
            system=BA_SYSTEM_PROMPT,
            role="ba",
            session_id=session_id,
            task_id="generate_requirements"
        )
    except GroqKeyMissingError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
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
    groq_configured: Optional[bool] = False
    groq_online: Optional[bool] = False
    masked_groq_key: Optional[str] = ""
    active_generator_model: Optional[str] = ""
    active_judge_model: Optional[str] = ""
    default_provider: Optional[str] = "groq"


class LLMSettingsUpdateRequest(BaseModel):
    role: str
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class LocalOnlyToggleRequest(BaseModel):
    session_id: str
    local_only: bool


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
    """Local-first status (Handbook 22.6): Ollama health always; Groq only when cloud is enabled."""
    cloud_on = default_llm_client.cloud_enabled()
    gen_route = default_llm_client.resolve_route("pm")
    judge_route = default_llm_client.resolve_judge_route("pm")
    groq_online = bool(default_llm_client.fetch_groq_models()) if cloud_on else False

    ollama_online = False
    version = "unknown"
    try:
        v_res = requests.get(f"{OLLAMA_HOST}/api/version", timeout=1.5)
        if v_res.status_code == 200:
            ollama_online = True
            version = v_res.json().get("version", "unknown")
    except Exception:
        pass
    local_models = default_llm_client.list_ollama_models(force_refresh=True) if ollama_online else []
    model_ready = gen_route["provider"] != "none"

    if not ollama_online and not groq_online:
        status_val, msg = "error", f"Ollama is not running at {OLLAMA_HOST}. Start it with `ollama serve`."
    elif not model_ready:
        status_val, msg = "error", gen_route["downgrade_note"]
    elif any(default_llm_client.resolve_route(r)["downgraded"] for r in ("architect", "judge", "backend")):
        status_val = "warning"
        msg = (f"Running locally on {gen_route['model']}. Some roles are below their target tier; "
               f"install a larger local model for better quality.")
    else:
        status_val, msg = "ready", f"Running locally (Generator: {gen_route['model']}, Judge: {judge_route['model']})"
    if cloud_on:
        msg += f" Cloud enabled (Groq {'online' if groq_online else 'unreachable'})."

    return StatusResponse(
        status=status_val,
        ollama_online=ollama_online,
        model_ready=model_ready,
        version=version,
        groq_configured=default_llm_client.is_groq_configured(),
        groq_online=groq_online,
        masked_groq_key=default_llm_client.get_masked_api_key(),
        active_generator_model=gen_route["model"],
        active_judge_model=judge_route["model"],
        default_provider="groq" if cloud_on else "ollama",
        message=msg + (f" Installed local models: {', '.join(m['name'] for m in local_models)}." if local_models else ""),
    )


@app.get("/models")
def get_models_endpoint():
    """
    Active route per role and Judge validity per Handbook 14.1.2 & 22.4 rule 3:
    the Judge uses a different model from each author where possible and is never weaker.
    """
    agent_validations = {}
    all_valid = True
    for role in ["ba", "pm", "architect", "designer", "hr", "recruiter", "scrum", "tech-lead", "backend", "frontend", "qa", "devops"]:
        gen = default_llm_client.resolve_route(role)
        judge = default_llm_client.resolve_judge_route(role)
        valid = not judge["weaker_than_author"]
        all_valid = all_valid and valid
        agent_validations[role] = {
            "generator_model": gen["model"],
            "generator_capability_score": gen["capability"],
            "judge_model": judge["model"],
            "judge_capability_score": judge["capability"],
            "different_model": not judge["same_model_as_author"],
            "is_valid": valid,
            "downgrade_note": gen["downgrade_note"],
        }
    return {
        "status": "success",
        "cloud_enabled": default_llm_client.cloud_enabled(),
        "models": default_llm_client.fetch_groq_models(),
        "local_models": default_llm_client.list_ollama_models(),
        "role_configs": default_llm_client.role_configs,
        "judge_validation": {
            "all_roles_valid": all_valid,
            "agent_validations": agent_validations,
            "note": ("Judge is never weaker than the author; a different model is used where one is installed."
                     if all_valid else "A Judge would be weaker than its author: install a larger local model."),
        },
    }


class CloudToggleRequest(BaseModel):
    enabled: bool


@app.post("/settings/cloud")
def toggle_cloud(req: CloudToggleRequest):
    """Cloud is opt-in (Handbook 1.4). While disabled, the engine makes no outbound network calls."""
    default_llm_client.set_cloud_enabled(req.enabled)
    return {"status": "ok", "cloud_enabled": default_llm_client.cloud_enabled()}


@app.get("/settings/llm")
def get_llm_settings(session_id: Optional[str] = None):
    return default_llm_client.get_settings(session_id=session_id)


@app.post("/settings/llm")
def update_llm_settings(req: LLMSettingsUpdateRequest):
    updated = default_llm_client.update_role_config(
        role=req.role,
        provider=req.provider,
        model=req.model,
        temperature=req.temperature,
        max_tokens=req.max_tokens
    )
    return {"status": "ok", "role": req.role, "config": updated}


@app.post("/settings/local-only")
def toggle_local_only(req: LocalOnlyToggleRequest):
    default_llm_client.set_project_local_only(req.session_id, req.local_only)
    return {
        "status": "ok",
        "session_id": req.session_id,
        "local_only": req.local_only,
        "message": f"Local-only mode set to {req.local_only} for project {req.session_id}"
    }


@app.get("/settings/fallbacks")
def get_fallbacks_endpoint():
    return {
        "status": "ok",
        "fallbacks": default_llm_client.get_fallbacks()
    }


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

    user_msg = {
        "id": str(uuid.uuid4()),
        "role": "user",
        "content": prompt,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "meta": None,
    }
    conversation_store.append(user_msg)
    save_conversation(conversation_store)

    start_t = time.time()
    try:
        response_text = query_llm(
            prompt=prompt,
            role="general",
            force_model=req.model if req.model else None
        )
        duration = time.time() - start_t
        token_count = len(response_text.split()) * 2

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
    except GroqKeyMissingError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error communicating with LLM provider: {str(e)}",
        )


# -----------------------------------------------------------------------------
# Business Analyst (BA) Workflow Endpoints
# -----------------------------------------------------------------------------

@app.post("/ba/start")
def ba_start(req: IntakeRequest, authorization: Optional[str] = Header(None)):
    """
    Creates a new BA session, stores intake to data/projects/<session_id>/intake.json,
    and calls Ollama with BA_SYSTEM_PROMPT to produce the round 0 opening greeting + intro + permission ask.
    """
    current_user = office_auth.require_user(authorization)
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
        # New projects follow the router: cloud first when cloud is enabled, local otherwise.
        "local_only": not default_llm_client.cloud_enabled(),
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

    try:
        raw_response = query_llm(
            prompt=prompt,
            system=BA_SYSTEM_PROMPT,
            role="ba",
            session_id=session_id,
            task_id="ba_start"
        )
    except GroqKeyMissingError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    cleaned_message = strip_ba_state_marker(raw_response)

    # Store first message in session messages
    initial_state["messages"].append({
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "content": cleaned_message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    save_json(os.path.join(session_dir, "session_state.json"), initial_state)

    if current_user:
        office_auth.assign_project(session_id, current_user["id"])
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

    # Helper: Detect conversational non-answers (Handbook Quality Bar & DOD)
    def _is_non_answer(text: str) -> bool:
        clean = re.sub(r"[^\w\s]", "", text.strip()).lower()
        non_answers = {
            "yes", "no", "sure", "ok", "okay", "proceed",
            "yes please proceed", "please proceed", "go ahead",
            "yes lets begin", "lets begin", "sounds good",
            "continue", "looks good", "start", "yes go ahead",
            "yes proceed", "yes start", "yep", "yeah", "agree",
            "ready", "im ready", "i am ready", "let us begin",
            "sounds good please proceed", "yes please", "sure thing"
        }
        if clean in non_answers:
            return True
        words = clean.split()
        if len(words) <= 4 and any(w in words for w in ["proceed", "begin", "start", "continue", "ahead"]):
            return True
        return False

    # Append to real qa_log.json array ONLY if not a conversational non-answer
    if not _is_non_answer(client_answer):
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
    else:
        logger.info(f"Skipping non-answer from qa_log.json: '{client_answer}'")

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

    try:
        raw_response = query_llm(
            prompt=prompt,
            system=BA_SYSTEM_PROMPT,
            role="ba",
            session_id=session_id,
            task_id=f"ba_round_{current_round}"
        )
    except GroqKeyMissingError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
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
        qa_file = os.path.join(session_dir, "qa_log.json")
        qa_log = load_json(qa_file, [])
        if session_state.get("ready_for_requirements", False) or len(qa_log) >= 2:
            try:
                content = generate_requirements_doc(session_id)
                session_state["ready_for_requirements"] = True
                save_json(state_file, session_state)
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
def list_ba_sessions(authorization: Optional[str] = Header(None)):
    """
    Lists all BA sessions under DATA_PROJECTS_DIR with project name, timestamps, and status.
    """
    if not os.path.exists(DATA_PROJECTS_DIR):
        return []
    current_user = office_auth.require_user(authorization)
    mine = set(office_auth.projects_of(current_user["id"])) if current_user else None

    sessions = []
    try:
        for item in os.listdir(DATA_PROJECTS_DIR):
            if mine is not None and item not in mine:
                continue
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
def get_ba_session(session_id: str, authorization: Optional[str] = Header(None)):
    """
    Returns a session's full intake, conversation messages, qa_log, and requirements status.
    """
    office_auth.require_owner(session_id, office_auth.require_user(authorization))
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


@app.get("/office/status/{session_id}")
def get_office_status(session_id: str):
    session_dir = get_session_dir(session_id)
    intake_data = load_json(os.path.join(session_dir, "intake.json"), default={})
    ba_state = load_json(os.path.join(session_dir, "ba_state.json"), default={})
    if not ba_state:
        ba_state = load_json(os.path.join(session_dir, "state.json"), default={})
    qa_log = load_json(os.path.join(session_dir, "qa_log.json"), default=[])
    req_path = os.path.join(session_dir, "docs", "requirements.md")
    has_requirements = os.path.exists(req_path)

    pm_state = load_json(os.path.join(session_dir, "pm_state.json"), default={})
    prd_path = os.path.join(session_dir, "docs", "prd.md")
    has_prd = os.path.exists(prd_path)

    # BA status
    if has_requirements:
        ba_status = "done"
    elif len(qa_log) > 0:
        ba_status = "waiting-on-you"
    else:
        ba_status = "idle"

    # PM status
    if has_prd:
        pm_status = "done"
    elif pm_state.get("started", False):
        pm_status = "waiting-on-you"
    else:
        pm_status = "idle"

    # Gate 1, Architect & Designer status
    gate1_state = load_json(os.path.join(session_dir, "gate1_state.json"), default={})
    gate1_approved = gate1_state.get("approved", False)
    arch_state = load_json(os.path.join(session_dir, "architect_state.json"), default={})
    arch_path = os.path.join(session_dir, "docs", "architecture.md")
    has_arch = os.path.exists(arch_path)
    feasibility_path = os.path.join(session_dir, "docs", "feasibility.md")
    has_feasibility = os.path.exists(feasibility_path)

    designer_state = load_json(os.path.join(session_dir, "designer_state.json"), default={})
    app_flow_path = os.path.join(session_dir, "docs", "app-flow.md")
    has_designer = os.path.exists(app_flow_path)

    if has_arch:
        arch_status = "done"
    elif gate1_approved:
        arch_status = "waiting-on-you"
    elif has_prd:
        arch_status = "idle"
    else:
        arch_status = "idle"

    if has_designer:
        designer_status = "done"
    elif gate1_approved:
        designer_status = "waiting-on-you"
    elif has_prd:
        designer_status = "idle"
    else:
        designer_status = "idle"

    # Stage 4 Staffing (HR & Recruiter) & Gate 2 status
    team_plan_path = os.path.join(session_dir, "docs", "team-plan.json")
    has_team_plan = os.path.exists(team_plan_path)
    staffing_report_path = os.path.join(session_dir, "docs", "staffing-report.md")
    has_staffing_report = os.path.exists(staffing_report_path)

    gate2_state = get_gate2_state(session_id)
    gate2_approved = gate2_state.get("approved", False)

    if has_team_plan:
        hr_status = "done"
    elif has_arch:
        hr_status = "waiting-on-you"
    else:
        hr_status = "idle"

    if has_staffing_report:
        recruiter_status = "done"
    elif has_team_plan:
        recruiter_status = "waiting-on-you"
    else:
        recruiter_status = "idle"

    # Specialist skills attachments
    attachments = load_json(os.path.join(session_dir, "agent_attachments.json"), default={})

    return {
        "session_id": session_id,
        "project_name": intake_data.get("project_name", "Untitled Project"),
        "description": intake_data.get("description", ""),
        "target_users": intake_data.get("target_users", ""),
        "timeline": intake_data.get("timeline", ""),
        "budget": intake_data.get("budget", ""),
        "gate1": {
            "status": gate1_state.get("status", "pending" if has_prd else "waiting_for_prd"),
            "approved": gate1_approved,
            "approved_at": gate1_state.get("approved_at"),
            "has_feasibility": has_feasibility,
            "has_prd": has_prd,
        },
        "gate2": gate2_state,
        "has_team_plan": has_team_plan,
        "has_staffing_report": has_staffing_report,
        "agents": {
            "ba": {
                "id": "ba",
                "role": "Business Analyst",
                "abbr": "BA",
                "status": ba_status,
                "has_output": has_requirements,
                "output_name": "docs/requirements.md",
                "output_type": "markdown",
                "message_count": len(ba_state.get("messages", [])),
                "qa_count": len(qa_log),
                "ready_for_handoff": has_requirements,
                "can_start": True,
                "attached_skills": attachments.get("ba", []),
            },
            "pm": {
                "id": "pm",
                "role": "Product Manager",
                "abbr": "PM",
                "status": pm_status,
                "has_output": has_prd,
                "output_name": "docs/prd.md",
                "output_type": "markdown",
                "message_count": len(pm_state.get("messages", [])),
                "ready_for_handoff": has_prd,
                "can_start": has_requirements and not has_prd,
                "attached_skills": attachments.get("pm", []),
            },
            "architect": {
                "id": "architect",
                "role": "Solution Architect",
                "abbr": "ARCH",
                "status": arch_status,
                "has_output": has_arch,
                "output_name": "docs/architecture.md",
                "output_type": "markdown",
                "message_count": 1 if has_arch else 0,
                "is_unlocked": gate1_approved or has_arch,
                "can_start": gate1_approved and not has_arch,
                "attached_skills": attachments.get("architect", []),
            },
            "designer": {
                "id": "designer",
                "role": "UI/UX Designer",
                "abbr": "DES",
                "status": designer_status,
                "has_output": has_designer,
                "output_name": "docs/app-flow.md",
                "output_type": "markdown",
                "message_count": 1 if has_designer else 0,
                "is_unlocked": gate1_approved or has_designer,
                "can_start": gate1_approved and not has_designer,
                "attached_skills": attachments.get("designer", []),
            },
            "hr": {
                "id": "hr",
                "role": "Staffing Planner",
                "abbr": "HR",
                "status": hr_status,
                "has_output": has_team_plan,
                "output_name": "docs/team-plan.json",
                "output_type": "json",
                "message_count": 1 if has_team_plan else 0,
                "is_unlocked": has_arch,
                "can_start": has_arch and not has_team_plan,
                "attached_skills": attachments.get("hr", []),
            },
            "recruiter": {
                "id": "recruiter",
                "role": "Technical Recruiter",
                "abbr": "REC",
                "status": recruiter_status,
                "has_output": has_staffing_report,
                "output_name": "docs/staffing-report.md",
                "output_type": "markdown",
                "message_count": 1 if has_staffing_report else 0,
                "is_unlocked": has_team_plan,
                "can_start": has_team_plan and not has_staffing_report,
                "attached_skills": attachments.get("recruiter", []),
            },
            "engineer": {
                "id": "engineer",
                "role": "Full-Stack Engineer",
                "abbr": "ENG",
                "status": "idle",
                "has_output": False,
                "output_name": "src/",
                "output_type": "code",
                "message_count": 0,
                "can_start": False,
                "is_unlocked": gate2_approved,
                "attached_skills": attachments.get("engineer", attachments.get("backend", [])),
            },
            "qa": {
                "id": "qa",
                "role": "QA Engineer",
                "abbr": "QA",
                "status": "idle",
                "has_output": False,
                "output_name": "tests/",
                "output_type": "tests",
                "message_count": 0,
                "can_start": False,
                "is_unlocked": gate2_approved,
                "attached_skills": attachments.get("qa", []),
            },
        },
    }



# =========================================================================
# Specialist Skill Registry Endpoints (Chapter 6 & 23)
# =========================================================================

@app.get("/skills/packs")
def list_skill_packs():
    """Lists all valid registered specialist skill packs with metadata."""
    if not get_skill_registry:
        raise HTTPException(status_code=500, detail="Skill registry not available")
    registry = get_skill_registry()
    return {
        "packs": registry.list_packs(),
        "total": len(registry.packs),
        "broken_count": len(registry.broken_packs),
    }


@app.get("/skills/broken")
def list_broken_skill_packs():
    """Reports any broken or invalid skill packs on disk."""
    if not get_skill_registry:
        raise HTTPException(status_code=500, detail="Skill registry not available")
    registry = get_skill_registry()
    return {"broken_packs": registry.get_broken_packs()}


@app.post("/skills/detect/{session_id}")
def detect_project_specialists(session_id: str):
    """
    Deterministically detects specialist skill requirements from prd.md,
    requirements.md, and architecture.md without consuming LLM tokens.
    """
    if not detect_specialist_needs:
        raise HTTPException(status_code=500, detail="Detection engine not available")

    session_dir = get_session_dir(session_id)
    req_file = os.path.join(session_dir, "docs", "requirements.md")
    prd_file = os.path.join(session_dir, "docs", "prd.md")
    arch_file = os.path.join(session_dir, "docs", "architecture.md")

    req_text = ""
    prd_text = ""
    arch_text = ""

    if os.path.exists(req_file):
        with open(req_file, "r", encoding="utf-8") as f:
            req_text = f.read()
    if os.path.exists(prd_file):
        with open(prd_file, "r", encoding="utf-8") as f:
            prd_text = f.read()
    if os.path.exists(arch_file):
        with open(arch_file, "r", encoding="utf-8") as f:
            arch_text = f.read()

    result = detect_specialist_needs(
        prd_text=prd_text,
        requirements_text=req_text,
        architecture_text=arch_text,
    )

    # Persist detection results in project session
    save_json(os.path.join(session_dir, "specialist_needs.json"), result)
    return result


class SkillAttachRequest(BaseModel):
    session_id: str
    role: str
    pack_id: str
    agent_id: Optional[str] = None


@app.post("/skills/attach")
def attach_skill_endpoint(req: SkillAttachRequest):
    """
    Attaches a specialist pack to an agent profile with tool-permission validation.
    Returns 'blocked' if the pack does not exist.
    """
    if not attach_skill_pack:
        raise HTTPException(status_code=500, detail="Attach functionality not available")

    session_dir = get_session_dir(req.session_id)
    agent_id = req.agent_id or f"{req.role}-1"

    # Load agent profile or build default
    profile = get_agent_profile_from_db(agent_id) if get_agent_profile_from_db else None
    if not profile:
        route = default_llm_client.resolve_route(req.role, session_id=req.session_id)
        profile = {
            "agent_id": agent_id,
            "project_id": req.session_id,
            "name": req.role.capitalize(),
            "role": req.role.lower(),
            "seat_id": f"ROLE-{req.role.upper()}",
            "reports_to": "tech-lead-1",
            "tier": route["target_tier"],
            "provider": route["provider"],
            "model": route["model"],
            "tools": ["read_file", "write_file"],
            "skill_packs": [],
            "fs_scope": f"projects/{req.session_id}/",
            "token_cap": 400000,
            "status": "idle",
        }

    attach_res = attach_skill_pack(agent_profile=profile, pack_id=req.pack_id)

    if attach_res.get("status") == "blocked":
        # Missing pack per Handbook Chapter 6: return blocked naming the pack
        return {
            "status": "blocked",
            "missing_pack": attach_res.get("missing_pack"),
            "error": attach_res.get("error"),
        }

    if attach_res.get("status") == "rejected":
        raise HTTPException(status_code=400, detail=attach_res.get("error"))

    # Update session attachments file
    attachments_path = os.path.join(session_dir, "agent_attachments.json")
    attachments = load_json(attachments_path, default={})
    role_skills = attachments.get(req.role, [])
    if req.pack_id not in role_skills:
        role_skills.append(req.pack_id)
    attachments[req.role] = role_skills
    save_json(attachments_path, attachments)

    # Persist in DB
    if save_agent_profile_to_db:
        save_agent_profile_to_db(attach_res["agent_profile"])

    return attach_res


@app.post("/skills/detach")
def detach_skill_endpoint(req: SkillAttachRequest):
    """Detaches a specialist pack from an agent profile."""
    if not detach_skill_pack:
        raise HTTPException(status_code=500, detail="Detach functionality not available")

    session_dir = get_session_dir(req.session_id)
    agent_id = req.agent_id or f"{req.role}-1"

    profile = get_agent_profile_from_db(agent_id) if get_agent_profile_from_db else None
    if not profile:
        profile = {
            "agent_id": agent_id,
            "project_id": req.session_id,
            "role": req.role.lower(),
            "tools": ["read_file", "write_file"],
            "skill_packs": [],
        }

    detach_res = detach_skill_pack(agent_profile=profile, pack_id=req.pack_id)

    # Update session attachments file
    attachments_path = os.path.join(session_dir, "agent_attachments.json")
    attachments = load_json(attachments_path, default={})
    role_skills = attachments.get(req.role, [])
    if req.pack_id in role_skills:
        role_skills = [p for p in role_skills if p != req.pack_id]
    attachments[req.role] = role_skills
    save_json(attachments_path, attachments)

    if save_agent_profile_to_db:
        save_agent_profile_to_db(detach_res["agent_profile"])

    return detach_res


@app.get("/skills/prompt/{role}")
def preview_assembled_prompt(role: str, packs: Optional[str] = None):
    """Previews assembled prompt with section breakdown and token count."""
    if not assemble_agent_prompt:
        raise HTTPException(status_code=500, detail="Prompt assembler not available")

    pack_list = [p.strip() for p in packs.split(",") if p.strip()] if packs else []
    result = assemble_agent_prompt(role=role, attached_pack_ids=pack_list)
    return result



# Initialize PM agent module and routes
try:
    from pm import init_pm_routes
except ImportError:
    try:
        from engine.pm import init_pm_routes
    except ImportError:
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from pm import init_pm_routes

def make_role_query_fn(role: str):
    def _role_query(prompt: str, system: Optional[str] = None, session_id: Optional[str] = None, **kwargs) -> str:
        return query_llm(
            prompt=prompt,
            system=system,
            role=role,
            session_id=session_id,
            **kwargs
        )
    return _role_query

init_pm_routes(
    main_app=app,
    get_session_dir_fn=get_session_dir,
    load_json_fn=load_json,
    save_json_fn=save_json,
    query_ollama_fn=make_role_query_fn("pm"),
    data_projects_dir=DATA_PROJECTS_DIR,
    generate_requirements_fn=generate_requirements_doc,
)

# Initialize Architect agent module and routes
try:
    from architect import init_architect_routes
except ImportError:
    try:
        from engine.architect import init_architect_routes
    except ImportError:
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from architect import init_architect_routes

init_architect_routes(
    main_app=app,
    get_session_dir_fn=get_session_dir,
    load_json_fn=load_json,
    save_json_fn=save_json,
    query_ollama_fn=make_role_query_fn("architect"),
    data_projects_dir=DATA_PROJECTS_DIR,
)

# Initialize Designer agent module and routes
try:
    from designer import init_designer_routes
except ImportError:
    try:
        from engine.designer import init_designer_routes
    except ImportError:
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from designer import init_designer_routes

init_designer_routes(
    main_app=app,
    get_session_dir_fn=get_session_dir,
    load_json_fn=load_json,
    save_json_fn=save_json,
    query_ollama_fn=make_role_query_fn("designer"),
    data_projects_dir=DATA_PROJECTS_DIR,
)


# =========================================================================
# Stage 4 Staffing (HR & Recruiter), Gate 2, & Budget Endpoints
# Handbook Chapters 6 (6.1-6.3), 2.7.5 (steps 14-17), 5.1.6, 22.4, 24.1, 26.4
# =========================================================================

class Gate2ApprovalRequest(BaseModel):
    session_id: str
    client_notes: Optional[str] = None


class Gate2ChangeRequest(BaseModel):
    session_id: str
    feedback: str


@app.post("/hr/plan/{session_id}")
def run_hr_team_plan(session_id: str):
    """
    Executes HR Staffing Planner engine to generate docs/team-plan.json
    per Handbook Chapter 6.1 and 6.2.
    """
    try:
        plan = generate_hr_team_plan(session_id, data_projects_dir=DATA_PROJECTS_DIR)
        return plan
    except RuntimeError as re:
        raise HTTPException(status_code=400, detail=str(re))
    except Exception as e:
        logger.error(f"Error in HR staffing plan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"HR staffing plan failed: {str(e)}")


@app.get("/hr/team-plan/{session_id}")
def get_hr_team_plan(session_id: str):
    """Retrieves docs/team-plan.json for a project."""
    session_dir = get_session_dir(session_id)
    plan_path = os.path.join(session_dir, "docs", "team-plan.json")
    if not os.path.exists(plan_path):
        raise HTTPException(status_code=404, detail="Team plan not generated yet")
    return load_json(plan_path)


@app.post("/recruiter/hire/{session_id}")
def run_recruiter_hiring(session_id: str):
    """
    Executes Recruiter hiring engine per Handbook Chapter 6.1 and 6.3:
    1. Reads team-plan.json requisitions.
    2. Matches skill packs (spec-only or blocked).
    3. Resolves model tiers dynamically via live GET /models.
    4. Enforces least-privilege tools and sandboxes.
    5. Derives token caps with 20% rework buffer.
    6. Persists hired agents into SQLite 'agents' table.
    7. Synthesizes docs/staffing-report.md and registers Gate 2 approval.
    """
    try:
        result = execute_recruiter_hiring(session_id, data_projects_dir=DATA_PROJECTS_DIR)
        return result
    except RuntimeError as re:
        raise HTTPException(status_code=400, detail=str(re))
    except Exception as e:
        logger.error(f"Error in Recruiter hiring: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Recruiter hiring failed: {str(e)}")


@app.get("/recruiter/agents/{session_id}")
def get_recruiter_agents(session_id: str):
    """Returns all hired agents for a project from the SQLite agents table."""
    agents = get_agents_by_project(session_id)
    return {
        "session_id": session_id,
        "agents": agents,
        "count": len(agents)
    }


@app.get("/recruiter/report/{session_id}")
def get_recruiter_report(session_id: str):
    """Retrieves docs/staffing-report.md for a project."""
    session_dir = get_session_dir(session_id)
    report_path = os.path.join(session_dir, "docs", "staffing-report.md")
    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="Staffing report not generated yet")
    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()
    return {"session_id": session_id, "content": content}


@app.get("/gate2/status/{session_id}")
def get_gate2_status_endpoint(session_id: str):
    """Returns Gate 2 status, approvals table record, and SHA256 hashes."""
    return get_gate2_state(session_id)


@app.post("/gate2/approve")
def approve_gate2_endpoint(req: Gate2ApprovalRequest):
    """
    Approves Gate 2 staffing and budget plan (Handbook 2.7.5 Step 17).
    Records approval in SQLite 'approvals' table and unlocks Stage 5 (Scrum Master).
    """
    return approve_gate2(session_id=req.session_id, client_notes=req.client_notes)


@app.post("/gate2/request-changes")
def request_changes_gate2_endpoint(req: Gate2ChangeRequest):
    """
    Requests changes on Gate 2 staffing and budget plan (Handbook 2.7.5 & 2.5).
    Reopens HR/Recruiter and routes feedback as new Q- item to the BA.
    """
    return request_changes_gate2(session_id=req.session_id, feedback=req.feedback)


class BudgetRaiseRequest(BaseModel):
    session_id: str
    budget_limit_tokens: Optional[int] = None
    budget_limit_usd: Optional[float] = None
    note: Optional[str] = ""


@app.post("/budget/raise")
def raise_budget_endpoint(req: BudgetRaiseRequest):
    """Client raises the budget to resume a project paused at 100% (Handbook 26.4)."""
    return raise_budget(req.session_id, req.budget_limit_tokens, req.budget_limit_usd, req.note or "")


@app.get("/budget/status/{session_id}")
def get_budget_status_endpoint(session_id: str):
    """
    Returns token budget guard status (Handbook 26.4: warn at 80%, pause at 100%)
    and Step 16 budget recomputation (Handbook 5.1.6).
    """
    guard = check_budget_guard(session_id)
    recomputation = recompute_budget_step16(session_id)
    return {
        "session_id": session_id,
        "guard": guard,
        "recomputation": recomputation
    }


# ==============================================================================
# STAGE 5 SCRUM MASTER & TECH LEAD READINESS ENDPOINTS (Handbook Ch 9, 10.1.4, 2.7.6)
# ==============================================================================

@app.post("/scrum/start/{session_id}")
def start_scrum_stage(session_id: str):
    """
    Starts Stage 5 (Scrum Master).
    Enforces Gate 2 server-side: returns HTTP 403 if Gate 2 is not approved or invalidated.
    Generates docs/backlog.json, computes critical path, renders implementation-plan.md and Gantt chart.
    """
    enforce_gate2_server_side(session_id)
    try:
        result = generate_backlog_and_plan(session_id)
        return {
            "status": "success",
            "stage": "Stage 5 Scrum Master",
            "session_id": session_id,
            "message": "Gate 2 verified approved. Backlog and implementation plan generated successfully.",
            "data": result
        }
    except Exception as e:
        logger.error(f"Scrum Master generation failed for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scrum/backlog/{session_id}")
def get_scrum_backlog(session_id: str):
    """Returns current project backlog from docs/backlog.json."""
    session_dir = os.path.join("data", "projects", session_id)
    backlog_file = os.path.join(session_dir, "docs", "backlog.json")
    if os.path.exists(backlog_file):
        try:
            with open(backlog_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to read backlog.json: {e}")
    return {"stories": []}


@app.get("/scrum/plan/{session_id}")
def get_scrum_implementation_plan(session_id: str):
    """Returns docs/implementation-plan.md and scheduling metrics."""
    session_dir = os.path.join("data", "projects", session_id)
    plan_file = os.path.join(session_dir, "docs", "implementation-plan.md")
    content = ""
    if os.path.exists(plan_file):
        with open(plan_file, "r", encoding="utf-8") as f:
            content = f.read()

    backlog_file = os.path.join(session_dir, "docs", "backlog.json")
    stories = []
    if os.path.exists(backlog_file):
        try:
            with open(backlog_file, "r", encoding="utf-8") as f:
                stories = json.load(f).get("stories", [])
        except Exception:
            pass

    crit_info = calculate_critical_path(stories)
    load_info = calculate_load_balance(stories)

    return {
        "session_id": session_id,
        "content": content,
        "critical_path": crit_info,
        "load_balance": load_info
    }


@app.get("/scrum/gantt/{session_id}")
def get_scrum_gantt(session_id: str):
    """Returns Gantt chart data and Mermaid diagram for the backlog."""
    session_dir = os.path.join("data", "projects", session_id)
    backlog_file = os.path.join(session_dir, "docs", "backlog.json")
    stories = []
    if os.path.exists(backlog_file):
        try:
            with open(backlog_file, "r", encoding="utf-8") as f:
                stories = json.load(f).get("stories", [])
        except Exception:
            pass

    crit_info = calculate_critical_path(stories)
    gantt_info = generate_gantt_chart_data(stories, crit_info)
    return {
        "session_id": session_id,
        "gantt": gantt_info
    }


@app.get("/scrum/daily-report/{session_id}")
def get_scrum_daily_report(session_id: str, day: int = 1):
    """Returns the daily report (reports/day-NN.md)."""
    session_dir = os.path.join("data", "projects", session_id)
    report_file = os.path.join(session_dir, "reports", f"day-{day:02d}.md")
    if os.path.exists(report_file):
        with open(report_file, "r", encoding="utf-8") as f:
            return {"session_id": session_id, "day": day, "content": f.read()}

    report_content = generate_daily_report(session_id, day=day)
    return {"session_id": session_id, "day": day, "content": report_content}


@app.post("/readiness/{session_id}")
def start_readiness_review_endpoint(session_id: str):
    """
    Executes Tech Lead pre-build readiness review (Handbook 10.1.4, 2.7.6 step 19b).
    Enforces Gate 2 approval. Returns readiness verdict, gaps, contradictions, and traceability.
    """
    enforce_gate2_server_side(session_id)
    try:
        result = run_readiness_review(session_id)
        return {
            "status": "success",
            "session_id": session_id,
            "data": result
        }
    except Exception as e:
        logger.error(f"Readiness review failed for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/readiness/{session_id}")
def get_readiness_status_endpoint(session_id: str):
    """
    Queries current Tech Lead readiness review state and verifies invalidation status.
    Handbook 10.1.4: Changes to backlog, architecture, or PRD invalidate the verdict.
    """
    state = get_readiness_state(session_id)
    session_dir = os.path.join("data", "projects", session_id)
    readiness_file = os.path.join(session_dir, "docs", "readiness.md")
    content = ""
    if os.path.exists(readiness_file):
        with open(readiness_file, "r", encoding="utf-8") as f:
            content = f.read()

    return {
        "session_id": session_id,
        "state": state,
        "content": content
    }


# =========================================================================
# Accounts: sign up, log in, profiles, Google sign-in (local accounts in data/office.db)
# =========================================================================

try:
    import auth as office_auth
    import google_oauth
except ImportError:
    from engine import auth as office_auth, google_oauth


class SignupRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    organization: Optional[str] = None


@app.post("/auth/signup")
def auth_signup(req: SignupRequest):
    return office_auth.signup(req.name, req.email, req.password)


@app.post("/auth/login")
def auth_login(req: LoginRequest):
    return office_auth.login(req.email, req.password)


@app.get("/auth/me")
def auth_me(authorization: Optional[str] = Header(None)):
    user = office_auth.user_for_token(office_auth.token_from_header(authorization))
    return {"user": user, "accounts_exist": office_auth.users_exist(),
            "google_enabled": google_oauth.is_configured()}


@app.post("/auth/logout")
def auth_logout(authorization: Optional[str] = Header(None)):
    office_auth.logout(office_auth.token_from_header(authorization))
    return {"status": "logged_out"}


@app.get("/auth/profile")
def auth_get_profile(authorization: Optional[str] = Header(None)):
    user = office_auth.require_user(authorization)
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in")
    return office_auth.update_profile(user)


@app.put("/auth/profile")
def auth_update_profile(req: ProfileUpdateRequest, authorization: Optional[str] = Header(None)):
    user = office_auth.require_user(authorization)
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in")
    return office_auth.update_profile(user, req.name, req.title, req.organization)


@app.get("/auth/google/start")
def auth_google_start():
    return google_oauth.start()


@app.get("/auth/google/callback", response_class=HTMLResponse)
def auth_google_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    return google_oauth.finish(code, state, error, office_auth.login_or_create_google_user)


@app.get("/auth/google/result/{state}")
def auth_google_result(state: str):
    return google_oauth.result(state)


# =========================================================================
# Stages 6-9: Build loop, Alpha, Beta (Gate 3), Release (Gate 4), Delivery
# Handbook 2.7.7-2.7.10, 10, 13-16, 20.4, 23, 32
# =========================================================================

try:
    import events as office_events
    import devops as office_devops
    import release as office_release
    from build_loop import start_build_in_background, get_build_state, BuildLoop
except ImportError:
    from engine import events as office_events, devops as office_devops, release as office_release
    from engine.build_loop import start_build_in_background, get_build_state, BuildLoop

default_llm_client.add_call_listener(office_events.llm_call_listener())


class AllowlistApprovalRequest(BaseModel):
    session_id: str
    commands: Optional[Dict[str, str]] = None
    network_allowed: bool = False


class GateDecisionRequest(BaseModel):
    session_id: str
    note: Optional[str] = ""


class UATFeedbackRequest(BaseModel):
    session_id: str
    feedback: str
    kind: str = "bug"  # bug -> new UAT story; change -> scope question for the PM


def _require_project(session_id: str) -> None:
    if not os.path.isdir(os.path.join(DATA_PROJECTS_DIR, validate_session_id(session_id))):
        raise HTTPException(status_code=404, detail=f"Project {session_id} not found")


@app.get("/build/allowlist/{session_id}")
def get_command_allowlist(session_id: str):
    _require_project(session_id)
    current = office_devops.get_allowlist(session_id)
    return current if current.get("commands") else office_devops.propose_allowlist(session_id)


@app.post("/build/allowlist/approve")
def approve_command_allowlist(req: AllowlistApprovalRequest):
    """Client approves the agent command allowlist (Handbook 23.4.1). Network stays off unless approved."""
    _require_project(req.session_id)
    enforce_gate2_server_side(req.session_id)
    try:
        return office_devops.approve_allowlist(req.session_id, req.commands, req.network_allowed)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/build/start/{session_id}")
def start_build_stage_endpoint(session_id: str):
    """
    Stage 6 Build Loop (Handbook 2.7.7, 32 BuildStory). Server-side gates: Gate 2 approved,
    readiness verdict ready, command allowlist approved. Runs in the background.
    """
    _require_project(session_id)
    enforce_gate2_server_side(session_id)
    enforce_readiness_server_side(session_id)
    if not office_devops.get_allowlist(session_id).get("approved"):
        raise HTTPException(status_code=403, detail={"error": "ALLOWLIST_NOT_APPROVED",
                                                     "rule": "Handbook 23.4.1: the command allowlist is approved by the client."})
    guard = check_budget_guard(session_id)
    if guard.get("pause_100"):
        raise HTTPException(status_code=402, detail=guard["message"])
    try:
        return start_build_in_background(session_id)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/build/status/{session_id}")
def get_build_status_endpoint(session_id: str):
    _require_project(session_id)
    return get_build_state(session_id)


@app.get("/build/daily-report/{session_id}")
def get_build_daily_report(session_id: str):
    path = os.path.join(get_session_dir(session_id), "reports", "build-daily.md")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No build report yet")
    with open(path, "r", encoding="utf-8") as f:
        return {"session_id": session_id, "markdown": f.read()}


@app.get("/events/{session_id}")
def get_events_endpoint(session_id: str, after: int = 0, limit: int = 500, task_id: Optional[str] = None):
    _require_project(session_id)
    return {"session_id": session_id, "events": office_events.list_events(session_id, after, task_id=task_id, limit=limit)}


@app.get("/preview/{session_id}")
def get_preview_endpoint(session_id: str):
    _require_project(session_id)
    return office_devops.get_preview_state(session_id)


@app.post("/preview/stop/{session_id}")
def stop_preview_endpoint(session_id: str):
    _require_project(session_id)
    office_devops.stop_preview(session_id)
    return office_devops.get_preview_state(session_id)


@app.post("/beta/start/{session_id}")
def start_beta_endpoint(session_id: str):
    """Stage 8: preview with seed data, then Gate 3 opens for client UAT."""
    _require_project(session_id)
    return office_release.start_beta(session_id)


@app.get("/gate/{gate}/status/{session_id}")
def get_gate_status_endpoint(gate: int, session_id: str):
    _require_project(session_id)
    if gate not in (3, 4):
        raise HTTPException(status_code=400, detail="Gates 1 and 2 have their own endpoints")
    return office_release.gate_state(session_id, gate)


@app.post("/gate3/approve")
def approve_gate3_endpoint(req: GateDecisionRequest):
    _require_project(req.session_id)
    return office_release.decide_gate(req.session_id, 3, True, req.note or "")


@app.post("/gate3/feedback")
def gate3_feedback_endpoint(req: UATFeedbackRequest):
    """UAT feedback through the BA (new Q-); bugs re-enter Stage 6 as UAT stories."""
    _require_project(req.session_id)
    if req.kind not in ("bug", "change"):
        raise HTTPException(status_code=400, detail="kind must be 'bug' or 'change'")
    return office_release.uat_feedback(req.session_id, req.feedback, req.kind)


@app.post("/release/prepare/{session_id}")
def prepare_release_endpoint(session_id: str, version: str = "v1.0.0"):
    """Stage 9: CI on main, rollback and restore drills, image, runbook; then Gate 4 opens."""
    _require_project(session_id)
    return office_release.prepare_release(session_id, version)


@app.post("/gate4/approve")
def approve_gate4_endpoint(req: GateDecisionRequest):
    _require_project(req.session_id)
    return office_release.decide_gate(req.session_id, 4, True, req.note or "")


@app.post("/gate4/request-changes")
def request_changes_gate4_endpoint(req: GateDecisionRequest):
    _require_project(req.session_id)
    return office_release.decide_gate(req.session_id, 4, False, req.note or "")


@app.post("/deliver/{session_id}")
def deliver_endpoint(session_id: str):
    """Delivery: local repo bundle, docs, runbook and final report. Nothing is pushed or uploaded."""
    _require_project(session_id)
    return office_release.deliver(session_id)


if __name__ == "__main__":
    port = int(os.environ.get("ENGINE_PORT", 8765))
    logger.info(f"Starting Autonoma Python Engine on http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


