"""
Specialist Skill Registry for Autonoma Virtual Office
Per Handbook Chapter 6 (HR, Recruiter and Skill Pack Registry), Chapter 3 (Operating Rules),
Chapter 12 (Backend/Full-Stack), Chapter 19 (Resilience), Chapter 23 (Agent Runtime & Tools),
and Chapter 24 (Data Model).
"""

import os
import re
import json
import logging
import sqlite3
from typing import Dict, Any, List, Optional, Set, Tuple

logger = logging.getLogger("autonoma-engine.skill_registry")

# Role allowed tool permissions per Handbook Section 6.1.3 (Least privilege):
# "BA, PM, HR, Recruiter, Scrum, Designer: read artifacts, write docs/ | docs/"
# "Architect: + check_package | docs/"
# "Developers: read/write/edit, run (allowlist), git on own branch, check_package | own worktree"
# "Tech Lead: read, diff, comment | read-only"
# "QA / Perf: read, write tests, run_tests, k6_run | tests/, perf/"
# "DevOps: CI, Docker, run | repo root, never production"
ROLE_TOOL_ALLOWANCES: Dict[str, Set[str]] = {
    "ba": {"read_file", "write_file", "get_artifact", "ask_client"},
    "pm": {"read_file", "write_file", "get_artifact", "ask_client"},
    "hr": {"read_file", "write_file", "get_artifact", "ask_client"},
    "recruiter": {"read_file", "write_file", "get_artifact", "ask_client"},
    "scrum": {"read_file", "write_file", "get_artifact", "ask_client"},
    "designer": {"read_file", "write_file", "get_artifact", "ask_client"},
    "architect": {
        "read_file", "write_file", "get_artifact", "ask_client",
        "check_package", "list_files", "search"
    },
    "backend": {
        "read_file", "write_file", "edit_file", "list_files", "search",
        "run", "git_commit", "get_artifact", "check_package"
    },
    "frontend": {
        "read_file", "write_file", "edit_file", "list_files", "search",
        "run", "git_commit", "get_artifact", "check_package"
    },
    "fullstack": {
        "read_file", "write_file", "edit_file", "list_files", "search",
        "run", "git_commit", "get_artifact", "check_package"
    },
    "engineer": {
        "read_file", "write_file", "edit_file", "list_files", "search",
        "run", "git_commit", "get_artifact", "check_package"
    },
    "tech_lead": {
        "read_file", "list_files", "search", "get_artifact", "ask_client"
    },
    "qa": {
        "read_file", "write_file", "run_tests", "k6_run", "get_artifact",
        "list_files", "search"
    },
    "perf": {
        "read_file", "write_file", "run_tests", "k6_run", "get_artifact",
        "list_files", "search"
    },
    "devops": {
        "read_file", "write_file", "run", "get_artifact", "list_files", "search"
    },
    "judge": {
        "read_file", "get_artifact", "list_files", "search"
    }
}

# Role filesystem sandboxes per Handbook Table 6.1.3 and Chapter 23.5
ROLE_FS_SCOPES: Dict[str, str] = {
    "ba": "docs/",
    "pm": "docs/",
    "hr": "docs/",
    "recruiter": "docs/",
    "scrum": "docs/",
    "designer": "docs/",
    "architect": "docs/",
    "backend": "own worktree",
    "frontend": "own worktree",
    "fullstack": "own worktree",
    "engineer": "own worktree",
    "tech_lead": "read-only",
    "tech-lead": "read-only",
    "qa": "tests/",
    "perf": "perf/",
    "devops": "repo root",
    "judge": "read-only",
}

# Roles whose handbook chapter exists but whose agent runtime is spec-only (Handbook 6.3.4 Step 1)
SPEC_ONLY_ROLES: Set[str] = {
    "tech-lead", "tech_lead", "frontend", "backend", "fullstack", "qa", "perf", "devops", "scrum"
}

# Document roles that only produce text and MUST NOT receive shell/execution/network tools (Handbook 6.1.3 & 6.3.6)
DOCUMENT_ONLY_ROLES: Set[str] = {
    "ba", "pm", "hr", "recruiter", "scrum", "designer"
}

# Default text caps per agent prompt instructions (in characters / tokens)
DEFAULT_SKILL_TEXT_CHAR_CAP = 30000  # ~7500 tokens max for skill instructions prefix



class SkillManifest:
    """Represents a validated specialist skill pack manifest."""

    def __init__(
        self,
        id: str,
        name: str,
        version: str,
        description: str,
        compatible_roles: List[str],
        triggers: Dict[str, List[str]],
        required_tools: List[str],
        forbidden_tools: List[str],
        rubric_path: str,
        dir_path: str,
        instructions_path: Optional[str] = None,
        standards_path: Optional[str] = None,
        checklist_path: Optional[str] = None,
        templates_dir: Optional[str] = None,
    ):
        self.id = id
        self.name = name
        self.version = version
        self.description = description
        self.compatible_roles = compatible_roles
        self.triggers = triggers
        self.required_tools = required_tools
        self.forbidden_tools = forbidden_tools
        self.rubric_path = rubric_path
        self.dir_path = dir_path
        self.instructions_path = instructions_path
        self.standards_path = standards_path
        self.checklist_path = checklist_path
        self.templates_dir = templates_dir

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "compatible_roles": self.compatible_roles,
            "triggers": self.triggers,
            "required_tools": self.required_tools,
            "forbidden_tools": self.forbidden_tools,
            "rubric_path": self.rubric_path,
            "dir_path": self.dir_path,
            "has_instructions": bool(self.instructions_path and os.path.exists(self.instructions_path)),
            "has_standards": bool(self.standards_path and os.path.exists(self.standards_path)),
            "has_checklist": bool(self.checklist_path and os.path.exists(self.checklist_path)),
            "has_rubric": bool(self.rubric_path and os.path.exists(self.rubric_path)),
        }


class SkillRegistry:
    """
    Pluggable registry for specialist skill packs.
    Scans skills/ and skills/specialists/ at startup and builds an index.
    Adding a new pack only requires dropping a folder with manifest.json.
    """

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = workspace_root or os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..")
        )
        self.skills_dir = os.path.join(self.workspace_root, "skills")
        self.specialists_dir = os.path.join(self.skills_dir, "specialists")
        self.shared_dir = os.path.join(self.skills_dir, "_shared")

        self.packs: Dict[str, SkillManifest] = {}
        self.broken_packs: Dict[str, str] = {}
        self.scan()

    def scan(self) -> None:
        """Scans skills/ and skills/specialists/ directories and registers all valid manifests."""
        self.packs.clear()
        self.broken_packs.clear()

        search_dirs = [self.specialists_dir, self.skills_dir]

        for base_dir in search_dirs:
            if not os.path.exists(base_dir):
                continue

            for entry in os.scandir(base_dir):
                if entry.is_dir() and not entry.name.startswith((".", "_")):
                    # Avoid scanning specialists twice if nested
                    if base_dir == self.skills_dir and entry.name == "specialists":
                        continue

                    manifest_file = os.path.join(entry.path, "manifest.json")
                    if os.path.exists(manifest_file):
                        self._load_and_validate_manifest(entry.path, manifest_file)

        logger.info(
            f"Skill Registry loaded {len(self.packs)} valid packs, {len(self.broken_packs)} broken packs."
        )

    def _load_and_validate_manifest(self, folder_path: str, manifest_path: str) -> None:
        """Loads and strictly validates manifest.json against required fields."""
        folder_name = os.path.basename(folder_path)
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            err_msg = f"Failed to parse JSON in {manifest_path}: {e}"
            self.broken_packs[folder_name] = err_msg
            logger.error(err_msg)
            return

        # Required fields check
        required_fields = [
            "id", "name", "version", "description",
            "compatible_roles", "triggers", "required_tools",
            "forbidden_tools", "rubric_path"
        ]
        missing = [rf for rf in required_fields if rf not in data]
        if missing:
            err_msg = f"Pack at '{folder_name}' missing required manifest fields: {', '.join(missing)}"
            self.broken_packs[folder_name] = err_msg
            logger.error(err_msg)
            return

        # Type checks
        if not isinstance(data["id"], str) or not data["id"].strip():
            err_msg = f"Pack at '{folder_name}' has invalid 'id' (must be non-empty string)"
            self.broken_packs[folder_name] = err_msg
            return

        pack_id = data["id"].strip().lower()

        if not isinstance(data["compatible_roles"], list) or not data["compatible_roles"]:
            err_msg = f"Pack '{pack_id}' must provide a non-empty list for 'compatible_roles'"
            self.broken_packs[folder_name] = err_msg
            return

        if not isinstance(data["triggers"], dict):
            err_msg = f"Pack '{pack_id}' 'triggers' must be an object with 'keywords' and 'signals'"
            self.broken_packs[folder_name] = err_msg
            return

        # Resolve paths
        raw_rubric = data["rubric_path"]
        if os.path.isabs(raw_rubric):
            rubric_abs = raw_rubric
        else:
            rubric_abs = os.path.join(folder_path, raw_rubric)

        if not os.path.exists(rubric_abs):
            err_msg = f"Pack '{pack_id}' rubric_path '{raw_rubric}' does not exist on disk"
            self.broken_packs[folder_name] = err_msg
            logger.warning(err_msg)

        instructions_abs = os.path.join(folder_path, "instructions.md")
        standards_abs = os.path.join(folder_path, "standards.md")
        checklist_abs = os.path.join(folder_path, "checklist.md")
        templates_abs = os.path.join(folder_path, "templates")

        manifest = SkillManifest(
            id=pack_id,
            name=data["name"],
            version=data["version"],
            description=data["description"],
            compatible_roles=[r.lower() for r in data["compatible_roles"]],
            triggers=data["triggers"],
            required_tools=list(data.get("required_tools", [])),
            forbidden_tools=list(data.get("forbidden_tools", [])),
            rubric_path=rubric_abs,
            dir_path=folder_path,
            instructions_path=instructions_abs if os.path.exists(instructions_abs) else None,
            standards_path=standards_abs if os.path.exists(standards_abs) else None,
            checklist_path=checklist_abs if os.path.exists(checklist_abs) else None,
            templates_dir=templates_abs if os.path.exists(templates_abs) else None,
        )

        self.packs[pack_id] = manifest

    def get_pack(self, pack_id: str) -> Optional[SkillManifest]:
        return self.packs.get(pack_id.lower())

    def list_packs(self) -> List[Dict[str, Any]]:
        return [manifest.to_dict() for manifest in self.packs.values()]

    def get_broken_packs(self) -> Dict[str, str]:
        return dict(self.broken_packs)


# Global singleton registry instance
_GLOBAL_REGISTRY: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = SkillRegistry()
    return _GLOBAL_REGISTRY


# =========================================================================
# 2. Prompt Assembly (Handbook Chapter 23.2 & Operating Rules Chapter 3)
# =========================================================================

def assemble_agent_prompt(
    role: str,
    attached_pack_ids: Optional[List[str]] = None,
    output_template: str = "",
    task_instructions: str = "",
    registry: Optional[SkillRegistry] = None,
    char_cap: int = DEFAULT_SKILL_TEXT_CHAR_CAP,
) -> Dict[str, Any]:
    """
    Builds the composite system prompt for an agent run per Chapter 23.2:
    1. skills/_shared/operating-rules.md (Universal cached prefix)
    2. skills/<role>/role.md (Role specification)
    3. Attached specialist packs' instructions (sorted for deterministic cacheability)
    4. Output template / format
    5. Task instructions
    """
    reg = registry or get_skill_registry()
    norm_role = role.strip().lower()
    attached_pack_ids = sorted(list(set(attached_pack_ids or [])))

    sections: List[Dict[str, Any]] = []
    loaded_packs: List[str] = []

    # 1. Operating Rules (Universal stable prefix)
    operating_rules_path = os.path.join(reg.shared_dir, "operating-rules.md")
    operating_rules_content = ""
    if os.path.exists(operating_rules_path):
        with open(operating_rules_path, "r", encoding="utf-8") as f:
            operating_rules_content = f.read().strip()
    else:
        operating_rules_content = "# Operating Rules (Default Grounding & Token Discipline Active)"

    sections.append({
        "name": "operating_rules",
        "path": operating_rules_path,
        "content": operating_rules_content,
        "tokens_est": len(operating_rules_content) // 4,
    })

    # 2. Role File (skills/<role>/role.md)
    role_file_path = os.path.join(reg.skills_dir, norm_role, "role.md")
    role_content = ""
    if os.path.exists(role_file_path):
        with open(role_file_path, "r", encoding="utf-8") as f:
            role_content = f.read().strip()
    else:
        role_content = f"# Role Specification for {norm_role.upper()}"

    sections.append({
        "name": f"role_{norm_role}",
        "path": role_file_path,
        "content": role_content,
        "tokens_est": len(role_content) // 4,
    })

    # 3. Attached Specialist Packs Instructions
    specialist_contents = []
    for pack_id in attached_pack_ids:
        pack = reg.get_pack(pack_id)
        if not pack:
            logger.warning(f"Skill pack '{pack_id}' attached to agent but not found in registry.")
            continue

        if pack.instructions_path and os.path.exists(pack.instructions_path):
            with open(pack.instructions_path, "r", encoding="utf-8") as f:
                p_text = f.read().strip()
            sections.append({
                "name": f"pack_{pack_id}",
                "path": pack.instructions_path,
                "content": p_text,
                "tokens_est": len(p_text) // 4,
            })
            specialist_contents.append(f"## Specialist Pack: {pack.name} (v{pack.version})\n{p_text}")
            loaded_packs.append(pack_id)
        else:
            logger.warning(f"Pack '{pack_id}' has no instructions.md on disk.")

    # 4. Output Template
    if output_template:
        sections.append({
            "name": "output_template",
            "path": None,
            "content": f"# Output Template\n{output_template.strip()}",
            "tokens_est": len(output_template) // 4,
        })

    # 5. Task Instructions
    if task_instructions:
        sections.append({
            "name": "task_instructions",
            "path": None,
            "content": f"# Current Task Instructions\n{task_instructions.strip()}",
            "tokens_est": len(task_instructions) // 4,
        })

    # Assemble composite text
    prompt_parts = [s["content"] for s in sections if s["content"]]
    full_prompt = "\n\n---\n\n".join(prompt_parts)

    total_chars = len(full_prompt)
    total_tokens_est = total_chars // 4

    # Cap check and warning
    if total_chars > char_cap:
        logger.warning(
            f"Agent prompt for '{norm_role}' with packs {loaded_packs} exceeded character cap: "
            f"{total_chars} > {char_cap} chars (~{total_tokens_est} tokens)."
        )

    # Stable cacheable prefix calculation (sections 1, 2, 3 before task)
    stable_prefix_sections = [s for s in sections if s["name"] in (["operating_rules", f"role_{norm_role}"] + [f"pack_{p}" for p in loaded_packs])]
    stable_prefix_len = sum(len(s["content"]) for s in stable_prefix_sections)

    logger.info(
        f"Prompt assembled for role '{norm_role}': {len(sections)} sections, "
        f"{len(loaded_packs)} packs ({', '.join(loaded_packs) or 'none'}), "
        f"~{total_tokens_est} tokens, cacheable prefix: {stable_prefix_len} chars."
    )

    return {
        "system_prompt": full_prompt,
        "sections": [
            {
                "name": s["name"],
                "path": s["path"],
                "tokens": s["tokens_est"],
                "chars": len(s["content"]),
            }
            for s in sections
        ],
        "total_chars": total_chars,
        "total_tokens_estimated": total_tokens_est,
        "cacheable_prefix_length": stable_prefix_len,
        "loaded_packs": loaded_packs,
        "exceeded_cap": total_chars > char_cap,
    }


# =========================================================================
# 4. Deterministic Code Detection (0 Tokens)
# =========================================================================

def detect_specialist_needs(
    prd_text: str = "",
    requirements_text: str = "",
    architecture_text: str = "",
    registry: Optional[SkillRegistry] = None,
) -> Dict[str, Any]:
    """
    Deterministically matches project artifacts against specialist triggers.
    0 LLM tokens consumed.
    Outputs evidence list with matching F-, FR-, and API- citations.
    If evidence is weak, flags an OQ- instead of attaching.
    """
    reg = registry or get_skill_registry()

    # Pre-extract structured ID blocks
    # Features (F-###)
    feature_blocks = _extract_id_blocks(prd_text, r"\b(F-\d{2,4})\b")
    # Functional Requirements (FR-###)
    req_blocks = _extract_id_blocks(requirements_text or prd_text, r"\b(FR-\d{2,4})\b")
    # API Endpoints (API-###)
    api_blocks = _extract_id_blocks(architecture_text, r"\b(API-\d{2,4})\b")

    combined_corpus = f"{requirements_text}\n\n{prd_text}\n\n{architecture_text}".lower()

    detected_packs = []
    open_questions = []

    for pack_id, pack in reg.packs.items():
        triggers = pack.triggers or {}
        keywords = [k.lower() for k in triggers.get("keywords", [])]
        signals = [s.lower() for s in triggers.get("signals", [])]

        evidence_items = []
        raw_keyword_hits = []

        # 1. Check Feature blocks (F-)
        for f_id, text in feature_blocks.items():
            t_lower = text.lower()
            for kw in keywords:
                if _keyword_matches(kw, t_lower):
                    evidence_items.append({
                        "id": f_id,
                        "type": "feature",
                        "trigger": kw,
                        "snippet": _create_snippet(text, kw),
                        "source": "docs/prd.md"
                    })
                    raw_keyword_hits.append(kw)

        # 2. Check Requirement blocks (FR-)
        for fr_id, text in req_blocks.items():
            t_lower = text.lower()
            for kw in keywords:
                if _keyword_matches(kw, t_lower):
                    evidence_items.append({
                        "id": fr_id,
                        "type": "requirement",
                        "trigger": kw,
                        "snippet": _create_snippet(text, kw),
                        "source": "docs/requirements.md"
                    })
                    raw_keyword_hits.append(kw)

        # 3. Check API blocks (API-)
        for api_id, text in api_blocks.items():
            t_lower = text.lower()
            for kw in keywords:
                if _keyword_matches(kw, t_lower):
                    evidence_items.append({
                        "id": api_id,
                        "type": "endpoint",
                        "trigger": kw,
                        "snippet": _create_snippet(text, kw),
                        "source": "docs/architecture.md"
                    })
                    raw_keyword_hits.append(kw)

        # 4. Check general text if no explicit F-/FR-/API- match yet
        corpus_hits = []
        if not evidence_items:
            for kw in keywords:
                if _keyword_matches(kw, combined_corpus):
                    corpus_hits.append(kw)

        # Evaluate confidence
        unique_evidence_ids = {e["id"] for e in evidence_items}
        matched_triggers = {e["trigger"].lower() for e in evidence_items}

        core_triggers = {
            "payments": {"payment", "payments", "checkout", "billing", "subscription", "charge", "idempotency"},
            "auth": {"login", "signup", "session", "jwt", "oauth", "password", "rbac", "credentials", "mfa"},
            "notifications": {"email", "sms", "push notification", "webhook", "outbox", "notification"},
            "file-storage": {"upload", "s3", "bucket", "object storage", "attachment", "stored files"}
        }.get(pack_id, set())

        has_core_flow = bool(matched_triggers.intersection(core_triggers))
        is_keyword_only = (not has_core_flow) or (len(unique_evidence_ids) < 2 and not any(e["type"] == "feature" for e in evidence_items))

        # Explicit negative tests / edge cases per DOD Part 2.3:
        # 1. "refund policy" with no payment flow:
        if pack_id == "payments" and matched_triggers.issubset({"refund", "refunds", "invoice", "stripe"}):
            if not any(t in matched_triggers for t in ["payment", "payments", "checkout", "billing", "charge", "idempotency"]):
                is_keyword_only = True

        # 2. "authentication" mentioned in passing or custody signature false positive:
        # Custody signature / chain-of-custody sign-off != authentication (Handbook Ch 3, Ch 6)
        if pack_id == "auth":
            is_custody_only = bool(evidence_items)
            for ev in evidence_items:
                snip = ev.get("snippet", "").lower()
                if not ("custod" in snip or "chain-of-custody" in snip or "handover" in snip):
                    is_custody_only = False
                    break
            if is_custody_only and not any(t in matched_triggers for t in ["login", "signup", "register", "password", "jwt", "oauth", "mfa", "credentials"]):
                is_keyword_only = True

            if matched_triggers.issubset({"authentication", "auth", "token"}):
                if not any(t in matched_triggers for t in ["login", "signup", "session", "jwt", "oauth", "password", "rbac", "credentials", "mfa"]):
                    is_keyword_only = True

        if len(unique_evidence_ids) >= 1 and not is_keyword_only:
            # Strong evidence grounded in specific requirements/features/endpoints
            adr_refs = sorted(list(unique_evidence_ids))
            detected_packs.append({
                "pack_id": pack_id,
                "name": pack.name,
                "version": pack.version,
                "status": "recommended",
                "confidence": "high",
                "evidence_count": len(evidence_items),
                "evidence": evidence_items,
                "adr_recommendation": (
                    f"ADR recommends attaching '{pack.name}' ({pack_id}) "
                    f"per verified work in {', '.join(adr_refs)}."
                ),
            })
        elif len(unique_evidence_ids) >= 1 and is_keyword_only:
            # Keyword-only hit: NEVER reaches 'high' per DOD Part 2.3
            hit_terms = sorted(list(matched_triggers))
            oq_id = f"OQ-SKILL-{pack_id.upper()}"
            oq = {
                "id": oq_id,
                "to": "client",
                "text": (
                    f"Project documents mention '{hit_terms[0]}', but lack an active, multi-step {pack.name} workflow. "
                    f"Should the '{pack.name}' specialist pack be attached for v1?"
                ),
                "why": f"Keyword-only or incidental mention of {hit_terms[:2]}; requires client confirmation before attaching specialist pack",
                "refs": hit_terms[:3]
            }
            open_questions.append(oq)
            detected_packs.append({
                "pack_id": pack_id,
                "name": pack.name,
                "version": pack.version,
                "status": "weak_evidence",
                "confidence": "medium",
                "evidence_count": len(evidence_items),
                "evidence": evidence_items,
                "open_question": oq,
            })
        elif len(corpus_hits) >= 1:
            # Weak evidence: keyword mentioned in conversation or brief, but no dedicated F- or FR-
            oq_id = f"OQ-SKILL-{pack_id.upper()}"
            oq = {
                "id": oq_id,
                "to": "client",
                "text": (
                    f"Project documents mention '{corpus_hits[0]}', but lack a dedicated feature (F-) "
                    f"or requirement (FR-). Should the '{pack.name}' specialist pack be attached for v1?"
                ),
                "why": f"Weak detection evidence for specialist pack '{pack_id}'",
                "refs": corpus_hits[:3]
            }
            open_questions.append(oq)
            detected_packs.append({
                "pack_id": pack_id,
                "name": pack.name,
                "version": pack.version,
                "status": "weak_evidence",
                "confidence": "low",
                "evidence_count": 0,
                "evidence": [],
                "open_question": oq,
            })

    return {
        "specialist_needs": [p for p in detected_packs if p["status"] == "recommended"],
        "weak_matches": [p for p in detected_packs if p["status"] == "weak_evidence"],
        "open_questions": open_questions,
    }


def _is_negated_in_context(keyword: str, text: str) -> bool:
    """
    Checks if all occurrences of keyword in text are negated (e.g. 'no payments in scope',
    'out of scope: payments', 'without payments', 'zero payments').
    """
    t_lower = text.lower()
    kw = keyword.lower()
    matches = list(re.finditer(r"\b" + re.escape(kw) + r"\b", t_lower))
    if not matches:
        return False

    neg_prefix_pat = r"\b(?:no|not|neither|never|without|zero|exclude[s|d]?|excluding|out of scope|non-goals?)\b[\w\s,:\-]{0,25}\b" + re.escape(kw) + r"\b"
    neg_suffix_pat = r"\b" + re.escape(kw) + r"\b[\w\s]{0,25}\b(?:is|are|was|were)?\s*(?:out of scope|not in scope|not supported|excluded|not planned|not permitted)\b"

    negated_count = 0
    for m in matches:
        start_ctx = max(0, m.start() - 40)
        end_ctx = min(len(t_lower), m.end() + 40)
        snippet = t_lower[start_ctx:end_ctx]
        if re.search(neg_prefix_pat, snippet) or re.search(neg_suffix_pat, snippet):
            negated_count += 1

    return negated_count == len(matches)


def _keyword_matches(keyword: str, text: str) -> bool:
    """Matches keyword as word boundary or exact token, rejecting negated matches."""
    pattern = r"\b" + re.escape(keyword) + r"\b"
    if not re.search(pattern, text, re.IGNORECASE):
        return False
    if _is_negated_in_context(keyword, text):
        return False
    return True


def _create_snippet(text: str, keyword: str, max_chars: int = 120) -> str:
    """Extracts a snippet of text surrounding a matched keyword."""
    m = re.search(r"\b" + re.escape(keyword) + r"\b", text, re.IGNORECASE)
    if not m:
        return text[:max_chars].strip() + ("..." if len(text) > max_chars else "")
    start = max(0, m.start() - 40)
    end = min(len(text), m.end() + 60)
    snippet = text[start:end].replace("\n", " ").strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


def _extract_id_blocks(text: str, id_regex_pattern: str) -> Dict[str, str]:
    """Finds paragraphs or sections associated with requirement IDs."""
    blocks: Dict[str, str] = {}
    if not text:
        return blocks

    lines = text.split("\n")
    current_id: Optional[str] = None
    current_lines: List[str] = []

    for line in lines:
        matches = re.findall(id_regex_pattern, line)
        if matches:
            if current_id and current_lines:
                blocks[current_id] = "\n".join(current_lines).strip()
            current_id = matches[0]
            current_lines = [line]
        elif current_id:
            if line.startswith("# ") or line.startswith("## "):
                # Section break
                blocks[current_id] = "\n".join(current_lines).strip()
                current_id = None
                current_lines = []
            else:
                current_lines.append(line)

    if current_id and current_lines:
        blocks[current_id] = "\n".join(current_lines).strip()

    return blocks


# =========================================================================
# 5. Recruiter / HR Integration and Tool Enforcement (Chapter 6 & 23)
# =========================================================================

def attach_skill_pack(
    agent_profile: Dict[str, Any],
    pack_id: str,
    registry: Optional[SkillRegistry] = None,
) -> Dict[str, Any]:
    """
    Attaches a specialist skill pack to an agent profile.
    Enforces Handbook rules:
    - If pack does not exist, return 'blocked' with the missing pack named (never invent one).
    - If pack is not compatible with agent role, reject.
    - If pack requires tools exceeding role allowance, reject.
    - Updates agent profile tools and skill_packs list.
    """
    reg = registry or get_skill_registry()
    pack_id_norm = pack_id.strip().lower()

    pack = reg.get_pack(pack_id_norm)
    if not pack:
        logger.error(f"Recruiter blocked: Skill pack '{pack_id}' does not exist.")
        return {
            "status": "blocked",
            "error": f"Missing skill pack '{pack_id}'. Recruiter cannot invent skill packs.",
            "missing_pack": pack_id,
            "agent_profile": agent_profile,
        }

    role = agent_profile.get("role", "").strip().lower()
    if role not in pack.compatible_roles:
        err = (
            f"Skill pack '{pack_id}' is incompatible with role '{role}'. "
            f"Allowed roles: {', '.join(pack.compatible_roles)}"
        )
        logger.warning(err)
        return {
            "status": "rejected",
            "error": err,
            "agent_profile": agent_profile,
        }

    # Tool permission checks
    allowed_tools = ROLE_TOOL_ALLOWANCES.get(role, set())
    required_tools = set(pack.required_tools)
    forbidden_tools = set(pack.forbidden_tools)

    # 1. Does pack require tools not allowed for this role?
    exceeded_tools = required_tools - allowed_tools
    if exceeded_tools:
        err = (
            f"Tool permission violation: Skill pack '{pack_id}' requires tools {list(exceeded_tools)} "
            f"which exceed role '{role}' tool allowance."
        )
        logger.warning(err)
        return {
            "status": "rejected",
            "error": err,
            "agent_profile": agent_profile,
        }

    # 2. Does agent currently hold tools forbidden by this pack?
    current_tools = set(agent_profile.get("tools", []))
    conflicting_forbidden = current_tools.intersection(forbidden_tools)
    if conflicting_forbidden:
        err = (
            f"Tool conflict violation: Agent holds forbidden tools {list(conflicting_forbidden)} "
            f"disallowed by specialist pack '{pack_id}'."
        )
        logger.warning(err)
        return {
            "status": "rejected",
            "error": err,
            "agent_profile": agent_profile,
        }

    # Attach pack cleanly
    skill_packs = list(agent_profile.get("skill_packs", []))
    if pack_id_norm not in skill_packs:
        skill_packs.append(pack_id_norm)

    # Add required tools within allowed boundaries
    new_tools = sorted(list(current_tools.union(required_tools)))

    updated_profile = dict(agent_profile)
    updated_profile["skill_packs"] = skill_packs
    updated_profile["tools"] = new_tools

    logger.info(f"Attached pack '{pack_id_norm}' to agent '{agent_profile.get('agent_id', role)}'.")
    return {
        "status": "attached",
        "pack_id": pack_id_norm,
        "pack_name": pack.name,
        "agent_profile": updated_profile,
    }


def detach_skill_pack(agent_profile: Dict[str, Any], pack_id: str) -> Dict[str, Any]:
    """Detaches a specialist skill pack from an agent profile."""
    pack_id_norm = pack_id.strip().lower()
    skill_packs = [p for p in agent_profile.get("skill_packs", []) if p.lower() != pack_id_norm]
    updated_profile = dict(agent_profile)
    updated_profile["skill_packs"] = skill_packs
    return {
        "status": "detached",
        "pack_id": pack_id_norm,
        "agent_profile": updated_profile,
    }


def get_role_pack(role: str, registry: Optional[SkillRegistry] = None) -> Dict[str, Any]:
    """
    Looks up a base role skill pack in skills/<role>/.
    Enforces Handbook 6.3.4 Rule 1:
    - If pack does not exist: status 'blocked', do not invent one.
    - If handbook chapter exists but agent not built yet: marked 'spec_only: true'.
    """
    reg = registry or get_skill_registry()
    norm_role = role.strip().lower()

    role_dir = os.path.join(reg.skills_dir, norm_role)
    role_md_path = os.path.join(role_dir, "role.md")
    rubric_path = os.path.join(role_dir, "rubric.json")

    if not os.path.exists(role_md_path):
        logger.error(f"Recruiter blocked: Role skill pack '{norm_role}' does not exist at {role_dir}.")
        return {
            "status": "blocked",
            "exists": False,
            "role": norm_role,
            "missing_pack": norm_role,
            "spec_only": False,
            "error": f"Missing skill pack '{norm_role}'. Recruiter cannot invent skill packs."
        }

    is_spec_only = norm_role in SPEC_ONLY_ROLES
    return {
        "status": "available",
        "exists": True,
        "role": norm_role,
        "pack_path": f"skills/{norm_role}",
        "dir_path": role_dir,
        "role_md_path": role_md_path,
        "rubric_path": rubric_path if os.path.exists(rubric_path) else None,
        "has_role_md": True,
        "has_rubric": os.path.exists(rubric_path),
        "spec_only": is_spec_only,
        "notes": f"Role '{norm_role}' skill pack loaded from skills/{norm_role}/role.md" + (" (spec_only: true)" if is_spec_only else "")
    }


def validate_agent_permissions(
    role: str,
    tools: List[str],
    fs_scope: str
) -> Tuple[bool, List[str]]:
    """
    Validates agent tool allowances and filesystem scope per Handbook 6.1.3 & 6.3.6.
    Rejects any profile exceeding role permissions.
    """
    errors: List[str] = []
    norm_role = role.strip().lower()

    allowed_tools = ROLE_TOOL_ALLOWANCES.get(norm_role, set())
    if not allowed_tools:
        errors.append(f"Unknown or unconfigured role '{norm_role}' for tool allowance check.")

    tool_set = set(tools)
    exceeded = tool_set - allowed_tools
    if exceeded:
        errors.append(
            f"Least privilege violation: Agent with role '{norm_role}' holds unauthorized tools {sorted(list(exceeded))}. "
            f"Allowed tools for this role are: {sorted(list(allowed_tools))}."
        )

    # Document role must-not check: roles that only write documents never get run/shell/git tools
    if norm_role in DOCUMENT_ONLY_ROLES:
        forbidden_doc_tools = {"run", "edit_file", "git_commit", "git", "run_tests", "k6_run"}
        doc_violations = tool_set.intersection(forbidden_doc_tools)
        if doc_violations:
            errors.append(
                f"Must-Not violation (Handbook 6.3.6): Document role '{norm_role}' was given executable/shell tools {sorted(list(doc_violations))}."
            )

    # Filesystem scope check
    allowed_scope = ROLE_FS_SCOPES.get(norm_role, "docs/")
    if fs_scope and allowed_scope:
        norm_scope = fs_scope.strip().rstrip("/") + "/"
        norm_allowed = allowed_scope.strip().rstrip("/") + "/"
        if norm_allowed == "docs/" and norm_scope != "docs/":
            errors.append(
                f"Least privilege folder violation: Document role '{norm_role}' restricted to 'docs/', but received '{fs_scope}'."
            )

    return (len(errors) == 0, errors)


def init_agents_db(db_path: str = "data/office.db") -> None:
    """Initializes the agents table in SQLite per Handbook Chapter 24.1."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            seat_id TEXT,
            reports_to TEXT,
            tier TEXT NOT NULL DEFAULT 'high',
            provider TEXT NOT NULL DEFAULT 'groq',
            model TEXT NOT NULL DEFAULT 'llama-3.3-70b-versatile',
            tools TEXT NOT NULL DEFAULT '[]',
            skill_packs TEXT NOT NULL DEFAULT '[]',
            fs_scope TEXT NOT NULL DEFAULT '',
            token_cap INTEGER DEFAULT 400000,
            status TEXT NOT NULL DEFAULT 'idle',
            hired_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    conn.commit()
    conn.close()


def init_approvals_db(db_path: str = "data/office.db") -> None:
    """Initializes the approvals table in SQLite per Handbook Chapter 24.1."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS approvals (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            gate INTEGER NOT NULL,
            summary TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            note TEXT,
            opened_at TEXT NOT NULL DEFAULT (datetime('now')),
            decided_at TEXT
        );
        """
    )
    conn.commit()
    conn.close()



def save_agent_profile_to_db(agent_profile: Dict[str, Any], db_path: str = "data/office.db") -> None:
    """Persists or updates an agent profile in SQLite."""
    init_agents_db(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    proj_id = agent_profile.get("project_id", "p_01")
    aid = agent_profile.get("agent_id", "be-1")
    db_id = f"{proj_id}_{aid}" if not aid.startswith(proj_id) else aid

    cur.execute(
        """
        INSERT INTO agents (id, project_id, name, role, seat_id, reports_to, tier, provider, model, tools, skill_packs, fs_scope, token_cap, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            role = excluded.role,
            name = excluded.name,
            tier = excluded.tier,
            provider = excluded.provider,
            model = excluded.model,
            tools = excluded.tools,
            skill_packs = excluded.skill_packs,
            fs_scope = excluded.fs_scope,
            token_cap = excluded.token_cap,
            status = excluded.status
        """,
        (
            db_id,
            proj_id,
            agent_profile.get("name", "Arjun"),
            agent_profile.get("role", "backend"),
            agent_profile.get("seat_id", "ROLE-01"),
            agent_profile.get("reports_to", "tech-lead-1"),
            agent_profile.get("model_tier", agent_profile.get("tier", "high")),
            agent_profile.get("provider", "groq"),
            agent_profile.get("model", "llama-3.3-70b-versatile"),
            json.dumps(agent_profile.get("tools", [])),
            json.dumps(agent_profile.get("skill_packs", [])),
            agent_profile.get("fs_scope", "projects/"),
            agent_profile.get("token_cap", 400000),
            agent_profile.get("status", "idle"),
        ),
    )
    conn.commit()
    conn.close()


def get_agent_profile_from_db(agent_id: str, db_path: str = "data/office.db") -> Optional[Dict[str, Any]]:
    """Retrieves an agent profile from SQLite."""
    if not os.path.exists(db_path):
        return None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM agents WHERE id = ? OR id LIKE ?", (agent_id, f"%_{agent_id}"))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    raw_id = d.get("id", "")
    pid = d.get("project_id", "")
    clean_aid = raw_id[len(pid)+1:] if (pid and raw_id.startswith(f"{pid}_")) else raw_id
    d["agent_id"] = clean_aid
    d["tier"] = d.get("tier", "medium")
    d["tools"] = json.loads(d["tools"]) if d["tools"] else []
    d["skill_packs"] = json.loads(d["skill_packs"]) if d["skill_packs"] else []
    return d


def get_agents_by_project(project_id: str, db_path: str = "data/office.db") -> List[Dict[str, Any]]:
    """Retrieves all agent profiles for a project from SQLite."""
    if not os.path.exists(db_path):
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM agents WHERE project_id = ? ORDER BY id ASC", (project_id,))
    rows = cur.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        raw_id = d.get("id", "")
        clean_aid = raw_id[len(project_id)+1:] if raw_id.startswith(f"{project_id}_") else raw_id
        d["agent_id"] = clean_aid
        d["tier"] = d.get("tier", "medium")
        d["tools"] = json.loads(d["tools"]) if d.get("tools") else []
        d["skill_packs"] = json.loads(d["skill_packs"]) if d.get("skill_packs") else []
        result.append(d)
    return result





# =========================================================================
# 6. Composite Rubric for Judge
# =========================================================================

def get_composite_rubric(
    role: str,
    attached_pack_ids: Optional[List[str]] = None,
    registry: Optional[SkillRegistry] = None,
) -> Dict[str, Any]:
    """
    Constructs a composite evaluation rubric:
    Composite = Role Rubric + Attached Specialist Packs' Rubrics.
    """
    reg = registry or get_skill_registry()
    norm_role = role.strip().lower()
    attached_pack_ids = attached_pack_ids or []

    # 1. Load base role rubric
    role_rubric_file = os.path.join(reg.skills_dir, norm_role, "rubric.json")
    role_rubric: Dict[str, Any] = {
        "role": norm_role,
        "pass_threshold": 15,
        "max_total": 18,
        "criteria": []
    }
    if os.path.exists(role_rubric_file):
        try:
            with open(role_rubric_file, "r", encoding="utf-8") as f:
                role_rubric = json.load(f)
        except Exception as e:
            logger.error(f"Error loading role rubric {role_rubric_file}: {e}")

    composite_criteria = list(role_rubric.get("criteria", []))
    total_max = role_rubric.get("max_total", 0)
    total_pass = role_rubric.get("pass_threshold", 0)

    # 2. Append criteria from each attached pack
    for pack_id in attached_pack_ids:
        pack = reg.get_pack(pack_id)
        if not pack or not pack.rubric_path or not os.path.exists(pack.rubric_path):
            continue

        try:
            with open(pack.rubric_path, "r", encoding="utf-8") as f:
                p_rubric = json.load(f)
            pack_criteria = p_rubric.get("criteria", [])
            for c in pack_criteria:
                c_copy = dict(c)
                c_copy["pack_id"] = pack_id
                c_copy["name"] = f"[{pack.name}] {c.get('name')}"
                composite_criteria.append(c_copy)

            total_max += p_rubric.get("max_total", 0)
            total_pass += p_rubric.get("pass_threshold", 0)
        except Exception as e:
            logger.error(f"Error parsing specialist rubric for '{pack_id}': {e}")

    return {
        "role": norm_role,
        "attached_packs": attached_pack_ids,
        "pass_threshold": total_pass,
        "max_total": total_max,
        "criteria": composite_criteria,
    }
