import os
import logging
import math
import re
from typing import List, Optional, Dict
import numpy as np
import requests

logger = logging.getLogger(__name__)

class EmbeddingEngine:
    """Vector embedding engine supporting Ollama models, Google GenAI, and local semantic fallback."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, ollama_url: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
        self.model = model or os.environ.get("DEFAULT_EMBEDDING_MODEL", "bge-large")
        self.ollama_url = ollama_url or os.environ.get("OLLAMA_URL", "http://ollama:11434")
        if not os.environ.get("RUNNING_IN_DOCKER") and "ollama:11434" in self.ollama_url:
            self.ollama_url = self.ollama_url.replace("ollama:11434", "127.0.0.1:11434")
        self._genai_client = None
        self._cache: Dict[str, np.ndarray] = {}
        self._init_client()

    def _init_client(self):
        if self.api_key:
            try:
                from google import genai
                self._genai_client = genai.Client(api_key=self.api_key)
                logger.info("Initialized Google GenAI embedding client")
            except Exception as e:
                logger.warning(f"Failed to initialize Google GenAI client: {e}.")
                self._genai_client = None
        else:
            logger.info("No Gemini API key provided. Using Ollama / deterministic local semantic embedding engine.")

    def _store_cache(self, key: str, val: np.ndarray, max_size: int = 2000):
        """Stores embedding in memory cache with FIFO bounded capacity."""
        if len(self._cache) >= max_size:
            # Evict oldest 20% of entries
            evict_count = max(1, max_size // 5)
            for k in list(self._cache.keys())[:evict_count]:
                self._cache.pop(k, None)
        self._cache[key] = val

    def embed_text(self, text: str, model: Optional[str] = None) -> np.ndarray:
        """Compute normalized embedding vector for a single text using specified or default model."""
        cleaned_text = (text or "").strip()
        if not cleaned_text:
            cleaned_text = "empty"

        target_model = (model or self.model or "bge-large").strip()
        cache_key = f"{target_model}@@{cleaned_text}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 1. Try Ollama embedding if target_model is not Google GenAI model
        is_gemini_model = any(target_model.lower().startswith(p) for p in ["gemini", "text-embedding"])
        if not is_gemini_model and self.ollama_url:
            try:
                resp = requests.post(
                    f"{self.ollama_url}/api/embeddings",
                    json={"model": target_model, "prompt": cleaned_text},
                    timeout=10
                )
                if resp.status_code != 200:
                    alt_model = target_model.split(":")[0] if ":" in target_model else f"{target_model}:latest"
                    resp = requests.post(
                        f"{self.ollama_url}/api/embeddings",
                        json={"model": alt_model, "prompt": cleaned_text},
                        timeout=10
                    )
                if resp.status_code == 200:
                    emb = resp.json().get("embedding", [])
                    if emb:
                        vec = np.array(emb, dtype=np.float32)
                        norm = np.linalg.norm(vec)
                        res = vec / norm if norm > 0 else vec
                        self._store_cache(cache_key, res)
                        return res
            except Exception as e:
                logger.debug(f"Ollama embedding ({target_model}) error: {e}")

        # 2. Try Google GenAI
        if self._genai_client and (is_gemini_model or not self.ollama_url):
            try:
                g_model = target_model if is_gemini_model else "gemini-embedding-001"
                response = self._genai_client.models.embed_content(
                    model=g_model,
                    contents=cleaned_text
                )
                if response.embeddings and len(response.embeddings) > 0:
                    vec = np.array(response.embeddings[0].values, dtype=np.float32)
                    norm = np.linalg.norm(vec)
                    res = vec / norm if norm > 0 else vec
                    self._store_cache(cache_key, res)
                    return res
            except Exception as e:
                logger.warning(f"Google GenAI embedding failed ({e}); falling back to local semantic embedding.")

        # 3. Deterministic local semantic embedding fallback
        res = self._local_embed(cleaned_text)
        self._store_cache(cache_key, res)
        return res

    def embed_batch(self, texts: List[str], model: Optional[str] = None) -> List[np.ndarray]:
        """Compute normalized embedding vectors for multiple texts."""
        return [self.embed_text(t, model=model) for t in texts]

    def _local_embed(self, text: str, dim: int = 384) -> np.ndarray:
        """Lightweight deterministic semantic hash + character n-gram local embedding."""
        vec = np.zeros(dim, dtype=np.float32)
        tokens = re.findall(r'\b\w+\b', text.lower())

        if not tokens:
            return vec

        for i, token in enumerate(tokens):
            # Unigram hash
            h = hash(token) % dim
            vec[h] += 1.0 / math.sqrt(i + 1)

            # Character 3-grams for subword semantic matching
            if len(token) >= 3:
                for j in range(len(token) - 2):
                    sub = token[j:j+3]
                    sub_h = hash(sub) % dim
                    vec[sub_h] += 0.4 / math.sqrt(i + 1)

            # Bigram with next token
            if i < len(tokens) - 1:
                bigram = f"{token}_{tokens[i+1]}"
                bi_h = hash(bigram) % dim
                vec[bi_h] += 1.2 / math.sqrt(i + 1)

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    @staticmethod
    def compute_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        """Calculate cosine similarity between two normalized vectors."""
        if vec_a is None or vec_b is None:
            return 0.0
        # If dimensions differ, slice to matching min dimension
        if vec_a.shape != vec_b.shape:
            min_dim = min(len(vec_a), len(vec_b))
            vec_a = vec_a[:min_dim]
            vec_b = vec_b[:min_dim]

        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)
        if norm_a == 0 or norm_b == 0:
            return 0.0

        similarity = float(np.dot(vec_a, vec_b) / (norm_a * norm_b))
        return max(-1.0, min(1.0, similarity))
