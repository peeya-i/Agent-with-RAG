"""Ollama embedding and process lifecycle service."""
import os
import signal
import subprocess
import time
import requests
from typing import Dict, Any, List, Optional
import config
from services.log_service import get_log_service

# Catalogue of well-known Ollama embedding models with specifications
KNOWN_EMBEDDING_MODELS = [
    {
        "name": "bge-m3",
        "tag": "bge-m3:latest",
        "dimensions": 1024,
        "context_window": 8192,
        "size": "1.2 GB",
        "description": "Multi-lingual, dense & multi-functional state-of-the-art embedding model.",
    },
    {
        "name": "bge-large",
        "tag": "bge-large:latest",
        "dimensions": 1024,
        "context_window": 512,
        "size": "670 MB",
        "description": "High performance dense English sentence and document embedding model.",
    },
    {
        "name": "nomic-embed-text",
        "tag": "nomic-embed-text:latest",
        "dimensions": 768,
        "context_window": 8192,
        "size": "274 MB",
        "description": "High-performance embedding model with large 8k context window support.",
    },
    {
        "name": "all-minilm",
        "tag": "all-minilm:latest",
        "dimensions": 384,
        "context_window": 512,
        "size": "45 MB",
        "description": "Ultra-compact, ultra-fast embedding model ideal for rapid local processing.",
    },
    {
        "name": "mxbai-embed-large",
        "tag": "mxbai-embed-large:latest",
        "dimensions": 1024,
        "context_window": 512,
        "size": "670 MB",
        "description": "Mixedbread AI state-of-the-art text representation model.",
    },
    {
        "name": "snowflake-arctic-embed",
        "tag": "snowflake-arctic-embed:latest",
        "dimensions": 1024,
        "context_window": 512,
        "size": "669 MB",
        "description": "Optimized enterprise retrieval model developed by Snowflake.",
    },
]

class OllamaService:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or config.OLLAMA_BASE_URL
        self.active_model = config.DEFAULT_EMBEDDER_MODEL
        self.started_by_app = False
        self._process: Optional[subprocess.Popen] = None
        self.logger = get_log_service()

    def is_running(self) -> bool:
        """Check if Ollama server is responding."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return resp.status_code == 200
        except Exception:
            return False

    def ensure_running(self) -> bool:
        """Verify Ollama is running; launch it if not already active."""
        if self.is_running():
            self.started_by_app = False
            # Select best installed model as active
            installed = self.get_installed_model_names()
            if self.active_model not in installed and installed:
                for cand in ["bge-m3", "nomic-embed-text", "all-minilm", "bge-large"]:
                    if any(cand in name for name in installed):
                        self.active_model = cand
                        break
                else:
                    self.active_model = installed[0].split(":")[0]
            return True

        # Launch ollama serve in background
        try:
            self._process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            # Wait up to 10 seconds for it to bind
            for _ in range(20):
                time.sleep(0.5)
                if self.is_running():
                    self.started_by_app = True
                    return True
            return False
        except Exception:
            return False

    def shutdown(self):
        """Shutdown Ollama ONLY if this app instance started it."""
        if self.started_by_app and self._process:
            try:
                os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
                self._process.wait(timeout=5)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            finally:
                self._process = None
                self.started_by_app = False

    def get_installed_model_names(self) -> List[str]:
        """Fetch list of models locally available in Ollama."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                return [m.get("name", "") for m in models if m.get("name")]
        except Exception:
            pass
        return []

    def list_available_models(self) -> List[Dict[str, Any]]:
        """Return catalogue of embedding models with dimension, context, size, and status."""
        installed = self.get_installed_model_names()
        models = []
        for item in KNOWN_EMBEDDING_MODELS:
            is_installed = any(
                item["name"] in inst or item["tag"] in inst for inst in installed
            )
            is_active = (self.active_model == item["name"] or self.active_model in item["name"])
            
            if is_active:
                status = "Active"
            elif is_installed:
                status = "Installed"
            else:
                status = "Available to Pull"

            models.append({
                "name": item["name"],
                "tag": item["tag"],
                "dimensions": item["dimensions"],
                "context_window": item["context_window"],
                "size": item["size"],
                "description": item["description"],
                "status": status,
                "is_active": is_active,
                "is_installed": is_installed,
            })
        return models

    def pull_model(self, model_name: str) -> bool:
        """Instruct Ollama to download/pull an embedding model."""
        try:
            resp = requests.post(
                f"{self.base_url}/api/pull",
                json={"name": model_name, "stream": False},
                timeout=180,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def get_embedding(self, text: str, conversation_id: str = "system") -> List[float]:
        """Generate vector embedding for text and log per specification:
        Log first 50 chars of chunk, vectorizer name, and response excluding vector array.
        """
        start_time = time.time()
        snippet = text[:50]
        
        try:
            resp = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.active_model, "prompt": text},
                timeout=30,
            )
            elapsed_ms = (time.time() - start_time) * 1000
            
            if resp.status_code == 200:
                data = resp.json()
                vector = data.get("embedding", [])
                
                # Log per specification: log first 50 chars, vectorizer name, exclude raw vector float array
                self.logger.log_event(
                    conversation_id=conversation_id,
                    event_type="ollama vector",
                    invoker="OllamaService",
                    target=f"Ollama ({self.active_model})",
                    short_description=f"Generated embedding for: '{snippet}'...",
                    payload={
                        "text_snippet_50chars": snippet,
                        "vectorizer": self.active_model,
                        "vector_dimensions": len(vector),
                        "status": "success",
                    },
                    elapsed_ms=elapsed_ms,
                )
                return vector
            else:
                self.logger.log_event(
                    conversation_id=conversation_id,
                    event_type="ollama vector",
                    invoker="OllamaService",
                    target=f"Ollama ({self.active_model})",
                    short_description=f"Embedding failed: HTTP {resp.status_code}",
                    payload={
                        "text_snippet_50chars": snippet,
                        "vectorizer": self.active_model,
                        "error": resp.text,
                        "status_code": resp.status_code,
                    },
                    elapsed_ms=elapsed_ms,
                    is_error=True,
                )
                raise RuntimeError(f"Ollama embedding failed with HTTP {resp.status_code}")
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            self.logger.log_event(
                conversation_id=conversation_id,
                event_type="ollama vector",
                invoker="OllamaService",
                target=f"Ollama ({self.active_model})",
                short_description=f"Ollama connection error: {str(e)}",
                payload={"text_snippet_50chars": snippet, "error": str(e)},
                elapsed_ms=elapsed_ms,
                is_error=True,
            )
            raise

    def set_active_model(self, model_name: str) -> bool:
        """Switch active embedding model, pulling if not installed."""
        installed = self.get_installed_model_names()
        if not any(model_name in inst for inst in installed):
            success = self.pull_model(model_name)
            if not success:
                return False
        self.active_model = model_name
        return True

# Singleton instance
_OLLAMA_SERVICE: Optional[OllamaService] = None

def get_ollama_service() -> OllamaService:
    global _OLLAMA_SERVICE
    if _OLLAMA_SERVICE is None:
        _OLLAMA_SERVICE = OllamaService()
    return _OLLAMA_SERVICE
