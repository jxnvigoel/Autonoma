import os
import json
import sqlite3
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

logger = logging.getLogger("autonoma-engine.token_ledger")

# Default database location
DEFAULT_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "office.db"))

# Seed baseline dataset: clearly marked as starting default baseline,
# not presented as real project history, as required by Handbook Section 5.1.6
SEED_DEFAULT_RATES: List[Dict[str, Any]] = [
    {
        "role": "BA",
        "item_type": "requirements_doc",
        "avg_tokens": 3500,
        "sample_count": 0,
        "source": "seed_default",
        "notes": "Starting default baseline rate before project history is accumulated."
    },
    {
        "role": "PM",
        "item_type": "prd_doc",
        "avg_tokens": 4200,
        "sample_count": 0,
        "source": "seed_default",
        "notes": "Starting default baseline rate before project history is accumulated."
    },
    {
        "role": "Architect",
        "item_type": "architecture_doc",
        "avg_tokens": 4800,
        "sample_count": 0,
        "source": "seed_default",
        "notes": "Starting default baseline rate before project history is accumulated."
    },
    {
        "role": "UI/UX Designer",
        "item_type": "design_doc",
        "avg_tokens": 2800,
        "sample_count": 0,
        "source": "seed_default",
        "notes": "Starting default baseline rate before project history is accumulated."
    },
    {
        "role": "Scrum Master",
        "item_type": "sprint_plan",
        "avg_tokens": 2200,
        "sample_count": 0,
        "source": "seed_default",
        "notes": "Starting default baseline rate before project history is accumulated."
    },
    {
        "role": "Engineer",
        "item_type": "story_small",
        "avg_tokens": 1800,
        "sample_count": 0,
        "source": "seed_default",
        "notes": "Starting default baseline rate for small stories (1-2 points)."
    },
    {
        "role": "Engineer",
        "item_type": "story_medium",
        "avg_tokens": 3600,
        "sample_count": 0,
        "source": "seed_default",
        "notes": "Starting default baseline rate for medium stories (3-5 points)."
    },
    {
        "role": "Engineer",
        "item_type": "story_large",
        "avg_tokens": 6500,
        "sample_count": 0,
        "source": "seed_default",
        "notes": "Starting default baseline rate for large stories (8+ points)."
    },
    {
        "role": "Tech Lead",
        "item_type": "code_review",
        "avg_tokens": 1500,
        "sample_count": 0,
        "source": "seed_default",
        "notes": "Starting default baseline rate for code review per story."
    },
    {
        "role": "QA Engineer",
        "item_type": "test_plan",
        "avg_tokens": 2600,
        "sample_count": 0,
        "source": "seed_default",
        "notes": "Starting default baseline rate for test plan and verification."
    },
    {
        "role": "DevOps",
        "item_type": "devops_deploy",
        "avg_tokens": 1800,
        "sample_count": 0,
        "source": "seed_default",
        "notes": "Starting default baseline rate for deployment automation."
    },
]


def init_token_ledger_db(db_path: str = DEFAULT_DB_PATH):
    """
    Initializes SQLite tables for the token ledger and rates, seeding default rates if absent.
    """
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        # Table 1: llm_calls ledger (Handbook Chapter 24)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS llm_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                task_id TEXT,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                cached_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL,
                cost_usd REAL NOT NULL DEFAULT 0,
                latency_ms INTEGER,
                stop TEXT,
                at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_llm_calls_project ON llm_calls(project_id, agent_id);")

        # Table 2: token_rates (historical averages & seed defaults)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS token_rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                item_type TEXT NOT NULL,
                avg_tokens INTEGER NOT NULL,
                sample_count INTEGER NOT NULL DEFAULT 0,
                source TEXT NOT NULL,
                notes TEXT,
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(role, item_type)
            );
        """)

        # Seed defaults if not yet populated
        for item in SEED_DEFAULT_RATES:
            cur.execute("""
                INSERT OR IGNORE INTO token_rates (role, item_type, avg_tokens, sample_count, source, notes)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (
                item["role"],
                item["item_type"],
                item["avg_tokens"],
                item["sample_count"],
                item["source"],
                item["notes"],
            ))
        conn.commit()
    finally:
        conn.close()


def get_rate_for_item(role: str, item_type: str, db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    Retrieves the historical average tokens for a given role and item_type.
    If real calls exist in llm_calls for this role, computes real historical average.
    Otherwise returns seed default rate marked as 'seed_default'.
    """
    init_token_ledger_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()

        # Check if we have real historical data for this agent in llm_calls
        cur.execute("""
            SELECT AVG(input_tokens + output_tokens), COUNT(*)
            FROM llm_calls
            WHERE agent_id = ?
        """, (role.lower(),))
        row = cur.fetchone()

        if row and row[1] and row[1] >= 2 and row[0] is not None:
            return {
                "role": role,
                "item_type": item_type,
                "avg_tokens": int(round(row[0])),
                "sample_count": row[1],
                "source": "historical_ledger",
                "notes": f"Computed from {row[1]} actual historical LLM calls in ledger."
            }

        # Otherwise read from token_rates table
        cur.execute("""
            SELECT avg_tokens, sample_count, source, notes
            FROM token_rates
            WHERE role = ? AND item_type = ?
        """, (role, item_type))
        rate_row = cur.fetchone()

        if rate_row:
            return {
                "role": role,
                "item_type": item_type,
                "avg_tokens": rate_row[0],
                "sample_count": rate_row[1],
                "source": rate_row[2],
                "notes": rate_row[3],
            }

        # Fallback to in-memory seed default
        for item in SEED_DEFAULT_RATES:
            if item["role"] == role and item["item_type"] == item_type:
                return dict(item)

        return {
            "role": role,
            "item_type": item_type,
            "avg_tokens": 3000,
            "sample_count": 0,
            "source": "seed_default",
            "notes": "Fallback default rate."
        }
    finally:
        conn.close()


def record_llm_call(
    project_id: str,
    agent_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    provider: str = "ollama",
    cached_tokens: int = 0,
    cost_usd: float = 0.0,
    latency_ms: Optional[int] = None,
    task_id: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH
):
    """
    Appends an entry to the llm_calls token ledger table.
    """
    try:
        init_token_ledger_db(db_path)
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO llm_calls (
                    project_id, agent_id, task_id, provider, model,
                    input_tokens, cached_tokens, output_tokens, cost_usd, latency_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                project_id, agent_id.lower(), task_id, provider, model,
                input_tokens, cached_tokens, output_tokens, cost_usd, latency_ms
            ))
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"Failed to record LLM call to ledger: {e}")


PRICING_CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config", "model_pricing.json"))


def get_model_price(model_name: str, provider: str = "groq") -> Dict[str, Any]:
    if provider == "ollama" or model_name.startswith("ollama") or model_name == "llama3.2:3b":
        return {
            "input_per_1k": 0.0,
            "output_per_1k": 0.0,
            "blended_per_1k": 0.0,
            "is_local": True,
            "provider": "ollama"
        }

    rates = {}
    if os.path.exists(PRICING_CONFIG_PATH):
        try:
            with open(PRICING_CONFIG_PATH, "r", encoding="utf-8") as f:
                rates = json.load(f).get("rates", {})
        except Exception:
            rates = {}

    model_rate = rates.get(
        model_name,
        rates.get("default_cloud", {"input_per_million": 0.20, "output_per_million": 0.50})
    )
    in_1k = model_rate.get("input_per_million", 0.20) / 1000.0
    out_1k = model_rate.get("output_per_million", 0.50) / 1000.0
    # Weighted average: 60% input, 40% output
    blended = (in_1k * 0.6) + (out_1k * 0.4)

    return {
        "input_per_1k": in_1k,
        "output_per_1k": out_1k,
        "blended_per_1k": round(blended, 6),
        "is_local": False,
        "provider": provider or "groq"
    }


def calculate_project_estimate(
    session_id: str,
    project_name: str,
    features: List[Dict[str, Any]],
    model_name: Optional[str] = None,
    provider: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH
) -> Dict[str, Any]:
    """
    Calculates the token and cost estimate strictly following Handbook Section 5.1.6:
    tokens(stage) = Σ over planned artifacts and stories:
      historical_avg_tokens(role, artifact_type or story_points)
    total = Σ tokens(stage) × 1.20 (20% rework buffer)
    cost_usd = Σ over roles: tokens(role) × price(model of that role) (local models: $0)
    """
    # If model_name or provider not provided, detect from llm_client if available
    active_provider = provider or "groq"
    active_model = model_name or "openai/gpt-oss-120b"
    try:
        from llm_client import default_llm_client
        if default_llm_client.is_project_local_only(session_id):
            active_provider = "ollama"
            active_model = "llama3.2:3b"
        elif not default_llm_client.is_groq_configured():
            active_provider = "ollama"
            active_model = "llama3.2:3b"
        elif not model_name:
            active_model = default_llm_client.role_configs.get("pm", {}).get("model", "openai/gpt-oss-120b")
    except Exception:
        try:
            from engine.llm_client import default_llm_client
            if default_llm_client.is_project_local_only(session_id):
                active_provider = "ollama"
                active_model = "llama3.2:3b"
            elif not default_llm_client.is_groq_configured():
                active_provider = "ollama"
                active_model = "llama3.2:3b"
            elif not model_name:
                active_model = default_llm_client.role_configs.get("pm", {}).get("model", "openai/gpt-oss-120b")
        except Exception:
            pass
    # Size stories based on acceptance criteria count
    small_stories = 0
    medium_stories = 0
    large_stories = 0

    if not features:
        # Default minimum stories if no features parsed
        small_stories = 1
        medium_stories = 2
        large_stories = 0
    else:
        for f in features:
            ac_list = f.get("acceptance_criteria", [])
            ac_count = len(ac_list)
            priority = str(f.get("priority", "")).lower()

            # Out of scope / won't have are not planned for v1 implementation
            if "won't" in priority or "deferred" in priority or "v2" in priority:
                continue

            if ac_count <= 2:
                small_stories += 1
            elif ac_count <= 4:
                medium_stories += 1
            else:
                large_stories += 1

    total_stories = small_stories + medium_stories + large_stories
    if total_stories == 0:
        total_stories = max(1, len(features))
        medium_stories = total_stories

    # Rates from ledger
    r_ba = get_rate_for_item("BA", "requirements_doc", db_path)
    r_pm = get_rate_for_item("PM", "prd_doc", db_path)
    r_arch = get_rate_for_item("Architect", "architecture_doc", db_path)
    r_design = get_rate_for_item("UI/UX Designer", "design_doc", db_path)
    r_scrum = get_rate_for_item("Scrum Master", "sprint_plan", db_path)
    r_small = get_rate_for_item("Engineer", "story_small", db_path)
    r_med = get_rate_for_item("Engineer", "story_medium", db_path)
    r_lrg = get_rate_for_item("Engineer", "story_large", db_path)
    r_rev = get_rate_for_item("Tech Lead", "code_review", db_path)
    r_qa = get_rate_for_item("QA Engineer", "test_plan", db_path)
    r_devops = get_rate_for_item("DevOps", "devops_deploy", db_path)

    # Stages calculation
    eng_tokens = (
        small_stories * r_small["avg_tokens"] +
        medium_stories * r_med["avg_tokens"] +
        large_stories * r_lrg["avg_tokens"]
    )
    rev_tokens = total_stories * r_rev["avg_tokens"]

    stages = [
        {
            "stage_id": "STAGE-01",
            "stage": "Requirements Discovery",
            "role": "Business Analyst (BA)",
            "planned_artifacts": ["docs/requirements.md"],
            "unit_type": "artifact",
            "unit_count": 1,
            "historical_rate_per_unit": r_ba["avg_tokens"],
            "subtotal_tokens": r_ba["avg_tokens"],
            "rate_source": r_ba["source"],
        },
        {
            "stage_id": "STAGE-02",
            "stage": "Product Planning",
            "role": "Product Manager (PM)",
            "planned_artifacts": ["docs/prd.md", "docs/estimate.json"],
            "unit_type": "artifact",
            "unit_count": 1,
            "historical_rate_per_unit": r_pm["avg_tokens"],
            "subtotal_tokens": r_pm["avg_tokens"],
            "rate_source": r_pm["source"],
        },
        {
            "stage_id": "STAGE-03",
            "stage": "System Architecture",
            "role": "Solution Architect",
            "planned_artifacts": ["docs/architecture.md", "ADR records"],
            "unit_type": "artifact",
            "unit_count": 1,
            "historical_rate_per_unit": r_arch["avg_tokens"],
            "subtotal_tokens": r_arch["avg_tokens"],
            "rate_source": r_arch["source"],
        },
        {
            "stage_id": "STAGE-04",
            "stage": "UI/UX Design",
            "role": "UI/UX Designer",
            "planned_artifacts": ["docs/design_system.md", "wireframes"],
            "unit_type": "artifact",
            "unit_count": 1,
            "historical_rate_per_unit": r_design["avg_tokens"],
            "subtotal_tokens": r_design["avg_tokens"],
            "rate_source": r_design["source"],
        },
        {
            "stage_id": "STAGE-05",
            "stage": "Sprint Planning",
            "role": "Scrum Master",
            "planned_artifacts": ["sprint_plan.json", "story_backlog"],
            "unit_type": "artifact",
            "unit_count": 1,
            "historical_rate_per_unit": r_scrum["avg_tokens"],
            "subtotal_tokens": r_scrum["avg_tokens"],
            "rate_source": r_scrum["source"],
        },
        {
            "stage_id": "STAGE-06",
            "stage": "Implementation",
            "role": "Software Engineers",
            "planned_artifacts": [f"{total_stories} User Stories ({small_stories}S / {medium_stories}M / {large_stories}L)"],
            "unit_type": "stories",
            "unit_count": total_stories,
            "historical_rate_per_unit": int(round(eng_tokens / total_stories)) if total_stories > 0 else 0,
            "subtotal_tokens": eng_tokens,
            "rate_source": r_med["source"],
        },
        {
            "stage_id": "STAGE-07",
            "stage": "Code Review",
            "role": "Tech Lead",
            "planned_artifacts": [f"{total_stories} Pull Request Reviews"],
            "unit_type": "reviews",
            "unit_count": total_stories,
            "historical_rate_per_unit": r_rev["avg_tokens"],
            "subtotal_tokens": rev_tokens,
            "rate_source": r_rev["source"],
        },
        {
            "stage_id": "STAGE-08",
            "stage": "Quality Assurance",
            "role": "QA Engineer",
            "planned_artifacts": ["docs/test_plan.md", "test_execution_report"],
            "unit_type": "artifact",
            "unit_count": 1,
            "historical_rate_per_unit": r_qa["avg_tokens"],
            "subtotal_tokens": r_qa["avg_tokens"],
            "rate_source": r_qa["source"],
        },
        {
            "stage_id": "STAGE-09",
            "stage": "Deployment & DevOps",
            "role": "DevOps Engineer",
            "planned_artifacts": ["deploy_manifests", "dockerfile"],
            "unit_type": "artifact",
            "unit_count": 1,
            "historical_rate_per_unit": r_devops["avg_tokens"],
            "subtotal_tokens": r_devops["avg_tokens"],
            "rate_source": r_devops["source"],
        },
    ]

    subtotal_tokens = sum(s["subtotal_tokens"] for s in stages)
    # 20% rework buffer as specified in Handbook 5.1.6
    rework_buffer_percentage = 20
    rework_buffer_tokens = int(round(subtotal_tokens * 0.20))
    total_tokens = subtotal_tokens + rework_buffer_tokens

    pricing_info = get_model_price(active_model, provider=active_provider)
    is_local_model = pricing_info["is_local"]
    cost_usd = 0.0 if is_local_model else round(total_tokens * (pricing_info["blended_per_1k"] / 1000.0), 4)

    return {
        "project_name": project_name,
        "session_id": session_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": active_model,
        "provider": active_provider,
        "model_pricing": {
            "provider": active_provider,
            "model": active_model,
            "is_local": is_local_model,
            "price_per_1k_tokens_usd": pricing_info["blended_per_1k"],
            "input_per_1k_usd": pricing_info["input_per_1k"],
            "output_per_1k_usd": pricing_info["output_per_1k"],
            "pricing_source": "config/model_pricing.json",
            "notes": "Local models cost $0 but still count tokens. Cloud models charge per 1M tokens based on config/model_pricing.json."
        },
        "ledger_metadata": {
            "source": "seed_default",
            "description": "Historical averages ledger initialized with starting default baseline rates. Rates automatically recalibrate as completed project runs accrue in llm_calls table.",
            "db_path": db_path,
        },
        "formula": "tokens(stage) = Σ historical_avg_tokens(role, artifact or story_points); total = Σ tokens(stage) × 1.20 (20% rework buffer); cost_usd = Σ tokens(role) × price(model)",
        "stories_by_size": {
            "small": small_stories,
            "medium": medium_stories,
            "large": large_stories,
            "total_stories": total_stories
        },
        "stages": stages,
        "subtotal_tokens": subtotal_tokens,
        "rework_buffer_percentage": rework_buffer_percentage,
        "rework_buffer_tokens": rework_buffer_tokens,
        "total_estimated_tokens": total_tokens,
        "estimated_cost_usd": cost_usd,
    }
