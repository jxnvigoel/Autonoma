export const ENGINE_BASE_URL = "http://127.0.0.1:8765";

export interface EngineStatus {
  status: "ready" | "error" | "starting" | "warning";
  ollama_online: boolean;
  model_ready: boolean;
  version?: string;
  message: string;
  groq_configured?: boolean;
  groq_online?: boolean;
  masked_groq_key?: string;
  active_generator_model?: string;
  active_judge_model?: string;
  default_provider?: string;
}

export interface LLMModelInfo {
  id: string;
  owned_by: string;
  context_window: number;
  capability_score: number;
}

export interface RoleConfig {
  provider: "groq" | "ollama";
  model: string;
  temperature: number;
  max_tokens: number;
}

export interface LLMFallbackRecord {
  timestamp: string;
  session_id: string;
  role: string;
  original_provider: string;
  original_model: string;
  fallback_provider: string;
  fallback_model: string;
  reason: string;
  duration_ms: number;
}

export interface LLMSettings {
  groq_configured: boolean;
  masked_api_key: string;
  available_models: LLMModelInfo[];
  role_configs: Record<string, RoleConfig>;
  local_only: boolean;
  fallback_count: number;
  recent_fallbacks: LLMFallbackRecord[];
}

export interface ChatResponse {
  response: string;
  duration: number; // nanoseconds matching Ollama total_duration
  token_count: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
  createdAt?: Date;
  meta?: {
    duration?: number;
    token_count?: number;
  };
}

export interface IntakeFormData {
  projectName: string;
  description: string;
  targetUsers: string;
  timeline: string;
  budget: string;
}

export interface BAStartResponse {
  session_id: string;
  message: string;
}

export interface BAMessageResponse {
  session_id?: string;
  message: string;
  ready_for_requirements: boolean;
}

export interface BARequirementsResponse {
  session_id: string;
  content: string;
}

export type AgentLiveStatus = "idle" | "working" | "waiting-on-you" | "done";

export interface PMEstimateStage {
  stage_id: string;
  stage: string;
  role: string;
  planned_artifacts: string[];
  unit_type: string;
  unit_count: number;
  historical_rate_per_unit: number;
  subtotal_tokens: number;
  rate_source: string;
}

export interface PMEstimateData {
  project_name: string;
  session_id: string;
  generated_at: string;
  model: string;
  model_pricing: {
    provider: string;
    is_local: boolean;
    price_per_1k_tokens_usd: number;
    notes: string;
  };
  ledger_metadata: {
    source: string;
    description: string;
    db_path: string;
  };
  formula: string;
  stories_by_size: {
    small: number;
    medium: number;
    large: number;
    total_stories: number;
  };
  stages: PMEstimateStage[];
  subtotal_tokens: number;
  rework_buffer_percentage: number;
  rework_buffer_tokens: number;
  total_estimated_tokens: number;
  estimated_cost_usd: number;
}

export interface PMStartResponse {
  session_id: string;
  message: string;
  prd_content: string;
  estimate?: PMEstimateData | null;
  quality_bar?: Record<string, any>;
  already_started?: boolean;
}

export interface PMMessageResponse {
  session_id: string;
  message: string;
  prd_content: string;
  estimate?: PMEstimateData | null;
  round: number;
}

export interface PMSessionDetail {
  session_id: string;
  project_name: string;
  started: boolean;
  status: AgentLiveStatus;
  messages: ChatMessage[];
  prd_content?: string | null;
  estimate?: PMEstimateData | null;
  round: number;
  can_start: boolean;
}

export interface OfficeAgentInfo {
  id: "ba" | "pm" | "architect" | "designer" | "hr" | "recruiter" | "engineer" | "qa";
  role: string;
  abbr: string;
  status: AgentLiveStatus;
  has_output: boolean;
  output_name: string;
  output_type: string;
  message_count: number;
  qa_count?: number;
  ready_for_handoff?: boolean;
  can_start?: boolean;
  is_unlocked?: boolean;
  attached_skills?: string[];
}

export interface Gate1State {
  status: "pending" | "approved" | "changes_requested" | "waiting_for_prd";
  approved: boolean;
  approved_at?: string | null;
  has_feasibility?: boolean;
  has_prd?: boolean;
  feedback?: string;
}

export interface Gate2State {
  session_id: string;
  gate: number;
  status: "open" | "approved" | "changes_requested" | "pending" | "waiting_for_team_plan" | "invalidated";
  approved: boolean;
  approved_at?: string | null;
  feedback?: string;
  routed_qid?: string;
  has_team_plan?: boolean;
  has_staffing_report?: boolean;
  client_notes?: string;
  invalidated_reason?: string;
}

export interface TeamPlanRequisition {
  role: string;
  seat_id: string;
  count: number;
  start_week: number;
  end_week: number;
  why: string;
  refs: string[];
  replaces_roles?: string[];
}

export interface TeamPlanData {
  project_id: string;
  generated_at: string;
  total_weeks: number;
  total_headcount_weeks: number;
  headcount_budget_cap: number;
  headcount_over_budget: boolean;
  points_per_agent_per_week: number;
  features_covered: string[];
  requisitions: TeamPlanRequisition[];
  unstaffed_must_haves: string[];
}

export interface AgentProfile {
  id: string;
  project_id: string;
  name: string;
  role: string;
  seat_id: string;
  reports_to: string;
  tier: string;
  provider: string;
  model: string;
  tools: string[];
  skill_packs: string[];
  fs_scope: string;
  token_cap: number;
  status: string;
  hired_at?: string;
}

export interface BudgetGuardStatus {
  session_id: string;
  spent_tokens: number;
  budget_limit_tokens: number;
  token_percent: number;
  spent_cost_usd: number;
  budget_limit_usd?: number | null;
  usd_percent: number;
  warn_80: boolean;
  pause_100: boolean;
  status: "ok" | "warning" | "paused";
  message: string;
  notes?: string;
}

export interface OfficeStatusResponse {
  session_id: string;
  project_name: string;
  description: string;
  target_users: string;
  timeline: string;
  budget: string;
  gate1?: Gate1State;
  gate2?: Gate2State;
  has_team_plan?: boolean;
  has_staffing_report?: boolean;
  agents: {
    ba: OfficeAgentInfo;
    pm: OfficeAgentInfo;
    architect: OfficeAgentInfo & { is_unlocked?: boolean };
    designer?: OfficeAgentInfo & { is_unlocked?: boolean };
    hr?: OfficeAgentInfo & { is_unlocked?: boolean };
    recruiter?: OfficeAgentInfo & { is_unlocked?: boolean };
    engineer: OfficeAgentInfo & { is_unlocked?: boolean };
    qa: OfficeAgentInfo & { is_unlocked?: boolean };
  };
}

export interface BASessionSummary {
  session_id: string;
  project_name: string;
  description: string;
  created_at: string;
  updated_at: string;
  ready_for_requirements: boolean;
  has_requirements: boolean;
  round: number;
}

export interface BASessionDetail {
  session_id: string;
  intake: {
    project_name: string;
    description: string;
    target_users: string;
    timeline: string;
    budget: string;
    created_at?: string;
  };
  state: {
    checklist_covered?: string[];
    checklist_missing?: string[];
    round?: number;
    ready_for_requirements?: boolean;
    messages?: ChatMessage[];
  };
  qa_log: Array<{
    id: string;
    question: string;
    answer: string;
    round: number;
    timestamp: string;
  }>;
  messages: ChatMessage[];
  ready_for_requirements: boolean;
  has_requirements: boolean;
  requirements_content?: string | null;
}

/**
 * Pings the Python engine at http://localhost:8765/status
 */
export async function checkEngineStatus(): Promise<EngineStatus> {
  try {
    const res = await fetch(`${ENGINE_BASE_URL}/status`, {
      method: "GET",
      signal: AbortSignal.timeout(4000),
    });

    if (!res.ok) {
      return {
        status: "error",
        ollama_online: false,
        model_ready: false,
        message: `Python engine returned HTTP ${res.status}: ${res.statusText}`,
      };
    }

    const data: EngineStatus = await res.json();
    return data;
  } catch (err: unknown) {
    const details = err instanceof Error ? err.message : String(err);
    return {
      status: "starting",
      ollama_online: false,
      model_ready: false,
      message: `Connecting to Python engine at ${ENGINE_BASE_URL}... (${details})`,
    };
  }
}

/**
 * Starts a new BA intake session on the Python engine
 */
export async function startBaSession(intake: IntakeFormData): Promise<BAStartResponse> {
  const payload = {
    project_name: intake.projectName.trim(),
    description: intake.description.trim(),
    target_users: intake.targetUsers.trim(),
    timeline: intake.timeline.trim(),
    budget: intake.budget.trim(),
  };

  const res = await fetch(`${ENGINE_BASE_URL}/ba/start`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    const detail = errData?.detail || `Python engine error HTTP ${res.status}: ${res.statusText}`;
    throw new Error(detail);
  }

  const data: BAStartResponse = await res.json();
  return data;
}

/**
 * Sends a message in an existing BA session
 */
export async function sendBaMessage(
  sessionId: string,
  message: string
): Promise<BAMessageResponse> {
  if (!message || !message.trim()) {
    throw new Error("Message cannot be empty");
  }

  const res = await fetch(`${ENGINE_BASE_URL}/ba/message`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      session_id: sessionId,
      message: message.trim(),
    }),
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    const detail = errData?.detail || `Python engine error HTTP ${res.status}: ${res.statusText}`;
    throw new Error(detail);
  }

  const data: BAMessageResponse = await res.json();
  return data;
}

/**
 * Fetches the generated requirements.md for a BA session
 */
export async function getBaRequirements(
  sessionId: string
): Promise<BARequirementsResponse> {
  const res = await fetch(`${ENGINE_BASE_URL}/ba/requirements/${sessionId}`, {
    method: "GET",
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    const detail = errData?.detail || `HTTP ${res.status}: ${res.statusText}`;
    throw new Error(detail);
  }

  const data: BARequirementsResponse = await res.json();
  return data;
}

/**
  * Fetches all past BA sessions from http://localhost:8765/ba/sessions
  */
export async function getBaSessions(): Promise<BASessionSummary[]> {
  const res = await fetch(`${ENGINE_BASE_URL}/ba/sessions`, {
    method: "GET",
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    const detail = errData?.detail || `HTTP ${res.status}: ${res.statusText}`;
    throw new Error(detail);
  }

  const data: BASessionSummary[] = await res.json();
  return data;
}

/**
  * Fetches full history and metadata for a specific BA session
  */
export async function getBaSession(
  sessionId: string
): Promise<BASessionDetail> {
  const res = await fetch(`${ENGINE_BASE_URL}/ba/session/${sessionId}`, {
    method: "GET",
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    const detail = errData?.detail || `HTTP ${res.status}: ${res.statusText}`;
    throw new Error(detail);
  }

  const data: BASessionDetail = await res.json();
  return data;
}

/**
 * Fetches the full persistent shared conversation from http://localhost:8765/conversation
 */
export async function getConversation(): Promise<ChatMessage[]> {
  try {
    const res = await fetch(`${ENGINE_BASE_URL}/conversation`, {
      method: "GET",
      signal: AbortSignal.timeout(6000),
    });

    if (!res.ok) {
      throw new Error(`Failed to get conversation: HTTP ${res.status}`);
    }

    const data: ChatMessage[] = await res.json();
    return data;
  } catch (err: unknown) {
    console.error("Error fetching conversation:", err);
    throw err;
  }
}

/**
 * Clears the conversation history on the Python engine
 */
export async function clearConversation(): Promise<void> {
  try {
    const res = await fetch(`${ENGINE_BASE_URL}/conversation`, {
      method: "DELETE",
      signal: AbortSignal.timeout(6000),
    });

    if (!res.ok) {
      throw new Error(`Failed to clear conversation: HTTP ${res.status}`);
    }
  } catch (err: unknown) {
    console.error("Error clearing conversation:", err);
    throw err;
  }
}

/**
 * Sends a chat prompt to the Python engine at http://localhost:8765/chat
 */
export async function sendChatMessage(prompt: string, model?: string): Promise<ChatResponse> {
  if (!prompt || !prompt.trim()) {
    throw new Error("Prompt cannot be empty");
  }

  try {
    const res = await fetch(`${ENGINE_BASE_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ prompt: prompt.trim(), model }),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => null);
      const detail =
        errData?.detail || `Python engine error HTTP ${res.status}: ${res.statusText}`;
      throw new Error(detail);
    }

    const data: ChatResponse = await res.json();
    return data;
  } catch (err: unknown) {
    if (err instanceof Error) {
      throw err;
    }
    throw new Error(`Failed to send message to Python engine: ${String(err)}`);
  }
}

/**
 * Starts a new PM session for a completed BA session
 */
export async function startPmSession(sessionId: string): Promise<PMStartResponse> {
  if (!sessionId) {
    throw new Error("sessionId is required to start PM session");
  }

  const res = await fetch(`${ENGINE_BASE_URL}/pm/start`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ session_id: sessionId.trim() }),
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    const detail = errData?.detail || `HTTP ${res.status}: ${res.statusText}`;
    throw new Error(detail);
  }

  const data: PMStartResponse = await res.json();
  return data;
}

/**
 * Sends a message in an active PM session
 */
export async function sendPmMessage(
  sessionId: string,
  message: string
): Promise<PMMessageResponse> {
  if (!sessionId) {
    throw new Error("sessionId is required");
  }
  if (!message || !message.trim()) {
    throw new Error("Message cannot be empty");
  }

  const res = await fetch(`${ENGINE_BASE_URL}/pm/message`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      session_id: sessionId.trim(),
      message: message.trim(),
    }),
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    const detail = errData?.detail || `HTTP ${res.status}: ${res.statusText}`;
    throw new Error(detail);
  }

  const data: PMMessageResponse = await res.json();
  return data;
}

/**
 * Fetches current PM session state, conversation history, and PRD content
 */
export async function getPmSession(sessionId: string): Promise<PMSessionDetail> {
  if (!sessionId) {
    throw new Error("sessionId is required");
  }

  const res = await fetch(`${ENGINE_BASE_URL}/pm/session/${sessionId.trim()}`, {
    method: "GET",
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    const detail = errData?.detail || `HTTP ${res.status}: ${res.statusText}`;
    throw new Error(detail);
  }

  const data: PMSessionDetail = await res.json();
  return data;
}

/**
 * Fetches real live status for all project agents in a given session
 */
export async function getOfficeStatus(sessionId: string): Promise<OfficeStatusResponse> {
  if (!sessionId) {
    throw new Error("sessionId is required");
  }

  const res = await fetch(`${ENGINE_BASE_URL}/office/status/${sessionId.trim()}`, {
    method: "GET",
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    const detail = errData?.detail || `HTTP ${res.status}: ${res.statusText}`;
    throw new Error(detail);
  }

  const data: OfficeStatusResponse = await res.json();
  return data;
}

/**
 * Gate 1: Get Gate 1 review status
 */
export async function apiGetGate1Status(sessionId: string): Promise<{ gate1: Gate1State; has_prd: boolean; has_feasibility: boolean }> {
  const res = await fetch(`${ENGINE_BASE_URL}/gate1/status/${sessionId.trim()}`);
  if (!res.ok) {
    throw new Error(`Failed to get Gate 1 status: HTTP ${res.status}`);
  }
  return await res.json();
}

/**
 * Gate 1: Approve PRD, scope, non-goals, and assumptions
 */
export async function apiApproveGate1(sessionId: string, clientNotes?: string): Promise<{ status: string; approved: boolean }> {
  const res = await fetch(`${ENGINE_BASE_URL}/gate1/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId.trim(),
      client_notes: clientNotes || "Approved at Gate 1."
    })
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    throw new Error(errData?.detail || `HTTP ${res.status}`);
  }
  return await res.json();
}

/**
 * Gate 1: Request changes on PRD (routed through BA)
 */
export async function apiRequestGate1Changes(sessionId: string, feedback: string): Promise<{ status: string; routed_qid: string }> {
  const res = await fetch(`${ENGINE_BASE_URL}/gate1/request-changes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId.trim(),
      feedback: feedback.trim()
    })
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    throw new Error(errData?.detail || `HTTP ${res.status}`);
  }
  return await res.json();
}

/**
 * Run Stage 2 Step 8 Feasibility check
 */
export async function apiRunFeasibility(sessionId: string): Promise<{ status: string; verdict: string; path: string; content: string }> {
  const res = await fetch(`${ENGINE_BASE_URL}/architect/feasibility/${sessionId.trim()}`, {
    method: "POST"
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    throw new Error(errData?.detail || `HTTP ${res.status}`);
  }
  return await res.json();
}

/**
 * Run Stage 3 Architect generation
 */
export async function apiGenerateArchitectArtifacts(sessionId: string): Promise<any> {
  const res = await fetch(`${ENGINE_BASE_URL}/architect/generate/${sessionId.trim()}`, {
    method: "POST"
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    throw new Error(errData?.detail || `HTTP ${res.status}`);
  }
  return await res.json();
}

/**
 * Get current Architect session state and artifacts
 */
export async function apiGetArchitectSession(sessionId: string): Promise<{
  session_id: string;
  has_output: boolean;
  state: any;
  architecture_content: string;
  schema_content: string;
  openapi_content: string;
}> {
  const res = await fetch(`${ENGINE_BASE_URL}/architect/session/${sessionId.trim()}`);
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${res.statusText}`);
  }
  return await res.json();
}

/**
 * Run Stage 3 Designer generation
 */
export async function apiGenerateDesignerArtifacts(sessionId: string): Promise<any> {
  const res = await fetch(`${ENGINE_BASE_URL}/designer/generate/${sessionId.trim()}`, {
    method: "POST"
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    throw new Error(errData?.detail || `HTTP ${res.status}`);
  }
  return await res.json();
}

/**
 * Get current Designer session state and artifacts
 */
export async function apiGetDesignerSession(sessionId: string): Promise<{
  session_id: string;
  has_output: boolean;
  state: any;
  app_flow_content: string;
  design_brief_content: string;
  validation: any;
  judge_verdict: any;
}> {
  const res = await fetch(`${ENGINE_BASE_URL}/designer/session/${sessionId.trim()}`);
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${res.statusText}`);
  }
  return await res.json();
}

/**
 * Fetch LLM settings, active models, and role configurations
 */
export async function apiGetLLMSettings(sessionId?: string): Promise<LLMSettings> {
  const url = sessionId
    ? `${ENGINE_BASE_URL}/settings/llm?session_id=${encodeURIComponent(sessionId)}`
    : `${ENGINE_BASE_URL}/settings/llm`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to fetch LLM settings: HTTP ${res.status}`);
  }
  return await res.json();
}

/**
 * Update role LLM configuration (provider, model, temperature, max_tokens)
 */
export async function apiUpdateLLMSettings(
  role: string,
  config: Partial<RoleConfig>
): Promise<any> {
  const res = await fetch(`${ENGINE_BASE_URL}/settings/llm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role, ...config })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.detail || `HTTP ${res.status}`);
  }
  return await res.json();
}

/**
 * Toggle per-project Local-Only mode (forces Ollama)
 */
export async function apiToggleLocalOnly(
  sessionId: string,
  localOnly: boolean
): Promise<{ status: string; session_id: string; local_only: boolean }> {
  const res = await fetch(`${ENGINE_BASE_URL}/settings/local-only`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, local_only: localOnly })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.detail || `HTTP ${res.status}`);
  }
  return await res.json();
}

/**
 * Specialist Skill Pack Interfaces and API Helpers
 */
export interface SpecialistSkillPack {
  id: string;
  name: string;
  version: string;
  description: string;
  compatible_roles: string[];
  triggers: {
    keywords: string[];
    signals: string[];
  };
  required_tools: string[];
  forbidden_tools: string[];
  rubric_path: string;
  dir_path?: string;
  has_instructions: boolean;
  has_standards: boolean;
  has_checklist: boolean;
  has_rubric: boolean;
}

export interface SpecialistEvidenceItem {
  id: string;
  type: string;
  trigger: string;
  snippet: string;
  source: string;
}

export interface SpecialistNeed {
  pack_id: string;
  name: string;
  version: string;
  status: string;
  confidence: string;
  evidence_count: number;
  evidence: SpecialistEvidenceItem[];
  adr_recommendation: string;
}

export interface SpecialistDetectionResult {
  specialist_needs: SpecialistNeed[];
  weak_matches: Array<{
    pack_id: string;
    name: string;
    version: string;
    status: string;
    confidence: string;
    open_question?: {
      id: string;
      to: string;
      text: string;
      why: string;
      refs: string[];
    };
  }>;
  open_questions: Array<{
    id: string;
    to: string;
    text: string;
    why: string;
    refs: string[];
  }>;
}

export async function fetchSkillPacks(): Promise<{ packs: SpecialistSkillPack[]; total: number; broken_count: number }> {
  const res = await fetch(`${ENGINE_BASE_URL}/skills/packs`);
  if (!res.ok) {
    throw new Error(`Failed to fetch skill packs: ${res.statusText}`);
  }
  return res.json();
}

export async function detectSpecialistNeeds(sessionId: string): Promise<SpecialistDetectionResult> {
  const res = await fetch(`${ENGINE_BASE_URL}/skills/detect/${sessionId}`, { method: "POST" });
  if (!res.ok) {
    throw new Error(`Failed to detect specialist needs: ${res.statusText}`);
  }
  return res.json();
}

export async function attachSkillPack(
  sessionId: string,
  role: string,
  packId: string,
  agentId?: string
): Promise<any> {
  const res = await fetch(`${ENGINE_BASE_URL}/skills/attach`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, role, pack_id: packId, agent_id: agentId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to attach skill pack");
  }
  return res.json();
}

export async function detachSkillPack(
  sessionId: string,
  role: string,
  packId: string,
  agentId?: string
): Promise<any> {
  const res = await fetch(`${ENGINE_BASE_URL}/skills/detach`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, role, pack_id: packId, agent_id: agentId }),
  });
  if (!res.ok) {
    throw new Error(`Failed to detach skill pack: ${res.statusText}`);
  }
  return res.json();
}

/**
 * Stage 4 Staffing (HR & Recruiter), Gate 2, & Budget API Functions
 */
export async function apiRunHrPlan(sessionId: string): Promise<TeamPlanData> {
  const res = await fetch(`${ENGINE_BASE_URL}/hr/plan/${sessionId}`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to generate HR staffing plan");
  }
  return res.json();
}

export async function apiGetHrTeamPlan(sessionId: string): Promise<TeamPlanData> {
  const res = await fetch(`${ENGINE_BASE_URL}/hr/team-plan/${sessionId}`);
  if (!res.ok) {
    throw new Error(`Failed to retrieve HR team plan: ${res.statusText}`);
  }
  return res.json();
}

export async function apiRunRecruiterHire(sessionId: string): Promise<any> {
  const res = await fetch(`${ENGINE_BASE_URL}/recruiter/hire/${sessionId}`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to execute Recruiter hiring");
  }
  return res.json();
}

export async function apiGetRecruiterAgents(
  sessionId: string
): Promise<{ session_id: string; agents: AgentProfile[]; count: number }> {
  const res = await fetch(`${ENGINE_BASE_URL}/recruiter/agents/${sessionId}`);
  if (!res.ok) {
    throw new Error(`Failed to retrieve hired agents: ${res.statusText}`);
  }
  return res.json();
}

export async function apiGetRecruiterReport(
  sessionId: string
): Promise<{ session_id: string; content: string }> {
  const res = await fetch(`${ENGINE_BASE_URL}/recruiter/report/${sessionId}`);
  if (!res.ok) {
    throw new Error(`Failed to retrieve staffing report: ${res.statusText}`);
  }
  return res.json();
}

export async function apiGetGate2Status(sessionId: string): Promise<Gate2State> {
  const res = await fetch(`${ENGINE_BASE_URL}/gate2/status/${sessionId}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch Gate 2 status: ${res.statusText}`);
  }
  return res.json();
}

export async function apiApproveGate2(sessionId: string, clientNotes?: string): Promise<any> {
  const res = await fetch(`${ENGINE_BASE_URL}/gate2/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, client_notes: clientNotes }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to approve Gate 2");
  }
  return res.json();
}

export async function apiRequestGate2Changes(sessionId: string, feedback: string): Promise<any> {
  const res = await fetch(`${ENGINE_BASE_URL}/gate2/request-changes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, feedback }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to request changes at Gate 2");
  }
  return res.json();
}

export async function apiGetBudgetStatus(
  sessionId: string
): Promise<{ session_id: string; guard: BudgetGuardStatus; recomputation: any }> {
  const res = await fetch(`${ENGINE_BASE_URL}/budget/status/${sessionId}`);
  if (!res.ok) {
    throw new Error(`Failed to retrieve budget status: ${res.statusText}`);
  }
  return res.json();
}

export async function apiStartScrumStage(sessionId: string): Promise<any> {
  const res = await fetch(`${ENGINE_BASE_URL}/scrum/start/${sessionId}`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to start Scrum stage");
  }
  return res.json();
}

