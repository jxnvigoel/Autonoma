import os
import time
import json
import logging
import threading
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
import requests
from dotenv import load_dotenv

# Ensure .env is loaded
load_dotenv()

logger = logging.getLogger("autonoma-engine.llm_client")

# Paths
ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(ENGINE_DIR)
PRICING_FILE = os.path.join(PROJECT_ROOT, "config", "model_pricing.json")
FALLBACK_LOG_FILE = os.path.join(PROJECT_ROOT, "data", "llm_fallbacks.json")

# Fallback Ollama configuration
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqKeyMissingError(Exception):
    """Raised when GROQ_API_KEY is required but missing from .env."""
    pass


class LLMRateLimitExhaustedError(Exception):
    """Raised when all rate limit retries are exhausted on Groq."""
    pass


# ==============================================================================
# PRICING AND LEDGER HELPERS
# ==============================================================================

def load_pricing_config() -> Dict[str, Any]:
    if os.path.exists(PRICING_FILE):
        try:
            with open(PRICING_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not read pricing config at {PRICING_FILE}: {e}")
    return {"rates": {}}


def calculate_cost_usd(model: str, input_tokens: int, output_tokens: int, provider: str = "groq") -> float:
    if provider == "ollama" or model.startswith("ollama") or model == OLLAMA_DEFAULT_MODEL:
        return 0.0

    pricing = load_pricing_config().get("rates", {})
    rate = pricing.get(model, pricing.get("default_cloud", {"input_per_million": 0.20, "output_per_million": 0.50}))

    in_price = rate.get("input_per_million", 0.20) / 1_000_000.0
    out_price = rate.get("output_per_million", 0.50) / 1_000_000.0
    cost = (input_tokens * in_price) + (output_tokens * out_price)
    return round(cost, 6)


# ==============================================================================
# MODEL ROUTER & STATE MANAGEMENT
# ==============================================================================

class LLMClient:
    def __init__(self):
        self._lock = threading.Lock()
        self._last_request_time: float = 0.0
        self._min_request_interval_s: float = 1.0  # Pace burst requests
        self._cached_groq_models: Optional[List[Dict[str, Any]]] = None
        self._cached_groq_models_time: float = 0.0
        self._project_local_only: Dict[str, bool] = {}  # session_id -> bool

        # Role configurations (provider, model, temperature, max_tokens)
        self.role_configs: Dict[str, Dict[str, Any]] = {
            "ba": {
                "provider": "groq",
                "model": "openai/gpt-oss-120b",
                "temperature": 0.6,
                "max_tokens": 4096
            },
            "pm": {
                "provider": "groq",
                "model": "openai/gpt-oss-120b",
                "temperature": 0.3,
                "max_tokens": 8192
            },
            "architect": {
                "provider": "groq",
                "model": "openai/gpt-oss-120b",
                "temperature": 0.2,
                "max_tokens": 8192
            },
            "designer": {
                "provider": "groq",
                "model": "qwen/qwen3.8-27b",  # Distinct generator family (Alibaba Cloud 27B)
                "temperature": 0.2,
                "max_tokens": 800
            },
            "judge": {
                "provider": "groq",
                "model": "openai/gpt-oss-120b",  # Judge is larger (120B) & from OpenAI per Handbook 14.1
                "temperature": 0.1,
                "max_tokens": 4096
            },
            "engineer": {
                "provider": "groq",
                "model": "openai/gpt-oss-120b",
                "temperature": 0.2,
                "max_tokens": 8192
            },
            "qa": {
                "provider": "groq",
                "model": "openai/gpt-oss-120b",
                "temperature": 0.2,
                "max_tokens": 4096
            },
            "general": {
                "provider": "groq",
                "model": "openai/gpt-oss-120b",
                "temperature": 0.4,
                "max_tokens": 4096
            }
        }

        # Initialize available models from Groq at startup
        self.refresh_models()

    def get_api_key(self) -> str:
        load_dotenv(override=True)
        key = os.environ.get("GROQ_API_KEY", "").strip()
        # Clean any accidental wrapping quotes
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
        logger.info(f"Project '{session_id}' local-only override set to: {local_only}")

    def is_project_local_only(self, session_id: Optional[str]) -> bool:
        if not session_id:
            return False
        return self._project_local_only.get(session_id, False)

    def fetch_groq_models(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Fetches the live list of models from Groq's GET /models endpoint.
        Filters out non-chat models (audio, prompt guard).
        """
        now = time.time()
        if not force_refresh and self._cached_groq_models is not None and (now - self._cached_groq_models_time < 300):
            return self._cached_groq_models

        key = self.get_api_key()
        if not key:
            return []

        try:
            headers = {"Authorization": f"Bearer {key}"}
            res = requests.get(f"{GROQ_BASE_URL}/models", headers=headers, timeout=10)
            if res.status_code == 200:
                raw_models = res.json().get("data", [])
                valid_models = []
                for m in raw_models:
                    mid = m.get("id", "")
                    mid_lower = mid.lower()
                    # Filter out non-chat / guard models
                    if any(x in mid_lower for x in ["whisper", "guard", "embedding", "orpheus"]):
                        continue
                    valid_models.append({
                        "id": mid,
                        "owned_by": m.get("owned_by", "Groq"),
                        "context_window": m.get("context_window", 8192),
                        "capability_score": self._score_model_capability(mid)
                    })

                # Sort by capability score descending
                valid_models.sort(key=lambda x: x["capability_score"], reverse=True)
                self._cached_groq_models = valid_models
                self._cached_groq_models_time = now
                return valid_models
            else:
                logger.warning(f"Groq GET /models returned {res.status_code}: {res.text}")
                return []
        except Exception as e:
            logger.warning(f"Failed to fetch models from Groq: {e}")
            return []

    def _score_model_capability(self, model_id: str) -> int:
        m_lower = model_id.lower()
        if "120b" in m_lower:
            return 120
        if "70b" in m_lower:
            return 70
        if "32b" in m_lower:
            return 32
        if "27b" in m_lower:
            return 27
        if "20b" in m_lower:
            return 20
        if "8b" in m_lower:
            return 8
        if "7b" in m_lower:
            return 7
        return 10

    def refresh_models(self) -> None:
        """
        Fetches live models from Groq. Per Handbook Chapter 14 & 22:
        - Judge model must be at least as capable as generator, larger size or distinct family.
        - Defaults Judge to the most capable model (e.g. openai/gpt-oss-120b, 120B).
        - Defaults Designer generator to a distinct family model (e.g. qwen/qwen3.8-27b, 27B).
        """
        groq_models = self.fetch_groq_models(force_refresh=True)
        if not groq_models:
            return

        largest_model = groq_models[0]["id"]
        # Judge is assigned the most capable model
        judge_model = largest_model

        # Generator candidates from distinct family or smaller model
        gen_candidates = [
            m["id"] for m in groq_models
            if "qwen" in m["id"].lower()
        ]
        designer_model = gen_candidates[0] if gen_candidates else (groq_models[1]["id"] if len(groq_models) > 1 else largest_model)

        for role in ["ba", "pm", "architect", "engineer", "qa", "general"]:
            if self.role_configs.get(role, {}).get("provider") == "groq":
                self.role_configs[role]["model"] = largest_model

        if self.role_configs.get("designer", {}).get("provider") == "groq":
            self.role_configs["designer"]["model"] = designer_model

        if self.role_configs.get("judge", {}).get("provider") == "groq":
            self.role_configs["judge"]["model"] = judge_model

        logger.info(f"LLM Client refreshed models -> Generator (Designer): '{designer_model}', Judge: '{judge_model}'")

    def log_fallback(self, session_id: Optional[str], role: str, original_model: str, error: str, duration_ms: int) -> None:
        fallback_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id or "global",
            "role": role,
            "original_provider": "groq",
            "original_model": original_model,
            "fallback_provider": "ollama",
            "fallback_model": OLLAMA_DEFAULT_MODEL,
            "reason": error,
            "duration_ms": duration_ms
        }
        logger.warning(f"FALLBACK TO OLLAMA TRIGGERED: {json.dumps(fallback_record)}")
        try:
            os.makedirs(os.path.dirname(FALLBACK_LOG_FILE), exist_ok=True)
            existing = []
            if os.path.exists(FALLBACK_LOG_FILE):
                try:
                    with open(FALLBACK_LOG_FILE, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                except Exception:
                    existing = []
            existing.append(fallback_record)
            with open(FALLBACK_LOG_FILE, "w", encoding="utf-8") as f:
                json.dump(existing[-100:], f, indent=2)
        except Exception as e:
            logger.error(f"Could not persist fallback log: {e}")

    def get_fallbacks(self) -> List[Dict[str, Any]]:
        if os.path.exists(FALLBACK_LOG_FILE):
            try:
                with open(FALLBACK_LOG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def get_active_provider_and_model(self, role: str, session_id: Optional[str] = None) -> Tuple[str, str]:
        if self.is_project_local_only(session_id):
            return ("ollama", OLLAMA_DEFAULT_MODEL)
        cfg = self.role_configs.get(role.lower(), self.role_configs.get("general", {}))
        provider = cfg.get("provider", "groq")
        model = cfg.get("model", "openai/gpt-oss-120b")
        if provider == "ollama":
            model = OLLAMA_DEFAULT_MODEL
        return (provider, model)

    def update_role_config(
        self,
        role: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        role_key = role.lower()
        if role_key not in self.role_configs:
            self.role_configs[role_key] = {
                "provider": "groq",
                "model": "openai/gpt-oss-120b",
                "temperature": 0.3,
                "max_tokens": 4096
            }
        if provider:
            self.role_configs[role_key]["provider"] = provider
        if model:
            self.role_configs[role_key]["model"] = model
        if temperature is not None:
            self.role_configs[role_key]["temperature"] = temperature
        if max_tokens is not None:
            self.role_configs[role_key]["max_tokens"] = max_tokens
        return self.role_configs[role_key]

    def get_settings(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        groq_models = self.fetch_groq_models()
        fallbacks = self.get_fallbacks()
        return {
            "groq_configured": self.is_groq_configured(),
            "masked_api_key": self.get_masked_api_key(),
            "available_models": groq_models,
            "role_configs": self.role_configs,
            "local_only": self.is_project_local_only(session_id),
            "fallback_count": len(fallbacks),
            "recent_fallbacks": fallbacks[-10:]
        }

    # ==============================================================================
    # EXECUTION CORE
    # ==============================================================================

    def query(
        self,
        prompt: str,
        system: Optional[str] = None,
        role: str = "general",
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        force_provider: Optional[str] = None,
        force_model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes an LLM call per Handbook Chapter 22 & 23:
        1. Checks per-project local-only toggle (forces Ollama if enabled).
        2. Routes to Groq by default; enforces GROQ_API_KEY presence (clear error if missing).
        3. Paces calls to respect token/minute rate limits.
        4. Handles 429 and timeouts with exponential backoff and retry-after headers.
        5. Falls back to Ollama ONLY after retries are exhausted.
        6. Logs token usage and real cost to the Token Ledger.
        """
        start_time = time.time()
        role_key = role.lower()
        config = self.role_configs.get(role_key, self.role_configs["general"])

        # Determine provider and model
        is_local_only = self.is_project_local_only(session_id)
        provider = force_provider or ("ollama" if is_local_only else config.get("provider", "groq"))
        model = force_model or (OLLAMA_DEFAULT_MODEL if provider == "ollama" else config.get("model"))
        temp = temperature if temperature is not None else config.get("temperature", 0.3)
        max_tok = max_tokens if max_tokens is not None else config.get("max_tokens", 4096)

        # 1. Enforce GROQ_API_KEY if Groq is target provider
        if provider == "groq":
            api_key = self.get_api_key()
            if not api_key:
                err_msg = "GROQ_API_KEY is missing from environment. Set GROQ_API_KEY in .env to use cloud LLM provider or switch to local-only mode."
                logger.error(err_msg)
                raise GroqKeyMissingError(err_msg)

            # Attempt execution via Groq with rate-limiting and backoff retries
            try:
                result = self._execute_groq_call(
                    prompt=prompt,
                    system=system,
                    model=model,
                    temperature=temp,
                    max_tokens=max_tok,
                    session_id=session_id
                )
                latency_ms = int((time.time() - start_time) * 1000)
                result["latency_ms"] = latency_ms

                # Record to Token Ledger
                self._record_to_ledger(
                    session_id=session_id,
                    role=role_key,
                    task_id=task_id,
                    provider="groq",
                    model=model,
                    input_tokens=result["usage"]["prompt_tokens"],
                    output_tokens=result["usage"]["completion_tokens"],
                    cost_usd=result["cost_usd"],
                    latency_ms=latency_ms
                )
                return result
            except Exception as e:
                if isinstance(e, GroqKeyMissingError):
                    raise
                # If it's a rate limit or timeout exhausted on Groq, fall back to Ollama
                logger.warning(f"Groq call failed after retries for role '{role}': {e}. Falling back to Ollama.")
                latency_ms = int((time.time() - start_time) * 1000)
                self.log_fallback(session_id, role_key, model, str(e), latency_ms)

                # Fallback execution on Ollama
                provider = "ollama"
                model = OLLAMA_DEFAULT_MODEL

        # 2. Ollama Execution (Direct or Fallback)
        result = self._execute_ollama_call(
            prompt=prompt,
            system=system,
            model=model,
            temperature=temp
        )
        latency_ms = int((time.time() - start_time) * 1000)
        result["latency_ms"] = latency_ms

        self._record_to_ledger(
            session_id=session_id,
            role=role_key,
            task_id=task_id,
            provider="ollama",
            model=model,
            input_tokens=result["usage"]["prompt_tokens"],
            output_tokens=result["usage"]["completion_tokens"],
            cost_usd=0.0,
            latency_ms=latency_ms
        )
        return result

    def _execute_groq_call(
        self,
        prompt: str,
        system: Optional[str],
        model: str,
        temperature: float,
        max_tokens: int,
        session_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        Executes a single Groq chat completion call with rate limit pacing,
        exponential backoff, and retry-after inspection.
        """
        api_key = self.get_api_key()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        # Rate limiting burst control
        with self._lock:
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < self._min_request_interval_s:
                sleep_needed = self._min_request_interval_s - elapsed
                time.sleep(sleep_needed)
            self._last_request_time = time.time()

        max_retries = 4
        backoffs = [5.0, 15.0, 30.0, 45.0]

        for attempt in range(max_retries + 1):
            try:
                res = requests.post(
                    f"{GROQ_BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=90
                )

                # Check for Rate Limit (HTTP 429)
                if res.status_code == 429:
                    retry_after_hdr = res.headers.get("retry-after")
                    reset_tokens_hdr = res.headers.get("x-ratelimit-reset-tokens")

                    wait_seconds = backoffs[min(attempt, len(backoffs) - 1)]
                    if retry_after_hdr:
                        try:
                            wait_seconds = max(float(retry_after_hdr), wait_seconds)
                        except ValueError:
                            pass
                    elif reset_tokens_hdr:
                        match = re.search(r"([0-9.]+)(?:s|ms)?", reset_tokens_hdr)
                        if match:
                            try:
                                parsed = float(match.group(1))
                                if "ms" in reset_tokens_hdr:
                                    parsed /= 1000.0
                                wait_seconds = max(parsed + 0.5, wait_seconds)
                            except ValueError:
                                pass

                    if "reduce max_tokens" in res.text:
                        old_tok = payload.get("max_tokens", 800)
                        payload["max_tokens"] = max(400, int(old_tok * 0.7))
                        logger.info(f"Groq OTPM limit signaled. Dynamically reduced max_tokens from {old_tok} to {payload['max_tokens']}.")

                    logger.warning(
                        f"Groq HTTP 429 Rate Limit encountered on attempt {attempt+1}/{max_retries+1} for model '{model}'. "
                        f"Backing off for {wait_seconds:.2f}s..."
                    )
                    if attempt < max_retries:
                        time.sleep(wait_seconds)
                        continue
                    else:
                        raise LLMRateLimitExhaustedError(f"Groq HTTP 429: {res.text}")

                # Check for other errors
                if res.status_code == 401:
                    raise GroqKeyMissingError("Groq API key is invalid or unauthorized (HTTP 401).")

                if res.status_code != 200:
                    if attempt < max_retries and res.status_code in [500, 502, 503, 504]:
                        time.sleep(backoffs[attempt])
                        continue
                    raise RuntimeError(f"Groq returned HTTP {res.status_code}: {res.text}")

                data = res.json()
                choice = data.get("choices", [{}])[0]
                content = choice.get("message", {}).get("content", "")
                usage = data.get("usage", {})
                p_tokens = usage.get("prompt_tokens", len(prompt) // 4)
                c_tokens = usage.get("completion_tokens", len(content) // 4)
                tot_tokens = usage.get("total_tokens", p_tokens + c_tokens)

                cost_usd = calculate_cost_usd(model, p_tokens, c_tokens, provider="groq")

                return {
                    "text": content,
                    "provider": "groq",
                    "model": model,
                    "usage": {
                        "prompt_tokens": p_tokens,
                        "completion_tokens": c_tokens,
                        "total_tokens": tot_tokens
                    },
                    "cost_usd": cost_usd,
                    "raw_response": data
                }

            except requests.exceptions.Timeout:
                logger.warning(f"Groq request timeout on attempt {attempt+1}/{max_retries+1}")
                if attempt < max_retries:
                    time.sleep(backoffs[attempt])
                    continue
                raise TimeoutError("Groq request timed out after all retries.")
            except (requests.exceptions.ConnectionError) as e:
                logger.warning(f"Groq network connection error: {e}")
                if attempt < max_retries:
                    time.sleep(backoffs[attempt])
                    continue
                raise

        raise RuntimeError("Unexpected termination of Groq execution loop.")

    def _execute_ollama_call(
        self,
        prompt: str,
        system: Optional[str],
        model: str,
        temperature: float
    ) -> Dict[str, Any]:
        """
        Executes a local Ollama API call via /api/generate as fallback or local-only mode.
        """
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        if system:
            payload["system"] = system

        try:
            res = requests.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=180)
            if res.status_code != 200:
                raise RuntimeError(f"Ollama returned HTTP {res.status_code}: {res.text}")

            data = res.json()
            content = data.get("response", "")
            p_tokens = data.get("prompt_eval_count", len(prompt) // 4)
            c_tokens = data.get("eval_count", len(content) // 4)

            return {
                "text": content,
                "provider": "ollama",
                "model": model,
                "usage": {
                    "prompt_tokens": p_tokens,
                    "completion_tokens": c_tokens,
                    "total_tokens": p_tokens + c_tokens
                },
                "cost_usd": 0.0,
                "raw_response": data
            }
        except Exception as e:
            logger.error(f"Error querying Ollama at {OLLAMA_HOST}: {e}")
            raise

    def _record_to_ledger(
        self,
        session_id: Optional[str],
        role: str,
        task_id: Optional[str],
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        latency_ms: int
    ) -> None:
        try:
            from token_ledger import record_llm_call
            record_llm_call(
                project_id=session_id or "global",
                agent_id=role,
                task_id=task_id or f"{role}_generation",
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                cached_tokens=0,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                latency_ms=latency_ms
            )
        except Exception as e:
            # Fallback import path
            try:
                from engine.token_ledger import record_llm_call
                record_llm_call(
                    project_id=session_id or "global",
                    agent_id=role,
                    task_id=task_id or f"{role}_generation",
                    provider=provider,
                    model=model,
                    input_tokens=input_tokens,
                    cached_tokens=0,
                    output_tokens=output_tokens,
                    cost_usd=cost_usd,
                    latency_ms=latency_ms
                )
            except Exception as e2:
                logger.debug(f"Could not record LLM call to token ledger: {e2}")


# Singleton client instance
default_llm_client = LLMClient()


def query_llm(
    prompt: str,
    system: Optional[str] = None,
    role: str = "general",
    session_id: Optional[str] = None,
    task_id: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    force_provider: Optional[str] = None,
    force_model: Optional[str] = None
) -> str:
    """Convenience string-returning query function compatible with existing agent callers."""
    res = default_llm_client.query(
        prompt=prompt,
        system=system,
        role=role,
        session_id=session_id,
        task_id=task_id,
        temperature=temperature,
        max_tokens=max_tokens,
        force_provider=force_provider,
        force_model=force_model
    )
    return res.get("text", "")
