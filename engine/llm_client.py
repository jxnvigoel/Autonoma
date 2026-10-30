"""
LLM client and model router (Handbook Chapters 22, 23.3, 26.4).

Routing (Handbook 22.4):
- Every role routes through config/model_router.json (role -> tier -> ordered provider list);
  the configured order is Groq first, local Ollama as the fallback.
- Cloud is used only while cloud is enabled (router `cloud_enabled`, config/runtime.json, or
  AUTONOMA_ALLOW_CLOUD) AND the project is not local-only. With cloud disabled the client makes
  no outbound request at all; only the local Ollama server is called.
- A failed cloud call falls back to the best installed local model and is marked degraded.
- latency_ms in the ledger is the duration of the model request itself; time spent
  waiting on rate limits or backoff is recorded separately as wait_ms.
- Before every call the project budget guard runs; at 100% the call is refused
  (Handbook 26.4 hard pause) until the client raises the budget.
"""

import os
import re
import json
import time
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Callable

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("autonoma-engine.llm_client")

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(ENGINE_DIR)
PRICING_FILE = os.path.join(PROJECT_ROOT, "config", "model_pricing.json")
ROUTER_FILE = os.path.join(PROJECT_ROOT, "config", "model_router.json")
RUNTIME_FILE = os.path.join(PROJECT_ROOT, "config", "runtime.json")
FALLBACK_LOG_FILE = os.path.join(PROJECT_ROOT, "data", "llm_fallbacks.json")
DATA_PROJECTS_DIR = os.path.join(PROJECT_ROOT, "data", "projects")

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def _load_json_file(path: str, default: Any) -> Any:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not read {path}: {e}")
    return default


def load_router() -> Dict[str, Any]:
    return _load_json_file(ROUTER_FILE, {"tiers": {}, "roles": {}})


# Local default model: env override, else router config, else a small common model.
OLLAMA_DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL") or load_router().get("local_default_model", "gemma3:1b")

# Per-role sampling defaults. Models are never named here; they come from the router.
ROLE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "ba": {"temperature": 0.2, "max_tokens": 1000},
    "pm": {"temperature": 0.2, "max_tokens": 1200},
    "architect": {"temperature": 0.2, "max_tokens": 3000},
    "designer": {"temperature": 0.2, "max_tokens": 1500},
    "judge": {"temperature": 0.1, "max_tokens": 3000},  # reasoning models need room before the verdict
    "hr": {"temperature": 0.2, "max_tokens": 2048},
    "recruiter": {"temperature": 0.2, "max_tokens": 2048},
    "scrum": {"temperature": 0.2, "max_tokens": 4096},
    "tech-lead": {"temperature": 0.1, "max_tokens": 4096},
    "engineer": {"temperature": 0.2, "max_tokens": 8192},
    "frontend": {"temperature": 0.2, "max_tokens": 8192},
    "backend": {"temperature": 0.2, "max_tokens": 8192},
    "fullstack": {"temperature": 0.2, "max_tokens": 8192},
    "qa": {"temperature": 0.2, "max_tokens": 4096},
    "perf": {"temperature": 0.2, "max_tokens": 4096},
    "devops": {"temperature": 0.2, "max_tokens": 4096},
    "general": {"temperature": 0.4, "max_tokens": 4096},
}

TIER_ORDER = ["high", "medium", "low"]


class GroqKeyMissingError(Exception):
    """Raised when cloud is enabled but GROQ_API_KEY is missing."""
    pass


class LLMRateLimitExhaustedError(Exception):
    """Raised when all rate limit retries are exhausted on Groq."""
    pass


class DailyQuotaError(Exception):
    """A cloud model's daily limit is used up; `retry_s` is when the provider says it frees up."""

    def __init__(self, message: str, retry_s: Optional[float]):
        super().__init__(message)
        self.retry_s = retry_s


class BudgetExhaustedError(Exception):
    """Raised when the project budget guard is at 100% (Handbook 26.4 hard pause)."""
    pass


class NoLocalModelError(Exception):
    """Raised when no usable local Ollama model is installed."""
    pass


# ==============================================================================
# PRICING HELPERS
# ==============================================================================

def load_pricing_config() -> Dict[str, Any]:
    return _load_json_file(PRICING_FILE, {"rates": {}})


def calculate_cost_usd(model: str, input_tokens: int, output_tokens: int, provider: str = "groq") -> float:
    if provider in ("ollama", "fake") or model.startswith("ollama"):
        return 0.0
    pricing = load_pricing_config().get("rates", {})
    rate = pricing.get(model, pricing.get("default_cloud", {"input_per_million": 0.20, "output_per_million": 0.50}))
    in_price = rate.get("input_per_million", 0.20) / 1_000_000.0
    out_price = rate.get("output_per_million", 0.50) / 1_000_000.0
    return round((input_tokens * in_price) + (output_tokens * out_price), 6)


def parse_retry_seconds(text: str, retry_after: Optional[str] = None) -> Optional[float]:
    """Seconds until a rate limit resets, from Groq's message ("try again in 7m33.1s") or Retry-After."""
    m = re.search(r"try again in (?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?", text or "")
    if m and any(m.groups()):
        h, mi, sec = (float(g) if g else 0.0 for g in m.groups())
        return h * 3600 + mi * 60 + sec
    try:
        return float(retry_after) if retry_after else None
    except ValueError:
        return None


def network_available(host: str) -> bool:
    """True when the host name resolves (the machine is online)."""
    import socket
    try:
        socket.getaddrinfo(host, 443)
        return True
    except OSError:
        return False


def wait_for_network(host: str, max_s: float, step_s: float = 15.0) -> float:
    """Waits until `host` resolves again or `max_s` passes. Returns the seconds waited."""
    waited = 0.0
    if not network_available(host):
        logger.warning(f"network is down ({host} does not resolve); waiting up to {max_s:.0f}s for it to return")
    while waited < max_s and not network_available(host):
        time.sleep(step_s)
        waited += step_s
    return waited


def score_model_capability(model_id: str) -> float:
    """Approximate capability by parameter count parsed from the model name (e.g. '7b', '120b')."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*b\b", model_id.lower().replace("-", " ").replace(":", " "))
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return 1.0


def parse_duration_s(text: Optional[str]) -> Optional[float]:
    """Groq header durations such as '7.66s', '1m2.5s', '120ms'."""
    if not text:
        return None
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m(?!s))?(?:([\d.]+)s)?(?:([\d.]+)ms)?", text.strip())
    if not m or not any(m.groups()):
        try:
            return float(text)
        except ValueError:
            return None
    h, mi, sec, ms = (float(g) if g else 0.0 for g in m.groups())
    return h * 3600 + mi * 60 + sec + ms / 1000.0


class RateTracker:
    """
    Per-model view of provider rate limits (Groq limits are per model per organisation).
    Learned from x-ratelimit-* response headers and from 429 messages ("... (OTPM): Limit 1000"),
    so calls are planned instead of fired blindly into 429s.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._models: Dict[str, Dict[str, Any]] = {}

    def _get(self, model: str) -> Dict[str, Any]:
        return self._models.setdefault(model, {"tpm_remaining": None, "tpm_reset_at": 0.0, "limits": {},
                                               "out": [], "last_at": 0.0, "blocked_until": 0.0})

    def block(self, model: str, seconds: float) -> None:
        """A daily limit was hit: the model takes no calls until its quota frees up."""
        with self._lock:
            self._get(model)["blocked_until"] = max(self._get(model)["blocked_until"], time.time() + seconds)

    def update_from_headers(self, model: str, headers: Any) -> None:
        with self._lock:
            st = self._get(model)
            rem, reset = headers.get("x-ratelimit-remaining-tokens"), headers.get("x-ratelimit-reset-tokens")
            lim = headers.get("x-ratelimit-limit-tokens")
            try:
                if rem is not None:
                    st["tpm_remaining"] = int(float(rem))
                if lim is not None:
                    st["limits"]["TPM"] = int(float(lim))
            except ValueError:
                pass
            d = parse_duration_s(reset)
            if d is not None:
                st["tpm_reset_at"] = time.time() + d

    def learn_from_429(self, model: str, text: str) -> None:
        m = re.search(r"\((\w+)\): Limit (\d+)", text or "")
        if m:
            with self._lock:
                self._get(model)["limits"][m.group(1).upper()] = int(m.group(2))

    def record_call(self, model: str, output_tokens: int) -> None:
        with self._lock:
            st = self._get(model)
            now = time.time()
            st["out"] = [(t, n) for t, n in st["out"] if now - t < 60] + [(now, int(output_tokens or 0))]
            st["last_at"] = now

    def max_output(self, model: str, requested: int) -> int:
        """Never ask for more output than the model's per-minute output limit allows."""
        limit = self._get(model)["limits"].get("OTPM")
        return min(int(requested), max(256, int(limit * 0.9))) if limit else int(requested)

    def wait_needed(self, model: str, est_input: int, est_output: int) -> float:
        """Seconds to wait before this call fits the model's known per-minute limits (0 = send now)."""
        with self._lock:
            st = self._get(model)
            now = time.time()
            wait = max(0.0, st.get("blocked_until", 0.0) - now)
            if st["tpm_remaining"] is not None and st["tpm_reset_at"] > now and est_input + est_output > st["tpm_remaining"]:
                wait = st["tpm_reset_at"] - now
            limit = st["limits"].get("OTPM")
            window = [(t, n) for t, n in st["out"] if now - t < 60]
            used = sum(n for _, n in window)
            if limit and window and used + est_output > limit:
                need, freed = used + est_output - limit, 0
                for t, n in window:
                    freed += n
                    if freed >= need:
                        wait = max(wait, t + 60 - now)
                        break
                else:
                    wait = max(wait, window[-1][0] + 60 - now)
            return max(0.0, wait)


# ==============================================================================
# MODEL ROUTER & CLIENT
# ==============================================================================

class LLMClient:
    def __init__(self):
        self._lock = threading.Lock()
        self._cached_groq_models: Optional[List[Dict[str, Any]]] = None
        self._cached_groq_models_time: float = 0.0
        self._cached_ollama_models: Optional[List[Dict[str, Any]]] = None
        self._cached_ollama_time: float = 0.0
        self._project_local_only: Dict[str, bool] = {}
        self._overrides: Dict[str, Dict[str, Any]] = {}
        self._fake_responder: Optional[Callable[..., str]] = None
        self._call_listeners: List[Callable[[Dict[str, Any]], None]] = []
        self._current = threading.local()  # the call this thread is making, for "waiting" notices
        self.budget_guard_enabled: bool = True
        self.ledger_db_path: Optional[str] = None  # tests point this at a temporary database
        self.rates = RateTracker()
        # No network access here: nothing is fetched until a role is actually used.

    # ---------------------------------------------------------------- config

    @property
    def router(self) -> Dict[str, Any]:
        return load_router()

    def cloud_enabled(self) -> bool:
        env = os.environ.get("AUTONOMA_ALLOW_CLOUD", "").strip().lower()
        if env in ("0", "false", "no"):
            return False
        runtime = _load_json_file(RUNTIME_FILE, {})
        enabled = env in ("1", "true", "yes") or bool(runtime.get("cloud_enabled", self.router.get("cloud_enabled", False)))
        return enabled and self.is_groq_configured()

    def set_cloud_enabled(self, enabled: bool) -> None:
        runtime = _load_json_file(RUNTIME_FILE, {})
        runtime["cloud_enabled"] = bool(enabled)
        os.makedirs(os.path.dirname(RUNTIME_FILE), exist_ok=True)
        with open(RUNTIME_FILE, "w", encoding="utf-8") as f:
            json.dump(runtime, f, indent=2)
        self._cached_groq_models = None

    def get_api_key(self) -> str:
        load_dotenv(override=True)
        key = os.environ.get("GROQ_API_KEY", "").strip()
        if (key.startswith("'") and key.endswith("'")) or (key.startswith('"') and key.endswith('"')):
            key = key[1:-1].strip()
        return key

    def is_groq_configured(self) -> bool:
        key = self.get_api_key()
        return bool(key and len(key) >= 10 and not key.startswith("your_"))

    def get_masked_api_key(self) -> str:
        key = self.get_api_key()
        if not key:
            return ""
        if len(key) <= 8:
            return "gsk_••••"
        return f"{key[:4]}••••••••••••••••••••••••••••••••{key[-4:]}"

    def set_project_local_only(self, session_id: str, local_only: bool) -> None:
        self._project_local_only[session_id] = local_only
        state_file = os.path.join(DATA_PROJECTS_DIR, session_id, "session_state.json")
        if os.path.exists(state_file):
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["local_only"] = local_only
                with open(state_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                logger.warning(f"Could not persist local_only to {state_file}: {e}")

    def is_project_local_only(self, session_id: Optional[str]) -> bool:
        """Explicit per-project setting wins; otherwise projects are local-only unless cloud is enabled."""
        if session_id:
            if session_id in self._project_local_only:
                return self._project_local_only[session_id]
            state_file = os.path.join(DATA_PROJECTS_DIR, session_id, "session_state.json")
            data = _load_json_file(state_file, {})
            if isinstance(data, dict) and "local_only" in data:
                val = bool(data["local_only"])
                self._project_local_only[session_id] = val
                return val
        return not self.cloud_enabled()

    def cloud_allowed(self, session_id: Optional[str]) -> bool:
        return self.cloud_enabled() and not self.is_project_local_only(session_id)

    # --------------------------------------------------------------- health

    def fetch_groq_models(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Live Groq model list. Returns [] without any network call while cloud is disabled."""
        if not self.cloud_enabled():
            return []
        now = time.time()
        if not force_refresh and self._cached_groq_models is not None and (now - self._cached_groq_models_time < 300):
            return self._cached_groq_models
        try:
            res = requests.get(f"{GROQ_BASE_URL}/models", headers={"Authorization": f"Bearer {self.get_api_key()}"}, timeout=10)
            if res.status_code != 200:
                logger.warning(f"Groq GET /models returned {res.status_code}")
                return []
            models = []
            for m in res.json().get("data", []):
                mid = m.get("id", "")
                if any(x in mid.lower() for x in ["whisper", "guard", "embedding", "orpheus"]):
                    continue
                models.append({"id": mid, "owned_by": m.get("owned_by", "Groq"),
                               "context_window": m.get("context_window", 8192),
                               "capability_score": self._score_model_capability(mid)})
            models.sort(key=lambda x: x["capability_score"], reverse=True)
            self._cached_groq_models, self._cached_groq_models_time = models, now
            return models
        except Exception as e:
            logger.warning(f"Failed to fetch models from Groq: {e}")
            return []

    def list_ollama_models(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Installed local models from the local Ollama server (GET /api/tags)."""
        if self._fake_responder is not None:
            return [{"name": "fake-model", "size": 0, "capability_score": 1.0}]
        now = time.time()
        if not force_refresh and self._cached_ollama_models is not None and (now - self._cached_ollama_time < 30):
            return self._cached_ollama_models
        models: List[Dict[str, Any]] = []
        try:
            res = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=2)
            if res.status_code == 200:
                for m in res.json().get("models", []):
                    name = m.get("name", "")
                    models.append({"name": name, "size": m.get("size", 0), "capability_score": self._score_model_capability(name)})
        except Exception as e:
            logger.warning(f"Ollama not reachable at {OLLAMA_HOST}: {e}")
        self._cached_ollama_models, self._cached_ollama_time = models, now
        return models

    def _ollama_installed(self, model: str) -> Optional[str]:
        """Returns the installed tag matching `model` (with or without ':latest'), else None."""
        for m in self.list_ollama_models():
            name = m["name"]
            if name == model or name == f"{model}:latest" or name.split(":latest")[0] == model:
                return name
        return None

    def _score_model_capability(self, model_id: str) -> float:
        return score_model_capability(model_id)

    # -------------------------------------------------------------- routing

    def resolve_route(self, role: str, session_id: Optional[str] = None,
                      exclude_models: Optional[List[str]] = None, local_only: bool = False) -> Dict[str, Any]:
        """
        Handbook 22.4: first healthy entry of the role's tier, then lower tiers.
        Every downgrade is recorded with its expected quality effect (shown at Gate 2).
        """
        role_key = role.strip().lower()
        router = self.router
        effects = router.get("downgrade_quality_effects", {})
        target_tier = router.get("roles", {}).get(role_key, router.get("roles", {}).get("general", "medium"))
        exclude = set(exclude_models or [])
        cloud_ok = self.cloud_allowed(session_id) and not local_only

        if self._fake_responder is not None:
            return {"role": role_key, "target_tier": target_tier, "actual_tier": target_tier, "provider": "fake",
                    "model": "fake-model", "downgraded": False, "downgrade_note": "", "capability": 1.0}

        override = self._overrides.get(role_key, {})
        if override.get("provider") and override.get("model") and override["model"] not in exclude:
            prov, model = override["provider"], override["model"]
            if prov == "ollama" and self._ollama_installed(model):
                return {"role": role_key, "target_tier": target_tier, "actual_tier": "override", "provider": "ollama",
                        "model": self._ollama_installed(model), "downgraded": False,
                        "downgrade_note": "Model set manually in Settings.", "capability": self._score_model_capability(model)}
            if prov == "groq" and cloud_ok:
                return {"role": role_key, "target_tier": target_tier, "actual_tier": "override", "provider": "groq",
                        "model": model, "downgraded": False, "downgrade_note": "Model set manually in Settings.",
                        "capability": self._score_model_capability(model)}

        groq_ids = {m["id"] for m in self.fetch_groq_models()} if cloud_ok else set()
        start = TIER_ORDER.index(target_tier) if target_tier in TIER_ORDER else 1
        # Roles listed in local_first_roles try installed local models before Groq inside the same tier
        # (no downgrade: same tier, it just spares the cloud quota). Without Ollama they use Groq as before.
        local_first = role_key in set(router.get("local_first_roles", []))
        for tier in TIER_ORDER[start:]:
            cands = router.get("tiers", {}).get(tier, [])
            if local_first:
                cands = sorted(cands, key=lambda c: c.get("provider") != "ollama")
            for cand in cands:
                prov, model = cand.get("provider"), cand.get("model", "")
                if model in exclude:
                    continue
                chosen = None
                if prov == "ollama":
                    chosen = self._ollama_installed(model)
                elif prov == "groq" and model in groq_ids:
                    chosen = model
                if not chosen:
                    continue
                downgraded = tier != target_tier
                note = ""
                if downgraded:
                    effect = effects.get(f"{target_tier}_to_{tier}", "reduced quality")
                    note = f"{role_key}: tier '{target_tier}' unavailable, using '{tier}' ({prov}: {chosen}). Expected effect: {effect}"
                return {"role": role_key, "target_tier": target_tier, "actual_tier": tier, "provider": prov,
                        "model": chosen, "downgraded": downgraded, "downgrade_note": note,
                        "capability": self._score_model_capability(chosen)}

        # Nothing from the tier lists is available: use the local default model if installed.
        local_default = self._ollama_installed(OLLAMA_DEFAULT_MODEL)
        if local_default and local_default not in exclude:
            return {"role": role_key, "target_tier": target_tier, "actual_tier": "local-default", "provider": "ollama",
                    "model": local_default, "downgraded": target_tier != "low",
                    "downgrade_note": (f"{role_key}: no '{target_tier}' tier model installed; using local default "
                                       f"{local_default}. Expected effect: {effects.get('to_local_default', 'much lower quality')}")
                    if target_tier != "low" else "",
                    "capability": self._score_model_capability(local_default)}

        return {"role": role_key, "target_tier": target_tier, "actual_tier": "none", "provider": "none", "model": "",
                "downgraded": True, "capability": 0.0,
                "downgrade_note": (f"No usable model for '{role_key}'. Install one locally, e.g. "
                                   f"`ollama pull {OLLAMA_DEFAULT_MODEL}`.")}

    def resolve_judge_route(self, target_role: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Handbook 14.1.2 / 22.4 rule 3: the Judge uses a different model from the author where possible,
        and must not be weaker than the author.
        """
        gen = self.resolve_route(target_role, session_id)
        judge = self.resolve_route("judge", session_id)
        judge["generator_model"] = gen.get("model", "")
        judge["same_model_as_author"] = False
        judge["weaker_than_author"] = False
        if gen.get("model") and judge.get("model") == gen.get("model"):
            alt = self.resolve_route("judge", session_id, exclude_models=[gen["model"]])
            if alt.get("model") and alt.get("capability", 0) >= gen.get("capability", 0):
                alt["generator_model"] = gen["model"]
                alt["same_model_as_author"] = False
                alt["weaker_than_author"] = False
                judge = alt
            else:
                judge["same_model_as_author"] = True
        if judge.get("capability", 0) < gen.get("capability", 0):
            judge["weaker_than_author"] = True
        return judge

    def get_active_provider_and_model(self, role: str, session_id: Optional[str] = None) -> Tuple[str, str]:
        route = self.resolve_route(role, session_id)
        return (route["provider"], route["model"])

    @property
    def role_configs(self) -> Dict[str, Dict[str, Any]]:
        """Effective configuration per role, as resolved right now (read-only view for the UI)."""
        out: Dict[str, Dict[str, Any]] = {}
        roles = set(self.router.get("roles", {}).keys()) | set(ROLE_DEFAULTS.keys())
        for role in sorted(roles):
            route = self.resolve_route(role)
            cfg = dict(ROLE_DEFAULTS.get(role, ROLE_DEFAULTS["general"]))
            cfg.update({k: v for k, v in self._overrides.get(role, {}).items() if k in ("temperature", "max_tokens")})
            cfg.update({"provider": route["provider"], "model": route["model"], "tier": route["target_tier"],
                        "actual_tier": route["actual_tier"], "downgraded": route["downgraded"]})
            out[role] = cfg
        return out

    def update_role_config(self, role: str, provider: Optional[str] = None, model: Optional[str] = None,
                           temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> Dict[str, Any]:
        role_key = role.lower()
        ov = self._overrides.setdefault(role_key, {})
        if provider:
            ov["provider"] = provider
        if model:
            ov["model"] = model
        if temperature is not None:
            ov["temperature"] = temperature
        if max_tokens is not None:
            ov["max_tokens"] = max_tokens
        return self.role_configs.get(role_key, ov)

    def get_settings(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        fallbacks = self.get_fallbacks()
        return {
            "cloud_enabled": self.cloud_enabled(),
            "local_default_model": OLLAMA_DEFAULT_MODEL,
            "groq_configured": self.is_groq_configured(),
            "masked_api_key": self.get_masked_api_key(),
            "available_models": self.fetch_groq_models(),
            "local_models": self.list_ollama_models(),
            "role_configs": self.role_configs,
            "local_only": self.is_project_local_only(session_id),
            "fallback_count": len(fallbacks),
            "recent_fallbacks": fallbacks[-10:],
        }

    # ------------------------------------------------------- test / events

    def set_fake_responder(self, fn: Optional[Callable[..., str]]) -> None:
        """Deterministic fake provider for tests (Handbook 30.1). fn(prompt, system, role, task_id) -> text."""
        self._fake_responder = fn

    def add_call_listener(self, fn: Callable[[Dict[str, Any]], None]) -> None:
        if fn not in self._call_listeners:
            self._call_listeners.append(fn)

    def _notify(self, phase: str, **call: Any) -> None:
        """Tells listeners a call started, is waiting (rate limit / network), or finished ("done")."""
        if phase == "start":
            self._current.call = call
        elif phase == "waiting":
            call = {**getattr(self._current, "call", {}), **call}
        for listener in list(self._call_listeners):
            try:
                listener({"phase": phase, **call})
            except Exception as e:
                logger.debug(f"LLM call listener failed: {e}")

    def log_fallback(self, session_id: Optional[str], role: str, original_model: str, error: str,
                     duration_ms: int, fallback_model: str = "") -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id or "global",
            "role": role,
            "original_provider": "groq",
            "original_model": original_model,
            "fallback_provider": "ollama",
            "fallback_model": fallback_model,
            "reason": error,
            "duration_ms": duration_ms,
        }
        logger.warning(f"FALLBACK TO OLLAMA TRIGGERED: {json.dumps(record)}")
        try:
            os.makedirs(os.path.dirname(FALLBACK_LOG_FILE), exist_ok=True)
            existing = _load_json_file(FALLBACK_LOG_FILE, [])
            existing.append(record)
            with open(FALLBACK_LOG_FILE, "w", encoding="utf-8") as f:
                json.dump(existing[-100:], f, indent=2)
        except Exception as e:
            logger.error(f"Could not persist fallback log: {e}")

    def get_fallbacks(self) -> List[Dict[str, Any]]:
        return _load_json_file(FALLBACK_LOG_FILE, [])

    # --------------------------------------------------------------- budget

    def _check_budget(self, session_id: Optional[str]) -> None:
        if not self.budget_guard_enabled or not session_id or session_id == "global":
            return
        if not os.path.isdir(os.path.join(DATA_PROJECTS_DIR, session_id)):
            return
        try:
            try:
                from budget import check_budget_guard
            except ImportError:
                from engine.budget import check_budget_guard
            guard = check_budget_guard(session_id)
        except Exception as e:
            logger.warning(f"Budget guard unavailable for {session_id}: {e}")
            return
        if guard.get("pause_100"):
            raise BudgetExhaustedError(guard.get("message", "Budget exhausted (Handbook 26.4)."))

    # ------------------------------------------------------------ execution

    def query(
        self,
        prompt: str,
        system: Optional[str] = None,
        role: str = "general",
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        target_role: Optional[str] = None,
        force_provider: Optional[str] = None,
        force_model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        One model call (Handbook 22, 23.3):
        budget guard -> route (tier, local-first) -> call -> ledger row -> listeners.
        A cloud failure falls back to the local route and marks the result degraded.
        """
        role_key = role.lower()
        self._check_budget(session_id)

        defaults = dict(ROLE_DEFAULTS.get(role_key, ROLE_DEFAULTS["general"]))
        defaults.update({k: v for k, v in self._overrides.get(role_key, {}).items() if k in ("temperature", "max_tokens")})
        temp = temperature if temperature is not None else defaults["temperature"]
        max_tok = max_tokens if max_tokens is not None else defaults["max_tokens"]

        judge_info: Dict[str, Any] = {}
        if (force_provider or force_model) and self._fake_responder is not None:
            route = {"provider": "fake", "model": "fake-model", "downgraded": False, "downgrade_note": ""}
        elif force_provider or force_model:
            provider = force_provider or ("groq" if self.cloud_allowed(session_id) else "ollama")
            if provider == "groq" and not self.cloud_allowed(session_id):
                provider = "ollama"  # a forced cloud call never overrides local-only
            if provider == "ollama":
                model = (self._ollama_installed(force_model) if force_model else None) or \
                    self.resolve_route(role_key, session_id)["model"]
            else:
                model = force_model or self.resolve_route(role_key, session_id)["model"]
            route = {"provider": provider, "model": model, "downgraded": False, "downgrade_note": ""}
        elif role_key == "judge":
            tgt = (target_role or ("pm" if "prd" in (task_id or "") else "architect" if "arch" in (task_id or "")
                                   else "designer" if "design" in (task_id or "") else "ba")).lower()
            route = self.resolve_judge_route(tgt, session_id)
            judge_info = {"judge_generator_model": route.get("generator_model"),
                          "judge_same_model_as_author": route.get("same_model_as_author", False),
                          "judge_weaker_than_author": route.get("weaker_than_author", False)}
        else:
            route = self.resolve_route(role_key, session_id)

        provider, model = route["provider"], route["model"]
        if provider == "none" or not model:
            raise NoLocalModelError(route.get("downgrade_note") or "No local model installed.")

        self._notify("start", session_id=session_id, role=role_key, task_id=task_id, provider=provider, model=model)
        fallback_triggered = False
        result: Dict[str, Any]
        if provider == "fake":
            result = self._execute_fake_call(prompt, system, role_key, task_id)
        elif provider == "groq":
            failed: List[str] = []
            result = None
            est_in = (len(system or "") + len(prompt)) // 3
            tier = route.get("actual_tier")
            quota_hits = 0
            while provider == "groq":
                model, planned_wait = self._plan_cloud_model(role_key, session_id, model, tier, est_in, max_tok, failed)
                if planned_wait > 0:
                    self._notify("waiting", session_id=session_id, role=role_key, task_id=task_id, provider=provider,
                                 model=model, wait_s=round(planned_wait), reason="Groq rate limit")
                    time.sleep(planned_wait)
                try:
                    result = self._execute_groq_call(prompt, system, model, temp, self.rates.max_output(model, max_tok),
                                                     role=role_key, effort=reasoning_effort)
                    result["wait_ms"] = result.get("wait_ms", 0) + int(planned_wait * 1000)
                    break
                except GroqKeyMissingError:
                    raise
                except DailyQuotaError as e:
                    quota_hits += 1
                    max_wait = float(self.router.get("max_quota_wait_s", 600))
                    nxt, wait = self._plan_cloud_model(role_key, session_id, model, tier, est_in, max_tok, failed)
                    if nxt != model and quota_hits <= 6:
                        logger.warning(f"{e}; moving {role_key} to {nxt}")
                        model = nxt
                        continue
                    allow_down = bool(self.router.get("allow_tier_downgrade", False))
                    if (e.retry_s is not None and e.retry_s <= max_wait and quota_hits <= 6) or not allow_down:
                        logger.warning(f"{e}; no other model of the tier has quota, waiting "
                                       f"{(e.retry_s or max_wait):.0f}s (tier downgrade {'allowed' if allow_down else 'not allowed'})")
                        if not allow_down and quota_hits > 6:
                            self._notify("waiting", reason="Groq daily quota used up",
                                         wait_s=round(min(e.retry_s or max_wait, max_wait)))
                            time.sleep(min(e.retry_s or max_wait, max_wait))
                        continue  # the planner sleeps until the block expires
                    failed.append(model)
                    nxt = self.resolve_route(role_key, session_id, exclude_models=failed)
                    if nxt["provider"] == "groq" and len(failed) < 3:
                        model = nxt["model"]
                        continue
                    local = self.resolve_route(role_key, session_id, local_only=True)
                    if local["provider"] != "ollama" or not local.get("model"):
                        raise NoLocalModelError(f"Cloud quota used up ({e}) and no local model is installed.")
                    self.log_fallback(session_id, role_key, failed[0], str(e), 0, fallback_model=local["model"])
                    fallback_triggered = True
                    provider, model = "ollama", local["model"]
                    result = self._execute_ollama_call(prompt, system, model, temp, max_tok)
                except Exception as e:
                    failed.append(model)
                    nxt = self.resolve_route(role_key, session_id, exclude_models=failed)
                    if nxt["provider"] == "groq" and len(failed) < 3:
                        logger.warning(f"Groq {model} failed for {role_key} ({e}); trying {nxt['model']}")
                        model = nxt["model"]
                        continue
                    local = self.resolve_route(role_key, session_id, local_only=True)  # best installed local model
                    if local["provider"] != "ollama" or not local.get("model"):
                        raise NoLocalModelError(f"Cloud calls failed ({e}) and no local model is installed.")
                    self.log_fallback(session_id, role_key, failed[0], str(e), 0, fallback_model=local["model"])
                    fallback_triggered = True
                    provider, model = "ollama", local["model"]
                    result = self._execute_ollama_call(prompt, system, model, temp, max_tok)
            if failed and not fallback_triggered:
                result["cloud_models_skipped"] = failed  # another cloud model of the router answered
            if not fallback_triggered and model != route.get("model"):
                planned_cap = self._score_model_capability(route.get("model", ""))
                if self._score_model_capability(model) < planned_cap:
                    result["downgraded"] = True
                    result["downgrade_note"] = f"{role_key}: {route.get('model')} unavailable; answered by weaker {model}"
                    logger.warning(result["downgrade_note"])
        else:
            result = self._execute_ollama_call(prompt, system, model, temp, max_tok)

        result["is_fallback"] = fallback_triggered
        if role_key == "judge" and judge_info.get("judge_generator_model"):
            if self._score_model_capability(model) < self._score_model_capability(judge_info["judge_generator_model"]):
                judge_info["judge_weaker_than_author"] = True  # the model that actually answered, not the plan
        # Degraded = cannot be trusted for a PASS: a cloud fallback, or a judge weaker than its author.
        result["is_degraded"] = fallback_triggered or bool(judge_info.get("judge_weaker_than_author"))
        result["route"] = {k: route.get(k) for k in ("target_tier", "actual_tier", "downgraded", "downgrade_note")}
        result.update(judge_info)
        result["latency_ms"] = result.get("request_ms", 0)

        self._record_to_ledger(
            session_id=session_id, role=role_key, task_id=task_id, provider=provider, model=model,
            input_tokens=result["usage"]["prompt_tokens"], output_tokens=result["usage"]["completion_tokens"],
            cost_usd=result.get("cost_usd", 0.0), latency_ms=result.get("request_ms", 0),
            wait_ms=result.get("wait_ms", 0), stop=result.get("stop"),
        )
        self._notify("done", session_id=session_id, role=role_key, task_id=task_id, provider=provider, model=model,
                     usage=result["usage"], latency_ms=result.get("request_ms", 0), is_degraded=result["is_degraded"])
        return result

    def _plan_cloud_model(self, role: str, session_id: Optional[str], model: str, tier: Optional[str],
                          est_in: int, max_tok: int, failed: List[str]) -> Tuple[str, float]:
        """
        Picks the cloud model of this role's tier that can take the call soonest. Different models have
        separate quotas, so a busy model's work moves to an idle sibling instead of waiting or failing.
        """
        best_model = model
        best_wait = self.rates.wait_needed(model, est_in, self.rates.max_output(model, max_tok))
        if best_wait <= 1.0:
            return model, best_wait
        tried = list(failed) + [model]
        for _ in range(3):
            alt = self.resolve_route(role, session_id, exclude_models=tried)
            if alt["provider"] != "groq" or alt.get("actual_tier") != tier:
                break
            tried.append(alt["model"])
            w = self.rates.wait_needed(alt["model"], est_in, self.rates.max_output(alt["model"], max_tok))
            if w < best_wait:
                best_model, best_wait = alt["model"], w
            if w <= 1.0:
                break
        if best_model != model:
            logger.info(f"{model} is busy for ~{self.rates.wait_needed(model, est_in, max_tok):.0f}s; "
                        f"sending {role} to {best_model}")
        # Waiting for a short per-minute window is capped low; a daily-limit block may be waited out
        # up to max_quota_wait_s when no other model of the tier can take the call.
        cap = float(self.router.get("max_quota_wait_s", 600))
        return best_model, min(best_wait, cap)

    def _execute_fake_call(self, prompt: str, system: Optional[str], role: str, task_id: Optional[str]) -> Dict[str, Any]:
        t0 = time.time()
        text = self._fake_responder(prompt=prompt, system=system, role=role, task_id=task_id) or ""
        p_tok, c_tok = max(1, len(prompt) // 4), max(1, len(text) // 4)
        return {"text": text, "provider": "fake", "model": "fake-model", "stop": "end",
                "usage": {"prompt_tokens": p_tok, "completion_tokens": c_tok, "total_tokens": p_tok + c_tok},
                "cost_usd": 0.0, "request_ms": int((time.time() - t0) * 1000), "wait_ms": 0}

    def reasoning_effort_for(self, model: str, role: str) -> Optional[str]:
        """
        Handbook 22.3.2: low effort for relay and summary roles, more for Architect, devs and Judge.
        Reasoning models spend output tokens on hidden reasoning, so effort also protects output caps.
        """
        cfg = self.router.get("reasoning_effort", {})
        if model not in cfg.get("models", []):
            return None
        tier = self.router.get("roles", {}).get(role, "medium")
        return cfg.get("by_tier", {}).get(tier)

    def _execute_groq_call(self, prompt: str, system: Optional[str], model: str, temperature: float,
                           max_tokens: int, role: str = "general", effort: Optional[str] = None) -> Dict[str, Any]:
        """Groq chat completion with pacing and backoff. Only reachable while cloud is enabled."""
        if not self.cloud_enabled():
            raise RuntimeError("Cloud is disabled; refusing to contact Groq.")
        api_key = self.get_api_key()
        if not api_key:
            raise GroqKeyMissingError("GROQ_API_KEY is missing. Set it in .env or keep cloud disabled.")
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        # A caller may lower effort for mechanical output (YAML/SQL fragments); otherwise the role's tier decides.
        tier_effort = self.reasoning_effort_for(model, role)
        if tier_effort:
            payload["reasoning_effort"] = effort or tier_effort

        wait_s = 0.0  # per-model limits are planned by RateTracker; no global gap between different models

        backoffs = [5.0, 15.0, 30.0, 45.0]
        max_retries = 4
        for attempt in range(max_retries + 1):
            try:
                t0 = time.time()
                res = requests.post(f"{GROQ_BASE_URL}/chat/completions", headers=headers,
                                    json={k: v for k, v in payload.items() if not k.startswith("_")}, timeout=90)
                request_ms = int((time.time() - t0) * 1000)
                self.rates.update_from_headers(model, res.headers)

                if res.status_code == 429:
                    self.rates.learn_from_429(model, res.text)
                    payload["max_tokens"] = self.rates.max_output(model, payload["max_tokens"])
                    if "tokens per day" in res.text or "TPD" in res.text or "requests per day" in res.text:
                        retry_s = parse_retry_seconds(res.text, res.headers.get("retry-after"))
                        self.rates.block(model, (retry_s or 600) + 2)
                        # The caller moves the work to another model of the tier, or waits if none has quota.
                        raise DailyQuotaError(f"Groq daily quota for {model} used up: {res.text[:300]}", retry_s)
                    wait = backoffs[min(attempt, len(backoffs) - 1)]
                    m_msg = re.search(r"try again in ([0-9.]+)s", res.text)
                    if m_msg:
                        wait = max(float(m_msg.group(1)) + 0.5, wait)
                    if wait > 45.0 or attempt >= max_retries:
                        raise LLMRateLimitExhaustedError(f"Groq HTTP 429: {res.text}")
                    self._notify("waiting", reason="Groq rate limit (429)", wait_s=round(wait))
                    time.sleep(wait)
                    wait_s += wait
                    continue

                if res.status_code in (400, 413) and ("tokens per minute" in res.text or "reduce" in res.text):
                    payload["max_tokens"] = max(500, int(payload["max_tokens"] / 2))
                    time.sleep(3.0)
                    wait_s += 3.0
                    continue
                if res.status_code == 401:
                    raise GroqKeyMissingError("Groq API key is invalid or unauthorized (HTTP 401).")
                if res.status_code != 200:
                    if attempt < max_retries and res.status_code in (500, 502, 503, 504):
                        time.sleep(backoffs[attempt])
                        wait_s += backoffs[attempt]
                        continue
                    raise RuntimeError(f"Groq returned HTTP {res.status_code}: {res.text}")

                data = res.json()
                choice = data.get("choices", [{}])[0]
                content = choice.get("message", {}).get("content", "") or ""
                usage = data.get("usage", {})
                if not content.strip() and choice.get("finish_reason") == "length":
                    reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
                    bigger = self.rates.max_output(model, int(payload["max_tokens"] * 2.5))
                    if reasoning and bigger > payload["max_tokens"] and not payload.get("_grown"):
                        # Hidden reasoning used the whole budget: give the same model room once.
                        logger.warning(f"{model} used {reasoning} reasoning tokens of {payload['max_tokens']}; retrying with {bigger}")
                        payload["max_tokens"], payload["_grown"] = bigger, True
                        continue
                    raise RuntimeError(f"{model} returned no answer: the output limit ({payload['max_tokens']} tokens) "
                                       f"was used up{' by ' + str(reasoning) + ' reasoning tokens' if reasoning else ''}")
                p_tok = usage.get("prompt_tokens", len(prompt) // 4)
                c_tok = usage.get("completion_tokens", len(content) // 4)
                self.rates.record_call(model, c_tok)
                return {"text": content, "provider": "groq", "model": model,
                        "stop": "max_tokens" if choice.get("finish_reason") == "length" else "end",
                        "usage": {"prompt_tokens": p_tok, "completion_tokens": c_tok, "total_tokens": p_tok + c_tok},
                        "cost_usd": calculate_cost_usd(model, p_tok, c_tok, provider="groq"),
                        "request_ms": request_ms, "wait_ms": int(wait_s * 1000), "raw_response": data}
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if isinstance(e, requests.exceptions.ConnectionError) and not network_available("api.groq.com"):
                    # The machine is offline (asleep, Wi-Fi dropped): wait for the network instead of handing
                    # the work to a much weaker local model.
                    self._notify("waiting", reason="network is down; waiting for it to come back", wait_s=None)
                    waited = wait_for_network("api.groq.com", float(self.router.get("max_network_wait_s", 900)))
                    wait_s += waited
                    if network_available("api.groq.com"):
                        logger.warning(f"network back after {waited:.0f}s; retrying {model}")
                        continue
                if attempt < max_retries:
                    time.sleep(backoffs[attempt])
                    wait_s += backoffs[attempt]
                    continue
                raise TimeoutError(f"Groq request failed after retries: {e}")
        raise RuntimeError(f"Groq call to {model} gave up after {max_retries + 1} attempts "
                           f"(last HTTP status {getattr(locals().get('res'), 'status_code', 'none')})")

    def ollama_context_length(self, model: str) -> int:
        """The model's real context window from /api/show (cached)."""
        cache = getattr(self, "_ctx_cache", None)
        if cache is None:
            cache = self._ctx_cache = {}
        if model not in cache:
            length = 0
            try:
                res = requests.post(f"{OLLAMA_HOST}/api/show", json={"model": model}, timeout=5)
                if res.status_code == 200:
                    info = res.json().get("model_info", {}) or {}
                    length = max([int(v) for k, v in info.items() if k.endswith(".context_length")] or [0])
            except (requests.RequestException, ValueError):
                length = 0
            cache[model] = length or 8192
        return cache[model]

    def _num_ctx_for(self, model: str, system: Optional[str], prompt: str, max_tokens: Optional[int]) -> int:
        """
        Ollama defaults to a small context window and silently drops the START of longer prompts
        (role instructions and the task). Size the window to fit the prompt plus the reply, capped
        at the model's real limit; refuse loudly if it cannot fit.
        """
        est_prompt = (len(system or "") + len(prompt)) // 3 + 64  # conservative chars-per-token
        needed = est_prompt + int(max_tokens or 1024)
        limit = self.ollama_context_length(model)
        if est_prompt > limit:
            raise RuntimeError(f"prompt (~{est_prompt} tokens) does not fit {model}'s context window ({limit} tokens)")
        size = 4096
        while size < needed:
            size *= 2
        return min(size, limit)

    def _execute_ollama_call(self, prompt: str, system: Optional[str], model: str, temperature: float,
                             max_tokens: Optional[int] = None) -> Dict[str, Any]:
        """Local Ollama call via /api/generate."""
        payload: Dict[str, Any] = {"model": model, "prompt": prompt, "stream": False,
                                   "options": {"temperature": temperature,
                                               "num_ctx": self._num_ctx_for(model, system, prompt, max_tokens)}}
        if max_tokens:
            payload["options"]["num_predict"] = int(max_tokens)
        if system:
            payload["system"] = system
        t0 = time.time()
        res = requests.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=600)
        request_ms = int((time.time() - t0) * 1000)
        if res.status_code != 200:
            raise RuntimeError(f"Ollama returned HTTP {res.status_code}: {res.text}")
        data = res.json()
        content = data.get("response", "")
        p_tok = data.get("prompt_eval_count", len(prompt) // 4)
        if p_tok >= payload["options"]["num_ctx"] - 8:
            logger.warning(f"Ollama prompt filled the whole context window ({p_tok} tokens); input was likely truncated")
        c_tok = data.get("eval_count", len(content) // 4)
        return {"text": content, "provider": "ollama", "model": model,
                "stop": "max_tokens" if data.get("done_reason") == "length" else "end",
                "usage": {"prompt_tokens": p_tok, "completion_tokens": c_tok, "total_tokens": p_tok + c_tok},
                "cost_usd": 0.0, "request_ms": request_ms, "wait_ms": 0, "raw_response": data}

    def _record_to_ledger(self, session_id: Optional[str], role: str, task_id: Optional[str], provider: str,
                          model: str, input_tokens: int, output_tokens: int, cost_usd: float, latency_ms: int,
                          wait_ms: int = 0, stop: Optional[str] = None) -> None:
        try:
            try:
                from token_ledger import record_llm_call
            except ImportError:
                from engine.token_ledger import record_llm_call
            kwargs = {"db_path": self.ledger_db_path} if self.ledger_db_path else {}
            record_llm_call(project_id=session_id or "global", agent_id=role, task_id=task_id or f"{role}_generation",
                            provider=provider, model=model, input_tokens=input_tokens, cached_tokens=0,
                            output_tokens=output_tokens, cost_usd=cost_usd, latency_ms=latency_ms,
                            wait_ms=wait_ms, stop=stop, **kwargs)
        except Exception as e:
            logger.debug(f"Could not record LLM call to token ledger: {e}")


# Singleton client instance
default_llm_client = LLMClient()


def query_llm(prompt: str, system: Optional[str] = None, role: str = "general", session_id: Optional[str] = None,
              task_id: Optional[str] = None, temperature: Optional[float] = None, max_tokens: Optional[int] = None,
              target_role: Optional[str] = None, force_provider: Optional[str] = None,
              force_model: Optional[str] = None, reasoning_effort: Optional[str] = None) -> str:
    """Convenience string-returning query function compatible with existing agent callers."""
    res = default_llm_client.query(prompt=prompt, system=system, role=role, session_id=session_id, task_id=task_id,
                                   temperature=temperature, max_tokens=max_tokens, target_role=target_role,
                                   force_provider=force_provider, force_model=force_model,
                                   reasoning_effort=reasoning_effort)
    return res.get("text", "")


def query_llm_with_meta(prompt: str, system: Optional[str] = None, role: str = "general",
                        session_id: Optional[str] = None, task_id: Optional[str] = None,
                        temperature: Optional[float] = None, max_tokens: Optional[int] = None,
                        target_role: Optional[str] = None, force_provider: Optional[str] = None,
                        force_model: Optional[str] = None, reasoning_effort: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
    """Returns (text, metadata) where metadata contains is_fallback, is_degraded, model, provider, route."""
    res = default_llm_client.query(prompt=prompt, system=system, role=role, session_id=session_id, task_id=task_id,
                                   temperature=temperature, max_tokens=max_tokens, target_role=target_role,
                                   force_provider=force_provider, force_model=force_model,
                                   reasoning_effort=reasoning_effort)
    return res.get("text", ""), res
