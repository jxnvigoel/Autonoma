import os
import re
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

try:
    from prompts.pm_system_prompt import PM_SYSTEM_PROMPT
except ImportError:
    from engine.prompts.pm_system_prompt import PM_SYSTEM_PROMPT

logger = logging.getLogger("autonoma-engine.pm")

pm_router = APIRouter(prefix="/pm", tags=["pm"])

PRD_START_TAG = "<!--PRD_CONTENT_START-->"
PRD_END_TAG = "<!--PRD_CONTENT_END-->"
PRD_PATTERN = re.compile(rf"{re.escape(PRD_START_TAG)}(.*?){re.escape(PRD_END_TAG)}", re.DOTALL)


class PMSessionRequest(BaseModel):
    session_id: str


class PMMessageRequest(BaseModel):
    session_id: str
    message: str


def extract_prd_content(text: str) -> tuple[str, Optional[str]]:
    """
    Extracts conversational response and PRD content between PRD tags if present.
    Returns (cleaned_message, prd_content).
    """
    match = PRD_PATTERN.search(text)
    if match:
        prd_content = match.group(1).strip()
        cleaned_msg = PRD_PATTERN.sub("", text).strip()
        return cleaned_msg, prd_content

    # If closing tag is missing or cut off, look for starting tag
    if PRD_START_TAG in text:
        parts = text.split(PRD_START_TAG, 1)
        cleaned_msg = parts[0].strip()
        prd_content = parts[1].replace(PRD_END_TAG, "").strip()
        return cleaned_msg, prd_content

    # If the response starts with a markdown header # Product Requirement Document
    if "# Product Requirement Document" in text or "## 1. Executive Summary" in text:
        idx = text.find("# Product Requirement Document")
        if idx == -1:
            idx = text.find("## 1. Executive Summary")
        cleaned_msg = text[:idx].strip() if idx > 0 else "I've drafted the initial Product Requirement Document (PRD) below based on the Business Analyst discovery."
        prd_content = text[idx:].strip()
        return cleaned_msg, prd_content

    return text.strip(), None


def create_grounded_skeleton_prd(intake: Dict[str, Any], qa_log: List[Dict[str, Any]], requirements_text: str) -> str:
    """
    Creates a high-quality, structured fallback PRD grounded in the BA intake and QA data
    if the local model does not output the full template.
    """
    proj_name = intake.get("project_name", "Untitled Project")
    description = intake.get("description", "Software Application")
    target_users = intake.get("target_users", "General Users")
    timeline = intake.get("timeline", "6 weeks")
    budget = intake.get("budget", "Standard MVP budget")

    qa_summary_lines = []
    for item in qa_log:
        q = item.get("question", "")[:80]
        a = item.get("answer", "")
        qa_summary_lines.append(f"- **{item.get('id', 'Q-???')}**: {a}")

    qa_summary = "\n".join(qa_summary_lines) if qa_summary_lines else "- Grounded in client discovery session."

    skeleton = f"""# Product Requirement Document (PRD): {proj_name}

## 1. Executive Summary & Problem Statement
- **Problem**: Users need an effective solution for: {description}.
- **Product Vision**: {proj_name} provides a seamless, robust workflow tailored for {target_users}.
- **Core Value Proposition**: Rapid delivery within {timeline} with cost predictability ({budget}).

## 2. Product Goals & Success Metrics
- **Primary Goal**: Deliver a reliable MVP addressing key client workflows within {timeline}.
- **Target Audience**: {target_users}
- **Success Metrics**:
  - 85%+ user task completion rate in core workflows.
  - Sub-second UI response times for primary interactions.
  - Zero critical data loss defects in v1 beta testing.

## 3. User Personas & Core Journeys
- **P-01: Primary End User ({target_users})**
  - Goal: Efficiently utilize {proj_name} to achieve their daily objectives without friction.
  - Journey: Launch tool -> Setup initial preferences -> Execute primary workflow -> Review results.
- **P-02: Project Admin / Stakeholder**
  - Goal: Monitor progress, configure system limits, and export status reports.

## 4. Scope & Feature Prioritization (MoSCoW)
- **Must Have (v1 MVP Core)**:
  - Core application flow and persistent storage.
  - Fast, responsive interface with status tracking.
  - Grounded features agreed upon during BA discovery.
- **Should Have**:
  - Export capabilities (Markdown / JSON).
  - Configurable settings and telemetry toggles.
- **Could Have**:
  - Advanced automation hooks and external integrations.
- **Out of Scope for v1**:
  - Third-party cloud sync (planned for v2).
  - Multi-tenant enterprise role management (planned for v2).

## 5. User Stories & Acceptance Criteria
### US-01: Workspace Initialization
- **Story**: As a {target_users}, I want to launch the project and see all active agent roles, so that I understand current project status.
- **Acceptance Criteria**:
  - [ ] Given an active project session, when the user opens the workspace, then all agent stations and live status badges are shown.
  - [ ] Given a completed BA session, when the user inspects requirements, then the full Q&A log and requirements.md are accessible.

### US-02: Requirements & PRD Grounding
- **Story**: As a stakeholder, I want the PRD to reference real discovery Q&A, so that engineering builds exactly what was requested.
- **Acceptance Criteria**:
  - [ ] Given BA findings from Q-001 through Q-{len(qa_log):03d}, when the PRD is generated, then all functional scope directly traces back to source citations.

### US-03: Real-Time Specification Review
- **Story**: As a project creator, I want to discuss and refine the PRD interactively with the PM agent, so that any edge cases are documented before implementation.
- **Acceptance Criteria**:
  - [ ] Given user feedback on scope or priority, when submitted to the PM, then the PM updates prd.md incrementally with revised stories.

## 6. Functional Specifications & Flow
- **Data Persistence**: Local storage within the session data directory.
- **Discovery Inputs Traceability**:
{qa_summary}

## 7. Non-Functional Requirements
- **Performance**: Instant local file I/O; low memory footprint.
- **Privacy & Security**: 100% local execution; client data remains on disk.
- **Compatibility**: Standard modern desktop environment.

## 8. Assumptions & Risks
- **ASM-01**: User has Ollama or compatible local inference engine running.
- **ASM-02**: Initial user feedback cycle will refine acceptance criteria prior to code generation.
"""
    return skeleton.strip()


def init_pm_routes(main_app, get_session_dir_fn, load_json_fn, save_json_fn, query_ollama_fn, data_projects_dir: str):
    """
    Registers the PM endpoints with access to shared engine helpers.
    """

    @pm_router.post("/start")
    def pm_start(req: PMSessionRequest):
        session_id = req.session_id.strip()
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required")

        session_dir = get_session_dir_fn(session_id)
        intake_file = os.path.join(session_dir, "intake.json")
        qa_file = os.path.join(session_dir, "qa_log.json")
        state_file = os.path.join(session_dir, "session_state.json")
        req_file = os.path.join(session_dir, "docs", "requirements.md")
        pm_state_file = os.path.join(session_dir, "pm_state.json")
        prd_file = os.path.join(session_dir, "prd.md")

        if not os.path.exists(intake_file):
            raise HTTPException(status_code=404, detail="Project session not found")

        intake_data = load_json_fn(intake_file, {})
        qa_log = load_json_fn(qa_file, [])
        ba_state = load_json_fn(state_file, {})

        # Validation: BA discovery must be completed
        has_requirements = os.path.exists(req_file) and os.path.getsize(req_file) > 10
        is_ba_ready = ba_state.get("ready_for_requirements", False) or ba_state.get("is_complete", False)
        has_qa_log = isinstance(qa_log, list) and len(qa_log) > 0

        if not (has_requirements or (is_ba_ready and has_qa_log)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot start Product Manager: Business Analyst requirements discovery is not complete yet. Finish the BA interview and finalize requirements first.",
            )

        # Check if PM session is already initialized
        if os.path.exists(pm_state_file) and os.path.exists(prd_file):
            pm_state = load_json_fn(pm_state_file, {})
            try:
                with open(prd_file, "r", encoding="utf-8") as f:
                    prd_content = f.read()
            except Exception:
                prd_content = ""

            messages = pm_state.get("messages", [])
            initial_msg = messages[0]["content"] if messages else "Welcome back! Here is our current Product Requirement Document (PRD)."
            return {
                "session_id": session_id,
                "message": initial_msg,
                "prd_content": prd_content,
                "already_started": True,
            }

        requirements_content = ""
        if os.path.exists(req_file):
            try:
                with open(req_file, "r", encoding="utf-8") as f:
                    requirements_content = f.read()
            except Exception as e:
                logger.warning(f"Failed reading requirements.md: {e}")

        # Construct prompt for the PM agent
        prompt = f"""You are the Product Manager for the project "{intake_data.get('project_name', 'Untitled Project')}".
The Business Analyst has completed the client discovery interview. Here is the full handoff data:

CLIENT INTAKE:
- Project Name: {intake_data.get('project_name')}
- Description: {intake_data.get('description')}
- Target Users: {intake_data.get('target_users')}
- Target Timeline: {intake_data.get('timeline')}
- Budget & Running Costs: {intake_data.get('budget')}

FULL BA Q&A DISCOVERY LOG:
{json.dumps(qa_log, indent=2)}

BA REQUIREMENTS DOCUMENT:
{requirements_content if requirements_content else "Refer to Q&A Log above for all requirements."}

INSTRUCTIONS FOR ROUND 1 (KICKOFF):
1. Greet the client as their Product Manager.
2. Provide a 2-sentence executive summary of the product scope you are taking into planning.
3. Explain that you have structured the initial Product Requirement Document (PRD) below, highlighting key scope priorities (what is in v1 MVP vs deferred) and invite them to review it.
4. Output the complete, structured, unambiguous PRD between {PRD_START_TAG} and {PRD_END_TAG}.
Ground every feature in the real BA discovery answers (referencing Q- numbers where appropriate). Do not use placeholders."""

        try:
            raw_response = query_ollama_fn(prompt=prompt, system=PM_SYSTEM_PROMPT)
            cleaned_message, prd_content = extract_prd_content(raw_response)
        except Exception as e:
            logger.error(f"Error querying Ollama for PM start: {e}")
            cleaned_message = f"Hello! I am your Product Manager for {intake_data.get('project_name')}. I have reviewed the Business Analyst's discovery log and structured our initial Product Requirement Document (PRD) below."
            prd_content = None

        if not prd_content or len(prd_content.strip()) < 50:
            prd_content = create_grounded_skeleton_prd(intake_data, qa_log, requirements_content)

        # Save prd.md
        with open(prd_file, "w", encoding="utf-8") as f:
            f.write(prd_content)

        # Save pm_state.json
        now_iso = datetime.now(timezone.utc).isoformat()
        first_message = {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": cleaned_message,
            "timestamp": now_iso,
        }
        pm_state = {
            "session_id": session_id,
            "round": 1,
            "status": "waiting-on-you",
            "messages": [first_message],
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        save_json_fn(pm_state_file, pm_state)

        logger.info(f"PM session initialized for {session_id} with PRD at {prd_file}")

        return {
            "session_id": session_id,
            "message": cleaned_message,
            "prd_content": prd_content,
            "already_started": False,
        }

    @pm_router.post("/message")
    def pm_message(req: PMMessageRequest):
        session_id = req.session_id.strip()
        user_text = req.message.strip()

        if not session_id or not user_text:
            raise HTTPException(status_code=400, detail="session_id and message are required")

        session_dir = get_session_dir_fn(session_id)
        pm_state_file = os.path.join(session_dir, "pm_state.json")
        prd_file = os.path.join(session_dir, "prd.md")
        intake_file = os.path.join(session_dir, "intake.json")
        qa_file = os.path.join(session_dir, "qa_log.json")

        if not os.path.exists(pm_state_file):
            raise HTTPException(status_code=404, detail="PM session has not been started. Call /pm/start first.")

        pm_state = load_json_fn(pm_state_file, {"messages": [], "round": 1})
        intake_data = load_json_fn(intake_file, {})
        qa_log = load_json_fn(qa_file, [])

        current_prd = ""
        if os.path.exists(prd_file):
            try:
                with open(prd_file, "r", encoding="utf-8") as f:
                    current_prd = f.read()
            except Exception as e:
                logger.error(f"Error reading prd.md: {e}")

        # Add user message to history
        now_iso = datetime.now(timezone.utc).isoformat()
        user_msg = {
            "id": str(uuid.uuid4()),
            "role": "user",
            "content": user_text,
            "timestamp": now_iso,
        }
        pm_state.setdefault("messages", []).append(user_msg)

        current_round = pm_state.get("round", 1) + 1
        pm_state["round"] = current_round

        # Build prompt for PM follow-up turn
        recent_messages = pm_state["messages"][-6:]  # Last few turns for context
        history_str = "\n".join([f"{m.get('role').upper()}: {m.get('content')}" for m in recent_messages])

        prompt = f"""PROJECT: {intake_data.get('project_name', 'Untitled')}
CLIENT INTAKE RECAP:
- Goal: {intake_data.get('description')}
- Users: {intake_data.get('target_users')}
- Timeline: {intake_data.get('timeline')}

CURRENT PRD DOCUMENT:
{current_prd}

CONVERSATION HISTORY:
{history_str}

CLIENT'S NEW FEEDBACK / MESSAGE:
"{user_text}"

INSTRUCTIONS FOR THIS TURN:
1. Respond to the client directly as their Product Manager: acknowledge their points, discuss the product implications, and clarify any scope changes or trade-offs.
2. If the client asked to add, modify, or clarify any features, stories, or constraints, incorporate those updates directly into the PRD.
3. At the end of your response, output the complete, updated PRD inside {PRD_START_TAG} and {PRD_END_TAG}.
If no changes to the PRD are needed, you may omit the tags or output the unchanged PRD inside the tags. Keep your conversational response sharp and professional."""

        try:
            raw_response = query_ollama_fn(prompt=prompt, system=PM_SYSTEM_PROMPT)
            cleaned_message, updated_prd = extract_prd_content(raw_response)
        except Exception as e:
            logger.error(f"Error querying Ollama in pm_message: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to communicate with local model: {e}")

        final_prd = updated_prd if updated_prd and len(updated_prd.strip()) > 50 else current_prd

        # Save updated PRD if changed
        if updated_prd and len(updated_prd.strip()) > 50:
            try:
                with open(prd_file, "w", encoding="utf-8") as f:
                    f.write(updated_prd)
            except Exception as e:
                logger.error(f"Error saving updated prd.md: {e}")

        # Add assistant response to history
        assistant_msg = {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": cleaned_message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        pm_state["messages"].append(assistant_msg)
        pm_state["status"] = "waiting-on-you"
        pm_state["updated_at"] = datetime.now(timezone.utc).isoformat()
        save_json_fn(pm_state_file, pm_state)

        return {
            "session_id": session_id,
            "message": cleaned_message,
            "prd_content": final_prd,
            "round": current_round,
        }

    @pm_router.get("/session/{session_id}")
    def get_pm_session(session_id: str):
        session_id = session_id.strip()
        session_dir = get_session_dir_fn(session_id)
        pm_state_file = os.path.join(session_dir, "pm_state.json")
        prd_file = os.path.join(session_dir, "prd.md")
        intake_file = os.path.join(session_dir, "intake.json")
        state_file = os.path.join(session_dir, "session_state.json")
        req_file = os.path.join(session_dir, "docs", "requirements.md")

        if not os.path.exists(intake_file):
            raise HTTPException(status_code=404, detail="Session not found")

        intake_data = load_json_fn(intake_file, {})
        ba_state = load_json_fn(state_file, {})
        has_ba_requirements = os.path.exists(req_file) or ba_state.get("ready_for_requirements", False)

        started = os.path.exists(pm_state_file)
        pm_state = load_json_fn(pm_state_file, {}) if started else {}

        prd_content = None
        if os.path.exists(prd_file):
            try:
                with open(prd_file, "r", encoding="utf-8") as f:
                    prd_content = f.read()
            except Exception as e:
                logger.warning(f"Error reading prd.md: {e}")

        status_str = "idle"
        if started:
            status_str = pm_state.get("status", "waiting-on-you")
        elif has_ba_requirements:
            status_str = "idle"  # Ready to start PM
        else:
            status_str = "idle"  # Blocked on BA

        return {
            "session_id": session_id,
            "project_name": intake_data.get("project_name", "Untitled"),
            "started": started,
            "status": status_str,
            "messages": pm_state.get("messages", []),
            "prd_content": prd_content,
            "round": pm_state.get("round", 0),
            "can_start": has_ba_requirements,
        }

    @main_app.get("/office/status/{session_id}")
    def get_office_status(session_id: str):
        """
        Returns real live status and metadata for all project agents in this session.
        """
        session_id = session_id.strip()
        session_dir = get_session_dir_fn(session_id)
        intake_file = os.path.join(session_dir, "intake.json")
        ba_state_file = os.path.join(session_dir, "session_state.json")
        qa_file = os.path.join(session_dir, "qa_log.json")
        req_file = os.path.join(session_dir, "docs", "requirements.md")
        pm_state_file = os.path.join(session_dir, "pm_state.json")
        prd_file = os.path.join(session_dir, "prd.md")

        if not os.path.exists(intake_file):
            raise HTTPException(status_code=404, detail="Session not found")

        intake_data = load_json_fn(intake_file, {})
        ba_state = load_json_fn(ba_state_file, {})
        qa_log = load_json_fn(qa_file, [])
        pm_state = load_json_fn(pm_state_file, {}) if os.path.exists(pm_state_file) else None

        has_requirements = os.path.exists(req_file) and os.path.getsize(req_file) > 10
        ba_ready = ba_state.get("ready_for_requirements", False) or ba_state.get("is_complete", False) or has_requirements
        ba_messages = ba_state.get("messages", [])

        # Compute real live BA status
        if ba_ready:
            ba_status = "done"
        elif len(ba_messages) > 0:
            ba_status = "waiting-on-you"
        else:
            ba_status = "idle"

        # Compute real live PM status
        has_prd = os.path.exists(prd_file) and os.path.getsize(prd_file) > 10
        if pm_state:
            pm_messages = pm_state.get("messages", [])
            pm_status = pm_state.get("status", "waiting-on-you")
            if has_prd and len(pm_messages) >= 3 and pm_state.get("status") == "done":
                pm_status = "done"
        else:
            pm_status = "idle"
            pm_messages = []

        return {
            "session_id": session_id,
            "project_name": intake_data.get("project_name", "Untitled Project"),
            "description": intake_data.get("description", ""),
            "target_users": intake_data.get("target_users", ""),
            "timeline": intake_data.get("timeline", ""),
            "budget": intake_data.get("budget", ""),
            "agents": {
                "ba": {
                    "id": "ba",
                    "role": "Business Analyst",
                    "abbr": "BA",
                    "status": ba_status,
                    "has_output": has_requirements,
                    "output_name": "requirements.md",
                    "output_type": "markdown",
                    "message_count": len(ba_messages),
                    "qa_count": len(qa_log),
                    "ready_for_handoff": ba_ready,
                },
                "pm": {
                    "id": "pm",
                    "role": "Product Manager",
                    "abbr": "PM",
                    "status": pm_status,
                    "has_output": has_prd,
                    "output_name": "prd.md",
                    "output_type": "markdown",
                    "message_count": len(pm_messages),
                    "can_start": ba_ready,
                },
                "architect": {
                    "id": "architect",
                    "role": "Software Architect",
                    "abbr": "ARCH",
                    "status": "idle",
                    "has_output": False,
                    "output_name": "architecture.md",
                    "output_type": "markdown",
                    "message_count": 0,
                    "can_start": has_prd,
                },
                "engineer": {
                    "id": "engineer",
                    "role": "Software Engineer",
                    "abbr": "ENG",
                    "status": "idle",
                    "has_output": False,
                    "output_name": "source_code",
                    "output_type": "code",
                    "message_count": 0,
                    "can_start": False,
                },
                "qa": {
                    "id": "qa",
                    "role": "Quality Assurance",
                    "abbr": "QA",
                    "status": "idle",
                    "has_output": False,
                    "output_name": "test_plan.md",
                    "output_type": "markdown",
                    "message_count": 0,
                    "can_start": False,
                },
            },
        }

    main_app.include_router(pm_router)
    logger.info("PM agent router and office status endpoints successfully initialized.")
