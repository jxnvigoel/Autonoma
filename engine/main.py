import os
import sys
import logging
from typing import Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("autonoma-engine")

app = FastAPI(title="Autonoma Engine", version="1.0.0")

# Enable CORS for Electron renderer
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")


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


@app.get("/status", response_model=StatusResponse)
def get_status():
    """
    Pings Ollama and checks if the service is reachable and whether llama3.2:3b is pulled.
    """
    model_name = DEFAULT_MODEL
    try:
        # Check if Ollama daemon is reachable
        version_res = requests.get(f"{OLLAMA_HOST}/api/version", timeout=3)
        if version_res.status_code != 200:
            return StatusResponse(
                status="error",
                ollama_online=False,
                model_ready=False,
                message=f"Cannot connect to Ollama at {OLLAMA_HOST} (HTTP {version_res.status_code}). Make sure the Ollama daemon is running ('ollama run {model_name}').",
            )
        version_data = version_res.json()
        version = version_data.get("version", "unknown")

        # Check if the target model is installed
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
                message=f"Model '{model_name}' not found in Ollama. Make sure you have downloaded it by running: ollama pull {model_name}",
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
            message=f"Unable to reach Ollama at {OLLAMA_HOST}. Please ensure the Ollama service is running ('ollama run {model_name}').",
        )
    except Exception as e:
        return StatusResponse(
            status="error",
            ollama_online=False,
            model_ready=False,
            message=f"Error checking Ollama status: {str(e)}",
        )


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """
    Sends a prompt to Ollama's REST API at http://localhost:11434/api/generate
    with model llama3.2:3b and stream: false.
    """
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prompt cannot be empty",
        )

    model = req.model or DEFAULT_MODEL

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
        return ChatResponse(
            response=data.get("response", ""),
            duration=data.get("total_duration", 0),
            token_count=data.get("eval_count", 0),
        )

    except requests.exceptions.ConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to Ollama at {OLLAMA_HOST}. Make sure Ollama is running ('ollama run {model}').",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error communicating with Ollama: {str(e)}",
        )


if __name__ == "__main__":
    port = int(os.environ.get("ENGINE_PORT", 8765))
    logger.info(f"Starting Autonoma Python Engine on http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
